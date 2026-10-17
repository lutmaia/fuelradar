# Dados locais

Coloque os arquivos originais recebidos da ANP em `data/raw/`. Preserve nome e conteúdo, inclusive registros de outras UFs. Não recorte SP, corrija, regrave ou sobrescreva o original. Para nomes repetidos ou revisões, use subpastas distintas por recebimento; preserve também o arquivo compactado original, quando houver.

- `raw/`: arquivos exatamente como recebidos, para auditoria e reprocessamento. `raw/downloads/retrieved_at=<UTC>/` é criada por `scripts/fetch_anp.py`; uma pasta nova por recebimento, nunca sobrescrita. `raw/external/<fonte>/retrieved_at=<UTC>/` guarda as fontes externas (dólar, produtores e distribuição), baixadas por `scripts/fetch_external.py`.
- `processed/`: saídas derivadas (`manifest.json`, `observations/`, `runs/`) geradas por `scripts/ingest_local.py`, e `staging/observations.csv` e `quality/` (cobertura e relatórios) geradas por `scripts/check_quality.py`; nunca substituir os originais.
- `quarantine/`: `<id>_rejected.csv`, linhas rejeitadas pela ingestão (UF, preço de venda ou data não interpretáveis), e `quality_observations.csv`, linhas suspeitas pelas regras de qualidade; ambas com motivo. A origem nunca é apagada.

Os conteúdos dessas pastas são ignorados pelo Git, exceto os marcadores `.gitkeep`. Não coloque dados brutos fora de `data/raw/`, não os envie ao GitHub e não force sua inclusão com `git add -f`. O `.gitignore` não protege arquivos previamente rastreados ou adicionados à força.

O manifesto (`processed/manifest.json`) registra nome, caminho, checksum (SHA-256) e, para o que foi baixado pelo projeto, URL e data do download. A lista de cada arquivo de origem com o SHA-256 está em `reports/dataset/fontes.csv`; arquivos da ANP com defeito conhecido ficam em `config/excluded_sources.json`, com o motivo.

A descoberta inicial dos formatos está em [data-discovery.md](../docs/data-discovery.md) e o contrato em [data-contract.md](../docs/data-contract.md); a [ficha do conjunto de dados](../docs/ficha-dados.md) é o retrato atual.

Além das semanas baixadas, o projeto usa um histórico semestral por revenda (`historicos/Preços semestrais - AUTOMOTIVOS_2026.01.csv`), recebido à mão. Os XLSX mensais são agregados: não substituem microdados nem são inseridos na tabela de observações individuais.
