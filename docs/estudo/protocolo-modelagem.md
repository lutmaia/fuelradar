# Protocolo da modelagem v2 (Marco 10)

- **Versão:** 1.0, de 2026-10-15. Pré-registro do Marco 10: escrito e commitado **antes** de qualquer treino ou avaliação sobre os dados reais. Nenhum modelo v2 foi rodado até este commit.
- **Desenho aprovado:** [estudo-de-caso.md](../estudo-de-caso.md), seções 6.1 a 6.5, com o desvio de 2026-10-14 do [protocolo do estudo](protocolo.md) (opção B: camada L2 sem os municípios líderes).
- **Código que fixa as constantes:** `src/radar_combustiveis/modelv2/spec.py`; um teste confere que os números daqui são os mesmos do código. As janelas são as de `forecasting/protocol.py`.

## 1. Pergunta e tese

**Q4:** quanto da mudança da mediana semanal de preço nas próximas 1 a 4 semanas é previsível, e a partir de que informação? O Marco 7 mostrou que, para o **valor**, nenhum modelo superou "repetir o último valor". Aqui o alvo principal é a **classe** da mudança (cai, fica, sobe), e cada fonte de informação entra numa camada separada, para atribuir o ganho a ela. **Resultado negativo é resultado** e é publicado como está.

## 2. Séries, origens e janelas

- **Séries:** as mesmas do Marco 7: mediana semanal por município e do estado, em todos os produtos automotivos (`mart_weekly_city_price`, `mart_weekly_state_price`). Lacunas não são preenchidas.
- **Elegibilidade:** a regra do Marco 7 (`forecasting/panel.py`), aplicada em cada origem só com dados até ela: 52 semanas de histórico, 80% das semanas recentes com dado, mediana de pelo menos 3 postos (municípios) e sem cobertura baixa nas 4 semanas mais recentes.
- **Origem:** cada semana (passo de 1 semana). **Horizontes:** h = 1, 2 e 4 semanas.
- **Janelas** (data da origem; ver `forecasting/protocol.py`):

| Janela | Origens | Alvo | Uso |
|---|---|---|---|
| Desenvolvimento | até 2025-06-29 | até 2025-06-29 | treino |
| Validação | 2025-07-06 a 2026-03-29 | **até 2026-03-29** | seleção do candidato e checagens (a) e (d) |
| Teste final | a partir de 2026-04-05 | até a última semana com dado | **lido uma única vez** |

  Pontos de validação cujo alvo cai no teste final ficam de fora: senão o teste seria lido pela porta dos fundos.
- **Treino:** só com pares cuja origem **e** alvo já eram conhecidos na data de corte. Os modelos são retreinados a cada **13 semanas**, com janela crescente: o primeiro ajuste da validação usa o corte 2025-06-29; o do teste, 2026-03-29.

## 3. Alvos

- **Classe** em h semanas: Δ = mediana(t + h) − mediana(t). **Queda** se Δ ≤ −τ, **alta** se Δ ≥ τ, **estável** caso contrário, com **τ = R$ 0,05** (R$/m³ no GNV). Sensibilidade: τ = 0,03 e 0,10.
- **Valor** (secundário): a mediana em t + h.

## 4. Camadas e modelos

Cada camada acrescenta informação à anterior; todas são comparadas nos mesmos pontos.

| Camada | Informação | Variáveis |
|---|---|---|
| **L0** | nenhuma | **taxa-base**: frequência de cada classe por produto e mês do alvo, nos pares de treino; **persistência** (estável com probabilidade 1); para o valor, o último valor e a média móvel de 4 semanas |
| **L1** | a própria série | as variáveis do Marco 7 (nível, diferenças para as defasagens 1, 2, 4, 8, 13, 26 e 52, médias e desvios móveis de 4, 8 e 13 semanas, mediana de 8, postos, razão de postos, cobertura baixa), semana do ano e mês do alvo, produto, nível estadual |
| **L2** | + sinais do estado | variação da mediana estadual do mesmo produto na semana de origem e em 4 semanas; fração dos municípios elegíveis (sem cobertura baixa) cuja mediana subiu e fração que caiu ao menos R$ 0,01 na semana de origem |
| **L3** | + fontes externas | dólar: variação percentual da média semanal na última semana e em 4 semanas; preço de produtores do Sudeste do produto correspondente: variação percentual da última semana publicada e em 4 semanas, **evento de reajuste** (variação absoluta ≥ 2% na última semana publicada) e semanas desde o último evento (limitado a 52) |

- **Disponibilidade (*as-of*):** as variáveis de L3 usam só valores com `available_at` até o **sábado da semana de origem** (`external/asof.py`, ADR 0010). Produtos sem preço de produtor correspondente (etanol hidratado e GNV) têm essas variáveis ausentes.
- **Correspondência de produtores:** gasolina comum e aditivada → `GASOLINA_A_COMUM`; diesel S10 → `DIESEL_A_S10`; diesel comum (S500) → `DIESEL_A_S500`.
- **Pares de treino:** todas as séries com mediana na origem e no alvo (elegíveis ou não), com origem a partir da 60ª semana do painel (para as defasagens existirem); **um modelo por horizonte**.
- **Modelos em L1, L2 e L3**, com parâmetros fixos, sem busca de hiperparâmetros:
  - **logística multinomial** com penalidade L2 (λ = 1,0 sobre variáveis padronizadas pela média e desvio do treino), ajustada por L-BFGS; variável ausente vira 0 com uma indicadora de ausência;
  - **LightGBM multiclasse**, com os parâmetros do Marco 7 (taxa 0,05, 31 folhas, mínimo de 40 por folha, *bagging* 0,8, semente 7, 300 rodadas), objetivo `multiclass`.
  - Para o valor (secundário): LightGBM com objetivo L1 sobre a diferença para o último valor, como no Marco 7.

