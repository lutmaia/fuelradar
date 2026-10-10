# Plano de desenvolvimento

A [arquitetura](docs/architecture.md) é a especificação principal. Este plano divide sua execução em marcos menores conforme o escopo solicitado, sem alterar o documento. A numeração começa em 0. Cada conclusão exige evidência; não confundir documentação com funcionalidade executada.

- [x] **Marco 0 — Fundação:** documentação, estrutura Python e dados, configuração mínima e proteção no Git. Aceite: conferir estrutura, sintaxe TOML/Python, regras de exclusão e integridade da arquitetura.
- [x] **Marco 1 — Descoberta e contrato dos dados:** nove XLSX reais (históricos agregados e semanas por revenda/resumos), 21 planilhas analisadas; esquema, formatos, cobertura, produtos e qualidade registrados; contrato proposto, perfil reproduzível e 21 testes aprovados. Histórico individual CSV/ZIP não recebido: validar esse formato antes de implementar seu ramo de ingestão.
- [x] **Marco 2 — Ingestão histórica e semanal:** download, manifesto, checksum, versões e rastreabilidade; preservar raw nacional e selecionar SP nas saídas derivadas. Aceite: reexecução sem duplicação e revisão de fonte verificadas em arquivos locais, sem antecipar o banco. Concluído em 2026-10-08: ingestão local e download das semanas por revenda da ANP executados sobre dados reais, 63 testes aprovados. Revisão de fonte verificada só com dados sintéticos (a ANP não revisou nenhum arquivo observado); detalhes na seção "Marco 2 — etapas".
- [x] **Marco 3 — Qualidade e normalização:** padronizar campos, validar regras e preservar suspeitos em quarentena. Aceite: casos válidos, inválidos e falhas críticas exercitados e contagens reconciliadas. Concluído em 2026-10-10: regras críticas, de linha e de cobertura executadas sobre os dados reais, contagens reconciliadas e conferidas de forma independente, 82 testes aprovados. Casos inválidos e falhas críticas só com dados sintéticos (os dados reais não têm nenhum); detalhes em "Verificação do Marco 3".
- [ ] **Marco 4 — Banco de dados:** implementar PostgreSQL, migrações, dimensões, fatos e agregações. Aceite: carga, integridade, revisão e consultas verificadas em banco real de teste.
- [ ] **Marco 5 — API:** consultas de leitura com filtros, paginação, atualidade e cobertura SP. Aceite: contratos, respostas, erros e limite de UF testados.
- [ ] **Marco 6 — Dashboard:** exploração, comparações, histórico, postos e metodologia. Aceite: jornadas verificadas contra API e dados reais, com datas e amostra visíveis.
- [ ] **Marco 7 — Baselines e machine learning:** modelos de referência simples, validação temporal, candidato e intervalos. Aceite: relatório reproduzível e decisão de aprovação ou manutenção do baseline, sem inventar ganho.
- [ ] **Marco 8 — Automação, monitoramento e deploy:** agendamento, CI/CD, contêineres, monitoramento e implantação progressiva. Aceite: execução automática, alertas, recuperação, segredos e custos verificados.
- [ ] **Marco 9 — Acabamento para portfólio:** documentação de reprodução, demonstração, métricas e limitações. Aceite: revisão da definição de pronto da arquitetura e demonstração verificável.

## Limite da tarefa atual

Marco 3 concluído em 2026-10-10. Parar aqui: sem banco (Marco 4), API ou painel. O próximo marco, o 4, só começa por solicitação. `DIESEL` e `DIESEL S500` unidos em `DIESEL_COMUM` por decisão do usuário; S10 separado. Agregados municipais e regionais não são inseridos na tabela de observações individuais.

## Verificação do Marco 0

Concluído em 2026-09-29. Verificados os 16 arquivos esperados, links locais, sintaxe Python e TOML, ausência de dependências e configuração de exemplo SP. O SHA-256 da arquitetura permaneceu idêntico após a renomeação. As regras do `.gitignore` passaram em 26 casos de inclusão/exclusão em repositório temporário, incluindo dados em subpastas e `.env`.

