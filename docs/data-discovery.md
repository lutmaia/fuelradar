# Descoberta dos dados reais da ANP — Marco 1

Análise local em 2026-09-29 dos nove arquivos recebidos em `data/raw/`, preservados byte a byte. Resultados da leitura completa de 21 planilhas, sem presumir conteúdo pelos nomes. URLs individuais e datas de download não foram fornecidas nem verificadas. Não houve download automático.

Artefatos: [script](../scripts/profile_anp_data.py), [JSON detalhado](../reports/data-profile/profile.json), [resumo gerado](../reports/data-profile/summary.md), [contrato](data-contract.md) e [testes sintéticos](../tests/test_profile_anp_data.py).

## Inventário

| Arquivo em raw | Natureza | Linhas de dados | Planilhas |
|---|---|---:|---:|
| mensal-municipios-jan2022-2025.xlsx | Histórico mensal municipal | 118.444 | 1 |
| mensal-municipios-desde-jan2026.xlsx | Histórico mensal municipal | 20.438 | 1 |
| mensal-regioes-desde-jan2013.xlsx | Histórico mensal regional | 5.247 | 1 |
| resumo_semanal_lpc_2026-09-06_2026-09-12.xlsx | Resumos em cinco níveis | 2.727 | 5 |
| resumo_semanal_lpc_2026-09-13_2026-09-19.xlsx | Resumos em cinco níveis | 2.767 | 5 |
| resumo_semanal_lpc_2026-09-20_2026-09-26.xlsx | Resumos em cinco níveis | 2.843 | 5 |
| revendas_lpc_2026-09-06_2026-09-12.xlsx | Observações individuais | 19.516 | 1 |
| revendas_lpc_2026-09-13_2026-09-19.xlsx | Observações individuais | 20.076 | 1 |
| revendas_lpc_2026-09-20_2026-09-26.xlsx | Observações individuais | 20.434 | 1 |

As linhas dos resumos somam níveis sobrepostos, **não** observações nem postos. `.gitkeep` não é dado e não entra no perfil.

## Formato físico e esquema

Todos são XLSX verdadeiros: contêiner ZIP/OOXML, XML declarado UTF-8. Não há delimitador CSV; colunas são células. O JSON lista membros internos (workbook, worksheets, sharedStrings, estilos e metadados). Nenhum conteúdo foi extraído para raw. Não há CSV nem ZIP externo real.

| Família | Cabeçalho real | Colunas nomeadas | Particularidade |
|---|---:|---:|---|
| Mensal municipal | 17 | 18 | Preâmbulo e notas antes dos dados |
| Mensal regional | 17 | 16 | Excel declara 21 colunas; cinco finais sem dados/cabeçalho |
| Revendas | 10 | 15 | Aba POSTOS REVENDEDORES |
| Resumo CAPITAIS/MUNICIPIOS/ESTADOS | 10 | 12 | ESTADOS usa ESTADOS e REGIAO |
| Resumo REGIOES/BRASIL | 10 | 11 | Sem UF; não isola SP |

Existem linhas vazias formatadas ao fim de resumos. MUNICIPIOS da primeira semana tem 2.353 linhas de dados e 1.525 vazias após o cabeçalho. `max_row` não é contagem de registros. Nomes originais completos por esquema estão no resumo gerado e no JSON.

## São Paulo

Totais incluem GLP para diagnóstico integral. O MVP deverá usar combustíveis automotivos. Datas mensais são **referências mensais**, não dias em que todos os preços foram coletados.

| Fonte | Período real SP | Linhas SP | Municípios SP | CNPJs distintos SP |
|---|---|---:|---:|---:|
| Mensal municipal 2022–2025 | jan/2022 a dez/2025 | 29.185 | 108 | Indisponível |
| Mensal municipal 2026 | jan/2026 a ago/2026 | 4.901 | 100 | Indisponível |
| Revendas 06–12/set | 07/09/2026 a 12/09/2026 | 5.130 | 87 | 1.804 |
| Revendas 13–19/set | 14/09/2026 a 18/09/2026 | 5.365 | 91 | 1.916 |
| Revendas 20–26/set | 21/09/2026 a 25/09/2026 | 5.458 | 94 | 1.928 |
| União das três semanas | 07/09/2026 a 25/09/2026 | 15.953 | 97 | 2.380 |

A união conta CNPJ normalizado, não soma postos das semanas. Um estabelecimento reaparece em produtos/datas diferentes. Com GLP, “CNPJ de revenda” é mais preciso que “posto automotivo”.

Sem GLP: **13.842 observações, 97 municípios e 1.635 CNPJs distintos** nas três semanas. Por semana: 4.473/4.638/4.731 registros e 1.183/1.222/1.239 CNPJs automotivos. Nos mensais municipais: 25.129 linhas automotivas em 2022–2025 e 4.129 em 2026.

