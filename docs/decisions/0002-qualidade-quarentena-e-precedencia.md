# 0002 — Qualidade, quarentena e precedência entre fontes

- **Status:** aceita (Marco 3, 2026-10-10)
- **Contexto:** a seção 12 da [arquitetura](../architecture.md) define regras críticas, de linha e de cobertura e um relatório por execução. A ingestão ([ADR 0001](0001-manifesto-revisoes-e-saida-csv.md)) grava uma saída por versão de arquivo, sem deduplicar nem julgar valores. O CSV semestral e a semana de 28/06 a 04/07 compartilham 3.107 chaves.

## Decisão

1. **A qualidade lê só as saídas da ingestão** (manifesto e `observations/` das revisões com `is_current`) e nunca abre `data/raw`. `scripts/check_quality.py` roda depois de `ingest_local.py`/`fetch_anp.py`.
2. **Falha crítica bloqueia a publicação inteira** e mantém a saída anterior: as saídas são escritas em arquivos temporários e só substituídas no fim, se a decisão não for `bloquear`. Regras: arquivo não ingerido, colunas diferentes do contrato, arquivo vazio, nenhuma data no período do nome, nenhum preço válido, duplicação causada pela carga (posição repetida ou contagem diferente do manifesto), redução abaixo de 50% da mediana das até oito semanas anteriores (com pelo menos três) e contagens não reconciliadas.
3. **Quarentena por linha** (`data/quarantine/quality_observations.csv`, com `quality_reasons`): preço ausente ou não positivo, data inválida, futura ou fora do período do arquivo, UF ou município ausente, CNPJ ausente, malformado ou com dígito verificador inválido, produto ou unidade desconhecidos, unidade incompatível com o produto, conflito de preço na mesma chave e preço implausível.
4. **Preço extremo é marcado, não excluído.** Por produto e unidade, numa janela de nove semanas (a da coleta e as oito anteriores, com pelo menos 30 preços): fora de `[Q1 − 3×IQR, Q3 + 3×IQR]` gera o aviso `preco_extremo` e a linha continua publicada; abaixo de metade ou acima do dobro da mediana vai para a quarentena como `preco_implausivel` (erro de digitação ou de unidade). A primeira versão colocava a cerca IQR em quarentena e retirou 1.019 linhas plausíveis (por exemplo, gasolina a R$ 7,49 em uma semana de mediana R$ 6,39), contrariando "um preço raro pode ser verdadeiro".
5. **Precedência entre fontes:** mesma chave (`uf|município|cnpj|produto|unidade|data`) com preços numericamente iguais mantém uma cópia, a do arquivo de período mais curto (a semana publicada, que tem URL de origem), e registra as demais em `duplicate_sources`. Preços diferentes mandam todas as cópias para a quarentena (`conflito_de_preco_mesma_chave`), sem escolher um vencedor.
6. **Preços comparados como número, não texto.** As "13 chaves com preço diferente" registradas no Marco 2 eram `7.30` contra `7.3`; numericamente, as 3.107 chaves coincidem. A saída usa uma forma canônica sem arredondamento (`7.30`, `5.999`).
7. **GLP fica fora da publicação** (MVP automotivo), contado como `rows_out_of_scope_product`; continua nas observações da ingestão.
8. **`DIESEL` e `DIESEL S500` são `DIESEL_COMUM`; `DIESEL_S10` fica separado.** Decidido em 2026-10-10. Na sobreposição, o `DIESEL` do CSV tem preço idêntico ao `DIESEL S500` da semana em 305 de 305 pares (posto e dia), contra 9 de 249 para S10. Depois da fusão, essas 305 chaves passaram a coincidir e foram tratadas como cópias idênticas, sem nenhum conflito. Para aplicar a regra às saídas existentes, a ingestão passou a registrar `normalization_version` e refaz as observações quando a versão muda.
9. **Cobertura sobre as linhas publicadas**, por município, produto e semana (domingo a sábado, como a ANP): postos (CNPJs distintos), mediana das oito semanas anteriores (ausência conta zero), baixa cobertura abaixo de 50% de uma mediana ≥ 3, séries recorrentes (6 de 8 semanas) ausentes na última semana, proporção de semanas presentes, dias úteis sem coleta (de todas as linhas avaliadas) e atraso desde a última coleta.
10. **Decisão:** `bloquear` com falha crítica; `publicar_com_aviso` com quarentena acima de 1%, baixa cobertura ou município recorrente ausente na última semana, ou atraso acima de 14 dias; senão `publicar`. O relatório vai para `data/processed/quality/runs/<run_id>.json` e `latest.json`, com contagens por regra, diferença para a execução anterior e amostras sem CNPJ, razão social ou endereço.
11. **Somente a biblioteca padrão.** Pandera (recomendada na arquitetura) não foi adicionada: as regras cabem em funções pequenas e testáveis, e o projeto só acrescenta dependências necessárias. Os testes de dbt e SQL ficam para o Marco 4.

## Alternativas consideradas

- **Precedência do CSV semestral** (consolidado posterior): sem conflito real observado, não há ganho; a semana tem URL e data de download.
- **Escolher um vencedor em conflitos:** esconderia uma divergência que deve ser vista; com 0 conflitos reais, a quarentena não custa nada hoje.
- **Bloquear só o arquivo com falha crítica:** publicaria um conjunto parcial sem aviso claro; a arquitetura manda manter a versão anterior.

## Consequências

- Os limites (50%, 1%, 14 dias, fator 2, 3×IQR, 30 preços) são escolhas iniciais documentadas em constantes, não valores homologados.
- Sem dados prévios, as regras de distribuição e de redução só se aplicam depois de semanas suficientes; o início da série tem menos proteção.
- A saída publicada (`data/processed/staging/observations.csv`) é um arquivo único regenerado a cada execução e só regravado quando muda.