Verificações executadas com Python 3.14.7 e Git já disponíveis, sem instalar dependências. Não foram executados testes funcionais, instalação/build do pacote, análise da ANP, ingestão, banco, API, dashboard, ML ou deploy. `tests/` contém somente um marcador. Nenhum repositório Git foi inicializado nesta pasta e nada foi publicado. Todos os demais marcos permanecem pendentes.

## Verificação do Marco 1

Concluído em 2026-09-29, limitado à descoberta dos arquivos recebidos. A seção anterior registra o estado ao terminar o Marco 0; o estado atual é este:

- Analisados dois históricos mensais municipais, um mensal regional, três resumos semanais e três semanas por revenda: nove arquivos reais, 21 planilhas.
- Perfil executado com sucesso: `scripts/profile_anp_data.py "data/raw/*.xlsx"`, usando `.venv/Scripts/python.exe`. Gerados `reports/data-profile/profile.json` e `summary.md`.
- SP nas revendas: 15.953 linhas, 97 municípios, 2.380 CNPJs (inclui GLP); 13.842 linhas e 1.635 CNPJs no recorte automotivo.
- `python -m unittest discover -s tests -v` no ambiente: **21 testes, OK**. `python -m pip check`: **No broken requirements found.**
- SHA-256 dos nove arquivos permaneceu idêntico ao inventário anterior à análise. Arquitetura também permaneceu intacta. Links locais, TOML, hash do script no relatório e 15 regras de inclusão/exclusão Git conferidos.
- Dependência direta: openpyxl 3.1.5; transitiva instalada: et-xmlfile 2.0.0. Sem pandas/pytest; testes usam unittest da biblioteca padrão.
- Contrato e diferenças documentados em `docs/data-contract.md` e `docs/data-discovery.md`. Históricos são agregados: não fornecem CNPJ nem permitem reconstruir preços individuais. CSV/ZIP só tem verificação sintética, não homologação de fonte real.
- Nenhuma ingestão definitiva, banco, API, dashboard, ML, download automático ou nuvem implementados. Nenhum raw alterado, Git inicializado ou dado publicado. Marcos 2 a 9 permanecem pendentes.

## Marco 2 — etapas

- [x] **Etapa 1 — validar histórico individual:** CSV real lido integralmente, esquema comparado com as semanas, perfil e contrato atualizados, identificadores conservadores e sobreposições verificados, testes aprovados.
- [x] **Etapa 2 — ingestão local:** manifesto por SHA-256, revisões por período, leitura de CSV/XLSX/ZIP, recorte por `TARGET_UFS` e saída CSV; evidências abaixo.
- [x] **Etapa 3 — descoberta e download:** descoberta pelos links da página da ANP (`--url` como alternativa manual), cliente com timeout e tentativas, `source_url`/`retrieved_at` só com evidência, falha de rede preservando o estado anterior; evidências abaixo.
- [x] Concluir o Marco 2: reexecução sem duplicação, revisão, falha de rede e raw intacto verificados.

### Evidências da etapa 1 — 2026-10-01

- Pasta real: `data/raw/historicos/`; `historical/` não existe. Os dois XLSX dessa pasta são agregados municipais. O novo `Preços semestrais - AUTOMOTIVOS_2026.01.csv` contém observações individuais reais.
- CSV: UTF-8 com BOM, `;`, cabeçalho na linha 1, 16 colunas e 422.418 registros. SP: 117.616 registros, 100 municípios, 2.599 CNPJs, seis produtos, de 01/01 a 30/06/2026. Jundiaí: 1.699 registros e 56 CNPJs, de 07/01 a 30/06/2026.
- Seis duplicatas exatas no arquivo completo, nenhuma em SP. Zero datas e chaves compartilhadas entre o histórico e cada uma das três semanas de setembro; lacunas permanecem entre esses períodos.
- Originais e normalizados separados no relatório. CNPJ/CEP completos com máscara no CSV; recuperar zeros somente de inteiros nativos representáveis nos XLSX. Texto curto/científico/decimal e float são ambíguos e sinalizados. DIESEL histórico permanece distinto de S500, até confirmação semântica.
- Perfil: `.\.venv\Scripts\python.exe scripts/profile_anp_data.py "data/raw/historicos/*.csv" "data/raw/revendas*.xlsx" --output-dir reports/data-profile/historical-validation` → retorno 0, quatro fontes individuais analisadas.
- `.\.venv\Scripts\python.exe -m unittest discover -s tests -v` → **29 testes, OK** (21 anteriores + oito novos). `.\.venv\Scripts\python.exe -m pip check` → **No broken requirements found.** Nenhuma dependência adicionada.
- Trecho independente com `csv.DictReader` confirmou linhas, municípios, CNPJs, período e ausência de chaves repetidas em SP. SHA-256 de 13 arquivos raw (12 fontes + `.gitkeep`) permaneceu idêntico; arquitetura intacta.
- Relatórios novos em `reports/data-profile/historical-validation/`; os relatórios do Marco 1 foram preservados. Resultado e limitações em `docs/data-discovery.md` e contrato versão 0.2 em `docs/data-contract.md`.
- Fontes suficientes para **iniciar** a ingestão local dos formatos validados; cobertura não contínua e ZIP real ainda não recebido (suporte testado sinteticamente). Nenhum extremo removido; nenhuma ingestão definitiva, banco, API, painel, download automático ou nuvem implementados.

