# Contrato de dados proposto — versão 0.5

Validado exploratoriamente nos nove XLSX do Marco 1 e no CSV histórico por revenda recebido em 2026-10-01, descritos em [data-discovery.md](data-discovery.md). Este é um contrato dos formatos observados. A versão 0.3 acrescentou a [saída da ingestão local](#saída-da-ingestão-local-marco-2-etapa-2) a 0.4, as [regras de qualidade e a saída publicada](#qualidade-e-saída-publicada-marco-3) e a 0.5, o [modelo no PostgreSQL](#banco-de-dados-marco-4). O perfil do Marco 1 (perfil do Marco 1, retirado; ver data-discovery.md) preserva o diagnóstico inicial; a validação histórica atual (perfil do Marco 1, retirado; ver data-discovery.md) contém o CSV e a nova comparação com as três semanas. A [arquitetura](architecture.md) permanece a especificação principal.

## Granularidades e limites

- **R — revendas semanais** e **H — histórico individual CSV:** observação candidata por UF, município, CNPJ, produto, unidade e data de coleta. Ambas possuem preço individual e identidade do estabelecimento.
- **M — mensal municipal:** agregado por mês, UF, município, produto e unidade. `MÊS` não é data de coleta individual. Não fornece CNPJ, bandeira, mediana nem postos únicos no intervalo.
- **S — resumo semanal:** agregados municipais/capitais, estaduais, regionais e nacionais em planilhas separadas. Não concatenar níveis como observações independentes.
- **MR — mensal regional:** não possui UF; não pode alimentar resultados de SP, mesmo quando `REGIÃO=SUDESTE`.

GLP é descrito porque está nas fontes, mas está fora do MVP automotivo. Não eliminar GLP do raw. O perfil separa `automotive_*` (sem GLP) dos totais de diagnóstico. Não foi criada camada publicada.

O CSV `Preços semestrais - AUTOMOTIVOS_2026.01.csv`, em `data/raw/historicos/`, foi lido integralmente: UTF-8 com BOM, separador `;`, cabeçalho na linha 1, 16 colunas. ZIP externo não foi recebido; o mesmo esquema CSV dentro de ZIP foi testado com amostra sintética. Formatos de outros períodos continuam sujeitos a validação.

**Agregados municipais e regionais não serão inseridos na tabela de observações individuais.** Resumos semanais também permanecem separados dos microdados. O campo `kind` do perfil explicita essa distinção, sem implementar carga.

## Correspondência do histórico individual (H) com o semanal (R)

| Canônica | Nome original H | Nome original R | Regra e ausência |
|---|---|---|---|
| `region` | Regiao - Sigla | — | Original N/NE/CO/SE/S preservado; não usar para inferir SP |
| `uf` | Estado - Sigla | ESTADO | SP e SAO PAULO → SP; obrigatório |
| `municipality_name` | Municipio | MUNICÍPIO | Original preservado; trim/maiúsculas/sem acentos para comparação; obrigatório |
| `legal_name` | Revenda | RAZÃO | Nome descritivo; não é chave; ausência → aviso |
| `cnpj` | CNPJ da Revenda | CNPJ | Texto completo com máscara em H; inteiro nativo em R; obrigatório; regras conservadoras abaixo |
| `address` | Nome da Rua | ENDEREÇO | Texto, original preservado; ausência → aviso |
| `address_number` | Numero Rua | NÚMERO | Texto, inclusive S/N; nulo permitido |
| `address_complement` | Complemento | COMPLEMENTO | Texto opcional; vazio → nulo |
| `neighborhood` | Bairro | BAIRRO | Texto opcional; vazio → nulo |
| `postal_code` | Cep | CEP | Texto com máscara em H; inteiro em R; inválido/ambíguo → sinalização |
| `product` | Produto | PRODUTO | Enumeração explícita; original e normalizado separados |
| `collection_date` | Data da Coleta | DATA DA COLETA | DD/MM/AAAA em H; data Excel em R; obrigatório |
| `sale_price` | Valor de Venda | PREÇO DE REVENDA | Decimal positivo; vírgula em H, número Excel em R; obrigatório |
| `purchase_price` | Valor de Compra | — | Decimal positivo opcional; 100% vazio em H analisado; não imputar |
| `unit` | Unidade de Medida | UNIDADE DE MEDIDA | BRL/L ou BRL/M3 em H; R também traz GLP/BRL/13KG |
| `brand` | Bandeira | BANDEIRA | Texto original e normalizado, opcional; BRANCA é valor válido |

H não traz nome fantasia separado. Seus exemplos de representação observados incluem `SP`, `GASOLINA`, `02/01/2026`, `7,97` e `R$ / litro`. Tipos canônicos e demais validações das tabelas seguintes também se aplicam a H nos campos correspondentes.

## Identificação e observações

`—` significa ausente nesse formato. Exemplos ilustram normalização; identificadores exemplificados são sintéticos. No pipeline futuro, campo obrigatório ausente/inválido deverá sinalizar e impedir aceitação da linha, preservando origem e motivo. O perfil apenas mede problemas.

| Canônica | Coluna R | Coluna M / S | Tipo esperado | Obrigatoriedade e ausência | Normalização e validação | Exemplo válido |
|---|---|---|---|---|---|---|
| `uf` | ESTADO | ESTADO; ESTADOS na aba estadual S | texto de 2 letras | Obrigatória para SP; sem UF não atribuir SP | Trim, espaços, maiúsculas sem acentos para busca; nome completo → sigla; desconhecido → sinalizar | SAO PAULO → SP |
| `municipality_name` | MUNICÍPIO | MUNICÍPIO, se municipal | texto | Obrigatória em R/M/S municipal; nula nos outros níveis | Guardar original; comparação com trim, espaços simples, maiúsculas sem acentos; não inferir IBGE | Jundiaí → JUNDIAI |
| `region` | — | REGIÃO ou REGIAO; também MR | texto | Opcional; nulo se ausente | Normalizar texto; SUDESTE nunca significa SP | SUDESTE |
| `cnpj` | CNPJ | — | texto de 14 dígitos | Obrigatória em R/H; nula nos agregados | Aceitar máscara completa ou 14 dígitos; recuperar zeros apenas de inteiro nativo representável; texto curto/científico é ambíguo | 123456780001 (inteiro) → 00123456780001 |
| `legal_name` | RAZÃO | — | texto | Descritiva; ausência → nulo com aviso | Texto e trim, preservar grafia | POSTO EXEMPLO LTDA |
| `trade_name` | FANTASIA | — | texto opcional | Nulo permitido; não identifica o posto | Texto/trim; aceitar números como texto | POSTO EXEMPLO |
| `address` | ENDEREÇO | — | texto opcional | Ausência → nulo com aviso | Texto/trim; sem geocodificação | RUA EXEMPLO |
| `address_number` | NÚMERO | — | texto opcional | Nulo permitido | Preservar números e S/N; não exigir inteiro | S/N |
| `address_complement` | COMPLEMENTO | — | texto opcional | Nulo permitido | Texto/trim; ausência não invalida preço | LOJA 2 |
| `neighborhood` | BAIRRO | — | texto opcional | Nulo permitido | Texto/trim, preservar grafia | CENTRO |
| `postal_code` | CEP | — | texto de 8 dígitos, opcional | Nulo permitido; inválido/ambíguo → aviso | Aceitar máscara completa ou 8 dígitos; recuperar zeros apenas de inteiro nativo; texto curto/científico é ambíguo | 1234567 (inteiro) → 01234567 |
| `brand` | BANDEIRA | — | texto opcional | Nulo permitido com aviso | Original e versão normalizada; BRANCA não é ausência; sem enumeração fechada | BRANCA |
| `product` | PRODUTO | PRODUTO, também MR | enumeração textual | Obrigatório; desconhecido → sinalizar | Mapeamento explícito abaixo; preservar original | GASOLINA_COMUM |
| `unit` | UNIDADE DE MEDIDA | Mesmo nome, também MR | enumeração textual | Obrigatória | Remover espaços e normalizar m³/m3; validar produto; não misturar litro/m³/13 kg | BRL/L |
| `collection_date` | DATA DA COLETA | — | data | Obrigatória em R; indisponível nos agregados | Data Excel ou DD/MM/AAAA/ISO; rejeitar impossível; número sem estilo Excel não é data implícita | 2026-09-24 |
| `sale_price` | PREÇO DE REVENDA | — | decimal positivo | Obrigatório em R | Vírgula → Decimal; aceitar número nativo; rejeitar não finito, texto inválido e ≤ 0; não arredondar antes de avaliar precisão | 5,99 → 5.99 |

CNPJ/CEP em H são textos completos com máscara e zeros já preservados; não precisam de preenchimento. Nos XLSX R são inteiros nativos. Só se completa a largura fixa de inteiro positivo menor que 10^14 (CNPJ) ou 10^8 (CEP): a magnitude cabe exatamente na precisão numérica e a operação é reversível em relação ao valor recebido. Isso não garante que não houve corrupção anterior ao recebimento.

Texto curto, notação científica textual, texto decimal e float são **ambíguos**: o normalizador retorna nulo com status, sem adivinhar zeros ou dígitos. Sinal, pontuação malformada e tamanho excessivo são inválidos. A fonte original permanece acessível sem alteração. O perfil registra contagens de status, inclusive SP, e até dez posições de registros ambíguos. CNPJ ambíguo não entra na contagem de postos únicos nem na comparação de chaves completas; a linha permanece na contagem total.

Essa validação de representação não verifica existência cadastral nem do CEP. O dígito verificador do CNPJ é conferido na qualidade (Marco 3).

`dimensions` mantém domínios originais. `normalization_pairs` registra separadamente `original`, `normalized` e contagem para UF, município, produto, unidade e bandeira; não substitui o original nem exporta uma cópia das linhas. `canonical_mapping` liga cada campo ao nome exato da coluna recebida.

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
| GASOLINA (H) | GASOLINA_COMUM, alias explícito proposto | BRL/L |
| GASOLINA ADITIVADA | GASOLINA_ADITIVADA | BRL/L |
| ETANOL (R); ETANOL HIDRATADO (agregados) | ETANOL_HIDRATADO | BRL/L |
| DIESEL S500 (R); OLEO DIESEL (agregados); DIESEL (H) | DIESEL_COMUM | BRL/L |
| DIESEL S10 (R); OLEO DIESEL S10 (agregados) | DIESEL_S10 | BRL/L |
| GNV | GNV | BRL/M3 |
| GLP | GLP, fora do MVP | BRL/13KG |

O preâmbulo dos agregados informa que OLEO DIESEL se refere a diesel B S500 comum. ETANOL segue a correspondência proposta entre as famílias. `GASOLINA` foi observado em H, junto de GASOLINA ADITIVADA: o alias explícito GASOLINA_COMUM passa a ser exercitado em fonte real, com original preservado. Essa correspondência é uma decisão proposta do contrato, não uma confirmação independente de metadados oficiais.

`DIESEL` (H), `DIESEL S500` (R) e `OLEO DIESEL` (agregados) são o mesmo diesel comum, por decisão do usuário em 2026-10-10, apoiada pela sobreposição: preço idêntico em 305 de 305 pares de posto e dia entre `DIESEL` e `DIESEL S500`, contra 9 de 249 para S10. `DIESEL_S10` permanece separado. O rótulo original continua em `product_original`. Há seis produtos no histórico e sete nas semanas (incluindo GLP), com sete nomes canônicos na união.

`R$/l`/`R$ / litro` → BRL/L; `R$/m3`/`R$/m³`/`R$ / m³` → BRL/M3; `R$/13kg`/`R$ / 13 kg` → BRL/13KG. Desconhecidos são sinalizados, sem associação por similaridade.

## Ausências, preços e cobertura

- O perfil reconhece célula vazia, texto vazio, `-`, `NA`, `N/A` e `NULL` como ausentes. Nas fontes foram observados vazios e `-`; os demais têm suporte preventivo. Ausência nunca vira zero.
- A triagem de extremos usa `[Q1 − 3×IQR, Q3 + 3×IQR]`, quartis inclusivos, por planilha/coluna/produto/unidade, separando SP do conjunto completo. IQR é a distância entre primeiro e terceiro quartil.
- É uma heurística **exploratória**, não um limite homologado: não exclui registros nem indica irregularidade. Nos históricos mistura meses e pode refletir variação temporal legítima. Limites por período/produto ficam para qualidade.
- Datas de download não foram fornecidas; modificação do arquivo não é data de coleta/download.
- `normalize_uf(valor) == "SP"` identifica SP. O normalizador conhece nomes/siglas das UFs para preservar a dimensão; produto permanece limitado a SP. SUDESTE não identifica SP.
- Município normalizado identifica localidade somente junto da UF. Resolução por IBGE e variações mais complexas não foi implementada.

## Chaves candidatas

- R/H: `(uf, municipality_name_normalized, cnpj, product, unit, collection_date)`.
- M: `(uf, municipality_name_normalized, product, unit, reference_month)`.
- S: `(aggregation_level, uf/localidade, município quando aplicável, product, unit, period_start, period_end)`.
- MR: `(region, product, unit, reference_month)`, diagnóstico fora da publicação SP.

São candidatas, não autorização para deduplicar automaticamente. O perfil conta repetições por planilha e na união das revendas SP. MR tem dois conflitos com valores diferentes. Revisões futuras devem distinguir origem/versão: chave igual em revisão posterior não pode ser descartada cegamente. Unidade e granularidade impedem misturar observações incompatíveis.

Em H há seis repetições exatas/chaves repetidas no arquivo completo, nenhuma em SP. Em SP, H e cada semana R têm zero chaves e zero datas de coleta compartilhadas. `overlaps_sp` compara pares de fontes, incluindo igualdade/conflito dos conjuntos de preços por chave. Essa comparação cobre apenas chaves completas e a normalização explícita atual, sem eliminar linhas. Outros períodos e revisões precisam passar novamente pela verificação.

## Auditoria

| Campo | Regra |
|---|---|
| `source_file_name` | Nome recebido; `file` no JSON |
| `source_file_sha256` | SHA-256 dos bytes originais; `sha256` |
| `source_size_bytes` | Tamanho original; `size_bytes` |
| `source_member` | Membro de ZIP externo, quando aplicável; `member` |
| `source_sheet` | Planilha original; `sheet` |
| `source_header_row` | Linha do cabeçalho iniciando em 1; `header_row` |
| `source_row_number` | Linha física no XLSX e registro lógico (cabeçalho = 1) no CSV; amostra no perfil e, por observação, na saída da ingestão |
| `source_url`, `source_retrieved_at` | Desconhecidos; preencher com evidência, nunca inferir do nome |
| `source_revision` | `revision` do manifesto: 1 para o primeiro arquivo de um período e +1 para cada SHA-256 novo com o mesmo nome; não vem da ANP |
| `profile_generated_at`, `profile_script_sha256` | Horário UTC da análise e hash do script no relatório; distintos de coleta/download |

O JSON registra versões Python/openpyxl e compara SHA-256 antes/depois. Falha de leitura/esquema retorna código não zero com arquivo/planilha. Colunas extras nomeadas são perfiladas; valores sem cabeçalho causam erro. Nenhuma fonte é regravada.

## Saída da ingestão local (Marco 2, etapa 2)

`scripts/ingest_local.py` lê `data/raw/` (somente leitura), mantém um manifesto e grava as observações individuais das UFs de `TARGET_UFS` (padrão `["SP"]`). Detalhes da decisão em [ADR 0001](decisions/0001-manifesto-revisoes-e-saida-csv.md).

**Manifesto** (`data/processed/manifest.json`, uma entrada por SHA-256): `source_file_id` (16 primeiros hex do SHA-256), `sha256`, `size_bytes`, `paths` (caminhos relativos a `raw/`; o mesmo conteúdo em dois lugares é uma entrada), `kinds`, `period_key` (nome do arquivo sem extensão), `reference_start`/`reference_end` (do nome, quando traz o período; senão, min/max das datas de coleta ingeridas), `revision`, `is_current`, `first_seen_at`, `source_url`/`retrieved_at` (`null` até haver download com evidência) e `ingestion` (contagens, `target_ufs` e saída). Mesmo `period_key` com SHA-256 novo gera `revision` + 1 e a anterior deixa de ser `is_current`; a saída antiga é preservada. Agregados (M, S, MR) são registrados, mas nunca ingeridos.

**Observações** (`data/processed/observations/<source_file_id>.csv`, UTF-8, `
`): `uf`, `region`, `municipality_original`, `municipality_normalized`, `legal_name`, `trade_name`, `brand`, `cnpj`, `cnpj_status`, `address`, `address_number`, `address_complement`, `neighborhood`, `cep`, `cep_status`, `product_original`, `product`, `product_category` (`automotivo`, `glp` ou `desconhecido`), `unit_original`, `unit`, `collection_date` (ISO), `sale_price` e `purchase_price` (decimal como texto), `row_key` (chave candidata acima, vazia se incompleta) e a auditoria (`source_file_id`, `source_sha256`, `source_member`, `source_sheet`, `source_row_number`, `source_row_hash`, `ingestion_run_id`). A saída preserva a ordem do arquivo de origem, mantém GLP e **não** remove duplicatas nem extremos.

**Rejeição técnica** (`data/quarantine/<source_file_id>_rejected.csv`): só linhas de UF, preço de venda ou data de coleta ausentes ou não interpretáveis, com o motivo e os valores originais. Preço zero ou negativo, produto ou unidade desconhecidos e CNPJ/CEP inválidos ou ambíguos **permanecem** na observação (campo normalizado vazio e status), para as regras do Marco 3. Vale `rows_read = rows_accepted + rows_out_of_scope + rows_rejected`.

**Origem e download** (`scripts/fetch_anp.py`, [ADR 0001](decisions/0001-manifesto-revisoes-e-saida-csv.md)): `data/processed/downloads.jsonl` registra cada tentativa (`url`, `retrieved_at`, `action` = `saved`, `duplicate` ou `error`, `sha256`, `size_bytes`, `http_status`, `raw_path`, `page_updated_on`, `error`). Arquivos novos ficam em `data/raw/downloads/retrieved_at=<UTC>/`. No manifesto, `source_url` vem de um download salvo ou idêntico; `retrieved_at` só de um arquivo que nós baixamos. Arquivos recebidos à mão e idênticos à fonte têm URL, mas `retrieved_at` nulo.

**Sobreposição entre fontes:** a ingestão não deduplica entre arquivos. Com o histórico semestral e as semanas de 28/06 a 03/10 baixadas, 3.107 chaves (29 e 30/06/2026) aparecem no CSV e na semana de 28/06 a 04/07; todas têm o mesmo preço quando comparado como número (as 13 "diferenças" registradas antes eram `7.30` contra `7.3`, comparação de texto). A precedência é definida na qualidade, abaixo.

Linhas de outras UFs são contadas (`rows_out_of_scope`), mas não gravadas; o raw nacional não é alterado. Arquivo ilegível ou com valor fora das colunas nomeadas não publica nada daquela versão e é listado em `errors` do relatório (`data/processed/runs/<run_id>.json`).

## Evidência e pendência

Comandos, contagens e testes estão em [data-discovery.md](data-discovery.md). Já há fonte histórica individual CSV e três semanas por revenda suficientes para iniciar a implementação local da ingestão desses formatos. ZIP mantém teste sintético; nenhum ZIP real foi recebido. Há lacuna de julho/agosto e começo de setembro entre os microdados disponíveis, e a equivalência DIESEL/S500 continua pendente. Agregados não suprem essas lacunas. A ingestão local e o download das semanas por revenda foram executados sobre os arquivos reais (evidências em [PLAN.md](../PLAN.md)). Com as semanas de 28/06 a 03/10, a lacuna de julho a início de setembro deixou de existir: de 01/01 a 02/10/2026, 76 dos 79 dias sem observações em SP são fins de semana e três são sextas-feiras (26/06, 24/07 e 04/09), a avaliar no Marco 3. Considerando só combustíveis automotivos, são quatro sextas-feiras sem coleta (26/06, 24/07, 04/09 e 18/09; em 18/09 há só duas linhas de GLP). As regras de qualidade estão na seção seguinte.

## Qualidade e saída publicada (Marco 3)

`scripts/check_quality.py` lê o manifesto e as observações das revisões atuais (nunca `data/raw`). Decisões e limites em [ADR 0002](decisions/0002-qualidade-quarentena-e-precedencia.md).

- **Publicadas** (`data/processed/staging/observations.csv`): colunas da observação mais `brand_normalized`, `week_start` (domingo da semana da ANP), `quality_flags` (avisos separados por `;`: `preco_extremo`, `cep_ausente`, `cep_ambiguo_ou_invalido`, `bandeira_ausente`, `razao_social_ausente`, `endereco_ausente`) e `duplicate_sources` (`<source_file_id>:<linha>` das cópias idênticas removidas). `sale_price` e `purchase_price` usam forma canônica sem arredondamento (`7.30`, `5.999`). Uma linha por chave; sem GLP.
- **Quarentena** (`data/quarantine/quality_observations.csv`): mesmas colunas da observação, `week_start` e `quality_reasons`: `preco_ausente_ou_ilegivel`, `preco_nao_positivo`, `data_invalida`, `data_futura`, `data_fora_do_periodo_do_arquivo`, `uf_ausente`, `municipio_ausente`, `cnpj_ausente`, `cnpj_malformado`, `cnpj_digito_verificador_invalido`, `produto_desconhecido`, `unidade_desconhecida`, `unidade_incompativel` (produto e unidade fora da tabela acima), `conflito_de_preco_mesma_chave` e `preco_implausivel`.
- **Cobertura** (`data/processed/quality/coverage_weekly.csv` e `coverage_series.csv`): postos e observações por município, produto e semana, mediana de postos das oito semanas anteriores, razão e `low_coverage`; proporção de semanas presentes por série.
- **Relatório** (`data/processed/quality/runs/<run_id>.json` e `latest.json`): falhas críticas por arquivo, contagens por regra, reconciliação (`rows_ingested = rows_published + rows_quarantined + rows_duplicate_removed + rows_out_of_scope_product`), cobertura, comparação com a execução anterior, amostras sem CNPJ, razão social ou endereço, avisos e decisão (`publicar`, `publicar_com_aviso`, `bloquear`). Com `bloquear`, nenhuma saída é substituída.

Uma mudança de regra de normalização aumenta `NORMALIZATION_VERSION` (em `ingestion/observations.py`); a ingestão refaz uma vez as observações registradas com versão anterior, lendo o raw sem alterá-lo, e grava `normalization_version` no manifesto. A versão 2 trouxe `DIESEL_COMUM`.

## Banco de dados (Marco 4)

`scripts/load_db.py` aplica `migrations/*.sql` e carrega a saída publicada no esquema `radar`. Decisões em [ADR 0003](decisions/0003-banco-postgresql.md) e operação em [local-database.md](local-database.md).

| Tabela | Conteúdo e chave |
|---|---|
| `ingestion_run` | uma linha por carga: status (`success`, `warning`, `failed`), commit, contagens, execução e decisão da qualidade, resumo do erro sem valores de linha |
| `source_file` | todo arquivo do manifesto (inclusive agregados, que nunca viram observações): SHA-256 único, `period_key` + `revision`, `is_current`, URL, `retrieved_at`, `storage_uri` |
| `dim_location` | `(uf, municipality_name_normalized)` único; `region` quando a fonte traz; `ibge_code` nulo |
| `dim_product` | 7 produtos canônicos com unidade; GLP presente e `active = false` |
| `dim_station` | CNPJ único; atributos do registro mais recente; `first_seen_date`/`last_seen_date` |
| `fact_price_observation` | uma linha por observação publicada; `sale_price` numérico exato; `row_key` único entre as vigentes; `quality_status`, `quality_flags`, `duplicate_sources`; `is_current_source_revision` |
| `quarantine_observation` | linhas em quarentena com `reasons` e `original` (jsonb) |
| `mart_weekly_city_price` | por semana, município e produto: observações, postos, mínimo, p25, mediana, média, p75, máximo, desvio, mediana-base de postos, `coverage_ratio` e `quality_flag` (`ok`, `cobertura_baixa`, `sem_historico`) |
| `mart_weekly_state_price` | as mesmas estatísticas de preço por semana, UF e produto |

Regras: a carga só aceita saída com decisão `publicar` ou `publicar_com_aviso` e contagens iguais às do relatório; linhas que deixam de pertencer ao conjunto publicado (revisão nova da fonte, precedência, regra de qualidade) ficam com `is_current_source_revision = false` e nunca são apagadas; consultas de produto devem filtrar `is_current_source_revision` (as agregações já filtram). As estatísticas de preço são arredondadas a 4 casas.

**Leitura pela API (Marco 5).** A migração `0003_api_reader.sql` cria o papel `radar_reader` (sem login), com `SELECT` só nas tabelas e colunas que a API usa: ficam de fora `source_file.storage_uri`, `ingestion_run.error_summary`, `ingestion_run.code_sha`, `quarantine_observation.original` e `schema_migration`. Também cria os índices `ix_mart_city_series` e `ix_fact_current_collection_date`. A API conecta como `radar_api` (membro de `radar_reader`) e não escreve. Contrato das respostas em [api.md](api.md) e no OpenAPI.
