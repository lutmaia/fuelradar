# 0005 — Painel: Streamlit sobre a API, sem acesso ao banco

- **Status:** aceita (Marco 6, 2026-10-11)
- **Contexto:** a seção 16 da [arquitetura](../architecture.md) define as páginas do painel e a seção 17 recomenda Streamlit e Plotly. A API de leitura existe ([ADR 0004](0004-api-de-leitura.md)). `/forecasts` e `/anomalies` ficam para o Marco 7, então as páginas de previsão e de variações incomuns não entram agora.

## Decisão

1. **Streamlit + Plotly.** Streamlit monta as páginas em Python, com filtros, tabelas e downloads; Plotly desenha os gráficos interativos. Ambos estão na arquitetura. O Streamlit traz pandas, numpy, pyarrow e outras dependências transitivas (cerca de 30 pacotes).
2. **O painel só fala com a API.** `dashboard/client.py` é um cliente `httpx` para os endpoints do ADR 0004; o painel não importa nada de `db/`, não tem credenciais de banco e usa só `RADAR_API_URL`. Assim a API é o único contrato de dados e o painel pode rodar noutra máquina. O `httpx` passa a ser dependência de produção (antes só de testes).
3. **O painel não calcula preço.** Ele formata, destaca limites e desenha: medianas, estatísticas, variações, posições e cobertura vêm prontos da API. Os únicos cálculos locais são de apresentação: o índice base 100 do gráfico comparativo e a diferença entre a mediana do município e a do estado na mesma semana.
4. **Páginas** (seção 16): Início, Explorar município, Postos (mais baratos e mais caros), Comparar municípios e Qualidade e metodologia. Não há página nem texto de previsão ou de variação incomum; a metodologia diz que ainda não existem.
5. **Atualidade, fonte e amostra sempre visíveis:** toda página mostra data da última coleta, instante do download (ou "sem registro de download") e número de observações e de postos. Cobertura baixa, série sem dados na semana mais recente, semana sem anterior e dados com mais de 14 dias têm aviso próprio.
6. **Sem inventar valores:** semanas sem dados são lacunas no gráfico (nunca interpoladas); variação sem valor aparece como `N/D` com o motivo; cobertura baixa aparece com marcador `×` (não só cor); ranking exclui cobertura baixa (regra da API).
7. **Experiência (16.7):** layout largo e responsivo do Streamlit, textos em português, valores em formato brasileiro (`R$ 6,29`, `27/09/2026`), tooltips nas métricas, paleta Okabe-Ito para daltônicos, tabela de dados sob cada gráfico, URL com `?municipio=&produto=` para compartilhar uma visão.
8. **Download em CSV** do histórico e dos postos, com `;`, vírgula decimal e BOM (Excel em português). Limite de 2.000 linhas, avisado quando atinge (seção 24: limitar exportações). Sem endpoint novo na API.
9. **Cache de 2 minutos** (`st.cache_data`) nas consultas: os dados mudam no máximo uma vez por semana, e isso evita repetir chamadas a cada interação.
10. **Falhas legíveis:** API fora do ar ou erro da API viram uma mensagem com o código e o `request_id`, nunca uma pilha.
11. **Tabelas tipadas.** Cada coluna guarda o valor de verdade (`date`, número) e um formatador cuida só da exibição em pt-BR (`dashboard/tables.py`, com o `Styler` do pandas). Assim, clicar no cabeçalho ordena pelo calendário ou pelo número, não pelo texto: uma coluna `31/08/2026` como texto ordena pelo dia antes do mês e colocava 31/08 antes de 30/09. Isso foi achado em uso e corrigido; ver `PLAN.md`.
12. **Mais baratos e mais caros só com preço da semana mais recente.** Pedido de uso: ordenar o "último preço" de *Explorar município* punha em primeiro um posto com preço de três meses atrás, que parecia o mais barato justamente por não ter sido reajustado. A página *Postos* usa `GET /stations?only_latest_week=true&order=price_asc|price_desc&page_size=5`: a regra (semana mais recente do estado para o produto, via `mart_weekly_state_price`) e a ordenação ficam na API, não no painel. "Atual" é a semana da ANP (domingo a sábado), a mesma unidade do restante do painel, e não uma janela de dias arbitrária. Preço com aviso `preco_extremo` não é excluído (seria decidir sozinho o que é erro); aparece marcado e explicado.
13. **Dependências novas (justificadas):** `streamlit==1.65.0`, `plotly==7.1.0`, `httpx==0.28.1` e `pandas==3.0.6`, que já vinha com o Streamlit e passou a ser usado diretamente.

## Alternativas consideradas

- **Painel lendo o banco direto:** mais simples, mas duplicaria regras (cobertura, variação, ranking) e ultrapassaria a fronteira da API. Descartado.
- **Dash, Panel ou um front-end próprio:** o Streamlit já cobre a necessidade e a arquitetura o recomenda.
- **Gráficos nativos do Streamlit (Altair):** menos controle sobre faixa p25–p75, marcadores de cobertura e lacunas.
- **Texto já formatado em pt-BR nas células:** foi a primeira versão e ordenava errado (datas pelo dia, contagens como `1.251` antes de `98`). Descartado pelo `Styler`, que mantém o valor tipado e só formata a exibição.
- **`st.column_config.NumberColumn`/`DateColumn` com formato:** ordenam certo, mas o formato de número segue o padrão do navegador (ponto decimal) e não há `R$`.

## Consequências e limitações

- **Sem previsão, variações incomuns, autenticação nem métricas de uso.** Previsões entram no Marco 7; operação e exposição pública, no Marco 8.
- **A lista de municípios em destaque é fixa** (maiores cidades paulistas presentes nos dados). Não há "popularidade" real.
- **"Atual" é a semana mais recente do estado, não a do município.** Um município cuja última coleta foi na semana anterior fica com lista vazia, e a página avisa. Isso é correto para o objetivo (não comparar preços de datas diferentes), mas pode esvaziar cidades pequenas em semanas em que a ANP não pesquisou lá.
- **Os nomes aparecem como a ANP publica** (caixa alta, sem acento).
- **Postos:** a lista inclui postos que já tiveram preço do produto em qualquer semana, não só os da semana atual; cada preço traz sua data.
- **Testes sem navegador** usam o `AppTest` do Streamlit; a renderização visual foi conferida à parte, em Edge headless (ver `PLAN.md`), e não há teste automatizado de aparência.
- **Aviso conhecido:** o `TestClient` do Starlette 1.7 marca o uso com `httpx` como obsoleto (recomenda `httpx2`). Funciona e as versões estão fixadas; reavaliar ao atualizar o FastAPI.
- **Não verificado:** uso em celular real, leitores de tela e contraste medido com ferramenta; só se conferiu o layout em 1.400, 1.000 e 600 px de largura (sem rolagem horizontal).
