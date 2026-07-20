@echo off
title Blinkit RAG - Refresh Now (no scraping)
echo ============================================================
echo   Blinkit RAG - Refresh Now (NO SCRAPING)
echo   Reprocesses the existing corpus -^> report -^> validate.
echo   Good for a quick test; still uses Groq.
echo ============================================================
echo.
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0scripts\run_refresh.ps1" --skip-ingest
echo.
echo ============================================================
echo   Finished. Full log is in the logs\ folder.
echo   A successful run ends with: VALIDATION GATE: PASS
echo ============================================================
pause
