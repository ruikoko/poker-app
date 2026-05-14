# Onboarding prompt — sessão pt25e (sucessora de pt25d)

Documento auto-suficiente. Cola este prompt no início de uma nova sessão Claude Code para arrancar pt25e sem precisar de pedir nada ao Rui. **Leitura obrigatória completa antes de qualquer acção.**

---

## 1. Quem é o Rui + modelo 3-actores

**Rui Dias** — jogador profissional MTT online (regs PKO mid-stakes, GG/PS/WN/WPN), residente em Aveiro. **Não é programmer.** Sabe ler código, intervém com instinto técnico afinado, mas a implementação é toda Claude. Pediu este projecto para automatizar o pipeline de estudo de mãos.

**3 actores:**
- **Rui** — decisor, dono do produto, executor manual (smoke real, Beelink physical, transferências de exe). Comunica em pt-PT corrente.
- **Claude Web (Sonnet 4.6 normalmente, Opus 4 quando complex)** — arquitecto e planeador. Pensa em alto nível, valida planos, valida outputs de Code. Tem acesso aos docs do projecto via uploads do Rui mas não corre código nem usa tools — tudo via prosa.
- **Claude Code (eu / tu)** — implementador. Lê código, escreve código, corre comandos. Tem o repo todo + tools (Read, Edit, Write, Bash, Grep, Glob). É invocado pelo Rui directamente; Web dá-lhe instruções via Rui (Web nunca fala directo a Code).

**Como funciona o trio na prática:** Rui descreve necessidade ao Web. Web devolve plano em prosa pt-PT + bloco markdown de instruções literais para Rui colar ao Code. Code executa, reporta. Rui leva report ao Web. Web valida ou pede iteração. Loop até closure.

## 2. Regras comunicação

