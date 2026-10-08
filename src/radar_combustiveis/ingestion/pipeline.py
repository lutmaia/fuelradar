"""Ingestão local: varre data/raw, atualiza o manifesto e grava observações do recorte configurado.

Nunca altera data/raw. Cada versão de arquivo (SHA-256) tem a própria saída; revisões novas
não apagam as anteriores. Sem banco: a saída é CSV, a ser carregada no PostgreSQL pelo Marco 4.
"""

import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import uuid

from .manifest import load_manifest, register, save_manifest, write_text_atomic
from .observations import OBSERVATION_COLUMNS, REJECTED_COLUMNS, normalize_row, row_hash
from .readers import SourceFormatError, iter_tables, sha256

SUPPORTED_SUFFIXES = {".csv", ".xlsx", ".zip"}


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _check_output_dir(raw_dir, output_dir):
    if output_dir == raw_dir or raw_dir in output_dir.parents:
        raise ValueError(f"Saída não pode ficar dentro de data/raw: {output_dir}")


def scan_raw(raw_dir):
    """Lista os arquivos suportados, com SHA-256, tamanho e data de modificação (não altera nada)."""
    found = []
    for path in sorted(raw_dir.rglob("*")):
        if not path.is_file() or path.name.startswith(".") or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        stat = path.stat()
        found.append({"path": path.relative_to(raw_dir).as_posix(), "absolute": path,
                      "sha256": sha256(path), "size_bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns})
    return found


def detect_kinds(path):
    """Tipos de tabela do arquivo (retail_observation, monthly_aggregate, weekly_aggregate)."""
    return {table.kind for table in iter_tables(path)}


def _needs_ingestion(entry, out_dir, target_ufs):
    if not entry["is_current"] or "retail_observation" not in entry["kinds"]:
        return False
    done = entry["ingestion"]
    return (done is None or done["target_ufs"] != list(target_ufs)
            or not (out_dir / done["output"]).exists())


def ingest_file(entry, source, target_ufs, run_id, out_dir, quarantine_dir):
    """Normaliza as tabelas de observações e publica a saída só se o arquivo inteiro for lido."""
    file_id = entry["source_file_id"]
    output = out_dir / "observations" / f"{file_id}.csv"
    rejected = quarantine_dir / f"{file_id}_rejected.csv"
    temps = [output.with_name(output.name + ".tmp"), rejected.with_name(rejected.name + ".tmp")]
    for temp in temps:
        temp.parent.mkdir(parents=True, exist_ok=True)
    counts = {"rows_read": 0, "rows_accepted": 0, "rows_out_of_scope": 0, "rows_rejected": 0,
              "duplicate_keys": 0, "rows_automotive": 0, "rows_glp": 0, "rows_unknown_product": 0}
    keys, municipalities, cnpjs, dates = set(), set(), set(), []
    published = False
    try:
        with temps[0].open("w", encoding="utf-8", newline="") as obs_stream, \
                temps[1].open("w", encoding="utf-8", newline="") as rej_stream:
            observations = csv.DictWriter(obs_stream, OBSERVATION_COLUMNS, lineterminator="\n")
            rejections = csv.DictWriter(rej_stream, REJECTED_COLUMNS, lineterminator="\n")
            observations.writeheader()
            rejections.writeheader()
            for table in iter_tables(source):
                if table.kind != "retail_observation":
                    continue
                for number, values in table.rows:
                    counts["rows_read"] += 1
                    status, observation, reason = normalize_row(table, values, target_ufs)
                    if status == "out_of_scope":
                        counts["rows_out_of_scope"] += 1
                    elif status == "rejected":
                        counts["rows_rejected"] += 1
                        rejections.writerow({"source_row_number": number, "reason": reason,
                                             "original_values": json.dumps(values, default=str, ensure_ascii=False)})
                    else:
                        counts["rows_accepted"] += 1
                        observation.update(
                            source_file_id=file_id, source_sha256=entry["sha256"],
                            source_member=table.member, source_sheet=table.sheet,
                            source_row_number=number, source_row_hash=row_hash(values),
                            ingestion_run_id=run_id)
                        observations.writerow(observation)
                        counts[{"automotivo": "rows_automotive", "glp": "rows_glp"}.get(
                            observation["product_category"], "rows_unknown_product")] += 1
                        if observation["row_key"]:
                            if observation["row_key"] in keys:
                                counts["duplicate_keys"] += 1
                            keys.add(observation["row_key"])
                        municipalities.add(observation["municipality_normalized"])
                        if observation["cnpj"]:
                            cnpjs.add(observation["cnpj"])
                        dates.append(observation["collection_date"])
        os.replace(temps[0], output)
        os.replace(temps[1], rejected)
        published = True
    finally:
        if not published:
            for temp in temps:
                temp.unlink(missing_ok=True)
    return {**counts, "municipalities": len(municipalities), "unique_cnpj": len(cnpjs),
            "collection_date_min": min(dates) if dates else None,
            "collection_date_max": max(dates) if dates else None,
            "output": f"observations/{file_id}.csv", "quarantine": f"{file_id}_rejected.csv"}


def run_ingestion(raw_dir, out_dir, quarantine_dir, target_ufs):
    raw_dir, out_dir, quarantine_dir = (Path(p).resolve() for p in (raw_dir, out_dir, quarantine_dir))
    if not raw_dir.is_dir():
        raise ValueError(f"Pasta raw inexistente: {raw_dir}")
    _check_output_dir(raw_dir, out_dir)
    _check_output_dir(raw_dir, quarantine_dir)
    target_ufs = tuple(target_ufs)
    started = _now()
    run_id = str(uuid.uuid4())
    manifest_path = out_dir / "manifest.json"
    manifest = load_manifest(manifest_path)
    report = {"run_id": run_id, "started_at": started, "target_ufs": list(target_ufs),
              "raw_dir": str(raw_dir), "events": [], "ingested": [], "errors": []}

    found = scan_raw(raw_dir)
    known = {e["sha256"] for e in manifest["files"]}
    registrable = []
    for item in found:
        if item["sha256"] not in known:
            try:
                item["kinds"] = detect_kinds(item["absolute"])
            except (SourceFormatError, ValueError, OSError) as exc:
                report["errors"].append({"path": item["path"], "stage": "detect", "error": str(exc)})
                continue
        registrable.append(item)
    for event, entry in register(manifest, registrable, started):
        report["events"].append({"event": event, "source_file_id": entry["source_file_id"],
                                 "period_key": entry["period_key"], "revision": entry["revision"],
                                 "paths": entry["paths"], "kinds": entry["kinds"]})

    by_path = {item["path"]: item["absolute"] for item in found}
    for entry in manifest["files"]:
        if not _needs_ingestion(entry, out_dir, target_ufs):
            continue
        source = next((by_path[p] for p in entry["paths"] if p in by_path), None)
        if source is None:
            report["errors"].append({"path": entry["paths"][0], "stage": "locate",
                                     "error": "Arquivo do manifesto não encontrado em raw"})
            continue
        try:
            stats = ingest_file(entry, source, target_ufs, run_id, out_dir, quarantine_dir)
        except (SourceFormatError, ValueError, OSError) as exc:
            report["errors"].append({"path": entry["paths"][0], "stage": "ingest", "error": str(exc)})
            continue
        if entry["reference_start"] is None:
            entry["reference_start"], entry["reference_end"] = (
                stats["collection_date_min"], stats["collection_date_max"])
        entry["ingestion"] = {"run_id": run_id, "ingested_at": _now(), "target_ufs": list(target_ufs), **stats}
        report["ingested"].append({"source_file_id": entry["source_file_id"], "path": entry["paths"][0], **stats})

    changed = [item["path"] for item in found if sha256(item["absolute"]) != item["sha256"]]
    if changed:
        raise RuntimeError(f"Arquivos de raw mudaram durante a execução: {changed}")
    report["raw_unchanged"] = True
    report["manifest_written"] = save_manifest(manifest_path, manifest)
    report["finished_at"] = _now()
    write_text_atomic(out_dir / "runs" / f"{run_id}.json",
                      json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return report
