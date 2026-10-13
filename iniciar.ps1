Set-Location $PSScriptRoot

docker compose up -d --wait

$pw = (Get-Content .env | Where-Object { $_ -like 'POSTGRES_PASSWORD=*' }).Split('=', 2)[1]
$env:DATABASE_URL = "postgresql://radar:$pw@127.0.0.1:54329/radar"
$env:RADAR_TEST_DATABASE_URL = "postgresql://radar:$pw@127.0.0.1:54329/postgres"
$env:RADAR_API_PASSWORD = -join ((1..32) | ForEach-Object { '{0:x}' -f (Get-Random -Maximum 16) })
.\.venv\Scripts\python.exe scripts/create_api_role.py
$env:API_DATABASE_URL = "postgresql://radar_api:$($env:RADAR_API_PASSWORD)@127.0.0.1:54329/radar"

Start-Process powershell -WorkingDirectory $PSScriptRoot -ArgumentList '-NoExit', '-Command', '.\.venv\Scripts\python.exe scripts/run_dashboard.py'
Start-Process "http://127.0.0.1:8501"

.\.venv\Scripts\python.exe scripts/run_api.py