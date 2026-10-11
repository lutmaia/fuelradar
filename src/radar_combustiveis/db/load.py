"""Carga das saídas de qualidade no PostgreSQL, como instantâneo atômico e idempotente.

`staging/observations.csv` é o conjunto publicado atual: ele define quais observações são
vigentes. A carga roda numa única transação: registra a execução, sincroniza os arquivos de
origem, faz upsert das dimensões e do fato, marca como não vigentes as linhas que saíram do
instantâneo (revisão nova, precedência, regra de qualidade) sem apagá-las, reconcilia as
contagens e recalcula as agregações. Qualquer erro desfaz tudo e fica registrado como
execução `failed`.
"""

import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import uuid

import psycopg

from ..ingestion.manifest import load_manifest
from ..quality.pipeline import PUBLISHED_COLUMNS, QUARANTINE_COLUMNS
from .connection import connect


class LoadError(Exception):
    pass


def _code_sha():
    """Commit em execução, com sufixo -dirty se houver alterações; None fora de um repositório."""
    try:
        run = lambda *a: subprocess.run(["git", *a], capture_output=True, text=True, check=True).stdout.strip()  # noqa: E731
        sha = run("rev-parse", "HEAD")
        return sha + ("-dirty" if run("status", "--porcelain") else "")
    except (OSError, subprocess.CalledProcessError):
        return None


def _check_header(path, expected):
    with path.open(encoding="utf-8", newline="") as stream:
        header = next(csv.reader(stream), None)
    if header != expected:
        raise LoadError(f"Colunas de {path.name} diferentes do contrato")


def _read_quality_report(out_dir):
    path = out_dir / "quality" / "latest.json"
    if not path.exists():
        raise LoadError("Relatório de qualidade ausente: rode scripts/check_quality.py antes da carga")
    report = json.loads(path.read_text(encoding="utf-8"))
    if report["decision"] == "bloquear":
        raise LoadError("A qualidade bloqueou a publicação; nada foi carregado")
    if not report["reconciliation"]["balanced"]:
        raise LoadError("Contagens da qualidade não reconciliadas; nada foi carregado")
    return report


def _copy_csv(conn, table, columns, path):
    with conn.cursor() as cursor:
        with cursor.copy(f"COPY {table} ({', '.join(columns)}) FROM STDIN WITH (FORMAT csv, HEADER true)") as copy:
            with path.open("rb") as stream:
                while chunk := stream.read(1 << 20):
                    copy.write(chunk)


def _station_columns():
    """Atributos da estação: o valor mais recente vence, nunca um mais antigo sobre um mais novo."""
    names = ["legal_name", "trade_name", "brand", "address", "neighborhood", "postal_code", "location_id"]
    return ",\n".join(
        f"{n} = CASE WHEN excluded.last_seen_date >= dim_station.last_seen_date "
        f"THEN excluded.{n} ELSE dim_station.{n} END" for n in names)


def _sync_source_files(conn, manifest, run_id):
    entries = sorted(manifest["files"], key=lambda e: e["is_current"])  # desmarca antes de marcar
    for e in entries:  # arquivos conhecidos: apenas vigência e proveniência podem mudar
        conn.execute("""
            UPDATE source_file SET is_current = %(is_current)s,
                   source_url = coalesce(source_url, %(source_url)s),
                   retrieved_at = coalesce(retrieved_at, %(retrieved_at)s)
            WHERE source_file_id = %(source_file_id)s""", e)
    for e in entries:
        conn.execute("""
            INSERT INTO source_file (source_file_id, run_id, sha256, period_key, revision, is_current, kinds,
                                     reference_start, reference_end, source_url, retrieved_at, storage_uri,
                                     size_bytes, first_seen_at)
            VALUES (%(source_file_id)s, %(run_id)s, %(sha256)s, %(period_key)s, %(revision)s, %(is_current)s,
                    %(kinds)s, %(reference_start)s, %(reference_end)s, %(source_url)s, %(retrieved_at)s,
                    %(storage_uri)s, %(size_bytes)s, %(first_seen_at)s)
            ON CONFLICT (source_file_id) DO NOTHING""",
                     {**e, "run_id": run_id, "storage_uri": "raw/" + e["paths"][0]})


