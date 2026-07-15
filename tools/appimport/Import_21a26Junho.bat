@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
echo ========================================
echo   Poker App - Import 21 a 26 de Junho
echo   *** AO VIVO (envia e move) ***
echo   Janela: --desde 2026-06-21 --ate 2026-06-26
echo ========================================
echo.
echo   Correr SO com as salas de poker fechadas.
echo   Envio unico; nao corre em background.
echo.
echo ----------------------------------------
python "%~dp0app_import.py" --desde 2026-06-21 --ate 2026-06-26 --ao-vivo
echo ----------------------------------------
echo.
echo   TERMINADO. Le o resumo acima.
pause
