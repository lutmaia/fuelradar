# Arquitetura da versão completa — estudo de caso

**Status:** **aprovado pelo usuário em 2026-10-13**, com as restrições do usuário incorporadas em 2026-10-12 (custo zero, só fontes de licença simples, repositório e demonstrativo públicos) e as decisões de protocolo e de hospedagem em 2026-10-13 (seção 15). Não altera [architecture.md](architecture.md), que continua sendo a especificação do produto; este documento acrescenta o estudo, os dados externos, a avaliação contínua e a operação sobre o que os Marcos 0 a 7 já entregam.

## 1. Tese

O produto já responde "quanto custa". O estudo responde a pergunta que faltou:

> **O que o preço do combustível em São Paulo permite prever, e o que não permite?**

O Marco 7 deu o ponto de partida honesto: com a própria história de cada série, nenhum modelo superou "repetir o último valor". A versão completa testa, de forma pré-registrada e em camadas, se outras informações (o que o resto do estado faz, o câmbio, o preço de produtores) mudam essa conclusão. **Qualquer resultado é publicável**, desde que medido sem vazamento e sem busca de parâmetros sobre o teste.

Perguntas do estudo:

| Id | Pergunta | Tipo |
|---|---|---|
| Q1 | Quanto a bandeira branca cobra a menos, no mesmo município, produto e semana? | descritiva/associação |
| Q2 | Como o preço de um posto muda (frequência, tamanho, duração) e as altas são diferentes das quedas? | descritiva |
| Q3 | Reajustes se espalham entre municípios? Quem se move primeiro e com que defasagem? | associação temporal |
| Q4 | Quanto da mudança de preço nas próximas 1 a 4 semanas é previsível, e a partir de que informação? | preditiva |
| Q5 | As previsões publicadas se sustentam depois que o valor real chega? | avaliação prospectiva |

Fora do escopo, por decisão: qualquer inferência sobre qualidade ou adulteração de combustível, notas de terceiros e acusação a postos.

## 2. Princípios

1. **Pré-registro.** Hipóteses, alvos, métricas, janelas e regra de decisão ficam em `docs/estudo/protocolo.md`, em commit **anterior** à primeira execução que as usa.
2. **Teste final lacrado.** Um período reservado só é lido uma vez, por um caminho de código que registra o acesso (seção 6.2).
3. **Camadas com ablação.** Cada fonte de informação entra por vez, e o ganho é atribuído a ela.
4. **Inferência honesta.** Intervalos de confiança por *bootstrap* em blocos de semanas (as séries são dependentes), correção para múltiplas comparações e linguagem de associação, nunca de causa.
5. **Reprodutível.** Cada resultado carrega hash dos dados, hash das fontes externas, commit do código e semente.
6. **Resultado negativo é resultado.** Se nada superar o baseline, esse é o achado, e a documentação diz por quê.
7. **Preserva o que existe.** Brutos intactos, mesma qualidade, mesmo manifesto, mesma regra de mostrar atualidade e amostra.

## 3. Visão de componentes

```
Fontes ANP (semanal) ─┐                       ┌─ Estudo exploratório (Q1–Q3) ── reports/study/
Fontes externas ──────┼─► Ingestão ─► Qualidade ─► PostgreSQL ─┼─ Modelagem v2 (Q4) ──────── model_version / forecast
(câmbio, produtores…) │   manifesto, hash   regras, quarentena │                                       │
                      │                                        └─ Avaliação contínua (Q5) ◄───────────┘
                      │                                                     │
                      └──────────────  API somente leitura  ◄───────────────┘
                                             │
                                          Painel  +  README/relatório
```

Módulos novos em `src/radar_combustiveis/`:

| Pacote | Responsabilidade |
|---|---|
| `external/` | fontes externas: descoberta, download, manifesto, qualidade, alinhamento temporal (*as-of*) |
| `study/` | funções puras das análises Q1–Q3 (modelos de regressão, duração, defasagem), sem I/O |
| `forecasting/` (existente) | ganha `protocol.py` (janelas e lacre), `targets.py`, `layers.py`, `calibration.py`, `inference.py` |
| `live/` | pontuação das previsões quando o real chega, métricas móveis e alertas de degradação |

## 4. Dados

### 4.1 O que já existe e permanece

Observações ANP por posto e semana (801.810 vigentes, 174 semanas, 2022-11 a 2026-10), dimensões, agregações semanais e a lista de arquivos excluídos. Nenhuma mudança de contrato.

