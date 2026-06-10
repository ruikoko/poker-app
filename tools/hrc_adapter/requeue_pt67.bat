@echo off
REM ============================================================
REM  requeue_pt67.bat — re-enfileira as 2 maos da re-smoke pt67 no Beelink.
REM
REM  FLUXO regra 4 (canal unico): este bat DESCARREGA o requeue_state.py da
REM  Release watcher-pt67 e corre-o pela venv do adapter — zero transferencias
REM  manuais, zero edicao de JSON a mao.
REM
REM  Porque: o fix do Max Players e' BACKEND. Os packs das 2 maos no Beelink
REM  tem o meta ANTIGO (Max=2) e o state.json do adapter marca-as como done ->
REM  o adapter NAO as re-puxa. Este bat limpa o lado do Beelink (state.json +
REM  packs/zips antigos).
REM
REM  ⚠️ PRE-REQUISITO (lado backend, feito pelo Code via Railway com OK do Rui):
REM     apagar as 2 linhas de hrc_jobs (GG-6029013400 + GG-6039094225) -> senao
REM     a app NAO as re-serve. (Ja feito quando correres isto.)
REM
REM  Correr no BEELINK. Duplo-clique. Precisa de internet.
REM ============================================================
setlocal
chcp 65001 >nul

set "PYEXE=C:\hrc\adapter\venv\Scripts\python.exe"
set "TMP_PY=%TEMP%\requeue_state_pt67.py"
set "RQ_URL=https://github.com/ruikoko/poker-app/releases/download/watcher-pt67/requeue_state.py"

echo === requeue_pt67 — GG-6029013400 + GG-6039094225 ===

echo -- A parar o watcher (se activo)...
taskkill /F /IM hrc_watcher.exe >nul 2>&1
echo    ^(fecha tambem a consola do ADAPTER antes de continuar, se estiver aberta^)

echo -- A descarregar requeue_state.py da Release...
powershell -NoProfile -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; try{Invoke-WebRequest -Uri '%RQ_URL%' -OutFile '%TMP_PY%' -UseBasicParsing;exit 0}catch{Write-Host $_.Exception.Message;exit 1}"
if errorlevel 1 (
  echo [ERRO] download falhou. Verifica a internet e re-corre.
  pause
  exit /b 1
)
if not exist "%PYEXE%" (
  echo [ERRO] Python da venv do adapter nao encontrado em:
  echo        %PYEXE%
  echo        Confirma que o adapter esta instalado em C:\hrc\adapter\.
  pause
  exit /b 1
)

"%PYEXE%" "%TMP_PY%" GG-6029013400 GG-6039094225
del /F /Q "%TMP_PY%" >nul 2>&1

echo.
echo === Proximo (lado Beelink): ===
echo   1) Arranca o adapter:  duplo-clique em arranca_adapter.bat
echo   2) Arranca o watcher:  hrc_watcher.exe
echo   3) O adapter re-puxa as 2 maos -> packs NOVOS (Max=5) -> re-smoke.
echo.
pause
endlocal
