# Modelagem v2 — resultado final

- **Dados:** hash `1a3225c5094b949b…`, 600 séries, semanas de 2022-11-13 a 2026-10-04.
- **Código:** `b79188e4b8bd5b8fc3e7f1a1a07fc51818adb366` · **protocolo:** `b79188e4b8bd5b8fc3e7f1a1a07fc51818adb366` · semente 20261013 · bootstrap B = 2000.
- Método e critérios: [protocolo da modelagem](../../docs/estudo/protocolo-modelagem.md).

Teste final: 26 origens, 21387 pontos; lido 1 vez(es) (registro em `holdout_access`).

## Decisão

Candidato escolhido na validação: **L2_lightgbm**. **Não aprovado**: nada muda no produto.

- ✅ b ganho confirmado no teste
- ✅ c sem piora em grupo
- ❌ d calibracao
- ✅ e reprodutivel

## Todos os modelos no teste (h = 2)

| Camada | Modelo | BSS | IC 95% |
|---|---|---|---|
| L1 | logística multinomial | +0,031 | [-0,044 ; +0,112] |
| L1 | LightGBM | +0,062 | [+0,020 ; +0,095] |
| L2 | logística multinomial | +0,124 | [+0,065 ; +0,185] |
| L2 | LightGBM | +0,164 | [+0,104 ; +0,208] |
| L3 | logística multinomial | +0,126 | [+0,067 ; +0,181] |
| L3 | LightGBM | +0,152 | [+0,100 ; +0,198] |

## Secundários (Holm)

| Medida | Estimativa | IC 95% | p (Holm) |
|---|---|---|---|
| L1_vs_L0 | +0,031 | [-0,044 ; +0,112] | 1,000 |
| L2_vs_L1 | +0,133 | [+0,063 ; +0,186] | < 0,001 |
| L3_vs_L2 | -0,012 | [-0,024 ; +0,009] | 1,000 |
| candidato_h1 | +0,105 | [+0,034 ; +0,170] | 0,021 |
| candidato_h4 | +0,116 | [+0,015 ; +0,185] | 0,096 |
| tau_0.03 | +0,171 | [+0,113 ; +0,212] | < 0,001 |
| tau_0.1 | +0,151 | [+0,081 ; +0,199] | < 0,001 |
| valor_L1_dm | -0,035 | — | 1,000 |
| valor_L2_dm | +0,063 | — | 1,000 |
| valor_L3_dm | -0,027 | — | 1,000 |

**Verificação da referência:** BSS do candidato +0,164 contra a taxa-base por produto e mês e +0,172 contra a taxa-base só por produto.

## Valor (secundário): LightGBM de cada camada contra o último valor

| Camada | MAE | MAE do último valor | Skill | Cobertura do intervalo de 80% |
|---|---|---|---|---|
| L1 | 0,1126 | 0,1088 | -0,035 | 76,8% |
| L2 | 0,1019 | 0,1088 | +0,063 | 76,0% |
| L3 | 0,1117 | 0,1088 | -0,027 | 72,6% |
