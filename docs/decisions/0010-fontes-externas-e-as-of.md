# 0010 — Fontes externas, disponibilidade (*as-of*) e margem bruta de revenda

- **Status:** aceita (Marco 9, 2026-10-15)
- **Contexto:** o [desenho](../estudo-de-caso.md) (seção 4) prevê fontes externas para a camada L3 da modelagem, sem olhar para o futuro. A [triagem](../estudo/triagem-fontes-externas.md) aprovou o dólar do BCB e os preços de produtores e de distribuição da ANP; o usuário decidiu usar as três e mostrar quanto o preço nos postos fica acima da distribuição.

## Decisão

1. **Três fontes, um formato.** `src/radar_combustiveis/external/` baixa (com o cliente da ingestão da ANP: tentativas, limite de tamanho), guarda os brutos intactos em `data/raw/external/<fonte>/retrieved_at=<instante>/` (nunca sobrescreve; conteúdo repetido não é guardado de novo), lê, confere e carrega. Todas as linhas viram `external_observation` (migração `0005`): fonte, produto, nível geográfico (`pais`, `regiao`, `uf`, `municipio`), local, período, valor, `available_at`, primeiro e último download e o SHA-256 do arquivo.
2. **`available_at` pela regra publicada de cada fonte**, sem histórico real de publicação: dólar no dia seguinte à cotação; produtores 12 dias após o fim da semana (estimativa da ANP); distribuição no último dia do mês seguinte (prazo da ANP). Se o projeto baixou o valor antes desse prazo, vale o dia do download. `external/asof.py` devolve o valor já disponível no sábado da semana de origem de uma previsão. Isso é o que o Marco 10 vai usar.
3. **Qualidade por fonte** (desenho, 4.4): crítico (nenhuma linha, chave repetida, valor fora da faixa plausível, período incoerente) bloqueia só aquela fonte; lacunas semanais e atraso acima do esperado são avisos. Relatório em `data/processed/external/quality.json`.
4. **Revisões:** a carga é idempotente; um valor que muda num download posterior é atualizado e marcado `revised`, sem mudar `first_retrieved_at` nem `available_at`.
5. **Margem bruta de revenda** = mediana da pesquisa nos postos − preço médio de distribuição da ANP, no estado ou município e na mesma semana (as duas usam domingo a sábado). Endpoints `/prices/margins`, `/prices/margins/municipalities` e `/prices/margins/stations`, página *Margem dos postos*. Por posto, o número é o preço do posto na semana menos a **média** do município, chamado de **margem bruta estimada**; o texto é neutro ("segundo os dados da ANP, a margem bruta estimada é de…"), diz que não é lucro e que o custo real de cada posto não é público (decisão do usuário, 2026-10-15).
6. **Licenças.** Os termos de uso do portal da ANP autorizam reprodução sem fins lucrativos com citação e link; o rodapé do painel passou a trazer os dois links. O dólar (ODbL) entra no banco, mas **não** no pacote público do demonstrativo, para não publicar um banco derivado que misture ODbL com dados da ANP sem fins lucrativos.
7. **Dependência nova:** `xlrd==2.0.2`, só para a planilha `.xls` de produtores (o `openpyxl` não lê o formato antigo).

## Alternativas consideradas

- **Só a distribuição** (sem `.xls` nem dependência nova): perderia o sinal de custo com menor atraso, que é o útil para prever 1 a 4 semanas.
- **Tabela por fonte:** mais colunas específicas, mas três cargas e três conjuntos de consultas para o mesmo tipo de dado (série com período e local).
- **`available_at` pela data de download apenas:** o histórico inteiro pareceria publicado no dia do primeiro download e o *as-of* seria inútil para o passado.
- **Margem por posto com o nome "lucro":** descartado; o custo de cada posto não é conhecido e a despesa operacional não está descontada.

## Consequências e limitações

- A regra de disponibilidade é uma aproximação do calendário real da ANP; se a ANP atrasar mais que o próprio prazo, o *as-of* do passado será otimista nesses casos.
- A distribuição chega com 5 a 9 semanas de atraso; a margem mais recente é sempre de semanas atrás, e a página diz qual.
- A média de distribuição é ponderada por volume e truncada pela ANP; a mediana dos postos é da amostra da pesquisa. A diferença entre as duas não é a margem de um posto específico.
- Linhas que deixam de aparecer na fonte não são apagadas; valores revisados guardam só a versão mais recente.
- Os preços de produtores são do Sudeste (não há valor por estado) e não incluem etanol.
