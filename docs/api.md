# API de leitura

Guia de uso da API do Marco 5. O contrato completo e executável é o OpenAPI em `/openapi.json` (interface em `/docs`); as decisões estão no [ADR 0004](decisions/0004-api-de-leitura.md). A API só **lê**, sobre os dados já carregados no PostgreSQL, e cobre somente **São Paulo**.

## Subir

```powershell
$pw = (Get-Content .env | Where-Object { $_ -like 'POSTGRES_PASSWORD=*' }).Split('=', 2)[1]
$env:DATABASE_URL = "postgresql://radar:$pw@127.0.0.1:54329/radar"
.\.venv\Scripts\python.exe scripts/load_db.py --migrate-only          # aplica 0003 (papel e índices)

# senha do usuário somente leitura (só hexadecimal, para caber na URL); não é impressa
$env:RADAR_API_PASSWORD = -join ((1..32) | ForEach-Object { '{0:x}' -f (Get-Random -Maximum 16) })
.\.venv\Scripts\python.exe scripts/create_api_role.py
$env:API_DATABASE_URL = "postgresql://radar_api:$($env:RADAR_API_PASSWORD)@127.0.0.1:54329/radar"

.\.venv\Scripts\python.exe scripts/run_api.py                          # http://127.0.0.1:8000/docs
```

`create_api_role.py` é idempotente: repetir troca a senha. Dependências: `pip install fastapi==0.143.0 uvicorn==0.54.0 psycopg-pool==3.3.3 httpx==0.28.1` (o `httpx` serve aos testes e ao [painel](dashboard.md)).

## Endpoints

| Método | Caminho | Para quê |
|---|---|---|
| GET | `/health/live` | o processo está vivo |
| GET | `/health/ready` | o banco responde e há carga publicada (`503` caso contrário) |
| GET | `/api/v1/metadata/freshness` | última coleta, último download, última carga, UFs publicadas |
| GET | `/api/v1/products` | produtos publicados, com unidade |
| GET | `/api/v1/locations` | municípios com preços (`q`, paginação) |
| GET | `/api/v1/prices/latest` | estatística semanal mais recente (`product`; `municipality` opcional) |
| GET | `/api/v1/prices/history` | série semanal (`start`, `end`, paginação) |
| GET | `/api/v1/prices/compare` | municípios lado a lado numa semana, com o estado como referência |
| GET | `/api/v1/prices/by-brand` | mediana semanal por bandeira no mesmo recorte (`product`; `municipality` e `week_start` opcionais) |
| GET | `/api/v1/prices/ethanol-vs-gasoline` | razão entre as medianas do etanol e da gasolina comum por semana e se o etanol compensa (até 70%); `municipality` opcional, `weeks` 1 a 156 |
| GET | `/api/v1/prices/station-choice` | quanto o posto mais barato fica abaixo da mediana do município, a economia típica do último ano e o reajuste semanal típico (`product` e `municipality` obrigatórios) |
| GET | `/api/v1/prices/regions` | capital, região metropolitana, litoral e interior: mediana de todos os preços da região na semana mais recente, diferença para a capital e a série das últimas `weeks` semanas (`product`; `weeks` 1 a 156, padrão 26) |
| GET | `/api/v1/prices/rankings` | por município, nas últimas `weeks` semanas: com que frequência o etanol compensou e a economia típica de escolher o posto (`product`, padrão gasolina comum; `weeks` 1 a 156, padrão 26) |
| GET | `/api/v1/forecasts` | previsão de 1 a 4 semanas com intervalo, modelo publicado e desempenho no backtest (`product`; `municipality` opcional) |
| GET | `/api/v1/anomalies` | variações incomuns recentes (`weeks` 1 a 12; `product` e `municipality` opcionais) |
| GET | `/api/v1/stations` | postos pesquisados, com o último preço do produto (`order=price_asc\|price_desc` e `only_latest_week=true`, ambos exigem `product`) |
| GET | `/api/v1/data-quality` | cobertura da semana, avisos e quarentena |

