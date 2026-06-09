@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
echo ========================================
echo   Poker App - Import por pasta local
echo ========================================
echo.
echo   Correr SO depois da sessao de poker
echo   (salas fechadas). E um envio unico,
echo   nao corre em background.
echo.
echo ----------------------------------------
python "%~dp0app_import.py"
echo ----------------------------------------
echo.
pause
