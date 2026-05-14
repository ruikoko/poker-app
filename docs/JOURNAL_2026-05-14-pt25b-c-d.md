# Sessão 14 Maio 2026 — pt25b + pt25c + pt25d

Sessão consolidada de ~10h: três pontas (pt25b, pt25c, pt25d) sobre o mesmo gatekeeper `#HRC-PRUNE-IN-GAP-DOWNSTREAM`. Backend acabou completo. Smoke real parcial pós-pt25d expôs **5 bugs novos do watcher (F-J)** + **1 feature de re-arquitectura (K)** — abertos para pt25e/pt25f.

## Resumo

| pt | Foco | Commit | Suite |
|---|---|---|---|
| **pt25b** | Robustez backend cross-site (PS/GG/WN/WPN) | `f32ed28` | 264 PASSED |
| **pt25c** | `hrc_scripts/` move para `backend/` (fix Railway deploy) + manifest field defensivo | `77ff496` | 264 PASSED |
| **pt25d** | Convention indices fix (UTG=0 docs canonical) | `3347fcf` | 266 PASSED |

**Smoke real pt25d:** indices certos chegam ao Beelink no `script.js` (validado visual por Rui). Watcher é o gap — só faz 1ª run + save directo, sem 2ª run em Selected Subtree.

## Detalhe pt25b — robustez cross-site (commit `f32ed28`)

**Problema descoberto pré-pt25b:** o helper `derive_seats_in_preflop_order` (pt25 original) assumia formato PS/GG (`*** HOLE CARDS ***` + `nick: raises X to Y`). Para WN/WPN o parser falhava em silêncio (markers diferentes, action sem colon). Smoke pré-pt25b mostrou que mãos Winamax (a maioria do volume real) nunca chegavam a ter `aggressor` identificado → prune nunca disparava.

### 4 etapas, 4 tech debts fechados

| ETAPA | Tech debt | Como fechou |
|---|---|---|
| 1 | **#HH-FORMAT-WINAMAX-MARKERS** | Helper novo `find_preflop_marker(hh_text)` aceita `*** HOLE CARDS ***` (PS/GG/WPN) **e** `*** PRE-FLOP ***` (Winamax) — devolve a posição mais cedo. Regex `_PREFLOP_OPEN_RE` ganha colon opcional `(?::)?` para action lines sem colon (WN/WPN: `nick raises X to Y`). |
| 2 | **#GENERATE-HRC-SCRIPT-DUPLICATE-LET** | Bug: `generate_hrc_script` inseria bloco `let REAL_AGGRESSOR_POS = ...` antes do `let ALLIN = 9999` no template, mas o template B2 (pt25 PASSO B2) **já tinha** placeholder com o mesmo nome → 2 declarações `let` mesmo identificador → JS SyntaxError no Nashorn. Fix: regex `_PRUNE_PLACEHOLDER_RE.subn` faz substitution in-place no placeholder existente. **Idempotente** (rodar 2× com mesmos args produz output byte-igual). Fallback legacy mantido para templates sem placeholder. |
| 3 | **#TABLE-FORMAT-DETECTION** + **#SEATS-EMPTY-TABLE-LAYOUT** | Helper novo `derive_table_format(hh_text)` parsa `\b(\d+)-max\b` (universal nos 4 sites). `derive_seats_in_preflop_order` walks apenas pelos seats sentados (não pelo table_format regular), tratando 6-max-com-5-sentados como 5-handed (CO desaparece nos labels). Funcionou para INTERSTELLAR Winamax pós-eliminação. |
| 4 | Smoke pré-pt25c | Dry-run sample WN INTERSTELLAR confirmou aggressor identificado correctamente. |

### Suite

Adicionou 22 tests cross-site reais (sample HHs de cada site PS/GG/WN/WPN) + sintéticos para edge cases. **264 PASSED** total.

## Detalhe pt25c — Railway deploy fix + manifest defensivo (commit `77ff496`)

**Diagnóstico pós-pt25b deploy:** smoke real Beelink puxou 42 mãos do `/api/queue/hrc`, mas pasta `WN-4699459877053923331-277-1778535900` continha **apenas** `hh.txt` + `payouts.json` (sem `script.js`, sem `meta.json`). Backend logs Railway: zero erros, zero warnings. **Bug silencioso.**

