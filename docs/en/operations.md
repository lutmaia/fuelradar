# Operations manual

What runs on its own, what to do when something fails, and the dates that still need attention. The decisions behind it are in the ADRs (in Portuguese), especially [0011](../decisions/0011-rotina-semanal-no-ci.md) (weekly routine on GitHub) and [0006](../decisions/0006-arquivos-da-fonte-excluidos.md) (defective ANP files). Versão em português: [operacao.md](../operacao.md).

## What runs on its own

| What | When | Where |
|---|---|---|
| Tests and workflow validation | on every push and pull request | `.github/workflows/tests.yml` |
| Weekly update | every day at 22:00 UTC; with no new ANP week it ends in seconds | `.github/workflows/weekly.yml` |
| Demo redeploy | on every push to `main`, including the bot's | Streamlit Community Cloud |

When there is a new week, the weekly workflow opens the encrypted state, runs `scripts/weekly_refresh.py` on a temporary PostgreSQL (download, ingestion, quality, load, external sources, forecasts, live forecast and package), stores the new state in the `estado` release (the previous one becomes `estado-anterior`) and commits `reports/ledger/` and `snapshot/` as `github-actions[bot]`. Before committing from your computer, run `git pull --rebase`.

## When the update fails

GitHub sends an email; a failure never publishes anything halfway (state and repository stay as they were), and the next day's run tries again. In the **Rotina semanal** step log, the line `FALHOU em: <stage>` says where it stopped.

| Stage or symptom | Likely cause | What to do |
|---|---|---|
| `ler a página da ANP` | site down or page changed | wait a day; if it persists, check the address in `ingestion/download.py` and the link format |
| `ingerir` or `qualidade` with a new file | defective ANP spreadsheet | confirm the defect and record it in `config/excluded_sources.json` with the reason (ADR 0006); the week becomes a gap |
| `fontes externas` | Central Bank or ANP down | on GitHub the routine stops and retries the next day (no earlier download is kept there); on your computer the last downloaded version is still used |
| `Abrir o estado cifrado` | wrong key or missing asset | see [Encrypted state](#encrypted-state) |
| workflow no longer runs | 60 days without repository activity | Actions → Atualização semanal → *Enable workflow* |

To run it now: Actions → Atualização semanal → *Run workflow*. "Rodar mesmo com o pacote em dia" forces a full run; the failure field (a stage name) simulates a failure to test detection.

**Plan B, on your computer:** with Docker running, `./atualizar.sh` (macOS and Linux) or `.\atualizar.ps1` (Windows) runs the same routine on the local database (`--dry-run` only says whether there is a new week); then commit `reports/ledger/` and `snapshot/`.

## Encrypted state

- **What it is:** a database copy (`pg_dump`) plus the processed São Paulo history, in an AES-256 encrypted `.tar.gz`, attached to the `estado` release. Raw ANP files are not included.
- **Key:** `RADAR_STATE_KEY` in the local `.env` and `STATE_KEY` in the repository secrets. GitHub cannot show a secret again: keep a copy in a password manager.
- **Set the key** (scripts do not read `.env` on their own): on macOS or Linux, `export RADAR_STATE_KEY="$(grep '^RADAR_STATE_KEY=' .env | cut -d= -f2-)"`; in PowerShell, `$env:RADAR_STATE_KEY = ((Get-Content .env | Select-String '^RADAR_STATE_KEY=').Line -split '=', 2)[1]`
- **Go back to the previous state:** download `estado-anterior.tar.enc` from the release, rename it to `estado.tar.enc` and upload it again, replacing the current one (edit the release).
- **Restore the local database from the state** (empty database): `python scripts/state.py unpack --container <postgres container> --input estado.tar.enc`, with `RADAR_STATE_KEY` set.
- **Change the key or rebuild the state:** with the local database up to date, `python scripts/state.py pack --container radar-combustiveis-postgres-1 --output estado.tar.enc` with the new key; upload it to the release (replacing) and update the secret.

## Live evaluation: dates

Fall, stable and rise probabilities are written every week to `reports/ledger/` before the price is known, and scored when ANP publishes ([protocol](../estudo/protocolo-ao-vivo.md), in Portuguese). Nothing here needs action to work:

- **~January 2027, 13 scored weeks:** the scoreboard starts computing the degradation alert; if it fires, the *Desempenho ao vivo* page shows it.
- **~April 2027, 26 scored weeks two weeks ahead:** the decision is made automatically. "Oficial" removes the experimental label from the API and dashboard; "reprovado" hides the probabilities. The manual step is updating the [model card](../model-card.md) and the README with the result, whatever it is.

The ledger never changes: `scripts/run_live.py` checks each file's SHA-256 in `manifesto.csv` and stops if any changed.

## Checks

- `python scripts/reproduce.py` rebuilds every published report in a temporary folder and compares (about 6 minutes; the final test is checked from the points of the single read, without a new access).
- `python scripts/dataset_card.py` regenerates the [dataset card](dataset-card.md).

## Running on your computer

Setup in the [README](../../README.md#rodar-localmente). `./iniciar.sh` (or `.\iniciar.ps1` on Windows) starts the database, API and dashboard (http://127.0.0.1:8501); `docker compose --profile demo up --build demo` starts only the demo, without a database. The development database runs in Docker at `127.0.0.1:54329` (use `127.0.0.1`, not `localhost`).
