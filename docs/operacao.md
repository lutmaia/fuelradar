# Manual de operação

O que roda sozinho, o que fazer quando algo falha e as datas que ainda pedem atenção. As decisões por trás estão nos ADRs, em especial o [0011](decisions/0011-rotina-semanal-no-ci.md) (rotina no GitHub) e o [0006](decisions/0006-arquivos-da-fonte-excluidos.md) (arquivos da ANP com defeito). English version: [en/operations.md](en/operations.md).

## O que roda sozinho

| O quê | Quando | Onde |
|---|---|---|
| Testes e validação dos workflows | a cada push e pull request | `.github/workflows/tests.yml` |
| Atualização semanal | todo dia às 22h UTC (19h de Brasília); sem semana nova na ANP, termina em segundos | `.github/workflows/weekly.yml` |
| Republicação do demonstrativo | a cada push no `main`, inclusive o do robô | Streamlit Community Cloud |

Com semana nova, o workflow semanal abre o estado cifrado, roda `scripts/weekly_refresh.py` num PostgreSQL temporário (download, ingestão, qualidade, carga, fontes externas, previsões, previsão ao vivo e pacote), guarda o estado novo na release `estado` (o anterior vira `estado-anterior`) e commita `reports/ledger/` e `snapshot/` como `github-actions[bot]`. Antes de commitar no seu computador, rode `git pull --rebase`.

## Quando a atualização falha

O GitHub avisa por e-mail; uma falha não publica nada pela metade (estado e repositório ficam como estavam), e a execução do dia seguinte tenta de novo. No log do passo **Rotina semanal**, a linha `FALHOU em: <etapa>` diz onde parou.

| Etapa ou sintoma | Causa provável | O que fazer |
|---|---|---|
| `ler a página da ANP` | site fora do ar ou página mudou | esperar um dia; se persistir, conferir o endereço em `ingestion/download.py` e o formato dos links |
| `ingerir` ou `qualidade` com arquivo novo | planilha da ANP com defeito | confirmar o defeito e registrá-lo em `config/excluded_sources.json`, com o motivo (ADR 0006); a semana vira lacuna |
| `fontes externas` | Banco Central ou ANP fora do ar | no GitHub, a rotina para e tenta no dia seguinte (lá não há download anterior guardado); no computador, a última versão baixada continua valendo |
| `Abrir o estado cifrado` | chave errada ou anexo ausente | ver [Estado cifrado](#estado-cifrado) |
| workflow não roda mais | 60 dias sem atividade no repositório | Actions → Atualização semanal → *Enable workflow* |

Para rodar na hora (sem esperar as 19h): Actions → Atualização semanal → *Run workflow*. "Rodar mesmo com o pacote em dia" força uma execução completa; o campo de falha (nome de uma etapa) simula uma falha, para testar a detecção.

**Plano B, no computador:** com o Docker aberto, `./atualizar.sh` (macOS e Linux) ou `.\atualizar.ps1` (Windows) faz a mesma rotina sobre o banco local (`--dry-run` só diz se há semana nova); depois, commitar `reports/ledger/` e `snapshot/`.

## Estado cifrado

- **O que é:** cópia do banco (`pg_dump`) e histórico processado de SP, num `.tar.gz` cifrado (AES-256). Fica nos anexos da release `estado`. Os arquivos brutos da ANP não entram.
- **Chave:** em `RADAR_STATE_KEY` no `.env` local e em `STATE_KEY` nos Secrets do repositório. O GitHub não deixa ler o secret de volta: guarde uma cópia num gerenciador de senhas.
- **Definir a chave** (os scripts não leem o `.env` sozinhos): no macOS ou no Linux, `export RADAR_STATE_KEY="$(grep '^RADAR_STATE_KEY=' .env | cut -d= -f2-)"`; no PowerShell, `$env:RADAR_STATE_KEY = ((Get-Content .env | Select-String '^RADAR_STATE_KEY=').Line -split '=', 2)[1]`
- **Voltar ao estado anterior:** baixar `estado-anterior.tar.enc` da release, renomear para `estado.tar.enc` e subir de novo, substituindo o atual (editar a release).
- **Restaurar o banco local a partir do estado** (banco vazio): `python scripts/state.py unpack --container <contêiner do postgres> --input estado.tar.enc`, com `RADAR_STATE_KEY` definida.
- **Trocar a chave ou refazer o estado:** com o banco local em dia, `python scripts/state.py pack --container radar-combustiveis-postgres-1 --output estado.tar.enc` com a chave nova; subir o arquivo na release (substituindo) e atualizar o secret.

## Avaliação ao vivo: datas

As probabilidades de queda, estabilidade e alta são gravadas toda semana em `reports/ledger/` antes de o preço sair, e conferidas quando a ANP publica ([protocolo](estudo/protocolo-ao-vivo.md)). Nada aqui pede ação para funcionar:

- **~janeiro de 2027, 13 semanas conferidas:** o placar passa a calcular o alerta de degradação; se disparar, a página *Desempenho ao vivo* mostra o aviso.
- **~abril de 2027, 26 semanas conferidas em 2 semanas à frente:** a decisão sai sozinha. "Oficial" tira o rótulo experimental da API e do painel; "reprovado" esconde as probabilidades. O passo manual é atualizar o texto do [cartão do modelo](model-card.md) e do README com o resultado, seja qual for.

O registro não se altera: `scripts/run_live.py` confere o SHA-256 de cada arquivo no `manifesto.csv` e para se algum mudou.

## Conferências

- `python scripts/reproduce.py` refaz cada relatório publicado numa pasta temporária e compara (cerca de 6 minutos; o teste final é conferido pelos pontos da leitura única, sem novo acesso).
- `python scripts/dataset_card.py` regenera a [ficha do conjunto de dados](ficha-dados.md).

## Rodar no computador

Instalação no [README](../README.md#rodar-localmente). `./iniciar.sh` (ou `.\iniciar.ps1` no Windows) sobe o banco, a API e o painel (http://127.0.0.1:8501); `docker compose --profile demo up --build demo` sobe só o demonstrativo, sem banco. O banco de desenvolvimento roda em Docker, em `127.0.0.1:54329` (use `127.0.0.1`, não `localhost`).
