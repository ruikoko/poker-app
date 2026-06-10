@echo off
REM ============================================================
REM  instala_watcher_TEMPLATE.bat - MODELO source-controlled do
REM  instalador do watcher HRC no Beelink.
REM
REM  COMO USAR (Web/Code, por cada build novo):
REM    1. Cria a GitHub Release (publica) com o hrc_watcher.exe novo.
REM    2. Copia este ficheiro para _local_only\instala_ptXX.bat.
REM    3. Preenche os 3 campos marcados [PREENCHER] abaixo:
REM         VERSION, EXE_URL, EXPECTED_SHA.
REM    4. Entrega o .bat ao Rui (duplo-clique no Beelink).
REM
REM  FLUXO_DE_TRABALHO regra 4 (canal unico): zero zip, zero Discord,
REM  zero transferencias manuais. O .bat DESCARREGA o exe da Release.
REM
REM  REGRA PERMANENTE (CLAUDE.md): o Beelink tem SEMPRE 1 SO watcher exe.
REM    0. DESCARREGA o exe novo da GitHub Release -> %TEMP%
REM    1. VERIFICA o SHA256 (obrigatorio; aborta se nao bater)
REM    2. PARA o processo do watcher (nao se troca um exe a correr)
REM    3. APAGA TODOS os exes antigos (HRCWatch + Desktop + DOWNLOADS)
REM    4. instala APENAS o exe novo em HRCWatch
REM    5. re-verifica o SHA do instalado + confirma 1 SO exe
REM  Sem backup. Rollback/historico vivem no PC principal + git.
REM
REM  pt64: o download vai SEMPRE para %TEMP% e e apagado no fim; o
REM  sweep do passo 3 inclui a pasta Downloads para nao sobrar
REM  nenhuma copia manual (lic. pt64: ficaram 2 exes em Downloads).
REM
REM  Correr no BEELINK (user riand). Duplo-clique. Precisa de internet.
REM ============================================================
setlocal EnableDelayedExpansion
chcp 65001 >nul

REM ---- [PREENCHER] por build -------------------------------------------------
set "VERSION=ptXX"
set "EXE_URL=https://github.com/ruikoko/poker-app/releases/download/watcher-ptXX/hrc_watcher.exe"
set "EXPECTED_SHA=0000000000000000000000000000000000000000000000000000000000000000"
REM ---------------------------------------------------------------------------

set "INSTALL_DIR=C:\Users\riand\HRCWatch"
set "INSTALL_EXE=%INSTALL_DIR%\hrc_watcher.exe"
set "TMP_EXE=%TEMP%\hrc_watcher_%VERSION%.exe"

echo === instala_%VERSION% - watcher HRC (download + regra 1 exe) ===

REM --- 0. Descarregar o exe novo da GitHub Release (para %TEMP%) ---
echo -- A descarregar o exe novo da GitHub Release...
echo    %EXE_URL%
powershell -NoProfile -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; try { Invoke-WebRequest -Uri '%EXE_URL%' -OutFile '%TMP_EXE%' -UseBasicParsing; exit 0 } catch { Write-Host $_.Exception.Message; exit 1 }"
if errorlevel 1 (
  echo [ERRO] download falhou. Verifica a internet e re-corre.
  pause
  exit /b 1
)
if not exist "%TMP_EXE%" (
  echo [ERRO] exe nao foi descarregado.
  pause
  exit /b 1
)

REM --- 1. Verificar SHA256 do descarregado (obrigatorio) ---
for /f "usebackq delims=" %%H in (`powershell -NoProfile -Command ^
  "(Get-FileHash '%TMP_EXE%' -Algorithm SHA256).Hash"`) do set "DL_SHA=%%H"
echo    SHA256 descarregado: !DL_SHA!
if /I not "!DL_SHA!"=="%EXPECTED_SHA%" (
  echo [ERRO] SHA NAO bate com o esperado:
  echo        esperado:     %EXPECTED_SHA%
  echo        descarregado: !DL_SHA!
  echo        Abortado, NAO instala. Avisa o Code/Web.
  del /F /Q "%TMP_EXE%" >nul 2>&1
  pause
  exit /b 1
)
echo    [OK] SHA bate com o build %VERSION%.

REM --- 2. Parar o processo do watcher (se estiver a correr) ---
echo -- A parar o processo do watcher (se activo)...
taskkill /F /IM hrc_watcher.exe >nul 2>&1
if !errorlevel!==0 (echo    processo terminado) else (echo    nao estava a correr)
timeout /t 2 /nobreak >nul

REM --- 3. Apagar TODOS os exes antigos do watcher (sem backup) ---
REM     Inclui o sweep da pasta Downloads (pt64: copias manuais ficavam la).
echo -- A apagar exes antigos do watcher (HRCWatch + Desktop + Downloads)...
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
del /F /Q "%INSTALL_DIR%\hrc_watcher*.exe" >nul 2>&1
del /F /Q "%USERPROFILE%\Desktop\hrc_watcher*.exe" >nul 2>&1
del /F /Q "%USERPROFILE%\Downloads\hrc_watcher*.exe" >nul 2>&1

REM --- 4. Instalar APENAS o exe novo ---
echo -- A instalar o exe novo...
copy /Y "%TMP_EXE%" "%INSTALL_EXE%" >nul
if not exist "%INSTALL_EXE%" (
  echo [ERRO] copia falhou.
  pause
  exit /b 1
)
del /F /Q "%TMP_EXE%" >nul 2>&1

REM --- 5. Re-verificar SHA256 do instalado ---
for /f "usebackq delims=" %%H in (`powershell -NoProfile -Command ^
  "(Get-FileHash '%INSTALL_EXE%' -Algorithm SHA256).Hash"`) do set "INSTALLED_SHA=%%H"
echo    SHA256 instalado: !INSTALLED_SHA!
if /I "!INSTALLED_SHA!"=="%EXPECTED_SHA%" (
  echo    [OK] SHA do instalado bate com %VERSION%
) else (
  echo    [ALERTA] SHA do instalado NAO bate!
)

REM --- Confirmar: 1 SO exe do watcher presente (HRCWatch + Desktop + Downloads) ---
echo -- exes do watcher presentes (deve ser exactamente 1, em HRCWatch):
dir /b "%INSTALL_DIR%\hrc_watcher*.exe" "%USERPROFILE%\Desktop\hrc_watcher*.exe" "%USERPROFILE%\Downloads\hrc_watcher*.exe" 2>nul

echo === feito. Arranca o watcher a partir de: %INSTALL_EXE% ===
pause
endlocal