### 4.2 Fontes externas

**Política (decidida pelo usuário):** nada pago, nada com chave de API cobrada e nada com licença duvidosa. Só entra fonte que seja dado aberto de governo ou tenha licença aberta explícita; **dúvida é motivo de descarte**, não de investigação. Não há raspagem de site cujos termos a proíbam.

Princípio: **nenhuma fonte entra sem passar pela triagem** da tabela abaixo. Os nomes a seguir são candidatos; o que está marcado "a verificar" não foi confirmado.

| Candidato | Para quê | Situação |
|---|---|---|
| Banco Central — dólar (SGS, série 1) e PTAX (API Olinda) | custo de importação, variação cambial | existe em API aberta; confirmar limites de consulta e janela de 10 anos por requisição |
| ANP — preços de produtores e importadores (semanal) | proxy de custo na ponta da cadeia | página oficial existe; **a verificar** se há arquivo estruturado e a cobertura histórica |
| Reajustes da Petrobras (preço de venda às distribuidoras) | evento que antecede a mudança na bomba | **a verificar** fonte, formato e termos de uso |
| Brent | custo do insumo | **a verificar** fonte aberta com licença clara |
| Etanol anidro (mistura na gasolina) | custo parcial da gasolina | **tende a ser descartado**: indicadores setoriais costumam ter licença restritiva |
| IPCA combustíveis (IBGE/SIDRA) | verificação de sanidade mensal, não preditor | **a verificar** |

**Triagem (gate G2):** licença aberta que permita o uso e a redistribuição dos números derivados; cobertura desde 2022-11; periodicidade semanal ou melhor; formato estável; atraso de publicação conhecido. Fonte que falhar é descartada e a razão é registrada.

### 4.3 Modelo de dados novo (migração `0005`)

```
external_source      (source_id, publisher, url, license, cadence, notes, status)
external_series      (series_id, source_id, name, unit, description)
external_observation (series_id, observed_date, available_at, value, retrieved_at, file_sha256)
forecast_probability (model_version_id, uf, location_id, product_id, origin_week, horizon,
                      p_down, p_flat, p_up)
forecast_evaluation  (model_version_id, uf, location_id, product_id, origin_week, target_week, horizon,
                      predicted, lower, upper, actual, abs_error, in_interval, class_actual, scored_at)
holdout_access       (accessed_at, code_sha, purpose, data_hash, rows)
```

`available_at` é o que impede olhar para o futuro: um valor só pode alimentar uma previsão feita em data posterior a ele. Brutos externos ficam em `data/raw/external/`, com a mesma regra de preservação e hash da ANP.

### 4.4 Qualidade das fontes externas

Mesma disciplina das regras da ANP: formato esperado (colunas, tipos), faixa plausível, lacunas e atraso (defasagem entre `observed_date` e `retrieved_at`), duplicidade e revisão de valores. Falha crítica bloqueia o uso daquela fonte nas features, não o resto do pipeline.

## 5. Estudo exploratório (Q1 a Q3)

Cada análise é uma função pura em `study/`, com figura e conclusão em `reports/study/`, e declara suas limitações.

**Q1 — bandeira branca.** Regressão do log do preço do posto com efeito fixo de município × produto × semana, de modo que a comparação é entre postos do mesmo mercado na mesma semana; erro-padrão agrupado por posto. Robustez: acrescentar prefixo do CEP como proxy de vizinhança. Limitação declarada: a bandeira é a cadastral atual (sem histórico de trocas) e há seleção de quem escolhe ser bandeira branca.

**Q2 — dinâmica do posto.** Fração de posto-semanas com mudança, distribuição do tamanho das mudanças (altas e quedas), duração do preço (análise de sobrevivência, Kaplan–Meier) e assimetria de tamanho e de velocidade. A hipótese "sobe como foguete, cai como pena" só é testada com proxy de custo (camada externa); sem ela, o estudo reporta apenas a assimetria descritiva.

**Q3 — difusão.** Para semanas de alta ou queda estadual relevante, tempo até a mudança de cada município (sobrevivência, por porte); correlação cruzada defasada entre a série de municípios grandes e as dos demais; teste de precedência temporal. Resultado apresentado como mapa de defasagens, com aviso de testes múltiplos e de que precedência não é causa.

