# Radar de Combustíveis SP

Projeto em construção para consultar, comparar e acompanhar os preços de combustíveis pesquisados pela ANP em São Paulo. A arquitetura permite expansão futura por UF.

**Estado atual: Marco 8 concluído — estudo exploratório pré-registrado.** Os arquivos da ANP são baixados e ingeridos (Marco 2), passam por regras de qualidade e quarentena (Marco 3), são carregados no PostgreSQL (Marco 4), consultados por uma API REST somente leitura (Marco 5, [guia](docs/api.md)) e exploradas em um painel Streamlit (Marco 6, [guia](docs/dashboard.md)). O Marco 7 adiciona previsões de 1 a 4 semanas com intervalo e variações incomuns (API e painel); o modelo de machine learning testado não superou o baseline e o baseline permanece publicado ([cartão do modelo](docs/model-card.md)). O Marco 8 testa três perguntas com protocolo commitado antes dos resultados ([resumo](reports/study/resumo.md)): no mesmo município e semana, postos de bandeira branca cobram cerca de 5,6% menos (achado estável); os achados sobre assimetria de altas e quedas e sobre difusão entre municípios não foram estáveis. Ainda não há agendamento nem infraestrutura de produção. Resultados e limitações em [PLAN.md](PLAN.md).

## Começar

1. Leia [PROJECT.md](PROJECT.md) para entender o produto.
2. Consulte a especificação principal em [docs/architecture.md](docs/architecture.md).
3. Acompanhe os marcos em [PLAN.md](PLAN.md) e as orientações em [AGENTS.md](AGENTS.md).
4. Consulte [a descoberta real](docs/data-discovery.md), [o contrato](docs/data-contract.md) e [o resumo gerado](reports/data-profile/summary.md).
5. Preserve os originais conforme [data/README.md](data/README.md).

Python 3.12+ é o requisito. O `pyproject.toml` registra metadados e as dependências: `openpyxl` (ler XLSX), `psycopg[binary]` e `psycopg-pool` (cliente PostgreSQL), `fastapi` e `uvicorn` (API), `streamlit` e `plotly` (painel) e `httpx` (cliente HTTP do painel e dos testes). O código do produto está em `src/radar_combustiveis/` e os pontos de entrada em `scripts/`. Empacotamento, uv e lockfile serão configurados quando necessários, conforme a arquitetura.

