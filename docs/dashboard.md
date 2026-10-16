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
| **Início** | semana mais recente, última coleta, download, idade do dado; mediana estadual e variação por produto; se o etanol compensa no estado; cobertura da semana; municípios em destaque |
| **Explorar município** | cartões (mediana, média, faixa, diferença para o estado), *Na hora de abastecer* (quanto o posto mais barato fica abaixo da mediana, em R$/L e num tanque de 50 L, comparado ao reajuste semanal típico; e se o etanol compensa, com a razão das últimas 26 semanas), gráfico histórico com faixa p25–p75 e referência estadual, postos pesquisados com o último preço, download CSV |
| **Postos: mais baratos e mais caros** | os 5 postos de menor e os 5 de maior preço do município e produto escolhidos, só entre os que têm preço na semana mais recente do conjunto; muda com o município |
| **Preços por bandeira** | mediana por bandeira (inclusive bandeira branca) no estado ou município, com faixa do menor ao maior preço; só bandeiras com 3 postos ou mais |
| **Previsões** | histórico recente, previsão de 1 a 4 semanas com intervalo de 80%, modelo em uso e quão confiável é; sem número quando a série não é elegível |
| **Variações incomuns** | semanas em que a mediana saiu da faixa de 99% de variação esperada, com observado, esperado, faixa e postos |
| **Comparar municípios** | de 2 a 5 municípios numa semana: mediana, diferença para o estado, variação, amostra, cobertura e posição; gráficos em valores absolutos e em índice (base 100) |
| **Regiões** | capital, região metropolitana, litoral e interior na semana mais recente (mediana e diferença para a capital), gráfico das últimas 26 semanas e os municípios de cada região; rankings de onde o etanol mais compensa e de onde escolher o posto rende mais, nas últimas 26 semanas |
| **Margem dos postos** | preço nos postos × preço médio de distribuição da ANP e a **margem bruta de revenda** por semana, no estado ou município; no estado, a margem de cada município; no município, a margem bruta **estimada** de cada posto, com texto neutro e o aviso de que não é lucro nem o custo real do posto |
| **Estudo** | os achados do estudo (Q1 a Q3), o gate G1 e as medidas para o consumidor, **congelados** na janela do estudo (13/11/2022 a 29/03/2026) e rotulados assim; lê `reports/study/*.json`, não a API |
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

## Previsões e variações incomuns

A página de qualidade mostra o modelo publicado e o resultado do backtest, inclusive quando o candidato de machine learning não é aprovado (hoje o publicado é o baseline "último valor"). A previsão é da mediana semanal, não do preço de um posto, e não considera petróleo, câmbio nem política de preços. Veja o [cartão do modelo](model-card.md).

## Modo instantâneo (demonstrativo)

Com `RADAR_SNAPSHOT` apontando para um pacote, o painel lê o pacote em vez da API ([ADR 0009](decisions/0009-demonstrativo-e-pacote-instantaneo.md)). O pacote é gerado por `scripts/build_snapshot.py` (com `API_DATABASE_URL`) e fica em `snapshot/radar-sp.json.gz`; `demo/streamlit_app.py` é o ponto de entrada do demonstrativo:

```powershell
.\.venv\Scripts\python.exe -m streamlit run demo/streamlit_app.py
```

Em modo instantâneo, o rodapé avisa que é demonstrativo e quando o pacote foi gerado, e os postos aparecem sem CNPJ nem razão social (sem nome fantasia, pela bandeira).

## Não existe ainda

Autenticação. A atualização do pacote é automática desde o Marco 12 ([ADR 0011](decisions/0011-rotina-semanal-no-ci.md)).
