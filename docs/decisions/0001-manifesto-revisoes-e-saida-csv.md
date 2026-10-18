# ADR 0001 — Manifesto por SHA-256, revisões por período e saída em CSV

**Status:** aceito em 2026-10-08 (Marco 2, etapa 2). Complementa as ADR-001 a ADR-007 da [arquitetura](../architecture.md), sem alterá-las.

## Contexto

O Marco 2 precisa de ingestão rastreável e idempotente a partir de `data/raw/`, antes de existir banco (Marco 4) e sem dependências novas. A arquitetura exige que reexecutar a carga não duplique observações (seção 6.1), que revisões de um período sejam detectadas (RF-03) e que o raw nacional nunca seja alterado (RF-04).

## Decisão

1. **Identidade do arquivo = SHA-256.** O mesmo conteúdo em dois caminhos (por exemplo `mensal-municipios-jan2022-2025.xlsx` em `raw/` e `raw/historicos/`) é uma única entrada do manifesto com duas `paths`.
2. **Período = nome do arquivo sem extensão (`period_key`).** Mesmo nome com SHA-256 diferente é uma revisão: `revision` + 1, a anterior deixa de ser `is_current`. O nome identifica o período publicado, não as datas de coleta internas.
3. **Uma saída por versão.** `data/processed/observations/<source_file_id>.csv` é escrito em arquivo temporário e substituído de forma atômica. A saída de uma revisão antiga é preservada; quem consome usa o manifesto para saber qual é a vigente. Reexecutar sem arquivo novo não grava nada.
4. **Recorte por `TARGET_UFS`** (lista JSON, padrão `["SP"]`), lido em um único ponto (`config.py`). Mudar a lista reprocessa a versão vigente. O raw nacional não é alterado, e linhas de outras UFs apenas são contadas.
5. **Saída em CSV UTF-8**, com decimais e identificadores como texto, usando só a biblioteca padrão. O Marco 4 carrega esses arquivos no PostgreSQL.
6. **Rejeição técnica mínima.** Só UF, preço de venda e data de coleta não interpretáveis vão para `data/quarantine/`, com motivo e valores originais. Tudo o mais segue na observação para o Marco 3 julgar. Nenhuma linha é deduplicada ou descartada por valor extremo.
7. **Falha de um arquivo não publica nada dele** e não impede os demais. O erro fica no relatório da execução e o código de saída do script é não zero.
8. **Importação de `src/` por `sys.path`**, numa linha em cada script e teste, sem build-system nem instalação editável.
9. **Delimitador do CSV = o mais frequente na linha de cabeçalho.** O `csv.Sniffer` falhava em amostras pequenas e irregulares.

### Adendo — descoberta e download (etapa 3, 2026-10-08)

10. **A página da ANP é o manifesto de fontes.** `scripts/fetch_anp.py` lê os links `revendas_lpc_*.xlsx` da página "últimas semanas pesquisadas" (hrefs absolutos, nomes regulares, data "Atualizado em" por arquivo). Não há `sources/anp_sources.json`; a alternativa manual é `--url`, restrita a https de `.gov.br`. Se a página mudar e nenhum link for encontrado, o script falha com mensagem clara em vez de adivinhar.
11. **GET, nunca HEAD.** O servidor da ANP responde 403 a HEAD e 200/206 a GET, então não dá para checar tamanho ou data sem baixar. A revisão é sinalizada pela data "Atualizado em" da página: URL já obtida só é baixada de novo se essa data mudou (ou com `--force`). A identidade continua sendo o SHA-256 do conteúdo.
12. **Download em pasta temporária fora de `raw/`.** Conteúdo com SHA-256 já conhecido é descartado (a cópia temporária é nossa, não um raw). Conteúdo novo vai para `data/raw/downloads/retrieved_at=<UTC>/<nome>`, aberto com modo exclusivo (nunca sobrescreve) e conferido por SHA-256 após a cópia.
13. **Validação mínima antes de publicar:** tamanho > 0, `Content-Length` igual ao recebido, limite de 300 MB, XLSX/ZIP começando por `PK` e CSV que não seja HTML (páginas de erro com status 200). Erro de rede, HTTP 429/5xx e timeout têm 3 tentativas com espera de 2 s e 4 s; HTTP 4xx não é repetido. Falha nunca publica nada e o estado anterior permanece.
14. **Registro de downloads** em `data/processed/downloads.jsonl` (um evento por tentativa; só acrescenta). O manifesto preenche `source_url` quando um download salvo ou idêntico prova a URL, e `retrieved_at` somente quando o arquivo guardado foi de fato baixado por nós. Arquivos recebidos à mão, mas idênticos à fonte, ficam com URL e `retrieved_at` nulo.
15. **Sobreposição entre fontes não é resolvida na ingestão.** O CSV semestral e a semana de 28/06 a 04/07 compartilham 3.107 chaves (29 e 30/06). Cada saída preserva sua origem; a política de precedência fica para os Marcos 3 e 4. *Correção (Marco 3):* as "13 com preço diferente" eram uma comparação de texto (`7.30` contra `7.3`); numericamente, todas coincidem. Ver [ADR 0002](0002-qualidade-quarentena-e-precedencia.md).

## Alternativas consideradas

- **Identidade só pelo nome ou pela data de modificação:** não detecta a mesma publicação em dois lugares nem uma correção silenciosa da fonte.
- **Parquet ou pandas agora:** exigiriam dependência nova sem necessidade do marco; a regra do projeto é adicionar só o necessário.
- **Deduplicar na ingestão:** esconderia revisões e repetições da própria fonte; a decisão sobre elas é de qualidade (Marco 3).
- **Instalação editável (`pip install -e .`):** exige escolher um backend de build, o que fica para o Marco 8 (contêineres).

## Consequências

- Se a ANP renomear um arquivo corrigido, ele aparece como novo período e não como revisão; o SHA-256 evita duplicar o mesmo conteúdo, mas não liga os dois nomes.
- Quando duas versões novas do mesmo período aparecem na mesma execução, a ordem de revisão segue a data de modificação do arquivo.
- `source_url` e `retrieved_at` só são preenchidos com evidência do registro de downloads, porque o nome do arquivo não prova a origem. O CSV semestral recebido à mão continua sem URL.
- A data "Atualizado em" é publicada pela ANP na página, não no arquivo; uma correção sem mudança dessa data não seria vista sem `--force`.
- O ZIP semestral oficial (`ca-2026-01.zip`) não foi baixado: seu conteúdo coincidiria com o CSV que já temos e criaria duplicidade entre fontes.
- As saídas de revisões antigas acumulam em `data/processed/`; a limpeza é uma decisão futura, nunca automática.
