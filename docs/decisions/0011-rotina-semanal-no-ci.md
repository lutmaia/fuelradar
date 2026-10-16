# 0011 — Rotina semanal no GitHub Actions com estado cifrado

- **Status:** proposta, em verificação (Marco 12, 2026-10-15). Passa a aceita depois da primeira execução semanal completa no CI.
- **Contexto:** o [desenho](../estudo-de-caso.md) (seção 9) prevê a atualização semanal no CI gratuito, com banco efêmero e custo zero. O teste das fontes (etapa B2, 2026-10-15) mostrou que a ANP e o Banco Central aceitam downloads a partir do GitHub: semana da ANP em 6 s, fontes externas em 66 s. Mas o CI começa do zero a cada execução, e a carga no banco é por instantâneo: precisa de todo o histórico de SP já processado (cerca de 520 MB de CSV), que traz CNPJ e razão social. Os arquivos brutos da ANP não podem ir ao GitHub (AGENTS.md), e anexo de release de repositório público é público.

## Decisão

1. **Um comando** (`scripts/weekly_refresh.py`, etapa B3) faz a rotina no PC (`.\atualizar.ps1`) e no CI. "Em dia" quer dizer que o pacote do demonstrativo, último passo, já tem a semana mais recente da página da ANP. Uma execução que falha no meio é refeita por inteiro na seguinte, e as etapas idempotentes não duplicam nada.
2. **Estado cifrado** (`scripts/state.py`): cópia do banco (`pg_dump`) e histórico processado (`data/processed` sem `staging`, `external` e `modelv2`, mais `data/quarantine`), num `.tar.gz` cifrado com AES-256 (`openssl enc`, chave derivada por PBKDF2 com 600 mil iterações). A chave fica no `.env` local (`RADAR_STATE_KEY`) e nos Secrets do GitHub (`STATE_KEY`). O arquivo é anexo da release `estado`; o anterior fica como `estado-anterior`. Nenhum arquivo bruto da ANP entra.
3. **Fontes externas sem estado:** o CI baixa as três a cada execução. Os valores já carregados vêm no banco restaurado e mantêm `available_at` (ADR 0010, item 4).
4. **Workflow `weekly.yml`:** todo dia às 22h UTC confere a página da ANP. Sem semana nova, termina em segundos. Com semana nova: abre o estado, roda a rotina num PostgreSQL 16.15 de serviço, guarda o estado novo e commita `reports/ledger/` e `snapshot/` como `github-actions[bot]`. Esse é o único caminho de commit automático, por decisão do usuário. O Streamlit Community Cloud republica a cada push.
5. **Falhas:** qualquer etapa que falhe para o job antes de guardar o estado e de commitar. O GitHub avisa por e-mail, e o painel continua mostrando a idade do dado. O teste de falha (`RADAR_INJECT_FAILURE`, entrada `falha` do workflow) faz uma etapa falhar de propósito, para mostrar a detecção e a recuperação no dia seguinte.
6. **Contêineres** (etapa B6): `Dockerfile` único e perfis no `docker-compose.yml`. `demo` mostra o painel lendo o pacote commitado, sem banco. `completo` sobe banco, API e painel. `pipeline` roda a rotina semanal. Portas só no loopback.

## Alternativas consideradas

- **Rodar no PC do usuário com aviso do GitHub:** mais simples e nada sai do PC, mas a rotina seria semiautomática e não cumpriria o aceite do Marco 12. Continua sendo o plano B: o `.\atualizar.ps1` faz o mesmo trabalho.
- **Baixar todo o histórico da ANP a cada semana:** cerca de 480 MB por execução, carga desnecessária no site da ANP, e os históricos mensais não estão na página semanal.
- **Histórico em cache do Actions:** expira após 7 dias sem uso e não serve de backup; arquivos brutos ficariam guardados no GitHub.
- **Histórico sem cifra, sem CNPJ:** a identificação do posto (CNPJ) é a chave das observações e da página de postos; tirá-la mudaria o modelo de dados.

## Consequências e limitações

- **Chave:** se ela se perder, o estado vira lixo. A recuperação é refazer o estado no PC (banco local + `state.py pack`) e subir de novo; a chave fica em dois lugares.
- **Banco local:** depois que o CI assume, o banco do PC fica parado. Ele pode ser atualizado com `state.py unpack` num banco vazio, ou continuar com `.\atualizar.ps1` depois de um `git pull`; o pacote em dia evita duas execuções para a mesma semana.
- **Limites gratuitos (a conferir na etapa B7):** minutos ilimitados para repositório público em executores padrão; job de até 6 h; anexos de release de até 2 GiB; workflows agendados desativados depois de 60 dias sem atividade no repositório (os commits semanais do robô contam como atividade); o horário agendado pode atrasar em momentos de fila.
- **Integridade:** o `openssl enc` não autentica o conteúdo, mas só o dono do repositório pode trocar o anexo, e o `.tar.gz` confere a própria integridade (CRC); a extração aceita só caminhos esperados.