MUNICIPIOS dos resumos tem 536/565/585 linhas SP e 87/91/94 municípios. CAPITAIS tem sete linhas SP por arquivo, todas da capital; ESTADOS tem sete agregados SP. Não somar abas. Regiões/Brasil não isolam SP. O histórico regional cobre jan/2013 a ago/2026, mas **não** é uma série de SP.

### Produtos e unidades

| Produto canônico | Observações SP nas três semanas |
|---|---:|
| GASOLINA_COMUM | 3.606 |
| GASOLINA_ADITIVADA | 2.754 |
| ETANOL_HIDRATADO | 3.571 |
| DIESEL_S500 | 1.288 |
| DIESEL_S10 | 2.493 |
| GNV | 130 |
| GLP, fora do MVP | 2.111 |

Os seis primeiros produtos compõem o recorte automotivo. Revendas usa ETANOL/DIESEL S500/DIESEL S10; agregados usam ETANOL HIDRATADO/OLEO DIESEL/OLEO DIESEL S10. O preâmbulo explicita OLEO DIESEL/S500. GASOLINA COMUM e ADITIVADA ficam distintas. **GASOLINA isolado não apareceu**.

Unidades: `R$ / litro` versus `R$/l`; `R$ / m³` versus `R$/m³` e `R$/m3`; `R$ / 13 kg` versus `R$/13kg`. ESTADO/ESTADOS usa nomes completos, incluindo SAO PAULO; não foram observadas siglas. Revendas contém as 27 UFs. O normalizador aceita SP e SAO PAULO e preserva UF para expansão.

### Jundiaí

| Fonte | Cobertura | Registros | CNPJs distintos |
|---|---|---:|---:|
| Mensal 2022–2025 | 48 meses, sete produtos | 336 | Indisponível |
| Mensal 2026 | Oito meses, jan–ago, sete produtos | 56 | Indisponível |
| Revendas 06–12/set | Nenhum registro de Jundiaí | 0 | 0 na amostra |
| Revendas 13–19/set | Coleta em 15/09/2026 | 78 | 25 |
| Revendas 20–26/set | Coleta em 24/09/2026 | 78 | 25 |
| União das semanas | 15/09 a 24/09/2026 | 156 | 28 |

Sem GLP: 140 observações e 20 CNPJs na união. Cada semana com dados tem 70 observações automotivas e 17 CNPJs. Os resumos municipais também não contêm Jundiaí na primeira semana e têm sete linhas nas duas seguintes. Ausência na pesquisa não significa ausência de estabelecimentos.

## Qualidade encontrada

- Nenhuma duplicata exata nas 21 planilhas. Nenhuma repetição da chave candidata nas revendas, inclusive na união SP. Mensais municipais e resumos não repetem a chave dentro de cada planilha.
- O histórico **regional** tem dois conflitos de chave em ago/2014, GNV: SUDESTE (linhas 606/607) e SUL (608/609), com valores diferentes. Não foram removidos; esse arquivo não é elegível para SP.
- Nenhum preço negativo, zero ou texto monetário inválido nas colunas perfiladas. Nenhum preço individual de revenda ausente. Isso não comprova todas as regras futuras de negócio.
- Nos dois mensais municipais, margem e cinco campos de distribuição estão 100% preenchidos com `-` (ausência). Não converter em zero nem tratar distribuição como preço individual de compra.
- No regional, os cinco campos de distribuição têm 2.501 ausências cada; margem tem 2.380; coeficiente de variação de revenda tem 121. Misturam números e marcadores textuais.
- Em revendas SP, FANTASIA falta em 3.287/3.378/3.523 registros, COMPLEMENTO em 4.638/4.827/4.877 e BAIRRO em sete por semana. Não exigir esses campos para identificar observações.
- CNPJ e CEP são inteiros: restaurar zeros no formato textual. NÚMERO/FANTASIA/COMPLEMENTO têm tipos mistos. Preços são int/float e datas são datetime Excel. Tipo físico é diferente de tipo canônico.
- Bandeiras só estão disponíveis nas revendas: 56/55/54 rótulos nos arquivos completos, incluindo BRANCA, VIBRA e marcas de GLP. Domínios/frequências no JSON; bandeira não identifica estabelecimento.
- A heurística de extremos sinalizou 26/18/17 preços individuais SP: **61 sinais de inspeção**, não erros comprovados. Gasolina aditivada SP chega a R$ 9,89/l na última semana. Nenhuma linha foi excluída.

O JSON registra ausências por coluna (também SP), tipos físicos, domínios originais, datas, duplicidades e preços por produto/unidade. A heurística usa cercas de três IQR por arquivo/planilha/coluna/produto/unidade; mudanças históricas podem produzir extremos legítimos.