### Root cause

`_PRUNE_JS_TEMPLATE_PATH` apontava para `../../../tools/hrc_scripts/...bvb.js` (relativo desde `backend/app/services/queue_export.py`). Railway nixpacks **só ship `backend/`** para o container — `tools/` ficava fora. `open(template_path)` levantava `FileNotFoundError`, capturada por `try/except OSError` em `_try_build_prune_script`, com `logger.warning` (level baixo). Production Railway corre com `WARNING` filtrado por default → log nunca apareceu.

### 2 fixes

| ETAPA | Fix |
|---|---|
| 1 | **A — mover `hrc_scripts/`** de `tools/hrc_scripts/` (repo root) para `backend/app/services/hrc_scripts/`. 9 ficheiros (8 `.js` variants + 1 `README.txt`) movidos via `git mv`. `_PRUNE_JS_TEMPLATE_PATH` actualizado para path absoluto via `os.path.join(os.path.dirname(__file__), "hrc_scripts", "...")`. Railway agora vê o template. |
| 2 | **D — escalar warning para error + manifest field defensivo.** `_try_build_prune_script` mudou signature de tuple-3 para tuple-4: agora devolve `(aggressor, downstream, js, error)`. Catch do `OSError` faz `logger.error` (em vez de warning) com path + repr da exception, e passa `error=str` para o tuple. `build_queue_zip` propaga ao manifest entry: campo novo `"prune_script_error"` — `None` quando OK ou condição-não-satisfeita, `"FileNotFoundError: ..."` quando falha I/O. Garante que falhas similares no futuro são visíveis no zip recebido pelo adapter (sem precisar de cruzar Railway logs). |

Suite **264 PASSED** (inalterada; 2 tests novos do manifest field). Smoke pós-deploy: zip do `/api/queue/hrc` agora contém `script.js` per-mão.

## Detalhe pt25d — convention indices fix (commit `3347fcf`)

**Descoberta inesperada:** smoke pós-pt25c mostrou que o `script.js` chegava ao Beelink e era injectado pelo adapter no payouts.json (`script_path="script.js"` reescrito para path absoluto pós-unzip). Mas a tree do HRC continuava enorme — prune visualmente não fazia diferença. Web decidiu investigar a fundo lendo os **docs oficiais HRC scripting**.

### Bug silencioso descoberto via docs HRC

Docs oficiais declaram: **convenção HRC scripting de índices é `UTG=0` (first-to-act preflop), `SB=N-2`, `BB=N-1`.** O nosso backend (desde pt25 original) emitia índices na convenção `SB=0, BB=1, UTG=2, ..., BTN=N-1` (rotativo desde SB).

Consequência: `script.js` tinha `DOWNSTREAM_POSITIONS=[3,4,0]` (na nossa convenção velha, para INTERSTELLAR 5-handed com UTG opener) mas `ctx.getActivePlayer()` do HRC retorna índices na convenção docs. O guard `DOWNSTREAM_POSITIONS.indexOf(player) !== -1` no template **nunca matched** → `getSizingsOpening` nunca devolvia `[]` → prune dead → tree continuava como sempre.

### Diagnóstico por triangulação

Web pediu cat de 2 ficheiros:
- Template original (pre-patch) `mtt_advanced_20211029...bvb.js`
- Output actual `generate_hrc_script(_TEMPLATE_PATH, agg, ds)` para INTERSTELLAR

Comparação revelou: o template compara `player == ctx.getPlayerIndexButton/SmallBlind/BigBlind()` — API vs API, **convenção-agnóstico**. Mas o nosso `indexOf(player)` é API vs Python-emitted — tem de viver na mesma convenção. Confirmado bug backend-only.

### Fix em 3 etapas

