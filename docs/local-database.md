# Banco de dados local

Runbook do PostgreSQL de desenvolvimento e teste (decisões em [ADR 0003](decisions/0003-banco-postgresql.md)). Comandos no PowerShell, a partir da raiz do projeto. Há dois caminhos para o mesmo banco; use um por vez, pois ambos escutam na porta 54329.

## Opção A — Docker Compose (recomendada)

Requisito: Docker Desktop com WSL2. Instalação (uma vez, com permissão de administrador; depois saia e entre na sessão do Windows para o grupo `docker-users` valer):

```powershell
winget install --id Docker.DockerDesktop --exact
```

O Docker Desktop é gratuito para uso pessoal, educacional e pequenas empresas; confira os termos atuais da Docker.

```powershell
Copy-Item .env.example .env          # edite POSTGRES_PASSWORD; o .env não vai para o Git
docker compose up -d --wait          # sobe o postgres:16.15 e espera o healthcheck
$pw = (Get-Content .env | Where-Object { $_ -like 'POSTGRES_PASSWORD=*' }).Split('=', 2)[1]
$env:DATABASE_URL = "postgresql://radar:$pw@127.0.0.1:54329/radar"
.\.venv\Scripts\python.exe scripts/load_db.py
```

Use `127.0.0.1` e não `localhost` na URL: no Windows o `localhost` tenta IPv6 primeiro e cada conexão espera cerca de 30 s antes de cair no IPv4.

Dados em um volume do Docker (`radar-combustiveis_pgdata`): `docker compose down` mantém os dados; `docker compose down -v` apaga. Para trocar do banco portátil, basta pará-lo (`scripts/local_postgres.py stop`) e recarregar com `load_db.py`: o banco é reconstruído a partir dos arquivos já processados, sem `pg_dump`.

## Opção B — binários portáteis (sem Docker)

1. Baixe o zip de binários do PostgreSQL 16 (EDB), indicado em <https://www.postgresql.org/download/windows/>, e extraia em `%LOCALAPPDATA%\radar-combustiveis\pg16`, de modo que exista `...\pg16\pgsql\bin\postgres.exe`. Não use a pasta do projeto se ela estiver no OneDrive.
2. Crie o cluster e o banco: `.\.venv\Scripts\python.exe scripts/local_postgres.py init`. A senha é gerada em `%LOCALAPPDATA%\radar-combustiveis\pg_password`, fora do Git.
3. Uso: `scripts/local_postgres.py start|stop|status|url`; `$env:DATABASE_URL = (.\.venv\Scripts\python.exe scripts/local_postgres.py url)`.
4. Limpeza: `stop` e apague `%LOCALAPPDATA%\radar-combustiveis`. Nada é instalado no sistema.

## Pipeline

```powershell
.\.venv\Scripts\python.exe -m pip install openpyxl==3.1.5 "psycopg[binary]==3.3.6"   # uma vez, no .venv
.\.venv\Scripts\python.exe scripts/ingest_local.py
.\.venv\Scripts\python.exe scripts/check_quality.py
.\.venv\Scripts\python.exe scripts/load_db.py                   # migra e carrega; --migrate-only só migra
```

A carga é idempotente: repetir não insere nem altera nada. Se a qualidade decidir `bloquear`, a carga é recusada e o banco permanece como estava.

## Testes com banco real

```powershell
# mesma URL, apontando para o banco "postgres" (cada teste cria e remove um banco radar_test_*)
$env:RADAR_TEST_DATABASE_URL = $env:DATABASE_URL.Replace("/radar", "/postgres")
.\.venv\Scripts\python.exe -m unittest discover -s tests -t .
```

Sem a variável, os 16 testes do banco são ignorados.

## Consultas úteis

```sql
SET search_path TO radar;
SELECT status, rows_accepted, rows_quarantined, quality_decision, finished_at FROM ingestion_run ORDER BY started_at;
SELECT week_start, price_median, station_count FROM mart_weekly_state_price
  JOIN dim_product USING (product_id) WHERE canonical_name = 'GASOLINA_COMUM' ORDER BY week_start DESC LIMIT 8;
```
