# Modelagem v2 — validação

- **Dados:** hash `9f461344c1ed6c41…`, 598 séries, semanas de 2022-11-13 a 2026-03-29.
- **Código:** `b79188e4b8bd5b8fc3e7f1a1a07fc51818adb366` · **protocolo:** `b79188e4b8bd5b8fc3e7f1a1a07fc51818adb366` · semente 20261013 · bootstrap B = 2000.
- Método e critérios: [protocolo da modelagem](../../docs/estudo/protocolo-modelagem.md).

Validação: 30 origens, 26016 pontos (todos os horizontes). O teste final **não** foi lido.

## Desfecho primário (h = 2): Brier skill contra a taxa-base

| Camada | Modelo | BSS | IC 95% | Pontos |
|---|---|---|---|---|
| L1 | logística multinomial | +0,080 | [+0,004 ; +0,156] | 8854 |
| L1 | LightGBM | +0,024 | [-0,057 ; +0,125] | 8854 |
| L2 | logística multinomial | +0,122 | [+0,056 ; +0,175] | 8854 |
| L2 | LightGBM | +0,145 | [+0,081 ; +0,195] | 8854 |
| L3 | logística multinomial | +0,116 | [+0,050 ; +0,173] | 8854 |
| L3 | LightGBM | +0,143 | [+0,066 ; +0,197] | 8854 |

**Candidato:** L2_lightgbm.

Classes em h = 2: queda 16.0%, estável 50.0%, alta 34.0%. Brier da taxa-base 0.6677; da persistência (sempre "estável") 0.9991.