def _load_snapshot(conn, run_id, manifest, staging, quarantine, report):
    started = datetime.now(timezone.utc)
    conn.execute("INSERT INTO ingestion_run (run_id, started_at, status, code_sha, quality_run_id, quality_decision)"
                 " VALUES (%s, %s, 'running', %s, %s, %s)",
                 (run_id, started, _code_sha(), report["run_id"], report["decision"]))
    _sync_source_files(conn, manifest, run_id)

    conn.execute("CREATE TEMP TABLE stage_obs (" + ", ".join(f"{c} text" for c in PUBLISHED_COLUMNS)
                 + ") ON COMMIT DROP")
    conn.execute("CREATE TEMP TABLE stage_quarantine (" + ", ".join(f"{c} text" for c in QUARANTINE_COLUMNS)
                 + ") ON COMMIT DROP")
    _copy_csv(conn, "stage_obs", PUBLISHED_COLUMNS, staging)
    _copy_csv(conn, "stage_quarantine", QUARANTINE_COLUMNS, quarantine)
    staged = conn.execute("SELECT count(*) FROM stage_obs").fetchone()[0]
    quarantined = conn.execute("SELECT count(*) FROM stage_quarantine").fetchone()[0]
    expected = report["reconciliation"]
    if (staged, quarantined) != (expected["rows_published"], expected["rows_quarantined"]):
        raise LoadError(f"Arquivos de saída ({staged} publicadas, {quarantined} em quarentena) não batem com o "
                        f"relatório de qualidade ({expected['rows_published']}, {expected['rows_quarantined']})")

    unknown = [r[0] for r in conn.execute("""
        SELECT DISTINCT s.product FROM stage_obs s
        LEFT JOIN dim_product p ON p.canonical_name = s.product WHERE p.product_id IS NULL""")]
    if unknown:
        raise LoadError(f"Produtos fora de dim_product: {unknown}")
    missing = [r[0] for r in conn.execute("""
        SELECT DISTINCT s.source_file_id FROM (SELECT source_file_id FROM stage_obs
                                               UNION SELECT source_file_id FROM stage_quarantine) s
        LEFT JOIN source_file f USING (source_file_id) WHERE f.source_file_id IS NULL""")]
    if missing:
        raise LoadError(f"Arquivos de origem fora do manifesto: {missing}")

    conn.execute("""
        INSERT INTO dim_location (uf, municipality_name_normalized, municipality_name, region)
        SELECT DISTINCT ON (uf, municipality_normalized) uf, municipality_normalized, municipality_original, region
        FROM stage_obs
        ORDER BY uf, municipality_normalized, collection_date DESC, source_file_id DESC, source_row_number::int DESC
        ON CONFLICT (uf, municipality_name_normalized) DO UPDATE
            SET municipality_name = excluded.municipality_name,
                region = coalesce(excluded.region, dim_location.region)""")
    conn.execute(f"""
        WITH latest AS (
            SELECT DISTINCT ON (cnpj) cnpj, legal_name, trade_name, brand, address, neighborhood,
                   cep AS postal_code, uf, municipality_normalized
            FROM stage_obs
            ORDER BY cnpj, collection_date DESC, source_file_id DESC, source_row_number::int DESC),
        span AS (
            SELECT cnpj, min(collection_date::date) AS first_seen_date, max(collection_date::date) AS last_seen_date
            FROM stage_obs GROUP BY cnpj)
        INSERT INTO dim_station (cnpj, legal_name, trade_name, brand, address, neighborhood, postal_code,
                                 location_id, first_seen_date, last_seen_date)
        SELECT l.cnpj, l.legal_name, l.trade_name, l.brand, l.address, l.neighborhood, l.postal_code,
               loc.location_id, s.first_seen_date, s.last_seen_date
        FROM latest l
        JOIN span s USING (cnpj)
        JOIN dim_location loc ON loc.uf = l.uf AND loc.municipality_name_normalized = l.municipality_normalized
        ON CONFLICT (cnpj) DO UPDATE SET
            {_station_columns()},
            first_seen_date = least(dim_station.first_seen_date, excluded.first_seen_date),
            last_seen_date = greatest(dim_station.last_seen_date, excluded.last_seen_date)""")

    # Antes do upsert: libera a chave única das linhas que deixaram de ser vigentes.
    retired = conn.execute("""
        UPDATE fact_price_observation f SET is_current_source_revision = false
        WHERE f.is_current_source_revision AND NOT EXISTS (
            SELECT 1 FROM stage_obs s
            WHERE s.source_file_id = f.source_file_id AND s.source_row_hash = f.source_row_hash)""").rowcount
    changed = conn.execute("""
        WITH upsert AS (
            INSERT INTO fact_price_observation AS f (
                source_file_id, station_id, location_id, product_id, collection_date, week_start, sale_price,
                purchase_price, row_key, source_row_hash, source_row_number, quality_status, quality_flags,
                duplicate_sources, is_current_source_revision, loaded_run_id)
            SELECT s.source_file_id, st.station_id, loc.location_id, p.product_id, s.collection_date::date,
                   s.week_start::date, s.sale_price::numeric, s.purchase_price::numeric, s.row_key,
                   s.source_row_hash, s.source_row_number::int,
                   CASE WHEN coalesce(s.quality_flags, '') = '' THEN 'ok' ELSE 'warning' END,
                   coalesce(string_to_array(s.quality_flags, ';'), '{}'),
                   coalesce(string_to_array(s.duplicate_sources, ';'), '{}'), true, %(run)s
            FROM stage_obs s
            JOIN dim_station st ON st.cnpj = s.cnpj
            JOIN dim_location loc ON loc.uf = s.uf AND loc.municipality_name_normalized = s.municipality_normalized
            JOIN dim_product p ON p.canonical_name = s.product
            ON CONFLICT (source_file_id, source_row_hash) DO UPDATE SET
                is_current_source_revision = true, quality_status = excluded.quality_status,
                quality_flags = excluded.quality_flags, duplicate_sources = excluded.duplicate_sources
            WHERE (f.is_current_source_revision, f.quality_status, f.quality_flags, f.duplicate_sources)
                  IS DISTINCT FROM (true, excluded.quality_status, excluded.quality_flags, excluded.duplicate_sources)
            RETURNING (xmax = 0) AS inserted)
        SELECT count(*) FILTER (WHERE inserted), count(*) FILTER (WHERE NOT inserted) FROM upsert""",
                          {"run": run_id}).fetchone()
    inserted, updated = changed

    conn.execute("""
        UPDATE quarantine_observation q SET is_current = false
        WHERE q.is_current AND NOT EXISTS (
            SELECT 1 FROM stage_quarantine s
            WHERE s.source_file_id = q.source_file_id AND s.source_row_hash = q.source_row_hash)""")
    conn.execute("""
        INSERT INTO quarantine_observation AS q (source_file_id, source_row_number, source_row_hash,
                                                 collection_date, reasons, original, is_current, loaded_run_id)
        SELECT s.source_file_id, s.source_row_number::int, s.source_row_hash, safe_date(s.collection_date),
               string_to_array(s.quality_reasons, ';'), to_jsonb(s) - 'quality_reasons', true, %(run)s
        FROM stage_quarantine s
        ON CONFLICT (source_file_id, source_row_hash) DO UPDATE
            SET is_current = true, reasons = excluded.reasons
        WHERE (q.is_current, q.reasons) IS DISTINCT FROM (true, excluded.reasons)""", {"run": run_id})

    # Reconciliação dentro da transação: qualquer diferença desfaz a carga.
    current, = conn.execute("SELECT count(*) FROM fact_price_observation WHERE is_current_source_revision").fetchone()
    current_quarantine, = conn.execute("SELECT count(*) FROM quarantine_observation WHERE is_current").fetchone()
    if (current, current_quarantine) != (staged, quarantined):
        raise LoadError(f"Reconciliação falhou: vigentes {current} (esperado {staged}), "
                        f"quarentena {current_quarantine} (esperado {quarantined})")
    by_file = conn.execute("""
        SELECT coalesce(f.source_file_id, s.source_file_id), f.n, s.n FROM
            (SELECT source_file_id, count(*) n FROM fact_price_observation
             WHERE is_current_source_revision GROUP BY 1) f
        FULL JOIN (SELECT source_file_id, count(*) n FROM stage_obs GROUP BY 1) s USING (source_file_id)
        WHERE f.n IS DISTINCT FROM s.n""").fetchall()
    if by_file:
        raise LoadError(f"Reconciliação por arquivo falhou: {by_file}")
    stale, = conn.execute("""
        SELECT count(*) FROM fact_price_observation f JOIN source_file sf USING (source_file_id)
        WHERE f.is_current_source_revision AND NOT sf.is_current""").fetchone()
    if stale:
        raise LoadError(f"{stale} observações vigentes pertencem a uma revisão que não é a vigente")

    conn.execute("REFRESH MATERIALIZED VIEW mart_weekly_city_price")
    conn.execute("REFRESH MATERIALIZED VIEW mart_weekly_state_price")

    status = "warning" if report["decision"] == "publicar_com_aviso" else "success"
    conn.execute("""UPDATE ingestion_run SET status = %s, finished_at = %s, rows_read = %s, rows_accepted = %s,
                           rows_quarantined = %s WHERE run_id = %s""",
                 (status, datetime.now(timezone.utc), staged + quarantined, staged, quarantined, run_id))
    return {"run_id": str(run_id), "status": status, "rows_staged": staged, "rows_quarantined": quarantined,
            "inserted": inserted, "updated": updated, "unchanged": staged - inserted - updated,
            "retired": retired, "source_files": len(manifest["files"]),
            "quality_run_id": report["run_id"], "quality_decision": report["decision"]}


