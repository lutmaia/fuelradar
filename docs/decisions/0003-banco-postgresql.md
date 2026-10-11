# 0003 — Banco PostgreSQL, migrações em SQL e carga por instantâneo

- **Status:** aceita (Marco 4, 2026-10-10); a decisão 1 (binários portáteis) foi substituída por Docker Compose no último adendo, de 2026-10-10
- **Contexto:** a seção 11 da [arquitetura](../architecture.md) define as tabelas, e a seção 9.2 manda substituir o período derivado numa transação quando a fonte revisa um arquivo. O Marco 3 entrega um conjunto publicado único em CSV ([ADR 0002](0002-qualidade-quarentena-e-precedencia.md)). A máquina de desenvolvimento não tinha PostgreSQL nem Docker.

## Decisão

1. **PostgreSQL 16.15, binários portáteis da EDB**, extraídos em `%LOCALAPPDATA%/radar-combustiveis` (fora do projeto e do OneDrive, que sincroniza e trava arquivos de banco). Sem instalador, serviço nem administrador; `scripts/local_postgres.py` cria, sobe e para o servidor em `localhost:54329`, com autenticação `scram-sha-256` e senha gerada localmente. Docker Compose continua previsto para o Marco 8.
2. **Uma dependência nova: `psycopg[binary]==3.3.6`** (driver PostgreSQL 3, com a biblioteca C embutida; traz `tzdata` no Windows). Sem SQLAlchemy.
3. **Migrações em SQL puro** (`migrations/NNNN_nome.sql`), executadas por um runner de ~50 linhas: uma transação por arquivo, registro em `schema_migration` com SHA-256, erro se um arquivo já aplicado mudar e *advisory lock* contra execuções simultâneas. Alembic e SQLAlchemy (recomendados na arquitetura) não foram adotados: o esquema não usa ORM, a geração automática não é necessária e custariam três dependências. Reavaliar se surgir ORM na API.
4. **Esquema `radar`**, com as tabelas da seção 11: `ingestion_run`, `source_file`, `dim_location`, `dim_product`, `dim_station`, `fact_price_observation`, mais `quarantine_observation` (linhas suspeitas com motivo e valores originais, para reconciliar as contagens no banco).
5. **A carga é um instantâneo atômico.** `staging/observations.csv` é o conjunto vigente: numa transação, a carga sincroniza `source_file`, faz upsert das dimensões e do fato, marca `is_current_source_revision = false` nas linhas que saíram do instantâneo (revisão nova, precedência entre fontes, regra de qualidade) **sem apagá-las**, reconcilia as contagens e recalcula as agregações. Falha desfaz tudo e grava uma execução `failed` com resumo sem valores de linha. A carga se recusa se a qualidade decidiu `bloquear` ou se os arquivos não batem com o relatório.
6. **Integridade no banco, não só no código:** uma observação vigente por `row_key` (índice único parcial), uma revisão vigente por período, `week_start` obrigatoriamente domingo, preço positivo, `quality_status` coerente com os avisos, chaves estrangeiras e `UNIQUE (source_file_id, source_row_hash)`.
7. **Agregações como visões materializadas** (`mart_weekly_city_price` e `mart_weekly_state_price`), recalculadas na transação da carga. Mediana e percentis por `percentile_cont` (linear, igual a `statistics.quantiles(method="inclusive")`), arredondados a 4 casas; mínimo e máximo exatos. A cobertura repete a regra do relatório de qualidade (mediana de postos das oito semanas anteriores, ausência = 0, `cobertura_baixa` abaixo de 50% de uma mediana ≥ 3) e é conferida contra ele.
8. **Produtos em `dim_product` por semente na migração**, espelhando `PRODUCTS` e `PRODUCT_UNITS`; um teste confere a igualdade. Produto fora da tabela recusa a carga.
9. **Testes com banco real**, ativados por `RADAR_TEST_DATABASE_URL` (cada teste cria e remove o próprio banco). Sem a variável, são ignorados.

## Diferenças em relação à arquitetura

