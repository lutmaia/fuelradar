# Continuar o projeto em outro computador

Passo a passo para colocar o projeto de pé em uma segunda máquina (Windows, PowerShell). O código vem do GitHub; **os dados e as senhas não**, e é por isso que há passos separados para eles.

## O que viaja e o que não viaja

| Item | Como chega à outra máquina |
|---|---|
| Código, documentos, testes, relatórios | `git clone` / `git pull` |
| Dependências Python | `pip install -r requirements.txt` |
| Banco PostgreSQL | recriado no Docker; o conteúdo é reconstruído pelos scripts |
| **Dados brutos da ANP** (`data/raw`) | **não estão no Git** (regra do projeto); copiar a pasta ou baixar de novo |
| Dados processados (`data/processed`, `data/quarantine`) | **não estão no Git**; copiar ou regerar |
| `.env` (senhas) | **não está no Git**; criar de novo em cada máquina |
| Histórico de conversas e memórias de ferramentas | ficam na máquina onde foram criados; o contexto do projeto está nos `.md` do repositório |

## 1. Pré-requisitos

1. **Git** instalado.
2. **Python 3.14** (o projeto exige 3.12 ou superior e foi desenvolvido em 3.14.7). Conferir com `python --version`. Na instalação, marcar "Add python.exe to PATH".
3. **Docker Desktop** (com WSL2). Abra o Docker Desktop e espere o ícone indicar que está rodando. A virtualização precisa estar habilitada na BIOS.
4. **Espaço:** cerca de 5 GB livres (dados ~600 MB, ambiente Python ~430 MB, imagem e volume do Docker 1 a 3 GB). **Memória:** 8 GB é confortável; o PostgreSQL no Docker usa em torno de 1,5 GB.
5. Conta no GitHub com acesso ao repositório.

## 2. Identidade e acesso ao GitHub

```powershell
git config --global user.name "lutmaia"
git config --global user.email "lucasmaiaorenga@gmail.com"   # ou o e-mail noreply do GitHub
```

No primeiro `git push`, o Git Credential Manager abre o navegador para você entrar no GitHub. Alternativa: instalar o GitHub CLI e rodar `gh auth login`.

## 3. Clonar o repositório

Escolha uma pasta **fora do OneDrive** (a sincronização interfere em arquivos grandes e em bancos de dados):

```powershell
mkdir $HOME\projetos -Force
cd $HOME\projetos
git clone https://github.com/lutmaia/fuelradar.git
cd fuelradar
```

A pasta local pode ter qualquer nome; os comandos abaixo valem a partir da raiz do projeto.

## 4. Ambiente Python

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Para conferir: `.\.venv\Scripts\python.exe -c "import lightgbm, streamlit, fastapi, psycopg; print('ok')"`.

Se o seu Python for de outra versão, o `pip` pode escolher versões diferentes das fixadas; prefira instalar o 3.14.

## 5. Segredos locais (`.env`)

```powershell
Copy-Item .env.example .env
notepad .env
```

Troque `POSTGRES_PASSWORD=troque-por-uma-senha-local` por uma senha nova (não precisa ser a do outro computador). O `.env` é ignorado pelo Git; nunca o envie.

## 6. Banco de dados (Docker)

```powershell
docker compose up -d --wait
```

Isso sobe o PostgreSQL 16 em `127.0.0.1:54329`. Use sempre `127.0.0.1`, nunca `localhost`: o IPv6 faz cada conexão esperar cerca de 30 s. Se `docker` não for reconhecido, abra o Docker Desktop e reabra o terminal.

Variáveis desta sessão do terminal (repita a cada terminal novo):

```powershell
$pw = (Get-Content .env | Where-Object { $_ -like 'POSTGRES_PASSWORD=*' }).Split('=', 2)[1]
$env:DATABASE_URL = "postgresql://radar:$pw@127.0.0.1:54329/radar"
$env:RADAR_TEST_DATABASE_URL = "postgresql://radar:$pw@127.0.0.1:54329/postgres"
```

## 7. Dados

Escolha **uma** das opções.

### Opção A — copiar a pasta `data/` do outro computador (recomendada)

