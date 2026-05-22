# Inventário Tech Debts — 4-Mai 2026 pt13 (fechada)

Compilação read-only baseada em journals (23-24 Abr → 29-Abr pt6), VALIDACAO_END_TO_END §6/§7/§11, MAPA_ACOPLAMENTO, git log, e leitura directa do código.

Substitui os fragmentos espalhados pelos vários docs como **single source of truth** sobre tech debts pendentes. Para descrição detalhada de cada fix fechado, consultar journal/commit correspondente.

---

## Estado actual (22 Maio 2026 — pt30-pt34)

Sessão pt30-pt34 (madrugada). **Fecho de toda a cadeia da 2ª run do HRC**
(Selected Subtree), ponta-a-ponta no Beelink, com `.zip` final de ~23 000
nós (equivalente ao Save As manual). 6 commits feature em main, todos no
robot watcher (`tools/watcher_src/patched_funcs.py` + 2 ficheiros de teste);
`.exe` **não recompilado** (passo separado). Suite **550 → 569 PASSED**.
Detalhe em `docs/JOURNAL_2026-05-22-pt30-pt34.md` e
`docs/HRC_ANATOMIA_OPERACIONAL.md` v5.

Discovery transversal: **o HRC usa SWT, não Swing** — widgets expostos como
child windows nativas ao Win32 (`BM_CLICK`, `IsWindowEnabled`,
`GetWindowText`). Toda a sessão assenta nisto.

### Tech debts fechados em pt30-pt34 (6)

| ID | Como fechou |
|---|---|
| **#START-CALC-SELECTED-SUBTREE-NO-POPUP-OPEN** (CRIT, aberto pt26) | **pt32 v1 + v2** (`61dfa5f`/`c9c8818`). Causa raiz isolada por smoke + logging `[calc-diag pre-click]`: `_click_calculate_button` usava a `wpos` do wizard "Hand Setup" — **já fechado** no Finish da 1ª run — como origem do click do Play. Log: `coord=(1174,64)` com `wpos=(970,0,...)` → 1174=970+204, click em zona vazia. Fix: (a) coord Y 59→64 (a 1ª run usa 64 e funciona); (b) origem `wpos` → `find_hrc()`, igual à 1ª run do Baltazar OG (`hrc.left+204, hrc.top+64`). `find_hrc()` None → WARN + raise. Resultado: **popup Nash abre.** |
| **#START-CALC-SELECTED-SUBTREE-OK-CLICK-FAILS** (aberto+fechado pt33) | **pt33 v1** (`867460c`). Smoke pt32 v2 mostrou que o popup abre e os cliques intra-popup (scope, Selected Subtree, CI) funcionam, mas o OK por `Enter` não era registado → popup ficava aberto e parado, 2ª run não disparava. Snapshot Win32 (`check_nash_popup_children`) mostrou o popup como dialog `#32770` com Button OK **exposto** (`class='Button' text='OK'`). Fix: substituir Enter por `EnumChildWindows` + `BM_CLICK` no hwnd (`_find_nash_popup_hwnd` + `_find_ok_button` + `_click_ok_in_popup`), sem fallback Enter. Resultado: **popup fecha, 2ª run dispara.** |
| **#WAIT-FOR-RUN-COMPLETION-2A-RUN-FALSE-NEGATIVE** (aberto+fechado pt34) | **pt34 v1** (`e58c517`). A 2ª run disparava mas `_wait_for_run_completion` dava timeout 30s a "esperar a janela aparecer", porque procurava título exacto "Hand Setup" e a janela de progresso da 2ª run chama-se **"H-\<hand_id\>: Monte Carlo Sampling"**. Fix: param `match_substring` + helper `_find_progress_window_title` (None → FindWindowW exacto; preenchido → EnumWindows substring case-insensitive). 1ª run inalterada. Resultado: 2ª run esperada até ao fim real (~14 min). |
| **#WAIT-FOR-CALCULATION-FALSE-POSITIVE-MEMORY-HEURISTIC** (aberto+fechado pt31) | **pt31** (`0f159bc`). A heurística de memória do `wait_for_calculation` (Baltazar OG, instalada pt29-v3) deu falso positivo no smoke pt30 (declarou fim da 1ª run aos 48s = 15s+3×10s, com a run ainda a correr). Substituída por `_wait_for_run_completion`, que polla a janela de progresso top-level (sinal **binário**). `wait_for_calculation` fica no namespace mas já não chamada. |
| **#WIZARD-FINISH-DISABLED-DURING-TREE-CALC** (aberto+fechado pt30) | **pt30** (`52aef9c`). Diagnóstico SWT (`check_wizard_children_polling`) provou que ao carregar o script o HRC desabilita o Finish enquanto calcula o tree size (~1.7s); o slow-click pt29-v2 caía num botão **disabled** (causa do smoke pt29-v3 falhar). Fix: `_wait_for_finish_ready` espera a transição enabled→disabled→enabled via Win32 (`IsWindowEnabled`) antes do slow-click. Instância isolada `_pt30_user32` para não colidir argtypes com o launcher Baltazar. |
| **#FINALIZE-NEVER-FIRES-ON-NO-OP** (MED, aberto pt26) | Coberto pelo wiring do `second_run_dispatched` em `setup_hand`: `start_calculation_selected_subtree` devolve bool; `False` (popup não abriu) → WARN explícito antes do finalize; `True` → espera a 2ª run terminar antes do export. Com a cadeia pt32-pt34 a funcionar, o caminho `True` é o normal. |

### Tech debts novos abertos em pt30-pt34 (2)

| ID | Severidade | Resumo |
|---|---|---|
| **#CURSOR-ANOMALY-POST-SAVE-AS** | 🟢 LOW | Observação visual do Rui no smoke pt34: após o Save As, o cursor da Strategy Table fica na **2ª linha (EP)**. Origem desconhecida. Não bloqueia o flow actual (export já aconteceu), mas pode afectar uma futura 3ª run ou navegação encadeada. Investigar origem (efeito secundário do Save As? do export patch?). |
| **#WIZARD-FINISH-FALSE-POSITIVE-STATE-CHECK** | 🟢 LOW | `verify_wizard_finished` (state-check WARN-only pós-Finish, pt29-v1) verifica **cedo demais** — a janela "Hand Setup" ainda está presente no instante da verificação, gera WARN espúrio (`janela "Hand Setup" ainda presente apos click + activate`), mas a 1ª run efectivamente arranca. Fix: pequeno settle/poll antes de verificar, ou retirar o WARN. Não-bloqueante. |

### Tech debts confirmados abertos (3)

| ID | Severidade | Estado |
|---|---|---|
| **#HRC-BOUNTY-HARDCODED-50PCT** | 🟡 MED | **Continua aberto.** O watcher mete sempre `Bounty Mode PKO 50%` (via `select_bounty_mode` legacy + print "KO detetado — a selecionar Bounty Mode PKO 50%"). Nuance: o `progressiveFactor` no `payouts.json` **é** data-driven (lobby vision: 0.5/0.33/0.25/0.0); o que está hardcoded é o **dropdown do watcher**, que ignora esse valor. Fix: ler `progressiveFactor`/`tournament_format` e seleccionar a opção certa. Alta prioridade (ver `docs/PENDENTES.md`). |
| **#HRC-TOTAL-CHIPS-MISSING** | 🟡 MED | **Continua aberto.** `chips: null` no `payouts.json` (ainda visível no log: `Total chips: None`). É o total de fichas em jogo; o HRC precisa dele para o chip average / ICM. Fonte: `Average Stack × Players Left` do lobby. Ver `HRC_ANATOMIA_OPERACIONAL.md` §12.8. |
| **#CI-TARGET-INITIAL-NOT-CALIBRATED** (= antigo Bug F, pt25e Bloco 2) | 🟢 LOW | **Continua aberto.** Coords do CI Target inicial da 1ª run no main UI nunca calibradas (`CI_TARGET_FIELD_X/Y = 0`) → `_set_ci_target_common` degrada para Enter (funciona). Log: `[WARN] CI Target initial: coords não calibrados`. Calibrar em smoke devagar; não-bloqueante. |

### Estado da Fase 3 HRC pós-pt34

- Cadeia da 2ª run (Selected Subtree) **funcional ponta-a-ponta** ✓
- Smoke real **mecânico** ✓ + **funcional** ✓ (`.zip` ~23 000 nós)
- Pendente: **validação formal** dos nós vs Save As manual (alta prioridade,
  `docs/PENDENTES.md`) + `#HRC-BOUNTY-HARDCODED-50PCT`.

---

## Estado actual (21 Maio 2026 — pt29)

Sessão pt29 (cascata de fixes do robot HRC, smoke real com `GG-5944816316`).
Detalhe completo em `docs/JOURNAL_2026-05-21-pt29.md` e
`docs/HRC_ANATOMIA_OPERACIONAL.md` v4. Watcher recompilado pt29-v1/v2/v3.

### Tech debt novo aberto em pt29 (1)

| ID | Severidade | Resumo |
|---|---|---|
| **#HRC-BOUNTY-HARDCODED-50PCT** | 🟡 MED | O robot Baltazar OG tem o Bounty Mode hardcoded em PKO 50% na heurística "KO detetado → selecionar Bounty Mode PKO 50%". Para suportar PKO 25% e Mystery KO temos de ler o valor real do `tournament_format` parsed do TS e selecionar a opção correspondente no dropdown do HRC. Impacto: cálculos para torneios não-PKO-50% têm Bounty Mode errado. |

### Bugs do robot resolvidos em pt29 (nunca foram tech debts formais)

Descobertos e fechados na mesma sessão pt29 via smoke real — registados
aqui para histórico (não tinham entry própria no inventário):

| Bug | Como fechou |
|---|---|
| Finish click silenciosamente ignorado (HRC Java perde click instantâneo) | **pt29-v2** (`cb4c520`): slow-click `mouseDown → sleep(0.15) → mouseUp` + activate pré-click + state check pós-click via título "Hand Setup". |
| 2ª run começava antes da 1ª terminar (e Save As antes da 2ª) | **pt29-v3** (`3b9d72c`): `wait_for_calculation()` (Baltazar OG, já existia inutilizada) chamada após 1ª run e após 2ª run (esta condicionada a `second_run_dispatched is True`). Heurística: memória HRC estável >100 MB / variação <20 MB por 3 ciclos de 10s. |
| "Save As dialog não aparece em 20s" | Provavelmente resolvido em cascata pelo wait da 2ª run (pt29-v3) — **a confirmar com o resultado do smoke pt29-v3** (por arrancar à hora deste closeout). |

---

## Estado actual (19-20 Maio 2026 pós-pt27 closeout)

Sessão pt27 fechada com **1 commit feature em main** (`7de8df6`, 3 fixes
backend HRC) + commit docs (este). Bloco A (read-only) descobriu 1
regressão antiga não-fixada (`study_state` desde 18 Abr). Bloco B (etapa
2) entregou 3 fixes ao pipeline `/api/queue/hrc`. Bloco C (fix funcional
do `.exe`) **não atacado** — fica para pt28. Suite **449 → 455 PASSED
(+6 líquidos)**.

Re-classificação operacional: smoke A (rollback `.exe` pt25d) confirmou
fragilidade da baseline anterior (40 de 41 mãos pulled em 14 Maio nunca
chegaram a `done`). O caminho não é restaurar pt25d — é fixar
`#START-CALC-SELECTED-SUBTREE-NO-POPUP-OPEN` em pt28.

### Tech debts fechados em pt27 (3)

| ID | Como fechou |
|---|---|
| **#CI-DEFAULT-MISMATCH** | Backend `_DEFAULT_CI_TARGET_FIRST_RUN = 5.0` → `_DEFAULT_CI_TARGET = 10.0` em `services/queue_export.py` (`7de8df6`). Watcher já hardcode-passa 10.0 na 2ª run → 1ª e 2ª agora alinhadas. Decisão product Rui: opção (ii) "alinhar ambos em 10". |
| **#DERIVE-MAX-PLAYERS-HERO-REGEX-GG** | Aberto + fechado em pt27. 3 sub-bugs em `services/derive_max_players.py`: (a) `_HERO_RE = ^Dealt to (\S+)` apanhava 1º "Dealt to" (em GG pós-`_replace_hashes` todos os 8 seats têm essa linha); (b) `_SEAT_RE`/`_ACTION_RE` com `\S+` truncavam nicks com espaços tipo "Andrii Novak"; (c) `_SEAT_RE` matchava SUMMARY `Seat 6: Hero collected (X)` sobrescrevendo seats[6]. Fix: `_HERO_RE` exige ` \[`; `\S+` → `.+?`; parsing restrito ao header pré-`*** HOLE CARDS ***`. Mão real `GG-5944816316`: `max_players` 4 → 6. +1 test. Commit `7de8df6`. |
| **#COMPUTE-TARGET-NODE-OFFSET-USES-WRONG-PLAYER-COUNT** | Aberto + fechado em pt27. `compute_target_node_offset` usava `max_players` (redução ICM) como input para `strategy_table_positions`. Errado — Strategy Table HRC tem 1 linha-base por jogador real sentado. Para `GG-5944816316`: `max_players=6` fazia `MP` cair fora de `strategy_table_positions(6)=[UTG,HJ,CO,BU,SB]` → offset=None. Fix: param renomeado para `seats_at_table`; caller passa `len(derive_seats_in_preflop_order(hh_text))` em vez de `hints.get("max_players")`. Mão real: offset null → 4. Tests renomeados + 1 test novo. Commit `7de8df6`. |

### Tech debts novos abertos em pt27 (4)

| ID | Severidade | Resumo |
|---|---|---|
| **#STUDY-STATE-REGRESSION-HH-IMPORT** | 🟡 MED | Regressão silenciosa desde commit `15cb9b3` (2026-04-18, "feat: consolidate update v8.5"). Antes, `_insert_hand` tinha default `study_state='mtt_archive'` e `import_.py` não passava o arg → bulk HH imports iam para `mtt_archive` (conforme spec CLAUDE.md §"MODELO DE DADOS E FLUXO v2"). Pós-`15cb9b3`, `import_.py:311` e `:335` passam explicitamente `study_state='new'`, anulando o default. Pt13 (5 Maio) notou "1172 hands all in new" no journal mas adoptou-o como facto consumado em vez de fixar. Auditoria pt27 confirmou: 4258/4258 hh_import 7d em `new`, 0 em `mtt_archive`. UI sobreviveu por filtrar por tags em vez de `study_state`. Dashboard counter "mãos por estudar" inflacionado. **Fix conceptual:** remover `, study_state='new'` das 2 linhas em `import_.py:311/335` (default `mtt_archive` toma conta) + migration one-shot `UPDATE hands SET study_state='mtt_archive' WHERE origin='hh_import' AND study_state='new' AND entry_id IS NULL AND screenshot_url IS NULL`. Volume estimado ~25k mãos. **Decisão product pendente** antes de fix: Rui ainda quer a spec original "bulk imports invisíveis na página Mãos"? Se mudou de ideia (querer ver tudo na página Mãos), regressão vira feature pelo silêncio e a tech debt fecha por declaração. |
| **#WINAMAX-TOURNAMENT-SUMMARIES-PIPELINE** | 🟡 MED | Pipeline `tournament_summaries` é **GG-only**. Parser em `routers/tournament_summaries.py` reconhece header GG `Tournament #<tn>`; endpoint `/api/tournament-summaries/import` aceita `.txt`/`.zip`; UI em `Tournaments.jsx` faz upload. Para Winamax, workflow normal de Rui é upload manual de SS lobby (sem TS). Confirmado por Rui em pt27. **Impacto:** `tournament_resolver` TIER 0 (autoritativo, sem janela) só dispara para mãos GG. Mãos Winamax dependem 100% de TIER 1 (`tournaments_meta`) ou TIER 2 (`hands` fallback) — janela temporal apertada. Auditoria pt27 mostrou que 4/10 lobby failures 7d eram Winamax com `start_time` fora da janela `[posted_at-12h, posted_at-30min]`. **Fix conceptual:** espelhar pipeline GG para Winamax — parser dedicado para formato Winamax Summary (header `Winamax Poker Tournament Summary :`), reutilizar endpoint + UI com discriminação por `site`. Resolve parte do gap G1 (Winamax sempre falha no resolver). **Decisão pendente:** vale o esforço dado o volume Winamax (~5% das mãos 7d)? |
| **#AUTH-SCHEME-MIGRATION-UNDOCUMENTED** | 🟢 LOW | Tentativa pt27 de pull `/api/queue/hrc` com header `X-API-Key:` devolveu 401. Diagnóstico revelou que o auth-handler é `require_auth_or_api_key` (G4 pt21) que aceita `Authorization: Bearer <HRC_WATCHER_API_KEY>` mas não `X-API-Key`. Documentação `JOURNAL_2026-05-12-pt21.md` confere — sempre foi Bearer; nunca houve X-API-Key. Atribuir ruído a documentação intermédia esquecida no chat (não no repo). **Acção:** verificar se algum doc (README, ONBOARDING, MAPA) menciona X-API-Key e corrigir. Tempo estimado: 5 min de grep. |
| **#PT25D-WATCHER-FRAGILE-CLIPBOARD-OR-RESTORE** | 🟢 LOW | Smoke A pt27 (rollback `.exe` pt25d para validar baseline antes de atacar fix popup) revelou: watcher arrancou mas não conseguiu processar `GG-5944816316`. Causa exacta não isolada — 3 hipóteses: (a) auto-restore HRC da última "Hand 1" persistida cria race condition com paste do watcher; (b) clipboard interference (Windows clipboard history ou script paralelo); (c) state.json pt25d mostra **40 de 41 mãos pulled em 14 Maio nunca chegaram a `done`** — fragilidade conhecida da baseline, não regressão nova. **Decisão pt27:** não investigar mais — o caminho é fixar `#START-CALC-SELECTED-SUBTREE-NO-POPUP-OPEN` em pt28, não restaurar pt25d. Tech debt mantém-se como recordatório histórico se algum dia for necessário voltar ao pt25d como fallback. |

## Estado actual (19 Maio 2026 pós-pt26 closeout)

Sessão pt26 fechada com **1 commit feature em main** (`a735053`, pt26 smoke
calibração) + commit docs. Trabalho substancial em `_local_only/`
(gitignored): trampoline strategy do `swap_and_smoke.py` (4 SWAP + 13
APPEND + 15 consts), PyInstaller bundle do `.exe` pt26 (12.86 MB, sha256
`2213aa19...a4a7`). Suite **449 → 453 PASSED** (+4 líquidos para tests
de pixels-rel + Nash hint + Calculate calibration).

Re-classificação do problema reportado pelo Rui no smoke real: o sintoma
de "equity_model errado" **não é regressão FT/MTT** (design tag-based é
canónico desde pt23, confirmado nesta sessão) — é cadeia
`#VISION-LOBBY-API-FAILURE → #HRC-CONTEXT-MISMATCH-PLAYERS-LEFT`
mascarada pelo workaround `#HRC-MTT-OTHER-TABLES-INFO` aceite em pt23.
Erro do Web auto-registado no journal pt26: interpretação literal antes
de pattern-matching.

**Estado do gatekeeper `#HRC-PRUNE-IN-GAP-DOWNSTREAM`:** continua
**substituído** pelo flow Bloco 2; recompilação validada mecanicamente
no smoke harness do `swap_and_smoke.py` (14/14 PASS), mas
**funcionalmente bloqueada** por `#START-CALC-SELECTED-SUBTREE-NO-POPUP-OPEN`
(CRIT novo, descoberto no smoke real 19 Maio).

### Tech debts fechados em pt26 (1)

| ID | Como fechou |
|---|---|
| **#CALCULATE-BUTTON-COORD-PENDING** | `a735053` aplicou `CALCULATE_BUTTON_X=204`, `CALCULATE_BUTTON_Y=59` (pixels-rel à wpos, convenção alinhada com `EQUITY_MODEL_X/Y` e `STRATEGY_TABLE_FOCUS_X/Y`). Título Nash refinado para `("Nash Calculation",)` (drop hint permissivo `"Calculate"`). Migração das fracções do popup para pixels-rel (`SCOPE_DROPDOWN_REL = (278, 67)`, etc.) — robustez contra variação de tamanho do popup observada entre smokes 18 e 19 Maio (416×214 → 436×230). Tests 27→31 em `test_watcher_set_scope.py`. Detalhe completo em `docs/JOURNAL_2026-05-19-pt26.md`. |

### Tech debts abertos e fechados em pt27 Bloco B (4)

Diagnosticados na simulação Bloco B da mão `GG-5944816316` (8-handed, MP open 2bb, Hero HJ 3-bet jam, eff 6.64BB). Fechos backend-only — sem mudança no watcher.

