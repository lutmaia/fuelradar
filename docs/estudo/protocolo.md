# Protocolo do estudo exploratório (Q1 a Q3)

- **Versão:** 1.0, de 2026-10-13. Pré-registro do Marco 8: escrito e commitado **antes** de qualquer execução das análises. Nenhum resultado de Q1, Q2 ou Q3 foi calculado até este commit.
- **Desenho aprovado:** [estudo-de-caso.md](../estudo-de-caso.md), seções 2, 5 e 6.2. Decisão em [ADR 0008](../decisions/0008-protocolo-do-estudo.md).
- **Código que fixa as janelas:** `src/radar_combustiveis/forecasting/protocol.py`; um teste confere que as datas, a semente e o bootstrap daqui são os mesmos do código.

O que foi consultado nos dados antes deste protocolo, só para desenhá-lo (estrutura, não resultados): os rótulos de bandeira e quantos postos têm cada um; que há no máximo uma observação por posto, produto e semana; a distância, em semanas, entre observações consecutivas do mesmo posto e produto (74% a uma semana); e quantos municípios há por faixa de postos por semana. Nenhuma diferença de preço, frequência de mudança ou defasagem foi calculada.

## 1. Dados e janelas

- **Fonte:** observações vigentes de `fact_price_observation` (`is_current_source_revision`), UF SP, produtos automotivos ativos. Linhas com aviso `preco_extremo` entram na análise principal (são preços plausíveis mantidos pela qualidade) e saem numa checagem de robustez.
- **Janelas** (semana da ANP, `week_start`, domingo):

| Janela | Semanas | Uso |
|---|---|---|
| Desenvolvimento | 2022-11-13 a 2025-06-29 | estudo; treino na modelagem v2 |
| Validação | 2025-07-06 a 2026-03-29 | estudo; seleção na modelagem v2 |
| Teste final | 2026-04-05 em diante | **lacrado**: nem o estudo nem a seleção de modelos leem |

- **O estudo usa só desenvolvimento + validação (2022-11-13 a 2026-03-29).** Os achados de Q1 a Q3 orientam as camadas da modelagem (por exemplo, quem são os municípios "líderes" na camada L2); se usassem o teste final, ele deixaria de ser independente. Os carregadores do estudo passam por `assert_no_holdout`. Depois de o teste final ser lido no Marco 10, as análises podem ser repetidas no período inteiro como **replicação declarada**, nunca no lugar da original.
- **Subperíodos** para a checagem de estabilidade: A = 2022-11-13 a 2024-06-30 e B = 2024-07-07 a 2026-03-29.
- **Lacunas:** semanas sem dado ficam ausentes; nada é interpolado. Variações só são calculadas entre semanas consecutivas com dado.
- **Reprodutibilidade:** cada relatório registra o hash dos dados usados (SHA-256 das linhas ordenadas por `row_key`, com o preço), o commit do código, o commit deste protocolo e a semente **20261013**.
- **Incerteza:** onde houver *bootstrap*, ele é por blocos móveis de **4 semanas**, com **B = 2000** reamostragens, intervalo percentil de 95%.
- **Linguagem:** associação e precedência temporal, nunca causa. Nenhuma saída nomeia posto como suspeito nem fala de qualidade de combustível.

**Produto principal:** `GASOLINA_COMUM` em todas as perguntas, por ter mais postos e menos lacunas. Os demais produtos são análises secundárias, com correção de Holm dentro de cada pergunta.

**Bandeira:** a cadastral atual do posto (`dim_station.brand`). `BRANCA` é bandeira branca; qualquer outro valor é "bandeirado". Sinônimos unificados: `VIBRA ENERGIA` → `VIBRA` e `ALESAT` → `ALE`.

**Porte do município**, pela mediana semanal de postos com gasolina comum na janela do estudo: **grande** (≥ 20), **médio** (8 a 19), **pequeno** (3 a 7, fora de Q3).

## 2. Q1 — bandeira branca

**Pergunta:** no mesmo município, produto e semana, postos de bandeira branca cobram menos que postos bandeirados?

**Hipótese H1:** sim; o preço da bandeira branca é menor.

**Modelo:** regressão linear do log do preço do posto em uma indicadora de bandeira branca, com efeito fixo de município × produto × semana (estimada por transformação *within*). A comparação é sempre entre postos do mesmo mercado na mesma semana; células sem os dois tipos de posto não contribuem. Erro-padrão agrupado por posto.

