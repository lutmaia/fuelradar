# Próximos passos

Notas de retomada do projeto. **Ao começar uma nova sessão de trabalho, leia este arquivo primeiro** e depois o [PLAN.md](../PLAN.md). Atualizado em 2026-10-15 (fim do Marco 10).

## Onde paramos

- **Marcos 0 a 8 concluídos**: ingestão, qualidade, banco, API, painel, previsões, variações incomuns e comparação por bandeira (239 testes aprovados contra o PostgreSQL do Docker).
- **Resultado do Marco 7:** o candidato LightGBM **não foi aprovado** (7,9% pior que "último valor" no MAE ponderado); o baseline "último valor" está publicado. Relatório em `reports/forecasting/backtest.md`, cartão em [model-card.md](model-card.md).
- **Desenho da versão completa** (estudo de caso, marcos 8 a 13) em [estudo-de-caso.md](estudo-de-caso.md), com as decisões do usuário já incorporadas (as de protocolo em 2026-10-13: Q1 a Q3 enxutas, partição da seção 6.2, gate G1, desfecho primário e regra de decisão mantidos, modo sombra dispensado, demonstrativo no Streamlit Community Cloud). **Desenho aprovado em 2026-10-13.**
- **Resultado do Marco 8:** Q1 (bandeira branca −5,6%) é achado estável; Q2 e Q3 não. **Gate G1 não passou** (1 de 3). Resumo em `reports/study/resumo.md`.
- **Marco 8b (descritivo):** etanol × gasolina, economia escolhendo o posto e regiões, em `reports/study/descritivo.md`. No painel desde 2026-10-13: seção *Na hora de abastecer* (município) e veredito do etanol (página inicial).
- **2026-10-14:** páginas **Regiões** e **Estudo** no painel (parte do Marco 9); **demonstrativo público no ar** em https://fuelradar-a5kwciypheseufpbfh6ggv.streamlit.app/ (pacote instantâneo, [ADR 0009](decisions/0009-demonstrativo-e-pacote-instantaneo.md)) e README reescrito como estudo de caso; escopo do Marco 10 decidido (**opção B**); triagem das fontes externas feita ([registro](estudo/triagem-fontes-externas.md)). 319 testes aprovados contra o PostgreSQL do Docker.

## Decisões já tomadas (não reabrir sem motivo)

1. **Custo zero:** nada pago. Atualização semanal no CI gratuito de repositório público, banco efêmero e pacote instantâneo; hospedagem só em plano gratuito.
2. **Fontes externas só com licença simples**; dúvida significa descartar.
3. **Demonstrativo público: sim.** Em modo público não vão CNPJ nem razão social.
4. **Repositório público**, para portfólio. Licença **MIT** (arquivo `LICENSE`).
5. **Estudo enxuto:** três análises (Q1 a Q3), ampliável depois.
6. **Sem acusação a postos:** nenhuma tela associa postos a qualidade ou adulteração.

## Pendências imediatas

- [x] **Identidade dos commits:** decidido em 2026-10-13 manter o e-mail pessoal; o histórico não será reescrito.
- [x] **Atribuição à ANP no painel:** rodapé em todas as páginas, inclusive quando a API falha (2026-10-13, teste novo; 240 testes aprovados contra o PostgreSQL do Docker).
- [ ] **Regenerar o perfil dos dados** (`scripts/profile_anp_data.py`) com caminhos relativos, se for refeito: os relatórios commitados foram higienizados à mão.
- [x] **Conferir o que ficou público:** repositório conferido pelo usuário no GitHub em 2026-10-13.

## Marco 8 — protocolo e estudo exploratório (concluído)

