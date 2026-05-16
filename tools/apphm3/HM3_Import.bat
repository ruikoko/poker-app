@echo off
echo ========================================
echo   HM3 - Poker App - Import de maos
echo ========================================
echo.

set /p DIAS="Ultimos quantos dias? (Enter = tudo): "

if "%DIAS%"=="" (
    echo A importar TODAS as maos tagadas...
    python "%~dp0hm3_export.py"
) else (
    echo A importar maos dos ultimos %DIAS% dias...
    python "%~dp0hm3_export.py" --days %DIAS%
)

echo.
echo ========================================
pause
