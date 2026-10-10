"""Qualidade sobre as observações ingeridas: regras críticas, regras de linha, quarentena,
deduplicação entre fontes, cobertura e relatório (arquitetura, seção 12).

Lê só as saídas da ingestão (manifesto e observações das revisões atuais). Uma falha crítica
bloqueia a publicação e mantém a saída anterior. Sem banco: a saída é CSV, para o Marco 4.
"""

from collections import Counter, defaultdict
import csv
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import statistics
import uuid

from ..ingestion.manifest import load_manifest, write_text_atomic
from ..ingestion.normalize import normalize_text
from ..ingestion.observations import OBSERVATION_COLUMNS
from .rules import (
    EXTREME_WINDOW_WEEKS, OUT_OF_SCOPE_PRODUCTS, canonical_price, parse_decimal, price_bounds,
    row_reasons, week_start,
)

PUBLISHED_COLUMNS = OBSERVATION_COLUMNS + ["brand_normalized", "week_start", "quality_flags", "duplicate_sources"]
QUARANTINE_COLUMNS = OBSERVATION_COLUMNS + ["week_start", "quality_reasons"]
COVERAGE_COLUMNS = ["municipality_normalized", "product", "week_start", "observations", "stations",
                    "baseline_median_stations", "ratio_to_baseline", "low_coverage"]
SERIES_COLUMNS = ["municipality_normalized", "product", "weeks_present", "weeks_in_range",
                  "share_weeks_present", "first_week", "last_week"]

REDUCTION_MIN_SHARE = 0.5       # semana com menos da metade da mediana das anteriores é bloqueada
REDUCTION_MIN_HISTORY = 3       # semanas anteriores necessárias para avaliar a redução
LOW_COVERAGE_SHARE = 0.5        # postos abaixo da metade da mediana das 8 semanas anteriores
LOW_COVERAGE_MIN_BASELINE = 3   # mediana mínima de postos para avaliar a queda
RECURRING_MIN_WEEKS = 6         # presente em 6 das 8 semanas anteriores = série/localidade recorrente
WARN_QUARANTINE_SHARE = 0.01    # mais de 1% em quarentena → publicar com aviso
WARN_DELAY_DAYS = 14            # mais de 14 dias desde a última coleta → publicar com aviso
SAMPLE_SIZE = 5
# Amostra sanitizada: sem CNPJ, razão social nem endereço.
SAMPLE_FIELDS = ["source_file_id", "source_row_number", "municipality_normalized", "product",
                 "unit", "collection_date", "sale_price"]

# Linha da 1ª passagem: (status, motivos, avisos, row_key, preço, data, "arquivo:linha da fonte").
# status: candidate (publicável), quarantine, duplicate (cópia idêntica removida), out_of_scope (GLP).


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _iso(value):
    return date.fromisoformat(value) if value else None


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_rows(path):
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != OBSERVATION_COLUMNS:
            raise ValueError(f"Colunas da observação diferentes do contrato: {path.name}")
        yield from reader


class _CsvOutput:
    """Escreve num arquivo temporário; `close(True)` só substitui o destino se o conteúdo mudou,
    e `close(False)` descarta tudo, preservando a saída anterior. Devolve se substituiu."""

    def __init__(self, path, columns):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path, self.temp = path, path.with_name(path.name + ".tmp")
        self.stream = self.temp.open("w", encoding="utf-8", newline="")
        self.writer = csv.DictWriter(self.stream, columns, lineterminator="\n", extrasaction="ignore")
        self.writer.writeheader()

    def write(self, row):
        self.writer.writerow(row)

    def close(self, publish):
        self.stream.close()
        if not publish or (self.path.exists() and _digest(self.path) == _digest(self.temp)):
            self.temp.unlink()
            return False
        os.replace(self.temp, self.path)
        return True


def _current_sources(manifest):
    """Revisões atuais com observações individuais, na ordem do manifesto."""
    return [e for e in manifest["files"] if e["is_current"] and "retail_observation" in e["kinds"]]


