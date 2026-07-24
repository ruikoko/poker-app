@echo off
echo ========================================
echo   HM3 - Poker App - Import de maos
echo ========================================
echo.
echo O que queres importar?
echo.
echo   [Enter]      = TODAS as maos tagadas
echo   N            = ultimos N dias (ex: 7)
echo   DD/MM        = SO o dia de jogo DD/MM (ex: 12/07)
echo                  (dia de jogo = das 12h00 desse dia
echo                   as 11h59 do dia seguinte)
echo.
set /p ESCOLHA="Escolha: "

if "%ESCOLHA%"=="" (
    echo A importar TODAS as maos tagadas...
    python "%~dp0hm3_export.py"
    goto fim
)

echo %ESCOLHA% | findstr "/" >nul
if %errorlevel%==0 (
    echo A importar o dia de jogo %ESCOLHA%...
    python "%~dp0hm3_export.py" --day %ESCOLHA%
) else (
    echo A importar maos dos ultimos %ESCOLHA% dias...
    python "%~dp0hm3_export.py" --days %ESCOLHA%
)

:fim
echo.
echo ========================================
pause
