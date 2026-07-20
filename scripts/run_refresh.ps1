# Phase 8 — weekly refresh runner (invoked by Windows Task Scheduler).
#
# Wraps refresh.py so the scheduled run is logged and self-contained: it resolves
# the project's venv python, runs the full ingest -> process -> report -> validate
# (-> optional Google Doc) pipeline, and tees all output to a timestamped log in
# logs/. Any extra args are passed through to refresh.py (e.g. --skip-ingest for a
# test run that reprocesses the existing corpus without re-scraping).
#
# Manual test run (no scraping):
#   powershell -ExecutionPolicy Bypass -File scripts\run_refresh.ps1 --skip-ingest

$ErrorActionPreference = 'Continue'
$proj = 'C:\Users\KAUSHAL\OneDrive\Documents\final project nextleap\blinkit-rag-chatbot\blinkit-rag-chatbot'
$py = Join-Path $proj '.venv\Scripts\python.exe'
$logDir = Join-Path $proj 'logs'
New-Item -ItemType Directory -Force $logDir | Out-Null
$log = Join-Path $logDir ('refresh_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.log')

Set-Location $proj
"[run_refresh] $(Get-Date -Format s) starting refresh.py $args" | Tee-Object -FilePath $log
& $py (Join-Path $proj 'refresh.py') @args *>&1 | Tee-Object -FilePath $log -Append
$code = $LASTEXITCODE
"[run_refresh] $(Get-Date -Format s) finished with exit code $code" | Tee-Object -FilePath $log -Append
exit $code
