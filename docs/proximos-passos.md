# Próximos passos

Notas de retomada do projeto. **Ao começar uma nova sessão de trabalho, leia este arquivo primeiro** e depois o [PLAN.md](../PLAN.md). Atualizado em 2026-10-13.

## Onde paramos

- **Marcos 0 a 7 concluídos e commitados**: ingestão, qualidade, banco, API, painel, previsões, variações incomuns e comparação por bandeira (239 testes aprovados contra o PostgreSQL do Docker).
- **Resultado do Marco 7:** o candidato LightGBM **não foi aprovado** (7,9% pior que "último valor" no MAE ponderado); o baseline "último valor" está publicado. Relatório em `reports/forecasting/backtest.md`, cartão em [model-card.md](model-card.md).
- **Desenho da versão completa** (estudo de caso, marcos 8 a 13) em [estudo-de-caso.md](estudo-de-caso.md), com as decisões do usuário já incorporadas (as de protocolo em 2026-10-13: Q1 a Q3 enxutas, partição da seção 6.2, gate G1, desfecho primário e regra de decisão mantidos, modo sombra dispensado, demonstrativo no Streamlit Community Cloud). **Desenho aprovado em 2026-10-13.** O Marco 8 **começou** (etapa 1 de 3 feita; ver abaixo).

## Decisões já tomadas (não reabrir sem motivo)

1. **Custo zero:** nada pago. Atualização semanal no CI gratuito de repositório público, banco efêmero e pacote instantâneo; hospedagem só em plano gratuito.
2. **Fontes externas só com licença simples**; dúvida significa descartar.
3. **Demonstrativo público: sim.** Em modo público não vão CNPJ nem razão social.
4. **Repositório público**, para portfólio. Licença **MIT** (arquivo `LICENSE`).
5. **Estudo enxuto:** três análises (Q1 a Q3), ampliável depois.
6. **Sem acusação a postos:** nenhuma tela associa postos a qualidade ou adulteração.

## Pendências imediatas

- [x] **Identidade dos commits:** decidido em 2026-10-13 manter o e-mail pessoal; o histórico não será reescrito.
- [x] **Atribuição à ANP no painel:** rodapé em todas as páginas, inclusive quando a API falha (2026-10-13, teste novo; 240 testes aprovados contra o PostgreSQL do Docker).
- [ ] **Regenerar o perfil dos dados** (`scripts/profile_anp_data.py`) com caminhos relativos, se for refeito: os relatórios commitados foram higienizados à mão.
- [x] **Conferir o que ficou público:** repositório conferido pelo usuário no GitHub em 2026-10-13.

## Marco 8 em andamento — protocolo e estudo exploratório

1. [x] **Protocolo (2026-10-13):** [docs/estudo/protocolo.md](estudo/protocolo.md), janelas em `forecasting/protocol.py`, [ADR 0008](decisions/0008-protocolo-do-estudo.md) e `tests/test_protocol.py`. **Precisa estar commitado antes da etapa 3**; nenhum resultado foi calculado.
2. [ ] **Funções puras em `study/`** para Q1 a Q3, testadas com dados sintéticos de resposta conhecida; justificar e adicionar `statsmodels` se necessário.
3. [ ] **Execução real** (`scripts/run_study.py`) só sobre 2022-11-13 a 2026-03-29, relatórios em `reports/study/`, gate G1 e limitações; então atualizar o `PLAN.md`.

O Marco 9 (fontes externas) começa pela triagem de licença e cobertura; fonte que falhar é descartada com o motivo registrado.

## A verificar mais adiante (Marco 12)

- Se o site da ANP aceita download a partir dos servidores do CI.
- Limites e termos dos planos gratuitos de CI e de hospedagem do demonstrativo.
- Tamanho do pacote instantâneo.

## Preferências de trabalho do projeto

- **Commits:** manter o trailer `Co-Authored-By` nas mensagens; não reescrever histórico.
- **Banco:** somente Docker Compose (PostgreSQL 16), sempre por `127.0.0.1` (nunca `localhost`).
- **Escopo:** uma tarefa por marco solicitado; não avançar automaticamente (veja [AGENTS.md](../AGENTS.md)).
- **Dados brutos da ANP:** nunca editar, apagar nem enviar ao GitHub.
- **Resultados:** diferenciar o que foi verificado do que é hipótese; não inventar ganho.

## Como colocar tudo de pé

Instalação no [README](../README.md). Com o ambiente pronto e o `.env` criado, `.\iniciar.ps1` sobe o PostgreSQL do Docker, a API e o painel.
