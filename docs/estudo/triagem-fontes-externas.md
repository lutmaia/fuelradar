# Triagem das fontes externas (gate G2, Marco 9)

Triagem feita em 2026-10-14, antes de qualquer código de ingestão, pelos critérios da [seção 4.2 do desenho](../estudo-de-caso.md): licença que permita usar e redistribuir os números derivados, cobertura desde 2022-11, periodicidade semanal ou melhor, formato estável e atraso de publicação conhecido. Política do usuário: dado aberto de governo ou licença aberta explícita; **dúvida é motivo de descarte**.

Os arquivos baixados para a triagem ficaram fora do repositório (pasta temporária). Nada foi ingerido.

## Atualização de 2026-10-15: termos de uso da ANP e preços de distribuição

A pedido do usuário, revista a página geral de preços da ANP (`gov.br/anp/.../precos-e-defesa-da-concorrencia/precos`). Duas descobertas:

1. **Os termos de uso do portal da ANP são explícitos** ("Termos de uso do portal da ANP"): *"É autorizada a reprodução total ou parcial, sem fins lucrativos, do conteúdo, mediante a citação obrigatória da fonte de forma clara e visível, de preferência com link (endereço eletrônico) que remeta às informações originais do conteúdo reproduzido no site da Agência."* O uso *"com finalidade comercial de venda de serviços"* é proibido. Isso vale para todo o conteúdo do portal, **inclusive o levantamento de preços nos postos que o projeto já usa**. O projeto é sem fins lucrativos; falta o rodapé do painel trazer o link da fonte. A dúvida de licença dos preços de produtores deixa de existir: eles têm os mesmos termos da fonte principal.
2. **Preços de distribuição de combustíveis** (página própria, arquivos `.xlsx` em `.../precos/pdc/semanal/`): preço médio ponderado por volume que as distribuidoras cobram, com tributos e frete, **por estado e por município** (459 municípios no Brasil). Medido nos arquivos baixados em 2026-10-15:
   - **Produtos:** gasolina C comum e aditivada, **etanol hidratado**, diesel B S10 e S500, os mesmos da pesquisa nos postos.
   - **Semana:** domingo a sábado, a mesma da pesquisa nos postos (sem ajuste de calendário).
   - **São Paulo (estado):** os cinco produtos com 198 semanas consecutivas de 13/11/2022 a 23/08/2026, sem lacuna.
   - **Municípios de SP:** 108, os mesmos da nossa base, nos cinco produtos; o arquivo desde 2024 tem 139 semanas de linhas por município (há células `-` sem preço, não contadas). Há outro arquivo de ago/2020 a dez/2023, não medido.
   - **Atraso:** a semana mais recente era a de 23/08/2026 num arquivo atualizado em 21/09/2026; a ANP diz atualizar até o último dia útil do mês seguinte. Para prever 1 a 4 semanas à frente, o dado disponível na data da previsão tem cerca de 5 a 9 semanas.
   - Médias truncadas (até 25% das observações descartadas em cada extremo) e dados declarados pelos agentes regulados.

**Consequência para o ODbL do dólar:** a ODbL exige que um banco de dados derivado publicado fique sob ODbL, que permite uso comercial; os dados da ANP não permitem. Para não misturar as duas condições, a série do dólar não deve entrar no pacote público do demonstrativo; números e gráficos calculados com ela podem ser exibidos com o crédito ao BCB.

## Decisões do usuário (2026-10-15)

- **Produtores e distribuição entram**, nos termos de uso da ANP. Produtores como sinal de custo (camada L3 do Marco 10, pelo menor atraso); distribuição para medir quanto o posto cobra acima da distribuidora, por município e por posto.
- **Dólar entra** como fonte, **fora do pacote público** do demonstrativo (por causa da ODbL); números e gráficos derivados mostram o crédito ao BCB.
- Envio ao GitHub adiado a pedido do usuário.

## Resumo (2026-10-14)

| Fonte | Acesso | Licença | Cobertura | Situação |
|---|---|---|---|---|
| Dólar comercial, venda (BCB, SGS série 1) | API JSON aberta, sem chave | **ODbL**, declarada na ficha do portal de dados abertos do BCB | diária, 991 cotações de 01/11/2022 a 13/10/2026 | **aprovada** |
| Preços médios ponderados de produtores e importadores (ANP) | planilha `.xls` oficial, atualizada semanalmente | **não declarada** em nenhuma página encontrada | semanal, 204 semanas sem lacuna desde 11/2022 (gasolina A, diesel S-10 e S-500) | **aguarda decisão do usuário** |
| Preços de distribuição (ANP), *visto em 2026-10-15* | planilhas `.xlsx` oficiais | termos do portal da ANP: sem fins lucrativos, com citação e link | semanal, SP e 108 municípios, 5 produtos com etanol; atraso de 5 a 9 semanas | **candidata** (decisão do usuário) |
| Preço do etanol na usina | não há na publicação da ANP (só derivados de petróleo e biodiesel) | indicador CEPEA/Esalq tem licença restritiva | — | **descartada** pela política (já prevista no desenho) |
| Paridade de importação (PPI) publicada pela ANP | página da ANP | dados fornecidos pela S&P Global (terceiro) | — | **descartada**: licença de terceiro, dúvida |