- **PT-PT primeira ocorrência de termos técnicos.** "tree explosion (explosão da árvore de soluções)", "anti-cheat (scanner de processos das salas)". Anglicismos correntes na 2ª+ menção dentro da mesma resposta.
- **Prosa conversacional, não didáctica.** Rui não quer listas de bullet inflated nem "Let me explain X". Vai directo.
- **Instruções literais em bloco markdown.** Quando precisas que Rui colar/cole algo (comando, prompt para Web, ficheiro), embrulha em ```` ``` ```` bloco. Tudo o resto fora do bloco fica prosa.
- **Nunca especular.** Se não sabes, lê o código. Se não consegues, diz "preciso de Rui executar X para saber". Especulação inventa bugs que não existem e queima tempo.
- **Autonomia ampliada — paths livres SEM pedir aprovação per-edit:**
  - `backend/` — backend FastAPI
  - `frontend/` — React Vite
  - `tools/` — utilities locais (`hrc_adapter`, `watcher_src`)
  - `scripts/` — scripts ad-hoc (backfills, audits)
  - `docs/` — markdown
  - `_local_only/` — gitignored, binários grandes, venvs, decompilations
  - `backend/tests/` — pytest suite
  - `migrations/` — schema (se aplicável)
- **Autonomia ampliada — REQUER APROVAÇÃO EXPLÍCITA:**
  - `.env`, `secrets/`, `credentials.*` — segredos
  - Executáveis novos (.exe, .msi, binários)
  - Deletes (qualquer `rm`, `git rm`, ficheiros apagados)
  - Ficheiros **fora do repo** (e.g., paths absolutos `C:\hrc\`, `_local_only/` deletes)
  - **Token rotation** (Railway env vars, Discord token, etc.)
  - Commits + push (Rui aprova explicitamente cada commit feature em sessões pt-recentes)

## 3. Estado do projecto pós-pt25d

### Backend (Railway, deploy automático em push para `main`)

- **Host:** `poker-app-production-34a7.up.railway.app`
- **HEAD commit:** `3347fcf` — pt25d convention fix
- **Cross-site OK:** PS, GGPoker, Winamax, WPN/YaPoker. Helpers `derive_seats_in_preflop_order`, `derive_real_aggressor_position`, `derive_prune_downstream`, `derive_table_format`, `find_preflop_marker`.
- **Convenção HRC indices:** UTG=0 first-to-act preflop, SB=N-2, BB=N-1 (docs canonical — pt25d).
- **Suite pytest:** 266 PASSED (3 warnings pre-existentes — irrelevantes).
- **Templates HRC:** `backend/app/services/hrc_scripts/` (movido em pt25c de `tools/hrc_scripts/` por causa do Railway nixpacks só shipar `backend/`).
- **Manifest fields no `payouts.json` per-hand:**
  - `prune_aggressor: int|null` — HRC idx do primeiro raiser preflop
  - `prune_downstream: list[int]` — indices a prune downstream
  - `has_prune_script: bool` — se `script.js` foi escrito no zip
  - `prune_script_error: str|null` — repr da exception se geração falhou
  - `prune_index_convention: "hrc_docs_v1"|null` — traceability pt25d+

### Adapter (Beelink, source em `tools/hrc_adapter/`)

- **HEAD commit relevante:** `ac1f19a` (pt25 — `payouts_helpers.py` + `rewrite_script_path_in_payouts`)
- **Local Beelink:** `C:\hrc\adapter\hrc_adapter.py`
- **State file:** `C:\hrc\adapter\state.json`
- **Comportamento:**
  - Loop a cada N segundos: GET `/api/queue/hrc` (Bearer `HRC_WATCHER_API_KEY`).
  - Filtra hand_ids já em `state.json` (dedup).
  - Descompacta cada mão para `C:\Users\Administrator\Documents\Teste completo\queue\<hand_id>\`.
  - Reescreve `script_path` em `payouts.json` de `"script.js"` (relativo) para `C:\Users\Administrator\...\queue\<hand_id>\script.js` (absoluto).
  - Detecta zips em `done/Exports/<hand_id>.zip` (layout Baltazar) ou `done/<hand_id>.zip` (compat).
  - Injecta `meta.json` minimal se ausente.
  - POST para `/api/queue/hrc/results` com Bearer.

### Watcher (Beelink, recompilado em pt23)

- **HEAD commit relevante:** `b3968ee` (pt23 — backend hints + marshal swap + recompile via PyInstaller trampoline)
- **Local Beelink:** `C:\Users\riand\Desktop\hrc_watcher.exe` (~13.4 MB)
- **Source patches:** `tools/watcher_src/patched_funcs.py` (212 linhas; 4 funções marshal-swapped)
- **Bugs A/B/C/E (pt23): FIXED.**
  - A — `set_equity_model(wpos, equity_model)` aceita `multi_table_icm` (`'mu'`) ou `malmuth_harville_icm` (`'ma'`).
  - B — `get_player_count_from_hh` usa hint `max_players` do payouts.json.
  - C — `setup_scripting(wpos, script_path)` usa hint `script_path` do payouts.json.
  - E — `setup_hand` faz Next sobre página MTT Stacks (default Multi Table ICM) em vez de pendurar.
- **Bugs F-J (pt25d smoke): OPEN, target pt25e.** Detalhe abaixo §5.

### Pipeline ponta-a-ponta validado mecanicamente

```
poker-app backend (Railway)
   ↓ build_queue_zip → /api/queue/hrc → zip 42 mãos
adapter (Beelink)
   ↓ GET, dedup state.json, descompacta
   ↓ rewrite_script_path_in_payouts (relativo → absoluto)
HRC engine (Beelink)
   ↓ watcher extract + setup + 1ª run + ... ❌ falta 2ª run
   ↓ save_strategies (prematuro)
   ↓ export para done/Exports/<hand>.zip
adapter
   ↓ detect, _ensure_meta_in_zip, POST
   ↓ POST /api/queue/hrc/results
backend
   ↓ UPSERT hrc_jobs (status=done, result_zip_size)
```

Status: **mecanicamente OK**, mas conteúdo da árvore é parcial (sem prune avaliado em subtree refinada).

## 4. Pendência smoke real pt25d

- ✅ Indices certos chegam ao Beelink: `script.js` per-mão tem `let REAL_AGGRESSOR_POS = 0; let DOWNSTREAM_POSITIONS = [1, 2, 3];` para `WN-4699459877053923331-277-1778535900` INTERSTELLAR (validado visual por Rui).
- ✅ Manifest entry `prune_index_convention: "hrc_docs_v1"`.
- ❌ Watcher impede validação efectiva: faz 1ª run + save directo, sem 2ª run.
- **Precisa de pt25e (Bugs F-J + meta backend novo) ANTES de re-smokar.**

## 5. Bugs F-J + #META-AGGRESSOR-REAL-ACTION (pt25e — gatekeeper)

### #WATCHER-BUG-F-CI-TARGET-2ND-RUN 🔴 HIGH

A 1ª run usa CI Target 5.0 (default, exploração rápida). A 2ª run precisa de CI Target **10.0** para refinar subtree. Watcher actualmente set CI Target uma vez no setup.

**Fix:** split em `set_ci_target_initial(wpos, 5.0)` (pre-1ª run, antes do Calculate) + `set_ci_target_refine(wpos, 10.0)` (pre-2ª run, após Prune Action e antes do 2º Calculate).

### #WATCHER-BUG-G-SCOPE-SELECTED-SUBTREE 🔴 HIGH

A 2ª run tem de correr em Scope=`Selected Subtree`, não em `Full Tree`. Passos: (1) clicar dropdown Scope no painel da 2ª run, (2) seleccionar `Selected Subtree`, (3) **seleccionar a linha do sizing real do raiser inicial** na tree visual (raiz da subtree a refinar). Para (3) o watcher precisa de saber qual sizing o raiser fez na HH real. Depende de `#META-AGGRESSOR-REAL-ACTION`.

