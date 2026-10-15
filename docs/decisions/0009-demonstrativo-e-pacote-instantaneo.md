# 0009 — Demonstrativo público: painel lendo um pacote instantâneo

- **Status:** aceita (2026-10-14, antecipa parte dos Marcos 12 e 13 por decisão do usuário)
- **Contexto:** sem demonstração online, quem avalia o projeto precisa instalar Python, Docker e baixar os dados da ANP. O [desenho](../estudo-de-caso.md) (seções 8 e 9) prevê um *modo instantâneo*: o painel lê um pacote de arquivos em vez de uma API viva, hospedado de graça no Streamlit Community Cloud. Custo zero e repositório público são decisões já tomadas.

## Decisão

1. **Pacote gerado pela API, não por outro código.** `scripts/build_snapshot.py` sobe a API em processo (sem servidor) sobre o banco, com o usuário somente leitura, e grava as respostas de toda consulta finita que o painel faz (produto × município): última semana, bandeiras, previsões, escolha do posto, etanol, regiões, rankings, postos e qualidade. Assim o pacote segue as regras da API sem duplicá-las.
2. **O que é combinatório é recalculado no cliente com a regra da API.** Histórico por intervalo (guarda-se a série de 3 anos de cada produto e município e corta-se), comparação de 2 a 5 municípios (posição, empate, cobertura baixa) e filtros de variações incomuns. Para o `data_as_of` de qualquer recorte, o pacote guarda a última coleta e o último download por produto, município e semana. `tests/test_snapshot.py` confere, sobre o banco sintético, que o cliente instantâneo devolve exatamente o que a API devolve nas mesmas consultas.
3. **Mesmo painel, outro cliente.** `dashboard/snapshot.py` tem os mesmos métodos do cliente HTTP; `RADAR_SNAPSHOT` escolhe o pacote. Em modo instantâneo, o rodapé de toda página diz que é demonstrativo, quando o pacote foi gerado e que não há atualização automática; a idade do dado é contada a partir de hoje, então o aviso de dado antigo aparece sozinho.
4. **Privacidade (decisão do usuário, 2026-10-14):** nenhum CNPJ nem razão social vai ao pacote. O posto aparece pelo nome fantasia publicado pela ANP ou, sem ele (2.487 dos 4.009 postos), como "Posto" + bandeira; o endereço continua em coluna própria. Teste e conferência no pacote real: nenhum CNPJ e nenhuma razão social de posto sem nome fantasia aparecem no arquivo.
5. **Pacote commitado no repositório** (`snapshot/radar-sp.json.gz`, decisão do usuário), sem dado bruto da ANP. Formato JSON compactado com gzip.
6. **Hospedagem:** ponto de entrada `demo/streamlit_app.py`, com `demo/requirements.txt` mínimo (Streamlit, Plotly, pandas e httpx, nas versões do projeto), para a hospedagem não instalar banco, API nem LightGBM.

## Alternativas consideradas

- **Pré-calcular tudo, inclusive comparações:** o número de combinações de 2 a 5 entre 108 municípios em 156 semanas é grande demais.
- **Gerar o pacote direto do banco, com SQL próprio:** duplicaria as regras de cobertura, variação e ranking; qualquer divergência viraria um painel diferente da API.
- **Banco embarcado (SQLite/DuckDB) com a mesma API:** tiraria a API de dentro do demonstrativo à custa de portar o SQL do PostgreSQL; mais código para o mesmo resultado.
- **Pacote como anexo de release do GitHub:** mantém o histórico do Git limpo, mas exige publicar releases e baixar o arquivo ao iniciar. Pode substituir o commit no Marco 12, com a atualização semanal.

## Consequências e limitações

- **Tamanho:** o pacote de 2026-10-14 tem 4.679 respostas e 654 séries, 43,5 MB de JSON e 2,6 MB compactado; carrega em cerca de 1,6 s e ocupa cerca de 150 MB de memória. Cada atualização commitada aumenta o histórico do Git em alguns MB.
- **Sem atualização automática:** o pacote é gerado à mão até o Marco 12.
- **Histórico de 3 anos a partir da semana mais recente do conjunto:** uma série que parou há mais tempo mostra no demonstrativo só a parte dentro dessa janela.
- **Atualização com o app no ar (corrigido em 2026-10-15):** o Streamlit só recarrega módulos da pasta do ponto de entrada (`demo/`). Depois do push do Marco 9, o app rodou o `app.py` novo com o `views` antigo na memória e caiu com `AttributeError` (`margins_page`); o mesmo valeria para o pacote, preso no cache. `demo/streamlit_app.py` passou a comparar a data de modificação de `src/` e do pacote a cada execução e, se algo mudou, descarta os módulos `radar_combustiveis` e os caches. Reproduzido e conferido localmente (página nova adicionada com o app no ar). Até esse arquivo chegar ao app, o remédio é *Reboot app*.
- **O desempate entre postos com o mesmo preço** segue o nome usado pela API (com a razão social), não o nome público; a ordem dos empatados pode parecer arbitrária.
- **Implantado em 2026-10-14** em https://fuelradar-a5kwciypheseufpbfh6ggv.streamlit.app/: a instalação com `demo/requirements.txt` funcionou e as páginas abriram com o pacote. Limites de memória do plano gratuito seguem sem medição.
- **Verificado só em parte:** se o Streamlit Community Cloud usa `demo/requirements.txt` (pasta do ponto de entrada) antes do `pyproject.toml` da raiz, a versão de Python disponível e os limites de memória do plano gratuito.
