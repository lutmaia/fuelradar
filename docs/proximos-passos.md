# Próximos passos

Notas de retomada do projeto. **Ao começar uma nova sessão de trabalho, leia este arquivo primeiro** e depois o [PLAN.md](../PLAN.md). Atualizado em 2026-10-12.

## Onde paramos

- **Marcos 0 a 7 concluídos e commitados**: ingestão, qualidade, banco, API, painel, previsões, variações incomuns e comparação por bandeira (239 testes aprovados contra o PostgreSQL do Docker).
- **Resultado do Marco 7:** o candidato LightGBM **não foi aprovado** (7,9% pior que "último valor" no MAE ponderado); o baseline "último valor" está publicado. Relatório em `reports/forecasting/backtest.md`, cartão em [model-card.md](model-card.md).
- **Desenho da versão completa** (estudo de caso, marcos 8 a 13) em [estudo-de-caso.md](estudo-de-caso.md), com as decisões do usuário já incorporadas. O Marco 8 **ainda não começou**.

## Decisões já tomadas (não reabrir sem motivo)

1. **Custo zero:** nada pago. Atualização semanal no CI gratuito de repositório público, banco efêmero e pacote instantâneo; hospedagem só em plano gratuito.
2. **Fontes externas só com licença simples**; dúvida significa descartar.
3. **Demonstrativo público: sim.** Em modo público não vão CNPJ nem razão social.
4. **Repositório público**, para portfólio. Licença **MIT** (arquivo `LICENSE`).
5. **Estudo enxuto:** três análises (Q1 a Q3), ampliável depois.
6. **Sem acusação a postos:** nenhuma tela associa postos a qualidade ou adulteração.

## Pendências imediatas

- [ ] **Decidir a identidade dos commits:** manter o e-mail pessoal ou passar a usar o e-mail "noreply" do GitHub (o histórico antigo não será reescrito).
- [ ] **Atribuição à ANP também no painel** (rodapé), além do README.
- [ ] **Regenerar o perfil dos dados** (`scripts/profile_anp_data.py`) com caminhos relativos, se for refeito: os relatórios commitados foram higienizados à mão.
- [ ] **Conferir o que ficou público:** olhar o repositório no GitHub depois do push (README renderizado, nada de caminho local).

## Próximo marco: 8 — protocolo e estudo exploratório

Antes de qualquer análise:

1. Escrever `docs/estudo/protocolo.md` (hipóteses, métricas, janelas e regra de decisão) e **commitar antes de rodar resultados**.
2. Fixar as datas de desenvolvimento, validação e teste final (seção 6.2 do desenho) em código.
3. Só então implementar as análises Q1 (bandeira branca), Q2 (dinâmica) e Q3 (difusão).

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

## Como colocar tudo de pé em outro computador

Veja [continuar-em-outra-maquina.md](continuar-em-outra-maquina.md).
