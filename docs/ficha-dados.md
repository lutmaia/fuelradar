# Ficha do conjunto de dados

Gerada por `scripts/dataset_card.py` a partir do banco; os números não são digitados à mão. Dados detalhados em `reports/dataset/ficha.json`; arquivos de origem com SHA-256 em `reports/dataset/fontes.csv`.

## Origem

Levantamento de Preços de Combustíveis (LPC) da ANP, arquivos semanais por posto revendedor, mais os históricos publicados pela ANP para o período anterior. Fontes externas: dólar (Banco Central, SGS 1) e preços de produtores e de distribuição da ANP.

## Cobertura

Estado de São Paulo, de 13/11/2022 a 04/10/2026: 174 semanas com dado de 204 no intervalo, 108 municípios e 4.009 postos. 801.810 observações vigentes.

Semanas sem dado, nunca preenchidas: 19 semanas sem arquivo na página da ANP (27/11/2022; 25/12/2022; 08/01/2023; 02/04/2023; 16/04/2023 – 30/04/2023; 31/12/2023; 03/03/2024; 14/04/2024; 12/05/2024; 22/12/2024; 19/10/2025 – 30/11/2025) e 11 semanas com arquivo da ANP com defeito, fora por decisão registrada em `config/excluded_sources.json`, com o motivo de cada um: planilhas que o leitor não abre ou que trazem resumos no lugar dos postos (04/12/2022 – 18/12/2022; 01/01/2023; 26/02/2023 – 26/03/2023; 09/04/2023; 29/06/2025).

### Por combustível

| Combustível | Observações | Postos | Municípios | Semanas |
|---|---:|---:|---:|---:|
| GASOLINA_COMUM | 208.553 | 3.983 | 108 | 174 |
| ETANOL_HIDRATADO | 206.123 | 3.987 | 108 | 174 |
| GASOLINA_ADITIVADA | 163.696 | 3.248 | 108 | 174 |
| DIESEL_S10 | 139.030 | 3.133 | 108 | 174 |
| DIESEL_COMUM | 74.941 | 1.771 | 108 | 174 |
| GNV | 9.467 | 166 | 54 | 174 |

### Por ano

| Ano | Observações | Semanas |
|---|---:|---:|
| 2022 | 7.588 | 2 |
| 2023 | 192.881 | 40 |
| 2024 | 223.751 | 48 |
| 2025 | 193.335 | 44 |
| 2026 | 184.255 | 40 |

### Por região

| Região | Municípios | Semanas com dado (mediana) |
|---|---:|---:|
| Interior | 81 | 160 |
| Região metropolitana | 18 | 172 |
| Litoral | 8 | 170 |
| Capital | 1 | 174 |

## Tamanho da amostra

Em cada município e semana, a mediana é de 8 postos pesquisados (10% dos casos com até 3, 10% com 15 ou mais). 8.279 das 85.249 combinações de município e semana (9,7%) têm menos de 3 postos e são tratadas como série fraca.

## Qualidade

8.653 observações (1,1%) têm aviso (preço extremo para o combustível: 8.653); ficam no banco e entram nas medianas. 114.204 linhas não são vigentes porque outro arquivo da ANP traz o mesmo dado (revisão ou precedência entre fontes, ADR 0002). Em quarentena (fora das contas): 8 (preços diferentes para a mesma chave).

## Bandeiras

Participação nas observações: BRANCA 36,3%, IPIRANGA 23,9%, RAIZEN 19,7%, VIBRA 17,8%, ALE 1,2%, NEXTA 0,7%; demais, 0,4%.

## Fontes externas

| Fonte | Publicador | Licença | Linhas | Período |
|---|---|---|---:|---|
| anp_distribuicao | ANP | Termos de uso do portal da ANP: reprodução sem fins lucrativos, com citação da fonte | 170.755 | 23/08/2020 – 29/08/2026 |
| anp_produtores | ANP | Termos de uso do portal da ANP: reprodução sem fins lucrativos, com citação da fonte | 15.089 | 31/12/2012 – 04/10/2026 |
| bcb_sgs_1 | Banco Central do Brasil | ODbL (Open Database License) | 992 | 01/11/2022 – 14/10/2026 |

## Vieses e limitações

- A ANP pesquisa uma **amostra** de postos, não todos; municípios pequenos têm poucos postos e séries irregulares.
- A amostra muda de semana para semana; a mediana de um município pode variar por troca de postos, não só de preço.
- Preço de venda ao consumidor; o preço de compra é raro e não é usado.
- Lacunas de publicação ficam como lacunas: nada é interpolado.
- Bandeira é a declarada no arquivo da semana; trocas de bandeira ao longo do tempo não são reconstruídas.

## Privacidade e licenças

- Os arquivos da ANP trazem CNPJ, razão social e endereço. O banco local guarda esses campos; o pacote público do demonstrativo e os relatórios **não** trazem CNPJ nem razão social.
- Dados da ANP reproduzidos sem fins lucrativos, com citação e link, conforme os termos de uso do portal gov.br. O dólar (ODbL) entra no banco, mas não no pacote público.
- Os arquivos brutos não estão no repositório; `fontes.csv` lista o SHA-256 de cada um e a URL dos baixados pelo projeto (os históricos e agregados obtidos à mão no Marco 1 não têm URL registrada).
