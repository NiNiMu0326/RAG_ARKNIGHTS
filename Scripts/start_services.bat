@echo off
::: Start backend and frontend as hidden background processes
::: No console windows will appear on desktop

::: Switch to project root (this script lives in Scripts/)
cd /d "%~dp0.."

::: Kill existing processes
taskkill /f /im python.exe >nul 2>&1
taskkill /f /im node.exe >nul 2>&1

::: Start backend (hidden)
start /b "" python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 >nul 2>&1

::: Wait for backend to be ready
timeout /t 3 /nobreak >nul

::: Start frontend dev server (hidden)
start /b "" npx --prefix frontend vite --port 8889 >nul 2>&1

echo Backend:  http://localhost:8000
echo Frontend: http://localhost:8889
echo Both services started in background (no visible windows).
echo.
echo To stop all services, run: Scripts\stop_services.bat
pause