### #WATCHER-BUG-H-FLOW-ORDER-SAVE-LAST 🔴 HIGH

Fluxo actual: Setup → 1ª run → **save_strategies imediato**. Save deve ser último. Ordem correcta:

```
Setup → 1ª run → Prune Action (linha a linha downstream)
      → Selecção subtree + Scope=Selected Subtree + CI bump 10.0
      → 2ª run → save_strategies
```

Mover save_strategies da `setup_hand` para função `finalize_after_second_run`. **Reaproveitar a rotina actual do save_strategies para criar a similar do Prune Action** (mesma estrutura click+wait, alvo diferente).

### #WATCHER-BUG-I-FIRST-PANEL-WRONG-BUTTON 🟡 MED

Smoke devagar 14 Maio: Rui detectou botão errado no 1º painel pós-extract (Basic Hand Data), entre `select_bounty_mode` e `setup_scripting`. Repro pendente — identificar exactamente qual botão em smoke devagar dedicado pt25e (Rui executa step-by-step e regista).

### #WATCHER-BUG-J-PRUNE-ACTION-PER-LINE 🔴 HIGH

Watcher faz Prune Action **linha a linha** para cada player em `DOWNSTREAM_POSITIONS`, percorrendo a tree visual.

**CUIDADO armadilha UX HRC:** o context menu tem **2 entradas com "Prune"** — uma é **"Prune Action"** (queremos esta), outra é um Prune global mais agressivo. Watcher tem de seleccionar o texto exacto **"Prune Action"**. Coords + ordem das entradas no menu a confirmar em smoke devagar pt25e.

**Não confundir com o guard `getSizingsOpening` injectado pelo script.js:**
- `getSizingsOpening` = prune **scripted**, afecta árvore inicial pre-1ª run.
- `Prune Action` UI = prune **manual** sobre nós da subtree pré-2ª run.
- Os dois complementam-se.

### #META-AGGRESSOR-REAL-ACTION 🔴 HIGH (dependência backend)

Backend tem de injectar `aggressor_real_action` no `payouts.json` (ou `meta.json`) per-hand:

```json
{
  "aggressor_real_action": {
    "type": "raise",
    "size_bb": 2.0
  }
}
```

Permite ao watcher (Bug G passo 3) clicar a linha exacta do sizing real do raiser na tree HRC para a 2ª run.

**Implementação:**

1. Helper `derive_aggressor_real_action(hh_text, level_sb, level_bb) -> dict|None` em `backend/app/services/queue_export.py` — parseia primeira raise/bet preflop, converte chips → bb units relativos ao level da mão, devolve dict.
2. Injecção no manifest entry + payouts.json em `build_queue_zip`.
3. Tests pytest (5h UTG raise 2bb, raise 2.5bb, 3bb open, all-in shove, limp completion).

## 6. Bug K — pt25f (re-arquitectura template)

### #TEMPLATE-DYNAMIC-SIZINGS-PER-HAND 🟡 MED (pt25f+)

Template `mtt_advanced_20211029...bvb.js` actualmente declara sizings fixos top-of-file:
```js
let SIZES_OPEN_OTHERS = [2, ALLIN];
let SIZES_3BET_IP = [7.5, 12, ALLIN];
let SIZES_3BET_BB_VS_SB = [7, ALLIN];
// ...
```

Estes sizings inflam a árvore (solver explora cada um). Para que a árvore contenha apenas o sizing **real** da mão, backend injecta dinamicamente baseado na action sequence parseada da HH.

**Implementação:**

