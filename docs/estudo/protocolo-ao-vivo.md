# Protocolo da calibração e da avaliação ao vivo (Marcos 10b e 11)

- **Versão:** 1.0, de 2026-10-15. Escrito e commitado **antes** de ajustar a calibração e de gerar a primeira previsão ao vivo.
- **Ponto de partida:** o [Marco 10](protocolo-modelagem.md). O candidato L2 com LightGBM superou a taxa-base no teste final (BSS +0,164), mas teve erro de calibração 0,0504, acima do limite de 0,05, e não foi aprovado.
- **Por que um protocolo novo:** o teste final do Marco 10 **já foi visto**. Qualquer ajuste avaliado nele seria otimista por construção. Aqui o ajuste é aprendido só na validação, e a prova vem de **semanas futuras**, registradas antes de o valor real existir.
- **Código que fixa as constantes:** `src/radar_combustiveis/modelv2/live.py`; um teste confere que os números daqui são os do código.

## 1. O que muda e o que não muda

- **Não muda:** variáveis (camada L2), modelo (LightGBM multiclasse), hiperparâmetros, alvo (τ = R$ 0,05), horizontes (1, 2 e 4 semanas), elegibilidade e a taxa-base de referência. São exatamente os do Marco 10.
- **Muda só a calibração:** *temperature scaling*, **um parâmetro T por horizonte**. As probabilidades calibradas são `softmax(log(p) / T)`: T > 1 deixa o modelo menos confiante, T < 1 mais confiante, e a classe mais provável nunca muda.
- **Ajuste de T:** o valor que minimiza o *log-loss* nas previsões da **validação** do Marco 10 (origens de jul/2025 a mar/2026, `data/processed/modelv2/validacao.csv.gz`), por horizonte, com T entre 0,25 e 4. O relatório mostra o erro de calibração da validação antes e depois, **declarado otimista** (é a mesma amostra do ajuste).
- **O teste final do Marco 10 não é usado** para ajustar nem para avaliar a calibração.

## 2. Previsões ao vivo e registro imutável

- **Treino de produção:** a cada execução, um modelo por horizonte, com todos os pares cujo alvo já é conhecido na semana mais recente do conjunto (janela crescente, como no Marco 10).
- **Origem:** a semana mais recente com dado. **Séries:** as elegíveis pela regra do Marco 7 nessa semana.
- **Registro:** `reports/ledger/<origem>.csv` com, por série e horizonte, as probabilidades calibradas, as da taxa-base e o último valor; e uma linha em `reports/ledger/manifesto.csv` com o SHA-256 do arquivo. Um arquivo de origem **nunca é reescrito**: se já existe, a execução não o altera. O commit semanal desses arquivos (feito pelo usuário) é o carimbo de data de que a previsão veio antes do valor real.
- O banco recebe uma cópia do registro (tabela `forecast_class`), para a API e o painel.

## 3. Pontuação e placar

- Uma previsão **vence** quando a semana-alvo tem mediana publicada. A classe real usa a mesma regra do Marco 10 (sem excluir cobertura baixa).
- **Placar:** BSS contra a taxa-base, por horizonte, sobre todas as previsões vencidas, com IC de 95% por *bootstrap* em blocos de 4 origens (B = 2000, semente 20261013); erro de calibração (10 faixas, média nas classes); número de origens e pontos.
- **Alerta de degradação:** BSS em h = 2 das **13 origens vencidas mais recentes** abaixo de zero.

## 4. Decisão: de "experimental" para oficial

- Até a decisão, as probabilidades aparecem no painel e na API marcadas como **experimentais**.
- **Checagem única** quando houver **26 origens vencidas em h = 2** (cerca de seis meses). Não há decisão antes disso, para não parar no primeiro número bom.
- Passa a oficial se, nessas 26 origens: BSS em h = 2 maior que zero **com limite inferior do IC de 95% maior que zero**; erro de calibração **até 0,05**; nenhum produto, porte ou horizonte com BSS abaixo de **−0,05** (grupos com pelo menos 200 pontos). Senão, as probabilidades saem do produto e o resultado é publicado.
- Previsões geradas depois da semana em que se completam as 26 origens continuam no placar, mas não mudam a decisão.

## 5. Limitações já conhecidas

- O ajuste de T usa a validação, cuja distribuição de classes (16% de quedas) foi diferente da do teste (39%); a calibração pode não se manter.
- Lacunas de publicação da ANP atrasam o vencimento das previsões e a checagem.
- Uma execução que pule uma semana deixa de registrar aquela origem; o placar conta só o que foi registrado.

## 6. Desvios

| Data | Mudança | Motivo | Antes ou depois de resultados |
|---|---|---|---|
