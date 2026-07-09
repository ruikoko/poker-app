@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
echo ========================================
echo   ARRUMAR done\it achatado (por TAG da BD)
echo   *** DRY-RUN: mostra o plano, NAO move ***
echo ========================================
echo.
echo   Realoja cada print da RAIZ do done\it na subpasta
echo   da sua etiqueta (fonte de verdade = a base de dados).
echo   Prints SEM etiqueta na BD ficam na raiz (nao se adivinha).
echo.
echo   Este passo so MOSTRA o plano. Nada e movido.
echo   Se o plano estiver bom, corre depois:  TidyDoneIT_Aplicar.bat
echo   (ou:  python tidy_done_it.py --apply)
echo.
echo ----------------------------------------
python "%~dp0tidy_done_it.py" > "%~dp0_tidy_done_it.log" 2>&1
type "%~dp0_tidy_done_it.log"
echo ----------------------------------------
echo.
echo   Plano gravado em: %~dp0_tidy_done_it.log
pause