**Gate G1:** se Q1 a Q3 não produzirem ao menos dois achados estáveis (que sobrevivem a robustez e a subperíodos), o escopo da modelagem é reavaliado antes de seguir.

## 6. Modelagem v2 (Q4)

### 6.1 Alvos

- **Classe da mudança** em h semanas, com limiar τ = R$ 0,05: *queda* (Δ ≤ −τ), *estável* (|Δ| < τ), *alta* (Δ ≥ τ). Análise de sensibilidade com τ ∈ {0,03; 0,10}.
- **Valor** da mediana em h semanas, com quantis P10, P50 e P90.
- Horizontes 1, 2 e 4 semanas.

### 6.2 Partição temporal e lacre

| Janela | Origens | Uso |
|---|---|---|
| Desenvolvimento | até 2025-06-29 | treino e ajuste |
| Validação | 2025-07-06 a 2026-03-29 | seleção de hiperparâmetros e de limiar |
| **Teste final** | 2026-04-05 em diante | lido **uma única vez**, ao fim do Marco 10 |

As datas são constantes em `forecasting/protocol.py`, versionadas antes da modelagem. O carregador usado por desenvolvimento e validação **não consegue** devolver linhas do teste. O acesso ao teste exige um parâmetro explícito, grava uma linha em `holdout_access` (com o commit e o hash dos dados) e é conferido por teste automatizado. Se o teste for lido mais de uma vez, o relatório declara.

Observação de poder estatístico: o teste final tem em torno de 25 origens semanais. Para o agregado estadual isso é pouco; as conclusões por município usam o conjunto de séries e o *bootstrap* em blocos de semanas, e o relatório informa a largura dos intervalos.

### 6.3 Camadas (ablação)

| Camada | Informação | Modelos |
|---|---|---|
| L0 | nenhuma | persistência; taxa-base da classe por produto e mês; média móvel |
| L1 | própria série | regressão logística multinomial regularizada; LightGBM |
| L2 | + sinais entre séries | variação do estado na semana, fração de municípios que subiram, variação dos municípios líderes (definidos só com dados de treino) |
| L3 | + externas | variação cambial, preço de produtores, evento de reajuste e dias desde o último, conforme a triagem G2 |

Cada camada é comparada com a anterior nos mesmos pontos. Modelos mais simples (L1 linear) entram de propósito: complexidade só passa se ganhar.

### 6.4 Métricas e inferência

- **Classe:** Brier multiclasse (*skill* contra a taxa-base), log-loss, acurácia balanceada, curva de calibração e erro esperado de calibração.
- **Valor:** MAE, WAPE, MASE, perda *pinball* e *skill* contra a persistência.
- **Intervalos:** conformal temporal com cobertura-alvo de 80% e relatório de cobertura por produto e por porte.
- **Desfecho primário (pré-registrado):** *Brier skill score* da classe em h = 2, médio sobre séries elegíveis, contra a taxa-base. Os demais são secundários, com correção de Holm.
- **Incerteza:** *bootstrap* em blocos por semana (B = 2.000) e teste de Diebold–Mariano com erro-padrão robusto para o MAE.

### 6.5 Regra de decisão

Uma camada ou modelo só substitui o publicado se: (a) o limite inferior do IC de 95% do ganho no desfecho primário é maior que zero na **validação**; (b) o ganho se confirma no **teste final**; (c) não piora mais de 5% em produto, porte ou horizonte; (d) a calibração fica dentro da meta; (e) a execução é reprodutível. Caso contrário, o modelo publicado não muda, e isso é relatado.

**Gate G3:** o resultado, positivo ou negativo, é publicado como está.

## 7. Avaliação contínua (Q5)

- **Registro imutável das previsões.** Toda semana, antes de o valor real existir, as previsões são gravadas e um resumo com hash é commitado em `reports/ledger/` (o histórico do Git serve de carimbo de data).
- **Estado fora do banco.** Sem servidor persistente (custo zero), o estado vive no repositório: o registro de previsões em `reports/ledger/` e o histórico de métricas em arquivos pequenos. A execução semanal reconstrói o banco, lê o registro, pontua o que venceu e escreve de volta.
- **Pontuação.** Quando a carga traz a semana-alvo, `live/` preenche `forecast_evaluation` e atualiza métricas móveis (13 e 26 semanas) do modelo publicado e dos baselines.
- **Sem modo sombra** (decisão do usuário, 2026-10-13). Um candidato aprovado pela regra da seção 6.5 (validação e teste final) é publicado sem período de espera; a partir daí, o placar e os alertas de degradação abaixo acompanham seu desempenho ao vivo.
- **Degradação.** Alerta quando o erro móvel passa de um limiar relativo ao do backtest, ou quando a cobertura do intervalo sai da faixa.
- **API e painel:** `GET /api/v1/models/scoreboard` e a página "Desempenho ao vivo", com a série de acertos e erros do publicado contra a persistência. Previsões ainda sem real aparecem como pendentes.

