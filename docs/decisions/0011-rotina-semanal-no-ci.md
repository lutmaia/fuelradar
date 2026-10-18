# 0011 — Rotina semanal no GitHub Actions com estado cifrado

- **Status:** aceita (Marco 12, 2026-10-16), depois de duas execuções no GitHub: falha injetada na qualidade detectada sem tocar estado nem repositório (execução #2) e recuperação completa a partir do mesmo estado (execução #3, 11 min 44 s, commit do robô `8154fe4`, release com `estado` e `estado-anterior`). Falta só a primeira execução agendada com semana nova da ANP.
- **Contexto:** o [desenho](../estudo-de-caso.md) (seção 9) prevê a atualização semanal no CI gratuito, com banco efêmero e custo zero. O teste das fontes (etapa B2, 2026-10-15) mostrou que a ANP e o Banco Central aceitam downloads a partir do GitHub: semana da ANP em 6 s, fontes externas em 66 s (o workflow e o script desse teste foram retirados depois de cumprir o papel; estão no commit `36b00fb`). Mas o CI começa do zero a cada execução, e a carga no banco é por instantâneo: precisa de todo o histórico de SP já processado (cerca de 520 MB de CSV), que traz CNPJ e razão social. Os arquivos brutos da ANP não podem ir ao GitHub (AGENTS.md), e anexo de release de repositório público é público.

## Decisão

1. **Um comando** (`scripts/weekly_refresh.py`, etapa B3) faz a rotina no PC (`.\atualizar.ps1`) e no CI. "Em dia" quer dizer que o pacote do demonstrativo, último passo, já tem a semana mais recente da página da ANP. Uma execução que falha no meio é refeita por inteiro na seguinte, e as etapas idempotentes não duplicam nada.
2. **Estado cifrado** (`scripts/state.py`): cópia do banco (`pg_dump`) e histórico processado (`data/processed` sem `staging`, `external` e `modelv2`, mais `data/quarantine`), num `.tar.gz` cifrado com AES-256 (`openssl enc`, chave derivada por PBKDF2 com 600 mil iterações). A chave fica no `.env` local (`RADAR_STATE_KEY`) e nos Secrets do GitHub (`STATE_KEY`). O arquivo é anexo da release `estado`; o anterior fica como `estado-anterior`. Nenhum arquivo bruto da ANP entra.
3. **Fontes externas sem estado:** o CI baixa as três a cada execução. Os valores já carregados vêm no banco restaurado e mantêm `available_at` (ADR 0010, item 4).
4. **Workflow `weekly.yml`:** todo dia às 22h UTC confere a página da ANP. Sem semana nova, termina em segundos. Com semana nova: abre o estado, roda a rotina num PostgreSQL 16.15 de serviço, guarda o estado novo e commita `reports/ledger/` e `snapshot/` como `github-actions[bot]`. Esse é o único caminho de commit automático. O Streamlit Community Cloud republica a cada push.
5. **Falhas:** qualquer etapa que falhe para o job antes de guardar o estado e de commitar. O GitHub avisa por e-mail, e o painel continua mostrando a idade do dado. O teste de falha (`RADAR_INJECT_FAILURE`, entrada `falha` do workflow) faz uma etapa falhar de propósito, para mostrar a detecção e a recuperação no dia seguinte.
6. **Contêineres** (etapa B6): `Dockerfile` único e perfis no `docker-compose.yml`. `demo` mostra o painel lendo o pacote commitado, sem banco. `completo` sobe banco, API e painel. `pipeline` roda a rotina semanal. Portas só no loopback.

## Alternativas consideradas

- **Rodar no computador local com aviso do GitHub:** mais simples e nada sai do PC, mas a rotina seria semiautomática e não cumpriria o aceite do Marco 12. Continua sendo o plano B: o `.\atualizar.ps1` faz o mesmo trabalho.
- **Baixar todo o histórico da ANP a cada semana:** cerca de 480 MB por execução, carga desnecessária no site da ANP, e os históricos mensais não estão na página semanal.
- **Histórico em cache do Actions:** expira após 7 dias sem uso e não serve de backup; arquivos brutos ficariam guardados no GitHub.
- **Histórico sem cifra, sem CNPJ:** a identificação do posto (CNPJ) é a chave das observações e da página de postos; tirá-la mudaria o modelo de dados.

## Consequências e limitações

- **Chave:** se ela se perder, o estado vira lixo. A recuperação é refazer o estado no PC (banco local + `state.py pack`) e subir de novo; a chave fica em dois lugares.
- **Banco local:** depois que o CI assume, o banco do PC fica parado. Ele pode ser atualizado com `state.py unpack` num banco vazio, ou continuar com `.\atualizar.ps1` depois de um `git pull`; o pacote em dia evita duas execuções para a mesma semana.
- **Limites gratuitos (etapa B7, 2026-10-16):**
  - **Workflows agendados** são desativados depois de 60 dias sem atividade num repositório público (conferido na documentação do GitHub). Os commits semanais do robô contam como atividade, mas uma pausa longa da ANP (ou do workflow) pode desativá-lo; reativar é um clique em Actions.
  - **Minutos:** ilimitados para repositório público em executores padrão; a execução completa usa cerca de 12 min, e os dias sem semana nova, menos de 1 min.
  - **Job de até 6 h** e **anexos de release de até 2 GiB cada**: folga grande (12 min; estado de cerca de 140 MB).
  - **Horário agendado** pode atrasar em momentos de fila; não importa para uma rotina diária.
  - **Streamlit Community Cloud:** gratuito para app público, cerca de 1 GB de memória (o pacote tem 3 MB) e o app dorme sem visitas. O plano B registrado no ADR 0009 (Hugging Face Spaces) parece não oferecer mais Streamlit no plano gratuito; se o Streamlit mudar, sobram a execução local (`docker compose --profile demo up demo`) e as capturas de tela do README.
- **Integridade:** o `openssl enc` não autentica o conteúdo, mas só o dono do repositório pode trocar o anexo, e o `.tar.gz` confere a própria integridade (CRC); a extração aceita só caminhos esperados.