| ID | Como fechou |
|---|---|
| **#CI-DEFAULT-MISMATCH** | Backend default `_DEFAULT_CI_TARGET_FIRST_RUN = 5.0` renomeado para `_DEFAULT_CI_TARGET = 10.0` em `services/queue_export.py`. Watcher já hardcode-passa 10.0 a `start_calculation_selected_subtree` (1ª e 2ª run alinhadas). Decisão product do Rui em pt27 Bloco B: opção (ii) "alinhar ambos em 10". |
| **#DERIVE-MAX-PLAYERS-HERO-REGEX-GG** | Aberto + fechado em pt27 Bloco B. Sintoma: `derive_max_players` em `services/derive_max_players.py` devolvia 5 (ou 3 com nicks-com-espaço) em vez de 6 para mão GG-5944816316 8-handed. Cadeia causal: (a) `_HERO_RE = ^Dealt to (\S+)` apanhava o 1º `Dealt to` (em GG pós-`_replace_hashes` todos os 8 seats têm essa linha, não só Hero); (b) `_SEAT_RE`/`_ACTION_RE` usavam `\S+` que truncava nicks com espaços tipo "Andrii Novak" → seat 7 e action filtradas para fora; (c) `_SEAT_RE` matchava também na linha SUMMARY `Seat 6: Hero collected (X)` sobrescrevendo `seats[6]="Hero collected"` e fazendo `Hero` deixar de bater nicks. Fix: (i) `_HERO_RE` exige ` \[` (só Hero tem hole cards visíveis); (ii) `_SEAT_RE` + `_ACTION_RE` mudam `\S+` para lazy `.+?` (tolera espaços); (iii) parsing de seats restrito ao header pré `*** HOLE CARDS ***` para evitar match SUMMARY. +1 test reproduz a mão real. |
| **#COMPUTE-TARGET-NODE-OFFSET-USES-WRONG-PLAYER-COUNT** | Aberto + fechado em pt27 Bloco B. `compute_target_node_offset` em `services/hrc_node_offset.py` usava `max_players` (redução ICM via `derive_max_players`) como input para `strategy_table_positions`. Errado conceptualmente — Strategy Table HRC renderiza uma linha-base por jogador real sentado, não pela redução ICM. Em GG-5944816316 isto fazia `position='MP'` falhar lookup em `strategy_table_positions(6)=[UTG,HJ,CO,BU,SB]` → `target_node_offset=None`. Fix: renomear param para `seats_at_table`; caller `build_queue_zip` passa `len(derive_seats_in_preflop_order(hh_text))` em vez de `hints.get("max_players")`. Tests existentes renomeados semanticamente; +1 test reproduz mão real (offset esperado 4 = 2 posições × 2 linhas + 0 within bucket). |
| **#START-CALC-SELECTED-SUBTREE-NO-POPUP-OPEN** (parcial) | Continua **aberto** para a parte do popup. Dependência backend resolvida: `target_node_offset` agora computa correctamente em mãos cujo agressor está em posição que estava fora da redução ICM. O watcher pode usar este valor para `navigate_to_target_node` antes do click Calculate — mesmo que o popup falhe a abrir, a arrow-nav fica correcta. Diagnóstico do popup propriamente dito (timing/coord/state) continua bloqueador para smoke real funcional. |

### Tech debts novos abertos em pt26 (5)

| ID | Severidade | Resumo |
|---|---|---|
| **#VISION-LOBBY-API-FAILURE** | 🔴 CRIT (gatekeeper smoke real útil) | Vision API do lobby falhou em processar o SS do torneio para mão `WN-4690815078549684227-208-1778279040`. Investigação pendente: (a) SS estava associado à mão no canal Discord da tag HM3? (b) `lobby_processing_log` tem entrada para esta mão / este `tournament_number`? Erro registado? (c) Vision call site em `backend/app/services/lobby_vision.py` só faz `logger.error/warning` + `return None` em todas as failure paths — não há retry nem propagação de erro além de None. (d) Quotas/limits API Anthropic — auditoria 19 Maio mostrou só 5 dias de uso em Maio (plenty de quota); investigar outros factores (timeouts, rate limits, lobby SS malformado, JSON dict não-parseable). Fix conceptual: tornar Vision API failure observable (não silenciosa) + populate `lobby_processing_log` com `failure_reason` mesmo em erro. |
| **#HRC-CONTEXT-MISMATCH-PLAYERS-LEFT** | 🔴 CRIT (sintoma do `#VISION-LOBBY-API-FAILURE`) | HRC calcula como N-handed quando torneio tem K-left (N << K). Para `WN-4690815078549684227-208-1778279040`: 13-left em 6-max, HRC viu 4 jogadores no torneio totais → ICM strategies não confiáveis. Vinculado a `#VISION-LOBBY-API-FAILURE` (causa upstream) e `#HRC-MTT-OTHER-TABLES-INFO` (workaround aceite em pt23 Bloco 7 que mascara este sintoma). Fix em 2 frentes paralelas: (1) garantir `players_left` no meta.json (depende de `#VISION-LOBBY-API-FAILURE`); (2) watcher escreve Other Tables = `ceil((players_left - max_players) / max_players)` quando `players_left` está populado — source-side em `handle_mtt_stacks_page` ou função paralela. Coords + Generate button + sequência de teclas pendentes de calibração smoke. |
| **#START-CALC-SELECTED-SUBTREE-NO-POPUP-OPEN** | 🔴 CRIT | Smoke real 19 Maio com `.exe` pt26 mostrou que `start_calculation_selected_subtree` não dispara o popup Nash. `_wait_for_nash_popup` devolve `None` por timeout (5s). Cadeia cai no early-return defensivo de `_set_scope_in_popup`. Hipóteses: (a) `_click_calculate_button` clicou mas popup não abriu por algum estado do HRC; (b) timing — popup demora >5s, `_NASH_POPUP_WAIT_TIMEOUT_S=5.0` curto demais; (c) Calculate button coord `(204, 59)` errado para estado pós-1ª-run; (d) `start_calculation` legacy (não-patched) já abre e fecha popup Nash da 1ª run, o segundo Calculate vai a outro lado. Diagnóstico exige smoke devagar dedicada. **Bloqueia smoke real funcional do `.exe` pt26.** |
| **#FINALIZE-NEVER-FIRES-ON-NO-OP** | 🟡 MED | Quando `start_calculation_selected_subtree` faz early-return por popup não detectado (`#START-CALC-SELECTED-SUBTREE-NO-POPUP-OPEN`), `finalize_after_second_run` é chamado na mesma mas a 2ª run não correu. Zip exportado pode conter só a 1ª run (Full Tree) ou estar vazio/parcial. Fix: `start_calculation_selected_subtree` devolve bool de sucesso; `setup_hand` só chama `finalize` se Selected Subtree completou. Senão `finalize` da 1ª run com warning explícito. |
| **#CI-DEFAULT-MISMATCH** | 🟢 FECHADO em pt27 Bloco B (ver "Tech debts abertos e fechados em pt27 Bloco B" no topo). Texto preservado por contexto histórico. | Smoke real 19 Maio expôs inconsistência: `meta.json.ci` defaulta `5.0` em `_build_hand_meta` ([`queue_export.py:570`](backend/app/services/queue_export.py)); `start_calculation_selected_subtree` chamado em `setup_hand` com hardcoded `10.0`; docstrings DEPRECATED de `set_ci_target_initial/refine` falam de 5.0/10.0. Risk: tree explora em CI=5 na 1ª run mas user pode esperar CI=10 coerente em ambas. Decisão product pendente: (i) split 5/10 explícito; (ii) alinhar ambos em 10; (iii) parametrizar via meta.json. |

## Estado actual (15-18 Maio 2026 pós-pt25f closeout estendido)

Sessão pt25f fechada com **10 commits feature em main** + 2 commits docs.
Núcleo 15-16 Maio: `76e2ea7` / `0444cf2` / `11c2dea` / `e18c8ff` / `cde29f4` /
`9b6e839`. Extensão 18 Maio (não-prevista no scope original): `7e38d89` /
`f99e994` / `fa4f21a` / `92778bd`. Suite **340 → 449 PASSED (+109 líquidos)**.

Focos:
- Núcleo: limpezas cross-case + deprecation fix + versionamento bridge HM3 +
  rotação operacional de password + Trabalho A (refactor gerador `.js` HRC
  com sizings da HH real e prune via JS removido).
- Extensão: regra de multiplicador de efetiva nos 3-bet clássicos (5 buckets)
  + **Bloco 2 do watcher completo source-side** (peça 1 calibrada via
  smoke 2026-05-18 + peça 2 end-to-end com meta.json automático +
  `target_node_offset` + navegação por setas).

**Estado do gatekeeper `#HRC-PRUNE-IN-GAP-DOWNSTREAM`:** **substituído**
em pt25f. Mecanismo original (REAL_AGGRESSOR_POS + DOWNSTREAM_POSITIONS +
guard JS) removido em `9b6e839`. Caminho novo: (a) sizings literais
substituídos no `.js` pela acção real da HH + regra multiplicador para
classic 3-bet (`9b6e839` + `7e38d89`) + (b) Bloco 2 do watcher
(Scope=Selected Subtree + navegação até nó do raiser + 2ª run em subtree —
source-side completo em `92778bd`, recompilação `.exe` pendente pt26).
Gatekeeper continua aberto **apenas** até smoke real end-to-end no Beelink
pós-recompilação. Backend está 100% pronto.

**Falha de governance herdada de pt25:** o prune via JS foi implementado sem
aprovação product explícita do Rui em pt25/b/c/d (decisão user-facing tratada
como optimização técnica). Remediada em pt25f via Trabalho A. Próxima
instância: interpretar a rule de aprovação prévia em
`PAPEIS_E_RESPONSABILIDADES.md` de forma rigorosa para mudanças que afectam o
que o Rui vê quando usa a app/HRC.

### Tech debts fechados em pt25f (8)

| ID | Como fechou |
|---|---|
| **#HRC-PRUNE-IN-GAP-DOWNSTREAM (mecanismo)** | Removido em `9b6e839`. Active code já não tem referências a `REAL_AGGRESSOR_POS` / `DOWNSTREAM_POSITIONS` / `derive_prune_downstream`. Pasta `hrc_scripts/archive/` retém os ficheiros legacy para histórico. O gatekeeper continua aberto na sua intenção (redução de tree explosion), mas o caminho é agora via sizings literais + Bloco 2 do watcher (source-side completo em `92778bd`). |
| **#TEMPLATE-DYNAMIC-SIZINGS-PER-HAND** | Implementado em `9b6e839` exactamente como a tech debt descrevia (per-hand `SIZES_*` substituídos pela acção real da HH via regex sub) — só com semântica de prune via JS removida (não é defense-in-depth como a tech debt sugeria; é substituto). Módulo novo `backend/app/services/hrc_script_gen.py`. Estendido em `7e38d89` com regra de multiplicador para os 5 buckets de 3-bet clássico (sizing real da HH ignorado nesses; opens/squeezes/4-bets/5-bets mantêm sizing real). |
| **#APPHM3-NOT-VERSIONED** (descoberto pt25f) | Migrado para `tools/apphm3/` em `cde29f4`. `config_local.py` gitignored, template `.example` versionado, README PT-PT, fix `datetime.utcnow` aplicado, `.bat`s usam `%~dp0`. Rui migrou localmente. |
| **#DATETIME-UTCNOW-DEPRECATED** (descoberto pt25f) | Substituído em 3 sítios (`routers/hands.py:1326`, `routers/hands.py:1371`, `routers/hm3.py:756`) por `datetime.now(timezone.utc).replace(tzinfo=None)` em `e18c8ff`. Bit-for-bit preservado. Same fix aplicado em `tools/apphm3/hm3_export.py` no commit `cde29f4`. |
| **#WATCHER-BUG-G-SCOPE-SELECTED-SUBTREE** | Source-side completo em `f99e994` (função paralela `start_calculation_selected_subtree` + `_set_scope_in_popup` + defensive returns; opção (b) escolhida vs decompor `start_calculation` legacy — justificação no journal). Coords reais calibradas em `fa4f21a` (smoke 2026-05-18, fracções `SCOPE_DROPDOWN_FRAC = (0.668, 0.313)` + `SCOPE_OPTION_SELECTED_SUBTREE_FRAC = (0.659, 0.505)`; convenção de fracções alinhada com pt25d CI Target). Wiring end-to-end em `92778bd` (passos 1/2/4 do popup flow: `_wait_for_nash_popup` + `_fill_ci_target_in_popup` + `_click_ok_in_popup` via Enter). |
| **#WATCHER-BUG-H-FLOW-ORDER-SAVE-LAST** | Wiring resolvido em `92778bd`. `setup_hand` block "STUBS Bloco 2" descomentado e refeito: `navigate_to_target_node` + `start_calculation_selected_subtree` + `finalize_after_second_run` na ordem correcta após a 1ª run. `export_strategies` continua dentro de `finalize_after_second_run` (stub source-side de pt25e Bloco 1), agora chamado no fim — não no meio. |
| **#WATCHER-BUG-F-CI-TARGET-2ND-RUN** | Confirmado **DEPRECATED**. Popup Nash gere o CI internamente — não é necessário set no main UI antes de Calculate. Stubs `set_ci_target_initial` / `set_ci_target_refine` mantidos no source (`patched_funcs.py`) com docstrings DEPRECATED. Razão para manter: o marshal swap do bundle .pyc pareia cada função patched com slot específica; remover desalinha o slot map já documentado em pt25e Bloco 1. Eliminação fica acoplada ao smoke real pós-recompilação (quando confirmamos que o `_fill_ci_target_in_popup` dentro de `start_calculation_selected_subtree` cobre todos os casos). |
| **#META-AGGRESSOR-REAL-ACTION** (re-confirmado) | Já estava fechado em pt25e Bloco 2 fix urgente; em pt25f passou a alimentar `compute_target_node_offset` no backend (`92778bd`). O campo `position` (BTN→BU follow-up) é input directo do cálculo de offset. |

### Tech debts novos abertos em pt25f (2)

| ID | Severidade | Resumo |
|---|---|---|
| **#CHANGE-PASSWORD-FEATURE** | 🟡 MED | App não tem endpoint nem UI para change-password. Rotação de password do user `rui@pokerapp.com` em pt25f (15 Maio, post-exposure da `MudaEsta123!` em scripts/zips/briefings) foi single-shot via `UPDATE users SET password_hash = ...` na DB Railway com Code com acesso. Próxima rotação volta a depender de DB direct. Fix: implementar `POST /api/auth/change-password` (validar old + bcrypt-hash new + invalidate session opcional) + UI em SettingsPage / Profile dropdown. Pré-requisitos: nenhum. Esforço: ~2h (1 endpoint + 1 form). |
| **#CALCULATE-BUTTON-COORD-PENDING** | 🟢 FECHADO em pt26 (`a735053`) — ver §"Tech debts fechados em pt26" no topo. Texto pt25f preservado abaixo por contexto histórico. | `CALCULATE_BUTTON_X/Y` em `tools/watcher_src/patched_funcs.py:317` ainda a 0 (placeholder) + early-return defensivo no `_click_calculate_button`. Botão verde Calculate no main UI HRC, à direita do painel da Strategy Table — visualmente o único botão "go" verde grande no estado pós-1ª-run. Não documentado no source legacy do Baltazar; `start_calculation` legacy clica-o internamente sem expor coords. Calibração: smoke pequeno comigo no Beelink (Rui usa `pyautogui.position()`, 1 click) — `_local_only/get_calibrate_coords.py` se ainda existir, ou substituto inline. **Bloqueia recompilação do `.exe`**: sem este coord, o `start_calculation_selected_subtree` recompilado faz early-return defensivo do passo 1 e o flow Selected Subtree não dispara. Ao mesmo tempo confirmar o título exacto da janela do popup Nash (hints provisórios `("Nash", "Calculate")` em `_NASH_POPUP_TITLE_HINTS`) — Rui copia o título visível na barra do popup. |

## Estado actual (15 Maio 2026 pós-pt25e Bloco 1 + smoke devagar manual em curso)

Sessão pt25e Bloco 1 fechada (commits `8eb9d87` / `f7c8833` / `bad2c51`). Source watcher (`tools/watcher_src/patched_funcs.py`) ganhou stubs para Bugs F/G/H/J, todos atrás de defensive flags (coords não calibrados → early-return WARN; finalize ainda não wired no Bloco 1). `.exe` em produção (Beelink) continua pt25d intacto — Bloco 1 valida arquitectura, não muda comportamento operacional. Suite **266→282 PASSED** após Bloco 1.

Sessão pt25e Bloco 2 começa com smoke devagar manual. Rui corre o `.exe` pt25d **directamente** no Beelink com a mão GALACTICA (`WN-4706316461629505541-158-1778795596`, Winamax, 6-handed, UTG abre 2.5bb, SB 3-bet all-in, BB Hero call all-in). Pasta preparada à mão sem passar pelo backend: `hh.txt` + `payouts.json` (94 lugares reais do lobby + bountyType PKO + progressiveFactor 0.5 como aproximação ao Space KO Winamax) + `script.js` (template Charles "open 2x" com `SIZES_OPEN_OTHERS=[2.5, ALLIN]` + `SIZES_3BET_SB_VS_OTHER=[7.5, ALLIN]`, sem prune block) + `meta.json` (`stage=MTT`, `players_left=88`, `total_chips=14940000`, `ci=10.0`). 2ª run ainda a correr ao fechar deste briefing; Rui devolve screenshots + export + observações amanhã.

**Status do gatekeeper `#HRC-PRUNE-IN-GAP-DOWNSTREAM`:** **ainda OPEN.** Backend está 100% pt25/b/c/d/e; bloqueio é exclusivamente downstream — fluxo do watcher + dependência position-do-aggressor (este commit pt25e Bloco 2 fix urgente fecha essa dependência).

### Achados do smoke devagar pt25e Bloco 2 (15 Maio, em curso)

1. **MTT Stacks panel workaround por config:** sem `stage: "MTT"` explícito no `meta.json`, o caller cai no branch `elif equity_model == 'multi_table_icm'` (pt23 Bug E fix) e salta o painel com `BTN_NEXT` directo, deixando Other Tables em 0. Para mãos MTT correctas o Rui quer "++" + OK (live em `handle_mtt_stacks_page`, branch `if stage == 'MTT' and (players_left or players_in_hand)`). Fix imediato é config (meta.json com `stage=MTT` explícito + `players_left`); fix longo prazo é reavaliar heurística do branch — provavelmente manter como está e enriquecer meta.json no pipeline upstream.
2. **CI=10 confirmado empiricamente:** com CI=10 a 2ª run baixa de ~7.2h (CI=5) para ~76min. Confirma regra semântica correcta (CI baixo = mais refinado = mais lento) — alinha com a docstring de `_set_ci_target_common`.
3. **Save mid-flow continua a aparecer:** caixa "Save As" abre entre fim da 1ª run e início da 2ª, fica em wait até estratégias estabilizarem. Bug H stub (`finalize_after_second_run`) ainda não está wired. Sem prejuízo para o Bloco 1; reordering completo só depois de G+J calibrados.
4. **Bug I (Basic Hand Data, 1º painel pós-paste da HH)** ainda por isolar. Rui captura amanhã step-by-step.
5. **Re-priorização pelo Rui:** **Bug G > Bug J.** Argumento: Selected Subtree corta a 2ª run para uma fracção do tempo (centrado no spot real da mão) e Prune Action é optimização adicional menos crítica. Bug G passa para HIGHEST entre os 5 bugs do watcher; Bug J reposicionado abaixo.
6. **Solução desenhada para Bloco 2 wiring (depende deste commit fix urgente):** watcher faz OCR confinado à coluna Player da Strategy Table HRC e clica a primeira linha onde `Player == aggressor_real_action.position`; depois click no botão play (já calibrado pt25d); no popup Nash que abre — dropdown Scope → "Selected Subtree" → CI=10 (vem do meta.json) → OK. Reduz drasticamente o custo de OCR (vocabulário fechado de ~6 strings curtos vs OCR genérico sobre toda a tabela). Coords das 3 entradas novas (column Player, dropdown Scope no popup, opção "Selected Subtree") a calibrar em smoke devagar pt25e Bloco 2 final.

### Tech debts pt25e abertos — `#WATCHER-COMPLETE-FLOW` (HIGH gatekeeper) (6)

Ordem actualizada pelo Rui em 15 Maio: Bug G antes de Bug J.

