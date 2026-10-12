# Painel

Guia do painel do Marco 6. Decisões em [ADR 0005](decisions/0005-painel-streamlit.md); os dados vêm da [API](api.md). O painel é uma página Streamlit que consulta a API e **não acessa o banco**.

## Subir

Com a API no ar (passo a passo em [api.md](api.md)):

```powershell
$env:RADAR_API_URL = "http://127.0.0.1:8000"          # padrão; ajuste se a API estiver em outra porta
.\.venv\Scripts\python.exe scripts/run_dashboard.py     # http://127.0.0.1:8501
```

Dependências: `pip install streamlit==1.65.0 plotly==7.1.0 httpx==0.28.1`. O painel escuta só em `127.0.0.1`.

## Páginas

| Página | O que mostra |
|---|---|
| **Início** | semana mais recente, última coleta, download, idade do dado; mediana estadual e variação por produto; cobertura da semana; municípios em destaque |
| **Explorar município** | cartões (mediana, média, faixa, diferença para o estado), gráfico histórico com faixa p25–p75 e referência estadual, postos pesquisados com o último preço, download CSV |
| **Postos: mais baratos e mais caros** | os 5 postos de menor e os 5 de maior preço do município e produto escolhidos, só entre os que têm preço na semana mais recente do conjunto; muda com o município |
| **Comparar municípios** | de 2 a 5 municípios numa semana: mediana, diferença para o estado, variação, amostra, cobertura e posição; gráficos em valores absolutos e em índice (base 100) |
| **Qualidade e metodologia** | fonte, cargas, observações publicadas, com aviso e em quarentena, séries com cobertura baixa, como ler os números e limitações |

A URL guarda o município e o produto (`/municipio?municipio=CAMPINAS&produto=GASOLINA_COMUM`), então uma visão pode ser compartilhada.

## Como ler a tela

- **Mediana** é o indicador principal; a faixa sombreada do gráfico vai do percentil 25 ao 75 e a linha tracejada é a mediana do estado.
- **× no gráfico** marca semanas de cobertura baixa: poucos postos frente às 8 semanas anteriores. Nelas a variação semanal é `N/D`.
- **Lacunas** na linha são semanas sem dados; nada é preenchido.
- **Última coleta** e **arquivo baixado em** vêm de cada resposta da API. "Sem registro de download" indica arquivo recebido manualmente.
- **Postos pesquisados** (em *Explorar município*) inclui todo posto que já teve preço do produto; confira a data de cada preço.
- **Mais baratos e mais caros** usa só postos com preço coletado na semana mais recente do conjunto (domingo a sábado). Um posto cujo último preço é de meses atrás não entra: sem reajuste registrado, ele pareceria o mais barato por falta de dado, não por preço. Se o município não tem nenhum posto na semana, a página diz isso em vez de mostrar preços antigos. Preços com aviso de **preço extremo** continuam na lista, marcados, porque podem ser reais (e o ranking de extremos é onde eles mais aparecem).
- **Índice base 100** usa a primeira semana em que todos os municípios escolhidos têm dados; mostra variação relativa, não nível de preço.

Nas tabelas, clicar no cabeçalho de uma coluna ordena pelo valor real (data no calendário, preço e contagem como número), embora a exibição seja em formato brasileiro.

## Exportação

Os botões baixam CSV com `;` como separador, vírgula decimal e BOM, para abrir direto no Excel em português: histórico (uma linha por semana, com cobertura e variação) e postos (cadastro e último preço). Limite de 2.000 linhas, com aviso.

## Não existe ainda

Previsões, variações incomuns, métricas de backtesting, autenticação e implantação pública. Entram nos Marcos 7 e 8.
