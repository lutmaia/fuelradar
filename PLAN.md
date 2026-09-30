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

Marco 1 concluído para os formatos reais recebidos. Parar aqui. Próximo passo, em nova tarefa: Marco 2 — ingestão histórica e semanal. Obter manualmente uma amostra histórica por revenda antes de implementar esse ramo; os mensais atuais não substituem observações individuais.

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
