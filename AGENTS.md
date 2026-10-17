# Orientações de trabalho

Regras para quem desenvolve neste repositório, inclusive assistentes de IA.

- Antes de mudar algo, leia o [README](README.md) e o [relatório técnico](docs/relatorio-tecnico.md); para operar o que já está no ar, o [manual de operação](docs/operacao.md). Para mudanças grandes, leia antes a especificação (`docs/architecture.md`, `docs/estudo-de-caso.md`) e os ADRs em `docs/decisions/`.
- Faça só o que foi pedido, uma mudança por vez, com teste.
- Os arquivos brutos das fontes são intocáveis: não edite, sobrescreva nem apague, e não os envie ao repositório.
- Pré-registro vale: protocolos são versionados antes de qualquer resultado, e o teste final só é lido uma vez. Desvios são registrados no próprio protocolo. O teste final da modelagem v2 já foi lido; uma nova modelagem que o use precisa de novo protocolo e de declarar isso.
- Migrações já aplicadas, relatórios gerados em `reports/` e o registro das previsões ao vivo (`reports/ledger/`) não se editam à mão.
- Resultados são relatados como saíram, inclusive os negativos; diferencie o que foi executado e conferido do que é só estrutura ou hipótese.
- Privacidade: nada público traz CNPJ nem razão social (que pode ser o nome de uma pessoa); nenhuma tela associa postos a irregularidade.
- Dependência nova só quando necessária, com o motivo explicado.
- O produto não inclui agentes de IA, chat ou RAG.
- Mantenha a implementação pequena e compreensível; explique mudanças e limitações em linguagem clara.