**Previsões e variações incomuns (Marco 7).** `/forecasts` devolve, por horizonte (1 a 4), `point`, `lower` e `upper` (intervalo de `interval_level`, 80%), o modelo publicado (`name`, `kind`, `version`, `status`) e seu `backtest` (erro médio, viés, cobertura, comparação com o candidato). Série sem previsão volta com `eligible: false` e `reasons`, nunca com um número; sem modelo publicado, `404 NO_PUBLISHED_MODEL`. `/anomalies` lista semanas em que a mediana saiu do intervalo de 99% de variação semanal esperada (diferença mínima de R$ 0,15, ao menos 3 postos): é um sinal estatístico, não uma conclusão sobre os postos. `/prices/by-brand` só detalha bandeiras com 3 postos ou mais (`hidden_brands` conta o resto).

**Na hora de abastecer (Marco 8b).** `/prices/ethanol-vs-gasoline` usa as medianas semanais; semana com cobertura baixa em um dos dois produtos volta com `ratio: null` e `reason: "LOW_COVERAGE"`, e semana sem um dos produtos com `reason: "MISSING_PRODUCT"`; `latest` é a semana mais recente com razão. `/prices/station-choice` só usa semanas com 5 postos ou mais (`latest: null` se não houver); `saving` é mediana menos menor preço, `saving_tank` vale para 50 L e é nulo em produto que não é vendido por litro (GNV); `typical_change` é a mediana do tamanho de uma mudança de preço do mesmo posto entre semanas consecutivas. As definições seguem [docs/estudo/descritivo.md](estudo/descritivo.md).

**Regiões e rankings (página Regiões, Marco 9).** `/prices/regions` lê o fato, como `/prices/by-brand`: a mediana é de todos os preços da região na semana (não a mediana das medianas dos municípios), então a capital domina a própria região. As listas de municípios ficam em `src/radar_combustiveis/regions.py`, as mesmas do estudo descritivo; o que não está nelas é interior. `/prices/rankings` devolve um item por município com dado na janela, com a mesma regra de `/prices/ethanol-vs-gasoline` (semanas com as duas medianas e sem cobertura baixa) e de `/prices/station-choice` (semanas com 5 postos ou mais), resumidas na janela; `ranked` é verdadeiro com dado em pelo menos metade das semanas (`min_weeks`). A ordenação fica para quem consome.

**Postos mais baratos e mais caros.** `GET /api/v1/stations?municipality=…&product=…&only_latest_week=true&order=price_asc&page_size=5` devolve os 5 postos de menor último preço entre os que têm preço na **semana mais recente do estado para o produto** (`latest_week_start` na resposta; domingo a sábado). Postos cujo último preço é de semanas anteriores ficam fora, e `total` conta só os que entraram. Com `order=price_desc` a lista vem do mais caro. Empates de preço desempatam pelo nome, então as páginas não repetem postos. Sem `product`, `order` por preço e `only_latest_week` respondem 422 `PRODUCT_REQUIRED`.
Sem `municipality`, `latest` e `history` devolvem o **agregado estadual**. `uf` é opcional e só aceita `SP` enquanto `TARGET_UFS` for `["SP"]`.

## Exemplo

```http
GET /api/v1/prices/latest?municipality=Campinas&product=GASOLINA_COMUM
```

```json
{
  "data_as_of": "2026-10-01",
  "source_retrieved_at": "2026-10-08T19:25:21Z",
  "location": {"uf": "SP", "municipality": "CAMPINAS"},
  "product": "GASOLINA_COMUM",
  "week_start": "2026-09-27",
  "week_end": "2026-10-03",
  "is_dataset_latest_week": true,
  "statistics": {"min": 5.87, "p25": 5.99, "median": 6.29, "mean": 6.274, "p75": 6.49, "max": 6.95, "stddev": 0.3103},
  "sample": {"observations": 25, "stations": 25, "coverage_status": "ok", "coverage_ratio": 1.0,
             "baseline_median_stations": 25.0, "municipalities": null, "low_coverage_municipalities": null},
  "weekly_change": {"value": -0.0156, "previous_week_start": "2026-09-20", "reason": null}
}
```