def _is_weekly(entry):
    start, end = _iso(entry["reference_start"]), _iso(entry["reference_end"])
    return bool(start and end and (end - start).days <= 7)


def _precedence(entry):
    """Entre cópias idênticas de uma chave, fica a do arquivo de período mais curto (a semana
    publicada), depois a de início mais antigo e, por fim, o identificador."""
    start, end = _iso(entry["reference_start"]), _iso(entry["reference_end"])
    length = (end - start).days if start and end else 10 ** 6
    return length, entry["reference_start"] or "", entry["source_file_id"]


def _scan_file(entry, path, as_of):
    """1ª passagem: motivos e chaves de cada linha, sem guardar a linha inteira na memória."""
    period = (_iso(entry["reference_start"]), _iso(entry["reference_end"]))
    rows, positions = [], Counter()
    in_period = 0
    for row in _read_rows(path):
        positions[(row["source_member"], row["source_sheet"], row["source_row_number"])] += 1
        source = f"{entry['source_file_id']}:{row['source_row_number']}"
        if row["product"] in OUT_OF_SCOPE_PRODUCTS:
            rows.append(("out_of_scope", (), (), "", None, None, source))
            continue
        reasons, flags = row_reasons(row, period, as_of)
        day = None if "data_invalida" in reasons else _iso(row["collection_date"])
        if day and period[0] and period[0] <= day <= period[1]:
            in_period += 1
        rows.append(("quarantine" if reasons else "candidate", tuple(reasons), tuple(flags),
                     row["row_key"], parse_decimal(row["sale_price"]), day, source))
    repeated = sum(n - 1 for n in positions.values() if n > 1)
    return rows, in_period, repeated


def _critical_checks(entry, rows, in_period, repeated, weekly_history):
    """Regras críticas de um arquivo (seção 12.1). Coluna ausente e formato ilegível já impedem
    a ingestão e aparecem aqui como arquivo não ingerido ou colunas inválidas."""
    failures = []
    evaluated = [r for r in rows if r[0] != "out_of_scope"]
    if not rows:
        failures.append("arquivo_vazio")
    if entry["reference_start"] and evaluated and in_period == 0:
        failures.append("nenhuma_data_no_periodo")
    if evaluated and not any(r[0] == "candidate" for r in evaluated):
        failures.append("nenhum_preco_valido")
    if repeated or len(rows) != entry["ingestion"]["rows_accepted"]:
        failures.append("duplicacao_da_carga")
    if weekly_history is not None and len(weekly_history) >= REDUCTION_MIN_HISTORY:
        if len(rows) < REDUCTION_MIN_SHARE * statistics.median(weekly_history):
            failures.append("reducao_extrema")
    return failures


def _resolve_duplicates(scanned, order):
    """Mesma chave em várias linhas: preços numericamente iguais → fica uma cópia; preços
    diferentes → todas vão para a quarentena. Devolve {(arquivo, índice): cópias removidas}."""
    by_key = defaultdict(list)
    for file_id, rows in scanned.items():
        for index, row in enumerate(rows):
            if row[0] == "candidate":
                by_key[row[3]].append((file_id, index))
    removed = {}
    for copies in by_key.values():
        if len(copies) == 1:
            continue
        if len({scanned[f][i][4] for f, i in copies}) > 1:
            for f, i in copies:
                scanned[f][i] = ("quarantine", ("conflito_de_preco_mesma_chave",)) + scanned[f][i][2:]
            continue
        copies.sort(key=lambda c: (order[c[0]], c[1]))
        removed[copies[0]] = copies[1:]
        for f, i in copies[1:]:
            scanned[f][i] = ("duplicate",) + scanned[f][i][1:]
    return removed


def _product_unit(row):
    return tuple(row[3].split("|")[3:5])  # row_key: uf|município|cnpj|produto|unidade|data