### Evidências da etapa 2 — 2026-10-08

- Código novo: `src/radar_combustiveis/config.py`, `src/radar_combustiveis/ingestion/{normalize,readers,manifest,observations,pipeline}.py`, `scripts/ingest_local.py`. O perfil passou a importar de `src`; decisão em [ADR 0001](docs/decisions/0001-manifesto-revisoes-e-saida-csv.md), contrato versão 0.3.
- Refatoração sem regressão: perfil real regenerado depois da mudança é idêntico ao anterior (exceto timestamp e hash do script), e os 29 testes originais seguem passando.
- `.\.venv\Scripts\python.exe -m unittest discover -s tests` → **46 testes, OK** (29 anteriores + 17 novos, fixtures sintéticas). `python -m pip check` → **No broken requirements found.** Nenhuma dependência adicionada.
- `.\.venv\Scripts\python.exe scripts/ingest_local.py` sobre `data/raw` (≈12 s): 12 arquivos raw, 11 conteúdos distintos (o mesmo `mensal-municipios-jan2022-2025.xlsx` existe em `raw/` e `raw/historicos/` e vira uma entrada com duas `paths`); 4 com observações individuais e 7 agregados, apenas registrados.
  - CSV histórico: 422.418 linhas lidas, **117.616 em SP**, 304.802 fora do escopo, 0 rejeitadas, 0 chaves repetidas; 100 municípios, 2.599 CNPJs, 01/01 a 30/06/2026.
  - Semanas: 5.130 + 5.365 + 5.458 = **15.953 em SP** (4.473 + 4.638 + 4.731 = **13.842 automotivas**; 2.111 GLP), 0 rejeitadas, 0 chaves repetidas.
- Conferência independente (`csv.DictReader` e `openpyxl` direto, sem código do projeto) reproduziu 422.418 / 117.616 / 100 municípios / 2.599 CNPJs / 117.616 chaves únicas e 13.842 automotivas + 2.111 GLP.
- Idempotência: a 2ª e a 3ª execução não geraram eventos nem reingestão, não regravaram o manifesto, e as 9 saídas (manifesto, observações, quarentena) ficaram byte a byte idênticas. Revisão, mesmo conteúdo em dois caminhos, troca de `TARGET_UFS`, falha no meio do arquivo sem publicação e esquema desconhecido estão cobertos por testes sintéticos.
- SHA-256 dos 12 arquivos de `data/raw` idêntico ao inventário anterior; `docs/architecture.md` intacta. `data/processed/` e `data/quarantine/` seguem ignorados pelo Git.
- Limitações: nenhuma revisão real da fonte foi observada (só sintética); ZIP real não recebido; lacuna de julho a início de setembro; `DIESEL` continua distinto de S500; nenhuma regra de qualidade nem limpeza (preço zero, produto ou unidade desconhecidos seguem nas observações para o Marco 3); `source_url` e `retrieved_at` são `null`; `period_key` pelo nome do arquivo. (Os dois últimos itens foram tratados na etapa 3; ver abaixo.)

### Evidências da etapa 3 — 2026-10-08