## 5. Métricas e inferência

- **Desfecho primário (pré-registrado):** *Brier skill score* da classe em **h = 2**, `BSS = 1 − Brier(modelo) / Brier(taxa-base)`, com o Brier multiclasse (soma, nas três classes, do quadrado de probabilidade − indicadora) médio sobre **todos os pontos** (série elegível × origem) da janela.
- **Incerteza:** *bootstrap* em blocos móveis de **4 semanas de origem**, **B = 2000**, semente **20261013**, intervalo percentil de 95%.
- **Secundários** (correção de Holm entre eles, p-valor do *bootstrap* = duas vezes a menor fração de reamostras de cada lado do zero):
  1. ganho de cada camada sobre a anterior no BSS em h = 2 (L1 − L0, L2 − L1, L3 − L2), no melhor modelo de cada camada;
  2. BSS do candidato em h = 1 e h = 4;
  3. *log-loss* e acurácia balanceada do candidato contra a taxa-base;
  4. valor: *skill* de MAE contra o último valor do LightGBM de cada camada, com teste de Diebold–Mariano (erro-padrão HAC com 4 defasagens);
  5. sensibilidade a τ = 0,03 e 0,10 (BSS do candidato em h = 2).
- **Verificação da referência** (relatada, fora do Holm): BSS do candidato contra a taxa-base **só por produto** (sem o mês). Se o ganho contra a referência mensal for muito maior, parte dele vem de a referência por mês ser estimada com menos pontos, e o relatório diz isso.
- **Calibração:** erro esperado de calibração por classe (10 faixas iguais de probabilidade), médio nas três classes.
- **Intervalos do valor** (secundário): conformal temporal com cobertura-alvo de 80%, pelos quantis 10% e 90% dos resíduos da validação, por produto e horizonte; cobertura relatada no teste.

## 6. Seleção e regra de decisão

1. **Na validação**, para cada um dos seis modelos (3 camadas × 2 modelos), o BSS em h = 2 e seu IC. **Candidato** = o de maior BSS entre os que têm **(a) limite inferior do IC de 95% maior que zero**. Se nenhum tem, não há candidato, e o resultado é "nenhuma camada supera a taxa-base".
2. **No teste**, lido uma vez, todos os modelos são avaliados (para a ablação), mas a decisão é só do candidato escolhido na validação. Ele só passa a ser publicado se:
   - **(b)** BSS em h = 2 no teste maior que zero **e** com limite inferior do IC de 95% maior que zero;
   - **(c)** BSS em h = 2 de pelo menos −0,05 em cada produto, porte (grande ≥ 20, médio 8 a 19, pequeno 3 a 7 postos em mediana; estado à parte) e horizonte, nos grupos com pelo menos 200 pontos;
   - **(d)** erro esperado de calibração de até 0,05 no teste;
   - **(e)** reprodutível: dois treinos com os mesmos dados e semente dão probabilidades idênticas.
3. **Publicação:** aprovado, o produto passa a mostrar as probabilidades de queda, estabilidade e alta junto da previsão de valor (desenho, seção 8). Não aprovado, nada muda no produto e o relatório diz por quê. A previsão de **valor** publicada só muda pela regra do Marco 7; os resultados de valor aqui são secundários.

## 7. Lacre do teste final

- O carregador do teste exige um parâmetro explícito e grava uma linha em `holdout_access` (instante, commit do código, finalidade, hash dos dados, linhas lidas) **antes** de devolver os dados.
- Desenvolvimento e validação não conseguem devolver semanas do teste (`assert_no_holdout`), e um teste automatizado confere isso.
- Se o teste for lido mais de uma vez, o relatório declara quantas e por quê.

## 8. Entregáveis

- `src/radar_combustiveis/modelv2/`: alvos, variáveis por camada, modelos, métricas, inferência, seleção e lacre; testes com dados sintéticos de resposta conhecida **antes** da execução real.
- `scripts/run_modelv2.py`: validação (sem ler o teste) e, com `--read-test`, a leitura única do teste.
- `reports/modelv2/`: relatório da validação, relatório final e números em JSON, com hash dos dados, commit do código, commit deste protocolo e semente.

## 9. Limitações já conhecidas

- O teste final tem por volta de 25 origens semanais; para h = 2, os intervalos serão largos.
- `available_at` aproxima o calendário de publicação pela regra de cada fonte (ADR 0010).
- Produtores só por região (Sudeste) e sem etanol; o dólar pesa por meio do custo de importação, com defasagem incerta.
- Os parâmetros fixos podem não ser os melhores; isso é deliberado, para não ajustar nada sobre o teste.

## 10. Desvios

| Data | Mudança | Motivo | Antes ou depois de resultados |
|---|---|---|---|