def _flag_extremes(scanned):
    """Janela de nove semanas do mesmo produto e unidade: preço implausível → quarentena;
    preço fora da cerca IQR → aviso `preco_extremo`, sem excluir a linha."""
    by_week = defaultdict(list)
    for rows in scanned.values():
        for row in rows:
            if row[0] == "candidate":
                by_week[(*_product_unit(row), week_start(row[5]))].append(row[4])
    fences = {}
    for product, unit, week in by_week:
        window = [p for back in range(EXTREME_WINDOW_WEEKS + 1)
                  for p in by_week.get((product, unit, week - timedelta(weeks=back)), [])]
        fences[(product, unit, week)] = price_bounds(window)
    for rows in scanned.values():
        for index, row in enumerate(rows):
            bounds = fences[(*_product_unit(row), week_start(row[5]))] if row[0] == "candidate" else None
            if bounds is None:
                continue
            low, high = bounds["plausible"]
            if not low <= row[4] <= high:
                rows[index] = ("quarantine", ("preco_implausivel",)) + row[2:]
            elif not bounds["fence"][0] <= row[4] <= bounds["fence"][1]:
                rows[index] = row[:2] + (row[2] + ("preco_extremo",),) + row[3:]


def _write_rows(sources, scanned, paths, removed, published, quarantined, counts, samples, cells):
    """2ª passagem: relê cada arquivo na mesma ordem e grava a linha publicada ou em quarentena,
    com campos padronizados (preço canônico, semana e bandeira normalizada)."""
    for entry in sources:
        file_id = entry["source_file_id"]
        if file_id not in scanned:
            continue
        for index, row in enumerate(_read_rows(paths[file_id])):
            status, reasons, flags, _, _, day, _ = scanned[file_id][index]
            counts[f"rows_{status}"] += 1
            if status in {"out_of_scope", "duplicate"}:
                continue
            row["week_start"] = week_start(day).isoformat() if day else ""
            row["sale_price"] = canonical_price(parse_decimal(row["sale_price"])) or row["sale_price"]
            row["purchase_price"] = canonical_price(parse_decimal(row["purchase_price"])) or row["purchase_price"]
            if status == "quarantine":
                row["quality_reasons"] = ";".join(reasons)
                quarantined.write(row)
                for reason in reasons:
                    counts[f"reason:{reason}"] += 1
                    if len(samples[reason]) < SAMPLE_SIZE:
                        samples[reason].append({k: row[k] for k in SAMPLE_FIELDS})
                continue
            for flag in flags:
                counts[f"flag:{flag}"] += 1
            row["brand_normalized"] = normalize_text(row["brand"])
            row["quality_flags"] = ";".join(flags)
            row["duplicate_sources"] = ";".join(scanned[f][i][6] for f, i in removed.get((file_id, index), []))
            published.write(row)
            cell = cells[(row["municipality_normalized"], row["product"], week_start(day))]
            cell[0] += 1
            cell[1].add(row["cnpj"])


