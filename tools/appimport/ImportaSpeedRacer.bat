@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
echo ========================================
echo   IMPORTAR so a subpasta it\SpeedRacer
echo   *** DRY-RUN: mostra o plano, NAO envia ***
echo ========================================
echo.
echo   Processa SO it\SpeedRacer (salta a raiz e as outras subpastas).
echo   Confirma que os prints Speed Racer estao em it\SpeedRacer.
echo.
echo   Para ENVIAR a serio (depois de veres o plano), corre:
echo     python app_import.py --only "it/SpeedRacer" --ao-vivo
echo.
echo ----------------------------------------
python "%~dp0app_import.py" --only "it/SpeedRacer"
echo ----------------------------------------
echo.
pause
