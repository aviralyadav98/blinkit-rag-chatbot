@echo off
REM Phase 5 — regenerate the Insight Report on the signed-off 70b synthesis model
REM after Groq's daily token quota resets (UTC midnight). Scheduled to run once
REM at ~05:45 IST; safe to double-click manually any time after the reset too.
REM SYNTHESIS_MODEL is deliberately NOT set here, so synthesis.py defaults to
REM llama-3.3-70b-versatile.

cd /d "C:\Users\KAUSHAL\OneDrive\Documents\final project nextleap\blinkit-rag-chatbot\blinkit-rag-chatbot"
set "SYNTHESIS_MODEL="
".venv\Scripts\python.exe" "app\report_agent.py" > "app\report_70b_regen.log" 2>&1
