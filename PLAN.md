# Plano de desenvolvimento

A [arquitetura](docs/architecture.md) é a especificação principal. Este plano divide sua execução em marcos menores conforme o escopo solicitado, sem alterar o documento. A numeração começa em 0. Cada conclusão exige evidência; não confundir documentação com funcionalidade executada.

- [x] **Marco 0 — Fundação:** documentação, estrutura Python e dados, configuração mínima e proteção no Git. Aceite: conferir estrutura, sintaxe TOML/Python, regras de exclusão e integridade da arquitetura.
- [x] **Marco 1 — Descoberta e contrato dos dados:** nove XLSX reais (históricos agregados e semanas por revenda/resumos), 21 planilhas analisadas; esquema, formatos, cobertura, produtos e qualidade registrados; contrato proposto, perfil reproduzível e 21 testes aprovados. Histórico individual CSV/ZIP não recebido: validar esse formato antes de implementar seu ramo de ingestão.
- [ ] **Marco 2 — Ingestão histórica e semanal:** download, manifesto, checksum, versões e rastreabilidade; preservar raw nacional e selecionar SP nas saídas derivadas. Aceite: reexecução sem duplicação e revisão de fonte verificadas em arquivos locais, sem antecipar o banco.
- [ ] **Marco 3 — Qualidade e normalização:** padronizar campos, validar regras e preservar suspeitos em quarentena. Aceite: casos válidos, inválidos e falhas críticas exercitados e contagens reconciliadas.
- [ ] **Marco 4 — Banco de dados:** implementar PostgreSQL, migrações, dimensões, fatos e agregações. Aceite: carga, integridade, revisão e consultas verificadas em banco real de teste.
- [ ] **Marco 5 — API:** consultas de leitura com filtros, paginação, atualidade e cobertura SP. Aceite: contratos, respostas, erros e limite de UF testados.
- [ ] **Marco 6 — Dashboard:** exploração, comparações, histórico, postos e metodologia. Aceite: jornadas verificadas contra API e dados reais, com datas e amostra visíveis.
- [ ] **Marco 7 — Baselines e machine learning:** modelos de referência simples, validação temporal, candidato e intervalos. Aceite: relatório reproduzível e decisão de aprovação ou manutenção do baseline, sem inventar ganho.
- [ ] **Marco 8 — Automação, monitoramento e deploy:** agendamento, CI/CD, contêineres, monitoramento e implantação progressiva. Aceite: execução automática, alertas, recuperação, segredos e custos verificados.
- [ ] **Marco 9 — Acabamento para portfólio:** documentação de reprodução, demonstração, métricas e limitações. Aceite: revisão da definição de pronto da arquitetura e demonstração verificável.

## Limite da tarefa atual

Marco 2, etapa 2: ingestão local concluída em 2026-10-08. Parar aqui: sem download, descoberta de links, banco, API ou painel. O Marco 2 continua aberto até a etapa 3 (descoberta e download com tratamento de falha de rede). Agregados municipais e regionais não são inseridos na tabela de observações individuais.

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
- [ ] **Etapa 3 — descoberta e download:** manifesto de URLs, cliente com timeout e tentativas, `source_url`/`retrieved_at` com evidência, falha de rede preservando o estado anterior.
- [ ] Concluir o Marco 2: idempotência e revisão já verificadas localmente; faltam as falhas de rede e a verificação do download real.

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
- Limitações: nenhuma revisão real da fonte foi observada (só sintética); ZIP real não recebido; lacuna de julho a início de setembro; `DIESEL` continua distinto de S500; nenhuma regra de qualidade nem limpeza (preço zero, produto ou unidade desconhecidos seguem nas observações para o Marco 3); `source_url` e `retrieved_at` são `null`; `period_key` pelo nome do arquivo.