- Código novo: `src/radar_combustiveis/ingestion/download.py`, `scripts/fetch_anp.py`, `apply_provenance` em `manifest.py` e leitura do registro de downloads no `pipeline.py`. Decisões 10 a 15 no adendo do [ADR 0001](docs/decisions/0001-manifesto-revisoes-e-saida-csv.md). Nenhuma dependência adicionada (`urllib`, `html`, `http.server` só nos testes).
- Fonte consultada antes de codificar: o HTML das duas páginas da seção 33 da arquitetura foi baixado e os links extraídos por código, sem confiar em resumo. A página "últimas semanas" traz hrefs absolutos `.../arquivos-lpc/AAAA/revendas_lpc_<início>_<fim>.xlsx` e a data "Atualizado em" por arquivo; as 40 semanas por revenda de 2026 têm nomes regulares. O servidor da ANP responde **403 a HEAD** e 200/206 a GET, com identificação honesta de cliente.
- `.\.venv\Scripts\python.exe -W error::ResourceWarning -m unittest discover -s tests -t .` → **63 testes, OK** (46 anteriores + 17 novos com servidor HTTP local, sem internet). Cobrem: sucesso, retry com espera 2 s e 4 s, falha persistente mantendo o estado, HTTP 404 sem retry, timeout, HTML com status 200, download truncado, limite de tamanho, conteúdo já conhecido, pular URL já obtida, nova data "Atualizado em", destino existente nunca sobrescrito, ponta a ponta com revisão e proveniência, extração de links e CLI. Foi criado `tests/__init__.py`; `python -m unittest discover -s tests` também funciona. `python -m pip check` → **No broken requirements found.**
- Execução real: `scripts/fetch_anp.py --since 2026-06-28 --dry-run` listou 14 semanas; o download real levou 7 s: **11 salvos, 3 idênticos aos recebidos à mão (06/09, 13/09 e 20/09), 0 erros**. A ANP não revisou esses três: os bytes publicados hoje coincidem com os nossos.
- Ingestão sobre os novos arquivos: 11 arquivos, 0 rejeitadas e 0 chaves repetidas por arquivo; 5.245 a 5.544 linhas SP por semana. Total de linhas SP em todas as saídas: **193.111**. Conferência independente com `openpyxl` direto, na semana de 09 a 15/08: 5.391 linhas SP, igual à saída.
- Proveniência no manifesto: os 11 baixados têm `source_url` e `retrieved_at`; os 3 idênticos têm `source_url` e `retrieved_at` nulo; o CSV semestral e os agregados continuam sem URL.
- Idempotência: a 2ª execução de `fetch_anp.py --ingest` ignorou 14 URLs, não baixou nem gravou nada, e as 32 saídas (manifesto, registro de downloads, observações e quarentena) ficaram byte a byte idênticas. `data/raw` ficou com 23 arquivos antes e depois.
- Os 12 arquivos originais de `data/raw` mantêm o mesmo SHA-256 do inventário anterior; os 11 novos ficam em `data/raw/downloads/retrieved_at=2026-10-08T19-25-21Z/`.
- Cobertura: de 01/01 a 02/10/2026, 76 dos 79 dias sem observação em SP são fins de semana. Restam três sextas-feiras sem nenhuma linha (26/06, 24/07 e 04/09), a investigar no Marco 3. *(Marco 3: sem GLP são quatro; 18/09 só tem duas linhas de GLP.)* A lacuna de julho a início de setembro deixou de existir.
- Sobreposição: o CSV semestral e a semana de 28/06 a 04/07 compartilham 3.107 chaves (29 e 30/06); 3.094 com o mesmo preço e **13 com preço diferente**. *(Correção no Marco 3: comparação de texto, `7.30` contra `7.3`; numericamente, as 3.107 coincidem.)* Nada foi deduplicado. A precedência entre fontes precisa ser decidida antes das agregações.
- Limitações: nenhuma revisão real da ANP foi observada (só sintética); a data "Atualizado em" vem da página e uma correção sem mudança dela só seria vista com `--force`; não foram baixadas as semanas de jan a jun (redundantes com o CSV) nem o ZIP semestral oficial (`ca-2026-01.zip`); ZIP real ainda não passou pela ingestão; `DIESEL` segue distinto de S500; sem regras de qualidade (Marco 3).

## Verificação do Marco 3

