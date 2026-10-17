# Radar de Combustíveis SP

Preços de combustível pesquisados pela ANP em São Paulo, organizados para responder perguntas práticas (*onde abastecer, etanol ou gasolina, quanto o preço vai mudar*) e testados com um estudo pré-registrado.

**[Demonstração online](https://fuelradar-a5kwciypheseufpbfh6ggv.streamlit.app/)** · dados de 13/11/2022 a 09/10/2026 (última coleta) · sem instalar nada · [English](README.en.md)

## O problema

A ANP publica toda semana o preço de cerca de 1.200 postos paulistas (4 mil diferentes em três anos), em planilhas soltas, com lacunas e mudanças de formato. Dá para consultar um arquivo, mas não para perguntar "quanto economizo escolhendo o posto na minha cidade?" ou "a bandeira branca é mesmo mais barata?". Este projeto junta três anos dessas planilhas, cuida da qualidade e responde com a fonte, a data e o tamanho da amostra sempre à vista.

![Página de um município no painel: mediana, média e faixa da semana, quanto se economiza escolhendo o posto, etanol ou gasolina e a série semanal contra o estado](docs/img/municipio.png)

*Campinas, gasolina comum, semana de 04/10/2026: o posto mais barato da amostra estava R$ 0,44/L abaixo da mediana, e o etanol custava 61,8% da gasolina.*

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

![Página Estudo do painel: as três perguntas pré-registradas, só a da bandeira branca estável, e a diferença por produto com intervalo de confiança](docs/img/estudo.png)

## O que não funcionou (e está publicado assim mesmo)

- **Machine learning não superou o óbvio.** Um LightGBM para prever a mediana semanal de 1 a 4 semanas ficou **7,9% pior** que "repetir o último valor" num backtest com 24.481 previsões. A previsão publicada é a do método simples, e o [cartão do modelo](docs/model-card.md) explica por quê.
- **A segunda tentativa de previsão ficou perto, mas não passou.** Prevendo se a mediana vai cair, ficar ou subir em 2 semanas, o melhor modelo (LightGBM com sinais do estado) superou a taxa-base em **16%** no teste final, lido uma única vez ([relatório](reports/modelv2/final.md)). Mas a regra pré-registrada também exige probabilidades bem calibradas (erro até 0,05), e ele teve **0,0504**. Não foi aprovado, e nada mudou no produto. O que ajudou foram os sinais do estado; a própria série e o dólar/preço de produtores não acrescentaram ganho.
- **Duas das três hipóteses do estudo não se sustentaram.** "O preço sobe mais do que cai" (Q2) e "os reajustes começam nas cidades grandes" (Q3) não sobreviveram aos subperíodos. Pelo protocolo, o gate que liberaria a modelagem mais ambiciosa **não passou** (1 de 3), e nada foi refeito para passar.

**Em andamento:** o modelo da segunda tentativa, com as probabilidades recalibradas, registra toda semana a chance de cair, ficar ou subir **antes** de a ANP publicar o preço, num arquivo que não se altera. A decisão (oficial ou retirado) sai sozinha com 26 semanas conferidas, por volta de abril de 2027, pela regra [escrita antes da primeira previsão](docs/estudo/protocolo-ao-vivo.md). Até lá o painel mostra essas probabilidades como experimentais.

![Página Previsões do painel: série observada de Campinas, previsão do último valor com intervalo de 80% e, abaixo, as probabilidades experimentais de cair, ficar ou subir](docs/img/previsoes.png)

## Como foi feito

```text
ANP (planilhas semanais) → ingestão (manifesto SHA-256, brutos intactos) → qualidade (regras, quarentena)
  → PostgreSQL (dimensões, fatos, agregações) → API FastAPI somente leitura → painel Streamlit
                                              ↘ estudo pré-registrado e previsões (backtest)
```

- **Dados:** cerca de 800 mil preços em 174 semanas, de 108 municípios. Reexecução sem duplicar, revisões da fonte rastreadas, arquivos com defeito da ANP excluídos com registro ([ADR 0006](docs/decisions/0006-arquivos-da-fonte-excluidos.md)).
- **API:** endpoints de leitura com `data_as_of`, amostra e cobertura em cada resposta, usuário de banco somente leitura ([guia](docs/api.md)).
- **Painel:** 12 páginas: início, município, postos mais baratos, bandeiras, previsões, desempenho ao vivo, variações incomuns, comparação, regiões, margem dos postos, estudo e qualidade ([guia](docs/dashboard.md)).
- **Avaliação ao vivo:** toda semana, antes de o preço sair, as probabilidades de queda, estabilidade e alta são gravadas num registro que não se altera; o placar confere quando a ANP publica, e a decisão sobre o modelo sai com 26 semanas conferidas ([protocolo](docs/estudo/protocolo-ao-vivo.md)).
- **Operação:** testes a cada push e atualização semanal sozinha no GitHub Actions, num banco temporário aberto a partir de um estado cifrado, sem custo ([ADR 0011](docs/decisions/0011-rotina-semanal-no-ci.md)). [Ficha do conjunto de dados](docs/ficha-dados.md) e `scripts/reproduce.py`, que refaz e confere os relatórios.
- **Fontes externas:** dólar do Banco Central e preços de produtores e de distribuição da ANP, com a data em que cada valor ficou disponível, para a modelagem não usar dado do futuro ([ADR 0010](docs/decisions/0010-fontes-externas-e-as-of.md)). Com a distribuição, o painel mostra a **margem bruta de revenda**: quanto o preço nos postos fica acima do preço médio das distribuidoras.
- **Estudo:** [protocolo](docs/estudo/protocolo.md) commitado antes dos resultados, teste final lacrado em código, IC agrupado por posto, bootstrap em blocos de semanas e correção de Holm.
- **Testes:** suíte com dados sintéticos de resposta conhecida, contra PostgreSQL real em Docker; os números do painel foram conferidos contra SQL escrito à parte e as telas, no navegador.
- **Demonstração:** o mesmo painel lendo um pacote de respostas da API ([ADR 0009](docs/decisions/0009-demonstrativo-e-pacote-instantaneo.md)), sem CNPJ nem razão social.

Métodos, resultados e limitações num só lugar: [relatório técnico](docs/relatorio-tecnico.md) ([English](docs/en/technical-report.md)). Decisões em [docs/decisions/](docs/decisions/).

## Rodar localmente

Requisitos: Python 3.14 (a versão testada, no Windows, no macOS e no GitHub Actions) e, para o banco, Docker. No macOS ou no Linux, a partir da raiz:

```bash
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt   # ambiente fixado
cp .env.example .env                                   # defina POSTGRES_PASSWORD (e o DATABASE_URL com a mesma senha)
docker compose up -d --wait                            # PostgreSQL em 127.0.0.1:54329
```

**No Windows (PowerShell)**, os mesmos passos com `python -m venv .venv`, `.\.venv\Scripts\python.exe` no lugar de `.venv/bin/python`, `Copy-Item` no lugar de `cp` e os scripts `.ps1` no lugar dos `.sh` (`.\iniciar.ps1`, `.\atualizar.ps1`).

**Só o painel, sem banco nem API** (lê o pacote do demonstrativo; não precisa de Docker):

```bash
.venv/bin/python -m streamlit run demo/streamlit_app.py      # http://127.0.0.1:8501
```

**Pipeline completo** (os dados brutos não acompanham o Git; o download baixa as semanas da ANP). Os scripts leem a conexão de `DATABASE_URL` no ambiente, não do `.env`; `iniciar.sh` e `atualizar.sh` preparam as variáveis sozinhos:

```bash
export DATABASE_URL="postgresql://radar:$(grep '^POSTGRES_PASSWORD=' .env | cut -d= -f2-)@127.0.0.1:54329/radar"
.venv/bin/python scripts/fetch_anp.py --since 2026-09-01 --ingest   # baixa as semanas da ANP desde essa data e ingere
.venv/bin/python scripts/check_quality.py      # qualidade, quarentena e cobertura
.venv/bin/python scripts/load_db.py            # migra e carrega no PostgreSQL
.venv/bin/python scripts/run_forecasts.py      # backtest, decisão e previsões; relatório em reports/forecasting/
.venv/bin/python scripts/run_study.py          # estudo; relatórios em reports/study/
.venv/bin/python scripts/fetch_external.py     # dólar (BCB), produtores e distribuição (ANP): baixa, confere e carrega
./iniciar.sh                                   # sobe banco, API e painel (http://127.0.0.1:8501)
.venv/bin/python scripts/build_snapshot.py     # regenera o pacote do demonstrativo (API_DATABASE_URL)
```

**Toda semana**, depois que a ANP publica: `./atualizar.sh` baixa, ingere, confere, carrega, atualiza as fontes externas, as previsões, a previsão ao vivo (`scripts/run_live.py`) e o pacote, só se houver semana nova; para na primeira falha e diz em qual etapa. `./atualizar.sh --dry-run` só diz se há semana nova. No repositório público isso já roda sozinho no GitHub Actions ([manual de operação](docs/operacao.md)).

Sem `--since`, `fetch_anp.py` baixa todas as semanas desde 2022 (cerca de 300 MB); use `--dry-run` para ver o que seria baixado. O usuário somente leitura da API é criado por `scripts/create_api_role.py` ([docs/api.md](docs/api.md)). Testes: `.venv/bin/python -m unittest discover -s tests -t .`; com `RADAR_TEST_DATABASE_URL` (a mesma URL, terminando em `/postgres`) rodam também os de banco, API e integração.

## Fonte dos dados

Os preços vêm do **Levantamento de Preços de Combustíveis da ANP** (Agência Nacional do Petróleo, Gás Natural e Biocombustíveis), e os preços de produtores e de distribuição, das páginas de preços da ANP ([gov.br/anp](https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/precos)). Os [termos de uso do portal da ANP](https://www.gov.br/anp/pt-br/acesso-a-informacao/termos-de-uso-privacidade-e-seguranca-1) autorizam a reprodução **sem fins lucrativos**, com citação da fonte; este projeto não tem fins lucrativos. O dólar vem do **Banco Central do Brasil** (SGS, série 1), sob a [ODbL](https://opendatacommons.org/licenses/odbl/); ele não entra no pacote público do demonstrativo. Os arquivos originais **não** estão neste repositório. Medianas, comparações, previsões, margens e demais números são **derivados por este projeto** e não são divulgados pela ANP nem pelo BCB.

## Limites

- É uma **pesquisa por amostragem**: não cobre todos os postos nem dá preço em tempo real, e o preço pode ter mudado depois da coleta.
- Só **São Paulo** é publicado; a estrutura prevê outras UFs (`TARGET_UFS`).
- Variações incomuns são sinais estatísticos, não indício de irregularidade; nenhuma tela associa postos a qualidade do combustível.
- Previsões são estimativas com incerteza, sem garantia de preço.

## Organização

- `src/radar_combustiveis/`: ingestão, qualidade, banco, API (`api/`), painel (`dashboard/`), previsão (`forecasting/`), estudo (`study/`), fontes externas (`external/`), modelagem v2 e avaliação ao vivo (`modelv2/`) e rotina semanal (`weekly.py`).
- `scripts/`: pontos de entrada (download, ingestão, qualidade, carga, previsões, estudo, API, painel, pacote, rotina semanal, estado cifrado e reprodução).
- `iniciar.sh` e `atualizar.sh` (macOS e Linux), `iniciar.ps1` e `atualizar.ps1` (Windows): sobem tudo e fazem a rotina semanal no computador.
- `migrations/`: esquema do PostgreSQL em SQL versionado.
- `reports/`: relatórios reproduzíveis do backtest, do estudo, da modelagem v2 e da ficha dos dados; `reports/ledger/` é o registro imutável das previsões ao vivo e o placar.
- `snapshot/` e `demo/`: pacote e ponto de entrada do demonstrativo.
- `docs/`: [relatório técnico](docs/relatorio-tecnico.md), arquitetura, [desenho do estudo de caso](docs/estudo-de-caso.md), protocolos (`estudo/`), contratos, guias, decisões e capturas (`img/`); `docs/en/` traz em inglês o relatório técnico, o cartão do modelo, a ficha dos dados e o manual de operação.
- `tests/`: testes com dados sintéticos.
- `.github/workflows/`: testes e validação dos workflows a cada push; atualização semanal.

## Licença

Código sob a licença [MIT](LICENSE). Os dados de origem e os números derivados deles seguem os termos de cada fonte: os da ANP permitem uso sem fins lucrativos, com citação.
