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

**⚠️ Não depender de uma falha natural (rara).** Induzir a falha pós-janela de forma
**determinística**, pelo caminho de falha REAL (`_wait_for_finish_ready` →
`WIZARD_FINISH_NEVER_RE_ENABLED`), encolhendo o timeout da Fase 2.

### 5a. Indução determinística (build de SMOKE, timeout encolhido)

1. **Edição temporária** em `tools/watcher_src/patched_funcs.py:112`:
   `_FINISH_WAIT_PHASE2_TIMEOUT_S = 60.0` → **`1.0`**.
   (NÃO mexer no `_FINISH_WAIT_PHASE1_TIMEOUT_S = 5.0` — a Fase 1 tem de continuar a
   ver o Finish ficar *disabled*, senão `_wait_for_finish_ready` devolve cedo sem
   levantar.)
2. Build de um `.exe` de **SMOKE** com esse timeout (mesmo processo do passo 1; é um
   `.exe` descartável, NÃO o de produção). Instalar no Beelink pelo bat (ou cópia
   manual para `HRCWatch`).
3. Pôr **≥2 mãos** na fila, com a 1ª a ter **árvore não-trivial** (calc demora >1s, p/
   a Fase 1 ver o Finish *disabled* e a Fase 2 estourar ao 1s → levanta o
   `WIZARD_FINISH_NEVER_RE_ENABLED` **pós-janela**). Mão de árvore minúscula
   (tree≈0) NÃO serve (Fase 1 devolve cedo, sem raise).
4. Confirmar nos logs (passo 5c). **Repor o timeout a `60.0`** e construir/instalar o
   `.exe` de **produção** (timeout normal) — o build de smoke NÃO vai para produção.

### 5b. Caminho natural (alternativa, se calhar uma falha real em sessão)

Sem encolher nada: pôr ≥2 mãos e aproveitar uma falha pós-janela real (rara). Mesmos
critérios de log.

### 5c. Critérios de log (`C:\hrc\watcher_logs\hrc_watcher_*.log`)

- a mão falhada é marcada `.failed` e a fila avança (como antes);
- **no arranque da mão SEGUINTE** aparece:
  `[HRC-RESTART] mão anterior falhou pós-abertura-de-janela (cálculo/finish/export) — a reiniciar o HRC...`
- o HRC é morto+relançado e a mão seguinte **não falha por arrasto** ("setup failed"
  em cadeia deixa de acontecer);
- (opcional) numa mão de sucesso NÃO aparece o `[HRC-RESTART]` de pós-janela (só o de
  cada-N, se aplicável).

## 6. Push — bless do main

**Critério primário (preferido):** push **só depois** de o passo 5 confirmar o
`[HRC-RESTART]` pós-janela nos logs (via indução 5a, ou natural 5b).
`git push origin main` (commit `74f18ac` + estas notas).

**Critério de bless de RECUO** (decisão do Rui — para o push não ficar preso
indefinidamente se, mesmo com indução, não se observar o restart em sessão —
ex.: não foi possível correr o build de smoke, ou o HRC comportou-se de forma a
não chegar à Fase 2): blessar com **(a) instalação limpa verificada** (SHA do
instalado bate, 1 só exe) **+ (b) os 8 testes verdes** (`test_watcher_restart_post_window.py`),
e **confirmar o `[HRC-RESTART]` na PRIMEIRA falha pós-janela REAL** (monitorizar os
logs pós-bless). O fix é defensivo (`.get`-safe, sem novos símbolos no marshal) e
o bail limpo não muda — o risco do recuo é baixo.

Antes de qualquer push, o fix vive só em local.

## Rollback

Se o re-smoke falhar: **não** instalar/quedar o `.exe` pt79; reinstalar o `.exe`
anterior (Release `watcher-pt68`, SHA `222fc48d…3f57`) pelo seu `instala_pt68.bat`.
O source pt79 fica em local (não-pushed) para corrigir e re-build.
