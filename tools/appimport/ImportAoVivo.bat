@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
echo ========================================
echo   Poker App - Import por pasta local
echo   *** MODO AO VIVO (envia e move) ***
echo ========================================
echo.
echo   Correr SO depois da sessao de poker
echo   (salas fechadas). E um envio unico,
echo   nao corre em background.
echo.
echo   Isto ENVIA a serio e MOVE os ficheiros
echo   enviados para a pasta done\.
echo.
echo   Janela de IMAGENS (it/manual/lobby/gold) - dia-de-jogo 15:00-15:00.
echo   Enter nos dois = TUDO (cuidado: envia tambem imagens antigas).
echo   HH/TS entram sempre por inteiro.
echo.
set "DESDE="
set "ATE="
set /p DESDE="  Imagens - desde (YYYY-MM-DD, Enter = tudo): "
set /p ATE="  Imagens - ate   (YYYY-MM-DD, Enter = tudo): "
set "JANELA="
if not "%DESDE%"=="" set "JANELA=%JANELA% --desde %DESDE%"
if not "%ATE%"=="" set "JANELA=%JANELA% --ate %ATE%"
echo.
echo ----------------------------------------
python "%~dp0app_import.py" --ao-vivo%JANELA%
echo ----------------------------------------
echo.
pause