def _coverage(cells, days, as_of):
    """Cobertura por município, produto e semana (seção 12.3) sobre as linhas publicadas.

    `cells` mapeia (município, produto, semana) para [observações, CNPJs] publicados; `days` são
    as datas de coleta de todas as linhas avaliadas. Semanas ausentes
    contam como zero postos na mediana das oito anteriores.
    """
    empty = {"latest_week": None, "last_collection_date": None, "delay_days": None,
             "weekdays_without_collection": [], "low_coverage_latest_week": 0,
             "recurring_absent_latest_week": []}
    if not cells:
        return [], [], empty
    weeks = sorted({k[2] for k in cells})
    all_weeks = [weeks[0] + timedelta(weeks=n) for n in range((weeks[-1] - weeks[0]).days // 7 + 1)]
    stations = lambda m, p, w: len(cells[(m, p, w)][1]) if (m, p, w) in cells else 0  # noqa: E731
    coverage, summary = [], []
    for municipality, product in sorted({k[:2] for k in cells}):
        present = [w for w in all_weeks if (municipality, product, w) in cells]
        summary.append({"municipality_normalized": municipality, "product": product,
                        "weeks_present": len(present), "weeks_in_range": len(all_weeks),
                        "share_weeks_present": f"{len(present) / len(all_weeks):.3f}",
                        "first_week": present[0].isoformat(), "last_week": present[-1].isoformat()})
        for index, week in enumerate(all_weeks):
            cell = cells.get((municipality, product, week))
            previous = [stations(municipality, product, w) for w in all_weeks[max(0, index - 8):index]]
            if cell is None and sum(1 for n in previous if n) < RECURRING_MIN_WEEKS:
                continue  # ausência só é registrada para séries recorrentes
            current = stations(municipality, product, week)
            baseline = statistics.median(previous) if len(previous) == 8 else None
            low = (baseline is not None and baseline >= LOW_COVERAGE_MIN_BASELINE
                   and current < LOW_COVERAGE_SHARE * baseline)
            coverage.append({"municipality_normalized": municipality, "product": product,
                             "week_start": week.isoformat(), "observations": cell[0] if cell else 0,
                             "stations": current,
                             "baseline_median_stations": "" if baseline is None else f"{baseline:g}",
                             "ratio_to_baseline": f"{current / baseline:.3f}" if baseline else "",
                             "low_coverage": "true" if low else "false"})
    latest = all_weeks[-1]
    by_week = defaultdict(set)
    for municipality, _, week in cells:
        by_week[week].add(municipality)
    recent = all_weeks[-9:-1]
    recurring = set()
    if len(recent) == 8:
        recurring = {m for m in set().union(*(by_week[w] for w in recent))
                     if sum(m in by_week[w] for w in recent) >= RECURRING_MIN_WEEKS}
    first, last = min(days), max(days)
    calendar = (first + timedelta(days=n) for n in range((last - first).days + 1))
    return coverage, summary, {
        "latest_week": latest.isoformat(),
        "last_collection_date": last.isoformat(),
        "delay_days": (as_of - last).days,
        "weekdays_without_collection": [d.isoformat() for d in calendar if d.weekday() < 5 and d not in days],
        "low_coverage_latest_week": sum(1 for c in coverage
                                        if c["week_start"] == latest.isoformat() and c["low_coverage"] == "true"),
        "recurring_absent_latest_week": sorted(recurring - by_week[latest]),
    }


def _compare(previous, counts):
    if previous is None:
        return None
    keys = sorted(set(previous["counts"]) | set(counts))
    return {"previous_run_id": previous["run_id"],
            "delta": {k: counts.get(k, 0) - previous["counts"].get(k, 0) for k in keys
                      if counts.get(k, 0) != previous["counts"].get(k, 0)}}


def run_quality(out_dir, quarantine_dir, as_of=None):
    out_dir, quarantine_dir = Path(out_dir).resolve(), Path(quarantine_dir).resolve()
    as_of = as_of or datetime.now(timezone.utc).date()
    run_id = str(uuid.uuid4())
    report = {"run_id": run_id, "started_at": _now(), "as_of": as_of.isoformat(), "files": [],
              "critical_failures": [], "errors": []}
    sources = _current_sources(load_manifest(out_dir / "manifest.json"))
    if not sources:
        report["critical_failures"].append({"source_file_id": None, "rule": "nenhuma_fonte_ingerida"})

    scanned, paths, order, weekly_sizes = {}, {}, {}, []
    for entry in sorted(sources, key=lambda e: (e["reference_start"] or "", e["source_file_id"])):
        file_id = entry["source_file_id"]
        result = {"source_file_id": file_id, "period_key": entry["period_key"], "rows": None, "critical": []}
        report["files"].append(result)
        path = out_dir / entry["ingestion"]["output"] if entry["ingestion"] else None
        if path is None or not path.exists():
            result["critical"].append("arquivo_nao_ingerido")
            continue
        try:
            rows, in_period, repeated = _scan_file(entry, path, as_of)
        except (ValueError, OSError) as exc:
            result["critical"].append("colunas_ou_formato_invalidos")
            report["errors"].append({"source_file_id": file_id, "error": str(exc)})
            continue
        weekly = _is_weekly(entry)
        result["rows"] = len(rows)
        result["critical"] = _critical_checks(entry, rows, in_period, repeated,
                                              weekly_sizes[-8:] if weekly else None)
        if weekly:
            weekly_sizes.append(len(rows))
        scanned[file_id], paths[file_id], order[file_id] = rows, path, _precedence(entry)
    report["files"].sort(key=lambda f: f["period_key"])
    report["critical_failures"] += [{"source_file_id": f["source_file_id"], "rule": rule}
                                    for f in report["files"] for rule in f["critical"]]

    removed = _resolve_duplicates(scanned, order)
    _flag_extremes(scanned)

    counts, samples = Counter(), defaultdict(list)
    cells = defaultdict(lambda: [0, set()])
    quality_dir = out_dir / "quality"
    published = _CsvOutput(out_dir / "staging" / "observations.csv", PUBLISHED_COLUMNS)
    quarantined = _CsvOutput(quarantine_dir / "quality_observations.csv", QUARANTINE_COLUMNS)
    try:
        _write_rows(sources, scanned, paths, removed, published, quarantined, counts, samples, cells)
    except BaseException:
        published.close(False)
        quarantined.close(False)
        raise
    counts["rows_published"] = counts.pop("rows_candidate", 0)

    rows_read = sum(len(r) for r in scanned.values())
    expected = sum(e["ingestion"]["rows_accepted"] for e in sources if e["source_file_id"] in scanned)
    outcome = {"rows_published": counts["rows_published"], "rows_quarantined": counts["rows_quarantine"],
               "rows_duplicate_removed": counts["rows_duplicate"],
               "rows_out_of_scope_product": counts["rows_out_of_scope"]}
    report["reconciliation"] = {"rows_ingested": expected, "rows_read": rows_read, **outcome,
                                "balanced": expected == rows_read == sum(outcome.values())}
    if not report["reconciliation"]["balanced"]:
        report["critical_failures"].append({"source_file_id": None, "rule": "contagens_nao_reconciliadas"})

    # Dias de coleta de todas as linhas avaliadas, publicadas ou em quarentena (sem GLP).
    days = {r[5] for rows in scanned.values() for r in rows if r[0] != "out_of_scope" and r[5]}
    coverage, summary, status = _coverage(cells, days, as_of)
    report["coverage"] = status
    report["counts"] = dict(sorted(counts.items()))
    report["samples"] = dict(sorted(samples.items()))
    latest_path = quality_dir / "latest.json"
    previous = json.loads(latest_path.read_text(encoding="utf-8")) if latest_path.exists() else None
    report["comparison"] = _compare(previous, report["counts"])

    share = counts["rows_quarantine"] / rows_read if rows_read else 0
    warnings = []
    if share > WARN_QUARANTINE_SHARE:
        warnings.append(f"quarentena acima de {WARN_QUARANTINE_SHARE:.0%}: {share:.2%}")
    if status["low_coverage_latest_week"]:
        warnings.append(f"cobertura baixa em {status['low_coverage_latest_week']} séries na última semana")
    if status["recurring_absent_latest_week"]:
        warnings.append(f"{len(status['recurring_absent_latest_week'])} municípios recorrentes ausentes na última semana")
    if status["delay_days"] is not None and status["delay_days"] > WARN_DELAY_DAYS:
        warnings.append(f"última coleta há {status['delay_days']} dias")
    report["warnings"] = warnings
    report["decision"] = ("bloquear" if report["critical_failures"]
                          else "publicar_com_aviso" if warnings else "publicar")

    publish = report["decision"] != "bloquear"
    written = {"staging/observations.csv": published.close(publish),
               "quarantine/quality_observations.csv": quarantined.close(publish)}
    for name, columns, rows in (("coverage_weekly.csv", COVERAGE_COLUMNS, coverage),
                                ("coverage_series.csv", SERIES_COLUMNS, summary)):
        output = _CsvOutput(quality_dir / name, columns)
        for row in rows:
            output.write(row)
        written[f"quality/{name}"] = output.close(publish)
    report["outputs_written"] = written
    report["finished_at"] = _now()
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    write_text_atomic(quality_dir / "runs" / f"{run_id}.json", text)
    write_text_atomic(latest_path, text)
    return report
