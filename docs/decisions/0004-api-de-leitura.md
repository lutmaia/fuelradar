# 0004 — API de leitura: FastAPI, SQL explícito e usuário somente leitura

- **Status:** aceita (Marco 5, 2026-10-10)
- **Contexto:** a seção 15 da [arquitetura](../architecture.md) define a API REST. O Marco 4 deixou as agregações semanais no PostgreSQL ([ADR 0003](0003-banco-postgresql.md)) e três pendências para esta etapa: usuário de leitura separado, medição de desempenho e tratamento do `source_retrieved_at` nulo. O usuário decidiu não expor `/forecasts` nem `/anomalies` antes do Marco 7.

## Decisão

1. **FastAPI + Uvicorn.** FastAPI valida parâmetros, gera o OpenAPI e documenta os contratos (Pydantic vem junto). Uvicorn é o servidor ASGI que o executa. Ambos estão na arquitetura (seções 15 e 17).
2. **SQL explícito com psycopg, sem SQLAlchemy.** Cada consulta é uma função em `api/queries.py`, sempre parametrizada. A API só lê visões materializadas e filtros simples; um ORM não ajudaria e custaria dependências. A camada fica isolada em um módulo, então trocar depois é barato. Reavaliar se surgir escrita ou muitos filtros dinâmicos.
3. **`psycopg-pool` síncrono.** Os endpoints são `def` (o FastAPI os roda em threads) e usam um pool pequeno (5 conexões, espera de 5 s). O pool abre sem esperar o banco: `/health/live` responde mesmo com o banco fora e `/health/ready` informa a falha com `503`.
4. **Usuário somente leitura, por menor privilégio.** A migração `0003_api_reader.sql` cria o papel `radar_reader` (sem login) com `SELECT` apenas nas tabelas e colunas usadas: `storage_uri`, `error_summary`, `original` da quarentena e `schema_migration` ficam de fora. `scripts/create_api_role.py` cria o login `radar_api` como membro dele, com a senha vinda de `RADAR_API_PASSWORD` (nunca na linha de comando). A API lê `API_DATABASE_URL` e **não** cai para `DATABASE_URL`, o usuário de escrita do pipeline. Mesmo assim cada sessão abre com `default_transaction_read_only=on`.
5. **Consistência e limites por requisição.** Isolamento `REPEATABLE READ`: todas as consultas de uma requisição veem o mesmo instantâneo, mesmo que uma carga termine no meio. `statement_timeout` de 5 s vira `503 QUERY_TIMEOUT`.
6. **Índices novos (mesma migração):** `(location_id, product_id, week_start)` na visão municipal, pois o índice único começa por `week_start`; e `(collection_date)` parcial no fato, para a "última coleta" sem varrer a tabela.
7. **Contrato.** Prefixo `/api/v1`; JSON; datas ISO 8601; preços como número JSON; formato de erro único com `request_id` (também em `X-Request-ID`, aceito do cliente se tiver só `[A-Za-z0-9._-]{1,64}`); `details` só em `VALIDATION_ERROR`. `422` para parâmetros inválidos (inclusive `UF_NOT_PUBLISHED`, `INVALID_RANGE`, `RANGE_TOO_LARGE`, `INVALID_WEEK`) e `404` para recurso inexistente (`LOCATION_NOT_FOUND`, `PRODUCT_NOT_FOUND`, `NO_DATA`).
8. **Limites:** `uf` só aceita as de `TARGET_UFS` (padrão `SP`); histórico de até 1.096 dias (3 anos, ≤ 157 semanas) e padrão de 52 semanas; comparação de até 10 municípios; `page_size` até 200.
9. **Semântica dos dados.**
   - **Indicador principal:** mediana semanal; a semana é a da ANP (domingo a sábado) e `week_start` é sempre domingo.
   - **Atualidade:** `data_as_of` é a última coleta usada pelo recorte (não a data de hoje) e `source_retrieved_at` é o download mais recente entre os arquivos que o sustentam, **nulo** para arquivos recebidos manualmente.
   - **`/prices/latest`:** é a última semana *da série*. Se ela não é a mais recente do conjunto, `is_dataset_latest_week` é falso e a resposta diz qual semana usou. Não se preenche lacuna.
   - **`coverage_status`:** `ok`, `low` (abaixo de 50% da mediana de postos das 8 semanas anteriores, base ≥ 3), `no_history` (sem 8 semanas de base **ou série nova, base zero**), `not_applicable` (agregado estadual, que traz a contagem de municípios com cobertura baixa) e `no_data`. A base zero é marcada `ok` na visão (ausência conta como zero, [ADR 0003](0003-banco-postgresql.md)); a API a apresenta como `no_history`, porque uma série que acabou de aparecer não tem com o que ser comparada.
   - **Variação semanal:** `mediana ÷ mediana da semana anterior − 1`, com `null` e motivo (`NO_PREVIOUS_WEEK`, `LOW_COVERAGE`) quando não há semana imediatamente anterior ou a cobertura de qualquer das duas é baixa.
   - **Ranking de `/prices/compare`:** só entre municípios com dados e cobertura não baixa (seção 12.3 da arquitetura); empates compartilham a posição.
   - **Nomes:** os municípios saem como a ANP publica (caixa alta, sem acento); a entrada é aceita sem distinção de caixa, acento ou espaços repetidos.
   - **Postos:** `/stations` lista a amostra pesquisada, não o cadastro de revendedores; com `product`, só os postos com preço desse produto e o último preço de cada um, com a data.