| ID | Severidade | Resumo |
|---|---|---|
| **#WATCHER-BUG-G-SCOPE-SELECTED-SUBTREE** | 🟢 FECHADO em pt25f (`f99e994` + `fa4f21a` + `92778bd`) — ver "Tech debts fechados em pt25f" no topo. Recompilação `.exe` pendente pt26. | A 2ª run tem de correr em Scope=`Selected Subtree`, não em `Full Tree` (default da 1ª). Spec final pt25e Bloco 2 (15 Maio, simplificada): (1) OCR confinado à **coluna Player** da Strategy Table HRC (vocabulário fechado: UTG/HJ/CO/BU/SB/BB/EP/MP/EP1/EP2/`BU/SB`), (2) clicar a primeira linha onde `Player == aggressor_real_action.position` (vinda do payouts.json — este commit fecha a dependência), (3) clicar botão play (coords pt25d já calibrados), (4) no popup Nash que abre: dropdown Scope → seleccionar "Selected Subtree", (5) CI=10 (lido do meta.json), (6) OK. Coords pendentes calibração: column Player, dropdown Scope no popup, opção "Selected Subtree" no dropdown. Re-priorização pelo Rui em 15 Maio: corta 2ª run para fracção do tempo; mais crítico que Bug J. |
| **#WATCHER-BUG-H-FLOW-ORDER-SAVE-LAST** | 🟢 FECHADO em pt25f (`92778bd`) — `setup_hand` STUBS block descomentado, ordem correcta `navigate_to_target_node` → `start_calculation_selected_subtree` → `finalize_after_second_run` no fim. Recompilação `.exe` pendente pt26. | Fluxo actual: Setup → 1ª run → **save_strategies imediato** → done. O save_strategies deve ser **último**, após a 2ª run. Ordem correcta: Setup → 1ª run → (G: Selected Subtree + CI=10) → 2ª run → **save_strategies**. Mover o passo save_strategies da `setup_hand` para função `finalize_after_second_run`. Stub source-side já existe (pt25e Bloco 1, `tools/watcher_src/patched_funcs.py:finalize_after_second_run`); wiring + recompile do `.exe` é trabalho do Bloco 2 após G+J calibrados. |
| **#WATCHER-BUG-J-PRUNE-ACTION-PER-LINE** | 🔴 HIGH | Após 1ª run, o watcher faz Prune Action **linha a linha** para cada player em `DOWNSTREAM_POSITIONS`, percorrendo a tree visual. **CUIDADO armadilha UX HRC:** o context menu tem **2 entradas com "Prune"** — uma é **"Prune Action"** (queremos esta, prune da sizing específica clicada), outra é um Prune global mais agressivo (NÃO esta). Watcher tem de seleccionar o texto exacto **"Prune Action"**. Coords + ordem das entradas no menu a confirmar em smoke devagar pt25e Bloco 2. **Não confundir com o guard `getSizingsOpening` injectado pelo script.js** — esse é prune **scripted** (afecta árvore inicial pre-1ª run); este é prune **manual** sobre nós da subtree pré-2ª run. Os dois complementam-se. Re-priorização 15 Maio: abaixo de Bug G (optimização adicional, menos crítica). **Caminho preferido descoberto 15 Maio (manhã):** atalho de teclado **`Ctrl+D` = Prune Action** na Strategy Table HRC. Permite ao watcher fazer prune via keystroke após seleccionar a linha — sem coords de context menu, sem risco da armadilha das 2 entradas "Prune". Outros atalhos relevantes descobertos na mesma corrida: `Ctrl+Shift+D` (Prune Children — NÃO usar), `Ctrl+Shift+A` (Add Action), `Alt+L` (Lock/Unlock Range), `Ctrl+C` / `Ctrl+Shift+C` (Copy Range / Strategy), `Ctrl+V` / `Ctrl+Shift+V` (Paste Range / Strategy). Wiring de Bloco 2 deve seguir o caminho `Ctrl+D` via `pyautogui.hotkey('ctrl','d')` (ou equivalente), com fallback context menu apenas se `Ctrl+D` falhar em smoke. |
| **#WATCHER-BUG-I-FIRST-PANEL-WRONG-BUTTON** | 🟡 MED | Smoke devagar 14 Maio: Rui detectou que **o watcher clica num botão errado no 1º painel pós-extract** (Basic Hand Data). Repro confirmado visualmente mas sem screenshot/log estruturado ainda. Possíveis causas: deslocamento de coords pós-refresh HRC UI (5.0.X), race condition (botão clicked antes de habilitar), ou rotina chama wrong helper entre `select_bounty_mode` e `setup_scripting`. Identificar exactamente qual botão em smoke devagar dedicado pt25e Bloco 2 (Rui executa step-by-step e regista, planeado para 15-16 Maio). |
| **#WATCHER-BUG-F-CI-TARGET-2ND-RUN** | 🟢 FECHADO em pt25f (DEPRECATED confirmado em `f99e994` docstrings; CI passa a viver dentro do popup via `_fill_ci_target_in_popup` em `92778bd`). Stubs mantidos no source por razão de slot map do marshal swap. | Hipótese inicial pt25e: set CI Target no main UI HRC antes do Calculate, com initial=5.0 + refine=10.0. Smoke devagar 15 Maio revelou que CI value é controlado via `meta.json` campo `ci` que `start_calculation(ci_target)` lê, e o popup Nash que aparece pós-Calculate já tem o campo CI calibrado pt25d (`rect.left + int(w * 0.65)`, `rect.top + int(h * 0.51)`). Set CI no main UI antes do Calculate revela-se **desnecessário**. Helpers `set_ci_target_initial` / `set_ci_target_refine` continuam no source (`patched_funcs.py`) mas **não wired** em `setup_hand` e o early-return defensivo evita clicks falsos. Resolução: manter source-side para histórico mas remover stubs comentados em `setup_hand` quando Bloco 2 fechar; alternativa de fechar formal — limpar em pt25f. |
| **#META-AGGRESSOR-REAL-ACTION** | 🔴 HIGH | Dependência backend: `meta.json` (ou `payouts.json`) tem de ganhar campo novo `aggressor_real_action` com forma `{type: "raise"\|"bet", size_bb: float, position: str\|None}` extraído da HH parseada. Permite ao watcher (Bug G passo 3, simplificado em 15 Maio) clicar a linha exacta na coluna Player da Strategy Table HRC via OCR + position match. Implementação: helper `derive_aggressor_real_action(hh_text, level_sb, level_bb) -> dict\|None` em `services/queue_export.py` — parseia primeira raise/bet preflop, converte chips → bb units relativos ao level da mão, resolve position via `derive_seats_in_preflop_order`, devolve dict. Injecção no manifest entry + payouts.json em `build_queue_zip`. Status: campo `type/size_bb` deployed em pt25e Bloco 1 (commit `8eb9d87`); campo `position` deployed neste commit pt25e Bloco 2 fix urgente (ver `#META-AGGRESSOR-POSITION` abaixo). |
| **#META-AGGRESSOR-POSITION** | 🟢 FECHADO (pt25e Bloco 2 fix urgente, 15 Maio + follow-up BTN→BU mesmo dia) | Extensão de `derive_aggressor_real_action` com campo `position` (string maiúsculas — labels canónicos de `_POSITION_LABELS_BY_N`: UTG/HJ/CO/BU/SB/BB/EP/MP/EP1/EP2 + `BU/SB` para HU). Mapping nick → position via `derive_seats_in_preflop_order` (única fonte de verdade do preflop order pt25d). Schema final: `{type, size_bb, position}`. Schema injection: manifest entry + payouts.json (sítios onde `type/size_bb` já viviam). Tests pytest: 4 samples reais cross-site (PS Votsarrr=BU, GG 221ebf0d=HJ, WN INTERSTELLAR blueballs67=UTG, WPN DAVIDSBAGOFICE=HJ) + sintéticos N=5/N=4/HU cobrindo UTG/HJ/CO/BU/SB/BB/`BU/SB`. Justificação da urgência: destranca Bloco 2 do watcher — OCR confinado à coluna Player com vocabulário fechado de ~6 strings (vs OCR genérico sobre toda a tabela). Follow-up BTN→BU: confirmação empírica do Rui que Strategy Table HRC mostra "BU" não "BTN"; `_POSITION_LABELS_BY_N` realinhado nos índices 3-9 (HU mantém "BU/SB"). |

### Tech debts operacionais descobertos (sessão backfill HM3 pt25e, 15 Maio)

| ID | Severidade | Resumo |
|---|---|---|
| **#RAILWAY-POSTGRES-PASSWORD-DRIFT** | 🟡 MED | Divergência entre `POSTGRES_PASSWORD` da service `Postgres` e o password embutido no `DATABASE_URL` da service `poker-app` (Railway, projecto `trustworthy-dedication`). Diagnóstico empírico durante backfill HM3 pt25e: psql contra `ballast.proxy.rlwy.net:37559` (proxy TCP público) com credenciais da service Postgres dá `FATAL: password authentication failed for user "postgres"`. Credenciais embutidas no `DATABASE_URL` da poker-app autenticam OK. Detalhe: `POSTGRES_PASSWORD` tem 32 chars, password embutido no URL da poker-app tem 31 chars (após URL-decode) — desalinhamento de 1 caractere indicia rotação manual antiga apenas em UM dos sítios (provavelmente a poker-app foi reapontada com `?-password` actualizado mas a service Postgres ficou com o original; ou vice-versa). **Impacto runtime: zero** — a app em produção liga ao DB pelo hostname interno (`postgres.railway.internal:5432`) com o password que de facto autentica. **Impacto operacional: alto-para-ferramentas-locais** — qualquer script `railway run` que linke à service Postgres e use `DATABASE_PUBLIC_URL` falha em auth; o workaround usado em pt25e foi reescrever o URL da poker-app substituindo apenas o host/porto pelo proxy público (`sed -E "s\|@[^/]+/\|@${PG_TCP_DOMAIN}:${PG_TCP_PORT}/\|"`). Fix sugerido: rotar password explicitamente via Railway dashboard (Database service → Connect → Rotate password) e confirmar que `POSTGRES_PASSWORD` + `DATABASE_URL` (Postgres) + `DATABASE_URL` (poker-app) ficam todos sincronizados; ou aceitar a divergência e documentar o workaround do URL-swap no MAPA. **Só documentar nesta sessão**, sem fix. |

### Tech debts pt25f abertos — re-arquitectura template script.js (1)

| ID | Severidade | Resumo |
|---|---|---|
| **#TEMPLATE-DYNAMIC-SIZINGS-PER-HAND** | 🟢 FECHADO em pt25f (`9b6e839`) — ver "Tech debts fechados em pt25f" no topo do ficheiro. Restante texto abaixo preservado por contexto histórico. | Bug K — Re-arquitectura. Template `mtt_advanced_20211029...bvb.js` actualmente declara sizings fixos top-of-file: `SIZES_OPEN_OTHERS = [2, ALLIN]`, `SIZES_3BET_IP = [7.5, 12, ALLIN]`, `SIZES_3BET_BB_VS_SB = [7, ALLIN]`, etc. Estes sizings genéricos inflam a árvore HRC porque o solver explora cada um (e.g., 1ª open: 2bb + ALLIN; 3-bet IP: 7.5bb + 12bb + ALLIN). Para que a árvore contenha apenas o sizing **real** da mão, o backend tem de **injectar dinamicamente** `SIZES_*` per-hand baseados na action sequence parseada da HH. Cada raise/bet preflop é extraído e injectado no slot correspondente (e.g., UTG raise 2.1bb da HH → injectar `SIZES_OPEN_OTHERS = [2.1, ALLIN]`; HJ 3-bet 8bb IP → `SIZES_3BET_IP = [8, ALLIN]`). Reduz a tree drasticamente by design — pode tornar o prune via `getSizingsOpening` (pt25) redundante na prática, mas mantemos como defense-in-depth. Implementação: generalizar `generate_hrc_script` para 2 substituições — (a) bloco prune existente (REAL_AGGRESSOR_POS + DOWNSTREAM_POSITIONS), (b) cada SIZES_* var top-of-file via regex. Helper novo `derive_preflop_sizings(hh_text, level_sb, level_bb) -> dict[str, list[float]]` em `services/queue_export.py` faz parsing completo (5+ raises sequenciais) e mapeia bet_count + position → SIZES_* key. Trabalhoso; depende implicitamente de **#META-AGGRESSOR-REAL-ACTION** (parsing comum). |

### Smoke real pt25d — observações operacionais (14 Maio)

- ✅ Zip `/api/queue/hrc` chega ao Beelink com `script.js` per-hand correcto.
- ✅ `REAL_AGGRESSOR_POS=0` + `DOWNSTREAM_POSITIONS=[1,2,3]` em convenção docs UTG=0 — validado por Rui visual no `.js` desempacotado para INTERSTELLAR (`WN-4699459877053923331-277-1778535900`).
- ✅ Manifest entry com `prune_index_convention="hrc_docs_v1"` (traceability pt25d).
- ❌ Watcher salta 2ª run e exporta directo → tree guardada é a da 1ª run sem prune avaliado em subtree.
- ❌ Bug I (botão errado no 1º painel) detectado mas sem screenshot — pendente repro pt25e.
- **Conclusão:** pipeline backend → adapter → HRC engine está OK; o gap está no fluxo do watcher pós-extract.

### Commits pt25b/c/d/e em main (cronológico)

```
f32ed28  pt25b: robustez backend cross-site (markers WN/WPN + duplicate let fix + table_format detection + seats vazios) + 22 tests
77ff496  pt25c: mover hrc_scripts/ para backend/ (fix Railway deploy) + escalar silent OSError para logger.error + manifest field prune_script_error
3347fcf  pt25d: fix convention indices HRC scripting (UTG=0 docs canonical)
8eb9d87  pt25e bloco 1 #META-AGGRESSOR-REAL-ACTION: helper + injection manifest/payouts
f7c8833  pt25e bloco 1 Bug F: split set_ci_target em initial/refine (watcher source)
bad2c51  pt25e bloco 1 Bug H: re-order setup_hand + stubs Bloco 2 (watcher source)
```

---

## Estado actual (14 Maio 2026 — pt25d fix convenção indices HRC)

Sessão pt25d. Web descobriu via investigação dos docs oficiais HRC scripting que a convenção de índices oficial é **UTG=0 (first-to-act preflop), SB=N-2, BB=N-1** — não a convenção `SB=0, BB=1, UTG=2, ..., BTN=N-1` que `derive_seats_in_preflop_order` usava desde pt25. Bug silencioso: `script.js` injectado correctamente, template tinha o guard `DOWNSTREAM_POSITIONS.indexOf(player) !== -1`, mas `ctx.getActivePlayer()` retorna índices na convenção docs e o nosso array vivia na convenção SB=0 — `indexOf` nunca match → prune nunca disparava → tree continuava a explodir mesmo com pt25/pt25b deployed. **Não detectado em pt25b smoke** porque o smoke real bloqueou no fix script.js missing (pt25c). Confirmação por Web pediu cat do template original + output `generate_hrc_script` para INTERSTELLAR; comparação revelou que `getSizingsOpening` compara `player == ctx.getPlayerIndexButton/SmallBlind/BigBlind()` (API-vs-API, agnóstica) mas o nosso `indexOf` é API-vs-Python-emitted (precisa da mesma convenção).

Fix backend-only — template e JS patch são convenção-agnósticos. Refactor de 3 helpers (`derive_seats_in_preflop_order`, `derive_real_aggressor_position`, `derive_prune_downstream`) + drop de 2 params (`seated_hrc_indices`, `table_format` em `derive_prune_downstream`) + reescrita de `_POSITION_LABELS_BY_N` (8 entries, agora começa em UTG/BTN/BU consoante N e termina em BB). 28 tests reescritos + 18 sintéticos novos (`5h/6max/8max` series cobrindo todas as posições + HU + degenerate cases). Manifest field novo `prune_index_convention="hrc_docs_v1"` para distinguir zips pré-pt25d (buggy) vs pós-pt25d. Suite **264 PASSED** (era 264). Dry-run INTERSTELLAR confirma: `REAL_AGGRESSOR_POS=0, DOWNSTREAM=[1,2,3]` (UTG=0, downstream HJ/BTN/SB; BB=4 excluído). Smoke real pendente: Rui faz cleanup + re-pull Beelink + reporta tree size.

### Tech debts fechados pt25d (1)

| ID | Como fechou |
|---|---|
| **#HRC-INDEX-CONVENTION-MISMATCH** (descoberto pt25d) | `derive_seats_in_preflop_order` mudou a fórmula: `first_to_act_offset = 0 if n == 2 else 3` (HU age primeiro pelo botão; N≥3 age via `button + 3`, wraps mod N). Indices contíguos `0..N-1` por construção, daí drop do param `seated_hrc_indices` em `derive_prune_downstream`. SB-aberto early-return removido em `derive_real_aggressor_position` (era artefacto da convenção velha; com SB=N-2, `derive_prune_downstream` devolve [] naturalmente para esse caso). Commit pt25d ETAPA 3. |

### #HRC-PRUNE-IN-GAP-DOWNSTREAM (gatekeeper)

**Nota pt25f (16 Maio):** o mecanismo descrito abaixo (REAL_AGGRESSOR_POS +
DOWNSTREAM_POSITIONS + guard JS) foi **removido em `9b6e839`**. A redução de
tree passa agora pelo Trabalho A (sizings literais substituídos no `.js`) +
Bloco 2 do watcher. Ver "Estado actual (15-16 Maio 2026 pós-pt25f closeout)"
no topo do ficheiro. O texto abaixo é histórico (pt25 → pt25d).

Continua aberto até smoke real validar tree size pós-pt25d. Pipeline técnico completo:
- pt25 — helpers + JS template guard + adapter integration + lobby_vision `players_left`
- pt25b — robustez cross-site (PS/GG/WN/WPN markers, action format, table layout)
- pt25c — script.js no zip (Railway deploy fix) + manifest `prune_script_error`
- pt25d — fix convention indices (UTG=0 docs canónica)

Sem confirmação real de redução de tree size, o gatekeeper continua HIGH. Smoke real pt25d: Rui apaga state Beelink, re-pull `/api/queue/hrc`, abre INTERSTELLAR no HRC pos-extract, observa tree size na barra inferior — esperamos drop de ~17h ETA / >20GB para minutos / sub-GB se a optimização disparar como pretendido.

---

## Estado actual (13 Maio 2026 — pt25b validado, prune-in-gap robusto cross-site)

Sessão pt25 → pt25b. Foco em `#HRC-PRUNE-IN-GAP-DOWNSTREAM` (HIGH gatekeeper, herdado de pt24). **pt25** implementou 4 frentes core: helpers backend (`derive_real_aggressor_position` + `derive_prune_downstream` + `generate_hrc_script`), JS template guard, `build_queue_zip` escreve `script.js` no zip + override `script_path`, adapter reescreve para path absoluto pós-unzip. Plus `lobby_vision` extrai `players_left` mid-tournament + `lobby_processing_log` ganha coluna dedicada + `_resolve_players_left` lookup SQL. **pt25b** adicionou robustez cross-site (GG/PS/Winamax/WPN): helper novo `find_preflop_marker` (aceita `*** HOLE CARDS ***` e `*** PRE-FLOP ***`); `_PREFLOP_OPEN_RE` ganha colon opcional para action lines WN/WPN; `generate_hrc_script` faz substitution idempotente no placeholder em vez de inserir (evita duplicate `let`); helper canónico `derive_seats_in_preflop_order` com labels por N-handed (suporta 5-sentados-6-max INTERSTELLAR); `derive_prune_downstream` aceita `seated_hrc_indices` para downstream baseado nos sentados. Smoke real (PASSO B5) aguarda transferência adapter ao Beelink.

### Tech debts fechados em pt25b (4)

| ID | Como fechou |
|---|---|
| **#TABLE-FORMAT-DETECTION** | Novo helper `derive_table_format(hh_text)` parsa `\\b(\\d+)-max\\b` (universal nos 4 sites: PS, GG, Winamax, WPN — confirmado em ETAPA 1). `derive_prune_downstream` aceita `seated_hrc_indices` (canónico via `derive_seats_in_preflop_order`); fallback `table_format=8` mantido para tests sintéticos legacy. Commit pt25b ETAPA 3. |
| **#SEATS-EMPTY-TABLE-LAYOUT** | `derive_seats_in_preflop_order` walks apenas pelos seats sentados, mapping contínuo hrc_idx 0..N-1 (N = sentados, não table_format regular). 5-sentados-6-max (INTERSTELLAR Winamax) → `[SB, BB, UTG, HJ, BU]` com hrc_idx [0..4]; CO desaparece em 5-handed labels. Commit pt25b ETAPA 3. (Pt25e follow-up: label "BU" alinhado com Strategy Table HRC; era "BTN" pré-Bloco 2.) |
| **#HH-FORMAT-WINAMAX-MARKERS** | Novo helper `find_preflop_marker(hh_text)` tenta `*** HOLE CARDS ***` (PS/GG/WPN) e `*** PRE-FLOP ***` (Winamax) — devolve a posição mais cedo. `_build_nick_to_hrc_index` + `derive_real_aggressor_position` passam a usar o helper. `_PREFLOP_OPEN_RE` regex ganha colon opcional (`(?::)?`) para action lines sem colon (WN/WPN: `nick raises X to Y`; PS/GG: `nick: raises X to Y`). Commit pt25b ETAPA 1. |
| **#GENERATE-HRC-SCRIPT-DUPLICATE-LET** | `generate_hrc_script` revisto: regex `_PRUNE_PLACEHOLDER_RE` faz `subn` que substitui o bloco placeholder existente do template B2 em vez de inserir um segundo bloco antes de `let ALLIN`. Idempotente (rodar 2× com mesmos args produz output byte-igual). Fallback legacy mantido para templates sem placeholder. Commit pt25b ETAPA 2. |

### Tech debts pt25 ainda open (3)

| ID | Severidade | Resumo |
|---|---|---|
| **#FT-PLAYERS-DIFFERENT-FROM-REGULAR** | 🟡 MED (pt26+) | FT pode ter mais jogadores que a mesa regular (e.g., INTERSTELLAR Winamax é 6-max regular mas FT são 7 jogadores). O threshold `players_left > 3 × max_players` torna-se ambíguo: `3 × regular_max` (=18 para 6-max regular) vs `3 × FT_max` (=21 para 7-max FT). Resolver detectando FT layout do tournament metadata e ajustando `max_players` parameter accordingly. |
| **#BUY-IN-PKO-RATIO-EXTRACTION** | 🟡 MED (pt26+) | Buy-in revela ratio prize:KO real (e.g., INTERSTELLAR €40 prize + €50 KO = 44%:56%, não o 50:50 standard assumido pelo `apply_ratio_lookup` em `services/lobby_vision.py`). Esclarecimento Rui: o average buy-in está **registado na própria HH** da mão — backend pode extrair directamente sem precisar de `tournaments_meta` externo. Útil para enriquecer bounty injection (Bug D futuro) com valores accurate em vez do PKO standard. |
| **#BACKFILL-LOBBY-PLAYERS-LEFT-DISCORD-REFETCH** | 🟢 LOW | Cobertura retroactiva dos 18 lobby snapshots históricos via Discord API re-fetch. Script `scripts/backfill_lobby_players_left.py` está em **shell com `NotImplementedError`** no fetch step (lobby_processing_log NÃO persiste `img_b64`; imagens lobby passam in-memory por `process_lobby_message`). Implementação real exige bot token + lifecycle + rate-limit handling (custo ~$0.18-$0.36 Vision + 30-60min). Sem urgência: Rui posta SS fresca para qualquer torneio recente e o pipeline real-time captura, OU UPDATE manual via Rui visual (pt25 smoke usou esta via: `UPDATE lobby_processing_log SET players_left=36 WHERE discord_message_id='1503540439884501043'` para INTERSTELLAR Winamax tn=1094178268). |

---

## Estado actual (13 Maio 2026 — pt24 em curso, Vision bounty_value_usd validado)

Sessão pt24 em curso. Foco em `#HRC-GG-KOS-EXTRACTION` (HIGH gatekeeper pt24): Vision extrai `bounty_value_usd` (coroa dourada) por player no `players_list`. Prompt + parser de `backend/app/routers/screenshot.py:_extract_hand_data_from_image` actualizado para 5-field format (`name|stack|vpip_pct|bounty_value_usd|country`) com backward-compat 4-field. Smoke pt24 valida 8/8 contra ground truth do Rui em GG-5914506215 (bounty e vpip ambos correctos). **Sem commits ainda**.

### Tech debts novos levantados pt24 (em curso) (4)

