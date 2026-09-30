# Contrato de dados proposto — versão 0.1

Validado exploratoriamente nos nove XLSX locais descritos em [data-discovery.md](data-discovery.md). Este é um contrato dos formatos observados, não um pipeline de ingestão. O [perfil estruturado](../reports/data-profile/profile.json) contém nomes originais, tipos, ausências e hashes por arquivo/planilha. A [arquitetura](architecture.md) permanece a especificação principal.

## Granularidades e limites

- **R — revendas semanais:** observação candidata por UF, município, CNPJ, produto, unidade e data de coleta. Única família analisada com preço individual e identidade do estabelecimento.
- **M — mensal municipal:** agregado por mês, UF, município, produto e unidade. `MÊS` não é data de coleta individual. Não fornece CNPJ, bandeira, mediana nem postos únicos no intervalo.
- **S — resumo semanal:** agregados municipais/capitais, estaduais, regionais e nacionais em planilhas separadas. Não concatenar níveis como observações independentes.
- **MR — mensal regional:** não possui UF; não pode alimentar resultados de SP, mesmo quando `REGIÃO=SUDESTE`.

GLP é descrito porque está nas fontes, mas está fora do MVP automotivo. Não eliminar GLP do raw. O perfil separa `automotive_*` (sem GLP) dos totais de diagnóstico. Não foi criada camada publicada.

Não há CSV histórico individual nem ZIP externo nos arquivos recebidos. Seu esquema continua **não homologado**: o suporte CSV/ZIP do script foi exercitado apenas com fixtures sintéticas. Não presumir que um futuro CSV terá o mesmo esquema dos XLSX.

## Identificação e observações

`—` significa ausente nesse formato. Exemplos ilustram normalização; identificadores exemplificados são sintéticos. No pipeline futuro, campo obrigatório ausente/inválido deverá sinalizar e impedir aceitação da linha, preservando origem e motivo. O perfil apenas mede problemas.

| Canônica | Coluna R | Coluna M / S | Tipo esperado | Obrigatoriedade e ausência | Normalização e validação | Exemplo válido |
|---|---|---|---|---|---|---|
| `uf` | ESTADO | ESTADO; ESTADOS na aba estadual S | texto de 2 letras | Obrigatória para SP; sem UF não atribuir SP | Trim, espaços, maiúsculas sem acentos para busca; nome completo → sigla; desconhecido → sinalizar | SAO PAULO → SP |
| `municipality_name` | MUNICÍPIO | MUNICÍPIO, se municipal | texto | Obrigatória em R/M/S municipal; nula nos outros níveis | Guardar original; comparação com trim, espaços simples, maiúsculas sem acentos; não inferir IBGE | Jundiaí → JUNDIAI |
| `region` | — | REGIÃO ou REGIAO; também MR | texto | Opcional; nulo se ausente | Normalizar texto; SUDESTE nunca significa SP | SUDESTE |
| `cnpj` | CNPJ | — | texto de 14 dígitos | Obrigatória em R; nula nos agregados | Inteiro Excel → texto com zeros à esquerda; remover pontuação; rejeitar fração/não dígitos/excesso de tamanho | 123456780001 → 00123456780001 |
| `legal_name` | RAZÃO | — | texto | Descritiva; ausência → nulo com aviso | Texto e trim, preservar grafia | POSTO EXEMPLO LTDA |
| `trade_name` | FANTASIA | — | texto opcional | Nulo permitido; não identifica o posto | Texto/trim; aceitar números como texto | POSTO EXEMPLO |
| `address` | ENDEREÇO | — | texto opcional | Ausência → nulo com aviso | Texto/trim; sem geocodificação | RUA EXEMPLO |
| `address_number` | NÚMERO | — | texto opcional | Nulo permitido | Preservar números e S/N; não exigir inteiro | S/N |
| `address_complement` | COMPLEMENTO | — | texto opcional | Nulo permitido | Texto/trim; ausência não invalida preço | LOJA 2 |
| `neighborhood` | BAIRRO | — | texto opcional | Nulo permitido | Texto/trim, preservar grafia | CENTRO |
| `postal_code` | CEP | — | texto de 8 dígitos, opcional | Nulo permitido; inválido → aviso | Inteiro Excel → texto com zeros à esquerda; remover hífen; não tratar como quantidade | 1234567 → 01234567 |
| `brand` | BANDEIRA | — | texto opcional | Nulo permitido com aviso | Original e versão normalizada; BRANCA não é ausência; sem enumeração fechada | BRANCA |
| `product` | PRODUTO | PRODUTO, também MR | enumeração textual | Obrigatório; desconhecido → sinalizar | Mapeamento explícito abaixo; preservar original | GASOLINA_COMUM |
| `unit` | UNIDADE DE MEDIDA | Mesmo nome, também MR | enumeração textual | Obrigatória | Remover espaços e normalizar m³/m3; validar produto; não misturar litro/m³/13 kg | BRL/L |
| `collection_date` | DATA DA COLETA | — | data | Obrigatória em R; indisponível nos agregados | Data Excel ou DD/MM/AAAA/ISO; rejeitar impossível; número sem estilo Excel não é data implícita | 2026-09-24 |
| `sale_price` | PREÇO DE REVENDA | — | decimal positivo | Obrigatório em R | Vírgula → Decimal; aceitar número nativo; rejeitar não finito, texto inválido e ≤ 0; não arredondar antes de avaliar precisão | 5,99 → 5.99 |