Instalação, no PowerShell, a partir da raiz:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt   # ambiente fixado (Python 3.14)
Copy-Item .env.example .env                                         # defina POSTGRES_PASSWORD
docker compose up -d --wait                                         # PostgreSQL em 127.0.0.1:54329
.\.venv\Scripts\python.exe -m unittest discover -s tests -v       # com RADAR_TEST_DATABASE_URL, roda também os testes de banco
```

São necessários os arquivos locais: dados brutos não acompanham o Git. O script produz `reports/data-profile/profile.json` e `summary.md`, sem modificar os originais. Veja limitações e resultados em [data-discovery.md](docs/data-discovery.md).

A `.env.example` documenta `TARGET_UFS=["SP"]`, `DATABASE_URL` (pipeline) e `API_DATABASE_URL` (API, usuário somente leitura), lidas do ambiente. Não contém segredos; um `.env` local fica fora do Git.

Pipeline completo, a partir da raiz (banco local: [docs/local-database.md](docs/local-database.md)):

```powershell
.\.venv\Scripts\python.exe scripts/fetch_anp.py --since 2026-09-01 --ingest   # baixa as semanas da ANP desde essa data e ingere
.\.venv\Scripts\python.exe scripts/ingest_local.py              # ingestão local do que estiver em data/raw
.\.venv\Scripts\python.exe scripts/check_quality.py             # qualidade, quarentena e cobertura
.\.venv\Scripts\python.exe scripts/load_db.py                   # migra e carrega no PostgreSQL (DATABASE_URL)
.\.venv\Scripts\python.exe scripts/run_forecasts.py              # backtest, decisão e previsões (DATABASE_URL); relatório em reports/forecasting/
.\.venv\Scripts\python.exe scripts/run_api.py                   # sobe a API em http://127.0.0.1:8000/docs (API_DATABASE_URL)
.\.venv\Scripts\python.exe scripts/run_dashboard.py             # sobe o painel em http://127.0.0.1:8501 (RADAR_API_URL)
```

**Atenção ao `--since`:** sem ele, `fetch_anp.py` seleciona todas as semanas publicadas pela ANP desde 2022 (cerca de 300 MB) e a ingestão leva alguns minutos. Use `--dry-run` para ver o que seria baixado. Arquivos da ANP com defeito conhecido ficam em `config/excluded_sources.json` ([ADR 0006](docs/decisions/0006-arquivos-da-fonte-excluidos.md)).

O usuário somente leitura da API é criado uma vez por `scripts/create_api_role.py`; os passos estão em [docs/api.md](docs/api.md).

## Fonte dos dados

Os preços vêm do **Levantamento de Preços de Combustíveis da ANP** (Agência Nacional do Petróleo, Gás Natural e Biocombustíveis), publicado em dados abertos no portal gov.br/anp. Os arquivos originais **não** estão neste repositório e permanecem intactos em `data/raw`. Medianas, comparações, previsões e demais números exibidos são **derivados por este projeto** e não são divulgados pela ANP. É uma pesquisa por amostragem: não representa todos os postos nem preços em tempo real, e as previsões são estimativas estatísticas.

## Licença

Código sob a licença [MIT](LICENSE). Os dados de origem pertencem à ANP e seguem os termos de uso do portal de dados abertos.

## Organização

- `src/radar_combustiveis/`: ingestão, qualidade, acesso ao banco, API (`api/`) e painel (`dashboard/`).
- `scripts/`: perfil exploratório, download, ingestão, qualidade, carga, API, painel e criação do usuário da API.
- `migrations/`: esquema do PostgreSQL em SQL versionado.
- `tests/`: testes com dados sintéticos; os do banco, da API e a integração do painel exigem `RADAR_TEST_DATABASE_URL`.
- `reports/data-profile/`: estatísticas e metadados da análise, sem cópias de linhas brutas.
- `data/`: originais, derivados e quarentena locais, excluídos do Git.
- `docs/`: arquitetura, contratos de dados, guias da API e do painel, runbook do banco e decisões (ADRs).

Os arquivos `.gitkeep` são marcadores vazios para preservar pastas no Git. O `.gitignore` exclui dados locais, segredos e artefatos de execução; não use `git add -f` para contornar essa proteção.

## Limites do produto

Os dados são uma pesquisa, não preços em tempo real, e podem não cobrir todos os postos. Preços podem mudar após a coleta; ausência de município ou posto não indica ausência de atividade. O produto publicará somente São Paulo, sem representar todo o Brasil. Data da pesquisa, atualização e tamanho da amostra deverão acompanhar os resultados.

Variações incomuns não comprovam irregularidade. Previsões futuras serão estimativas com incerteza, sem garantia de preço ou recomendação financeira. A arquitetura aponta cobertura histórica limitada do preço de compra e o exclui como base do primeiro modelo; a descoberta verificará os arquivos reais. Agentes de IA, chat, RAG e sistemas multiagentes estão fora do escopo.

Para reproduzir a validação histórica (sem sobrescrever o relatório do Marco 1):

```powershell
.\.venv\Scripts\python.exe scripts/profile_anp_data.py "data/raw/historicos/*.csv" "data/raw/revendas*.xlsx" --output-dir reports/data-profile/historical-validation
```

Próximo passo: Marco 8, automação, monitoramento e implantação. Agregados municipais e regionais não entram na tabela de observações individuais; `DIESEL` e `DIESEL S500` são o mesmo produto (`DIESEL_COMUM`) e `DIESEL S10` fica separado, conforme o contrato.