Concluído em 2026-10-10. Decisões em [ADR 0002](docs/decisions/0002-qualidade-quarentena-e-precedencia.md), contrato versão 0.4.

- Código novo: `src/radar_combustiveis/quality/{rules,pipeline}.py`, `scripts/check_quality.py`, `tests/test_quality.py`. Nenhuma dependência adicionada (Pandera dispensada; só biblioteca padrão). Nenhum arquivo da ingestão foi alterado.
- Medição antes das regras: nos dados reais não há preço zero ou negativo, produto ou unidade desconhecidos, CNPJ ambíguo ou alfanumérico; os 193.111 CNPJs têm dígito verificador válido.
- `.\.venv\Scripts\python.exe -W error::ResourceWarning -m unittest discover -s tests -t .` → **82 testes, OK** (63 anteriores + 19 novos, sintéticos). Cobrem cada motivo de quarentena e aviso, preço canônico, semana, dígito verificador (inclusive o exemplo alfanumérico da Receita), cópias idênticas com `7.3`/`7.30`, conflito, preço implausível × extremo, revisão não atual ignorada, idempotência, as oito regras críticas mantendo a saída anterior, cobertura e códigos de saída do script. `python -m pip check` → **No broken requirements found.**
- Execução real: `scripts/check_quality.py --as-of 2026-10-10` (≈6 s) → **publicar_com_aviso**. 193.111 ingeridas = **180.004 publicadas** + 0 em quarentena + 3.107 cópias idênticas removidas + 10.000 GLP fora do escopo; reconciliado. 1.019 linhas com aviso `preco_extremo`, mantidas.
- Conferência independente (`csv` e `Decimal`, sem o código de qualidade): 180.004 chaves distintas sem GLP, 0 conflitos, staging com chaves únicas, preço igual à origem em todas as linhas, `week_start` sempre domingo e as 3.107 cópias removidas registradas em `duplicate_sources` (todas de 29 e 30/06, mantida a semana).
- Avisos reais: na semana de 27/09, 15 séries com cobertura baixa (Ibitinga com 2 a 3 postos contra mediana de 7 a 8; Marília em gasolina aditivada) e José Bonifácio e Ubatuba ausentes apesar de recorrentes. Dias úteis sem coleta automotiva: 26/06, 24/07, 04/09 e 18/09. Última coleta 02/10 (8 dias).
- Primeira versão revisada com os dados: a cerca 3×IQR em quarentena retirava 1.019 preços plausíveis; passou a aviso, e só preço abaixo da metade ou acima do dobro da mediana da janela vai para a quarentena (nenhum nos dados reais).
- Idempotência: a 2ª execução não regravou nenhuma das quatro saídas (SHA-256 idênticos) e a comparação com a anterior veio vazia. Os 23 arquivos de `data/raw` mantêm o SHA-256 do manifesto.
- `DIESEL` × `DIESEL_S500`: na sobreposição de 29 e 30/06, o `DIESEL` do CSV tem preço idêntico ao `DIESEL S500` da semana em 305 de 305 pares (mesmo posto e dia), contra 9 de 249 para S10.
- Fusão do diesel (decisão do usuário, 2026-10-10): `DIESEL`, `DIESEL S500` e `OLEO DIESEL` → `DIESEL_COMUM`; `DIESEL_S10` separado. A ingestão ganhou `NORMALIZATION_VERSION` (2) e refez as 15 observações a partir do raw; a 2ª execução não reprocessou nada e o raw ficou inalterado. Qualidade depois da fusão: **179.699 publicadas** + 0 quarentena + **3.412** cópias idênticas (3.107 + os 305 pares de diesel, 0 conflitos) + 10.000 GLP; 1.021 avisos `preco_extremo`; demais avisos iguais. `.\.venv\Scripts\python.exe -W error::ResourceWarning -m unittest discover -s tests -t .` → **84 testes, OK** (2 novos: reingestão por versão e chave única do diesel entre fontes).
- Limitações: casos inválidos e falhas críticas exercitados só com dados sintéticos; limites iniciais não homologados; regras de distribuição e redução precisam de histórico (início da série menos protegido); sem banco, testes dbt ou SQL (Marco 4); ZIP real ainda não ingerido.
