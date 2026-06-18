@echo off
REM ============================================================================
REM  limpa_scratch.bat  -  Limpeza SEGURA e REVERSIVEL do scratch do adapter HRC
REM ----------------------------------------------------------------------------
REM  O que faz:
REM   1. RECUSA se o adapter (python hrc_adapter) ou o watcher (hrc_watcher.exe)
REM      estiverem a correr -> nao limpar a meio.
REM   2. MOVE (nao apaga) para  Teste completo\_limpeza_AAAAMMDD\ :
REM        - todas as pastas de mao  <hand_id>\
REM        - done\   arquivo\   replied\
REM      (manifest.json e tudo o resto ficam intactos.)
REM   3. Faz copia do state.json para a pasta de backup e repoe state.json = {}.
REM   4. NAO toca no watcher, no adapter, nem em packs em uso.
REM
REM  Reversivel: para desfazer, mover de volta as pastas de _limpeza_AAAAMMDD\
REM  e restaurar o state.json.bak (instrucoes impressas no fim).
REM
REM  Apagar de vez (se o Rui preferir): depois de confirmar que esta tudo OK,
REM  apagar a pasta de backup:   rd /s /q "<...>\_limpeza_AAAAMMDD"
REM ============================================================================
setlocal EnableExtensions EnableDelayedExpansion

set "QUEUE_DIR=C:\Users\Administrator\Documents\Teste completo"
set "STATE_FILE=C:\hrc\adapter\state.json"

echo(
echo === Limpeza do scratch do adapter HRC ===
echo   QUEUE_DIR : %QUEUE_DIR%
echo   STATE     : %STATE_FILE%
echo(

REM --- 0) Pasta existe? ---
if not exist "%QUEUE_DIR%\" (
  echo [ERRO] Pasta nao encontrada: %QUEUE_DIR%
  echo Nada feito.
  goto :fim
)

REM --- 1) Recusar se adapter ou watcher a correr ---
set "ADAPTER_PROCS=0"
for /f %%n in ('powershell -NoProfile -Command "@(Get-CimInstance Win32_Process -Filter \"Name='python.exe' OR Name='pythonw.exe'\" -ErrorAction SilentlyContinue ^| Where-Object { $_.CommandLine -like '*hrc_adapter*' }).Count" 2^>nul') do set "ADAPTER_PROCS=%%n"

set "WATCHER_RUNNING="
tasklist /fi "imagename eq hrc_watcher.exe" 2>nul | find /i "hrc_watcher.exe" >nul && set "WATCHER_RUNNING=1"

if not "%ADAPTER_PROCS%"=="0" (
  echo [RECUSADO] O ADAPTER parece estar a correr ^(processos: %ADAPTER_PROCS%^).
  echo Fecha o adapter primeiro e volta a correr este .bat. Nada foi tocado.
  goto :fim
)
if defined WATCHER_RUNNING (
  echo [RECUSADO] O WATCHER ^(hrc_watcher.exe^) esta a correr.
  echo Pode estar a processar um pack. Fecha-o primeiro. Nada foi tocado.
  goto :fim
)
echo [OK] Adapter e watcher parados.
echo(

REM --- 2) Datestamp AAAAMMDD (locale-independent via PowerShell) ---
set "STAMP="
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd" 2^>nul') do set "STAMP=%%i"
if not defined STAMP set "STAMP=manual"
set "BACKUP=%QUEUE_DIR%\_limpeza_%STAMP%"

REM --- Pre-visualizar o que vai ser movido ---
echo Vai MOVER para:  %BACKUP%\
echo(
echo   Pastas de mao a mover:
set "NHANDS=0"
for /d %%D in ("%QUEUE_DIR%\*") do (
  set "NAME=%%~nxD"
  set "SKIP="
  if /i "!NAME!"=="done" set "SKIP=1"
  if /i "!NAME!"=="arquivo" set "SKIP=1"
  if /i "!NAME!"=="replied" set "SKIP=1"
  echo !NAME! | findstr /b /i "_limpeza_" >nul && set "SKIP=1"
  if not defined SKIP (
    echo     - !NAME!
    set /a NHANDS+=1
  )
)
echo   ^(total pastas de mao: !NHANDS!^)
for %%R in (done arquivo replied) do (
  if exist "%QUEUE_DIR%\%%R\" echo   - subpasta reservada: %%R\
)
echo   state.json -> backup + reset para {}
echo(

REM --- 3) Confirmacao ---
choice /c SN /n /m "Confirmar limpeza? [S]im / [N]ao: "
if errorlevel 2 (
  echo Cancelado. Nada foi tocado.
  goto :fim
)
echo(

REM --- 4) Criar pasta de backup ---
if not exist "%BACKUP%\" mkdir "%BACKUP%"
if not exist "%BACKUP%\" (
  echo [ERRO] Nao consegui criar a pasta de backup. Abortado, nada movido.
  goto :fim
)

REM --- 5) Backup do state.json (antes de repor) ---
if exist "%STATE_FILE%" (
  copy /y "%STATE_FILE%" "%BACKUP%\state.json.bak" >nul
  echo [OK] state.json salvaguardado em %BACKUP%\state.json.bak
)

REM --- 6) Mover subpastas reservadas (done/arquivo/replied) ---
for %%R in (done arquivo replied) do (
  if exist "%QUEUE_DIR%\%%R\" (
    move "%QUEUE_DIR%\%%R" "%BACKUP%\%%R" >nul && (
      echo [OK] movido: %%R\
    ) || echo [AVISO] falhou mover %%R\
  )
)

REM --- 7) Mover pastas de mao <hand_id> ---
for /d %%D in ("%QUEUE_DIR%\*") do (
  set "NAME=%%~nxD"
  set "SKIP="
  if /i "!NAME!"=="done" set "SKIP=1"
  if /i "!NAME!"=="arquivo" set "SKIP=1"
  if /i "!NAME!"=="replied" set "SKIP=1"
  echo !NAME! | findstr /b /i "_limpeza_" >nul && set "SKIP=1"
  if not defined SKIP (
    move "%%D" "%BACKUP%\!NAME!" >nul && (
      echo [OK] movido: !NAME!\
    ) || echo [AVISO] falhou mover !NAME!\
  )
)

REM --- 8) Repor state.json = {} ---
> "%STATE_FILE%" echo {}
echo [OK] state.json reposto a {}

echo(
echo === Concluido ===
echo Backup em: %BACKUP%
echo(
echo Para DESFAZER (reverter):
echo   1) mover de volta as pastas de   %BACKUP%\   para   %QUEUE_DIR%\
echo   2) copy /y "%BACKUP%\state.json.bak" "%STATE_FILE%"
echo(
echo Para APAGAR DE VEZ (depois de confirmar que esta tudo bem):
echo   rd /s /q "%BACKUP%"
echo(

:fim
endlocal
pause
