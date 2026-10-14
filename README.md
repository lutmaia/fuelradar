# Radar de Combustíveis SP

Preços de combustível pesquisados pela ANP em São Paulo, organizados para responder perguntas práticas (*onde abastecer, etanol ou gasolina, quanto o preço vai mudar*) e testados com um estudo pré-registrado.

**[Demonstração online](https://fuelradar-a5kwciypheseufpbfh6ggv.streamlit.app/)** · dados de 13/11/2022 a 09/10/2026 (última coleta) · sem instalar nada.

## O problema

A ANP publica toda semana o preço de cerca de 4 mil postos paulistas, em planilhas soltas, com lacunas e mudanças de formato. Dá para consultar um arquivo, mas não para perguntar "quanto economizo escolhendo o posto na minha cidade?" ou "a bandeira branca é mesmo mais barata?". Este projeto junta três anos dessas planilhas, cuida da qualidade e responde com a fonte, a data e o tamanho da amostra sempre à vista.

## O que os dados mostram

Números do [estudo](reports/study/resumo.md), na janela de 13/11/2022 a 29/03/2026 (675.834 preços), com métodos e critérios escritos e commitados **antes** de calcular qualquer resultado.

1. **Escolher o posto pesa mais do que esperar a semana.** No mesmo município e semana, o posto mais barato da amostra fica tipicamente **R$ 0,40/L** abaixo da mediana (R$ 20 num tanque de 50 L), cerca de **4 vezes** um reajuste semanal típico de um posto (R$ 0,10). [Relatório](reports/study/descritivo.md)
2. **A bandeira branca é cerca de 5,6% mais barata**, comparando postos do mesmo município na mesma semana (IC 95% de −6,0% a −5,2%). O resultado sobreviveu a todas as checagens (vizinhança por CEP, sem preços extremos, cada metade do período). É associação de preço, não efeito da bandeira nem medida de qualidade. [Relatório](reports/study/q1.md)
3. **O etanol compensou (até 70% da gasolina) em 83% das semanas de cada município**, mas isso muda muito com o tempo:

```mermaid
xychart-beta
    title "Etanol compensou: % das semanas, por município"
    x-axis ["2023", "2024", "2025", "2026 (até mar.)"]
    y-axis "% das município-semanas" 0 --> 100
    bar [74, 99, 90, 33]
```

## O que não funcionou (e está publicado assim mesmo)

- **Machine learning não superou o óbvio.** Um LightGBM para prever a mediana semanal de 1 a 4 semanas ficou **7,9% pior** que "repetir o último valor" num backtest com 24.481 previsões. A previsão publicada é a do método simples, e o [cartão do modelo](docs/model-card.md) explica por quê.
- **Duas das três hipóteses do estudo não se sustentaram.** "O preço sobe mais do que cai" (Q2) e "os reajustes começam nas cidades grandes" (Q3) não sobreviveram aos subperíodos. Pelo protocolo, o gate que liberaria a modelagem mais ambiciosa **não passou** (1 de 3), e nada foi refeito para passar.

## Como foi feito

```text
ANP (planilhas semanais) → ingestão (manifesto SHA-256, brutos intactos) → qualidade (regras, quarentena)
  → PostgreSQL (dimensões, fatos, agregações) → API FastAPI somente leitura → painel Streamlit
                                              ↘ estudo pré-registrado e previsões (backtest)
```

- **Dados:** cerca de 800 mil preços em 174 semanas, de 108 municípios. Reexecução sem duplicar, revisões da fonte rastreadas, arquivos com defeito da ANP excluídos com registro ([ADR 0006](docs/decisions/0006-arquivos-da-fonte-excluidos.md)).
- **API:** endpoints de leitura com `data_as_of`, amostra e cobertura em cada resposta, usuário de banco somente leitura ([guia](docs/api.md)).
- **Painel:** 10 páginas: município, postos mais baratos, bandeiras, previsões, variações incomuns, comparação, regiões, estudo e qualidade ([guia](docs/dashboard.md)).
- **Estudo:** [protocolo](docs/estudo/protocolo.md) commitado antes dos resultados, teste final lacrado em código, IC agrupado por posto, bootstrap em blocos de semanas e correção de Holm.
- **Testes:** suíte com dados sintéticos de resposta conhecida, contra PostgreSQL real em Docker; os números do painel foram conferidos contra SQL escrito à parte e as telas, no navegador.
- **Demonstração:** o mesmo painel lendo um pacote de respostas da API ([ADR 0009](docs/decisions/0009-demonstrativo-e-pacote-instantaneo.md)), sem CNPJ nem razão social.

Decisões em [docs/decisions/](docs/decisions/), marcos e evidências em [PLAN.md](PLAN.md).

## Rodar localmente

Requisitos: Python 3.12+ (o ambiente fixado usa 3.14) e Docker. No PowerShell, a partir da raiz:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt   # ambiente fixado
Copy-Item .env.example .env                                         # defina POSTGRES_PASSWORD
docker compose up -d --wait                                         # PostgreSQL em 127.0.0.1:54329
```

**Só o painel, sem banco nem API** (lê o pacote do demonstrativo):

```powershell
.\.venv\Scripts\python.exe -m streamlit run demo/streamlit_app.py
```

**Pipeline completo** (os dados brutos não acompanham o Git; o download baixa as semanas da ANP):

```powershell
.\.venv\Scripts\python.exe scripts/fetch_anp.py --since 2026-09-01 --ingest   # baixa as semanas da ANP desde essa data e ingere
.\.venv\Scripts\python.exe scripts/check_quality.py             # qualidade, quarentena e cobertura
.\.venv\Scripts\python.exe scripts/load_db.py                   # migra e carrega no PostgreSQL (DATABASE_URL)
.\.venv\Scripts\python.exe scripts/run_forecasts.py              # backtest, decisão e previsões; relatório em reports/forecasting/
.\.venv\Scripts\python.exe scripts/run_study.py                  # estudo; relatórios em reports/study/
.\iniciar.ps1                                                    # sobe banco, API e painel (http://127.0.0.1:8501)
.\.venv\Scripts\python.exe scripts/build_snapshot.py            # regenera o pacote do demonstrativo (API_DATABASE_URL)
```

Sem `--since`, `fetch_anp.py` baixa todas as semanas desde 2022 (cerca de 300 MB); use `--dry-run` para ver o que seria baixado. O usuário somente leitura da API é criado por `scripts/create_api_role.py` ([docs/api.md](docs/api.md)). Testes: `.\.venv\Scripts\python.exe -m unittest discover -s tests -t .`, e com `RADAR_TEST_DATABASE_URL` rodam também os de banco, API e integração.

## Fonte dos dados

Os preços vêm do **Levantamento de Preços de Combustíveis da ANP** (Agência Nacional do Petróleo, Gás Natural e Biocombustíveis), publicado em dados abertos no portal gov.br/anp. Os arquivos originais **não** estão neste repositório. Medianas, comparações, previsões e demais números são **derivados por este projeto** e não são divulgados pela ANP.

## Limites

- É uma **pesquisa por amostragem**: não cobre todos os postos nem dá preço em tempo real, e o preço pode ter mudado depois da coleta.
- Só **São Paulo** é publicado; a estrutura prevê outras UFs (`TARGET_UFS`).
- Variações incomuns são sinais estatísticos, não indício de irregularidade; nenhuma tela associa postos a qualidade do combustível.
- Previsões são estimativas com incerteza, sem garantia de preço.

## Organização

- `src/radar_combustiveis/`: ingestão, qualidade, banco, API (`api/`), painel (`dashboard/`), previsão (`forecasting/`) e estudo (`study/`).
- `scripts/`: pontos de entrada (download, ingestão, qualidade, carga, previsões, estudo, API, painel e pacote).
- `migrations/`: esquema do PostgreSQL em SQL versionado.
- `reports/`: relatórios reproduzíveis do backtest, do estudo e do perfil dos dados.
- `snapshot/` e `demo/`: pacote e ponto de entrada do demonstrativo.
- `docs/`: arquitetura, [desenho do estudo de caso](docs/estudo-de-caso.md), contratos, guias e decisões.
- `tests/`: testes com dados sintéticos.

## Licença

Código sob a licença [MIT](LICENSE). Os dados de origem pertencem à ANP e seguem os termos de uso do portal de dados abertos.
