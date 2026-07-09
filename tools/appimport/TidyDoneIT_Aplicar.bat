@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
echo ========================================
echo   ARRUMAR done\it - APLICAR (move a serio)
echo ========================================
echo.
echo   Corre SO depois de veres o plano do dry-run (TidyDoneIT.bat)
echo   e concordares. MOVE os prints da raiz do done\it para as
echo   subpastas da sua etiqueta. So mexe dentro de Batmen.
echo.
set "OK="
set /p OK="  Escreve SIM para mover a serio (Enter = cancelar): "
if /I not "%OK%"=="SIM" (
  echo   Cancelado.
  pause
  exit /b
)
echo ----------------------------------------
python "%~dp0tidy_done_it.py" --apply
echo ----------------------------------------
echo.
pause
