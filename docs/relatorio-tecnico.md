# Relatório técnico — Radar de Combustíveis SP

**Versão de 2026-10-16.** Reúne o que o projeto mediu, como mediu e o que não conseguiu mostrar. Cada número vem de um relatório gerado por código e commitado em `reports/`; a seção 9 diz onde está cada um. English version: [en/technical-report.md](en/technical-report.md).

## 1. Resumo

O projeto organiza os preços de combustível pesquisados pela ANP em São Paulo (cerca de 800 mil preços, 174 semanas, de nov/2022 a out/2026) e pergunta: **o que esses preços permitem prever, e o que não permitem?** Métodos e critérios foram escritos e commitados antes de cada resultado.

- **Bandeira branca:** no mesmo município e semana, a gasolina comum da bandeira branca custa **5,59% menos** que a dos postos bandeirados (IC 95% −5,96% a −5,21%), resultado estável em todas as checagens. É associação de preço, não efeito da bandeira.
- **Dinâmica e difusão:** "o preço sobe mais do que cai" e "os reajustes começam nas cidades grandes" **não se sustentaram** nos subperíodos. Pelo protocolo, o gate G1 (2 de 3 achados estáveis) **não passou**.
- **Previsão do valor:** um LightGBM ficou **7,9% pior** que repetir o último valor. A previsão publicada é a do método simples.
- **Previsão da direção** (cai, fica, sobe em 2 semanas): o melhor modelo superou a taxa-base em **16,4%** (*Brier skill*) no teste final, lido uma vez, mas teve erro de calibração de **0,0504**, acima do limite de 0,05, e **não foi aprovado**. O ganho veio dos sinais do estado; dólar e preço de produtores não acrescentaram nada.
- **Avaliação ao vivo:** o mesmo modelo, recalibrado, registra previsões toda semana antes de o preço sair. A decisão sai com 26 semanas conferidas, por volta de abril de 2027. **Em andamento.**

## 2. Perguntas

| Id | Pergunta | Tipo | Situação |
|---|---|---|---|
| Q1 | Quanto a bandeira branca cobra a menos, no mesmo município, produto e semana? | associação | respondida, estável |
| Q2 | Como o preço de um posto muda, e as altas diferem das quedas? | descritiva | respondida, não estável |
| Q3 | Reajustes se espalham entre municípios, e quem se move primeiro? | associação temporal | respondida, não estável |
| Q4 | Quanto da mudança das próximas 1 a 4 semanas é previsível, e a partir de que informação? | preditiva | respondida, candidato não aprovado |
| Q5 | As previsões se sustentam depois que o valor real chega? | prospectiva | em andamento |

Fora do escopo, por decisão: qualquer inferência sobre qualidade ou adulteração de combustível e qualquer acusação a postos. O desenho completo está em [estudo-de-caso.md](estudo-de-caso.md).

## 3. Dados

- **Fonte:** Levantamento de Preços de Combustíveis da ANP, arquivos semanais por posto, mais um histórico semestral recebido no início. Ficha completa em [ficha-dados.md](ficha-dados.md).
- **Cobertura:** estado de São Paulo, 13/11/2022 a 04/10/2026; **174 semanas com dado** de 204 no intervalo, 108 municípios, 4.009 postos e **801.810 observações** vigentes, em seis combustíveis automotivos (GLP fora do escopo).
- **Lacunas:** 19 semanas não têm arquivo na página da ANP (a maior, de 19/10 a 30/11/2025) e 11 têm arquivo com defeito, excluído com motivo registrado em `config/excluded_sources.json` ([ADR 0006](decisions/0006-arquivos-da-fonte-excluidos.md)). Nada é interpolado.
- **Amostra:** a ANP pesquisa uma amostra que muda toda semana. A mediana é de 8 postos por município e semana, e 9,7% das combinações têm menos de 3 postos, tratadas como série fraca.
- **Pipeline:** ingestão com manifesto SHA-256 e arquivos brutos intactos ([ADR 0001](decisions/0001-manifesto-revisoes-e-saida-csv.md)); regras de qualidade, quarentena e precedência entre fontes ([ADR 0002](decisions/0002-qualidade-quarentena-e-precedencia.md)); PostgreSQL com migrações em SQL ([ADR 0003](decisions/0003-banco-postgresql.md)); API somente leitura e painel. 8.653 observações (1,1%) têm aviso de preço extremo e ficam nas medianas; 8 estão em quarentena.
- **Fontes externas** ([ADR 0010](decisions/0010-fontes-externas-e-as-of.md)): dólar do Banco Central e preços de produtores e de distribuição da ANP, cada valor com a data em que ficou disponível (`available_at`), para que nenhuma variável use dado do futuro. Etanol na usina e paridade de importação foram descartados por licença ([triagem](estudo/triagem-fontes-externas.md)).
- **Privacidade:** o banco guarda CNPJ e razão social; o pacote público, os relatórios e o registro das previsões não os trazem.

