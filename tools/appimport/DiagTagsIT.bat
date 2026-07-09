@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
echo ========================================
echo   DIAGNOSTICO - tags da pasta do IT
echo   *** DRY-RUN: NAO envia, NAO move nada ***
echo ========================================
echo.
echo   So LE a pasta it\ e mostra, por ficheiro:
echo     - de que subpasta veio + que TAG traria
echo     - se e MESA (table-ss) ou LOBBY
echo     - aviso se a subpasta NAO esta no mapa de tags
echo.
echo   Nao escreve na app. Podes correr as vezes que quiseres.
echo   (Ideal: salas de poker fechadas, como sempre.)
echo.
echo   ANTES de correr: confirma que os prints ICM FT e SpeedRacer
echo   estao DENTRO das subpastas it\ICM FT\ e it\SpeedRacer\
echo   (se ja foram processados, voltaram para done\it\ - ver plano B).
echo.
echo ----------------------------------------
python "%~dp0app_import.py" --only it > "%~dp0_diag_tags_it.log" 2>&1
echo ---------------------------------------- >> "%~dp0_diag_tags_it.log" 2>&1
type "%~dp0_diag_tags_it.log"
echo.
echo ========================================
echo   Log gravado em: %~dp0_diag_tags_it.log
echo   Envia-me esse ficheiro (_diag_tags_it.log).
echo ========================================
pause