| ETAPA | Detalhe |
|---|---|
| **1 — helpers backend** | `derive_seats_in_preflop_order`: fórmula nova `first_to_act_offset = 0 if n == 2 else 3` (HU agente é botão; N≥3 = botão+3 wraps mod N). Indices contíguos `0..N-1` por construção. `derive_real_aggressor_position`: drop do early-return SB-aberto (era artefacto da conv velha onde SB=idx 0). `derive_prune_downstream`: refactor radical — drop params `seated_hrc_indices` + `table_format`, add `n_seated` obrigatório, fórmula reduzida a `list(range(aggressor+1, n_seated-1))` (BB N-1 excluído por construção). Guard novo `K >= N-2 → []` (degenerate SB/BB aggressor). `_POSITION_LABELS_BY_N` 8 entries reescritos (cada lista começa em UTG/BTN/BU consoante N, termina em BB). HU explicitamente suportado. |
| **2 — reescrita tests** | 28 tests reescritos para nova convenção + 20 sintéticos novos (`5h/6max/8max` series cobrindo cada posição × N + HU + degenerate cases + defensive guards + n_seated bounds). Suite **264 → 266 PASSED**. Zero regressões noutros módulos. |
| **3 — manifest field + deploy** | Campo novo `"prune_index_convention": "hrc_docs_v1"` no manifest entry quando `has_prune_script=True`, `None` caso contrário. Traceability futura para distinguir zips pré-pt25d (buggy SB=0) vs pós-pt25d. 2 tests pytest. Commit `3347fcf` push → Railway deploy → `/health 200`. |

### Dry-run INTERSTELLAR pós-pt25d

```
seats (5-handed):
  hrc_idx=0 | seat=5 | UTG | blueballs67  ← aggressor
  hrc_idx=1 | seat=1 | HJ  | yousnouf75   ← downstream
  hrc_idx=2 | seat=2 | BTN | imbagosu     ← downstream
  hrc_idx=3 | seat=3 | SB  | Beu_Teu      ← downstream
  hrc_idx=4 | seat=4 | BB  | thinvalium   ← excluído (BB nunca abre in-gap)

Injectado no script.js:
  let REAL_AGGRESSOR_POS = 0;
  let DOWNSTREAM_POSITIONS = [1, 2, 3];
```

**Antes (pt25b/c, buggy):** `REAL_AGGRESSOR_POS = 2`, `DOWNSTREAM_POSITIONS = [3, 4, 0]` — mesmos jogadores lógicos (UTG/HJ/BTN/SB) mas em convenção SB=0 → `indexOf` no template nunca match → prune dead.

## Smoke real pt25d — passo a passo