1. Generalizar `generate_hrc_script` para 2 substituições — (a) bloco prune existente, (b) cada `SIZES_*` top-of-file via regex.
2. Helper novo `derive_preflop_sizings(hh_text, level_sb, level_bb) -> dict[str, list[float]]` faz parsing completo (5+ raises sequenciais) e mapeia `bet_count + position → SIZES_* key`.
3. Tests pytest cobrindo open, 3-bet, 4-bet, 5-bet, squeeze, e edge cases.

**Por design substitui parte do que o prune via `getSizingsOpening` faz** — pode tornar o pt25 prune redundante na prática. Mantemos pt25 como defense-in-depth.

Depende implicitamente de `#META-AGGRESSOR-REAL-ACTION` (parsing comum).

## 7. Arquitectura watcher recompilação (procedimento pt23)

Em pt23 estabeleceu-se o procedimento marshal-swap + PyInstaller trampoline. Manter o mesmo workflow para pt25e:

1. **Editar** `tools/watcher_src/patched_funcs.py` — adicionar/modificar funções (são compiladas no host Python 3.12 e swapped no `co_consts` do module original).
2. **`ast.parse` + `compile` check** local antes de prosseguir.
3. **Marshal swap:** script `_local_only/watcher_decompile/swap_and_smoke.py` carrega o pyc original Apr19 (header-stripped), substitui code objects das funções patched, escreve `_local_only/watcher_decompile/repacked/hrc_watcher_apr19.pyc` **header-less** (importante: launcher Baltazar faz `marshal.load(f)` directo sem skip).
4. **Smoke harness** com mocks (`pyautogui`, `pygetwindow`, `pyperclip`, `os.makedirs` mocked). 8+ sub-tests por função alterada.
5. **PyInstaller via trampoline:** `_local_only/watcher_decompile/build_pyi/wrapper.py` (49 linhas, gitignored) faz `marshal.load` do launcher Apr19 intacto. **Importante:** adicionar `import re/json/shutil/glob/time/traceback/subprocess/zipfile/ctypes` no wrapper.py — PyInstaller analyzer só vê imports do wrapper, o main pyc é carregado via marshal.
6. **Build:** `pyinstaller --onefile wrapper.py` no `_local_only/watcher_decompile/build_pyi/`. Output: `dist/hrc_watcher.exe` (~13.4 MB).
7. **Smoke standalone** no PC principal antes de transferir (mock paths que falham é OK — só queremos confirmar arranque + import OK).
8. **Transferir para Beelink:** copy para `C:\Users\riand\Desktop\hrc_watcher.exe`. Rui executa a transferência manual via mecanismo combinado entre PC principal e Beelink (USB ou SMB).

Procedimento detalhado em `docs/JOURNAL_2026-05-13-pt23.md` blocks 4-5. Tools necessárias: `pycdc.exe` + `pycdas.exe` (zrax — pré-built em `_local_only/watcher_decompile/tools/`), VS 2022 Build Tools + CMake (já instaladas).

**Versões de build do watcher recompilado:**
- pyinstaller 6.20.0
- pyautogui 0.9.54, pygetwindow 0.0.9, pyperclip 1.11.0
- Python 3.12.0

## 8. Locais Beelink (paths exactos)

```
C:\hrc\adapter\hrc_adapter.py             ← adapter Python source
C:\hrc\adapter\state.json                  ← dedup state (apagar para forçar re-process)
C:\Users\Administrator\Documents\Teste completo\
    ├─ queue\<hand_id>\hh.txt
    │                 \payouts.json
    │                 \script.js           ← se prune fires
    ├─ done\Exports\<hand_id>.zip         ← layout default Baltazar
    └─ done\replied\                      ← dead code Baltazar (não usar)
C:\Users\riand\Desktop\hrc_watcher.exe    ← watcher recompilado
```

HRC instalação: Beelink `riand` user, perfil `Administrator` legacy preservado pelo reset Windows nuclear (importante — paths antigos do Baltazar continuam válidos em vez de re-config).

## 9. Tech debts pt25 ainda OPEN (lista breve)

Detalhe completo em `docs/TECH_DEBTS_INVENTARIO.md`:

- **#HRC-PRUNE-IN-GAP-DOWNSTREAM** 🔴 HIGH (gatekeeper, em hold até pt25e fechar)
- **#WATCHER-COMPLETE-FLOW** (umbrella) 🔴 HIGH — pt25e
  - #WATCHER-BUG-F-CI-TARGET-2ND-RUN
  - #WATCHER-BUG-G-SCOPE-SELECTED-SUBTREE
  - #WATCHER-BUG-H-FLOW-ORDER-SAVE-LAST
  - #WATCHER-BUG-I-FIRST-PANEL-WRONG-BUTTON
  - #WATCHER-BUG-J-PRUNE-ACTION-PER-LINE
