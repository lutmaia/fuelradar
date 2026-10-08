"""Manifesto de arquivos brutos: identidade por SHA-256, revisões por período e escrita atômica.

O manifesto nunca fica em data/raw. Ele só descreve os arquivos; não os copia nem altera.
"""

import json
import os
from pathlib import Path
import re

MANIFEST_VERSION = 1
_PERIOD_IN_NAME = re.compile(r"(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})")


def empty_manifest():
    return {"manifest_version": MANIFEST_VERSION, "files": []}


def load_manifest(path):
    path = Path(path)
    if not path.exists():
        return empty_manifest()
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("manifest_version") != MANIFEST_VERSION:
        raise ValueError(f"Versão de manifesto não suportada: {manifest.get('manifest_version')!r}")
    return manifest


def serialize(manifest):
    return json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def save_manifest(path, manifest):
    """Grava de forma atômica e só se o conteúdo mudou. Devolve se gravou."""
    path = Path(path)
    text = serialize(manifest)
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    write_text_atomic(path, text)
    return True


def write_text_atomic(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temp, path)


def period_key(path):
    """Identidade do período: o nome do arquivo sem extensão.

    Mesmo nome com outro SHA-256 é tratado como revisão do mesmo período. O nome identifica
    o período publicado, não as datas de coleta que o arquivo contém.
    """
    return Path(path).stem


def reference_period(path):
    """(início, fim) em ISO quando o nome traz o período, como nas semanas por revenda."""
    match = _PERIOD_IN_NAME.search(Path(path).name)
    return (match.group(1), match.group(2)) if match else (None, None)


def find_by_sha(manifest, sha256):
    return next((e for e in manifest["files"] if e["sha256"] == sha256), None)


def register(manifest, found, now):
    """Atualiza o manifesto com os arquivos encontrados em disco.

    `found` é uma lista de dicts com path (relativo ao raw, em POSIX), sha256, size_bytes,
    mtime_ns e kinds (obrigatório só para SHA-256 ainda desconhecido).
    Devolve a lista de eventos: ("new", entrada), ("revision", entrada) ou ("alias", entrada).
    """
    events = []
    ordered = sorted(found, key=lambda f: (f["mtime_ns"], f["path"]))
    for item in ordered:
        entry = find_by_sha(manifest, item["sha256"])
        if entry is not None:
            if item["path"] not in entry["paths"]:
                entry["paths"] = sorted(entry["paths"] + [item["path"]])
                events.append(("alias", entry))
            continue
        key = period_key(item["path"])
        previous = [e for e in manifest["files"] if e["period_key"] == key]
        for old in previous:
            old["is_current"] = False
        start, end = reference_period(item["path"])
        entry = {
            "source_file_id": item["sha256"][:16],
            "sha256": item["sha256"],
            "size_bytes": item["size_bytes"],
            "paths": [item["path"]],
            "kinds": sorted(item["kinds"]),
            "period_key": key,
            "reference_start": start,
            "reference_end": end,
            "revision": max((e["revision"] for e in previous), default=0) + 1,
            "is_current": True,
            "first_seen_at": now,
            "source_url": None,
            "retrieved_at": None,
            "ingestion": None,
        }
        manifest["files"].append(entry)
        events.append(("revision" if previous else "new", entry))
    manifest["files"].sort(key=lambda e: (e["period_key"], e["revision"]))
    return events