| ID | Severidade | Resumo |
|---|---|---|
| **#VISION-BACKFILL-BOUNTY-VALUE-USD** | 🟡 MED (pt25+) | Re-correr Vision (já deployed em commit `59704da` — prompt pt24 com `bounty_value_usd`) sobre `entries.raw_json['img_b64']` de entries antigas com mãos GG já matched, para popular `player_names.players_list[].bounty_value_usd` retroactivamente. Sem este backfill, o bounty injection em `queue_export` (commit pt24 PASSO C) funciona apenas para mãos **novas** daqui em diante (ingestion pós-`59704da`). Implementação: script `backend/app/scripts/backfill_bounty_value_usd.py` que loopa entries com `entry_type='replayer_link'` + `raw_json->'img_b64'` não-null + hands GG matched, chama `_extract_hand_data_from_image` + `_parse_vision_response`, faz UPDATE `hands.player_names` com `players_list` re-extraído. Custo OpenAI: ~$0.01-0.02 por mão × ~N GG hands em prod. |
| **#VISION-STACK-UNIT-DETECTION** | 🟡 MED | Vision às vezes devolve stack em BB sem preservar o sufixo `BB` no output (ex: `28.1` quando devia ser `28.1 BB`). Parser `_parse_vision_response` (`screenshot.py:361`) detecta unit via regex `\\d+\\s*BB`; sem "BB" cai em `stack_unit='chips'` e o valor fica errado (28.1 chips em vez de 28.1 BB ≈ 196 700 fichas a BB=7000). Reproduzido em smoke pt24 (GG-5914506215): 8/8 stacks parseados como chips com valores ridiculos. Solução: cross-ref com a HH (que tem chips canónicos em "(N in chips)") via `_normalize_vision_stacks` (já existe parcialmente). Tunar prompt para reforçar "preserve BB suffix" não é definitivo (Vision pode escapar). Fix robusto: aceitar Vision como advisory, autoritativo = HH parser. |
| **#FIELD-BOUNTY-PCT-MISNAMED** | 🟢 LOW | Historicamente o field `players_list[].bounty_pct` armazena **VPIP %** (orange flame badge), não bounty. Mantido por backward-compat com 4 consumidores backend (`villain_rules.py`, `mtt.py`, `ire.py`, `screenshot.py:_replace_hashes_in_actions`) + 1 coluna BD (`hand_villains.bounty_pct TEXT`). Em pt24 o **prompt** novo de Vision foi clarificado: `vpip_pct` na output line; field key dict `bounty_pct` continua a existir com mesma semântica. Rename completo (key + coluna + 4 consumidores + frontend) fica para refactor futuro. |
| **#FIELD-STACK-CHIPS-AMBIGUOUS** | 🟢 LOW | `players_list[].stack_chips` está em "chips" para stacks que Vision lê numericamente (sem unit declarado) mas pode ser BB-derivado (×bb_size em `_normalize_vision_stacks`) ou valores fictícios (Vision a esquecer-se de preservar BB suffix — ver `#VISION-STACK-UNIT-DETECTION`). Frontend (`HandDetailPage.jsx:233`, `Hands.jsx:1259`) e backend IRE (`ire.py:186-269`) consomem como se fosse autoritativo. Unificar unidade para "chips canónicos" (sempre, com fallback a HH `(N in chips)`) eventualmente. |

### Edit pt24 ainda uncommitted

- `backend/app/routers/screenshot.py` — prompt + parser ganha campo `bounty_value_usd` (smoke 8/8 PASS).

---

## Estado actual (13 Maio 2026 — pt23 em curso, marshal swap + recompile validados)

Sessão pt23 em curso. Descompilação `hrc_watcher.exe` via `pycdc` (build local com VS 2022 Build Tools + CMake) + `dis` manual concluída. Marshal swap das 4 funções alteradas (`set_equity_model`, `get_player_count_from_hh`, `setup_scripting`, `setup_hand`) validado em smoke local (8/8 sub-tests PASS). Re-bundle PyInstaller `--onefile` valida arranque end-to-end no PC principal: launcher carrega `.pyc` swapped, `exec` do main inicia, bate como esperado em `os.makedirs('C:\\Users\\Administrator\\...')` (path do Beelink, não escrevível no PC principal). Pronto para smoke real no Beelink. **Sem commits ainda**.

### Tech debts novos levantados pt23 (em curso) (5)

| ID | Severidade | Resumo |
|---|---|---|
| **#HRC-PRUNE-IN-GAP-DOWNSTREAM** | 🔴 HIGH (pt24+) | **Gatekeeper de produção.** Reduzir tree HRC eliminando opens in gap das posições **downstream** do agressor inicial (pathways paralelos puros — só ocorreriam se agressor foldasse, o que não aconteceu na mão real → impacto zero no EV do spot focal). **Trigger:** `players_left > 3 × max_players` (pré-3 final tables, fase Multi Table ICM). **Excepção:** agressor SB → não trigger (BB nunca open). Por agressor inicial, eliminar opens in gap de: UTG → `{EP,MP,HJ,CO,BU,SB}`; EP → `{MP,HJ,CO,BU,SB}`; MP → `{HJ,CO,BU,SB}`; HJ → `{CO,BU,SB}`; CO → `{BU,SB}`; BU → `{SB}`. **Importante:** NÃO eliminar upstream (já foldaram mas range de fold real importa para card removal no nó focal). **Implementação pt24:** helper `derive_prune_downstream(hh_text, max_players, players_left) -> list[str] \| None` em `services/queue_export.py` → novo campo `prune_in_gap_downstream` em `payouts.json` → script HRC (variante `bvb.js`) lê hint e faz prune action por posição. **Razão da prioridade:** smoke real pt23 confirmou trees com ETA ~17h sem esta optimização, inviabilizando uso em volume real. |
| **#HRC-GG-KOS-EXTRACTION** | 🔴 HIGH (pt24) | GGPoker HHs exportadas sem bounties (KOs) → HRC roda PKO em vazio. Solução planeada: pipeline Vision (Claude Sonnet similar a `services/lobby_vision.py`) extrai `{nick: bounty}` da SS anexada à mão via `hand_attachments`, backend `services/queue_export.py` enriquece HH PS-compat inserindo bounties em cada linha `Seat` antes de enviar para o adapter. |
| **#HRC-MTT-OTHER-TABLES-INFO** | 🟡 MED (pt24+) | Multi Table ICM com Other Tables = 0 (default actual) reduz-se semanticamente à Final Table ICM — perde a contribuição informativa das outras mesas. Para precisão real, watcher precisa de info das outras mesas (player counts, stack averages). Backend pode derivar via `tournaments_meta` ou Lobbarize. Por agora aceitamos `Other Tables=0` (pipeline funcional, precisão sub-óptima). Descoberto no smoke real pt23 — fix cirúrgico Bug E em `setup_hand` clica Next sobre a página MTT Stacks sem preencher, em vez de pendurar o wizard. |
| **#WATCHER-META-INJECTION-BYPASSED** | 🟢 LOW (pt24+ refactor) | Watcher Baltazar Apr19 tinha `inject_meta_into_zip(hand_path, export_zip)` + `zip_is_ready` (verifica `done/replied/<hand>.zip`) que assumiam um "bot externo" que movia o zip de `Exports/` → `replied/` e adicionava `meta.json` com `{rank, players_left, stage, ci}`. Esse bot **não existe na pipeline poker-app→adapter→watcher** (pt22+). Adapter agora injecta meta minimal (`{hand_id, exported_at, source, watcher_built_meta=False}`) em `_ensure_meta_in_zip` antes do POST. Implicação: `inject_meta_into_zip` + ramo `replied/` no watcher são dead code. Quando refactorizarmos o watcher (pt24+) remover. Adapter perde acesso a `rank/players_left/ci` (esses valores existem em settings.json interno do HRC mas exigem parser do formato HRC — adiar para quando for útil). |
| **#PYINSTALLER-BUNDLE-SIZE** | 🟢 LOW (sem prazo) | Bundle re-empacotado em pt23 tem 13.4 MB vs 30.5 MB original do Baltazar. PIL/Pillow não auto-detectado pela análise estática do PyInstaller a partir do `wrapper.py`; provavelmente outras libs do bundle Apr19 que não são essenciais para runtime. Tunar `_local_only/watcher_decompile/build_pyi/hrc_watcher.spec` quando for relevante (ex: se faltar dep em runtime real no Beelink). |

---

## Estado actual (13 Maio 2026 — pós-pt22, Adapter G1 deployed, 3 bugs watcher tracked)

Sessão pt22 fechada. **2 commits feature em main:** `cc93698` (G1 adapter Python Beelink), `67761a0` (fix regex hand_id Winamax). + commit docs de fecho. Pipeline mecânico Beelink ↔ poker-app **validado ponta-a-ponta**; smoke funcional bloqueado por **3 bugs do watcher Baltazar** que exigem descompilação do exe. Suite **172 PASSED** inalterada (adapter é cliente externo). Detalhe completo em `docs/JOURNAL_2026-05-13-pt22.md`.

### Commits da pt22 em main (cronológico)

```
cc93698  feat(hrc-adapter): G1 adapter Python Beelink ↔ poker-app API
67761a0  fix(hrc-adapter): regex hand_id aceita formato Winamax multi-segmento
```

### Tech debts fechados pt22

| ID | Hash | Resumo |
|---|---|---|
| **G1 adapter (queue/results bridge)** ✅ | `cc93698` | 4 ficheiros novos em `tools/hrc_adapter/`. Loop Python 3.14 a correr no Beelink: GET zip → unzip → watcher → POST results. state.json local atomic. Logging diário rotativo 14d. Fecha G1 do plano Fase 3. |
| **Adapter regex multi-segmento** ✅ | `67761a0` | `HAND_ID_RE` agora `^[A-Z]+-\d+(-\d+)*$` — cobre GG (1 segmento) + Winamax (3 segmentos). 40 mãos WN saltadas no 1º tick smoke deixam de ser skipped. |

### Tech debts novos levantados pt22 (9)

| ID | Severidade | Resumo |
|---|---|---|
| **#HRC-WATCHER-EQUITY-MODEL-FIXO** | 🔴 HIGH | Bug A — watcher fixo em `Malmuth-Harville ICM`, sem branch para `Multi-Table FGS`. Mãos mid-MTT ficam com equity FT-style → solver dá EVs científicamente questionáveis. Solução proposta pelo Rui: tag-based design via canais Discord `#icm-ft`/`#icm-pko-ft` + HM3 tags → hint `equity_model` no payouts.json → watcher (recompilado) lê hint. Especificação em `REGRAS_NEGOCIO.md §14`. **Bloqueia G5/G6 funcionais**. Requer recompilação do watcher (pt23). |
| **#HRC-WATCHER-MAX-PLAYERS-ESTATICO** | 🔴 HIGH | Bug B — `get_player_count_from_hh()` regex de seats sentados na HH (ex: 8-9) em vez de jogadores relevantes à decisão (ex: 3 para `UTG raise / MP+CO+SB fold / BTN call / BB→hero`). Árvore do solver explode com combos irrelevantes → tempo de cálculo + EV diluído. Solução: parsing HH no watcher (`last_raiser_position → hero_position` + `players_after_hero_still_active`). Requer recompilação. |
| **#HRC-WATCHER-JS-HARDCODED** | 🔴 HIGH | Bug C — script `mtt_advanced_20211029 - 2 flats + bb close action size open 2x - 3x bvb.js` carregado por nome literal. Ranges muito largos → tree >20GB → OOM crash HRC. Mitigação imediata (sem recompilar): substituir o ficheiro do mesmo nome por versão tight. Final: config externa no watcher (env var `HRC_SCRIPT_PATH` ou metadata por mão). Requer recompilação. |
| **#HRC-WATCHER-DECOMPILE-REQUIRED** | 🔴 HIGH | Baltazar (autor do `hrc_watcher.exe`) emigrou, sem contacto. Sem fonte Python original. Material já no repo: `_local_only/hrc_watcher.exe` (30.5 MB), `_local_only/extracted/` (bytecode raw via pyinstxtractor), `_local_only/ANALYSIS.md` (~80% mapeado por análise estática). Próximo: `pycdc` ou `decompyle3` para gerar `.py` legível. Bloqueia A/B/C. Sessão pt23. |
| **#HRC-WATCHER-PATH-BETA-LEGACY** | 🟡 MED | Watcher hardcoded a 3 paths sob `C:\Users\Administrator\...` incluindo `AppData\Local\HoldemResources\HRC Beta\hrc.exe`. Hoje funcional via perfil legacy preservado pelo reset Windows; instalação HRC moderna do `riand` é em `Local\Programs\HoldemResources\HRC\` (sem "Beta"). Reconsiderar pós-recompilação — tornar paths configuráveis (env var ou config file). |
| **#HRC-ADAPTER-SCHEDULED-TASK** | 🟢 LOW | Adapter actualmente em interactive console (`python hrc_adapter.py`). Migrar para Windows Scheduled Task com restart-on-fail (instruções em `tools/hrc_adapter/README.md`). Não bloqueia nada — Rui pode parar com Ctrl+C; útil quando o adapter for 24/7. |
| **#SERVER-FILTER-HRC-STATUS** | 🟢 LOW | `GET /api/queue/hrc` (`routers/queue.py:export_queue`) **não** filtra mãos que já têm `hrc_jobs.status='done'`. Devolve sempre o mesmo conjunto baseado em tags/study_state. Adapter usa `state.json` local para dedup (D10 aprovado em pt22). Servidor podia filtrar para reduzir bandwidth — adicionar `WHERE NOT EXISTS (SELECT 1 FROM hrc_jobs WHERE hrc_jobs.hand_db_id = hands.id AND hrc_jobs.status = 'done')`. |
| **#HRC-RESET-PRESERVATION** | 🟡 MED | Perfil `Administrator` legacy intacto pós-reset Windows é **frágil** — qualquer reset/reinstall futuro pode levar tudo (script Charles, pasta `Teste completo\`, subpastas `done/arquivo/replied`). Mitigação: clonar pasta `Teste completo\` para `C:\Users\riand\Documents\Teste completo\` e reconsiderar paths hardcoded. Depende de `#HRC-WATCHER-PATH-BETA-LEGACY`. |
| **#TOKEN-ROTATION-DEFENSIVE-PT23** | 🟡 MED | `HRC_WATCHER_API_KEY` actual (mask `Z10Soz9...37zSZ`) foi visto numa screenshot Railway que Rui partilhou ao Web durante debug pt22. Rotação defensiva pré-pt23: gerar novo via `python -c "import secrets; print(secrets.token_urlsafe(48))"`, meter no Railway dashboard (save + redeploy), atualizar `.bat` no Desktop, executar no Beelink. Code valida via CLI que mask mudou. |

### Decisões fechadas pt22

