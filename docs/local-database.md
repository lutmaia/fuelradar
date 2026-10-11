# Banco de dados local

Runbook do PostgreSQL de desenvolvimento e teste (decisões em [ADR 0003](decisions/0003-banco-postgresql.md)). Comandos no PowerShell, a partir da raiz do projeto. O banco roda somente em Docker Compose, na porta 54329 de `127.0.0.1`.

## Docker Compose

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

Dados em um volume do Docker (`radar-combustiveis_pgdata`): `docker compose down` mantém os dados; `docker compose down -v` apaga. Depois de um `down -v`, recarregar com `load_db.py` reconstrói o banco a partir dos arquivos já processados, sem `pg_dump`.

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
# mesmo servidor, apontando para o banco "postgres" (cada teste cria e remove um banco radar_test_*)
$pw = (Get-Content .env | Where-Object { $_ -like 'POSTGRES_PASSWORD=*' }).Split('=', 2)[1]
$env:RADAR_TEST_DATABASE_URL = "postgresql://radar:$pw@127.0.0.1:54329/postgres"
.\.venv\Scripts\python.exe -m unittest discover -s tests -t .
```

Sem a variável, os 16 testes do banco e os 41 da API são ignorados (a API também exige `httpx`).

## Usuário somente leitura da API

A migração `0003` (aplicada por `load_db.py`) cria o papel `radar_reader`. O login `radar_api` que a API usa é criado por `scripts/create_api_role.py`, com a senha em `RADAR_API_PASSWORD`; o passo a passo está em [api.md](api.md). Como `CREATE ROLE` vale para o servidor inteiro, o papel `radar_reader` também existe depois dos testes, sem privilégios em bancos que não tenham a migração.

## Consultas úteis

```sql
SET search_path TO radar;
SELECT status, rows_accepted, rows_quarantined, quality_decision, finished_at FROM ingestion_run ORDER BY started_at;
SELECT week_start, price_median, station_count FROM mart_weekly_state_price
  JOIN dim_product USING (product_id) WHERE canonical_name = 'GASOLINA_COMUM' ORDER BY week_start DESC LIMIT 8;
```
