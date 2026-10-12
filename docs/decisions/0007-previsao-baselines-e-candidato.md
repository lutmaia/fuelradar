# 0007 — Previsão: baselines, candidato LightGBM e regra de aprovação

- **Status:** aceita (Marco 7, 2026-10-12)
- **Contexto:** a seção 14 da [arquitetura](../architecture.md) pede previsão da mediana semanal em 1 a 4 semanas, com intervalo, validação temporal e um candidato que só substitui o baseline se ganhar de forma consistente. Com o histórico carregado (174 semanas, 2022-11 a 2026-10) a regra de 52 semanas passa a ser alcançável.

## Decisão

1. **Alvo e origem.** Mediana semanal por (município ou estado, produto), nas semanas `t+1` a `t+4`, a partir da semana mais recente com dado. Semanas sem dado ficam como lacuna (NaN), nunca interpoladas.
2. **Elegibilidade (14.2), medida na origem e só com dados até ela:** pelo menos 52 semanas com dado; dados em 80% das últimas 104 semanas; mediana de 3 postos por semana (só municípios, últimas 26 semanas); sem cobertura baixa nas últimas 4 semanas; dado na semana de origem. Série inelegível devolve motivos, nunca um número. Na origem de 04/10/2026, 279 de 600 séries são elegíveis.
3. **Baselines (14.3):** último valor; média móvel de 4 semanas (exige 3 das 4); mesma semana do ano anterior.
4. **Candidato:** LightGBM global (API nativa, sem scikit-learn), um modelo para todos os produtos e municípios, prevendo a **diferença** para o último valor observado (alvo estacionário), com horizonte, lags de 1 a 52 semanas, médias e desvios móveis, semana do ano, produto, município e cobertura como features. **Hiperparâmetros fixados antes de ver o backtest e sem busca**, objetivo L1 (a métrica principal é o MAE), `num_threads=1` e `deterministic=True`.
5. **Backtest com origem deslizante (14.6):** uma origem a cada 4 semanas (35 planejadas, 30 com séries elegíveis); a cada origem o candidato é retreinado só com alvos já conhecidos naquela semana e avaliado nas 4 semanas seguintes. Sem divisão aleatória. As 8 primeiras origens só alimentam a calibração dos intervalos. As métricas valem para os pontos comuns aos quatro modelos.
6. **Intervalos (14.9):** previsão central mais quantis P10/P90 dos resíduos (real − previsão) de origens **anteriores**, por (nível, produto, horizonte), com fallback para (nível, horizonte). Nenhum intervalo usa resíduo da própria origem. Série sem resíduos suficientes não recebe previsão.
7. **Métricas (14.7):** MAE (principal), MAE ponderado pelo número de postos da semana prevista, WAPE, MASE (escala: erro absoluto médio de 1 passo até a origem), viés (previsão − observado), cobertura e largura do intervalo.
8. **Aprovação (14.8):** o candidato só vence se (a) melhora o MAE ponderado em pelo menos 5% contra o melhor baseline, (b) não piora mais de 5% em produto, nível, horizonte ou porte de município, (c) tem viés de até 25% do MAE, (d) tem cobertura do intervalo de 80% entre 70% e 90%, e (e) é reprodutível (duas execuções idênticas). Os limites de (c) e (d) são escolhas deste projeto. **Se falhar, o melhor baseline é o modelo publicado.**
9. **Publicação:** tabelas `model_version`, `forecast`, `forecast_eligibility` e `anomaly` (migração 0004); no máximo um modelo publicado (índice único parcial), o anterior fica arquivado para rollback; reexecutar com os mesmos dados substitui a versão. A API lê pelo papel `radar_reader`, sem acesso a `code_sha` nem `artifact_uri`.
10. **Variação incomum (14.10):** independente do candidato, usa o baseline de 1 semana. É marcada quando a mediana observada sai do intervalo de **99%** dos resíduos do backtest (por nível e produto, com pelo menos 200 resíduos), a diferença é de pelo menos **R$ 0,15**, a série era elegível, a semana não tem cobertura baixa e há ao menos 3 postos. Rótulo e texto são estatísticos; nenhuma página fala em fraude ou adulteração.
11. **Preço por bandeira:** `GET /prices/by-brand` compara a mediana semanal por bandeira (inclusive a bandeira branca) no mesmo recorte e semana; bandeiras com menos de 3 postos não são detalhadas. A página diz que preço não é qualidade.
12. **Dependências novas:** `lightgbm==4.7.0` (o candidato da arquitetura; traz `scipy`, que também é novo). Nada de `scikit-learn`: as métricas são poucas linhas de numpy.

## Alternativas consideradas

- **Regressão quantílica no LightGBM** (P10/P50/P90): mais complexa e, com o candidato já perdendo no ponto central, sem o que ganhar. A calibração por resíduos vale igual para qualquer modelo e foi mais simples de auditar.
- **Busca de hiperparâmetros no backtest:** deixaria a métrica otimista (seleção sobre os mesmos dados de avaliação). Fica como trabalho futuro, com janelas finais reservadas só para teste.
- **Detectar variações incomuns pelo candidato:** exigiria previsões semanais retroativas dele; como o baseline é o modelo publicado e mais simples de explicar, a detecção usa o baseline.
- **Interpolar semanas ausentes:** descartado; inventaria dado.

## Consequências e limitações

- **Resultado real:** o candidato **não foi aprovado**. No MAE ponderado ele ficou 7,9% pior que "último valor" (0,0876 contra 0,0812 R$/L) e piorou mais de 5% em vários grupos. O baseline "último valor" é o modelo publicado. Preços de combustível têm degraus e mudam pouco de semana a semana, o que torna difícil bater "o preço de hoje" em 1 a 4 semanas.
- **O intervalo de 80% cobre 75,3%** dos valores reais no backtest, abaixo da meta nominal, dentro da faixa aceita (70% a 90%). A previsão publicada é incerta: o erro médio é de R$ 0,11/litro.
- **Mesma semana do ano anterior** é muito pior (viés de −R$ 0,34/L): os preços subiram ao longo dos anos e o baseline sazonal ignora a tendência.
- **Só 279 de 600 séries** têm previsão; municípios pequenos ou com lacunas ficam sem número, por desenho.
- **Sem variáveis externas** (petróleo, câmbio, política de preços, impostos). O candidato tem alguma relação com a mudança real (correlação de cerca de 0,24 no teste exploratório), então um modelo mais regularizado ou com variáveis externas é uma direção honesta, a ser avaliada com janelas de teste separadas.
- **Reavaliação semanal e retreino mensal** (14.11) dependem de agendamento: Marco 8.
- **Não verificado:** estabilidade do resultado com outro passo de origem ou outro período; a escolha de `step=4` foi por tempo de execução.
