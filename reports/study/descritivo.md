# Análises descritivas para o consumidor (Marco 8b)

- **Janela:** semanas de 2022-11-13 a 2026-03-29 (147 com dado); o teste final (2026-04-05 em diante) não foi lido.
- **Dados:** 675.834 observações de SP; hash `1c7b8e52107be9a9…` (observações `0b95e2366b32…`, municípios `89e75d74ae93…`, estado `df2f21c97ce8…`).
- **Código:** `06d105160ac4cf0fe4426e855b0a6c94b357c1f2` · **protocolo:** `d0babef13bcc279ae052668213967979550c6e23` · semente 20261013 · bootstrap B = 2000.
- Método e critérios: [protocolo](../../docs/estudo/protocolo.md), inclusive a tabela de desvios. Resultados são associações, não efeitos causais.

Definições: [descritivo.md](../../docs/estudo/descritivo.md). São medidas descritivas, sem teste de hipótese.

## 1. Etanol ou gasolina?

Etanol compensa (até 70% do preço da gasolina) em **82,6%** das 13.593 combinações de município e semana. Na mediana do estado, em 83,7% das 147 semanas (razão mediana 66,0%; mínima 58,1% na semana de 2024-01-21, máxima 77,5% na de 2022-11-20).

Na última semana da janela (2026-03-29), compensava em 73 de 89 municípios.

| Ano | Município-semanas em que compensa | Base |
|---|---|---|
| 2022 | 0,7% | 134 |
| 2023 | 74,0% | 4.104 |
| 2024 | 99,4% | 4.451 |
| 2025 | 90,3% | 3.745 |
| 2026 | 32,8% | 1.159 |

Municípios com pelo menos 26 semanas com os dois preços: 108.

| Compensa com mais frequência | % das semanas | Razão mediana | Compensa com menos frequência | % das semanas | Razão mediana |
|---|---|---|---|---|---|
| ARACATUBA | 99% | 61,0% | CUBATAO | 43% | 70,1% |
| BIRIGUI | 99% | 61,1% | ITANHAEM | 57% | 69,8% |
| PRESIDENTE PRUDENTE | 98% | 62,0% | SANTOS | 61% | 68,9% |
| VOTUPORANGA | 98% | 60,6% | GUARATINGUETA | 65% | 69,0% |
| ADAMANTINA | 96% | 62,6% | CRUZEIRO | 65% | 68,5% |
| SAO JOSE DO RIO PRETO | 96% | 59,9% | MOGI MIRIM | 66% | 66,1% |
| JOSE BONIFACIO | 96% | 63,2% | AMPARO | 67% | 67,2% |
| MONTE ALTO | 94% | 65,5% | PINDAMONHANGABA | 67% | 66,0% |
| PARAGUACU PAULISTA | 92% | 64,8% | ITAPIRA | 68% | 67,2% |
| OLIMPIA | 92% | 62,8% | ITAPETININGA | 68% | 69,7% |

## 2. Quanto se economiza escolhendo o posto? (gasolina comum)

Em 13.385 combinações de município e semana com pelo menos 5 postos, o posto mais barato fica tipicamente **R$ 0,40/L abaixo da mediana** (P25–P75: R$ 0,23 a 0,57), cerca de 6,7% do preço, ou **R$ 20,00 num tanque de 50 L**. O "meio" do mercado (P25 a P75) tem largura típica de R$ 0,28/L.

**Comparação com o tempo:** uma mudança de preço típica no mesmo posto, de uma semana para a outra, é de R$ 0,10/L; a economia de escolher o posto equivale a 4,0 vezes esse reajuste típico.

Contando os preços marcados como extremos, a economia mediana seria R$ 0,40/L.

| Porte | Município-semanas | Economia mediana (R$/L) |
|---|---|---|
| grande | 572 | 0,50 |
| medio | 10.961 | 0,40 |
| pequeno | 1.852 | 0,29 |

Onde escolher o posto faz mais diferença (pelo menos 26 semanas):

| Município | Semanas | Economia mediana (R$/L) |
|---|---|---|
| ITAPETININGA | 105 | 0,81 |
| SAO CAETANO DO SUL | 147 | 0,80 |
| SANTO ANDRE | 147 | 0,80 |
| SAO PAULO | 147 | 0,76 |
| DIADEMA | 147 | 0,73 |
| PRESIDENTE PRUDENTE | 147 | 0,70 |
| ASSIS | 147 | 0,70 |
| SANTOS | 147 | 0,65 |
| JOSE BONIFACIO | 132 | 0,64 |
| MOGI MIRIM | 82 | 0,60 |

## 3. Capital × região metropolitana × litoral × interior

Diferença da mediana semanal da região para a da capital (negativo = mais barato que a capital):

| Produto | Região | Diferença mediana (R$/L) | Semanas mais barata que a capital | Semanas |
|---|---|---|---|---|
| Gasolina comum | Região metropolitana (sem a capital) | +0,100 | 1% | 147 |
| Gasolina comum | Litoral | +0,300 | 0% | 147 |
| Gasolina comum | Interior | +0,100 | 0% | 147 |
| Etanol hidratado | Região metropolitana (sem a capital) | +0,100 | 0% | 147 |
| Etanol hidratado | Litoral | +0,340 | 0% | 147 |
| Etanol hidratado | Interior | +0,025 | 18% | 147 |
| Diesel S10 | Região metropolitana (sem a capital) | +0,100 | 4% | 147 |
| Diesel S10 | Litoral | +0,300 | 1% | 147 |
| Diesel S10 | Interior | +0,000 | 19% | 147 |

Diferença mediana por ano, gasolina comum (R$/L):

| Região | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|
| Região metropolitana (sem a capital) | +0,090 | +0,100 | +0,100 | +0,033 | +0,060 |
| Litoral | +0,200 | +0,242 | +0,268 | +0,300 | +0,400 |
| Interior | +0,090 | +0,100 | +0,100 | +0,060 | +0,100 |

Municípios de cada região presentes nos dados: capital (1): SAO PAULO; região metropolitana (sem a capital) (18): BARUERI, CARAPICUIBA, COTIA, DIADEMA, EMBU DAS ARTES, GUARULHOS, ITAPECERICA DA SERRA, ITAQUAQUECETUBA, MAUA, MOGI DAS CRUZES, OSASCO, POA, RIBEIRAO PIRES, SANTO ANDRE, SAO BERNARDO DO CAMPO, SAO CAETANO DO SUL, SUZANO, TABOAO DA SERRA; litoral (8): CARAGUATATUBA, CUBATAO, GUARUJA, ITANHAEM, PRAIA GRANDE, SANTOS, SAO VICENTE, UBATUBA; interior (81).

## Limitações

- A ANP pesquisa uma amostra; o "posto mais barato" é o mais barato da amostra da semana, e os preços de uma semana podem ser de dias diferentes.
- A regra dos 70% é aproximada e não substitui o consumo do próprio carro.
- A mediana regional pesa mais os municípios com mais postos pesquisados; as listas de região foram escritas à mão.
- Descritivo não é causa: diferenças regionais refletem frete, tributos, concorrência e composição da amostra, que este relatório não separa.