## 8. Produto

| Superfície | Mudança |
|---|---|
| `/forecasts` | acrescenta as probabilidades de queda, estável e alta quando houver modelo de classe aprovado |
| `/models/scoreboard` (novo) | desempenho ao vivo e comparação com os baselines |
| `/metadata/sources` (novo) | fontes externas usadas, licença, última atualização |
| Painel | "Desempenho ao vivo"; página "Estudo" com os achados Q1 a Q3 e suas limitações; probabilidades nas previsões |

**Demonstrativo público.** O painel ganha um *modo instantâneo*: em vez de chamar uma API viva, lê um pacote de arquivos gerado a cada atualização semanal (seção 9). O contrato de dados é o mesmo da API, e o cliente do painel passa a ter duas implementações (HTTP e instantâneo). Em modo público, a razão social só aparece como a ANP a publica como nome fantasia ou bandeira; o CNPJ e razões sociais que possam ser nome de pessoa (microempreendedor individual) ficam fora do pacote.

Linguagem: variações são "incomuns" e "associações"; nenhuma tela fala de fraude, adulteração ou qualidade de combustível.

## 9. Engenharia e operação (custo zero)

**Premissa:** não há servidor pago. A atualização semanal roda no CI gratuito de repositório público, constrói o banco do zero numa execução efêmera e publica um **pacote instantâneo** (arquivos) que o demonstrativo consome.

```
agendamento semanal (GitHub Actions, repositório público)
   ├─ baixa ANP e fontes externas ─► ingere ─► qualidade ─► PostgreSQL efêmero (serviço do job)
   ├─ previsões + pontuação do registro anterior + estudo (se mudou)
   ├─ gera o pacote instantâneo (JSON/Parquet) e o relatório semanal
   └─ publica: pacote como artefato de release; registro e relatórios commitados
                                  │
                       demonstrativo público (hospedagem gratuita) lê o pacote
```

| Tema | Decisão proposta |
|---|---|
| CI | a cada commit: testes com PostgreSQL em contêiner de serviço, migrações, teste do lacre do holdout |
| Execução | `scripts/weekly_refresh.py`: baixar → ingerir → qualidade → carregar → previsões → pontuação → registro → pacote; idempotente, com log estruturado e códigos de saída |
| Agendamento | fluxo semanal do CI; o mesmo script roda na máquina local |
| Contêineres | `Dockerfile` e `docker compose` com perfis `db`, `api`, `dashboard`, `pipeline`: tudo sobe com um comando, para quem quiser reproduzir |
| Demonstrativo | painel em modo instantâneo, em hospedagem **gratuita** que aceite repositório público **Streamlit Community Cloud** (decisão de 2026-10-13); limites e termos a verificar no Marco 12, com Hugging Face Spaces como alternativa se não servir |
| Monitoramento | idade do dado e última execução no próprio pacote; falha do fluxo semanal avisa pelo CI; degradação do modelo vira aviso no painel |
| Segredos | nenhum necessário em produção; qualquer variável fica em *secrets* do CI, nunca no repositório |
| Backup | o banco é reconstruível a partir das fontes e do manifesto; o pacote anterior fica nas releases |
| Segurança | sem API pública (o demonstrativo só lê arquivos); a API continua local, com a restrição de loopback |

**O que isso muda no desenho anterior:** a API HTTP deixa de ser requisito de hospedagem, já que a demonstração lê o pacote; ela permanece como interface do produto local e como contrato. Autenticação por chave, limite de taxa e TLS só passam a importar se algum dia houver API pública.

**Gate G4 (custo e hospedagem), agora com a decisão tomada:** só planos gratuitos. Se nenhum plano gratuito servir o demonstrativo, o fallback é o repositório com vídeo curto e instruções de execução local, sem ficar fora do ar.

