# 0008 — Protocolo do estudo: pré-registro e lacre do teste final

- **Status:** aceita (Marco 8, 2026-10-13)
- **Contexto:** o [desenho do estudo de caso](../estudo-de-caso.md), aprovado em 2026-10-13, pede que hipóteses, métricas, janelas e regra de decisão sejam fixadas antes da primeira execução, e que o teste final só seja lido uma vez. Sem isso, as escolhas do estudo poderiam ser ajustadas depois de ver os números.

## Decisão

1. **Pré-registro em [docs/estudo/protocolo.md](../estudo/protocolo.md)**, commitado antes de qualquer análise de Q1 a Q3. Mudanças posteriores vão para a tabela de desvios do próprio protocolo, dizendo se foram feitas antes ou depois de ver resultados.
2. **Janelas em código:** `forecasting/protocol.py` guarda as datas da seção 6.2 do desenho (desenvolvimento até 2025-06-29, validação até 2026-03-29, teste final a partir de 2026-04-05), os subperíodos, a semente e os parâmetros do *bootstrap*. Um teste confere que o protocolo escrito e o código têm as mesmas datas.
3. **O estudo exploratório não lê o teste final.** Q1 a Q3 usam só desenvolvimento + validação, porque seus achados orientam a modelagem; `assert_no_holdout` recusa semanas do teste. Replicação no período inteiro só depois do Marco 10, e declarada como tal.
4. **Um desfecho primário por pergunta**, em gasolina comum; secundários com correção de Holm; critério de "achado estável" definido antes (IC sem zero e mesmo sinal nos subperíodos e na robustez); G1 passa com dois de três.
5. **O registro de acesso ao teste final** (`holdout_access`, migração `0005`) fica para o Marco 10, que é quando o teste é lido; no Marco 8, o lacre é a recusa no carregador.

## Alternativas consideradas

- **Estudo exploratório no período inteiro:** mais dados para Q1 a Q3, mas os achados (por exemplo, quem lidera em Q3) entrariam nas camadas da modelagem e contaminariam o teste final.
- **Protocolo só no texto, sem constantes em código:** fácil de divergir sem que ninguém perceba; o teste de igualdade custa pouco.
- **Todos os produtos como desfecho primário:** multiplica as chances de um falso achado; um primário por pergunta torna a leitura do G1 objetiva.

## Consequências e limitações

- Q1 a Q3 têm cerca de seis meses a menos de dados do que o banco oferece.
- Os limiares (R$ 0,01 para mudança, R$ 0,10 para evento estadual, 25% de seguidores em Q3) são escolhas deste projeto, feitas sem ver os resultados; a robustez mostra a sensibilidade a parte deles.
- O pré-registro é um compromisso verificável pelo histórico do Git, não uma garantia externa: o commit do protocolo precisa ser anterior ao do primeiro relatório em `reports/study/`.