CNPJ/CEP chegam como inteiros. Restaurar zeros é necessário, mas **não comprova validade cadastral**. O script verifica formato de CNPJ, não dígitos verificadores. Normalização/validação completa de CEP e descrições fica para o Marco 3.

## Campos próprios dos agregados

Não substituem `sale_price` nem `collection_date`.

| Canônica | M / MR | S | Tipo | Obrigatoriedade e ausência | Normalização e validação | Exemplo |
|---|---|---|---|---|---|---|
| `reference_month` | MÊS | — | data, primeiro dia do mês | Obrigatória nos mensais | Validar dia 1; não inventar coleta diária | 2026-08-01 |
| `period_start` | — | DATA INICIAL | data | Obrigatória em S | Data válida; início ≤ fim | 2026-09-20 |
| `period_end` | — | DATA FINAL | data | Obrigatória em S | Não confundir com última coleta observada | 2026-09-26 |
| `reported_station_count` | NÚMERO DE POSTOS PESQUISADOS | Mesmo nome | inteiro ≥ 0 | Obrigatória; ausência → sinalizar | Não somar produtos/meses/níveis; não equivale a CNPJs distintos no intervalo | 17 |
| `mean_sale_price` | PREÇO MÉDIO REVENDA | Mesmo nome | decimal positivo | Obrigatória | Parser decimal; mínimo ≤ média ≤ máximo | 6.10 |
| `min_sale_price` | PREÇO MÍNIMO REVENDA | Mesmo nome | decimal positivo | Esperada; ausência → aviso | Mínimo ≤ máximo | 5.99 |
| `max_sale_price` | PREÇO MÁXIMO REVENDA | Mesmo nome | decimal positivo | Esperada; ausência → aviso | Máximo ≥ mínimo | 6.29 |
| `stddev_sale_price` | DESVIO PADRÃO REVENDA | Mesmo nome | decimal ≥ 0 | Opcional; nulo permitido | Zero válido; não é preço | 0.10 |
| `cv_sale_price` | COEF DE VARIAÇÃO REVENDA | Mesmo nome | decimal ≥ 0 | Opcional; nulo permitido | Não é valor monetário | 0.02 |
| `mean_retail_margin` | MARGEM MÉDIA REVENDA | — | decimal opcional | Nulo permitido | `-` → nulo; não usar como preço de venda | 0.20 |
| `mean_distribution_price` | PREÇO MÉDIO DISTRIBUIÇÃO | — | decimal positivo opcional | Nulo permitido | `-` → nulo; não é preço de compra de posto identificado | 4.50 |
| `min_distribution_price` | PREÇO MÍNIMO DISTRIBUIÇÃO | — | decimal positivo opcional | Nulo permitido | Preservar ausência; não imputar | 4.20 |
| `max_distribution_price` | PREÇO MÁXIMO DISTRIBUIÇÃO | — | decimal positivo opcional | Nulo permitido | Preservar ausência; não imputar | 4.80 |
| `stddev_distribution_price` | DESVIO PADRÃO DISTRIBUIÇÃO | — | decimal ≥ 0 opcional | Nulo permitido | Zero válido | 0.10 |
| `cv_distribution_price` | COEF DE VARIAÇÃO DISTRIBUIÇÃO | — | decimal ≥ 0 opcional | Nulo permitido | Zero válido; não é preço | 0.02 |
| `aggregation_level` | Derivado da planilha/esquema | Derivado da planilha/esquema | enumeração | Obrigatória | município/capital/estado/região/país; manter separados | municipality |

Coerência mínimo/média/máximo, dia 1, contagem inteira e validação completa de endereço são propostas para tratamento futuro; não são declaradas como verificações executadas pelo perfil. Nenhum agregado fornece mediana de preços individuais.

## Produto e unidade

