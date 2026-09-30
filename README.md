# Radar de Combustíveis SP

Projeto em construção para consultar, comparar e acompanhar os preços de combustíveis pesquisados pela ANP em São Paulo. A arquitetura permite expansão futura por UF.

**Estado atual: Marco 1 — descoberta dos dados.** Nove XLSX reais foram perfilados, com contrato proposto e testes sintéticos. Há um script exploratório executável; ainda não há ingestão definitiva, banco, API, dashboard, modelos ou infraestrutura.

## Começar

1. Leia [PROJECT.md](PROJECT.md) para entender o produto.
2. Consulte a especificação principal em [docs/architecture.md](docs/architecture.md).
3. Acompanhe os marcos em [PLAN.md](PLAN.md) e as orientações em [AGENTS.md](AGENTS.md).
4. Consulte [a descoberta real](docs/data-discovery.md), [o contrato](docs/data-contract.md) e [o resumo gerado](reports/data-profile/summary.md).
5. Preserve os originais conforme [data/README.md](data/README.md).

Python 3.12+ é o requisito. O `pyproject.toml` registra metadados e `openpyxl==3.1.5`, necessário para ler XLSX. O código exploratório está em `scripts/`; `src/radar_combustiveis/` continua reservado para o código do produto. Empacotamento, uv e lockfile serão configurados quando necessários, conforme a arquitetura.

Para reproduzir o perfil no PowerShell, a partir da raiz (reutilize `.venv` se já existir):

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install openpyxl==3.1.5
.\.venv\Scripts\python.exe scripts/profile_anp_data.py "data/raw/*.xlsx"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

São necessários os arquivos locais: dados brutos não acompanham o Git. O script produz `reports/data-profile/profile.json` e `summary.md`, sem modificar os originais. Veja limitações e resultados em [data-discovery.md](docs/data-discovery.md).

A `.env.example` documenta a futura configuração central `TARGET_UFS=["SP"]`. Não contém segredos e ainda não é carregada por código. Um eventual `.env` local fica fora do Git.

## Organização

- `src/`: futuro código Python.
- `scripts/`: perfil exploratório reproduzível, sem ingestão definitiva.
- `tests/`: testes do perfil com amostras sintéticas pequenas.
- `reports/data-profile/`: estatísticas e metadados da análise, sem cópias de linhas brutas.
- `data/`: originais, derivados e quarentena locais, excluídos do Git.
- `docs/`: arquitetura, contrato pendente e futuras decisões.

Os arquivos `.gitkeep` são marcadores vazios para preservar pastas no Git. O `.gitignore` exclui dados locais, segredos e artefatos de execução; não use `git add -f` para contornar essa proteção.

## Limites do produto

Os dados são uma pesquisa, não preços em tempo real, e podem não cobrir todos os postos. Preços podem mudar após a coleta; ausência de município ou posto não indica ausência de atividade. O produto publicará somente São Paulo, sem representar todo o Brasil. Data da pesquisa, atualização e tamanho da amostra deverão acompanhar os resultados.

Variações incomuns não comprovam irregularidade. Previsões futuras serão estimativas com incerteza, sem garantia de preço ou recomendação financeira. A arquitetura aponta cobertura histórica limitada do preço de compra e o exclui como base do primeiro modelo; a descoberta verificará os arquivos reais. Agentes de IA, chat, RAG e sistemas multiagentes estão fora do escopo.

Próximo passo: Marco 2 — ingestão histórica e semanal. Os históricos recebidos são agregados mensais; obter manualmente uma amostra histórica por revenda antes de implementar esse ramo da ingestão.
