# Triagem das fontes externas (gate G2, Marco 9)

Triagem feita em 2026-10-14, antes de qualquer código de ingestão, pelos critérios da [seção 4.2 do desenho](../estudo-de-caso.md): licença que permita usar e redistribuir os números derivados, cobertura desde 2022-11, periodicidade semanal ou melhor, formato estável e atraso de publicação conhecido. Política do usuário: dado aberto de governo ou licença aberta explícita; **dúvida é motivo de descarte**.

Os arquivos baixados para a triagem ficaram fora do repositório (pasta temporária). Nada foi ingerido.

## Resumo

| Fonte | Acesso | Licença | Cobertura | Situação |
|---|---|---|---|---|
| Dólar comercial, venda (BCB, SGS série 1) | API JSON aberta, sem chave | **ODbL**, declarada na ficha do portal de dados abertos do BCB | diária, 991 cotações de 01/11/2022 a 13/10/2026 | **aprovada** |
| Preços médios ponderados de produtores e importadores (ANP) | planilha `.xls` oficial, atualizada semanalmente | **não declarada** em nenhuma página encontrada | semanal, 204 semanas sem lacuna desde 11/2022 (gasolina A, diesel S-10 e S-500) | **aguarda decisão do usuário** |
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

Opções apresentadas ao usuário em 2026-10-14:

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