def _failure_summary(exc):
    """Resumo sem valores de linhas: a mensagem principal do servidor, sem o campo DETAIL."""
    if isinstance(exc, psycopg.Error) and exc.diag.message_primary:
        return f"{type(exc).__name__}: {exc.diag.message_primary}"[:500]
    return f"{type(exc).__name__}: {exc}"[:500]


def load_database(url, out_dir, quarantine_dir):
    """Carrega o instantâneo publicado. Em falha, desfaz tudo e registra uma execução `failed`."""
    out_dir, quarantine_dir = Path(out_dir).resolve(), Path(quarantine_dir).resolve()
    staging = out_dir / "staging" / "observations.csv"
    quarantine = quarantine_dir / "quality_observations.csv"
    for path in (staging, quarantine, out_dir / "manifest.json"):
        if not path.exists():
            raise LoadError(f"Arquivo ausente: {path}")
    _check_header(staging, PUBLISHED_COLUMNS)
    _check_header(quarantine, QUARANTINE_COLUMNS)
    manifest = load_manifest(out_dir / "manifest.json")
    run_id = uuid.uuid4()
    started = datetime.now(timezone.utc)
    try:
        report = _read_quality_report(out_dir)
        with connect(url) as conn:
            with conn.transaction():
                conn.execute("SELECT pg_advisory_xact_lock(7204002)")
                return _load_snapshot(conn, run_id, manifest, staging, quarantine, report)
    except Exception as exc:
        with connect(url) as conn:
            conn.execute("INSERT INTO ingestion_run (run_id, started_at, finished_at, status, code_sha, error_summary)"
                         " VALUES (%s, %s, %s, 'failed', %s, %s)",
                         (run_id, started, datetime.now(timezone.utc), _code_sha(), _failure_summary(exc)))
        raise
