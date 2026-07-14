@echo off
setlocal

set ROOT=%~dp0
set NGROK_DIR=%LOCALAPPDATA%\ngrok

echo ==========================================
echo  SPED Manager - ambiente de teste
echo ==========================================
echo.

echo [1/3] Iniciando API (porta 8000)...
start "SPED Manager - API" cmd /k "cd /d %ROOT% && .venv\Scripts\python.exe -m uvicorn api.main:app --reload --port 8000"

echo [2/3] Iniciando frontend (porta 5173)...
start "SPED Manager - Frontend" cmd /k "cd /d %ROOT%frontend && npm run dev"

echo Aguardando os servidores subirem...
timeout /t 6 /nobreak >nul

echo [3/3] Iniciando tunel ngrok (link publico)...
start "SPED Manager - ngrok" cmd /k "%NGROK_DIR%\ngrok.exe start --all --config %NGROK_DIR%\ngrok.yml --config %NGROK_DIR%\tunnels.yml"

timeout /t 3 /nobreak >nul
start http://127.0.0.1:4040

echo.
echo Tudo iniciado em janelas separadas.
echo A URL publica (ngrok) aparece na aba que acabou de abrir (http://127.0.0.1:4040).
echo Para gerar credenciais de teste: .venv\Scripts\python.exe scripts\seed_usuarios_and_produtos_saas.py
echo.
echo Para encerrar, feche as 3 janelas abertas (API, Frontend, ngrok).
echo.
pause
