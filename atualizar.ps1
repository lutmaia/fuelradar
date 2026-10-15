# Atualização semanal em um comando: .\atualizar.ps1  (precisa do Docker Desktop aberto)
# Sobe o banco, prepara as conexões e roda scripts/weekly_refresh.py; se a ANP ainda não publicou
# semana nova, termina sem mudar nada. Argumentos extras vão para o script (ex.: --dry-run).
Set-Location $PSScriptRoot

docker compose up -d --wait
if ($LASTEXITCODE -ne 0) {
    Write-Host "O banco não subiu. O Docker Desktop está aberto?" -ForegroundColor Red
    exit 1
}

$pw = (Get-Content .env | Where-Object { $_ -like 'POSTGRES_PASSWORD=*' }).Split('=', 2)[1]
$env:DATABASE_URL = "postgresql://radar:$pw@127.0.0.1:54329/radar"
# Senha nova a cada execução, como no iniciar.ps1; se a API estiver aberta, reinicie-a depois.
$env:RADAR_API_PASSWORD = -join ((1..32) | ForEach-Object { '{0:x}' -f (Get-Random -Maximum 16) })
.\.venv\Scripts\python.exe scripts/create_api_role.py
$env:API_DATABASE_URL = "postgresql://radar_api:$($env:RADAR_API_PASSWORD)@127.0.0.1:54329/radar"

.\.venv\Scripts\python.exe scripts/weekly_refresh.py @args
exit $LASTEXITCODE
