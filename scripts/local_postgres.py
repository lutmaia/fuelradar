"""Servidor PostgreSQL local de desenvolvimento e teste, a partir de binários portáteis.

Uso: python scripts/local_postgres.py init|start|stop|status|url

Não instala nada: usa os binários extraídos em RADAR_PG_HOME (padrão
%LOCALAPPDATA%/radar-combustiveis) e mantém os dados fora do projeto e do OneDrive. Escuta
somente em localhost, porta 54329 (RADAR_PG_PORT), com senha gerada no `init`. É só para
desenvolvimento; credenciais reais nunca vão para o repositório.
"""

import argparse
import os
from pathlib import Path
import secrets
import subprocess
import sys

HOME = Path(os.environ.get("RADAR_PG_HOME") or Path(os.environ.get("LOCALAPPDATA", Path.home())) / "radar-combustiveis")
PORT = os.environ.get("RADAR_PG_PORT", "54329")
BIN = HOME / "pg16" / "pgsql" / "bin"
DATA = HOME / "data"
PASSWORD_FILE = HOME / "pg_password"
LOG = HOME / "server.log"
DATABASE = "radar"
USER = "radar"


def run(program, *args, check=True):
    exe = BIN / (program + (".exe" if os.name == "nt" else ""))
    if not exe.exists():
        raise SystemExit(f"ERRO: {exe} não encontrado. Extraia os binários do PostgreSQL 16 em {BIN.parents[1]}.")
    return subprocess.run([str(exe), *map(str, args)], check=check, text=True, capture_output=True)


def url():
    password = PASSWORD_FILE.read_text(encoding="utf-8").strip()
    return f"postgresql://{USER}:{password}@127.0.0.1:{PORT}/{DATABASE}"


def is_running():
    return run("pg_ctl", "-D", DATA, "status", check=False).returncode == 0


def _connection_env():
    return {**os.environ, "PGPASSWORD": PASSWORD_FILE.read_text(encoding="utf-8").strip()}


def init():
    """Idempotente: cria o cluster, sobe o servidor e cria o banco se algum passo faltar."""
    if not DATA.exists():
        HOME.mkdir(parents=True, exist_ok=True)
        PASSWORD_FILE.write_text(secrets.token_urlsafe(24), encoding="utf-8")
        run("initdb", "-D", DATA, "-U", USER, "--auth=scram-sha-256", f"--pwfile={PASSWORD_FILE}",
            "-E", "UTF8", "--locale=C")
        print(f"Cluster criado em {DATA}.")
    start()
    psql = [str(BIN / ("psql.exe" if os.name == "nt" else "psql")), "-h", "localhost", "-p", PORT,
            "-U", USER, "-d", "postgres", "-tA", "-c"]
    query = f"SELECT 1 FROM pg_database WHERE datname = '{DATABASE}'"
    exists = subprocess.run([*psql, query], env=_connection_env(), text=True, capture_output=True, check=True)
    if exists.stdout.strip() != "1":
        subprocess.run([*psql, f'CREATE DATABASE "{DATABASE}"'], env=_connection_env(), check=True,
                       capture_output=True)
        print(f"Banco '{DATABASE}' criado.")
    else:
        print(f"Banco '{DATABASE}' já existe.")


def start():
    if is_running():
        print("Já está em execução.")
        return
    # Sem capturar a saída: o servidor herdaria os pipes e o processo nunca terminaria.
    exe = str(BIN / ("pg_ctl.exe" if os.name == "nt" else "pg_ctl"))
    subprocess.run([exe, "-D", str(DATA), "-l", str(LOG), "-w", "-o",
                    f"-p {PORT} -c listen_addresses=localhost", "start"], check=True,
                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"Servidor em localhost:{PORT}")


def stop():
    if not is_running():
        print("Já está parado.")
        return
    run("pg_ctl", "-D", DATA, "-m", "fast", "-w", "stop")
    print("Servidor parado.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["init", "start", "stop", "status", "url"])
    command = parser.parse_args(argv).command
    if command == "status":
        print("em execução" if is_running() else "parado")
    elif command == "url":
        print(url())
    else:
        {"init": init, "start": start, "stop": stop}[command]()
    return 0


if __name__ == "__main__":
    sys.exit(main())
