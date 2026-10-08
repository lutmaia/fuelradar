# Dados locais

Coloque os arquivos originais recebidos da ANP em `data/raw/`. Preserve nome e conteúdo, inclusive registros de outras UFs. Não recorte SP, corrija, regrave ou sobrescreva o original. Para nomes repetidos ou revisões, use subpastas distintas por recebimento; preserve também o arquivo compactado original, quando houver.

- `raw/`: arquivos exatamente como recebidos, para auditoria e reprocessamento.
- `processed/`: saídas derivadas (`manifest.json`, `observations/`, `runs/`) geradas por `scripts/ingest_local.py`; nunca substituir os originais.
- `quarantine/`: linhas rejeitadas pela ingestão (UF, preço de venda ou data não interpretáveis), com motivo; as regras formais de qualidade são do Marco 3. A origem nunca é apagada.

Os conteúdos dessas pastas são ignorados pelo Git, exceto os marcadores `.gitkeep`. Não coloque dados brutos fora de `data/raw/`, não os envie ao GitHub e não force sua inclusão com `git add -f`. O `.gitignore` não protege arquivos previamente rastreados ou adicionados à força.

Na descoberta, registrar origem/URL, data do recebimento, nome e checksum (uma impressão digital do conteúdo) para rastreabilidade. O manifesto local já registra nome, caminho e checksum; URL e data de recebimento só serão preenchidas pelo download (etapa 3). Nenhum download, parsing ou análise foi executado no Marco 0.

No Marco 1, nove XLSX locais foram analisados em modo de leitura. Resultados em [data-discovery.md](../docs/data-discovery.md) e contrato proposto em [data-contract.md](../docs/data-contract.md). Os relatórios derivados ficam em `reports/data-profile/`, fora desta pasta, e não contêm cópias completas das linhas brutas.

Em 2026-10-01, foi recebido e validado `historicos/Preços semestrais - AUTOMOTIVOS_2026.01.csv`, com observações individuais por revenda. Os XLSX mensais continuam sendo agregados: não substituem microdados nem serão inseridos na tabela de observações individuais. Os novos relatórios ficam em `reports/data-profile/historical-validation/`. Não substitua os arquivos já recebidos.