## Dólar (Banco Central)

- **Endereço:** `https://api.bcb.gov.br/dados/serie/bcdata.sgs.1/dados?formato=json&dataInicial=dd/mm/aaaa&dataFinal=dd/mm/aaaa`. Testado: HTTP 200, 991 registros (`{"data": "01/11/2022", "valor": "5.1500"}` a `{"data": "13/10/2026", "valor": "5.0096"}`).
- **Licença:** Open Data Commons Open Database License (ODbL), conforme os metadados do conjunto `1-taxa-de-cambio---livre---dolar-americano-venda---diario` na API do portal `dadosabertos.bcb.gov.br`. Obriga a citar a fonte e, se um banco de dados derivado for publicado (por exemplo, o pacote do demonstrativo com o dólar), a mantê-lo sob ODbL. Gráficos e números exibidos só pedem o crédito.
- **Cuidados de implementação:** a cotação é diária (média semanal no alinhamento); a API recusa janelas acima de 10 anos em séries diárias (relato de terceiros, não de documento oficial); uma segunda chamada seguida voltou vazia uma vez, então o download precisa de nova tentativa e de conferência do conteúdo.

## Preços de produtores e importadores (ANP)

- **Endereço:** página "Preços de produtores e importadores de derivados de petróleo" no gov.br/anp; planilha `ppidp/precos-medios-ponderados-semanais-2013.xls` (de 2013 em diante; há outra de 2002 a 2012). Baixada em 2026-10-14: 2 MB, última semana de 28/09 a 04/10/2026, salva pela ANP em 09/10/2026.
- **Estrutura:** uma planilha, 11.544 linhas; colunas produto, início e fim da semana (segunda a domingo), Norte, Nordeste, Centro-Oeste, Sul, Sudeste e Brasil. Preços sem ICMS. `***` marca região sem valor. Notas metodológicas no fim da planilha.
- **Cobertura desde 2022-11:** Gasolina A Comum, Óleo Diesel S-10 e Óleo Diesel S-500 com 204 semanas consecutivas, sem lacuna e com valor numérico no Sudeste. Biodiesel B-100 também completo. Diesel não rodoviário tem lacunas e não tem Sudeste.
- **Limites para o projeto:** não há valor por estado (o mais próximo de SP é o Sudeste); não há etanol; a semana começa na segunda e a da pesquisa nos postos no domingo (resolvido pelo alinhamento *as-of*); a ANP estima publicar cerca de 12 dias após a semana, e a planilha é sobrescrita a cada atualização (cada download precisa ser guardado intacto); o formato `.xls` antigo exige uma dependência nova para leitura (`xlrd`).
- **Licença:** não encontrada. A página da série não menciona licença; a página de dados abertos da ANP também não; o Plano de Dados Abertos 2026–2028 é um PDF de imagens que não foi possível ler. Indício indireto: um catálogo de terceiros (`data.amerigeoss.org`) lista a série de preços nos postos da ANP, já usada pelo projeto, como Creative Commons com atribuição. A publicação é obrigação legal da ANP (Portaria ANP nº 297/2001), do mesmo órgão e com o mesmo status da fonte principal.

### Decisão pendente

Opções apresentadas ao usuário em 2026-10-14 (a primeira reforçada pelos termos de uso encontrados em 2026-10-15):

1. **Aceitar** como dado aberto de governo, com crédito à ANP, igual à fonte principal (sugestão registrada).
2. **Perguntar à ANP** (faleconosco@anp.gov.br) e só usar depois da resposta.
3. **Descartar** pela regra da dúvida; o Marco 9 segue só com o dólar.

## Fontes consultadas

- Ficha da série 1 no portal de dados abertos do BCB: <https://dadosabertos.bcb.gov.br/dataset/1-taxa-de-cambio---livre---dolar-americano-venda---diario>
- Limites da API do SGS (relato de terceiros): <https://www.tabnews.com.br/SidneyBissoli/series-do-banco-central-como-consultar-o-sgs-a-focus-e-a-ptax-sem-cair-nas-armadilhas>
- Página da ANP de preços de produtores e importadores: <https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/precos/precos-de-produtores-e-importadores-de-derivados-de-petroleo>
- Dados abertos da ANP: <https://www.gov.br/anp/pt-br/acesso-a-informacao/dados-abertos>
- Metadados do Anuário da ANP (tabela 2.41, produtores e importadores de gasolina A): <https://www.gov.br/anp/pt-br/centrais-de-conteudo/dados-abertos/arquivos/anuario-estatistico-2023/secao-2/metadados/tabela2-41.pdf>
- Espelho da série de preços nos postos da ANP em catálogo de terceiros: <https://data.amerigeoss.org/dataset/serie-historica-de-precos-de-combustiveis-por-revenda/resource/5352f0b9-8dbb-4278-9f1a-8f255d8c09b0>