1. **Rui apaga state Beelink:** `del C:\hrc\adapter\state.json` (forçar re-processamento de mãos previamente vistas).
2. **Re-pull do `/api/queue/hrc`** com Bearer token via adapter. Zip 42 mãos chega, descompacta para `C:\Users\Administrator\Documents\Teste completo\queue\`.
3. **Validação visual `script.js`** — Rui abre `WN-4699459877053923331-277-1778535900\script.js` num editor. Confirma `let REAL_AGGRESSOR_POS = 0;` + `let DOWNSTREAM_POSITIONS = [1, 2, 3];`. ✅ Indices em convenção docs canonical.
4. **Watcher arranca** com a mão na queue. Extract OK, abre Tournament Setup, navega Basic Hand Data, Bounty Mode, Scripting (carrega `script.js`), Calculate.
5. **1ª run completa** — solver corre com guard `getSizingsOpening` activo (downstream players retornam `[]` em opening scenarios). Tree visualmente mais pequena que pt25c, mas ainda não validável quantitativamente (Rui não capturou tree size na 1ª run isolada).
6. **Watcher salta directo para save_strategies** após 1ª run. Tree exportada é a da 1ª run, sem 2ª run em Selected Subtree, sem Prune Action manual por linha downstream, sem CI bump 10.0.
7. **Smoke termina prematuramente** — zip exportado vai para `done/Exports/`, adapter detecta, faz POST `/api/queue/hrc/results`. Backend recebe, faz UPSERT em `hrc_jobs`. **Mas o conteúdo da árvore é parcial.**

### 5 bugs descobertos durante smoke devagar

Rui correu o watcher em modo "smoke devagar" (step-by-step, observando cada acção UI):

- **Bug F:** CI Target deve passar de 5.0 (1ª run, exploração) para 10.0 (2ª run, refinação subtree).
- **Bug G:** 2ª run precisa de Scope=`Selected Subtree` + selecção da linha do sizing real do raiser (precisa de meta backend novo).
- **Bug H:** Ordem do flow está errada — save_strategies está no fim da 1ª run, deve ser no fim da 2ª run. Reaproveitar a rotina do save_strategies para criar a similar do Prune Action.
- **Bug I:** Botão errado clicked no 1º painel (Basic Hand Data) — Rui detectou visualmente mas sem screenshot/log; repro pendente pt25e.
- **Bug J:** Prune Action linha a linha downstream do raiser inicial. **CUIDADO:** o context menu HRC tem 2 entradas com "Prune" — queremos especificamente **"Prune Action"** (prune da sizing específica clicada), não o Prune global agressivo.

### 1 dependência backend nova

**#META-AGGRESSOR-REAL-ACTION:** payouts.json/meta.json tem de ganhar campo `aggressor_real_action = {type, size_bb}` extraído da HH parseada. Sem este dado o watcher (Bug G passo 3) não sabe que linha clicar para a 2ª run.

### 1 feature de re-arquitectura (pt25f)

**Bug K (#TEMPLATE-DYNAMIC-SIZINGS-PER-HAND):** template tem sizings fixos (`SIZES_OPEN_OTHERS = [2, ALLIN]`, `SIZES_3BET_IP = [7.5, 12, ALLIN]`, etc.) que inflam a tree. Para reduzir drasticamente, backend injecta dinamicamente os sizings reais parseados da HH. Por design substitui parte do que o prune via `getSizingsOpening` faz (mas mantemos como defense). Trabalhoso; depende de **#META-AGGRESSOR-REAL-ACTION**.

## Próxima sessão — pt25e (Bugs F-J + meta) + pt25f (Bug K dinâmico)

**Prioridade pt25e (gatekeeper de produção, em hold):**
1. Backend: helper `derive_aggressor_real_action(hh_text, level_sb, level_bb)` + injecção no `payouts.json` (#META-AGGRESSOR-REAL-ACTION).
2. Watcher: split CI Target (F), Scope+selecção (G), re-order save (H), debug 1º painel (I), Prune Action linha a linha (J).
3. Recompilar watcher via PyInstaller trampoline → transferir para Beelink `C:\Users\riand\Desktop\hrc_watcher.exe`.
4. Smoke real validado: 2ª run corre, tree exportada tem subtree refinada. Reportar tree size pré/pós para confirmar o gatekeeper.

**pt25f (após pt25e estabilizar):** Bug K — generalizar `generate_hrc_script` para 2 substituições (prune block + SIZES_* dinâmicos). Helper `derive_preflop_sizings(hh_text)` parsea action sequence completa.

## Commits do dia em main

```
f32ed28  pt25b: robustez backend cross-site (markers WN/WPN + duplicate let fix + table_format detection + seats vazios) + 22 tests
77ff496  pt25c: mover hrc_scripts/ para backend/ (fix Railway deploy) + escalar silent OSError para logger.error + manifest field prune_script_error
3347fcf  pt25d: fix convention indices HRC scripting (UTG=0 docs canonical)
```

Backend suite final: **266 PASSED**. Zero regressões em outros módulos.

## Lições

- **Decompilação de docs externos é diagnóstico válido.** O bug pt25d só foi detectável por leitura dos docs HRC oficiais. Sem essa investigação, pt25b/c/d ficariam deployed e o gatekeeper continuaria nominalmente "fechado" mas funcionalmente quebrado.
- **Bugs silenciosos custam caro em pipelines longos.** pt25c foi um warning suprimido em produção (Railway log level). pt25d foi convenção desencontrada onde nada gritava (script.js parecia certo, indexOf simplesmente nunca match). Manifest field `prune_index_convention` foi adicionado em pt25d especificamente para evitar a próxima divergência silenciosa.
- **Smoke devagar > smoke rápido para validar fluxos UI.** O Rui apanhou Bugs F-J em smoke devagar; smoke automático teria visto "extract OK + run OK + save OK + POST OK" e dado green sem detectar que a 2ª run nunca aconteceu.