- `source_file_id` é o texto de 16 hexadecimais já usado nas saídas, não UUID; o SHA-256 completo é `UNIQUE`.
- `dim_station.first_seen_at`/`last_seen_at` viraram `first_seen_date`/`last_seen_date` (são datas de coleta, não instantes) e há `legal_name`, porque o histórico só traz a razão social.
- `dim_location` não tem centroides e `ibge_code` fica nulo: não há fonte validada para eles.
- `ingestion_run` registra a execução de **carga** e referencia a execução de qualidade (`quality_run_id`, `quality_decision`).
- dbt Core e Pandera ficam fora por enquanto: as transformações são SQL versionado nas migrações, com teste próprio. Reavaliar no Marco 8.

## Alternativas consideradas

- **Carga incremental por arquivo:** não detecta que uma linha publicada deixou de valer por precedência ou nova regra; o instantâneo trata os três casos com a mesma regra.
- **Apagar linhas antigas:** perderia a auditoria de revisões; mantê-las custa pouco volume.
- **SQLite:** não exercita percentis, índices parciais nem a transação que o marco exige verificar.
- **Instalar o PostgreSQL no sistema ou o Docker Desktop:** alteram a máquina além do necessário para este marco.

## Consequências

- **Binários sem assinatura digital.** Os zips da EDB não são assinados (só o instalador); a origem é o link indicado por postgresql.org e o SHA-256 do arquivo baixado é `25e6fcdfb8caec38691bf461125e7564508760666f7b8e5dc6a5f0818f58f81e`. Aceitável para um banco de teste local sem dados sigilosos; não use este caminho em servidor.
- `is_current_source_revision` significa "pertence ao conjunto publicado atual", mais amplo que "revisão vigente".
- `first_seen_date`/`last_seen_date` só se ampliam: uma revisão que remova as linhas mais recentes de um posto não as recua.
- Atributos de posto e município seguem a regra "o mais recente vence": mudanças de bandeira ou endereço não têm histórico.
- Todo o histórico fica em `fact_price_observation`; a limpeza de linhas não vigentes é decisão futura.

## Adendo — Docker Compose (2026-10-10)

A pedido do projeto (portfólio), o banco também sobe por `docker-compose.yml`, com `postgres:16.15-bookworm`, mesma versão dos binários portáteis, porta somente em loopback, senha vinda do `.env` e dados em volume do Docker. O caminho portátil permanece como alternativa para quem não tem Docker. Verificado em 2026-10-10 com Docker Desktop 4.94.0 (engine 29.8.2, Compose v5.5.1): `docker compose config` válido; contêiner `healthy` com a porta só em `127.0.0.1`; carga real de 179.699 observações e recarga com 0 alterações; os 100 testes aprovados contra ele; os dados sobrevivem a `docker compose down` e `up` (volume `radar-combustiveis_pgdata`); a conferência independente CSV × banco repetida sem divergência. Conteinerizar o pipeline e a futura API segue no Marco 8.

**Lição: use `127.0.0.1`, não `localhost`, na URL.** No Windows, `localhost` resolve primeiro para `::1`; o Docker publica a porta só em IPv4, e cada conexão esperava ~30 s pelo timeout do IPv6 antes de cair no IPv4 (a primeira carga levou minutos; com `127.0.0.1` a recarga leva ~4,5 s). Consultas e `COPY` não eram o gargalo.

## Adendo — somente Docker (2026-10-10)

Decisão do projeto: o banco de desenvolvimento e teste passa a rodar **somente em Docker Compose**. O caminho de binários portáteis da EDB foi descontinuado: `scripts/local_postgres.py` e a "Opção B" do runbook foram removidos, e a pasta `%LOCALAPPDATA%/radar-combustiveis` já não existia na máquina. Isso substitui a decisão 1 deste ADR e dispensa a consequência sobre binários sem assinatura digital (e o SHA-256 do zip da EDB), que só valiam para aquele caminho. O restante permanece: `postgres:16.15-bookworm`, porta só em `127.0.0.1:54329`, `scram-sha-256` pela imagem oficial e senha no `.env` ignorado pelo Git.

Consequência: quem não tem Docker Desktop não consegue rodar o banco por este repositório. Os testes com banco continuam opcionais (`RADAR_TEST_DATABASE_URL`), e o histórico em `PLAN.md` e nas seções acima descreve o que foi feito no Marco 4 com os binários, sem reescrita.