**Desfecho primário:** diferença percentual 100 × (exp(β) − 1) da bandeira branca em relação aos bandeirados, em gasolina comum, com IC de 95%.

**Secundários:** a mesma diferença para cada um dos outros cinco produtos (Holm entre os cinco); a diferença de cada uma das três maiores bandeiras (`IPIRANGA`, `RAIZEN`, `VIBRA`) contra a branca, em gasolina comum (Holm entre as três).

**Robustez:** (a) efeito fixo de prefixo do CEP (5 dígitos) × produto × semana, como proxy de vizinhança; (b) sem as linhas `preco_extremo`; (c) cada subperíodo separado.

**Achado estável:** IC de 95% do desfecho primário sem o zero, e o mesmo sinal nos dois subperíodos e em (a) e (b).

**Limitações já conhecidas:** a bandeira é a atual, sem histórico de trocas, e postos que mudaram de bandeira são classificados pela de hoje; quem escolhe ser bandeira branca não é aleatório (localização, porte, público), então a diferença é associação, não efeito da bandeira; a ANP pesquisa uma amostra de postos.

## 3. Q2 — dinâmica do preço no posto

**Pergunta:** com que frequência e de quanto o preço de um posto muda, quanto tempo dura, e as altas são diferentes das quedas?

**Unidade:** pares de observações do mesmo posto e produto em **semanas consecutivas** (pares com intervalo maior ficam de fora). Δ = preço(t) − preço(t − 1). Há **mudança** quando |Δ| ≥ R$ 0,01; **alta** se Δ > 0, **queda** se Δ < 0.

**Medidas:** (i) fração dos pares com mudança, e com alta e com queda; (ii) distribuição de |Δ| nas altas e nas quedas (mediana, P10, P90); (iii) duração do preço: um período começa na semana seguinte a uma mudança observada e termina na próxima mudança (evento) ou é censurado numa lacuna de observação do posto ou no fim da janela; curva de Kaplan–Meier em semanas. Períodos sem mudança inicial observada (início da série do posto) ficam de fora.

**Desfecho primário:** assimetria de tamanho, em gasolina comum: mediana de |Δ| nas altas menos mediana de |Δ| nas quedas, em R$/L, com IC de 95% por *bootstrap* em blocos de semanas.

**Secundários:** a mesma assimetria nos outros produtos (Holm entre os cinco); diferença entre a fração de altas e a de quedas; duração depois de uma alta contra depois de uma queda (log-rank), em gasolina comum.

**Robustez:** (a) limiar de mudança de R$ 0,05; (b) sem `preco_extremo`; (c) cada subperíodo.

**Achado estável:** IC de 95% do desfecho primário sem o zero, e o mesmo sinal nos dois subperíodos e em (a) e (b).

**O que Q2 não testa:** "sobe como foguete, cai como pena" é uma afirmação sobre resposta a **custo**; sem um proxy de custo (Marco 9), Q2 relata só a assimetria descritiva. Em um período de preços subindo, altas mais frequentes são esperadas e não indicam assimetria de repasse.

## 4. Q3 — difusão entre municípios

**Pergunta:** os reajustes aparecem primeiro nos municípios grandes e depois nos demais? Com que defasagem?

**Séries:** mediana semanal por município em gasolina comum (`mart_weekly_city_price`). Δ semanal só entre semanas consecutivas com dado e sem `cobertura_baixa`. **Líderes:** os municípios grandes. **Seguidores:** os médios. Série dos líderes, L(t): média das variações semanais dos líderes com dado na semana (pelo menos dois).

**Desfecho primário:** para cada seguidor, regressão de Δ(t) em Δ(t − 1), Δ(t − 2), L(t − 1) e L(t − 2), com constante; teste F de que os coeficientes de L são zero; correção de Holm entre os seguidores, a 5%. O desfecho é a **fração de seguidores** com precedência significativa. **Controle obrigatório:** o teste reverso (Δ do seguidor precedendo L), com a mesma correção; se a fração reversa for parecida, o padrão é tratado como choque comum, não como difusão.

**Secundários:** (a) tempo até acompanhar: eventos estaduais são semanas em que a mediana estadual da gasolina comum varia ao menos R$ 0,10 (alta ou queda); um município acompanha na primeira semana k ≥ 0 em que sua mediana, contra a semana anterior ao evento, se move no mesmo sentido em pelo menos R$ 0,05; janela de 8 semanas, censurada em lacuna, no fim da janela ou em novo evento. Kaplan–Meier por porte (grande × médio) e por sentido (alta × queda). Se um sentido tiver menos de 5 eventos, o limiar desse sentido passa a R$ 0,05, e isso é declarado. (b) Correlação cruzada entre Δ do seguidor e L nas defasagens −4 a +4; a defasagem de maior correlação de cada seguidor vira o mapa de defasagens. (c) Repetição do desfecho primário em etanol hidratado.