## Implicações

1. Históricos recebidos são agregados. Não se reconstrói mediana, CNPJ ou datas individuais a partir de médias mensais.
2. Resumos têm intervalo de referência; revendas têm coleta real. A última semana termina em 26/set, mas a última coleta SP observada é 25/set.
3. Cabeçalhos não começam na primeira linha. Mapear nomes por família, não posições fixas.
4. Normalizar produtos/unidades explicitamente, preservando originais. Não misturar GLP e litros.
5. Linhas, contagem reportada de postos e CNPJs únicos são métricas diferentes. Somar contagens por mês/produto não produz postos únicos.

## Reprodução

Na raiz, PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install openpyxl==3.1.5
.\.venv\Scripts\python.exe scripts/profile_anp_data.py "data/raw/*.xlsx"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip check
```

Se `.venv` existir, use-o sem recriar. Ambiente utilizado: Python 3.14.7; requisito do projeto: Python 3.12+. Dependência direta: **openpyxl 3.1.5**, leitura XLSX; transitiva instalada: **et-xmlfile 2.0.0**, suporte XML. Sem pandas, pytest ou ferramentas de ingestão.

O script aceita caminhos/padrões entre aspas e `--output-dir`. XLSX é sequencial (`read_only=True`), usando valores armazenados (`data_only=True`), sem recalcular fórmulas. Leitura integral é necessária para contagens, cobertura, ausências e duplicatas exatas. Não mantém tabelas completas: guarda contadores, conjuntos de identidade e vetores de preços para quartis. Procura cabeçalho nas primeiras 50 linhas.

CSV infere UTF-8/UTF-8 BOM ou CP1252 e delimitadores comuns. ZIP externo aceita CSV/XLSX sem extrair caminhos na origem; conteúdo inesperado causa erro. Suporte sintético não homologa arquivos reais ainda não recebidos.

Falhas retornam código não zero sem gerar novo relatório final. Relatório anterior, se existente, permanece: conferir retorno do comando e `generated_at_utc`. Saída deve ficar fora de raw e das pastas de entrada.

## Situação e próximo passo

O histórico agregado e as semanas reais foram analisados e o contrato dos formatos observados foi preenchido. Próximo: **Marco 2 — ingestão histórica e semanal**. Antes de implementar o ramo histórico individual, obter manualmente um CSV/ZIP por revenda e validar seu esquema. Nenhum pipeline definitivo, banco, API, painel, ML ou nuvem foi implementado.

## Verificações executadas

| Comando/checagem | Resultado observado |
|---|---|
| `python -m venv .venv` | Ambiente local criado, Python 3.14.7 |
| `.\.venv\Scripts\python.exe -m pip install openpyxl` | Instalou openpyxl 3.1.5 e et-xmlfile 2.0.0; versão direta depois fixada no pyproject e no comando de reprodução |
| `.\.venv\Scripts\python.exe scripts/profile_anp_data.py "data/raw/*.xlsx"` | Retorno 0; nove arquivos e 21 planilhas; JSON e Markdown gerados |
| `.\.venv\Scripts\python.exe -m unittest discover -s tests -v` | 21 testes em 0,089 s, OK |
| `.\.venv\Scripts\python.exe -m pip check` | No broken requirements found. |
| Checagem local com hashlib, tomllib, pathlib e Git temporário | Nove hashes raw idênticos; arquitetura intacta; hash do script corresponde ao JSON; TOML e links locais válidos; 15 regras Git conferidas |

As fixtures cobrem cabeçalho com preâmbulo, colunas obrigatórias ausentes, moeda com vírgula, UF, SP/SAO PAULO, produtos, datas, município, CNPJ, unidades, duplicatas, GLP separado, ausências/preços inválidos, extremos, agregados sem CNPJ, região sem UF, arquivo vazio, coluna sem cabeçalho, CSV UTF-8/CP1252, ZIP CSV/XLSX, conteúdo ZIP inesperado e execução de ponta a ponta do **perfil** com preservação do original. Não são testes de um pipeline de ingestão.

Preservação adicional: comparados hashes dos nove arquivos antes da exploração com os hashes ao final. Nenhum repositório Git foi inicializado; nenhum dado foi publicado. Somente Marcos 0 e 1 estão concluídos em [PLAN.md](../PLAN.md).

## Aprendizado deste marco

O ponto central é a **granularidade**: uma linha de média mensal não equivale a uma pesquisa individual de preço. O contrato explicita como interpretar cada campo sem perder seu significado. O perfil reproduzível mede o que existe, os testes isolam casos pequenos e os hashes comprovam que os originais permanecem iguais. Limitações como falta de histórico individual são parte do resultado, não algo a preencher com suposições.