## 4. Protocolo e salvaguardas

- **Janelas fixas em código** (`forecasting/protocol.py`): desenvolvimento até 29/06/2025; validação de 06/07/2025 a 29/03/2026; **teste final a partir de 05/04/2026, lacrado**. O estudo (Q1 a Q3) usa só desenvolvimento e validação.
- **Lacre:** o carregador do teste exige um parâmetro explícito e grava uma linha em `holdout_access` (instante, commit, finalidade, hash dos dados) antes de devolver os dados. Há uma única linha, de 2026-10-15 às 12h29 (horário de Brasília).
- **Pré-registro verificável pelo Git:**

| Etapa | Protocolo commitado | Primeiro resultado commitado |
|---|---|---|
| Estudo Q1 a Q3 | `efeded4`, 13/10 19h58 ([protocolo](estudo/protocolo.md)) | `4ff5292`, 13/10 22h43 |
| Descritivo para o consumidor | `06d1051`, 13/10 23h04 ([definições](estudo/descritivo.md)) | `c285350`, 13/10 23h05 |
| Modelagem v2 (Q4) | `b79188e`, 15/10 12h25 ([protocolo](estudo/protocolo-modelagem.md)) | leitura do teste às 12h29; `1d2112d`, 15h28 |
| Calibração e avaliação ao vivo (Q5) | `3614baf`, 15/10 15h29 ([protocolo](estudo/protocolo-ao-vivo.md)) | `65fe8c3`, 15h41 |

  No descritivo, o intervalo de um minuto mostra a ordem dos commits, mas não prova que a execução veio depois do commit da definição.
- **Desvios** ficam registrados em cada protocolo, com a data e se vieram antes ou depois dos resultados. Os dois posteriores (ordenação de linhas no estudo, efeito só no 16º dígito; inconsistência de texto na modelagem, sem efeito na decisão) estão declarados como tal.
- **Incerteza:** *bootstrap* em blocos móveis de 4 semanas, B = 2000, semente 20261013; erro-padrão agrupado por posto em Q1; correção de Holm nos secundários.
- **Conferência independente:** os resultados principais foram recalculados em SQL, sem o código do projeto, e coincidiram (coeficiente de Q1, pares e medianas de Q2, as três medidas do descritivo, margens e números do painel).

## 5. Estudo exploratório (Q1 a Q3)

Janela de 13/11/2022 a 29/03/2026: 147 semanas com dado e 675.834 observações. Desfecho primário sempre em gasolina comum. Detalhes no [resumo](../reports/study/resumo.md).

**Q1, bandeira branca.** Regressão do log do preço com efeito fixo de município × semana e erro agrupado por posto: **−5,59%** (IC −5,96% a −5,21%), com 173.992 observações em 13.407 células. Estável em todas as checagens: vizinhança por prefixo de CEP (−5,55%), sem preços extremos (−5,23%), subperíodo A (−5,95%) e B (−5,28%). Nos outros produtos, de −2,17% (GNV, não significativo) a −6,39% (gasolina aditivada). Limitação: a bandeira é a do cadastro atual, e ser bandeira branca não é aleatório. [Relatório](../reports/study/q1.md)

**Q2, dinâmica.** Em 130.079 pares do mesmo posto em semanas seguidas, 22,2% têm mudança; a alta mediana é de R$ 0,12 e a queda, de R$ 0,10. Assimetria: **R$ 0,020** (IC 0,000 a 0,100), com 0,100 no subperíodo A e 0,000 no B: **não estável**. A causa provável é a medida: preços mudam em degraus de R$ 0,10, e a mediana pula entre eles. Trocar a medida agora seria escolher depois de ver os dados. [Relatório](../reports/study/q2.md)

**Q3, difusão.** As variações dos quatro líderes (São Paulo, Campinas, Guarulhos, Ribeirão Preto) melhoram a previsão de **38,6%** dos 83 seguidores, contra 4,8% no sentido reverso, mas **0,0%** no subperíodo A: **não estável**. A maioria dos municípios tem a maior correlação na mesma semana dos líderes, o que a resolução semanal não separa. [Relatório](../reports/study/q3.md)

**Gate G1:** 1 de 3 achados estáveis; o protocolo exigia 2. O resultado foi publicado como está e o escopo da modelagem foi reavaliado com o usuário (camada L2 sem os líderes de Q3).

