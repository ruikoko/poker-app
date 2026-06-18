# RUNBOOK pt79 — build + install + re-smoke do watcher (#HRC-RESTART-POST-WINDOW-FAILURE)

Notas de build para a **sessão no Beelink** (combinar tudo lá). O fix de código já
está commitado **local** (`74f18ac`, NÃO pushed). **Não fazer push para origin
antes de o re-smoke confirmar o `[HRC-RESTART]` nos logs** — só depois se blessa o main.

## O que mudou (recap)

`tools/watcher_src/patched_funcs.py` → `setup_hand`:
- novo flag módulo **`_HRC_WINDOW_DIRTY`** (lido via `globals().get(...,False)`);
- marca `True` ao abrir o wizard; limpa no fim de sucesso;
- no arranque da mão, reinicia o HRC se dirty (além do reinício a cada N);
- bail limpo de wizard-não-abriu NÃO marca dirty (sem duplicar a rung 2);
- loop guard: 1 restart por mão; a falhada é sempre `.failed`, a fila avança.

**Só `setup_hand` (já é SWAP) foi modificado** — não há funções novas. O
`_HRC_WINDOW_DIRTY` é lido com `.get(default=False)` → **seguro mesmo sem APPEND**
no marshal-swap (a 1ª escrita cria a chave no namespace do watcher).

## 1. Build do `.exe` (PC principal, `_local_only/`)

Mesma mecânica de pt66/pt68 (trampoline `swap_and_smoke.py` → PyInstaller):

1. Re-swap: o `swap_and_smoke.py` recompila `patched_funcs.py` e **re-swapa
   `setup_hand`** no `co_consts` do module code original (já está na lista de SWAP —
   nada a acrescentar à lista por causa do pt79).
   - **Const opcional:** podes acrescentar `_HRC_WINDOW_DIRTY=False` à lista de
     consts/APPEND por simetria com `_HANDS_DONE_SINCE_RESTART`, mas **não é
     obrigatório** (o `.get(default=False)` cobre a ausência).
2. Correr a smoke harness in-process (`swap_and_smoke`): confirmar **ALL OK**.
   - ⚠️ Nota: o sub-test pré-existente `#SMOKE-HARNESS-WAIT-FOR-FINISH-MOCK-MISSING`
     (mock Win32 ausente desde pt30) pode bater — **não-bloqueante**, é o mesmo de
     pt42d+. O que interessa é o resto verde.
3. Bundle PyInstaller → `_local_only/.../build_pyi/dist/hrc_watcher.exe`.
4. **SHA256** do `.exe`:
   `powershell -NoProfile -Command "(Get-FileHash '<...>\dist\hrc_watcher.exe' -Algorithm SHA256).Hash"`

## 2. Release `watcher-pt79`

`gh` costuma estar ausente → publicar via **REST API** (padrão pt68):
1. Criar a tag/Release `watcher-pt79` no repo `ruikoko/poker-app`.
2. Fazer upload do `hrc_watcher.exe` como asset.
3. Confirmar o round-trip do SHA (descarregar o asset e re-hash = SHA do build).

## 3. Finalizar o `instala_pt79.bat`

Template já preparado em `tools/watcher_src/instala_pt79.bat`. Falta **1 campo**:
- `EXPECTED_SHA` → preencher com o SHA256 do passo 1.4.
- (`VERSION=pt79` e `EXE_URL=.../watcher-pt79/hrc_watcher.exe` já estão preenchidos.)

Copiar o `.bat` finalizado para entrega ao Rui (duplo-clique no Beelink).

## 4. Instalar no Beelink (user `riand`)

Duplo-clique no `instala_pt79.bat`. O `.bat` (regra «1 só exe»): descarrega →
**SHA-check obrigatório** → `taskkill hrc_watcher.exe` → apaga TODOS os exes
(HRCWatch + Desktop + Downloads) → instala só o novo em `C:\Users\riand\HRCWatch\`
→ re-verifica SHA → confirma 1 só exe.

## 5. Re-smoke — critério de aceitação (ANTES do push)

Objetivo: ver o **`[HRC-RESTART]`** pós-falha-pós-janela nos logs e a auto-cura.

1. Arrancar o watcher novo a partir de `C:\Users\riand\HRCWatch\hrc_watcher.exe`.
2. Provocar (ou aproveitar) uma mão que falhe **depois de o wizard abrir** — o caso
   real é o `_wait_for_finish_ready` (`WIZARD_FINISH_NEVER_RE_ENABLED`, tree size que
   não acaba). Pôr ≥2 mãos na fila para ver a 2ª.
3. Confirmar em `C:\hrc\watcher_logs\hrc_watcher_*.log`:
   - a mão falhada é marcada `.failed` e a fila avança (como antes);
   - **no arranque da mão SEGUINTE** aparece:
     `[HRC-RESTART] mão anterior falhou pós-abertura-de-janela (cálculo/finish/export) — a reiniciar o HRC...`
   - o HRC é morto+relançado e a mão seguinte **não falha por arrasto** ("setup failed"
     em cadeia deixa de acontecer).
4. (Opcional) confirmar que numa mão de sucesso NÃO aparece o `[HRC-RESTART]` de
   pós-janela (só o de cada-N, se aplicável).

## 6. Push — bless do main

**Só depois** do passo 5 confirmado: `git push origin main` (commit `74f18ac` +
estas notas). Antes disso o fix vive só em local.

## Rollback

Se o re-smoke falhar: **não** instalar/quedar o `.exe` pt79; reinstalar o `.exe`
anterior (Release `watcher-pt68`, SHA `222fc48d…3f57`) pelo seu `instala_pt68.bat`.
O source pt79 fica em local (não-pushed) para corrigir e re-build.
