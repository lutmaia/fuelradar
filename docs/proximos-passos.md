# Próximos passos

Notas de retomada do projeto. **Ao começar uma nova sessão de trabalho, leia este arquivo primeiro** e depois o [PLAN.md](../PLAN.md). Atualizado em 2026-10-13 (fim do Marco 8).

## Onde paramos

- **Marcos 0 a 8 concluídos**: ingestão, qualidade, banco, API, painel, previsões, variações incomuns e comparação por bandeira (239 testes aprovados contra o PostgreSQL do Docker).
- **Resultado do Marco 7:** o candidato LightGBM **não foi aprovado** (7,9% pior que "último valor" no MAE ponderado); o baseline "último valor" está publicado. Relatório em `reports/forecasting/backtest.md`, cartão em [model-card.md](model-card.md).
- **Desenho da versão completa** (estudo de caso, marcos 8 a 13) em [estudo-de-caso.md](estudo-de-caso.md), com as decisões do usuário já incorporadas (as de protocolo em 2026-10-13: Q1 a Q3 enxutas, partição da seção 6.2, gate G1, desfecho primário e regra de decisão mantidos, modo sombra dispensado, demonstrativo no Streamlit Community Cloud). **Desenho aprovado em 2026-10-13.**
- **Resultado do Marco 8:** Q1 (bandeira branca −5,6%) é achado estável; Q2 e Q3 não. **Gate G1 não passou** (1 de 3). Resumo em `reports/study/resumo.md`.
- **Marco 8b (descritivo):** etanol × gasolina, economia escolhendo o posto e regiões, em `reports/study/descritivo.md`. No painel desde 2026-10-13: seção *Na hora de abastecer* (município) e veredito do etanol (página inicial).

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

## Marco 8 — protocolo e estudo exploratório (concluído)

1. [x] **Protocolo (2026-10-13):** [docs/estudo/protocolo.md](estudo/protocolo.md), janelas em `forecasting/protocol.py`, [ADR 0008](decisions/0008-protocolo-do-estudo.md) e `tests/test_protocol.py`. **Precisa estar commitado antes da etapa 3**; nenhum resultado foi calculado.
2. [x] **Funções puras em `study/` (2026-10-13):** `common`, `q1`, `q2`, `q3` e `gate`, sem acesso ao banco; `tests/test_study.py` com dados sintéticos de resposta conhecida (efeito plantado recuperado, nenhum efeito onde não há, lacre do teste final, cobertura do IC agrupado, Kaplan–Meier e log-rank iguais aos do scipy). Sem `statsmodels`: `scipy` (já instalado) passou a dependência direta. Detalhes de implementação que o texto não fixava estão na tabela de desvios do protocolo, todos **antes** de resultados. Ainda não rodou sobre dados reais.
3. [x] **Execução real (2026-10-13):** `scripts/run_study.py` sobre 2022-11-13 a 2026-03-29, relatórios reproduzíveis em `reports/study/`, conferência independente em SQL; ver "Verificação do Marco 8" no PLAN.

## Ordem decidida (2026-10-13), pensando em portfólio

1. [x] **Páginas Regiões e Estudo** no painel (parte do Marco 9 que não depende de fonte externa). **Feito em 2026-10-14:** endpoints `/prices/regions` e `/prices/rankings`, regiões em `regions.py` (as mesmas listas do estudo), página Estudo lendo `reports/study/*.json` (ADR 0005, adendo). 309 testes aprovados contra o PostgreSQL do Docker (16 novos); medianas regionais, economia de Araraquara e etanol de Adamantina recalculados em SQL direto no fato e iguais; as duas páginas fotografadas no Edge headless, com três defeitos visuais corrigidos ("None" na tabela, capital e metropolitana com azuis parecidos, rótulo cortado). O Marco 9 continua aberto: faltam as fontes externas.
2. **Demonstrativo online e README contando a história**: adianta parte dos Marcos 12 (hospedagem no Streamlit Community Cloud, pacote instantâneo) e 13 (README de estudo de caso: problema, três achados, um gráfico, link da demo).
3. **Fontes externas** (resto do Marco 9: dólar do Banco Central e preço de produtores da ANP), depois o Marco 10.

Motivo: hoje ninguém consegue ver o projeto sem instalar tudo; a demo e um README curto valem mais para quem avalia do que uma análise nova. O guia de estudo das escolhas de método (para entrevistas) **fica fora do repositório**, por decisão do usuário em 2026-10-14.

Defeito antigo visto na conferência de 2026-10-14, ainda não corrigido: a linha de referência de *Comparar municípios* mostra "None" onde deveria haver "—" (o `st.dataframe` ignora o `na_rep` do `Styler`).

## Próximas decisões

- [ ] **Reavaliar o escopo do Marco 10** (G1 não passou). Pelo protocolo, decidir com o usuário antes de seguir: por exemplo, manter a modelagem v2 como desenhada, reduzi-la ou trocar a camada L2 (que dependia de líderes de Q3, achado não estável).
- [ ] **Marco 9 (fontes externas e páginas de comparação)** começa pela triagem de licença do dólar (Banco Central) e do preço de produtores (ANP); independe do G1. Inclui, a pedido do usuário, as páginas **Regiões** (dados atuais, rankings) e **Estudo** (achados congelados) no painel.

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