**Robustez:** cada subperíodo; limiares de evento de R$ 0,05 e R$ 0,15 no secundário (a).

**Achado estável:** fração de seguidores significativos ≥ 25% na janela inteira, **e** maior que a fração reversa na janela inteira e em cada subperíodo.

**Limitações já conhecidas:** precedência temporal não é causa (um choque comum que chega antes aos grandes produz o mesmo padrão); a semana é a resolução mínima, então defasagens menores que uma semana aparecem como zero; a mediana de um município médio oscila com a amostra de postos da semana; muitos testes, por isso o Holm e o controle reverso.

## 5. Gate G1

Q1 a Q3 têm um desfecho primário cada. **G1 passa se ao menos dois dos três forem achados estáveis**, pelas definições acima. Se não passar, o resultado é publicado como está e o escopo da modelagem (Marco 10) é reavaliado com o usuário antes de seguir; nada é refeito para "passar".

## 6. Entregáveis

- `src/radar_combustiveis/study/`: funções puras de cada análise, sem acesso ao banco; testes com dados sintéticos de resposta conhecida antes de qualquer execução real.
- `scripts/run_study.py`: lê o banco, aplica o lacre, roda Q1 a Q3 e escreve os relatórios.
- `reports/study/`: um relatório por pergunta (método, resultado, robustez, limitações) e um resumo com o G1, com números em JSON e figuras em HTML do Plotly.

## 7. Desvios

Qualquer mudança neste protocolo depois do commit inicial é registrada abaixo, com data, motivo e se foi feita antes ou depois de ver algum resultado. Os relatórios citam os desvios.

| Data | Mudança | Motivo | Antes ou depois de resultados |
|---|---|---|---|
| 2026-10-13 | **Q1:** o erro-padrão agrupado usa a correção G/(G−1)·(N−1)/(N−K), com K contando os efeitos fixos absorvidos, e o IC usa a distribuição t com G−1 graus de liberdade. | O texto dizia só "agrupado por posto"; é a correção usual quando os efeitos fixos não estão contidos nos grupos (mais conservadora). | Antes: esclarecimento de implementação, testado só com dados sintéticos. |
| 2026-10-13 | **Q1:** a comparação das três maiores bandeiras usa só postos `BRANCA`, `IPIRANGA`, `RAIZEN` e `VIBRA`, com a branca como referência. | Definir a amostra do secundário. | Antes. |
| 2026-10-13 | **Q2:** o p-valor dos secundários (para o Holm) é o do *bootstrap*: duas vezes a menor fração de reamostras de cada lado do zero. | O texto pedia Holm sem dizer de onde vem o p-valor. | Antes. |
| 2026-10-13 | **Q3:** um seguidor só é testado com pelo menos 30 semanas utilizáveis (com Δ e defasagens); abaixo disso fica "não testável" e sai do denominador das frações. | Teste F com poucas semanas não tem poder; o texto não fixava um mínimo. | Antes. |
| 2026-10-13 | **Q3:** nas checagens de limiar de evento (R$ 0,05 e R$ 0,15), o critério de "acompanhar" continua R$ 0,05. Δ é calculado no calendário inteiro e depois recortado em cada subperíodo. | Deixar explícito o que a robustez varia. | Antes. |
| 2026-10-13 | **Todas:** uma checagem de robustez sem estimativa (por exemplo, sem dados suficientes) impede o "achado estável"; ausência de evidência não conta como mesmo sinal. | Evitar que falta de dado passe por concordância. | Antes. |
| 2026-10-13 | **Carregador:** as linhas lidas do banco passam a ser ordenadas antes da análise. | Duas execuções diferiam no 16º dígito de Q1 (ordem das somas em ponto flutuante); agora são idênticas byte a byte. Nenhuma regra, limiar ou amostra mudou. | **Depois** da primeira execução; não altera nenhum resultado além desse dígito. |
| 2026-10-13 | **Dependências:** sem `statsmodels`; regressão, teste F, Kaplan–Meier e log-rank estão em `study/` com numpy, pandas e as distribuições do `scipy`, conferidos contra o scipy nos testes. | Menos uma dependência; o scipy já estava instalado. | Antes. |
