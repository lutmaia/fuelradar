"""Download, leitura, qualidade e carga das três fontes externas, fonte por fonte.

Uma fonte bloqueada pela qualidade não é carregada e não impede as outras (desenho, 4.4).
O relatório vai para data/processed/external/quality.json.
"""

from datetime import date, datetime, timezone
import json
from pathlib import Path

from . import fetch, load, parse, quality
from .sources import DISTRIBUTION, DOLLAR, PRODUCERS, SOURCES

READERS = {
    DOLLAR.source_id: lambda path, ufs: parse.parse_dollar(Path(path).read_bytes()),
    PRODUCERS.source_id: lambda path, ufs: parse.parse_producers(path),
    DISTRIBUTION.source_id: parse.parse_distribution,
}


def run(raw_dir, processed_dir, target_ufs, conn=None, download=True, now=None, today=None):
    now = now or datetime.now(timezone.utc)
    today = today or now.date()
    raw_dir, out = Path(raw_dir), Path(processed_dir) / "external"
    log = out / "downloads.jsonl"
    report = {"run_at": now.isoformat(timespec="seconds"), "download": None, "sources": {}}
    if download:
        report["download"] = fetch.download(raw_dir, log, now)
    files = fetch.latest_files(log)
    for source_id in SOURCES:
        parsed, errors = [], []
        for (sid, name), record in sorted(files.items()):
            if sid != source_id:
                continue
            try:
                parsed.append((record, READERS[source_id](raw_dir / record["raw_path"], target_ufs)))
            except (parse.FormatError, OSError, ValueError) as exc:
                errors.append(f"{name}: {exc}")
        rows = [r for _, file_rows in parsed for r in file_rows]
        result = quality.check(source_id, rows, today)
        if errors:
            result["critical"] = errors + result["critical"]
            result["critical_total"] += len(errors)
            result["decision"] = "bloquear"
        result["files"] = [record["raw_path"] for record, _ in parsed]
        if conn is not None and result["decision"] != "bloquear":
            result["load"] = load.load_source(conn, source_id, parsed)
        report["sources"][source_id] = result
    out.mkdir(parents=True, exist_ok=True)
    (out / "quality.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=_json),
                                      encoding="utf-8")
    return report


def _json(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError(type(value))