Compacte a pasta `data` da máquina original (ou copie por pen drive ou nuvem) e extraia na raiz do projeto, mantendo `data\raw`, `data\processed` e `data\quarantine`. Os arquivos brutos ficam idênticos (mesmos hashes) e a execução é exatamente reproduzível. Depois:

```powershell
.\.venv\Scripts\python.exe scripts/check_quality.py
.\.venv\Scripts\python.exe scripts/load_db.py
```

### Opção B — baixar tudo de novo da ANP

```powershell
.\.venv\Scripts\python.exe scripts/fetch_anp.py --dry-run     # só lista o que seria baixado
.\.venv\Scripts\python.exe scripts/fetch_anp.py --ingest      # baixa o histórico completo (~300 MB) e ingere
.\.venv\Scripts\python.exe scripts/check_quality.py
.\.venv\Scripts\python.exe scripts/load_db.py
```

Notas da opção B:
- Sem `--since`, o script baixa **todas** as semanas publicadas (desde 2022); leva alguns minutos.
- 13 planilhas antigas (2022 a abr/2023) são ilegíveis e aparecem como erro de detecção; é esperado.
- O arquivo defeituoso de 29/06/2025 é ignorado pela lista `config/excluded_sources.json`.
- O arquivo "Preços semestrais" que foi recebido à mão não é baixado por esse script. Ele é redundante com as semanas, mas por isso o conjunto resultante pode diferir em detalhes. A conferência é o **hash dos dados** impresso por `run_forecasts.py` (na máquina original foi `1a3225c5094b`) e a contagem de observações publicadas (801.810 com os dados da data de 04/10/2026).

## 8. Conferir que está tudo certo

```powershell
.\.venv\Scripts\python.exe -W error::ResourceWarning -m unittest discover -s tests -t .
```

Resultado esperado: todos os testes aprovados (239 na data deste documento). Sem `RADAR_TEST_DATABASE_URL`, os testes de banco são ignorados (aparecem como "skipped"); com a variável da seção 6, rodam contra o Docker.

## 9. Rodar a plataforma

Previsões (opcional; cerca de 3 minutos):

```powershell
.\.venv\Scripts\python.exe scripts/run_forecasts.py
```

API (um terminal):

```powershell
$env:RADAR_API_PASSWORD = -join ((1..32) | ForEach-Object { '{0:x}' -f (Get-Random -Maximum 16) })
.\.venv\Scripts\python.exe scripts/create_api_role.py
$env:API_DATABASE_URL = "postgresql://radar_api:$($env:RADAR_API_PASSWORD)@127.0.0.1:54329/radar"
.\.venv\Scripts\python.exe scripts/run_api.py
```

Painel (outro terminal):

```powershell
.\.venv\Scripts\python.exe scripts/run_dashboard.py
```

Abra http://127.0.0.1:8501. Pare com Ctrl+C **uma vez** e espere a linha de encerramento; fechar a janela do terminal pode deixar o processo preso na porta.

## 10. Rotina de trabalho com duas máquinas

1. **Ao começar:** `git pull`.
2. **Ao terminar:** `git add -A`, `git commit` e `git push`.
3. Nunca trabalhe nas duas ao mesmo tempo sem dar `pull`/`push` entre elas.
4. Os dados (`data/`) e o `.env` não sincronizam por Git. Se alguma máquina baixar semanas novas, ela tem os dados mais novos; a outra pode baixar de novo (`fetch_anp.py --ingest`) ou copiar `data/`.
5. O banco é descartável: `docker compose down -v` apaga, e `load_db.py` reconstrói a partir de `data/processed`.

## 11. Problemas comuns

| Sintoma | Causa e solução |
|---|---|
| `docker` não reconhecido | Docker Desktop fechado ou terminal antigo; abra o Docker e reabra o terminal |
| Conexão demora cerca de 30 s | usou `localhost`; troque por `127.0.0.1` |
| "Port 8501 is not available" | processo antigo do painel; ache com `Get-NetTCPConnection -LocalPort 8501` e encerre com `Stop-Process -Id <PID>` |
| Avisos `LF will be replaced by CRLF` | só quebra de linha do Windows; inofensivo |
| `pip` não acha uma versão fixada | Python diferente do 3.14; instale o 3.14 |
| Testes de banco "skipped" | faltou `RADAR_TEST_DATABASE_URL` (seção 6) ou o Docker não está de pé |
