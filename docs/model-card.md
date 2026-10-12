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

## Variações incomuns

São semanas em que a mediana saiu da faixa de 99% de variação semanal esperada, com diferença de pelo menos R$ 0,15 e ao menos 3 postos. É um **sinal estatístico**, não indica irregularidade de postos nem de preço.
