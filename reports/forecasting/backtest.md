# Relatório do backtest (Marco 7)

- **Origem das previsões:** semana de 04/10/2026
- **Dados:** hash `1a3225c5094b949b…`, 86293 linhas semanais, 600 séries
- **Código:** `c8b0b27013564548d64b01aaa78d2104316e782c`
- **Backtest:** 35 origens planejadas a cada 4 semanas, 30 com séries elegíveis; as 8 primeiras só calibram intervalos e 22 são avaliadas. 24481 previsões avaliadas, todas em pontos comuns aos quatro modelos

## Resultado geral

| Modelo | MAE (R$/L) | MAE pond. | WAPE | MASE | Viés | Cobertura 80% | Largura |
|---|---|---|---|---|---|---|---|
| Último valor | 0.1064 | 0.0812 | 1.81% | 1.55 | -0.0173 | 75.3% | 0.284 |
| Média móvel de 4 semanas | 0.1316 | 0.1098 | 2.23% | 1.98 | -0.0241 | 70.6% | 0.318 |
| Mesma semana do ano anterior | 0.4051 | 0.3800 | 6.88% | 6.39 | -0.3358 | 73.8% | 0.780 |
| LightGBM global (candidato) | 0.1120 | 0.0876 | 1.90% | 1.68 | -0.0112 | 76.6% | 0.309 |

MAE ponderado: pesa cada previsão pelo número de postos da semana prevista. Viés = previsão − observado (negativo: subestima).

## Decisão

**Candidato NÃO aprovado — o baseline permanece publicado.** Melhor baseline: Último valor. Variação do MAE ponderado do candidato contra ele: +7.9% (negativo = candidato melhor).

- [ ] melhora de pelo menos 5% no MAE ponderado contra o melhor baseline
- [ ] sem piora grave em produto, nível, horizonte ou porte de município
- [x] viés médio de até 25% do MAE
- [x] cobertura do intervalo de 80% entre 70% e 90%
- [x] mesmos dados e semente geram previsões idênticas

Grupos em que o candidato piorou mais de 5% contra o melhor baseline: by_product:GASOLINA_ADITIVADA, by_product:GASOLINA_COMUM, by_product:GNV, by_level:estado, by_level:municipio, by_horizon:1, by_horizon:2, by_horizon:3, by_group:estado, by_group:grande (30+), by_group:medio (10 a 29)

**Modelo publicado:** Último valor.

## Por horizonte (MAE ponderado)

| Horizonte | Último valor | Média móvel de 4 semanas | Mesma semana do ano anterior | LightGBM global (candidato) |
|---|---|---|---|---|
| 1 semana(s) | 0.0427 | 0.0729 | 0.3597 | 0.0496 |
| 2 semana(s) | 0.0697 | 0.1001 | 0.3845 | 0.0777 |
| 3 semana(s) | 0.1003 | 0.1307 | 0.3882 | 0.1065 |
| 4 semana(s) | 0.1153 | 0.1389 | 0.3898 | 0.1199 |

## Por produto (MAE ponderado)

| Produto | Último valor | Média móvel de 4 semanas | Mesma semana do ano anterior | LightGBM global (candidato) |
|---|---|---|---|---|
| DIESEL_COMUM | 0.1341 | 0.1775 | 0.4227 | 0.1353 |
| DIESEL_S10 | 0.1272 | 0.1756 | 0.4962 | 0.1328 |
| ETANOL_HIDRATADO | 0.0772 | 0.1037 | 0.3481 | 0.0794 |
| GASOLINA_ADITIVADA | 0.0595 | 0.0772 | 0.3429 | 0.0678 |
| GASOLINA_COMUM | 0.0551 | 0.0769 | 0.3531 | 0.0664 |
| GNV | 0.0871 | 0.1096 | 0.3297 | 0.0924 |

## Por nível geográfico e porte do município (MAE ponderado)

| Grupo | Último valor | Média móvel de 4 semanas | Mesma semana do ano anterior | LightGBM global (candidato) |
|---|---|---|---|---|
| estado | 0.0706 | 0.1033 | 0.3717 | 0.0775 |
| municipio | 0.0946 | 0.1180 | 0.3906 | 0.1003 |
| grande (30+) | 0.0813 | 0.1035 | 0.3752 | 0.0868 |
| medio (10 a 29) | 0.0901 | 0.1111 | 0.3739 | 0.0962 |
| pequeno (<10 postos) | 0.1095 | 0.1371 | 0.4243 | 0.1147 |

## Publicação

- Séries elegíveis na origem: 279 de 600
- Previsões gravadas: 1116 (279 séries × 4 horizontes)
- Variações incomuns nas últimas semanas: 44

Reprodutibilidade verificada: sim, duas execuções de treino idênticas.