**Adapter G1 (D1-D10 + A1-A5):** D1 Python 3.14.5 / D2 source em `tools/hrc_adapter/` + copy manual / D3 interactive→Scheduled Task faseado / D4 `TimedRotatingFileHandler` 14d / D5 60s poll / D6 2 patterns (done/*.zip + <hand>/.failed) / D7 state.json atomic / D8 setx HKCU / D9 Retry urllib3 nativo 3x backoff 5/10/20s / D10 state.json local source of truth / A1 startup_scan / A2 estrutura repo / A3 logging com hand_id / A4 except amplo / A5 validação regex+RESERVED_NAMES.

**Watcher fix (decisão Web+Rui):** Opção 2 — descompilar `hrc_watcher.exe` em pt23. ANALYSIS.md cobre ~80%; resto via `pycdc`. Fixes cirúrgicos A/B/C + recompilar PyInstaller.

### Smokes validados em prod (pt22)

- **GET /api/queue/hrc** com Bearer válido → 200 OK + zip `queue_<ts>.zip` (size ~280 KB).
- **POST /api/queue/hrc/results** (status=done) → 200 OK, `hrc_jobs.status='done'`, `result_zip` populado em BD prod.
- **Pipeline mecânico ponta-a-ponta** — pull → unzip → watcher abre HRC → wizard completo executou → zip exportado para `done/<hand_id>.zip` → adapter POST → BD actualizada.

### Tech debts URGENT carry-over (pt19+, **nenhum atacado em pt22**)

- **Mãos órfãs em massa** (HIGHROLLER €250 WINAMAX, 27 mãos `#icm-pko` sem villains).

### Tech debts pt21 carry-over abertos (3)

- `#HRC-JOBS-HISTORY-SUBSEQUENT` 🟢 FUTURE / `#HRC-RESULT-STORAGE-MIGRATION` 🟢 FUTURE / `#HRC-AUTH-MULTI-KEY` 🟢 LOW.

### Tech debts pt20 carry-over abertos (5)

- `#BACKOFFICE-MYSTERY` 🟡 / `#TS-RATIO-MYSTERY-CONFIRM` 🟢 / `#TS-AUTO-PAYOUTS-ICM` 🟢 / `#SYNC-RECENT-RESPECT-MANUAL` 🟡 / `#PYDANTIC-V1-VALIDATOR-DEPRECATION` 🟢.

---

## Estado actual (12 Maio 2026 — pós-pt21, backend Fase 3 HRC G3+G4+G2 deployed)

Sessão pt21 fechada. **3 commits feature em main:** `5b9c10a` (G3 hrc_jobs schema), `764b53e` (G4 auth dual-path), `2fa1f60` (G2 POST /results). HRC_WATCHER_API_KEY setada em Railway env vars pelo Rui. Smokes G4+G2 validados em prod. Suite **154 → 172 PASSED** (7+11 tests novos, G3 sem tests dedicados — opção B). HEAD `2fa1f60` + commit docs. Detalhe completo em `docs/JOURNAL_2026-05-12-pt21.md`.

### Commits da pt21 em main (cronológico)

```
5b9c10a  G3 — tabela hrc_jobs schema
764b53e  G4 — auth dual-path cookie + Bearer
2fa1f60  G2 — POST /api/queue/hrc/results
```

### Tech debts fechados pt21

| ID | Hash | Resumo |
|---|---|---|
| **Schema persistência HRC** ✅ | `5b9c10a` | Tabela `hrc_jobs` criada com PK BIGSERIAL, FK ON DELETE CASCADE para `hands(id)`, UNIQUE (hand_db_id), status CHECK 5 valores, result_zip BYTEA. Fecha G3 do plano Fase 3. |
| **Auth long-lived para watcher** ✅ | `764b53e` | `require_auth_or_api_key` aceita cookie OU `Authorization: Bearer` constant-time. Aplicado em `/api/queue/hrc` + `/api/queue/hrc/results`. Fecha G4 do plano. |
| **Endpoint feedback do watcher** ✅ | `2fa1f60` | `POST /api/queue/hrc/results` multipart com lookup hand_id, validação zip, extract meta, UPSERT idempotente. Fecha G2 do plano. |

### Tech debts novos levantados pt21

| ID | Severidade | Resumo |
|---|---|---|
| **#HRC-JOBS-HISTORY-SUBSEQUENT** | 🟢 FUTURE | `UNIQUE (hand_db_id)` significa 1 job por mão. Re-upload overwrite. Se a regra de produto exigir histórico de re-attempts (2º solve com depth maior, comparação A/B), criar tabela auxiliar `hrc_job_attempts (id BIGSERIAL, hrc_job_id BIGINT FK, attempted_at, result_zip, meta_json)`. Migração não-destrutiva — adiciona, não muda. |
| **#HRC-RESULT-STORAGE-MIGRATION** | 🟢 FUTURE | `result_zip BYTEA` em BD. Volume actual estimado: Rui ~10-50 mãos/dia × ~273 KB de zip (GET) + zip results de ordem similar ≈ ~30 MB/dia. Aceitável durante meses. Migrar para storage externo (S3/R2/Railway storage quando existir) se chegar a GBs. Schema fica igual; coluna passa a TEXT (URL) + helper de read async. |
| **#HRC-AUTH-MULTI-KEY** | 🟢 LOW | `HRC_WATCHER_API_KEY` env var única cobre 1 watcher. Para 2+ máquinas (Beelink 2, watcher cloud, local test), migrar para tabela `hrc_api_keys (id, name, key_hash, created_at, last_used_at, revoked_at)`. Revogação granular sem redeploy, auditoria por key. Endpoint admin `POST/DELETE /api/admin/hrc-keys` protegido por cookie. |

### Decisões fechadas pt21

**G3 (schema hrc_jobs):** S1 FK INTEGER ON DELETE CASCADE / S2 BYTEA + size / S3 TEXT CHECK 5 valores / S4 JSONB / S5 BIGSERIAL PK + UNIQUE hand_db_id / S6 índice (status, submitted_at) / S7 services/hrc_jobs.py novo.

**G4 (auth dual-path):** D-G4-1 env var (opção A) / D-G4-2 `Authorization: Bearer` / D-G4-3 `HRC_WATCHER_API_KEY` / D-G4-4 48 bytes URL-safe / D-G4-5 `{id: None, email: None, auth_type: 'api_key'}` / D-G4-6 só endpoints HRC / D-G4-7 MAPA deferido / D-G4-8 log INFO em uso / D-G4-9 Bearer inválido não fallback / D-G4-10 key setada na sessão / D-G4-11 Rui gera local.

**G2 (POST /results):** D-G2-1 `/api/queue/hrc/results` / D-G2-2 multipart / D-G2-3 hand_id query / D-G2-4 50 MB cap / D-G2-5 validação minimal / D-G2-6 meta server-side / D-G2-7 augmentar meta / D-G2-8 UPSERT overwrite / D-G2-9 404 ausente / D-G2-10 só done+failed / D-G2-11 failed→error obrigatório / D-G2-12 1 por request / D-G2-13 MAPA fecho / D-G2-14 zip sintético / D-EXTRA-1 11 tests / D-EXTRA-2 submitted_at preservado / D-EXTRA-3 server-side wins / D-EXTRA-4 WARNING no failed com file.

### Smokes validados em prod (pt21)

- **G4 GET com Bearer**: `GET /api/queue/hrc?include_no_payout=true` → HTTP 200, size=279910 bytes (zip elegível). Via `railway run python` (env var injectada no subprocess, key nunca printed).
- **G2 POST sem auth**: HTTP 401 `"Não autenticado"` (rota registada).
- **G2 POST com Bearer + hand_id inexistente**: HTTP 404 `"hand_id 'GG-NONEXISTENT-99999' não encontrado"` (pipeline completo end-to-end).

### Achados operacionais (verificação BD pós-G3)

- `DATABASE_PUBLIC_URL` no serviço Postgres tem password stale (32 chars vs 31 chars real do `poker-app`). App usa internal URL, prod não bloqueada. Para queries externas: usar password do `poker-app` + proxy público do `Postgres`. Não formalizado como tech debt (workaround conhecido).
- `backend/.env` local com encoding não-UTF8 (byte `0xe3` em position 82). Causa `UnicodeDecodeError` em scripts ad-hoc que importam `app.db`. Workaround: ler vars via `subprocess(railway variables --kv)`. Não formalizado como tech debt (workaround conhecido).

### Operacional paralelo — Beelink GTR5 (Rui)

Reset PC nuclear (Windows reinstall local), conta `riand` criada, updates terminados, Python 3.12 instalado, HRC reinstalado, `hrc_watcher.exe` (30.5 MB PyInstaller) copiado do PC principal. **Pendente pt22:** `C:\hrc\queue\` + `C:\hrc\done\`; `hrc_watcher.exe --help` captura output.

### Tech debts URGENT carry-over (pt19+, **nenhum atacado pt21**)

- **Mãos órfãs em massa** (HIGHROLLER €250 WINAMAX, 27 mãos `#icm-pko` sem villains).

### Tech debts FASE 3 carry-over

- **#FASE-3-MINIPC** — substancialmente avançado em pt21 (reset+setup base); falta G1 adapter + smoke real (pt22).

### Tech debts pt20 carry-over abertos (5)

- `#BACKOFFICE-MYSTERY` 🟡 / `#TS-RATIO-MYSTERY-CONFIRM` 🟢 / `#TS-AUTO-PAYOUTS-ICM` 🟢 / `#SYNC-RECENT-RESPECT-MANUAL` 🟡 / `#PYDANTIC-V1-VALIDATOR-DEPRECATION` 🟢.

---

## Estado actual (12 Maio 2026 — pós-pt20, sync-recent + backoffice import deployed)

Sessão pt20 fechada. **2 commits feature em main:** `5465b32` (Commit E sync-recent + `lobby_processing_log`) e `af7e3c8` (endpoint backoffice `/api/tournament-results/import`). Ambos validados em campo. 5 tech debts novos registados, 2 fechados implicitamente. Suite **122 → 154 PASSED** (16+16 tests novos). HEAD `af7e3c8`. Detalhe completo em `docs/JOURNAL_2026-05-11-pt20.md`.

### Commits da pt20 em main (cronológico)

```
5465b32  Commit E — sync-recent de lobbys + lobby_processing_log
af7e3c8  Backoffice import — /tournament-results/import (vanilla+PKO)
```

### Tech debts fechados pt20

| ID | Hash | Resumo |
|---|---|---|
| **Persistência falhas #lobbys** ✅ | `5465b32` | Tabela `lobby_processing_log` UPSERT por `discord_message_id`. Handler real-time + sync-recent registam cada tentativa com `attempt_count`, `reason_detail`, `vision_json`. Logs Railway deixaram de ser source-of-truth para falhas. |
| **Buraco TS → tournament_payouts** ✅ | `af7e3c8` | Endpoint `POST /api/tournament-results/import` faz upload de SSs do backoffice GG, cruza com `tournament_summaries` via TIER 0 resolver, popula `tournament_payouts` com blob HRC completo (distribuição de prizes por posição). Vanilla + PKO; Mystery em tech debt separado. |

### Tech debts novos levantados pt20

| ID | Severidade | Resumo |
|---|---|---|
| **#BACKOFFICE-MYSTERY** | 🟡 MEDIUM | Suportar Mystery KO no backoffice import. Hoje devolve `mystery_unsupported` (fail-fast em `tournament_results._process_one` quando `ts_tournament_format == 'KO'`). Precisa de sample SS Mystery real + confirmação do `bountyType` aceite pelo HRC Structure Manager (`"KO"` ou mapear para `"PKO"` com factor especial). |
| **#TS-RATIO-MYSTERY-CONFIRM** | 🟢 LOW | Confirmar `apply_ratio_lookup` em `services/lobby_vision.py:35-45` para Mystery KO `("KO", 0.33)`. Web mencionou em pt20 que regra GG real é 25/75 — clarificar antes de fechar #BACKOFFICE-MYSTERY (impacta validação de drift). |
| **#TS-AUTO-PAYOUTS-ICM** | 🟢 FUTURE | Derivar `tournament_payouts` automaticamente a partir do TS via algoritmo ICM (TS tem pool+players+ratio; falta distribuição). Decisão de produto: ICM é estimativa, backoffice é literal. Manter pipelines distintos a não ser que Rui peça automação. |
| **#SYNC-RECENT-RESPECT-MANUAL** | 🟡 MEDIUM | `sync-recent` actualmente re-tenta SSs onde já há `tournament_payouts.source` `manual:` ou `backoffice_vision:` — overwrite com `discord_lobby_vision:` (dados parciais) seria regressão de qualidade. Adicionar guard: `process_lobby_message` skipa UPSERT se source actual ≠ `discord_lobby_vision:`. Hoje a precedência D11 está documentada mas não enforced no lobby pipeline (só no backoffice). |
| **#PYDANTIC-V1-VALIDATOR-DEPRECATION** | 🟢 LOW | `routers/lobbys.py:34` usa `@validator` Pydantic V1 (1 warning durante pytest). Migrar para `@field_validator` V2. Sem impacto funcional; cosmético. |

### Decisões fechadas pt20

**Commit E (sync-recent lobbys):**

| # | Decisão |
|---|---|
| D1 | Síncrono (4-10 min worst-case; sem job queue) |
| D2 | Throttle Anthropic default 1.2s; override no body |
| D3 | `max_messages` default 200, hard cap 500 |
| D4 | UI sub-painel em `Discord.jsx` |
| D5 | Extracção α — core para `services/lobby_sync.py` |
| D6 | Tabela `lobby_processing_log` (β) criada |
| D7 | Reusar `tournament_resolver.resolve_tournament_number` |
| D8 | Sem log da Vision para casos sem `#lobbys` |

**Backoffice import:**

| # | Decisão |
|---|---|
| D1 | Naming `/api/tournament-results/import` |
| D2 | Hardcoded `GGPoker` (param ignorado) |
| D3 | Tolerância 0.05 vanilla / 2% PKO relativa |
| D4 | Cap 20 imagens / 50 em zip |
| D5 | UI inline (não modal) |
| D6 | Source `backoffice_vision:<filename>` |
| D7 | Reusar resolver TIER 0 |
| D8 | NÃO registar em `lobby_processing_log` |
| D9 | Refactor `detect_image_mime` → `services/image_utils.py` |
| D10 | Scope vanilla + PKO; Mystery fora |
| D11 | Precedência `manual > backoffice > lobby` |
| D12 | Mystery ratio mantém `0.33` (tech debt para confirmar) |
| D13 | Mystery → fail-fast `mystery_unsupported` |

### Smokes validados em campo (pt20)

- **sync-recent** (Commit E): 6 candidatos, 4 successes, 2 falhas (Daily Hyper $80 GG, Vision `json_invalid`). Persistência em `lobby_processing_log` confirmada.
- **backoffice vanilla** (`af7e3c8`): Daily Hyper $80 tn=283542054, 18 prizes, 7.4s.
- **backoffice PKO** (`af7e3c8`): Bounty Hunters Deepstack Turbo $88 tn=282721937, 51 prizes, 13.1s.

### Operações ad-hoc pt20

- INSERT manual tn=283542120 (errado, detectado por Web), revertido via `DELETE`+`INSERT` para tn=283542054 (correcto, pool 9420.80, 18 prizes). Soma das prizes bateu **exactamente** ao `prize_pool` do TS. Source: `manual:rui_backoffice_ss_pt20_correction`.

### Tech debts URGENT carry-over (pt19+)

- **Mãos órfãs em massa** (reproducer: HIGHROLLER €250 WINAMAX, 27 mãos `#icm-pko` sem villains em `hand_villains`). Não atacado em pt20. Hipótese: pre-condição `has_cards ∨ has_vpip` muito restritiva para Hyper.

### Tech debts FASE 3 carry-over

- **#FASE-3-MINIPC** (Beelink GTR5 watcher HRC 24/7). Dependência: setup hardware operacional pelo Rui.

---

## Estado actual (11 Maio 2026 — pós-pt19, FASE A + FASE B fechadas)

Sessão pt19 fechada. **FASE A pipeline lobbys fechada em prod** (3 commits A/B/C resolvem G1/G2/G3 de pt18 + refactor terminológico). **FASE B Tournament Summaries fechada em prod** (B1 import + B1.x parser extendido + B2 TIER 0 + B2.1 sem janela com discriminantes Vision). **Backfill GTw → pos-nko** aplicado a 25 mãos em prod (0 GG, 0 overlap). 11 commits totais, HEAD `a4a9595`. Detalhe completo em `docs/JOURNAL_2026-05-11-pt19.md`.

### Commits da pt19 em main (cronológico)

```
d6dedda  FASE A commit A — token-set match em tm_resolver
c6088ee  FASE A commit B — fallback hands + posted_at_hint
f87be3a  FASE A commit C — caption manual TM em #lobbys
440b248  refactor — TM → tournament_number (categoria a/b/c)
9ad1ceb  FASE B B1 — import de Tournament Summaries GG
e6bef2d  diag — logger.exception + repr no except do TS import
0b0a087  fix B1 — usar RealDictCursor key no RETURNING
cdbbc59  FASE B B2 — tier 0 tournament_summaries no resolver
417c071  FASE B B1.x — parser TS extendido (12 campos novos)
c0ddef5  FASE B B2.1 — TIER 0 sem janela + prize_pool/players
a4a9595  GTw → pos-nko backfill + alias no importer
```

### Tech Debts fechados pt19

| ID | Hash | Resumo |
|---|---|---|
| **FASE A — A** ✅ | `d6dedda` | Token-set match em `tournament_resolver` (cobre G2). |
| **FASE A — B** ✅ | `c6088ee` | Fallback `hands` source + `posted_at_hint` window (cobre G1 Winamax/PS, mitiga G3). |
| **FASE A — C** ✅ | `f87be3a` | Caption manual `#TM<num>` no post Discord (bypass do resolver; cobre G3 final). |
| **Refactor TM** ✅ | `440b248` | TM → tournament_number (categoria a/b/c — serviços, símbolos, regex, mensagens). Categoria (d) deferida pt20+. |
| **FASE B B1** ✅ | `9ad1ceb` + `e6bef2d` + `0b0a087` | Import GG TS — tabela, parser 14 campos, endpoint, UI. Fix RealDictCursor row key. |
| **FASE B B1.x** ✅ | `417c071` | Parser TS extendido — 12 campos novos (literais + heurísticas + derivados). Bug regex `_RE_HERO_TOTAL_RECEIVED` apanhado pelos tests defensivos cross-check. |
| **FASE B B2** ✅ | `cdbbc59` | TIER 0 `tournament_summaries` no resolver. 3 helpers privados por tier. |
| **FASE B B2.1** ✅ | `c0ddef5` | TIER 0 sem janela (TS é autoritativo post-jogo). Discriminantes Vision `prize_pool` + `total_players`. |
| **GTw → pos-nko** ✅ | `a4a9595` | Backfill 25 mãos PS/WN/WPN + helper `apply_hm3_tag_aliases` no importer + `(9999, "pos-nko")` em `HM3_REAL_TAGS` + frontend (dropdown + cor). |

### Tech Debts URGENT pendentes pós-pt19

#### Mãos órfãs em massa (🔴 URGENT — reproducer concreto)

- **Reproducer:** Rui partilhou em pt19 screenshot do torneio HIGHROLLER €250 WINAMAX 08/05 com **27 mãos todas órfãs** em `#icm-pko`.
- **Hipótese inicial:** mão sem villain associado em `hand_villains` — regras A/B/C de `_classify_villain_categories` não dispararam. Causa-raiz possível: pre-condição padrão `has_cards ∨ has_vpip` muito restritiva para o tipo de mão deste torneio (Hyper, swings rápidos, pouca acção postflop), e nenhuma das tags HM3/Discord disparou a excepção `nota%`/`nota`.
- **Investigação adiada para pt20+.**

### Tech Debts pendentes (medium / future)

| ID | Severidade | Resumo |
|---|---|---|
| **TS-backfill** | 🟡 MEDIUM | Backfill histórico de Tournament Summaries GG para popular TIER 0 retroactivamente. Sem isto, casos antigos continuam a cair em TIER 1/2. Endpoint `/api/tournament-summaries/import` existe + UI em `Tournaments.jsx`; só falta correr os uploads. |
| **B2.1 Wina/PS** | 🟡 MEDIUM | Validação em campo da B2.1 com Winamax/PS. TIER 0 é GG-only (parser TS é GG-only). Winamax/PS dependem de TIER 2 fallback; field-testing necessário. |
| **Estudo TAGS column** | 🟡 MEDIUM | Vista "TAGS" na secção Estudo só mostra `hm3_tags`; `discord_tags` omitidos. Cosmético mas confunde Rui. |
| **2º Discord entry texto bruto** | 🟢 BAIXA | Marcado como "provavelmente resolvido pelo fix pt9; não-reproduzível em pt19". Reabrir só se Rui voltar a ver. |
| **Refactor TM cat. (d)** | 🟢 FUTURE | ~50 sítios no pipeline `hand_id GG` (screenshot.py, mtt.py, hm3.py, import_.py, discord.py, hands.py). Envolve coluna `mtt_hands.tm_number`, índices, lógica string-replace. Migração de dados necessária. |
| **Vilões vs Estudo arquitectura** | 🟢 FUTURE | Rui levantou em pt19 nuance entre as duas pistas. Discussão de produto antes de mexer. |
| **D — Gyazo URLs em #lobbys** | 🟢 BAIXA | Suporte a links Gyazo em `_handle_lobby_message` (hoje só Discord attachments). ~1h. |
| **E — Sync-recent UI** | 🟡 MEDIUM | `POST /api/lobbys/sync-recent` + botão UI. Permite backfill retroactivo do canal `#lobbys` sem depender de `LOBBY_AUTO=true`. ~2-3h. |
| **F — Cleanup instrumentation** | 🟢 BAIXA | Remover `[debug-msg-lobby]` + lobby channel list log no `on_ready` agora que pipeline está estável. ~10 min. |

### NEW — FASE 3 HRC (Watcher local Beelink GTR5)

- **🔴 ALTA, agendada pt20+.**
- Briefing `HRC_WATCHER_BRIEFING.md` recebido do Rui durante pt19. Cobre as 4 fases do plano de automação HRC; Fase A (FASE A deste repo, pipeline lobbys para popular `tournament_payouts`) **fechada** com este journal.
- **Hardware:** Beelink GTR5 em casa, ainda não ligado. Limpeza prévia necessária.
- **Licença HRC:** OK.
- **Plano:** porting do `hrc_watcher.exe` do Baltazar (`_local_only/ANALYSIS.md`) como referência, mas evitar fragilidades conhecidas — PKO ratio dinâmico do buy-in (não hardcoded), retries em GUI driving Win32 ctypes, error handling robusto.
- **Dependência:** limpeza/setup Beelink (operacional pelo Rui).

### Tech Debts IRE (carry-over de pt16, sem trabalho em pt18/pt19)

Mantêm-se em backlog: **#IRE-MB**, **#IRE-CL**, **#IRE-VB**, **#IRE-SK** (ver secção "Estado actual (8 Maio 2026 — pós-pt16, investigação IRE prod)" abaixo).

---

## Estado actual (7 Maio 2026 fim pt16)

pt16 atacou 3 itens num único arco de sessão. Sem journal próprio ainda — registo neste inventário substitui temporariamente.

- **#5 / #B26** (TAGS Discord vazia em Estudo): verificado em prod já resolvido. Chips Discord azul e `OriginBadge` (HM3 amarelo / Discord azul / HM3+D roxo) implementados em #B17 (pt9, commit `7806d33`) e reforçados em pt15. Sem código novo; backlog estava desactualizado.
- **#6** (status inconsistency Discord ao re-linkar via Vision): mãos `'resolved'` (Revista) voltavam a `'new'` (Nova) sempre que Vision corria enrichment. Causa: `screenshot.py:1432` forçava `study_state='new'` incondicionalmente. Fix em 3 fases num só commit (`be0b9c3`):
  - **Fase 1** — `screenshot.py` deixa de força `'new'`: passa a `CASE WHEN study_state = 'mtt_archive' THEN 'new' ELSE study_state END` (preserva `resolved`).
  - **Fase 2** — `match_state` computado por SQL CASE em 8 endpoints (`hands.py` × 3, `mtt.py` × 2, `tournaments.py`, `villains.py`, `hm3.py`). 5 valores: `archive` > `orphan` > `pending` > `matched`.
  - **Fase 3** — badge unificado de 5 estados (Nova azul / Revista verde / Pendente âmbar / Arquivo cinza / Órfã vermelho discreto) em `HandRow.jsx`, `Hands.jsx`, `Discord.jsx`, `Dashboard.jsx`, `HM3.jsx`. Botão "Marcar Revista" guarded para `match_state='matched'` (placeholders/arquivo/órfãs não estudáveis). Princípio invariante registado: linkagem é precondição obrigatória para o eixo Estudo.
- **Bug "Copiar HH"** (rejeitado pelo HRC com "No valid hand-history found"): regex `re.split(r"(?=(?:Poker\s+)?Hand\s*#)")` em `gg_hands.py:536` matcheia 2 vezes por hand (uma com `Poker `, outra sem) — `re.split` corta em ambos os pontos, descartando o prefixo `Poker ` para fora do bloco. Magnitude prod: 100% das 15.809 hands GG 2026. Fix (commit `0d18c52`): split ancorado em `^Poker\s+Hand\s*#` com `re.MULTILINE`. Validado: novo regex produz blocos com prefixo intacto; antigo produz `["", "Poker ", "Hand #..."]`.
- **Bug HRC concatenar BB+ante**: confirmado externo. App reproduz exactamente o input do GG; HRC interpreta `Level12(3,500/7,000(1,000))` agregando BB+ante quando colado directo do ZIP HH original. Sem acção do nosso lado.

### Tech Debts fechados pt16

| # | Hash | Descrição |
|---|---|---|
| **#B26** ✅ | (verificação) | Investigar cor das TAGS na secção Estudo. Verificado em prod (2026-05-07): vista 'tags' mostra chips Discord (azul `#5865F2`) e `OriginBadge` (HM3 amarelo / Discord azul / HM3+D roxo) — implementado em #B17 (pt9). Backlog desactualizado, sem código novo. |
| **#6** ✅ | `be0b9c3` | Status inconsistency Discord ao re-linkar via Vision. Backend: `screenshot.py:1432` preserva `resolved` (só promove `mtt_archive→new`); 8 endpoints adicionam coluna computada `match_state` por SQL CASE. Frontend: badge unificado de 5 estados; botão "Revista" guarded. Princípio: linkagem é precondição para Estudo. |
| **Bug "Copiar HH"** ✅ | `0d18c52` | Parser GG `gg_hands.py:536` re-split com lookahead `(?:Poker\s+)?Hand\s*#` matcheia 2× por hand, descartando `Poker `. Fix: split ancorado `^Poker\s+Hand\s*#` MULTILINE. 100% das 15.809 hands GG 2026 afectadas — wipe BD + re-import ZIP HM3 GG → 15.811 hands restauradas com prefixo correcto. Bug HRC ao interpretar BB(ante) registado como problema externo. |

### Operações pt16 (sem código)

- **Wipe BD**: 15.815 hands GG + 88 `hand_villains` apagadas. 305 entries Discord revertidas para `status='new'` para re-processamento. Tudo em transacção única; validações intra-transacção todas zero (órfãs, hands GG residuais).
- **Re-import ZIP HM3 GG**: 15.811 hands restauradas com `raw` começando em `Poker Hand #`. Confirmado em prod via SQL: `prefix 'Poker Hand #' = 15811 / 15811`.
- **Discord re-sync**: ainda por fazer pelo Rui — 319 entries em `status='new'` à espera. Re-sync vai re-criar as 4 placeholders Discord/SS em falta + atribuir matches SS↔HH com pipeline corrigido.

### Ainda em aberto pt16

- Re-sync Discord pelo Rui (operacional, fora de tech debt).
- Validação visual end-to-end na app (Estudo, Discord, Dashboard, modal de mão).

---

## Estado actual (9 Maio 2026 — pós-pt18, FASE A pipeline lobbys validado parcialmente)

Sessão pt18 fechada. **FASE 1 HRC export queue validated end-to-end em prod** (smoke real BBG $215). **FASE A C1-C3 deployed** com 9 commits totais (5 feature + 4 fixes/instrumentation). Pipeline lobbys responde no `#lobbys`, Vision API verde, mas TM resolver tem 3 gaps que bloqueiam upserts reais. Backlog ordenado A→B→C→E para pt19. Detalhe completo em `docs/JOURNAL_2026-05-09-pt18.md`.

### Commits FASE 1 + FASE A em main (cronológico)

```
2078eef  FASE 1 C1 — tabela tournament_payouts + endpoints upload
a3dc193  FASE 1 C2 — conversor HH GG → PokerStars-compativel
d16f291  FASE 1 C3 — endpoint GET /api/queue/hrc + build_queue_zip
93b9abc  FASE A C1 — payouts_service refactor
da36f56  FASE A C2 — Anthropic Claude Sonnet 4.6 + lobby_vision + tm_resolver
1ed640c  C2.5    — _DEFAULT_TAGS update (icm-pko/PKO SS/sqz-pko/ICM)
7e302e4  docs    — #FASE-3-MINIPC entry
68f40f9  FASE A C3 — Discord bot dispatch + lobby handler
1d15ac8  C3 patch — instrumentacao temporaria [debug-msg-lobby]
4dd3017  C3 fix   — filtro images Discord CDN URLs (content_type)
cd02d89  C3 fix   — remover assistant pre-fill (Sonnet 4.6 nao suporta)
0a1241b  C3 fix   — MIME magic-number + verbose [lobby] FAIL logs
```

### Gaps identificados na validação real (5 SSs no #lobbys)

| Gap | Casos (5 SSs) | Causa | Fix planeado |
|---|---|---|---|
| **G1** — `tournaments_meta` non-GG vazio | 2/5 (Winamax `GRAVITY`, `HIGHROLLER`) | `services/tournament_meta.py:upsert_tournament_meta` faz skip explícito para Winamax/PS/WPN | **Commit B** |
| **G2** — fuzzy matching insuficiente | 1/5 (`Bounty Hunters Hyper Special $108` → BD tem `Bounty Hunters Sunday Hyper Special $108`) | Vision pode omitir partes do nome; substring `%name%` falha quando nome lido < BD | **Commit A** |
| **G3** — `start_time_iso` ausente / nome muito comum | 2/5 (`Daily Hyper $80` × 2) | Vision não leu timestamp → fallback `LIMIT 5` sem janela; nome corre todos os dias | **Commit C** (caption TM) |

### Tech Debts pendentes pt19 (ordem de prioridade)

| ID | Título | Severidade | Esforço |
|---|---|---|---|
| **A** | Fuzzy / token-set match em `tm_resolver.resolve_tournament_number`. Cada token do nome lido por Vision tem que estar no nome do BD (sem ordem importar). Cobre G2 e elimina sensibilidade a "Sunday/Daily/etc" omitidos. | 🔴 ALTA | ~1-2h |
| **B** | Estender `tm_resolver` em 2 frentes: (i) fallback consulta `hands` directamente quando `tournaments_meta` retorna 0 rows — group by `(tournament_number, tournament_name, MIN(played_at))` com janela `±2h`. (ii) Aceitar `posted_at_hint: Optional[datetime]` (passar `message.created_at` do handler Discord); precedência `start_time_iso ±2h` → `posted_at_hint [-12h, -30min]` → fallback `LIMIT 5`. SS é tirada durante o torneio, logo torneio começou antes de posted_at. Cobre G1 (Winamax/PS) + mitiga G3 parcialmente. | 🔴 ALTA | ~1.5h |
| **C** | Suportar caption manual com TM no `message.content`: regex `\b(?:#|TM)?\s*(\d{8,12})\b`. Quando presente, override do Vision-resolved TM e bypass do resolver. Cobre G3 e qualquer caso ambíguo futuro. | 🟡 MÉDIA | ~30 min |
| **E** | Refactor manual sync de lobbys: endpoint `POST /api/lobbys/sync-recent` + botão UI. Permite backfill retroactivo do canal `#lobbys` sem depender de `LOBBY_AUTO=true` global. Útil quando Rui posta SS em batch. | 🟡 MÉDIA | ~2-3h |
| **D** | Suporte Gyazo URLs em `_handle_lobby_message` — extrair imagem do `message.content` quando contém `gyazo.com` link. | 🟢 BAIXA | ~1h |
| **F** | Cleanup `[debug-msg-lobby]` instrumentation + lobby channel list log no `on_ready` após pipeline estável (commit "remove temporary instrumentation"). | 🟢 BAIXA | ~10 min |

### Tech Debts IRE (carry-over de pt16, sem trabalho em pt18)

Mantêm-se em backlog: **#IRE-MB**, **#IRE-CL**, **#IRE-VB**, **#IRE-SK** (ver secção "Estado actual (8 Maio 2026 — pós-pt16, investigação IRE prod)" abaixo). Não atacados em pt18 por foco em FASE 1 + FASE A.

### Tech Debts FASE 3 (carry-over de pt18)

**#FASE-3-MINIPC** (Beelink GTR5) mantém-se 🔴 ALTA mas **adiada até FASE A pipeline lobbys completo** (= commits A+B+C+E fechados e pipeline a fazer upserts reais consistentemente).

---

## Estado actual (8 Maio 2026 — pós-pt16, investigação IRE prod)

Sessão de investigação read-only sobre o IRE v2 em prod (deployed pt16). 3 tech debts identificados, todos do lado IRE; nenhum requer mudança no `compute_ire` core nem no W3cray lookup.

### #IRE-MB — Monster Bounties tratado como PKO 25% (bug crítico)

- **File:** `backend/app/services/ire.py` (`compute_ire`, gates de filtragem) + `backend/app/services/tournament_meta.py` (schema `tournaments_meta`).
- **Origem:** Investigação prod 2026-05-08 sobre 6 mãos. Hand id=29675 é do torneio "$215 Sunday Bounty Overload [Monster Bounties]" — Monster Bounties = ratio bounty 75%, não 25%.
- **Vector:** A tabela W3cray hardcoded em `ire.py:54-76` (`W3CRAY_TABLE_25PCT`) é exclusivamente para ratio 25% (PKO standard). O único guard contra ratios diferentes é a deny-list textual `SUPER_KO_NEEDLE = "super ko"` que esconde Super KO 40%. Monster Bounties 75% **não** está na deny-list → IRE é calculado mas o valor está errado contra a tabela errada. UI mostra um número aparentemente válido que não corresponde à realidade do torneio.
- **Severidade:** 🔴 Funcional crítico. Dados errados apresentados como certos — pior que esconder.
- **Status:** **por corrigir**.
- **Solução temporária (~1h):** alargar a deny-list para apanhar todos os formatos não-25%. Adicionar needles tipo `"monster bounties"`, `"mystery bounties"` (case-insens). IRE fica escondido em vez de errado.
- **Solução robusta (~4h):** adicionar coluna `pko_ratio NUMERIC(4,2)` em `tournaments_meta` (ex: 0.25, 0.40, 0.75) com derivação automática via parser de nome do torneio + override manual. `compute_ire` selecciona a tabela W3cray correcta (ou fórmula fallback) consoante `pko_ratio`. Permite suportar todos os formatos sem deny-list crescente.
- **Esforço:** 1h (deny-list temporária) ou 4h (coluna `pko_ratio`).

### #IRE-CL — Clamp duro em off-table (sem fallback fórmula)

- **File:** `backend/app/services/ire.py:149-181` (`_nearest_idx`, `lookup_ire_pct`, `_formula_fallback`).
- **Origem:** Investigação prod 2026-05-08.
- **Vector:** A tabela W3cray é 17 linhas (stack_si 0.25–7.0) × 9 colunas (ko_units 1–5). Quando `(stack_si, ko_units)` cai fora destes limites, `_nearest_idx` faz **clamp para nearest-neighbour** (`if value <= axis[0]: return 0; if value >= axis[-1]: return len(axis)-1`). O `_formula_fallback` só é invocado quando a célula da tabela é `None` — não quando estamos genuinamente off-table. Resultado: stacks deep (>7×SI) ou bounties acumulados (>5 KO_iniciais) recebem o valor da última célula da tabela, que pode estar muito longe do correcto.
- **Severidade:** 🟡 Funcional. Valores aproximados grosseiros em casos extremos (late-stage MTT com stacks muito deep ou bounties acumulados).
- **Status:** **por iterar**.
- **Fix proposto:** detectar off-table antes do clamp (`if stack_si > rows[-1] or ko_units > cols[-1]: return _formula_fallback(...)`). Mantém clamp apenas para casos *interpolados* dentro do envelope da tabela.
- **Esforço:** ~2h (lógica + testes contra Mathematics.xlsx em ≥3 pontos off-table).

### #IRE-VB — Cobertura silenciosa zero quando Vision falha bounty_pct

- **File:** `backend/app/routers/screenshot.py` (Vision pipeline) + `backend/app/services/ire.py:282-284` (gate `any(op["ko_pct"] > 0)`).
- **Origem:** Investigação prod 2026-05-08 — 3 mãos sem badge IRE (18726, 19798, 20886) revelaram causa.
- **Vector:** Vision (GPT-4o-mini) falha por vezes em extrair `bounty_pct` da SS (% pouco legível, cortado, ou prompt não converge). Quando isso acontece, **todos** os jogadores no `players_list` ficam com `bounty_pct=0` e o mesmo se propaga para `all_players_actions`. O `compute_ire` deteca isto no GATE 9 (`not any(op["ko_pct"] > 0)`) e devolve `None` silenciosamente — UI esconde o badge sem qualquer aviso. Confirmado: 3/3 mãos afectadas têm config válida (GG PKO, `match_method='anchors_stack_elimination_v2'`, `starting_stack` válido, tag `icm-pko`); diferença é exclusivamente Vision-OCR. Nota: 20886 é mesmo torneio-tipo que 20879/20827 (Deepstack Turbo $88, SI 20k) — mesma config, resultados Vision diferentes em SSs distintas.
- **Severidade:** 🟡 Funcional. Sem corrupção de dados, mas o utilizador perde silenciosamente o IRE em mãos onde devia aparecer; sem sinal nenhum de que a Vision falhou esse campo específico.
- **Status:** **por iterar**.
- **Possíveis abordagens:**
  - **(a) Re-correr Vision com prompt melhorado** focado no campo bounty (~3h): ajustar prompt + re-processar entries afectadas + medir hit rate. Custo OpenAI moderado.
  - **(b) Parser de bounty do HH GG** (~5h): GG escreve `Total Bounty Awarded:` ou similar nas linhas de showdown. Parsear estas linhas dá ground-truth sem depender de Vision. Funciona retroactivamente sobre todas as HHs em BD, mas só apanha bounties de jogadores que efectivamente bustaram alguém na mão (não captura `bounty_pct` actual de jogadores que ainda não bustaram ninguém).
  - **(c) Aviso na UI quando bounty missing em PKO** (~1h): se mão é PKO/Mystery KO + match real + zero bounties detectados, mostrar badge cinza tipo "IRE indisponível (bounty não lido)" em vez de esconder silenciosamente. Não corrige a causa, mas torna a falha visível.
- **Esforço:** 3-5h (consoante abordagem).
- **Detectado em:** mãos id=18726, 19798, 20886 (todas GG PKO 2026, todas com SS matched, todas com `bounty_pct=0` em todos os jogadores).

### #IRE-SK — Super KO 40% (e outros ratios não-standard) escondido

- **File:** `backend/app/services/ire.py:42` (`SUPER_KO_NEEDLE`) + `ire.py:54-76` (`W3CRAY_TABLE_25PCT`) + `ire.py:228-230` (gate de filtragem por nome do torneio).
- **Origem:** Decisão de design v2 (pt16): expor IRE só para PKO standard 25%; esconder activamente Super KO 40% via deny-list. Outros ratios (Mystery KO 33%, Monster Bounties 75%) não estão na deny-list e caem em #IRE-MB.
- **Vector:** O lookup `lookup_ire_pct` consulta `W3CRAY_TABLE_25PCT` — tabela hardcoded para ratio 25%. Não há suporte para ratios diferentes; a única defesa contra falsa apresentação é a deny-list textual de nomes (`"super ko"` em `SUPER_KO_NEEDLE`). Resultado:
  - Super KO 40% → IRE escondido (gate `SUPER_KO_NEEDLE in tname`).
  - Mystery KO 33% → não-coberto (nem escondido, nem suportado correctamente — ver #IRE-MB).
  - Monster Bounties 75% → idem (#IRE-MB).
- **Severidade:** 🟡 Funcional. Não corrompe dados; só limita cobertura do produto. Rui perde análise IRE em formatos que joga (Super KO regularmente).
- **Status:** **por implementar**.
- **Solução A — tabelas W3cray paralelas por ratio (~3-4h):** uma tabela hardcoded `W3CRAY_TABLE_<ratio>PCT` para cada ratio suportado (25, 33, 40, 75). Validação de cada tabela contra Mathematics.xlsx sheet IRE para o ratio respectivo. `lookup_ire_pct` recebe `ratio` como param e selecciona a tabela. Vantagem: replica exactamente o que a Excel devolve (acceptance criterion). Desvantagem: requer Mathematics.xlsx ter sheets para todos os ratios pretendidos.
- **Solução B — fórmula matemática genérica (~2-3h):** generalizar `_formula_fallback` para aceitar qualquer ratio (`bounty_si = ko_units * ratio`) e usá-la como fonte primária quando ratio ≠ 25%. Vantagem: funciona para qualquer ratio sem tabela. Desvantagem: a fórmula é aproximação; pode divergir da W3cray real (que tem ajustes de modelo não-fórmula).
- **Híbrido recomendado:** tabela paralela para ratios comuns (25, 33, 40, 75) + fórmula fallback para ratios raros. Mantém precisão onde importa, cobertura onde for preciso.
- **Dependência:** **idealmente resolver #IRE-MB primeiro** — coluna `pko_ratio` em `tournaments_meta` permite detectar o ratio sem pattern matching frágil sobre nomes. Sem isso, a deny-list/needle-list cresce indefinidamente.
- **Esforço:** 3-4h (consoante solução A vs híbrido; ambos assumem `pko_ratio` resolvido por #IRE-MB).

---

## Estado actual (9 Maio 2026 — planeamento FASE 3)

Sessão de planeamento da FASE 3. FASE A (pipeline lobbys via Discord) em curso paralelamente — sem overlap directo. Esta entry regista a infra-estrutura nova (mini PC dedicado) que vai correr o watcher HRC 24/7 quando FASE A C3 estabilizar.

### #FASE-3-MINIPC — Mini PC dedicado para watcher HRC

- **Prioridade:** 🔴 ALTA (futura — apenas após FASE A C3 estabilizar).
- **Origem:** decisão Rui 9-Mai-2026.
- **Contexto:** Rui tem mini PC parado disponível. Decisão de o dedicar a watcher HRC 24/7, libertando o PC principal para jogar poker (sem o conflict ToS das salas a verem processos análise activos durante sessão).
- **Hardware (validado):**
  - Beelink GTR5
  - CPU: AMD Ryzen 9 5900HX (8C/16T, 3.3-4.6 GHz, Zen 3)
  - RAM: 32 GB DDR4 3200 MHz
  - Storage: 500 GB NVMe SSD
  - iGPU: AMD Radeon Vega 8
  - Network: Dual 2.5GbE + WiFi 6E
  - OS: Windows 11 Pro pré-instalado
- **Setup confirmado:** monitor + teclado + rato disponíveis (setup local). Mesma divisão do PC principal. WiFi por default; Ethernet opcional. Licença HRC já existente.
- **Limitação:** iGPU sem CUDA — **NÃO** permite OCR/Vision local (PaddleOCR-VL ou similar). Irrelevante para watcher HRC (que só consome cálculo CPU + filesystem queue), mas elimina cenário "all-in-one" (watcher + Vision local).
- **Plano (3 sub-steps):**
  1. **Setup ambiente:** HRC + Python 3.12 + watcher script (porting/adaptação do `hrc_watcher.exe` do amigo Baltazar — análise estática completa em `_local_only/ANALYSIS.md`).
  2. **Sync loop:** poll `GET /api/queue/hrc` → import zip → run analysis no HRC → POST `/api/queue/hrc/results` (endpoint a criar em FASE 4).
  3. **Operação 24/7:** auto-restart, logging estruturado, monitorização (uptime + queue depth).
- **Dependências:**
  - FASE 1 ✅ (queue endpoint deployed em prod, `da36f56`).
  - FASE A em curso (popular `tournament_payouts` via Discord lobby Vision).
  - Watcher Python script (a adaptar/escrever — base no exe do Baltazar).
  - Endpoint upload resultado `POST /api/queue/hrc/results` (FASE 4).
- **Estimativa:** 6-10h Code + algumas horas Rui setup HW.

---

## Estado actual (7 Maio 2026 fim pt15)

pt15 foi sessão exclusiva de iteração visual — UI/UX. Sem mudanças de backend, parsers, schema ou dados. Painel torneio (TournamentHeader + Hands.jsx Estudo), popup do replayer (ReplayerPage), e cartas de poker (9 callers) reformulados. Detalhes em `JOURNAL_2026-05-06-07-pt15.md`.

- **Sessão pt15 fechou**: zero tech debts numerados de backlog (sessão visual não atacou tech debts pendentes).
- **Sessão pt15 introduziu** 1 novo tech debt: 8 cópias inline de `PokerCard` + 1 shared (ver §pt15 abaixo).
- **Sessão pt14 fechou** (não documentado nesta inventário ainda): #P10. **Pendentes carry-over de pt14**: #P9, #P11, #P12.

### Tech Debts e pendências pt15

#### Tech Debt nova
| # | Descrição | Esforço |
|---|---|---|
| **#TD-pt15-1** | Unificar 8 cópias inline de `PokerCard` num componente único (`components/PokerCard.jsx` shared). Cópias actuais em: `HandRow.jsx`, `Dashboard.jsx`, `Discord.jsx`, `Hands.jsx`, `HM3.jsx`, `Tournaments.jsx`, `Replayer.jsx` (RCard), `ReplayerPage.jsx` (RCard), `HandDetailPage.jsx` (RCard). Divergências entre cópias (sizes, paletas) já harmonizadas em pt15 mas mantidas em código separado. | ~1h |

#### Pendências de iteração visual (média prioridade — opcional UX)
- **Tournaments e HM3**: aplicar mesma limpeza visual do Estudo (bareMode + watermark)? Adiada nesta sessão. Decisão Rui se aplicar a todas as páginas para consistência ou manter modo normal nessas duas.
- **Replayer head-up**: D + SB badges sobrepostas no mesmo player (BTN = SB em head-up). Cenário raro em MTT.
- **Replayer slot único topo (50,10)**: badge cobre o nome do player. Aceitável por agora, melhorar se aparecer queixa.

#### Housekeeping (baixa prioridade)
- **Assets em `frontend/public/logos/`** ficaram não-referenciados após pt15: `gg1.png`, `gg2.jpg`, `ya.webp`, `wina1.png`, `wina2.png`, `ps.png`. Apenas `gg_horizontal.png` e `ps_logo.png` em uso. Candidatos a remoção numa sessão futura de housekeeping.
- **`composeTournamentTitle` em `HM3.jsx`**: sem callers depois da iteração customTitle (substituída por extracção inline). Limpeza cosmética.
- **`components/Replayer.jsx`** (legacy, distinto de `pages/ReplayerPage.jsx`): possivelmente não-usado. Verificar e remover se confirmado.

#### Backlog operacional carry-over (NÃO atacado em pt15)
- **Discord/HM3 tag fragmentation** (carry-over de sessões anteriores) — afecta quase todas as study hands. URGENTE quando voltarmos ao backend.
- **2nd Discord entry para duplicate TMs** — pendente.
- **Discord pipeline para Winamax replayer URLs** (Vision não extrai TM dos URLs Winamax).
- **71 SS Discord sem match** (Replayer 57 + Imagem 14): listagem com link/data/origem, pendente investigação.
- **Estudo: torneios estudados rasurados** → desaparecem; toggle para mostrar ocultos.

---

## Estado actual (4 Maio 2026 fim pt13)

pt12 fechou #B33 (regressão da Onda 8 do refactor #B23 documentada em pt11 retrospectivo). Root cause: regex `r'TM(\d+)'` em `screenshot.py:307` exigia prefixo `TM` literal; Vision omitiu em 2/26 entries. Fix: word-boundary `r'\b(\d{8,12})\b'` (commit `e7d88b2`). Backfill retroactivo curou as 2 hands afectadas (id=2083, id=2297) — hand 2297 ganhou 2 villains via Regra C; hand 2083 ficou em canal `icm-pko` com `mm` populado mas 0 villains (correcto). BD final: 1172 hands, 24 enriched, 47 villains, 7/7 nota com villains. **Onda 8 do refactor #B23 declarada COMPLETA.**

- **Sessões pt9 + pt10 fecharam:** #B12, #B14, #B15, #B16, #B17, #B18, #B19, #B19-ext, #B23, #B27, #B32 (11 tech debts).
- **Pendentes numerados pós-pt10:** #11, #B10, #B11, #B13, #B-edge, #B20, #B21, #B26, #B28, N1, N2, N3.
- **Pendentes não-numerados:** path bulk archive `mtt_hand_id` legacy (4 call sites em `mtt.py` — REGRAS §8).
- **Onda 8 e 9 do refactor #B23 ficaram em estado "parcial":** teste regressão (delete + re-import GG ZIP) e validação manual visual SS↔HH adiados para pt11.
- **Onda 9 (pt11)** — Rui validou visualmente 3/3 hands canal nota (1070, 261, 878). Algoritmo SS↔HH confirmado correcto em prod. **ONDA 9 FECHADA ✓**
- **Onda 8 (pt11+pt12)** — re-import GG ZIP correu 3-Mai 14:11 UTC. Estado pt11 inicial: 22 enriched, 45 villains, 6/7 nota com villains (regressão #B33). Pt12 fix + backfill retroactivo: **24 enriched, 47 villains, 7/7 nota com villains. ONDA 8 FECHADA ✓**

### Tech Debts fechados pt13

| # | Hash | Descrição |
|---|---|---|
| **#B-NOVO-2** ✅ | `554cafb` | Resolvido por #B32 (pt10) + assert defensivo extra. Verificação prod confirmou `degenerate_count=0`. Sem evidência de re-aparecimento. Assert em `screenshot.py:_enrich_hand_from_orphan_entry` antes da chamada a `_build_anon_to_real_map`: levanta `ValueError` explícito se apa só tem `_meta` (placeholder-only) — torna a falha visível em vez de silent skip. |
| **#B29** ✅ | `d478b68` | hands_seen double-count em refix. Investigação: prod limpo (inflação=0), mas código tinha 2 sítios desprotegidos (`mtt.py:_create_villains_for_hand` e `mtt.py:re_enrich_all`). Opção α: removidos os 2 blocos UPSERT redundantes + dead code associado (-32 linhas net). Comentários explicativos no código. `apply_villain_rules` continua single source of truth com Q6 guard. |
| **#B31** ✅ | `b455ff5` | MAPA_ACOPLAMENTO actualizar para refactor #B23 + #B29 + vilão principal. §7.4 substituída (doc canónica de `apply_villain_rules`), §7.5 nova (call sites). §6.3 distingue UI filter (A∨B∨C, branch B dead pós-#B8) vs classification logic (A∨C∨D). 7 cross-refs actualizadas em §2.1, §2.8, §5.2, §5.4, §7.3, §8.1. Opção α adoptada para `VILLAIN_ELIGIBILITY_CONDITION` — branch B mantido no SQL como dead code documentado em vez de remover. |
| **#B22** ✅ | `875be7a` | Dashboard reordenar painéis (SS subiu para nível 2) — fechado como parte do refactor Dashboard expandido |
| **Refactor study_state** ✅ | `c3c14c4` | 4 estados → 3 (remove review+studying nunca usados). Apaga Inbox.jsx (-1034 linhas). UI mostra "Nova"/"Revista". |
| **Dashboard expandido** ✅ | `875be7a` | Painel Mãos por estudar com top 3 tags + 4 salas. Total de mãos com X revistas. SS sobe para nível 2. OrphanList paginação 10+10. |

### Tech Debts fechados pt12

| # | Hash | Descrição |
|---|---|---|
| **#B33** ✅ | `e7d88b2` | Regex TM em parser Vision tolerante a omissão do prefixo (`r'TM(\d+)'` → `r'\b(\d{8,12})\b'` em `screenshot.py:307`). Cura retroactiva: 2 entries afectadas (id=30, id=36) → hands 2297 e 2083 enriched + villains criados onde aplicável (hand 2297: 2 villains via Regra C; hand 2083: 0 villains, canal `icm-pko` não-nota). |
| **Vilão Principal** ✅ | `0ebacfd` | `apply_villain_rules` filtra candidates a quem chegou mais longe na mão. Spec definida + implementada + backfill retroactivo (47→34 `hand_villains`, 7/7 nota preservadas). Sem migration. Validado visualmente em prod pelo Rui. |
| **GTO 404** ✅ | `304eecf` | Router `gto.py` não estava wired em `main.py:include_router` (fix 2 linhas, smoke test HTTP 401). |
| **#13c** ✅ | `d959ad8` | SITE_COLORS aliases legacy removidos; callers (Dashboard.jsx, HandRow.jsx) consolidados a `SITE_COLORS` directo. 3 ficheiros tocados. |
| **#B25** ✅ | `ba2792b` | Agrupar torneios por `tournament_id`. Fix bugs cross-midnight (chave `${day}__${name}` dividia 1 torneio em 2) e nomes duplicados (chave `${name}` fundia torneios distintos). Ambos os modos passam a usar `tm:${tournament_number}` como chave. |
| **Stack Inicial GG** ✅ | `68a9e8a` + `799864e` + `457048f` + `a2158c3` | Tabela canónica `tournaments_meta` (PK `tournament_number+site`, restrito a GG). Hook em `_run_zip_import`, endpoint `GET /api/tournaments/meta?tms=...`, frontend lookup com fallback graceful. Backfill 26 TMs → 20 rows GG. |
| **#B34** ✅ | `43c0041` | ID hand visível em todas as vistas (Estudo Por Tags / Por Torneio / Tabela / Cards, Dashboard "Últimas mãos", HandDetailPage Normal+Placeholder, Tournaments drill-down). 4 ficheiros tocados. |
| **#B30** ✅ | `580be1c` | 142 scripts ad-hoc removidos da raiz + 28 patterns adicionados ao `.gitignore`. 3 backfills úteis preservados como tracked. |

### Tech Debts fechados pt9 (carry-over de pt8)

| # | Hash(es) | Descrição |
|---|---|---|
| **#B12** ✅ | (pt9) | Helper centralizado `append_discord_channel_to_hand` propaga `discord_tags` mesmo em hands GG sem match. |
| **#B14** ✅ | (pt9) | Estudo aceitava mãos sem `tournament_name`/`buy_in`/`site` — resolvido na sequência de #B17 (filtros `STUDY_VIEW_*` consolidados). |
| **#B15** ✅ | `1cca3a6` | Estudo passa a excluir mãos só com tag `nota` (HM3 ou Discord). Caso 2 e 5 dos canónicos. |
| **#B16** ✅ | (pt9) | `_apply_channel_tags` cross-post HH text — coberto pelo helper centralizado #B12. |
| **#B17** ✅ | `7806d33` | Estudo unifica tags HM3 + Discord (1 chip por nome normalizado), `OriginBadge` por mão, remove secções por origem. |
| **#B18** ✅ | (pt9) | Drill-down torneio passa a mostrar `OriginBadge` por mão (consistência com Estudo pós-#B17). |
| **#B19** ✅ | `ca9fbc3` + `f0b778d` + `ab8e033` | Vilões aceita non-hero postflop quando `hm3_tags ~ 'nota%'`; bypass da pré-condição `has_cards∨has_vpip`. (estendida em pt10 — ver #B19-ext) |

### Tech Debts fechados pt10

| # | Hash(es) | Descrição |
|---|---|---|
| **#B10** ✅ (mínimo) | `66db5cc` | Persistir `tournament_name` extraído por Vision em `entries.raw_json` (1 linha em `_run_vision_for_entry`). SS uploaded a partir deste commit. Backfill diferido. |
| **#B23** ✅ | `abb6d59` → `8476e87` (8 commits) | Refactor completo: 4 funções de criação de villains → 1 canónica `apply_villain_rules` em `services/villain_rules.py`. 18 call sites unificados (12 migrados, 5 skips legacy `mtt_hand_id` + 1 interno). ~470 linhas líquidas removidas. Resolveu Regra C não-disparada no caminho Discord+ZIP. |
| **#B27** ✅ | `8476e87` | Apagados blocos "Extract villains for nota++ hands" em `hm3.py` + função `_detect_vpip_hm3` redundante. Incluído na Onda 6 do refactor #B23. |
| **#B32** ✅ | `5fe2201` | Enrich SS↔HH não grava mais `match_method='anchors_stack_v2'` com `anon_map` vazio. Guard idempotência verifica também `existing_anon_map` populado. Defesa em camadas: previne novas + cura estado existente quando auto-rematch revisita. |
| **#B19-ext** ✅ | `677a1fb` | Excepção #B19 estendida a `'nota' ∈ discord_tags` (paridade semântica com tag HM3 `nota%`). Variável renomeada `has_nota_hm3` → `has_nota_intent`. Hand 261 passou a ter villains. |

### Tech Debts abertos pós-pt10 (carry-over + novos)

| ID | Título | Severidade | Origem | Esforço |
|---|---|---|---|---|
| **#11** | Botão eliminar villain manual. Decisão pt13: blacklist persistida escolhida; implementação adiada. Historicamente ligado a #12 (re-arquitectura modal). | 🟡 Funcional | pt7 | ~2-3h |
| **#B10** (full) | Vision galeria — extrair `tournament_name` para filtragem (fix mínimo já aplicado) | 🟢 UX | pt7 | ~2-3h |
| **#B11** | Auto-tag mãos via LLM (ideia exploratória) | 🟢 Feature | pt7 | ~3-4h |
| **#B13** | Contadores `last_sync` (N/M/K) medem entries criadas em vez de trabalho útil. Decisão pt13: manter como está, não tocar. Vive na página Discord, não migra para Dashboard. | 🟢 UX | pt8 | ~1h |
| **#B-edge** | Hero detection seat não-central (1/23 ≈ 4.3% taxa) | 🟢 Edge case | pt7 | ~30 min |
| **#B20** | Filtros HM3 por tag (não por nick) | 🟢 UX | pt10 | a estimar |
| **#B21** | Dashboard "por estudar" filtrar por elegibilidade | 🟢 UX | pt10 | a estimar |
| **#B26** ✅ FECHADO pt16 | Investigar cor das TAGS na secção Estudo. Verificado em prod (2026-05-07): chips Discord + `OriginBadge` já existiam (#B17 pt9). Backlog desactualizado, sem código novo. Detalhes em "Estado actual fim pt16" no topo. | 🟢 UX | pt10 | 0 (verificação) |
| **#B28** ✅ FECHADO pt14 | Counter `villains_created` no response do `POST /api/hm3/import` (e por extensão output do `.bat`) ficou silenciosamente em 0 desde refactor #B23 (pt10): a função canónica `apply_villain_rules` passou a devolver `dict` com `n_villains_created` em vez do `int` da predecessora, e os 2 call sites em `hm3.py:930` e `hm3.py:1034` passaram a ignorar o return. Fix: captar return em ambos os call sites e somar `n_villains_created` ao counter. Cosmético — sem efeito em dados, regras de elegibilidade ou pipelines downstream. | 🟡 Funcional | pt10 | ~30 min (consumido) |
| **N1** | MAPA_ACOPLAMENTO.md desactualizado: cabeçalho diz "Última actualização 2026-04-26" + drift pt10/pt12/pt13 (refactor #B23, vilão principal, study_state, tournaments_meta) | 🟢 Docs | pt14 | a estimar |
| **N2** | VISAO_PRODUTO.md tem refs de linha exactas (ex: `hands.py:567-574`, `hands.py:565-566`) que mexem com refactors. Substituir por refs simbólicas (constantes nomeadas) ou re-âncorar | 🟢 Docs | pt14 | ~30 min |
| **N3** | Promover regra "imagens directas Discord NUNCA criam mãos" (anexos `.png/.jpg/.webp` + Gyazo) de CLAUDE.md "Imagens de contexto Discord" para REGRAS_NEGOCIO.md §6 como regra dura | 🟢 Docs | pt14 | ~15 min |
| **#P9** ✅ FECHADO pt14 | Parser `buy_in` em `tournaments_meta` falha em vírgula de milhar — torneio com nome `'$1,050 GGMasters HR'` ficou com `buy_in=1.00`. Causa: regex `\d+(?:\.\d+)?` não suportava `,`. Fix: `_NUM_PATTERN = \d{1,3}(?:,\d{3})*(?:\.\d+)?` + helper `_to_float` em `gg_hands.py:114-148`. Backfill: 245 hands + 1 tournaments_meta. Mini-test 5/5. Commit a registar abaixo. | 🟡 Funcional | pt14 | ~30 min (consumido) |
| **#P10b** ✅ FECHADO pt14 | Queries X1.1 e X1.3 do `VERIFICACAO_PIPELINES.md` overly broad. X1.1 refinada com `STUDY_VIEW_REQUIRES_HH + STUDY_VIEW_HAS_STUDY_TAG` (2970→0). X1.3 refinada como sentinela do filtro UI (combinação contraditória: `STUDY_VIEW_HAS_STUDY_TAG` + "todas as tags = nota" = sempre 0; > 0 indica regressão no filtro UI). Validação BD: 2970→0, 3014→0. | 🟢 Docs | pt14 | ~30 min (consumido) |
| **#P10c** ✅ FECHADO pt14 | Query Q3.6 do `VERIFICACAO_PIPELINES.md` filtro hardcoded substituído por `cardinality(COALESCE(discord_tags, '{}'::text[])) > 0`. Validação BD: 40→57 hands apanhadas (canais como `pos-nko` que estavam invisíveis). | 🟢 Docs | pt14 | ~10 min (consumido) |
| **#P11** | Parser `_extract_buyin_numeric` apanha **primeiro `$X,YYY`** do nome do torneio sem distinguir buy-in vs prize pool. Caso real Fase B: `Daily $100,000 #ThanksGG Flipout` ficou com `buy_in=100000.00` (era GTD/prize pool, não buy-in). Magnitude: 1/236 torneios em pt14 Fase B (0.4%). Resolvido caso pontual com DELETE; fix conceptual aberto: parser semântico que reconheça padrões `$X GTD` / `$XM GTD` como prize pool. | 🟢 UX/Cosmético | pt14 | ~45 min |
| **#P12** | Parser não tolera símbolos monetários não-Latin1 (yuan ¥, won ₩, yen ¥). Torneios em moedas asiáticas vêm com `�` (replacement char U+FFFD) onde devia estar o símbolo monetário. Caso real Fase B: `Zodiac Late Night 6-Max �220` ficou com `buy_in=NULL`. Magnitude: 1/236 torneios em pt14 Fase B (0.4%). Causa: encoding Latin-1/Win-1252 do ficheiro GG antes do parser. Fix futuro: ler ficheiros com encoding UTF-8 ou parser tolerante a símbolos não-`$`. | 🟢 UX/Cosmético | pt14 | ~30 min |
| **#P13** ✅ FECHADO pt14 | Endpoint `process-replayer-links` com `limit` hardcoded 200 em `sync-and-process` + `ORDER BY id DESC` cortava entries silenciosamente quando volume >200. IDs mais baixos (canais sincronizados primeiro pelo bot) ficavam sempre fora do batch. Detectado pt14 Fase B: 83/283 entries (29%) cortadas, **100% das 67 mensagens do canal `nota` afectadas**. Adicional: filtro `img_b64 IS NULL` não cobria estado intermediário (img extraído mas Vision pendente). Fix em commit 2f15445: paginação interna até esgotar candidatos + cap defensivo 50 iter + `ORDER BY id ASC` (cronológico) + secção 4b inline em `sync-and-process` para apanhar estado intermediário + counter `new_entries` expandido. Validado em prod: 83 entries recuperadas, 72 hands canal `nota` enriched, 88 villains via Regra C criados (80 nicks únicos), princípio invariante GG anon mantido. | 🔴 Funcional | pt14 | ~2h (consumido) |
| **`mtt_hand_id` legacy** | 4 call sites em `mtt.py` (linhas 1264, 1882, 2202, 2297) ainda passam `mtt_hand_id` em vez de `hand_db_id`. REGRAS §8. | 🟢 Refactor | pt10 | a estimar |

### Pendente operacional pt11

- **Onda 8** — teste regressão (delete + re-import GG ZIP) confirma que pipeline produz mesmo resultado em re-execução.
- **Onda 9** — validação manual visual SS↔HH (Rui escolhe 3-4 hands ao calhas, valida visualmente que nicks atribuídos batem com imagem do SS).

---

## Estado actual (30-Abr fim pt8)

- **Total Tech Debts numerados detectados:** 25 (#1–#22, sem #19; +#UX1; +#B12 pt8; +#B13 pt8)
- **Fechados pt8:** 3 (#18 validado empiricamente, #15 fix Dashboard, #B7 cursor Discord)
- **Fechados pt7:** 9 (#10, #21, #B1, #B2, #B4, #B8, #B9, #12, #UX1) + 17 anteriores = **29 totais fechados** (incl. #18+#15+#B7 pt8)
- **Pendentes numerados:** #11, #13c, #B10, #B11, #B12, #B13, #B-edge
- **Bugs latentes não-numerados detectados em pt7:** 4 (registados §3 abaixo)
- **Feature nova pt8:** sincronização Discord manual com janelas (24h/72h/1sem/15d/1mês/custom) — substitui botão "Sincronizar Agora"

### Sumário pt7 (9 Tech Debts fechados)

| # | Hash(es) | Descrição |
|---|---|---|
| **#21** ✅ | `d61a241` | Idempotência `_enrich_hand_from_orphan_entry` |
| **#10** ✅ | `e74df0c` | Parser HM3 nicks com espaço (regex universal seat_nicks) |
| **#B1** ✅ | `c90b1b9` | Stack matching tolerância dinâmica `max(20, 2%)` |
| **#B2** ✅ | `0c0a1d3` | Anchor SB/BB via `difflib.SequenceMatcher` ratio≥0.85 |
| **#B4** ✅ | `82afcd7` | Phase 3 elimination brute-force optimal assignment |
| **#B8** ✅ | `ce56d59` | Regra B (auto-create cat='sd' showdown) removida + cleanup BD |
| **#B9** ✅ | `f98f8c8`→`cc2161c` (6 commits) | Bucket 1 automático → galeria manual de imagens |
| **#12** ✅ | `8871d1b`→`3c7dc13` (7 commits) | Refactor modal villain (layout, alinhamento, cores per-acção) |
| **#UX1** ✅ | (incluído `#12`) | Cards villain mostradas (não Hero) — fix bug pt6 |

### Tech Debts fechados pt8 (3 total)

| # | Hash | Data | Validação | Descrição |
|---|---|---|---|---|
| **#18** ✅ | (docs only) | 2026-04-30 | Empírica BD prod | Não-determinismo cross-post resolvido estruturalmente pelo guard #21. 1 hand cross-post real (1115) com APA coerente, 23 hands enriched protegidas pelo guard, 0 divergências. Sem fix de código necessário. |
| **#15** ✅ | `8919840` | 2026-04-30 | Visual frontend | Dashboard "Últimas mãos" passa a mostrar created_at (data import) + linha secundária "jogada DD Mmm" só quando played_at é dia diferente. Backend já ordenava por created_at desde 16-Abr; fix foi à apresentação. |
| **#B7** ✅ | `9d57b2b` | 2026-04-30 | Code + audit | `_get_sync_cursor` devolve `(last_message_id, last_sync_at)`; precedência (a) snowflake > (b) datetime > (c) APP_EPOCH_CUTOFF (1 Jan 2026 Lisbon hardcoded). Fix afecta `/sync` e `/sync-and-process`. |

### Feature nova pt8

| Hash | Descrição |
|---|---|
| `7ad41d4` | UI Discord painel inline com chips de janela (24h/72h/1sem/15d/1mês) + custom (De/Até). Endpoint POST `/api/discord/sync-and-process` aceita body opcional `{window?, from?, to?}`. Override de `discord_sync_state` antes do sync (`last_message_id=NULL, last_sync_at=from_clamped, messages_synced=0`) — usa precedência (b) do #B7. Response ganha `last_sync` com {window_label, from, to, n_links, m_canais, k_match_hh}. Banner "⟳ A sincronizar..." durante sync; sub-linha "Última sync: agora · janela X · N · M · K" persistente após. |

### Tech Debts pendentes para sessão pt9 (ordem prioridade)

| ID | Título | Severidade | Esforço |
|---|---|---|---|
| **#B12** | Hands GG anonimizadas com cross-post Discord não recebem `discord_tags` populado | 🟡 Funcional menor | ~1h investigação |
| **#B13** | Contadores `last_sync` (N/M/K) medem entries criadas em vez de trabalho útil | 🟢 UX | ~1h |
| **#11** | Botão eliminar villain manualmente do modal HandDetailPage | 🟡 UX | ~2-3h |
| **#B11** | Auto-tag mãos via LLM (ideia exploratória pt7) | 🟢 Feature | ~3-4h |
| **#B10** | Vision não extrai `tournament_name` da imagem na galeria | 🟢 UX | ~2-3h |
| **#B-edge** | Hero detection seat não-central (1/23 = 4.3% taxa) | 🟢 Edge case | ~30 min |
| **#13c** | Housekeeping aliases SITE_COLORS legacy | 🟢 Housekeeping | ~10-15 min |

#### Tech Debts pré-existentes mantidos (não atacados pt7)

| ID | Título | Severidade | Notas |
|---|---|---|---|
| **#22** | (consolidado em fixes #B1+#B2+#B4 — ver §3 abaixo) | — | Considera-se dissolvido nos fixes preventivos pt7 (validado 117/117 + 32/32 OK FASE 2) |
| **#13c** | Housekeeping aliases legacy SITE_COLORS | 🟢 | (idem cima) |

---

## §2. Bugs latentes detectados nesta auditoria pt7 (read-only código)

<!-- TODO futura: §2 tem entries ✅ RESOLVIDO misturadas com bugs ainda abertos. Limpar separadamente. -->

Identificados por leitura directa do código + cross-check com docs. **Não documentados em journals anteriores** — registo aqui para decisão Rui sobre numeração formal.

### #B1 — Stack matching tolerância rígida 2.0% em micro-stacks
- **File:** `screenshot.py:637-639`
- **Vector:** `if pct < 2.0 and diff < best_diff` — para stack_esperado=51 chips, 2% = 1.02 chip; diff inteiro de 2 já reprova. Stacks deep (>10k) nunca falham; stacks <500 falham frequentemente (false negatives).
- **Severidade:** Funcional (perde fold matches em micro-stacks; cai em Fase 3 elimination que é menos fiável).
- **Fix proposto:** `pct < 2.0 OR diff <= 2` (absoluto) — mantém deep stack tight, relaxa micro.
- **Esforço:** ~15 min + 1 backfill validação.

### #B2 — Hero/SB/BB matching frágil por `startswith(name[:6])`
- **File:** `screenshot.py:569, 582, 595`
- **Vector:** Quando 2 Vision nicks começam pelo mesmo prefixo de 6 chars ("Ander..."), o primeiro encontrado ganha. Sem Levenshtein, sem suffix check.
- **Severidade:** Funcional (false positive raro mas existe).
- **Fix proposto:** Levenshtein distance ≤2 vs vision_sb/bb completo, ou Jaro-Winkler.
- **Esforço:** ~30 min + biblioteca `python-Levenshtein` ou implementação ad-hoc.

### #B3 — Fallback silencioso quando vision_sb/bb=None
- **File:** `screenshot.py:586-588, 599-601`
- **Vector:** Se Vision falha em ler painel esquerdo, `vision_sb=None`. Branch `if player_key not in anon_map: anon_map[player_key] = vision_sb` insere `None` como nome. Downstream `_enrich_all_players_actions` trata como string vazia → APA com chave `None` ou `""`.
- **Severidade:** Funcional (silently broken APA quando Vision parcial).
- **Fix proposto:** Skip atribuição se sb/bb None. Logger.warning("Vision SB/BB None, deixar para Fase 3").
- **Esforço:** ~15 min.

### #B4 — Fase 3 greedy sem tie-breaking nem optimal assignment
- **File:** `screenshot.py:659-683`
- **Vector:** Para cada unmapped HH (na ordem do dict, não-determinística entre Python versions/imports), busca vision com diff mínimo. Sem tie-breaking quando 2 vision têm `diff` igual; sem Hungarian algorithm que minimiza diff total.
- **Severidade:** Funcional (potencialmente origina #22 quando combinado com keys-corruptas).
- **Fix proposto:** Hungarian algorithm via `scipy.optimize.linear_sum_assignment`. Custo ~20 linhas.
- **Esforço:** ~1-2h + dependência scipy (já em requirements? confirmar).

### #B5 — Heartbeat blocked durante Vision pesado
- **File:** logging async não confirmado, mas mencionado em sessão pt6 indirectamente
- **Vector:** Vision sync chamada (call OpenAI) bloqueia event loop FastAPI durante ~3-10s; durante esse período, healthcheck Railway pode falhar.
- **Severidade:** Operacional (Railway pode reciclar replica em healthcheck timeout).
- **Fix proposto:** confirmar se Vision call está em `BackgroundTasks` ou `asyncio.create_task` (já está em `_run_vision_for_entry` linha 1280-1286 com BackgroundTasks). Se sim, bug pode ser falso positivo. Validar logs Railway por entries `vision_ms > 5000ms`.
- **Esforço:** ~30 min (audit + ajuste threshold).

### #B9 — Bucket 1 não valida `tournament_name` ao fazer match imagem ↔ hand ✅ RESOLVIDO via substituição

- **File original do bug:** `backend/app/routers/attachments.py:180-248` (`_find_primary_match`, `_find_fallback_match`)
- **Vector:** Match temporal ±90s assume 1 torneio activo por janela. Quando jogador corre N torneios em paralelo (caso Rui = 9 torneios concorrentes), match falha sistematicamente. Fallback `hm3_temporal_fallback` é ainda pior — ignora canal e tournament_name, só compara timestamps.
- **Severidade:** Funcional grave (data corruption: imagens anexadas a mãos erradas).
- **Magnitude pt7:** 1/3 attachments confirmado errado pelo Rui (image `$88 Daily Hyper Special` anexada a hand `$525 Bounty Hunters HR`). Audit BD revelou 7-9 torneios distintos com mãos activas dentro de ±5min em cada caso → match temporal sem cruzamento de tournament_name é estatisticamente garantido a falhar.
- **Solução escolhida (29-Abr pt7):** **substituição completa por anexação manual** em vez de fix algorítmico. Bucket 1 automático é desactivado; utilizador escolhe explicitamente que imagem anexar a que mão via galeria UI.
  - Backend: novos endpoints `GET /api/images/gallery`, `POST /api/hands/{id}/images`, `DELETE /api/hands/{id}/images/{ha_id}`. Triggers Bucket 1 (`_find_primary_match`, `_find_fallback_match`) descontinuados.
  - Frontend: tag #imagens na página Discord, secção "Imagens anexadas (N)" no modal de mão, popup galeria com filtros canal+data.
- **Cleanup BD:** 3 hand_attachments rows apagados (entries image preservadas).

### #B10 — Vision não extrai `tournament_name` da imagem da galeria (futuro)

- **File:** `backend/app/routers/attachments.py` (futuro: helper `_extract_tournament_from_image`)
- **Vector:** A galeria manual de imagens (#B9 fix) deixa o utilizador escolher 1 imagem da lista, mas a lista não tem o `tournament_name` da imagem visível — só metadata Discord (canal, hora, autor). Para Rui filtrar/encontrar imagem certa, precisa abrir thumbnail e ver header. Vision (GPT-4o-mini) extrair `tournament_name` automaticamente do header da imagem permitiria filtragem na galeria por torneio.
- **Severidade:** UX (não bloqueia, melhora ergonomia).
- **Esforço estimado:** ~2-3h (helper Vision + threading + persistir em entries.raw_json).
- **Custo operacional:** ~$0.005 por image processada (~16 imagens actuais = $0.08).
- **Status:** Adiado para sessão futura. Galeria manual #B9 funciona sem isto.

### #B8 — Regra B (auto-create villain cat='sd' via showdown) era falso positivo ✅ RESOLVIDO

- **File:** `backend/app/services/hand_service.py:74-76` (removido)
- **Vector:** `_classify_villain_categories` regra B criava `category='sd'` automaticamente quando `has_real_match AND has_showdown AND has_cards`. Heurística partiu da assunção "showdown + cards reveladas = villain interessante", mas regra de negócio real é "tag `nota` explícita → entra em Vilões". Showdown sem tag não interessa para Vilões. Detectado pt7 quando NemoTT (mostrou cards em hand `GG-5885208311` no canal `#icm-pko`) apareceu como villain cat='sd' sem o Rui ter marcado a mão para estudo.
- **Severidade:** Funcional grave (data-pollution Vilões com mãos não marcadas).
- **Magnitude pré-fix pt7:** 22/22 cat='sd' = 100% falsos positivos (sample FASE 1 com 1175 hh_import + 50 hm3). Em BD pré-wipe pt7 eram 115 cat='sd' — provavelmente todos falsos positivos.
- **Fix aplicado** (commit `ce56d59`, 29-Abr pt7):
  - Removido bloco regra B (3 linhas)
  - Docstring actualizado (regras agora A∨C∨D, removido B)
  - Pré-condição `has_cards or has_vpip` (linha 60) preservada como safety net
  - Cleanup BD: `DELETE FROM hand_villains WHERE category='sd' AND hand sem tag nota` (defensivo) — 22 rows apagados
- **Pendente futuro:** tab "Mãos com SD" em `frontend/src/pages/Villains.jsx` deixada por agora — vai aparecer vazia. Será removida em Tech Debt #12 (re-arquitectura modal Vilões).

### #B7 — Discord bot ignora `last_sync_at` quando `last_message_id` é NULL

- **File:** `backend/app/discord_bot.py` (função `_sync_guild_history` ou `fetch_messages_for_channel`, a confirmar)
- **Vector:** Detectado pt7 ao popular `discord_sync_state` com cutoff `-1d` pós-wipe TOTAL. Bot ignora `last_sync_at` completamente quando `last_message_id` está NULL → varre TODA a história do canal (Março+). Volume idêntico pt6 com cutoff -3d (277 entries) confirma que cutoff temporal nunca foi respeitado em nenhum dos dois casos — os últimos 3d/1d apenas coincidiram com a janela onde havia mensagens novas.
- **Severidade:** Funcional (bloqueia controlo fino de cutoff em qualquer reset BD).
- **Magnitude observada pt7:** sync com cutoff -1d → 277 entries criadas → 156 placeholders Discord (apanhou Março, 19-26 Abril, 28-29 Abril). Esperado para -1d: ~50-100 entries (apenas 28-29 Abr). Erro factor: 3-5×.
- **Workaround temporário:** SQL DELETE selectivo de `hands.origin='discord'` pré-cutoff data desejada. Não é destrutivo (placeholders órfãos, sem `hand_villains` associadas).
- **Fix proposto:** quando `last_message_id` é NULL, em vez de fetch de toda a história, passar `after=<datetime do last_sync_at>` ao `discord.py.TextChannel.history()`. discord.py aceita ambos `before/after` como `Snowflake|datetime`.
- **Esforço:** ~30-60 min (ler código bot + identificar onde fetch é construído + 1 condicional).

### #B6 — Discord sync race overlap
- **File:** `discord_bot.py:189-192` (a confirmar exacto via leitura)
- **Vector:** `discord_message_id` UNIQUE com `ON CONFLICT DO NOTHING`. Se restart bot + auto-sync ligado simultâneo, 2 fetches paralelos podem fazer overlap em `after=last_message_id`. Conflict resolve dedup, mas se write-state-cursor lento, contagem reportada está errada.
- **Severidade:** Cosmético (count UI mostra menos do que real, dedup não falha).
- **Fix proposto:** advisory lock `pg_advisory_xact_lock` em `_sync_guild_history`. Ou simples: `DISCORD_AUTO_SYNC=False` (default actual — manter).
- **Esforço:** ~1h se decidirem.

### #B12 — Hands GG anonimizadas com cross-post Discord não recebem `discord_tags` populado

- **File provável:** `backend/app/routers/screenshot.py` (`_link_second_discord_entry_to_existing_hand:831`) ou path de ingestão de entries Discord órfãs (sem hand ligada).
- **Origem:** Achado lateral durante validação empírica do #18 (pt8, 30-Abr).
- **Vector:** Quando o Rui partilha a mesma mão em 2 canais Discord (cross-post), só **1/17 TMs** observados têm `discord_tags` populado na hand correspondente. As restantes 16 hands têm `discord_tags=[]` apesar de existirem 2 entries Discord em canais distintos. Padrão comum: estas 16 hands têm `match_method=null` (HH GG anonimizada sem match SS), enquanto a única que ficou correcta (hand 1115) tem `match_method=anchors_stack_elimination_v2`. Hipótese: `_link_second_discord_entry_to_existing_hand` só dispara quando a 1ª entry já tem hand ligada via enrich; em hands GG anon, a 1ª entry fica órfã e a 2ª também — `discord_tags` nunca recebe append.
- **Severidade:** 🟡 Funcional menor. Não corrompe dados; só impede UI de mostrar tags Discord em hands GG anonimizadas. Não toca em `hand_villains` (regra de negócio impede villains em hands sem `match_method`).
- **Magnitude pt8:** 16/17 TMs com cross-post Discord (94%) afectados.
- **Fix proposto:** investigar trigger de append `discord_tags` independente de existir match SS↔HH. Possível solução: ao ingerir entry Discord, tentar localizar hand pelo `hand_id` (TM number) e fazer append directo de `discord_tags` mesmo que não haja enrich.
- **Esforço:** ~1h investigação + ~30min fix se confirmado.

### #B13 — Contadores `last_sync` (N links/M canais/K match HH) medem entries criadas em vez de trabalho útil

- **File:** `backend/app/routers/discord.py` (CTE `new_entries` no fim de `sync_and_process`).
- **Origem:** Achado pt8 durante teste da feature nova de sincronização com janelas (commit `7ad41d4`).
- **Sintoma:** Utilizador faz sync de janela já totalmente importada e vê `n_links=0` mas a lista de mãos cresce de 23 para 150 (placeholders `GGDiscord` criados por `backfill_ggdiscord`, processamento Vision de entries antigas que faltavam imagem, matches feitos retroactivamente, etc.). Os contadores afirmam "esta janela trouxe X coisas novas", mas o pipeline `sync-and-process` faz muito mais do que ingerir mensagens novas — opera globalmente sobre entries pré-existentes.
- **Causa:** A query CTE filtra `entries WHERE source='discord' AND entry_type IN ('replayer_link','image') AND created_at >= sync_started_at`. Não captura: (a) processamento Vision de entries pré-existentes a `sync_started_at`, (b) placeholders criados em `hands` por `backfill_ggdiscord`, (c) matches SS↔HH feitos por `run_match_worker` (Bucket 1 attachments), (d) anexação de imagens órfãs.
- **Severidade:** 🟢 UX. Não corrompe dados. Mensagem na UI desalinhada com a realidade observada pelo utilizador.
- **Possíveis abordagens (a investigar pt9):**
  - **(a)** substituir contadores por "entries processadas + placeholders criados + matches feitos nesta sync" — instrumentar cada subtask para reportar contadores.
  - **(b)** acrescentar contadores adicionais sem remover os actuais — mantém compat com UI actual.
  - **(c)** deixar os contadores como estão e mudar texto da UI para "Mensagens novas: N · Canais: M · Match HH: K" — mais honesto sobre o que medem.
- **Bloqueado por:** nada. Investigação isolada.
- **Esforço:** ~1h.

### #B14 — Estudo aceita mãos sem tournament_name/buy_in/site

- **File:** `backend/app/routers/hands.py:359-363` (`STUDY_VIEW_GG_MATCH_FILTER`).
- **Origem:** Visão de produto pt9 (regra de negócio do Rui consolidada em `docs/VISAO_PRODUTO.md`).
- **Sintoma:** Mãos podem entrar em Estudo sem campos obrigatórios de identificação do torneio. Filtro actual só exige `match_method` populado; permite hands sem `tournament_name`, `buy_in` ou `site`.
- **Severidade:** 🟡 Funcional. Mostra mãos incompletas em Estudo, contraria regra de negócio.
- **Fix:** adicionar `AND h.tournament_name IS NOT NULL AND h.buy_in IS NOT NULL AND h.site IS NOT NULL` ao `STUDY_VIEW_GG_MATCH_FILTER` (e à variante `..._WITH_DISCORD_PLACEHOLDERS` quando aplicável).
- **Esforço:** ~30 min + validação contra BD prod.

### #B15 — Estudo aceita mãos só com tag "nota"

- **File:** `backend/app/routers/hands.py:359-363` (`STUDY_VIEW_GG_MATCH_FILTER`); ver também `..._WITH_DISCORD_PLACEHOLDERS` linhas 371-389.
- **Origem:** Visão de produto pt9 (regra de negócio do Rui consolidada em `docs/VISAO_PRODUTO.md`).
- **Sintoma:** Regra de negócio: mão só com tag `nota` (HM3 ou Discord) → só Vilões, não Estudo. Implementação actual cobre **parcialmente** o caso `discord_tags=['nota']` em placeholders Discord (`include_discord_placeholders=true`), mas falha:
  - (a) hands HM3 com `hm3_tags ⊆ {nota, notas, nota+, nota++}` exclusivamente.
  - (b) hands GG match-real com `discord_tags=['nota']` exclusivamente (não placeholders).
- **Severidade:** 🟡 Funcional. Polui Estudo com mãos destinadas a Vilões.
- **Fix:** estender o filtro principal para excluir hands cujo conjunto de tags de estudo (hm3_tags excluindo padrões `nota%` + discord_tags excluindo `nota`) seja vazio. Casos canónicos 2 e 5 (`docs/VISAO_PRODUTO.md`) servem de teste.
- **Esforço:** ~30-45 min + validação.

### #B16 — `_apply_channel_tags` filtra por entry_id (vector latente HH cross-post)

- **File:** `backend/app/discord_bot.py:244-257` (`_apply_channel_tags`).
- **Origem:** Identificado durante diagnóstico #B12 (pt9, 30-Abr).
- **Vector:** Quando uma HH text é cross-postada em 2 canais Discord, a 1ª entry processada cria as hands via `process_entry_to_hands` e `_apply_channel_tags` popula `discord_tags` com o canal A. A 2ª entry chega com a mesma HH; `process_entry_to_hands` faz `INSERT ... ON CONFLICT DO NOTHING` (não cria hands duplicadas); `_apply_channel_tags` filtra `WHERE entry_id = %s` (entry da 2ª) e não toca em nada — o canal B nunca é appendado.
- **Severidade:** 🟡 Funcional latente. Magnitude actual: 0 hands afectadas em prod (Rui não usa cross-post HH text — usa replayer_link, coberto por #B12 fix).
- **Fix proposto:** alterar `_apply_channel_tags` para também tocar hands cujo `hand_id` derive da mesma HH parseada da entry, mesmo quando `entry_id` ≠ entry actual. Em alternativa, chamar `append_discord_channel_to_hand` (helper #B12) para cada hand_id afectado.
- **Esforço:** ~45 min + validação contra cenário simulado.
- **Bloqueado por:** nada. Tem prioridade baixa enquanto magnitude=0.

### #B17 — Estudo separa tags por origem em vez de unificar (DIVERGÊNCIA 5)

- **File provável:** `frontend/src/pages/Hands.jsx` (vista "Por Tags") + `backend/app/routers/hands.py` (endpoint tag-groups).
- **Origem:** Visão de produto pt9 (DIVERGÊNCIA 5 documentada em `docs/REGRAS_NEGOCIO.md` §3.2.2).
- **Sintoma:** Estudo apresenta a mesma chip de tag em 3 secções separadas: PRINCIPAIS/SECUNDÁRIAS/SPOTS (HM3 only), CANAIS DISCORD (Discord with HH), DISCORD — SÓ SS (Discord without HH). Rui pediu há ~1 mês para unificar; não está implementado.
- **Severidade:** 🔴 Funcional alto. Viola pedido explícito antigo do Rui. Estudo torna-se redundante e confuso. Inclui caso especialmente grave: secção "DISCORD — SÓ SS" mostra 119 mãos sem HH, violando regra dura 3.2.1.
- **Fix proposto:**
  - Backend: query tag-groups deve agregar hm3_tags + discord_tags por NOME (ex: "ICM PKO" + "icm-pko" → mesma chave normalizada).
  - Frontend: remover secções "CANAIS DISCORD" e "DISCORD — SÓ SS (SEM HH)". Apresentar 1 chip por nome unificado. Cada mão mostra origem como rótulo discreto.
  - Aplicar regra dura: mãos sem HH NUNCA em Estudo.
- **Esforço:** ~3-4h (backend agregação + frontend redesign + validação).
- **Bloqueado por:** nada. Pode atacar em pt10 ou continuação pt9.

### #B18 — Lista de mãos em torneio (drill-down): falta badge de origem por mão

- **File provável:** `frontend/src/components/HandRow.jsx` ou caller no drill-down de torneio (`frontend/src/pages/Tournaments.jsx`, `frontend/src/pages/Hands.jsx::TournamentGroup`).
- **Origem:** Coerência com #B17 (pt9).
- **Sintoma:** No drill-down de torneio, lista de mãos mostra: nome do torneio, buy-in, data, número do torneio, stack inicial (quando disponível), número de mãos. Falta badge de origem por mão (HM3 / Discord / SS-only) — incoerente com a vista Estudo pós-#B17 que adicionou `OriginBadge` via prop `extraEnd`.
- **Severidade:** 🟢 UX.
- **Fix proposto:** passar `extraEnd={<OriginBadge ...>}` no `HandRow` dentro do `TournamentGroup` quando aplicável; ou tornar `HandRow` capaz de calcular o badge a partir das próprias `hand.hm3_tags` / `hand.discord_tags` quando uma prop `showOrigin=true` for passada.
- **Esforço:** ~30-45 min.
- **Bloqueado por:** nada.

---

## §3a. UX bugs detectados em validação pt7 (Bloco B Fase 1)

| ID | Bug | File (provável) | Severidade | Esforço | Notas |
|---|---|---|---|---|---|
| **#UX1** | Modal villain "MÃOS EM COMUM" mostra cards do Hero em vez do villain | `frontend/src/pages/Villains.jsx` ou `components/HandHistoryViewer.jsx` | 🟡 Cosmético-Funcional (pode confundir interpretação) | ~30 min frontend | Detectado 29-Abr pt7 quando Rui validou Pipeline 1 cutoff 1d. Comportamento esperado: se villain mostrou cards no showdown → cards villain; senão → "—" ou "Foldou". Decisão Rui: anotar + seguir; ataque sessão futura junto com #11/#12 (UX block). |

---

## §3. Bugs em parsers detectados (auditoria estática Agent A)

Relevância variável; alguns são edge cases raros, outros podem afectar produção. **Magnitude não medida** — precisava audit empírico cruzando com BD.

| ID | Bug | File:Line | Severidade | Esforço |
|---|---|---|---|---|
| **#P1** | Nicks com parênteses truncados ("Karluz (ex)") | `gg_hands.py:385`, `hm3.py:386, 407` | Funcional | 15 min |
| **#P2** | Stacks fraccionários EUR/US ambiguidade silenciosa | `winamax.py:49`, `gg_hands.py:388` | Cosmético→Funcional se moedas mistas | 30 min audit |
| **#P3** | Heads-up + 3-max position logic não testada | `gg_hands.py:33-64`, `hm3.py:89-126` | Funcional (raro) | 30 min + tests |
| **#P4** | Antes/straddle não extraído (silently 0) | `gg_hands.py:474`, `hm3.py:632-641` | Funcional grave (result em BB divergente quando hero folda preflop) | 30 min |
| **#P5** | "mucks hand" não capturado como showdown | `gg_hands.py:300` | Cosmético (cards None expected) | 15 min |
| **#P6** | Hero sitting out — posição calculada com seats activos errados | `gg_hands.py:384-404` (sem filtro vs `hm3.py:435-456` que filtra) | Funcional | 45 min unify |
| **#P7** | Side pots multi-way all-in: lógica presume HU | `gg_hands.py:439-446`, `hm3.py:547-567` | Funcional grave em torneios PKO multi-way | 1h |
| **#P8** | Idempotência parser GG anon_map (Padrão 2 dependente seat order) | `gg_hands.py:141-243` | Mitigado por #20 mas Padrão 2 ainda existe quando Hero é único nick real | 30 min |

---

## §4. Workarounds e dívida técnica (não-bugs)

| Item | Tipo | Esforço | Notas |
|---|---|---|---|
| Backfill 110 mãos absorvidas Discord (filtro entry_id) | Limpeza | ~1-2h | Pós-wipe pt5/pt6 estado actual já limpo — re-aplicar só se necessário |
| Pesquisa MTT 10 dígitos → modal directo | Feature | 30 min | Opção A aprovada 24-Abr |
| Página Discord: 2 listas + botão "Forçar Match" individual | Feature | 3-4h | Spec fixa |
| Gyazo pipeline Case 1/2 (±2min canal + WPN lobby 1min) | Feature | 4-5h | Vision integration |
| Centralizar trigger Fase IV em hand_service.py (refactor) | Refactor | 2h | Padrão duplicado em 3 routers |
| Endpoint legacy `/api/villains` (housekeeping) | Cleanup | 30 min | Bloqueado por #12 |
| Consolidação 8-9 PokerCard locais no partilhado | Refactor | 4-5h | Componente partilhado já existe (29-Abr); risco moderado |
| `_upload_screenshot_to_storage` stub /tmp ephemeral | Tech Debt | 1h | Mitigado por `/api/screenshots/image/{entry_id}` |
| Sessão B UI (`position_parse_failed` badge + edição manual) | Feature | 2-3h | Spec conhecida |
| Logos salas como banner esbatido | Feature | 2-3h | Mockup validado |
| Persistência viewMode Estudo (localStorage) | Feature | 5 min | Default 'tags' actual sem persistência |
| Validação SQL hand 253 (Upstakes_io villain sd) pós-Pipelines 2-5 | Validação | 15 min | Estado actual provável já limpo |

<!--
Nota histórica (#B31 limpeza pt13): §5-§10 (plano sequencial pré-pt8,
dependências, esforços, riscos, decisões, notas para próxima sessão)
foram apagadas porque referiam tech debts já fechados (#22, #18, #15,
#B7, #12, #13c, #B12, etc.) e não eram mais accionáveis. Conteúdo
preservado em git history. Único item ainda válido (#11 blacklist
persistida vs re-criar) movido inline para a entry de #11 no backlog
"Tech Debts abertos pós-pt10" acima.
-->

