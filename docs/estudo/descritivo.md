# Análises descritivas para o consumidor (Marco 8b)

- **Versão:** 1.0, de 2026-10-13, escrita antes da primeira execução.
- **Natureza:** descritiva. Não há hipótese, teste nem regra de decisão; os números medem e descrevem. Por isso não há gate nem correção para múltiplas comparações.
- **Janela:** a mesma do [protocolo](protocolo.md): semanas de 2022-11-13 a 2026-03-29. O teste final continua lacrado.
- **Código:** `src/radar_combustiveis/study/descriptive.py`; execução por `scripts/run_study.py --descritivo`.

## 1. Etanol ou gasolina?

- **Razão** = mediana semanal do etanol hidratado ÷ mediana semanal da gasolina comum, no mesmo município e semana. Semanas com cobertura baixa em qualquer dos dois ficam de fora.
- **Compensa** quando a razão é **até 70%**. É a regra prática usual (o etanol rende cerca de 70% da gasolina por litro); o ponto exato varia com o carro e o uso.
- **Medidas:** fração de município-semanas em que compensa, no total e por ano; a mesma conta para a mediana do estado; menor e maior razão estadual; municípios em que compensa com mais e menos frequência (com pelo menos 26 semanas com os dois preços); quantos municípios compensavam na última semana da janela.

## 2. Quanto se economiza escolhendo o posto?

- Por município e semana, gasolina comum, só semanas com **pelo menos 5 postos** pesquisados.
- **Economia** = mediana dos preços − menor preço; também a faixa P25–P75 (o "meio" do mercado). Em R$/L, em % da mediana e num tanque de **50 L**.
- Preços com aviso `preco_extremo` ficam fora da conta principal, porque o mínimo é sensível a um único valor fora da curva; a versão com eles também é relatada.
- **Referência temporal:** tamanho típico (mediana) de uma mudança de preço no mesmo posto entre semanas consecutivas, como em Q2. A comparação diz se escolher o posto pesa mais ou menos que esperar a semana.
- Também: por porte do município e os municípios com maior economia típica (pelo menos 26 semanas).

## 3. Capital × região metropolitana × litoral × interior

- **Regiões:** capital (São Paulo); metropolitana (os outros 38 municípios da RMSP); litoral (Baixada Santista, Litoral Norte e Iguape, Ilha Comprida e Cananéia); interior (os demais). As listas foram escritas à mão em `descriptive.py`, e o relatório mostra quais municípios de cada região estão nos dados.
- **Medida:** mediana semanal de todos os preços da região, por produto (gasolina comum, etanol hidratado e diesel S10); diferença para a capital na mesma semana; mediana e média da diferença, fração de semanas em que a região é mais barata e mediana por ano.

## Limitações já conhecidas

- A ANP pesquisa uma amostra de postos; o "menor preço" é o menor da amostra, não necessariamente o menor do município.
- Os preços de uma mesma semana podem ser de dias diferentes.
- A mediana regional pesa mais os municípios com mais postos pesquisados (a capital domina a própria região; Campinas e Ribeirão Preto pesam no interior).
- A regra dos 70% é uma aproximação; o relatório não recomenda combustível para um carro específico.
