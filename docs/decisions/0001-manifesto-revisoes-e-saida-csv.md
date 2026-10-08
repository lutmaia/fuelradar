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

## Alternativas consideradas

- **Identidade só pelo nome ou pela data de modificação:** não detecta a mesma publicação em dois lugares nem uma correção silenciosa da fonte.
- **Parquet ou pandas agora:** exigiriam dependência nova sem necessidade do marco; a regra do projeto é adicionar só o necessário.
- **Deduplicar na ingestão:** esconderia revisões e repetições da própria fonte; a decisão sobre elas é de qualidade (Marco 3).
- **Instalação editável (`pip install -e .`):** exige escolher um backend de build, o que fica para o Marco 8 (contêineres).

## Consequências

- Se a ANP renomear um arquivo corrigido, ele aparece como novo período e não como revisão; o SHA-256 evita duplicar o mesmo conteúdo, mas não liga os dois nomes.
- Quando duas versões novas do mesmo período aparecem na mesma execução, a ordem de revisão segue a data de modificação do arquivo.
- `source_url` e `retrieved_at` ficam `null` até o download (etapa 3), porque o nome do arquivo não prova a origem.
- As saídas de revisões antigas acumulam em `data/processed/`; a limpeza é uma decisão futura, nunca automática.