| Original observado | Canônico | Unidade canônica |
|---|---|---|
| GASOLINA COMUM | GASOLINA_COMUM | BRL/L |
| GASOLINA ADITIVADA | GASOLINA_ADITIVADA | BRL/L |
| ETANOL (R); ETANOL HIDRATADO (agregados) | ETANOL_HIDRATADO | BRL/L |
| DIESEL S500 (R); OLEO DIESEL (agregados) | DIESEL_S500 | BRL/L |
| DIESEL S10 (R); OLEO DIESEL S10 (agregados) | DIESEL_S10 | BRL/L |
| GNV | GNV | BRL/M3 |
| GLP | GLP, fora do MVP | BRL/13KG |

O preâmbulo dos agregados informa que OLEO DIESEL se refere a diesel B S500 comum. ETANOL segue a correspondência proposta entre as famílias; validar novamente ao adicionar fontes. `GASOLINA` isolado **não foi observado**: o alias GASOLINA_COMUM é testado sinteticamente e exige confirmação antes de homologar fonte que o utilize.

`R$/l`/`R$ / litro` → BRL/L; `R$/m3`/`R$/m³`/`R$ / m³` → BRL/M3; `R$/13kg`/`R$ / 13 kg` → BRL/13KG. Desconhecidos são sinalizados, sem associação por similaridade.

## Ausências, preços e cobertura

- O perfil reconhece célula vazia, texto vazio, `-`, `NA`, `N/A` e `NULL` como ausentes. Nas fontes foram observados vazios e `-`; os demais têm suporte preventivo. Ausência nunca vira zero.
- A triagem de extremos usa `[Q1 − 3×IQR, Q3 + 3×IQR]`, quartis inclusivos, por planilha/coluna/produto/unidade, separando SP do conjunto completo. IQR é a distância entre primeiro e terceiro quartil.
- É uma heurística **exploratória**, não um limite homologado: não exclui registros nem indica irregularidade. Nos históricos mistura meses e pode refletir variação temporal legítima. Limites por período/produto ficam para qualidade.
- Datas de download não foram fornecidas; modificação do arquivo não é data de coleta/download.
- `normalize_uf(valor) == "SP"` identifica SP. O normalizador conhece nomes/siglas das UFs para preservar a dimensão; produto permanece limitado a SP. SUDESTE não identifica SP.
- Município normalizado identifica localidade somente junto da UF. Resolução por IBGE e variações mais complexas não foi implementada.

## Chaves candidatas

- R: `(uf, municipality_name_normalized, cnpj, product, unit, collection_date)`.
- M: `(uf, municipality_name_normalized, product, unit, reference_month)`.
- S: `(aggregation_level, uf/localidade, município quando aplicável, product, unit, period_start, period_end)`.
- MR: `(region, product, unit, reference_month)`, diagnóstico fora da publicação SP.

São candidatas, não autorização para deduplicar automaticamente. O perfil conta repetições por planilha e na união das revendas SP. MR tem dois conflitos com valores diferentes. Revisões futuras devem distinguir origem/versão: chave igual em revisão posterior não pode ser descartada cegamente. Unidade e granularidade impedem misturar observações incompatíveis.

## Auditoria

| Campo | Regra |
|---|---|
| `source_file_name` | Nome recebido; `file` no JSON |
| `source_file_sha256` | SHA-256 dos bytes originais; `sha256` |
| `source_size_bytes` | Tamanho original; `size_bytes` |
| `source_member` | Membro de ZIP externo, quando aplicável; `member` |
| `source_sheet` | Planilha original; `sheet` |
| `source_header_row` | Linha do cabeçalho iniciando em 1; `header_row` |
| `source_row_number` | Posição física; amostra de linhas com chave duplicada no perfil; retenção por observação prevista na ingestão |
| `source_url`, `source_retrieved_at` | Desconhecidos; preencher com evidência, nunca inferir do nome |
| `source_revision` | A definir na ingestão; não inventar versão |
| `profile_generated_at`, `profile_script_sha256` | Horário UTC da análise e hash do script no relatório; distintos de coleta/download |

O JSON registra versões Python/openpyxl e compara SHA-256 antes/depois. Falha de leitura/esquema retorna código não zero com arquivo/planilha. Colunas extras nomeadas são perfiladas; valores sem cabeçalho causam erro. Nenhuma fonte é regravada.

## Evidência e pendência

Comandos, contagens e testes estão em [data-discovery.md](data-discovery.md). Há histórico real agregado e três semanas de microdados analisados. O **histórico individual CSV/ZIP ainda exige amostra real** antes de implementar esse ramo no Marco 2. Não reconstruir postos/observações individuais a partir de médias mensais.
