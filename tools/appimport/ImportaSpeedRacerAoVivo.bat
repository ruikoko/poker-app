@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
echo ========================================
echo   IMPORTAR so it\SpeedRacer  *** AO VIVO ***
echo   (envia a serio e MOVE p/ done\it\SpeedRacer)
echo ========================================
echo.
echo   Correr SO com as salas de poker FECHADAS.
echo   Processa SO a subpasta it\SpeedRacer (todas as datas;
echo   sem prompt de janela). Envia e move os prints.
echo.
set "OK="
set /p OK="  Escreve SIM para enviar (Enter = cancelar): "
if /I not "%OK%"=="SIM" (
  echo   Cancelado.
  pause
  exit /b
)
echo ----------------------------------------
python "%~dp0app_import.py" --only "it/SpeedRacer" --ao-vivo
echo ----------------------------------------
echo.
pause