10. **Não publicados:** `/api/v1/forecasts` e `/api/v1/anomalies` (Marco 7). Não há rota que devolva lista vazia fingindo cobertura; elas respondem `404 NOT_FOUND`.
11. **Dependências novas:** `fastapi==0.143.0`, `uvicorn==0.54.0` e `psycopg-pool==3.3.3` em produção; `httpx==0.28.1` só para testes (cliente do `TestClient`); no Marco 6 ele passou a dependência de produção, como cliente do painel ([ADR 0005](0005-painel-streamlit.md)). Transitivas: starlette, pydantic, anyio, h11, click, entre outras.

## Alternativas consideradas

- **SQLAlchemy:** adiciona uma camada e dependências sem benefício para leituras de visões prontas.
- **Pool assíncrono (`AsyncConnectionPool`) e endpoints `async`:** mais código e mais risco de bloquear o laço de eventos para consultas curtas.
- **Cair em `DATABASE_URL` quando `API_DATABASE_URL` falta:** conveniente, mas faria a API rodar silenciosamente com o usuário de escrita.
- **Preencher semanas ausentes com o último valor:** inventaria preços; lacunas são informação.

## Consequências e limitações

- **Sem autenticação, limite de taxa, CORS nem TLS.** É uma API pública de dados públicos, mas a exposição na internet fica para o Marco 8 (proxy, TLS e limites). Hoje escuta só em `127.0.0.1`.
- `CREATE ROLE` na migração exige `CREATEROLE`/superusuário; o `radar` do contêiner tem. Em outro servidor, aplique a migração com um usuário que tenha essa permissão.
- `/data-quality` desagrega `quality_flags` e `reasons` com `unnest` sobre o fato (≈ 60 ms com 180 mil linhas). Com volume nacional deve virar visão materializada.
- `source_retrieved_at` é nulo para o CSV semestral e para três semanas recebidas à mão; o painel deve mostrar isso como "sem registro de download".
- Não há exportação CSV (jornada do analista, seção 3.2) nem ranking de variação entre todos os municípios; ficam para o painel (Marco 6), com endpoint próprio se necessário.
- O `request_id` aparece nos logs de erro, mas não há log estruturado de acesso nem métricas (Marco 8).
