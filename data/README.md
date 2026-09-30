# Dados locais

Coloque os arquivos originais recebidos da ANP em `data/raw/`. Preserve nome e conteúdo, inclusive registros de outras UFs. Não recorte SP, corrija, regrave ou sobrescreva o original. Para nomes repetidos ou revisões, use subpastas distintas por recebimento; preserve também o arquivo compactado original, quando houver.

- `raw/`: arquivos exatamente como recebidos, para auditoria e reprocessamento.
- `processed/`: futuras saídas derivadas e tratadas; nunca substituir os originais.
- `quarantine/`: futuras cópias de registros suspeitos e motivos da sinalização, sem apagar a origem.

Os conteúdos dessas pastas são ignorados pelo Git, exceto os marcadores `.gitkeep`. Não coloque dados brutos fora de `data/raw/`, não os envie ao GitHub e não force sua inclusão com `git add -f`. O `.gitignore` não protege arquivos previamente rastreados ou adicionados à força.

Na descoberta, registrar origem/URL, data do recebimento, nome e checksum (uma impressão digital do conteúdo) para rastreabilidade. A automação desse registro pertence à ingestão futura. Nenhum download, parsing ou análise foi executado no Marco 0.

No Marco 1, nove XLSX locais foram analisados em modo de leitura. Resultados em [data-discovery.md](../docs/data-discovery.md) e contrato proposto em [data-contract.md](../docs/data-contract.md). Os relatórios derivados ficam em `reports/data-profile/`, fora desta pasta, e não contêm cópias completas das linhas brutas.

Os históricos disponíveis são agregados mensais. Para a futura carga histórica por posto, ainda será necessária uma amostra real CSV/ZIP com observações por revenda. Coloque-a aqui, preservada, e valide seu esquema antes de implementar a ingestão desse formato. Não substitua os arquivos já recebidos.
