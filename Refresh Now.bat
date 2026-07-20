@echo off
title Blinkit RAG - Refresh Now
echo ============================================================
echo   Blinkit RAG - Refresh Now
echo   Runs: ingest -^> process -^> report -^> validate
echo   (uses Groq + scrapes live sources; may take a few minutes)
echo ============================================================
echo.
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0scripts\run_refresh.ps1" %*
echo.
echo ============================================================
echo   Refresh finished. Full log is in the logs\ folder.
echo   A successful run ends with: VALIDATION GATE: PASS
echo ============================================================
pause
