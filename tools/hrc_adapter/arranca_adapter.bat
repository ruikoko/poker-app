@echo off
REM ============================================================
REM  arranca_adapter.bat - arranca o entregador (hrc_adapter.py)
REM  no Beelink, com logging garantido, SEM depender do
REM  'activate' do venv (bloqueado pela execution policy do
REM  PowerShell -> ver pt64).
REM
REM  Uso: DUPLO-CLIQUE. Deixa esta janela aberta enquanto o
REM  entregador corre. Ctrl+C (ou fechar a janela) para parar.
REM
REM  Coloca este .bat DENTRO da pasta do adapter
REM  (ex: C:\hrc\adapter\), ao lado de hrc_adapter.py e da venv\.
REM ============================================================

setlocal
cd /d "%~dp0"

REM Regra 6 do FLUXO (logging a prova de perda): sem buffer na
REM consola. O adapter ja grava em logs\hrc_adapter.log; isto
REM garante que a consola tambem sai em tempo real.
set PYTHONUNBUFFERED=1

set "PYEXE=%~dp0venv\Scripts\python.exe"

if not exist "%PYEXE%" (
  echo.
  echo [ERRO] Nao encontrei o Python da venv em:
  echo        %PYEXE%
  echo.
  echo  O que fazer:
  echo   1^) Confirma que este .bat esta DENTRO da pasta do adapter
  echo      ^(ex: C:\hrc\adapter\^), ao lado da pasta venv\.
  echo   2^) Se a venv nao existe, cria-a ^(ver README, seccao Setup^):
  echo        py -3.14 -m venv venv
  echo        venv\Scripts\python.exe -m pip install -r requirements.txt
  echo.
  pause
  exit /b 1
)

echo A arrancar o entregador ^(hrc_adapter.py^)...
echo  ^(deixa esta janela aberta; Ctrl+C para parar limpo^)
echo.

"%PYEXE%" hrc_adapter.py
set "RC=%ERRORLEVEL%"

echo.
echo === O entregador parou ^(codigo de saida %RC%^) ===
echo  Se foi sem querer, volta a fazer duplo-clique neste .bat.
echo  Logs em: %~dp0logs\hrc_adapter.log
pause
endlocal