**Descritivo para o consumidor** ([relatório](../reports/study/descritivo.md)): o etanol compensou (até 70% da gasolina) em **82,6%** das 13.593 combinações de município e semana, de 99,4% em 2024 a 32,8% em 2026; o posto mais barato fica tipicamente **R$ 0,40/L** abaixo da mediana do município, cerca de 4 vezes um reajuste semanal típico (R$ 0,10); a capital foi a região mais barata em gasolina comum (interior e metropolitana +R$ 0,10, litoral +R$ 0,30, em mediana).

## 6. Previsão (Q4)

**Valor da mediana semanal** ([relatório](../reports/forecasting/backtest.md), [ADR 0007](decisions/0007-previsao-baselines-e-candidato.md)). Backtest com origem deslizante a cada 4 semanas, 22 origens avaliadas e 24.481 previsões comuns aos quatro modelos, de 1 a 4 semanas à frente:

| Modelo | MAE (R$/L) | MAE ponderado por postos | Cobertura do intervalo de 80% |
|---|---|---|---|
| Último valor | 0,1064 | **0,0812** | 75,3% |
| Média móvel de 4 semanas | 0,1316 | 0,1098 | 70,6% |
| Mesma semana do ano anterior | 0,4051 | 0,3800 | 73,8% |
| LightGBM global (candidato) | 0,1120 | 0,0876 | 76,6% |

A regra pedia melhora de 5% no MAE ponderado; o candidato ficou **7,9% pior** e piorou em vários grupos. **Publicado: último valor.** Esta etapa não teve pré-registro formal: a melhora mínima de 5% e a ausência de piora por grupo vêm da especificação escrita no início do projeto ([architecture.md](architecture.md), seção 14.8), mas os limites de viés e de cobertura foram escolhidos durante essa etapa, e o Git não mostra se antes ou depois do backtest. Nenhum desses dois limites decidiu o resultado: o candidato falhou nos critérios da especificação.

**Direção da mudança (modelagem v2)** ([protocolo](estudo/protocolo-modelagem.md), [validação](../reports/modelv2/validacao.md), [final](../reports/modelv2/final.md)). Alvo: a mediana em h semanas cai, fica ou sobe, com limiar de R$ 0,05. Desfecho primário: *Brier skill score* (BSS) em h = 2 contra a taxa-base por produto e mês. Três camadas de informação, cada uma com logística multinomial e LightGBM de parâmetros fixos:

| Camada | Informação | BSS na validação (melhor modelo) | BSS no teste (melhor modelo) |
|---|---|---|---|
| L1 | a própria série | +0,080 (logística) | +0,062 (LightGBM) |
| L2 | + sinais do estado | **+0,145 (LightGBM, candidato)** | **+0,164** (IC +0,104 a +0,208) |
| L3 | + dólar e produtores | +0,143 (LightGBM) | +0,152 (LightGBM) |

- **Decisão no teste** (26 origens, 21.387 pontos; 25 origens em h = 2): (b) ganho confirmado ✅, (c) nenhum produto, porte ou horizonte abaixo de −0,05 ✅ (pior grupo: h = 1, +0,105), (e) reprodutível ✅, **(d) erro de calibração 0,0504 > 0,05 ❌. Não aprovado.**
- **Ablação (Holm):** própria série +0,031 (p 1,0); **sinais do estado +0,133 (p < 0,001)**; dólar e produtores −0,012 (p 1,0).
- **Referência:** contra a taxa-base só por produto, o BSS foi +0,172, então o ganho não vem de uma referência mensal ruidosa.
- **Valor (secundário):** o LightGBM da L2 teve MAE 0,1019 contra 0,1088 do último valor (+6,3%), sem significância (Diebold–Mariano, p de Holm 1,0).
- **Mudança de distribuição:** o teste teve 39% de quedas contra 16% na validação.

## 7. Avaliação ao vivo (Q5), em andamento

Pré-registro em [protocolo-ao-vivo.md](estudo/protocolo-ao-vivo.md), commitado antes de qualquer previsão.

- **O que muda:** só a calibração. Um parâmetro de temperatura por horizonte, ajustado uma vez na validação da modelagem v2: T = 1,32 (h = 1), 1,39 (h = 2) e 2,33 (h = 4). Na própria validação, o erro de calibração em h = 2 caiu de 0,050 para 0,036; o número é otimista por ser a amostra do ajuste. O teste final da modelagem v2 não é usado.
- **Registro imutável:** toda semana, antes de a ANP publicar o preço, as probabilidades de cada série elegível vão para `reports/ledger/<origem>.csv`, com o SHA-256 no manifesto, e o commit no GitHub serve de carimbo de data. Primeira origem: 04/10/2026, 837 previsões (279 séries × 3 horizontes).
- **Decisão única**, com 26 origens vencidas em h = 2: passa a oficial se o BSS em h = 2 tiver limite inferior do IC acima de zero, erro de calibração até 0,05 e nenhum grupo abaixo de −0,05. Senão, as probabilidades saem do produto e o resultado é publicado. Até lá aparecem como experimentais.
- **Datas:** alerta de degradação a partir de 13 origens vencidas (por volta de jan/2027); decisão por volta de abr/2027.
- **Situação em 2026-10-16:** 0 origens vencidas.

