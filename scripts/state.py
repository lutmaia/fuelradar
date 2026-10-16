"""Estado cifrado da rotina semanal no GitHub (Marco 12, etapa B4).

Uso:
  python scripts/state.py pack   --container NOME [--output estado.tar.enc]
  python scripts/state.py unpack --container NOME [--input estado.tar.enc] [--force]

O CI começa cada semana do zero, mas precisa do que já foi processado: o banco (cópia do
pg_dump) e o histórico de SP em data/processed e data/quarantine. Esse histórico tem CNPJ e razão
social, e anexo de release é público; por isso o pacote é cifrado (AES-256 com chave derivada por
PBKDF2, via openssl) com a chave de RADAR_STATE_KEY, que fica só no .env local e nos Secrets do
GitHub. Os arquivos brutos da ANP não entram. `--container` é o contêiner do PostgreSQL 16 onde
pg_dump e pg_restore rodam (mesma versão do servidor). `unpack` exige banco vazio.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from radar_combustiveis import weekly  # noqa: E402

PROCESSED = ("manifest.json", "downloads.jsonl", "weekly_runs.jsonl", "observations", "runs", "quality")
QUARANTINE = "data/quarantine"
DB_FILE, INFO_FILE = "db.dump", "estado.json"
ALLOWED = ("data/processed/", "data/quarantine", DB_FILE, INFO_FILE)
MIN_KEY_LENGTH = 32
OPENSSL_ARGS = ("enc", "-aes-256-cbc", "-pbkdf2", "-iter", "600000", "-md", "sha256", "-pass", "env:RADAR_STATE_KEY")
READER_ROLE = ("DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'radar_reader') "
               "THEN CREATE ROLE radar_reader NOLOGIN; END IF; END $$;")


class StateError(Exception):
    pass


def key():
    value = os.environ.get("RADAR_STATE_KEY", "")
    if len(value) < MIN_KEY_LENGTH:
        raise StateError(f"Defina RADAR_STATE_KEY com pelo menos {MIN_KEY_LENGTH} caracteres.")
    return value


def openssl(*args):
    binary = shutil.which("openssl")
    if binary is None:
        raise StateError("openssl não encontrado (no Windows vem com o Git).")
    key()
    result = subprocess.run([binary, *OPENSSL_ARGS, *args], capture_output=True)
    if result.returncode != 0:
        raise StateError("openssl falhou (chave errada ou arquivo corrompido?): "
                         + result.stderr.decode(errors="replace").strip())


def dump_database(container, path):
    with open(path, "wb") as stream:
        subprocess.run(["docker", "exec", container, "pg_dump", "-U", "radar", "-d", "radar", "-Fc"],
                       stdout=stream, check=True)


def restore_database(container, path):
    psql = ["docker", "exec", "-i", container, "psql", "-U", "radar", "-d", "radar", "-v", "ON_ERROR_STOP=1",
            "-tAc"]
    exists = subprocess.run([*psql, "SELECT count(*) FROM pg_namespace WHERE nspname = 'radar'"],
                            capture_output=True, text=True, check=True).stdout.strip()
    if exists != "0":
        raise StateError("O banco de destino já tem o esquema radar; o estado só é restaurado em banco vazio.")
    subprocess.run([*psql, READER_ROLE], check=True, capture_output=True)  # papel é do servidor, não do dump
    with open(path, "rb") as stream:
        subprocess.run(["docker", "exec", "-i", container, "pg_restore", "-U", "radar", "-d", "radar",
                        "--exit-on-error"], stdin=stream, check=True)


def pack(container, output, root=ROOT, dump=dump_database):
    with tempfile.TemporaryDirectory() as folder:
        folder = Path(folder)
        dump(container, folder / DB_FILE)
        info = {"created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "snapshot_week": weekly.snapshot_week(root / "snapshot" / "radar-sp.json.gz")}
        (folder / INFO_FILE).write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
        plain = folder / "estado.tar.gz"
        with tarfile.open(plain, "w:gz") as tar:
            tar.add(folder / INFO_FILE, INFO_FILE)
            tar.add(folder / DB_FILE, DB_FILE)
            for name in PROCESSED:
                if (root / "data" / "processed" / name).exists():
                    tar.add(root / "data" / "processed" / name, f"data/processed/{name}")
            if (root / QUARANTINE).exists():
                tar.add(root / QUARANTINE, QUARANTINE)
        openssl("-salt", "-in", str(plain), "-out", str(output))
    return {**info, "bytes": Path(output).stat().st_size, "sha256": hashlib.sha256(Path(output).read_bytes()).hexdigest()}


def unpack(container, source, root=ROOT, force=False, restore=restore_database):
    if (root / "data" / "processed" / "manifest.json").exists() and not force:
        raise StateError("data/processed já tem um manifesto; use --force para sobrescrever com o estado.")
    with tempfile.TemporaryDirectory() as folder:
        folder = Path(folder)
        plain = folder / "estado.tar.gz"
        openssl("-d", "-in", str(source), "-out", str(plain))
        with tarfile.open(plain, "r:gz") as tar:
            members = tar.getmembers()
            strange = [m.name for m in members if not m.name.startswith(ALLOWED)]
            if strange:
                raise StateError(f"Pacote com caminhos inesperados: {strange[:3]}")
            tar.extractall(folder / "pacote", filter="data")
        unpacked = folder / "pacote"
        restore(container, unpacked / DB_FILE)
        for item in sorted((unpacked / "data").rglob("*")):
            target = root / item.relative_to(unpacked)
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, target)
        return json.loads((unpacked / INFO_FILE).read_text(encoding="utf-8"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name, flag in (("pack", "--output"), ("unpack", "--input")):
        command = sub.add_parser(name)
        command.add_argument("--container", required=True)
        command.add_argument(flag, type=Path, default=Path("estado.tar.enc"))
        if name == "unpack":
            command.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "pack":
            info = pack(args.container, args.output)
            print(f"Estado: {args.output} · {info['bytes'] / 1e6:.1f} MB · semana do pacote {info['snapshot_week']} · "
                  f"sha256 {info['sha256']}")
        else:
            info = unpack(args.container, args.input, force=args.force)
            print(f"Estado restaurado: criado em {info['created_at']}, semana do pacote {info['snapshot_week']}")
    except (StateError, subprocess.CalledProcessError) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
