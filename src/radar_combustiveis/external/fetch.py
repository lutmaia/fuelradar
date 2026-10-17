"""Download das fontes externas para data/raw/external/<fonte>/retrieved_at=<instante>/<arquivo>.

Reaproveita o cliente da ingestão da ANP (tentativas, limite de tamanho, download incompleto). Só
guarda conteúdo novo (SHA-256 desconhecido), nunca sobrescreve, e registra cada tentativa em
data/processed/external/downloads.jsonl. Se um download falha, a última versão guardada continua valendo.
"""

import hashlib
from pathlib import Path
import shutil
import tempfile

from ..ingestion.download import DownloadError, append_log, fetch_to_file, read_log
from .sources import (DISTRIBUTION, DISTRIBUTION_FILES, DISTRIBUTION_URL, DOLLAR, DOLLAR_URL, HISTORY_START,
                      PRODUCERS, PRODUCERS_URL)

XLS_MAGIC = b"\xd0\xcf\x11\xe0"
XLSX_MAGIC = b"PK\x03\x04"


def targets(today):
    """(fonte, nome do arquivo, URL) de tudo que as fontes externas baixam."""
    dollar = DOLLAR_URL.format(start=HISTORY_START.strftime("%d/%m/%Y"), end=today.strftime("%d/%m/%Y"))
    return ([(DOLLAR.source_id, "sgs1.json", dollar), (PRODUCERS.source_id, "precos-medios-ponderados-semanais-2013.xls",
                                                       PRODUCERS_URL)]
            + [(DISTRIBUTION.source_id, f"{name}.xlsx", DISTRIBUTION_URL.format(name=name))
               for name in DISTRIBUTION_FILES])


def check_content(name, head):
    if name.endswith(".xls") and not head.startswith(XLS_MAGIC):
        raise DownloadError(f"Conteúdo não parece XLS (início {head[:4]!r})")
    if name.endswith(".xlsx") and not head.startswith(XLSX_MAGIC):
        raise DownloadError(f"Conteúdo não parece XLSX (início {head[:4]!r})")
    if name.endswith(".json") and not head.lstrip().startswith(b"["):
        raise DownloadError(f"Conteúdo não parece a lista JSON do BCB (início {head[:8]!r})")


def download(raw_dir, log_path, now, items=None, **fetch_options):
    """Baixa cada alvo; devolve o relatório. `now` é injetado para testes."""
    raw_dir = Path(raw_dir).resolve()
    records = read_log(log_path)
    known = {r["sha256"]: r["raw_path"] for r in records if r.get("action") == "saved"}
    stamp = now.strftime("%Y-%m-%dT%H-%M-%SZ")
    report = {"retrieved_at": now.isoformat(timespec="seconds"), "saved": [], "duplicate": [], "errors": []}
    for source_id, name, url in items or targets(now.date()):
        record = {"source_id": source_id, "name": name, "url": url, "retrieved_at": now.isoformat(timespec="seconds")}
        with tempfile.TemporaryDirectory() as folder:
            temp = Path(folder) / name
            try:
                info = fetch_to_file(url, temp, **fetch_options)
                check_content(name, info["head"])
            except DownloadError as exc:
                record.update(action="error", error=str(exc))
                report["errors"].append({"source_id": source_id, "name": name, "error": str(exc)})
            else:
                record.update(sha256=info["sha256"], size_bytes=info["size_bytes"])
                if info["sha256"] in known:
                    record.update(action="duplicate", raw_path=known[info["sha256"]])
                    report["duplicate"].append(name)
                else:
                    target = raw_dir / "external" / source_id / f"retrieved_at={stamp}" / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    problem = None
                    try:
                        with open(temp, "rb") as src, open(target, "xb") as dst:  # 'x': nunca sobrescreve
                            shutil.copyfileobj(src, dst)
                    except FileExistsError:
                        problem = f"Destino já existe e não será sobrescrito: {target.name}"
                    else:
                        if hashlib.sha256(target.read_bytes()).hexdigest() != info["sha256"]:
                            target.unlink()
                            problem = f"Cópia para raw divergiu do download: {name}"
                    if problem:
                        record.update(action="error", error=problem)
                        report["errors"].append({"source_id": source_id, "name": name, "error": problem})
                    else:
                        raw_path = target.relative_to(raw_dir).as_posix()
                        known[info["sha256"]] = raw_path
                        record.update(action="saved", raw_path=raw_path)
                        report["saved"].append(raw_path)
        append_log(log_path, record)
    return report


def latest_files(log_path):
    """Para cada (fonte, arquivo), o último download bem-sucedido: {(fonte, nome): registro}.

    O registro traz `raw_path`, `sha256` e `retrieved_at`, mais `first_retrieved_at` desse conteúdo."""
    latest, first_seen = {}, {}
    for record in read_log(log_path):
        if record.get("action") not in {"saved", "duplicate"}:
            continue
        first_seen.setdefault(record["sha256"], record["retrieved_at"])
        latest[(record["source_id"], record["name"])] = record
    return {key: {**rec, "first_retrieved_at": first_seen[rec["sha256"]]} for key, rec in latest.items()}
