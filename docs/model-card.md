# Cartão do modelo — previsão da mediana semanal de preços

Documento curto e honesto sobre o que a previsão faz e o que não faz. Decisões em [ADR 0007](decisions/0007-previsao-baselines-e-candidato.md); relatório numérico reproduzível em [reports/forecasting/backtest.md](../reports/forecasting/backtest.md).

## O que é previsto

A **mediana semanal** do preço de revenda de um produto, em um município paulista ou no estado, de 1 a 4 semanas à frente, com um intervalo de 80%. Não é o preço de um posto, nem de um dia.

## Modelo em uso

**Último valor observado** (baseline): a previsão da mediana das próximas semanas é a mediana da semana mais recente. O intervalo vem dos erros desse método em um teste com dados passados.

Um modelo de machine learning (**LightGBM global**) foi treinado e avaliado em um backtest com origem deslizante. **Ele não foi aprovado**: ficou 7,9% pior no erro ponderado e piorou mais de 5% em vários grupos. Por isso o baseline permanece publicado.

## Como foi avaliado

- 24.481 previsões avaliadas, em 22 datas de corte de 4 em 4 semanas, usando só dados anteriores a cada corte.
- Os quatro modelos (três baselines e o candidato) são comparados nos mesmos pontos.
- Erro médio do modelo publicado: R$ 0,106 por litro (R$ 0,043 em 1 semana; R$ 0,115 em 4 semanas, ponderado por postos).
- O intervalo de 80% contém o valor real em 75% dos casos.

## Quando não há previsão

Séries com menos de 52 semanas de histórico, dados em menos de 80% das semanas recentes, menos de 3 postos por semana (municípios), cobertura baixa recente ou sem dado na semana mais recente. Nesses casos o painel mostra o motivo, nunca um número. Hoje 279 de 600 séries têm previsão.

## Limitações

- Não considera petróleo, câmbio, impostos nem política de preços; mudanças bruscas não são previstas.
- Mudanças reais de preço costumam ser em degraus de R$ 0,10, o que limita a precisão.
- O backtest cobre nov/2022 a out/2026 e semanas ausentes na fonte aparecem como lacunas.
- Resultado de uma configuração fixa; não houve busca de hiperparâmetros.

## Modelagem v2 (Marco 10): classe da mudança, não aprovada

Pré-registro em [protocolo-modelagem.md](estudo/protocolo-modelagem.md); números em [reports/modelv2/final.md](../reports/modelv2/final.md).

- **Pergunta:** a mediana vai **cair, ficar ou subir** (limiar de R$ 0,05) em 1, 2 e 4 semanas? Desfecho primário: *Brier skill* em 2 semanas contra a taxa-base por produto e mês.
- **Camadas:** L1 (a própria série), L2 (+ sinais do estado: variação estadual e fração de municípios que subiram ou caíram), L3 (+ dólar e preço de produtores, só o que já estava publicado na data). Logística multinomial e LightGBM em cada camada, parâmetros fixos.
- **Candidato escolhido na validação** (jul/2025 a mar/2026): **L2 com LightGBM**, BSS +0,145 (IC 95% +0,081 a +0,195).
- **Teste final** (abr a out/2026, 25 origens, lido uma vez): BSS **+0,164** (IC +0,104 a +0,208), sem piora em nenhum produto, porte ou horizonte, reprodutível. **Erro de calibração 0,0504**, acima do limite pré-registrado de 0,05: **não aprovado**. O produto não mudou e a previsão de valor publicada continua "último valor".
- **O que cada camada trouxe** (teste, Holm): a própria série, nada significativo (+0,031); os sinais do estado, **+0,133** (p < 0,001); dólar e produtores, nada (−0,012).
- **Valor (secundário):** o LightGBM da L2 teve MAE 6,3% menor que "último valor", mas sem significância depois da correção (p de Holm 1,0).
- **Limitações:** probabilidades um pouco mal calibradas (o próximo passo natural seria uma etapa explícita de calibração, num novo protocolo); o período de teste teve mais quedas (39%) do que a validação (16%); o preço de produtores é do Sudeste e não há etanol nele.

## Variações incomuns

São semanas em que a mediana saiu da faixa de 99% de variação semanal esperada, com diferença de pelo menos R$ 0,15 e ao menos 3 postos. É um **sinal estatístico**, não indica irregularidade de postos nem de preço.
