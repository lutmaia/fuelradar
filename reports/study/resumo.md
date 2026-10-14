# Estudo exploratório — resumo (Q1 a Q3)

- **Janela:** semanas de 2022-11-13 a 2026-03-29 (147 com dado); o teste final (2026-04-05 em diante) não foi lido.
- **Dados:** 675.834 observações de SP; hash `1c7b8e52107be9a9…` (observações `0b95e2366b32…`, municípios `89e75d74ae93…`, estado `df2f21c97ce8…`).
- **Código:** `d0babef13bcc279ae052668213967979550c6e23` · **protocolo:** `d0babef13bcc279ae052668213967979550c6e23` · semente 20261013 · bootstrap B = 2000.
- Método e critérios: [protocolo](../../docs/estudo/protocolo.md), inclusive a tabela de desvios. Resultados são associações, não efeitos causais.

| Pergunta | Desfecho primário (gasolina comum) | Resultado | Achado estável |
|---|---|---|---|
| [Q1 — bandeira branca](q1.md) | diferença da branca contra bandeirados, mesmo município e semana | -5,59% [-5,96% ; -5,21%] | **sim** |
| [Q2 — dinâmica](q2.md) | mediana das altas − mediana das quedas | R$ 0,020 [0,000 ; 0,100] | **não** |
| [Q3 — difusão](q3.md) | seguidores com precedência dos líderes (controle reverso) | 38,6% (4,8%) | **não** |

## Gate G1: não passou

Achados estáveis: Q1 (1 de 3; o protocolo exige 2).
Pelo protocolo, o resultado é publicado como está e o escopo da modelagem (Marco 10) é reavaliado com o usuário antes de seguir; nada foi refeito para passar.

Figuras: [Q1](q1.html), [Q2](q2.html), [Q3](q3.html). Todos os números: [resultados.json](resultados.json).