## 8. Engenharia e operação

- **API** FastAPI somente leitura, com data dos dados, amostra e cobertura em cada resposta ([guia](api.md)); **painel** Streamlit com 12 páginas que só consome a API ([guia](dashboard.md)).
- **Margem bruta de revenda:** preço nos postos menos o preço médio das distribuidoras, por estado, município e posto, em tom neutro; não é lucro, e o custo real do posto não é público.
- **Testes:** 378, com dados sintéticos de resposta conhecida e, para banco, API e integração, contra PostgreSQL real em Docker. As telas foram conferidas no navegador.
- **Operação a custo zero** ([ADR 0011](decisions/0011-rotina-semanal-no-ci.md), [manual](operacao.md)): testes a cada push; rotina diária no GitHub Actions que, com semana nova, restaura um estado cifrado num PostgreSQL temporário, atualiza tudo e commita registro e pacote. Falha injetada e recuperação foram demonstradas no GitHub. O demonstrativo público lê um pacote sem CNPJ nem razão social ([ADR 0009](decisions/0009-demonstrativo-e-pacote-instantaneo.md)).
- **Reprodução:** `scripts/reproduce.py` refaz cada relatório numa pasta temporária e compara: 14 de 16 conferências idênticas e 2 avisos (números iguais, hash das observações diferente, provavelmente porque o estudo rodou num banco com outra numeração interna de postos). O teste final é conferido a partir dos pontos da leitura única, sem novo acesso. **Do zero, em outra máquina** (macOS arm64, clone limpo, tudo baixado da ANP, sem o estado do projeto): as mesmas 801.810 observações, o estudo Q1 a Q3 idêntico inclusive no hash dos dados, e a ficha igual nas contagens (difere só pelos arquivos recebidos à mão no início, que não estão na página da ANP). Os números do LightGBM mudam um pouco entre Windows x86-64 e Mac arm64 com os mesmos dados e a mesma versão (validação L2 +0,140 contra +0,145; backtest +11,0% pior contra +7,9%), sem mudar nenhuma decisão: eles só se reproduzem exatamente na mesma arquitetura.

## 9. Onde está cada número

| Assunto | Relatório gerado | Números em JSON |
|---|---|---|
| Cobertura e qualidade dos dados | [ficha-dados.md](ficha-dados.md) | `reports/dataset/ficha.json` |
| Q1 a Q3 e gate G1 | [resumo](../reports/study/resumo.md) | `reports/study/resultados.json` |
| Descritivo para o consumidor | [descritivo](../reports/study/descritivo.md) | `reports/study/descritivo.json` |
| Previsão do valor | [backtest](../reports/forecasting/backtest.md) | `reports/forecasting/backtest.json` |
| Modelagem v2: validação e teste | [validação](../reports/modelv2/validacao.md), [final](../reports/modelv2/final.md) | `reports/modelv2/validacao.json`, `final.json` |
| Calibração | — | `reports/modelv2/calibracao.json` |
| Avaliação ao vivo | página *Desempenho ao vivo* | `reports/ledger/placar.json` |

Cada relatório registra o hash dos dados, o commit do código e, quando há, o commit do protocolo.

## 10. Limitações

- **Amostra da ANP:** não cobre todos os postos, muda a cada semana e tem lacunas de publicação; a mediana de um município pequeno oscila com a amostra.
- **Associação, não causa:** nenhuma análise identifica efeito causal; bandeira, região e preço refletem localização, porte, frete, tributos e concorrência, que o projeto não separa.
- **Bandeira atual:** sem histórico de trocas de bandeira.
- **Um teste final pequeno:** 25 origens em h = 2, com distribuição de classes diferente da validação; o resultado ao vivo é a prova que falta.
- **Parâmetros fixos:** nenhuma busca de hiperparâmetros, de propósito; outros parâmetros poderiam ir melhor.
- **Fontes externas aproximadas:** `available_at` segue a regra publicada de cada fonte; produtores só por região (Sudeste) e sem etanol; a distribuição chega com 5 a 9 semanas de atraso.
- **O teste final já foi visto:** qualquer nova modelagem que o use precisa de um novo protocolo e de declarar isso.
