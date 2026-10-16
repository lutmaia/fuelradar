# Orientações de trabalho

Regras para quem desenvolve neste repositório, inclusive assistentes de IA.

- Antes de começar, leia `PLAN.md` (marcos, evidências e o que está em andamento em "Limite da tarefa atual") e, para operar o que já está no ar, `docs/operacao.md`. Para mudanças grandes, leia antes o escopo (`PROJECT.md`), a especificação (`docs/architecture.md`, `docs/estudo-de-caso.md`) e os ADRs em `docs/decisions/`.
- Trabalhe um marco por vez, só o que foi pedido; não avance sozinho para o próximo.
- Os arquivos brutos das fontes são intocáveis: não edite, sobrescreva nem apague, e não os envie ao repositório.
- Pré-registro vale: protocolos são versionados antes de qualquer resultado, e o teste final só é lido uma vez. Desvios são registrados no próprio protocolo.
- Resultados são relatados como saíram, inclusive os negativos; diferencie o que foi executado e conferido do que é só estrutura ou hipótese.
- Privacidade: nada público traz CNPJ nem razão social (que pode ser o nome de uma pessoa); nenhuma tela associa postos a irregularidade.
- Dependência nova só quando necessária, com o motivo explicado.
- O produto não inclui agentes de IA, chat ou RAG.
- Mantenha a implementação pequena e compreensível; explique mudanças e limitações em linguagem clara.