**A verificar antes de depender (Marco 12):** (1) se o *site da ANP* aceita o download a partir dos servidores do CI (pode bloquear faixas de IP); (2) limites de tempo, disco e tamanho de artefato do plano gratuito; (3) termos e limites da hospedagem gratuita escolhida; (4) tamanho do pacote instantâneo. Se (1) falhar, o download roda localmente e só o pacote sobe.

## 10. Narrativa e entregáveis finais

- **README** em formato de estudo de caso: problema, achados, o que não funcionou, como reproduzir.
- **Relatório técnico** (protocolo, dados, métodos, resultados, limitações).
- **Cartão do modelo** v2 e **ficha do conjunto de dados** (origem, cobertura, lacunas, vieses).
- **Reprodução em um comando**, com o hash dos dados que reproduz os números do relatório.
- **Vídeo** curto do painel e do placar.

## 11. Marcos propostos

Substituem os antigos Marcos 8 e 9 do [PLAN.md](../PLAN.md); ordem de execução igual à numeração.

| Marco | Entrega | Aceite |
|---|---|---|
| **8 — Protocolo e estudo exploratório** | `protocolo.md` (pré-registro), `study/`, análises Q1–Q3 e figuras | resultados reproduzíveis, limitações escritas, gate G1 |
| **9 — Fontes externas** | triagem, `external/`, migração `0005`, qualidade e alinhamento *as-of* | ao menos uma fonte utilizável e testada, ou descarte documentado (G2) |
| **10 — Modelagem v2** | alvos, camadas, lacre, calibração, inferência, relatório | regra 6.5 aplicada e relatório reproduzível (G3) |
| **11 — Avaliação contínua** | `live/`, registro imutável, placar, alertas | previsões pontuadas automaticamente e verificadas contra cálculo direto |
| **12 — Automação e operação (custo zero)** | CI, `weekly_refresh`, contêineres, pacote instantâneo, modo instantâneo do painel, demonstrativo gratuito | execução semanal sem intervenção, falha injetada detectada, recuperação verificada, demonstrativo no ar sem custo (G4) |
| **13 — Acabamento e narrativa** | README, relatório, ficha do dataset, vídeo | revisão da definição de pronto e reprodução por terceiro verificável |

ADRs previstos: 0008 protocolo do estudo, 0009 fontes externas e alinhamento *as-of*, 0010 modelagem v2, 0011 avaliação contínua, 0012 operação e hospedagem. *Atualização de 2026-10-14:* o demonstrativo foi antecipado e ficou com o 0009 ([pacote instantâneo](decisions/0009-demonstrativo-e-pacote-instantaneo.md)); os previstos passam a usar os números seguintes livres.

## 12. Dependências novas previstas

Justificadas e adicionadas só no marco que as exige:

| Pacote | Marco | Por quê |
|---|---|---|
| `statsmodels` | 8 | regressão com efeitos fixos e erro-padrão agrupado, sobrevivência, Diebold–Mariano |
| `scikit-learn` | 10 | regressão logística, calibração e métricas de classe; o Marco 7 evitou, aqui passa a ser necessário |
| `httpx` (já existe) | 9 | download das fontes externas |

Sem novas dependências no painel: gráficos continuam em Plotly.

## 13. Riscos

| Risco | Efeito | Mitigação |
|---|---|---|
| As variáveis externas não ajudam | conclusão "persistência basta" | é resultado válido; ablação mostra o porquê |
| Fonte sem licença ou sem histórico | camada L3 incompleta | gate G2; descartar com registro |
| Teste final pequeno | intervalos largos | bootstrap em blocos; desfecho primário único; validação prospectiva (Q5) |
| Multiplicidade de testes (Q3) | falsos achados | correção de Holm; reportar o que não sobrevive à robustez |
| Mudança de bandeira ao longo do tempo | viés em Q1 | declarar; robustez por subperíodo |
| Amostra da ANP e lacunas de publicação | cobertura irregular | lacunas explícitas, nunca preenchidas; elegibilidade já existente |
| Correlação lida como causa | conclusão enganosa | linguagem de associação; seção de limitações |
| Reputação (postos nomeados) | risco jurídico | nenhuma tela associa postos a qualidade ou adulteração; modo público sem CNPJ e sem razão social de pessoa física |
| Plano gratuito muda ou some | demonstrativo fora do ar | o pacote e o repositório são autossuficientes; fallback de vídeo e execução local |
| ANP bloqueia o download pelo CI | atualização semanal quebra | download local e envio só do pacote |
| Dado público de postos em repositório público | exposição de pessoa física (MEI) | pacote público sem CNPJ e sem razão social; auditoria de privacidade antes da publicação |