1. [x] **Protocolo (2026-10-13):** [docs/estudo/protocolo.md](estudo/protocolo.md), janelas em `forecasting/protocol.py`, [ADR 0008](decisions/0008-protocolo-do-estudo.md) e `tests/test_protocol.py`. **Precisa estar commitado antes da etapa 3**; nenhum resultado foi calculado.
2. [x] **Funções puras em `study/` (2026-10-13):** `common`, `q1`, `q2`, `q3` e `gate`, sem acesso ao banco; `tests/test_study.py` com dados sintéticos de resposta conhecida (efeito plantado recuperado, nenhum efeito onde não há, lacre do teste final, cobertura do IC agrupado, Kaplan–Meier e log-rank iguais aos do scipy). Sem `statsmodels`: `scipy` (já instalado) passou a dependência direta. Detalhes de implementação que o texto não fixava estão na tabela de desvios do protocolo, todos **antes** de resultados. Ainda não rodou sobre dados reais.
3. [x] **Execução real (2026-10-13):** `scripts/run_study.py` sobre 2022-11-13 a 2026-03-29, relatórios reproduzíveis em `reports/study/`, conferência independente em SQL; ver "Verificação do Marco 8" no PLAN.

## Ordem decidida (2026-10-13), pensando em portfólio

1. [x] **Páginas Regiões e Estudo** no painel (parte do Marco 9 que não depende de fonte externa). **Feito em 2026-10-14:** endpoints `/prices/regions` e `/prices/rankings`, regiões em `regions.py` (as mesmas listas do estudo), página Estudo lendo `reports/study/*.json` (ADR 0005, adendo). 309 testes aprovados contra o PostgreSQL do Docker (16 novos); medianas regionais, economia de Araraquara e etanol de Adamantina recalculados em SQL direto no fato e iguais; as duas páginas fotografadas no Edge headless, com três defeitos visuais corrigidos ("None" na tabela, capital e metropolitana com azuis parecidos, rótulo cortado). O Marco 9 continua aberto: faltam as fontes externas.
2. [x] **Demonstrativo online e README contando a história** (2026-10-14: modo instantâneo, pacote commitado, `demo/streamlit_app.py` e README de estudo de caso prontos; 319 testes aprovados contra o PostgreSQL do Docker (10 novos, entre eles o contrato cliente instantâneo × API e a privacidade do pacote), [ADR 0009](decisions/0009-demonstrativo-e-pacote-instantaneo.md); publicado pelo usuário no Streamlit Community Cloud em 2026-10-14: https://fuelradar-a5kwciypheseufpbfh6ggv.streamlit.app/ ; páginas Início e Regiões conferidas no ar, com os mesmos números do local): adianta parte dos Marcos 12 (hospedagem no Streamlit Community Cloud, pacote instantâneo) e 13 (README de estudo de caso: problema, três achados, um gráfico, link da demo).
3. [x] **Fontes externas** (Marco 9 concluído em 2026-10-15: três fontes carregadas, *as-of*, página *Margem dos postos*; ver "Verificação do Marco 9" no PLAN) (resto do Marco 9: dólar do Banco Central e preço de produtores da ANP), depois o Marco 10. **Triagem feita em 2026-10-14** ([registro](estudo/triagem-fontes-externas.md)): dólar aprovado (ODbL, API testada); produtores com cobertura completa mas **sem licença declarada**, aguardando decisão do usuário; etanol na usina e paridade de importação descartados. Nada foi ingerido.

Motivo: hoje ninguém consegue ver o projeto sem instalar tudo; a demo e um README curto valem mais para quem avalia do que uma análise nova. O guia de estudo das escolhas de método (para entrevistas) **fica fora do repositório**, por decisão do usuário em 2026-10-14.

Defeito visto em 2026-10-14 e **corrigido em 2026-10-15**: a linha de referência de *Comparar municípios* mostrava "None"; a tabela passou a `st.table`, que mostra "—".

## Próximas decisões

- [x] **Escopo do Marco 10 reavaliado (2026-10-14): opção B.** A camada L2 fica sem os líderes de Q3, só com os sinais do estado; o resto do desenho não muda. Registrado na tabela de desvios do protocolo. Alternativas consideradas: manter como desenhado, só dados externos (L0 × L1 × L3) e pular para o Marco 11.
- [x] **Fontes da ANP decididas (2026-10-15): as duas.** Preços de **produtores** (Sudeste, atraso de ~1 a 2 semanas) como sinal de custo para a camada L3 do Marco 10, e preços de **distribuição** (SP e 108 municípios, com etanol) para medir **quanto o posto cobra acima da distribuidora**, por município e por posto. Os termos de uso da ANP (sem fins lucrativos, citação com link) valem para as duas.
- [x] **Dólar (2026-10-15): solução simples.** Entra como fonte (ODbL), mas a série não vai ao pacote público do demonstrativo; só números e gráficos calculados com ela, com crédito ao Banco Central.
- [x] **Margem por posto (2026-10-15):** "margem bruta estimada", em tom neutro ("segundo os dados da ANP, a estimativa é de…"), com o aviso de que não é lucro e de que o custo real do posto não é público.
- [x] **Rodapé do painel e README (2026-10-15):** link da ANP e dos termos de uso no rodapé; README diz que os dados seguem os termos de cada fonte.
- [x] **Marco 10 — modelagem v2 (pedido em 2026-10-15), em etapas:**
  1. [x] **Protocolo e código testados com dados sintéticos (2026-10-15):** [protocolo-modelagem.md](estudo/protocolo-modelagem.md) (pré-registro), `modelv2/` (alvos, camadas L1 a L3, logística e LightGBM, métricas, *bootstrap*, regra de decisão), migração `0006_holdout_access`, `scripts/run_modelv2.py`; 359 testes aprovados. Sem dependência nova (logística com numpy e scipy). Nenhuma execução sobre dados reais.
  2. [x] **Commit do protocolo pelo usuário** (`b79188e`), antes da primeira execução real.
  3. [x] **Validação:** candidato L2 com LightGBM (BSS +0,145); sanidade conferida (semanas sem pontos explicadas, sem vazamento).
  4. [x] **Teste lido uma vez:** BSS +0,164, mas calibração 0,0504 > 0,05 → **não aprovado**; nada muda no produto. Ver "Verificação do Marco 10" no PLAN e o [cartão do modelo](model-card.md).
- [ ] **Marcos 10b e 11 — calibração e avaliação ao vivo (pedido em 2026-10-15), em etapas:**
  1. [x] **Protocolo e código testados com dados sintéticos:** [protocolo-ao-vivo.md](estudo/protocolo-ao-vivo.md); só a temperatura das probabilidades é ajustada (um T por horizonte, na validação do Marco 10); registro imutável em `reports/ledger/`, pontuação, placar e decisão com 26 semanas; `/forecasts` com probabilidades experimentais, `/models/scoreboard`, página *Desempenho ao vivo*; migração `0007_live`; 373 testes aprovados.
  2. [ ] **Commit do protocolo pelo usuário**, antes de ajustar a temperatura e de gerar a primeira previsão.
  3. [ ] `scripts/run_live.py --fit-calibration` (uma vez) e `scripts/run_live.py` (toda semana, depois de carregar a semana nova da ANP); commit semanal de `reports/ledger/`.
- [ ] **Enviar ao GitHub:** os commits desde 2026-10-15 estão só locais, a pedido do usuário. O pacote do demonstrativo foi regenerado com a margem; ao enviar, o Streamlit Community Cloud republica sozinho.
- [x] **Ingestão das fontes aprovadas (2026-10-15):** `external/`, migração `0005`, `scripts/fetch_external.py`, `xlrd` como dependência nova; o dólar fica fora do pacote público.

As páginas Regiões e Estudo, a outra parte do Marco 9, estão prontas (2026-10-14).

## A verificar mais adiante (Marco 12)

- Se o site da ANP aceita download a partir dos servidores do CI.
- Limites e termos dos planos gratuitos de CI e de hospedagem do demonstrativo.
- Tamanho do pacote instantâneo.

## Preferências de trabalho do projeto

- **Commits:** manter o trailer `Co-Authored-By` nas mensagens; não reescrever histórico.
- **Banco:** somente Docker Compose (PostgreSQL 16), sempre por `127.0.0.1` (nunca `localhost`).
- **Escopo:** uma tarefa por marco solicitado; não avançar automaticamente (veja [AGENTS.md](../AGENTS.md)).
- **Dados brutos da ANP:** nunca editar, apagar nem enviar ao GitHub.
- **Resultados:** diferenciar o que foi verificado do que é hipótese; não inventar ganho.

## Como colocar tudo de pé

Instalação no [README](../README.md). Com o ambiente pronto e o `.env` criado, `.\iniciar.ps1` sobe o PostgreSQL do Docker, a API e o painel.
