# 0006 — Arquivos da fonte com defeito conhecido: lista de exclusão por SHA-256

- **Status:** aceita (2026-10-12)
- **Contexto:** ao baixar o histórico semanal da ANP, a planilha `revendas_lpc_2025-06-29_2025-07-05.xlsx` veio com 2.101 linhas de resumo (média e desvio por produto, sem posto nem UF) sob o cabeçalho de postos. Todas as linhas foram rejeitadas por UF ausente, o arquivo ficou vazio e a regra crítica `arquivo_vazio` (mais `reducao_extrema`) bloqueou a publicação do conjunto inteiro. O bloqueio está correto: o defeito é da fonte. Mas, sem uma saída, um único arquivo ruim da ANP trava para sempre todo o histórico e toda semana nova.
- **Alternativas:** (a) apagar ou mover o arquivo de `data/raw`: viola a regra de preservar os brutos e não deixa registro do motivo; (b) afrouxar `arquivo_vazio`: enfraquece a proteção para todos os arquivos, inclusive os futuros; (c) lista de exclusão explícita, por arquivo.

## Decisão

1. `config/excluded_sources.json` (versionado) lista arquivos da fonte que a qualidade deve ignorar, cada um com `file`, `sha256`, `reason` e `registered_on`.
2. A chave é o **SHA-256 do conteúdo**, não o nome. Se a ANP republicar o arquivo corrigido, o hash muda, o arquivo novo entra como nova revisão e **deixa de ser excluído sozinho**.
3. `run_quality` ignora o arquivo por inteiro: não lê linhas, não aplica regras críticas e não o conta na reconciliação. Ele aparece em `report["excluded_sources"]` e gera um **aviso** ("arquivo da fonte excluído por defeito conhecido…"), então a decisão passa a `publicar_com_aviso`, nunca silenciosa.
4. O bruto continua intacto em `data/raw`, e o arquivo continua registrado no manifesto e na tabela `source_file`. O que muda é que ele não gera observações.
5. A semana excluída vira **lacuna** nas séries; nada é interpolado nem preenchido. O painel já mostra semanas sem dados como lacunas.
6. Entrar na lista é uma decisão humana e revisada (commit com o motivo). Nenhuma regra faz isso automaticamente.

## Consequências e limitações

- A lista é pequena e manual de propósito. Cada entrada precisa de uma justificativa verificável; `reason` vazio é rejeitado ao ler.
- Uma entrada cujo hash não corresponde a nenhum arquivo do manifesto é simplesmente inerte (não é erro).
- A exclusão vale para a etapa de qualidade, que alimenta a carga. A ingestão ainda lê e registra o arquivo (e rejeita as linhas), por isso a saída de `ingest_local.py` continua mostrando as 2.101 rejeições dele.
- O defeito foi encontrado a partir de uma carga em massa do histórico; outros defeitos de fonte devem aparecer do mesmo modo (bloqueio da qualidade) e passar por esta revisão.
