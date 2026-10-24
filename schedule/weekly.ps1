# Weekly tracker run for Windows. Register once (PowerShell as the same user):
#   schtasks /Create /SC WEEKLY /D MON /ST 08:00 /TN "IncuBrixAEO" /TR "powershell -ExecutionPolicy Bypass -File \"C:\path\to\incubrix-aeo\schedule\weekly.ps1\""
Set-Location (Split-Path -Parent $PSScriptRoot)
& .\.venv\Scripts\Activate.ps1
python -m engine.run
python -m engine.report
python -m engine.alerts      # exit code 2 = visibility moved; set ALERT_WEBHOOK_URL in .env to get a message
python -m engine.brief --top 10
python -m engine.selfcheck
