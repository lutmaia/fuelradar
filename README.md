# Radar de Combustíveis SP

Projeto em construção para consultar, comparar e acompanhar os preços de combustíveis pesquisados pela ANP em São Paulo. A arquitetura permite expansão futura por UF.

**Estado atual: Marco 4 concluído — banco PostgreSQL.** Os arquivos da ANP são baixados e ingeridos (Marco 2), passam por regras de qualidade e quarentena (Marco 3) e são carregados no PostgreSQL com dimensões, fato e agregações semanais (Marco 4). Ainda não há API, dashboard, modelos ou infraestrutura. Resultados e limitações em [PLAN.md](PLAN.md).

## Começar

1. Leia [PROJECT.md](PROJECT.md) para entender o produto.
2. Consulte a especificação principal em [docs/architecture.md](docs/architecture.md).
3. Acompanhe os marcos em [PLAN.md](PLAN.md) e as orientações em [AGENTS.md](AGENTS.md).
4. Consulte [a descoberta real](docs/data-discovery.md), [o contrato](docs/data-contract.md) e [o resumo gerado](reports/data-profile/summary.md).
5. Preserve os originais conforme [data/README.md](data/README.md).

Python 3.12+ é o requisito. O `pyproject.toml` registra metadados, `openpyxl==3.1.5` (ler XLSX) e `psycopg[binary]==3.3.6` (cliente PostgreSQL). O código do produto está em `src/radar_combustiveis/` e os pontos de entrada em `scripts/`. Empacotamento, uv e lockfile serão configurados quando necessários, conforme a arquitetura.

Para reproduzir o perfil no PowerShell, a partir da raiz (reutilize `.venv` se já existir):

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install openpyxl==3.1.5
.\.venv\Scripts\python.exe scripts/profile_anp_data.py "data/raw/*.xlsx"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

São necessários os arquivos locais: dados brutos não acompanham o Git. O script produz `reports/data-profile/profile.json` e `summary.md`, sem modificar os originais. Veja limitações e resultados em [data-discovery.md](docs/data-discovery.md).

A `.env.example` documenta `TARGET_UFS=["SP"]` e `DATABASE_URL`, lidas do ambiente. Não contém segredos; um `.env` local fica fora do Git.

Pipeline completo, a partir da raiz (banco local: [docs/local-database.md](docs/local-database.md)):

```powershell
.\.venv\Scripts\python.exe scripts/fetch_anp.py --ingest      # baixa as semanas novas da ANP e ingere
.\.venv\Scripts\python.exe scripts/ingest_local.py              # ingestão local do que estiver em data/raw
.\.venv\Scripts\python.exe scripts/check_quality.py             # qualidade, quarentena e cobertura
.\.venv\Scripts\python.exe scripts/load_db.py                   # migra e carrega no PostgreSQL (DATABASE_URL)
```

## Organização

- `src/radar_combustiveis/`: ingestão, qualidade e acesso ao banco.
- `scripts/`: perfil exploratório, download, ingestão, qualidade, carga e servidor local de teste.
- `migrations/`: esquema do PostgreSQL em SQL versionado.
- `tests/`: testes com dados sintéticos; os do banco exigem `RADAR_TEST_DATABASE_URL`.
- `reports/data-profile/`: estatísticas e metadados da análise, sem cópias de linhas brutas.
- `data/`: originais, derivados e quarentena locais, excluídos do Git.
- `docs/`: arquitetura, contrato pendente e futuras decisões.

Os arquivos `.gitkeep` são marcadores vazios para preservar pastas no Git. O `.gitignore` exclui dados locais, segredos e artefatos de execução; não use `git add -f` para contornar essa proteção.

## Limites do produto

Os dados são uma pesquisa, não preços em tempo real, e podem não cobrir todos os postos. Preços podem mudar após a coleta; ausência de município ou posto não indica ausência de atividade. O produto publicará somente São Paulo, sem representar todo o Brasil. Data da pesquisa, atualização e tamanho da amostra deverão acompanhar os resultados.

Variações incomuns não comprovam irregularidade. Previsões futuras serão estimativas com incerteza, sem garantia de preço ou recomendação financeira. A arquitetura aponta cobertura histórica limitada do preço de compra e o exclui como base do primeiro modelo; a descoberta verificará os arquivos reais. Agentes de IA, chat, RAG e sistemas multiagentes estão fora do escopo.

Para reproduzir a validação histórica (sem sobrescrever o relatório do Marco 1):

```powershell
.\.venv\Scripts\python.exe scripts/profile_anp_data.py "data/raw/historicos/*.csv" "data/raw/revendas*.xlsx" --output-dir reports/data-profile/historical-validation
```

Próximo passo: Marco 5, API de leitura sobre o banco. Agregados municipais e regionais não entram na tabela de observações individuais; `DIESEL` e `DIESEL S500` são o mesmo produto (`DIESEL_COMUM`) e `DIESEL S10` fica separado, conforme o contrato.
