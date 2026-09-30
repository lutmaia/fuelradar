# Visão do produto

## Problema

Os levantamentos públicos de preços da ANP estão distribuídos em arquivos periódicos. O projeto pretende facilitar a consulta e a comparação, preservando rastreabilidade e limites da pesquisa.

## Público

- Consumidores interessados nos preços pesquisados em municípios paulistas.
- Analistas interessados em histórico, comparações e cobertura.
- Recrutadores e avaliadores que buscam evidências de engenharia de dados e ciência de dados reproduzíveis.

## Proposta de valor

Transformar dados da ANP em consultas e comparações claras, com fonte, datas e amostra visíveis; posteriormente avaliar previsões semanais com incerteza.

## Escopo inicial

Somente São Paulo: histórico e atualização semanal, estatísticas por município e produto, comparação estadual, API de leitura e painel, entregues progressivamente. Arquivos nacionais originais serão preservados integralmente; o recorte SP será aplicado apenas nas etapas derivadas. A principal especificação é [architecture.md](docs/architecture.md).

## Fora do escopo

Agentes de IA, chat, RAG e sistemas multiagentes; preços em tempo real; promessa de cobertura de todos os postos; interpretação de anomalias como fraude. Cobertura nacional, aplicativo móvel, GLP e enriquecimentos são evoluções futuras, não requisitos do MVP. ML e nuvem pertencem a marcos posteriores, não à fundação.

## Expansão nacional

Preservar `uf` nos futuros contratos, chaves pertinentes, filtros e interfaces, com cobertura centralizada em `TARGET_UFS`, inicialmente `["SP"]`. Ativar outras UFs somente após validar dados, qualidade, testes, custo e desempenho, com cobertura explicitada ao usuário.

## Definição de sucesso

O produto será bem-sucedido quando permitir consultas úteis e reproduzíveis sobre SP, informar fonte, datas e cobertura, preservar originais e rastrear observações, atualizar sem duplicar cargas e tornar falhas de qualidade visíveis. API e painel deverão ser demonstráveis e testados. Na versão completa, previsões deverão ter avaliação temporal contra baselines e incerteza; um modelo complexo só será publicado se aprovado. A definição completa e as metas estão nas seções 6 e 30 da arquitetura; são objetivos, não resultados alcançados.

Estado atual: fundação e descoberta dos nove XLSX recebidos, com perfil reproduzível e contrato proposto, conforme [PLAN.md](PLAN.md). O histórico disponível é agregado; isso ainda não constitui ingestão histórica por posto nem produto funcional.