## 14. Definição de pronto da versão completa

1. Q1 a Q5 respondidas, cada uma com método, resultado e limitação, e o desfecho primário relatado como foi.
2. Teste final lido uma vez, com registro de acesso conferível.
3. Todo número do relatório reproduzível a partir do hash dos dados e do commit.
4. Atualização semanal automática, com falha detectada e recuperação demonstrada.
5. Placar ao vivo mostrando acertos e erros do modelo publicado contra a persistência.
6. README que um terceiro consegue seguir do zero ao painel, sem ajuda.

## 15. Decisões tomadas (2026-10-12)

| # | Pergunta | Decisão do usuário | Efeito no desenho |
|---|---|---|---|
| 1 | Hospedagem e orçamento | **Nada pago**, evitar qualquer coisa que custe | seção 9: CI gratuito de repositório público, banco efêmero, pacote instantâneo e hospedagem gratuita; sem servidor persistente |
| 2 | Exposição | **Demonstrativo público, sim** (a plataforma) | modo instantâneo do painel e pacote público, com cuidados de privacidade (seção 8) |
| 3 | Fontes externas | **Sem dor de cabeça de licença**; se não for simples, descartar | política da seção 4.2; etanol anidro tende a sair; Petrobras e Brent só entram com licença clara |
| 4 | Repositório | **Público** (portfólio) | registro de previsões e relatórios commitados; auditoria de segredos e privacidade antes de abrir |
| 5 | Profundidade de Q1 a Q3 | **enxuto por ora** (confirmado em 2026-10-13), ampliável depois | Marco 8 com três análises e limitações |

### Decisões de 2026-10-13

| # | Pergunta | Decisão do usuário | Efeito no desenho |
|---|---|---|---|
| 6 | Partição temporal | **manter** as datas da seção 6.2 | entram no protocolo e em `forecasting/protocol.py` antes de qualquer resultado |
| 7 | Gate G1 | **manter** (dois achados estáveis em Q1 a Q3) | seção 5 sem mudança |
| 8 | Desfecho primário | **aprovado** (Brier skill da classe em h = 2 contra a taxa-base) | seção 6.4 sem mudança |
| 9 | Regra de decisão | **aprovada** | seção 6.5 sem mudança |
| 10 | Modo sombra | **dispensado** | seção 7: candidato aprovado é publicado sem as 8 semanas de espera; placar e alertas continuam |
| 11 | Alvos (τ = R$ 0,05; h = 1, 2 e 4) | não comentado; mantido como proposto | seção 6.1 sem mudança |
| 12 | Hospedagem do demonstrativo | **Streamlit Community Cloud** (Vercel cogitada e descartada, ver abaixo) | seção 9; limites e termos verificados no Marco 12 |
| 13 | Aprovação do desenho | **aprovado** | Marcos 8 a 13 seguem este documento; o Marco 8 começa quando solicitado |

**Por que não a Vercel:** a Vercel serve sites estáticos e funções sem servidor de curta duração; o painel Streamlit precisa de um processo Python sempre ligado com conexão WebSocket, que ela não oferece. Usar a Vercel exigiria reescrever o painel como site estático que lê o pacote instantâneo (outra pilha, outro conjunto de testes). Por isso a escolha foi o **Streamlit Community Cloud** (gratuito para repositório público, roda o painel atual sem reescrita), com o Hugging Face Spaces como alternativa e o vídeo como último recurso (G4).

**Itens que decorrem de o repositório ser público** (situação em 2026-10-13):

1. **Licença do código.** Resolvido: MIT, arquivo `LICENSE`.
2. **Atribuição dos dados.** Resolvido: o README e o rodapé de todas as páginas do painel creditam a ANP e dizem que os números derivados são do projeto; o demonstrativo herda o rodapé.
3. **Higiene antes de abrir.** A auditoria de 2026-10-12 não achou segredos nem arquivos grandes no histórico. Os caminhos locais foram retirados dos arquivos atuais; o guia de outra máquina, que trazia o e-mail pessoal, foi removido (continua no histórico do commit `e9faea4`).
4. **Identidade nos commits.** Decidido em 2026-10-13: manter o e-mail pessoal, ciente de que fica público nos metadados.