- **#META-AGGRESSOR-REAL-ACTION** 🔴 HIGH — pt25e (dependência backend)
- **#TEMPLATE-DYNAMIC-SIZINGS-PER-HAND** 🟡 MED — pt25f
- **#FT-PLAYERS-DIFFERENT-FROM-REGULAR** 🟡 MED (pt26+) — herdado pt25
- **#BUY-IN-PKO-RATIO-EXTRACTION** 🟡 MED (pt26+) — herdado pt25
- **#BACKFILL-LOBBY-PLAYERS-LEFT-DISCORD-REFETCH** 🟢 LOW — herdado pt25
- Carry-overs pt22/pt23 vários (LOW/MED)

## 10. Links

### Commits do dia 14 Maio em main

```
3347fcf  pt25d: fix convention indices HRC scripting (UTG=0 docs canonical)
77ff496  pt25c: mover hrc_scripts/ para backend/ (fix Railway deploy) + escalar silent OSError para logger.error + manifest field prune_script_error
f32ed28  pt25b: robustez backend cross-site (markers WN/WPN + duplicate let fix + table_format detection + seats vazios) + 22 tests
```

### Commits chave anteriores

```
b3968ee  pt23 — watcher recompile + adapter fixes
ac1f19a  pt25 — payouts_helpers.py + rewrite_script_path_in_payouts (adapter)
cd94959  pt24 — queue_export injecta bounty_value_usd nas Seat lines (#HRC-GG-KOS-EXTRACTION)
```

### Documentos a consultar

- `docs/JOURNAL_2026-05-14-pt25b-c-d.md` — journal completo da sessão de hoje (3 commits + smoke real + bugs F-K)
- `docs/JOURNAL_2026-05-13-pt23.md` — descompilação watcher + marshal swap (procedimento de referência para pt25e)
- `docs/TECH_DEBTS_INVENTARIO.md` — secção "Estado actual (14 Maio 2026 pós-pt25d)" tem entries detalhados de cada bug F-J + K
- `CLAUDE.md` — secções "Estado actual" + "FASE 3 HRC" + "Cinco/seis/sete fontes de input" + "Variáveis de ambiente"
- `docs/PAPEIS_E_RESPONSABILIDADES.md` — modelo 3-actores formal
- `docs/REGRAS_NEGOCIO.md` — regras duras (especial: regra de ouro sobre processos suspeitos durante sessões de poker)
- `docs/MAPA_ACOPLAMENTO.md` — mapa técnico actualizado

## 11. Primeira acção sugerida

**Lê este documento na íntegra primeiro.** Depois lê em paralelo:

1. `docs/JOURNAL_2026-05-14-pt25b-c-d.md` (~5 min, contexto completo da sessão imediatamente anterior)
2. Secção "Estado actual (14 Maio 2026 pós-pt25d)" do `docs/TECH_DEBTS_INVENTARIO.md` (~3 min, detalhe técnico exacto de cada bug)
3. `backend/app/services/queue_export.py` — função `_build_watcher_hints` + `build_queue_zip` (vais ter de adicionar `aggressor_real_action` aqui)
4. `tools/watcher_src/patched_funcs.py` — funções actuais marshal-swapped (vais ter de adicionar/modificar para Bugs F-J)

**Não arrancar implementação até Rui dizer "arranca pt25e"** ou equivalente. Rui vai dar ordem por etapas (provavelmente backend primeiro = #META-AGGRESSOR-REAL-ACTION, depois watcher Bugs F-J).

**Token rotation:** `HRC_WATCHER_API_KEY` actual ainda é o de pt21 (mask `_5YENfRZai...qHT7EZOS`). Rotacionar fica deferido até oportunidade (tech debt `#TOKEN-ROTATION-DEFENSIVE-PT23` open).

**Workaround `backend/.env` encoding cp1252:** ainda válido — qualquer script local que importe `app.db` parte com UnicodeDecodeError. Usar `railway variables --kv` para extrair env vars; query directa via public proxy do Postgres com password do service `poker-app`.

Não correr a app HRC nem o watcher no PC principal sem confirmação do Rui (regra de ouro CLAUDE.md — anti-cheat das salas pode scanner processes durante sessões de poker).

---

**Welcome to pt25e. Boa sessão.**