Os valores acima vieram do banco real em 2026-10-10 e foram conferidos contra um cálculo direto sobre as observações (25 observações em Campinas; 1.251 no estado).

## Como ler uma resposta

- **`statistics.median`** é o indicador principal. Preços em R$/litro (GNV em R$/m³), com até 4 casas.
- **`data_as_of`** é a última data de coleta do recorte, não "hoje". **`source_retrieved_at`** é quando o arquivo mais recente foi baixado; `null` significa que o arquivo foi recebido à mão e não há registro de download.
- **`sample.coverage_status`**: `ok`, `low` (poucos postos frente às 8 semanas anteriores), `no_history`, `not_applicable` (estado) ou `no_data`. Cobertura baixa não entra em rankings nem em variação semanal.
- **`weekly_change.value`** `null` = N/D, e `reason` diz por quê.
- **`is_dataset_latest_week`** falso: o município ou produto não tem dados na semana mais recente do conjunto; a resposta usou a última semana que ele tem.
- Os preços são de **pesquisa por amostragem**, não preços em tempo real nem o universo de postos.

## Erros

Formato único, com o mesmo `request_id` do cabeçalho `X-Request-ID`:

```json
{"error": {"code": "LOCATION_NOT_FOUND",
           "message": "Município não encontrado na cobertura publicada para São Paulo: Atlântida.",
           "request_id": "3f2c…"}}
```

| Status | `code` | Quando |
|---|---|---|
| 404 | `LOCATION_NOT_FOUND`, `PRODUCT_NOT_FOUND` | município ou produto fora da cobertura publicada (GLP incluído) |
| 404 | `NO_DATA` | recorte válido, sem preços |
| 404 / 405 | `NOT_FOUND`, `METHOD_NOT_ALLOWED` | rota inexistente ou método não permitido |
| 422 | `VALIDATION_ERROR` | parâmetro ausente ou malformado (`details` lista os campos) |
| 422 | `UF_NOT_PUBLISHED` | `uf` fora de `TARGET_UFS` |
| 422 | `INVALID_RANGE`, `RANGE_TOO_LARGE`, `INVALID_WEEK` | `start` > `end`; intervalo acima de 1.096 dias; `week_start` que não é domingo |
| 503 | `NOT_READY`, `DATABASE_UNAVAILABLE`, `QUERY_TIMEOUT` | banco sem carga, fora do ar ou consulta acima de 5 s |
| 500 | `INTERNAL_ERROR` | falha inesperada; só o `request_id` sai, o detalhe fica no log |

## Limites

`page_size` até 200 (padrão 50); histórico de até 1.096 dias (padrão 52 semanas); até 10 municípios em `compare` (repita `municipality=`).

## Desempenho medido

Banco real (179.699 observações, 18.525 linhas semanais), servidor Uvicorn local, cliente na mesma máquina, 30 requisições sequenciais por endpoint, 2026-10-10:

| Endpoint | p50 | p95 |
|---|---|---|
| `prices/latest` (município / estado) | 7 ms | 10 ms |
| `prices/history` (município / estado, 2026 inteiro) | 21 / 26 ms | 22 / 27 ms |
| `prices/compare` (5 municípios) | 8 ms | 9 ms |
| `stations` (município / estado, 200 por página) | 7 / 18 ms | 8 / 22 ms |
| `data-quality` | 52 ms | 58 ms |

A meta da arquitetura é p95 < 500 ms para consultas agregadas comuns. A medição é de **uma máquina, uma sessão e sem concorrência**; não representa carga de 50 requisições por segundo.
