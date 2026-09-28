@echo off
rem Launch script for AI Review Analyst (Project 2).
rem Reads TG_TOKEN from the root .env, sets WB_BOT_TOKEN, runs the bot in demo mode.
cd /d "%~dp0"

for /f "usebackq tokens=1,* delims==" %%a in ("..\.env") do (
    if "%%a"=="TG_TOKEN" set "WB_BOT_TOKEN=%%b"
)
if not defined WB_BOT_TOKEN (
    echo [ERROR] TG_TOKEN not found in ..\.env
    pause
    exit /b 1
)

rem 1 = demo mode: mock reviews + mock LLM (no network, no keys) | 0 = real parsing + real LLM
set "WB_DEMO_MODE=1"
set "LLM_PROVIDER=mock"
set "PYTHONIOENCODING=utf-8"

rem --- REAL ANALYSIS: set keys, choose a provider, then switch off demo ---
rem 1) set "WB_DEMO_MODE=0"
rem 2) YandexGPT:  set "LLM_PROVIDER=yandex"  + YANDEX_FOLDER_ID / YANDEX_API_KEY
rem    OpenAI:     set "LLM_PROVIDER=openai"  + OPENAI_API_KEY
rem 3) restart this script. Fallback providers are set via LLM_FALLBACKS (default: mock).

..\.venv\Scripts\python.exe -u bot.py
