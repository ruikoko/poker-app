# Anatomia operacional do HRC

**Estado:** rascunho v6, 22 Maio 2026 (pt35).
**Origem:** consolidação dos factos espalhados pelos journals + observações
directas do Rui durante pt28 + smoke tests pt29 + cadeia da 2ª run pt30-pt34
+ Fase 1 GTO Brain pt35 (Complete Export).
**Responsável de manter actualizado:** quem descobrir um facto novo edita
este ficheiro antes de fechar o trabalho. Sem isto, o conhecimento perde-se.

**Histórico de versões:**
- v1 (pt28 manhã): rascunho inicial — filosofia + 11 secções + 14 lacunas.
- v2 (pt28 tarde): popup Nash detalhado (6 campos descobertos via screenshot)
  + clipboard bug pyperclip 1.11.0 documentado + apps competidoras mapeadas.
- v3 (pt28 fim do dia): **§12 nova "Formato de HH aceite pelo HRC"** — o
  HRC parser identifica formato por prefixo do header; descoberta empírica
  de que GG-format com bounty injectado nas seats é rejeitado, e de que a
  conversão para PokerStars-format funciona (validada manualmente no HRC
  com a mão GG-5944816316). §3.1 e §10 actualizadas com nota sobre o
  auto-import do clipboard pelo HRC quando o wizard abre.
- v4 (pt29 madrugada): **três factos novos sobre interacção com o HRC**,
  descobertos na cascata de bugs do robot pt29-v1 → v2 → v3.
  (a) §3.5 — o HRC (Java) **perde eventos de click instantâneo** no botão
  Finish: `mouse-down + mouse-up` em <50 ms não actua sobre o botão.
  É necessário um "slow-click" (down → sleep ≥100 ms → up) para o evento
  ser registado. Activate da janela pré-click é necessário mas não chega
  sem o slow-click.
  (b) §7 — o HRC **não emite sinal explícito de "calculation done"**.
  O único indicador inferível é a estabilização do uso de memória:
  enquanto calcula, a memória oscila com alocações; quando termina,
  estabiliza. Heurística usável: memória `>100 MB` e variação `<20 MB`
  durante 3 ciclos de 10 s implica run terminada.
  (c) §3.4 — comportamento de Hand Mode "Max Players" descoberto:
  controla quantos jogadores podem estar em pots simultaneamente no
  Monte Carlo. Mesas 8-handed deep PKO requerem **Max 6** (pots 5-way são
  possíveis); Max 4 trunca o cálculo. Foi a causa de discrepâncias de
  tree size entre PC principal (Max 4) e Beelink (Max 6) que se atribuíam
  ao script.
- v5 (pt30-pt34 madrugada, 22 Maio): **fecho da cadeia da 2ª run
  (Selected Subtree)** — toda a interacção da 2ª run validada ponta-a-ponta
  no Beelink. Factos novos:
  (a) **§1/§6/§9 — o HRC usa SWT, não Swing.** Os widgets são expostos como
  child windows nativas ao Win32 (descoberto pt30 no botão Finish,
  confirmado pt33 no popup Nash). Permite `BM_CLICK`, `IsWindowEnabled`,
  `GetWindowText`. É a base de toda a sessão pt30-pt34.
  (b) **§6 — anatomia do popup "Nash Calculation" como dialog `#32770`**:
  6 `SWT_Window0` (containers internos, sem widgets expostos para o
  dropdown de scope e campo CI) + 2 `Button` nativos expostos (OK, Cancel).
  Implicação: scope/CI continuam a depender de coord; OK/Cancel via BM_CLICK.
  (c) **§6.1 nova — janelas de progresso**: a 1ª run mostra janela top-level
  "Hand Setup"; a 2ª run mostra "H-\<hand_id\>: Monte Carlo Sampling".
  Detecção do fim de run via aparecer/desaparecer dessa janela (sinal
  binário) — **substitui a heurística de memória** do `wait_for_calculation`
  (§7.1), que dava falso positivo.
  (d) **§4/§5 — sequência manual da 2ª run** (Selected Subtree) documentada.
  (e) **§3.5/§6 — atalhos de teclado** (`&Finish` Alt+F, `Alt+R` Play) +
  limitação: **não funcionam dentro do popup Nash**.
  (f) **§9 — erros conhecidos não-bloqueantes** consolidados, incluindo o
  cursor anomaly pós-Save-As.
- v6 (pt35, 22 Maio): **§8 — export via Complete Export.** A
  `export_strategies` patched (SWAP em `patched_funcs.py`) muda o combo do
  diálogo Export Strategies de "Manual Selection" → "Complete Export" (Win32
  `CB_SETCURSEL` idx 0→1 + `CBN_SELCHANGE` + read-back), OK por `BM_CLICK`,
  Save As via `_save_as_set_and_click` portado. Armadilha
  `#DOC-MAKE-PATCHED-EXPORT-OVERRIDES-SWAP`: o launcher Baltazar sobrescrevia
  o SWAP pós-`exec` via `make_patched_export` — resolvido bootando o
  trampoline directo no `wrapper.py`. Smoke real `GG-5944816316` = 44 MB
  (era 1 nó). Fecha `#GTO-WATCHER-EXPORT-DEFAULT-DEPTH-2`.

---

## Função deste documento

Tornar o conhecimento operacional sobre o HRC um bem comum do projecto,
em vez de viver só na cabeça do Rui. Quando o Rui se encontrar a explicar
pela enésima vez o mesmo facto, é sintoma de que esse facto faltava aqui.
Quando o documento estiver completo, o Code e o Web podem trabalhar sobre
o HRC sem voltar a pedir-lhe o que ele já sabe.

## Filosofia

1. **Só factos observáveis.** Comportamentos visíveis ao olho ou medíveis
   com ferramentas standard. Não opiniões, não interpretações, não código
   nosso.

2. **Verdade sobre o HRC, não sobre o nosso software.** As coordenadas
   no nosso código são **medições** que pertencem aqui. A forma como o
   nosso robot reage é decisão nossa e vive em
   `tools/watcher_src/patched_funcs.py`.

3. **Baltazar é a base.** O robot original do Baltazar funcionava bem em
   uso single-hand. Bugs descobertos depois de nós alterarmos o robot
   foram introduzidos por nós.

4. **Cada facto com data e contexto.** Quando foi observado pela última
   vez, em que máquina, com que resolução.

5. **Tradução de jargão.** Termos técnicos traduzidos na primeira
   ocorrência (ex: "Strategy Table — a tabela das estratégias"). Audiência
   primária: Web + Code. Rui lê em bónus.

---

## 1. Identificação do HRC

| Item | Valor |
|---|---|
| Nome oficial | Holdem Resources Calculator (HRC) |
| Autor | Baltazar Studios |
| Estado | Descontinuado pelo autor (sem actualizações desde 2024-ish) |
| Versão instalada no Beelink | **LACUNA — Rui confirma número exacto** |
| Instalador moderno | `C:\Users\<user>\AppData\Local\Programs\HoldemResources\HRC\hrc.exe` |
| Instalador legacy "Beta" | `C:\Users\Administrator\AppData\Local\HoldemResources\HRC Beta\hrc.exe` |
| Configuração no Beelink actual | Junction `HRC Beta → HRC` em `Administrator\AppData\Local\HoldemResources\` (resolve mismatch do path interno do robot) |
| API | Nenhuma. Controlável apenas via simulação de cliques e teclas (pyautogui) **+ Win32 nas janelas/botões nativos (ver toolkit)** |
| Toolkit da UI (descoberto pt30/pt33) | **SWT** (Standard Widget Toolkit), **não Swing**. Crucial: os widgets (botões do wizard, botões do popup Nash) são expostos como **child windows nativas** ao Win32. Permite enumerá-los (`EnumChildWindows`), ler classe/texto (`GetClassNameW`/`GetWindowTextW`), saber se estão activos (`IsWindowEnabled`) e clicá-los sem coord nem foco (`SendMessageW` + `BM_CLICK`). Toda a cadeia da 2ª run (pt30-pt34) assenta nisto |
| Scripting interno | JavaScript via Nashorn — usado para configurar sizings e prune actions |

## 2. Janela e foco do HRC main

| Item | Valor |
|---|---|
| Tamanho típico observado no Beelink (não-maximizada) | `width=1050, height=850` |
| Posição típica observada no Beelink | `left=283, top=65` |
| Maximização | **LACUNA — confirmar: o HRC é arrancado maximizado ou em janela?** |
| Persistência de estado entre sessões | A última mão carregada **fica visível** no wizard quando o HRC reabre. A caixa do hand history não fica vazia |
| Sobrescrita | Quando se cola uma mão nova por cima de uma anterior (via `Ctrl+V` ou botão "Paste from Clipboard"), o conteúdo é **substituído**. Mão antiga não atrapalha |
| Borracha (botão de limpar) | Existe um botão na página Basic Hand Data que apaga todo o conteúdo. Usado **opcionalmente** quando o utilizador quer começar do zero. Não é necessário antes de colar mão nova — o paste sobrescreve sozinho |

## 3. Wizard de criação de mão ("Tournament Setup")

O wizard tem páginas em sequência. Cada página tem um botão "Next" para
avançar. A última página termina com "Finish".

### 3.1 Página Basic Hand Data (paste do HH)

| Item | Valor |
|---|---|
| Função | Colar o hand history (HH) da mão a calcular |
| Botão dedicado | "Paste from Clipboard" (lê do clipboard do Windows) |
| Sequência manual (utilizador a fazer à mão) | Apenas `Ctrl+V`. Sobrescreve qualquer conteúdo anterior |
| Borracha (opcional) | Clicar na borracha para limpar a caixa, e depois `Ctrl+V`. **Não é necessário** mas existe |
| Erro conhecido | `"No valid hand-history found in the Clipboard"` — aparece quando o clipboard está vazio ou contém conteúdo não reconhecido como HH |
| **Auto-import do clipboard** | **No momento em que o wizard "New Hand" abre, o HRC lê o clipboard imediatamente e tenta auto-importar. Se o conteúdo for lixo (qualquer texto que não seja HH válido), o popup azul "No valid hand-history" aparece logo, antes do robot ter chance de fazer Ctrl+V** |
| Implicação | O robot tem de pôr o HH no clipboard ANTES de abrir o wizard. Implementado em pt28-v3 (`_set_clipboard_with_verify` em `patched_funcs.py`) |
| Formatos de HH aceites | Ver §12. O HRC só aceita HHs em formatos específicos por sala (PokerStars, Winamax, GG, ...) — qualquer modificação ao formato canónico pode causar rejeição silenciosa |
| Bug histórico do nosso software | Bug I (pt25e, provisório, sem repro consistente) — robot clicava num botão errado neste painel |

### 3.2 Página Equity Model

| Item | Valor |
|---|---|
| Função | Escolher o modelo de equity |
| Posição da caixa (rel à wpos) | `(446, 561)` |
| Método de selecção | Typeahead — escrever as primeiras letras do nome do modelo |
| Typeahead "ma" | Selecciona "Malmuth-Harville ICM" |
| Typeahead "mu" | Selecciona "Multi Table ICM" |
| Typeahead "fg" | Selecciona "FGS" (fora do scope actual) |
| 4º modelo | **LACUNA — qual é o quarto modelo no dropdown?** |

### 3.3 Página MTT Stacks (condicional)

| Item | Valor |
|---|---|
| Quando aparece | Sempre que o equity model é "Multi Table ICM" |
| Campo "Remaining Players" | Coord absoluta `(977, 330)` no Beelink. Click-rel actual no source: `(1230, 289)` |
| Campo "Total Chips" | Coord rel `(677, 438)`. Sequência: click → Ctrl+A → typewrite |
| Campo "Other Tables" | **LACUNA — qual é a coord? Default = 0** |
| Implicação de Other Tables = 0 | Matematicamente equivalente a FT ICM com N jogadores. Cálculo enviesado se o torneio tem mais jogadores em outras mesas |
| Workaround actual | Se `meta.json.stage='MTT'` + `players_left` presentes, preenche Remaining Players. Senão, salta a página clicando "Next" (deixa Other Tables = 0) |

### 3.4 Página Scripting

| Item | Valor |
|---|---|
| Função | Carregar o script JavaScript que define sizings preflop e regras postflop (force checkdown, donk bets, all-in SPR, etc) |
| Tab "Scripting" | Coord `SCRIPTING_TAB` (**LACUNA — valor literal está no .pyc Baltazar**) |
| Campo Script Folder | Coord `SCRIPT_FOLDER` (**LACUNA — idem**) |
| Sequência | Click no Script Folder → paste do path absoluto do `.js` |
| Script per-mão | O backend gera um `.js` específico para cada mão (Trabalho A pt25f; **regra universal pt42**). Path absoluto vai em `payouts.json.script_path` |

#### 3.4.1 Template canónico (pt42)

`backend/app/services/hrc_scripts/mtt_advanced_canonical_2026.js`. Único — não há
variantes legacy. Os arrays `SIZES_*` são overridden per-mão pelo gerador
(`backend/app/services/hrc_script_gen.py`). Variáveis que a mão não toca ficam com os
defaults do template.

**Variáveis preflop (BB):** `SIZES_OPEN_OTHERS / BU / SB / BB`,
`SIZES_3BET_IP / BB_VS_SB / BB_VS_OTHER / SB_VS_BB / SB_VS_OTHER`,
`SIZES_3BET_SQUEEZE_IP / SB / BB`.
**Variáveis preflop (pot-fraction):** `SIZES_POT_4BET_IP / OOP`,
`SIZES_POT_5BET_IP / OOP` (conversão BB→fração vive no gerador
`_array_for_4bet5bet_in_pot_fraction`, preservando a forma do template; a JS function
`getSizings4Bets / 5Bets` aplica `ctx.sizingPot(s)`).

**Cortar turn/river (pt42, "pré-flop + flop only"):** `POSTFLOP_FORCE_CHECKDOWN_AFTER =
{2:FLOP, 3:FLOP, ..., 9:FLOP}`. `hasNextStreetBetting(ctx)` devolve `street <
POSTFLOP_FORCE_CHECKDOWN_AFTER[live]` → só PREFLOP tem next street com betting. Turn/river
ficam sem betting modelado (só check). Reduz tree size significativamente.

#### 3.4.2 Regra universal de sizings (pt42)

Substitui as duas regras anteriores (Trabalho A pt25f + tabela de multiplicadores 3-bet
pt25f-extensão). Para cada raise voluntário preflop (open / 3-bet clássico / squeeze /
4-bet / 5-bet), o gerador escreve um array com a forma:

- **1ª opção** = `to_amount_bb` da HH (ou `"ALLIN"` se a acção foi all-in via heurística
  95% — `to_amount_chips >= seat_initial × 0.95`, threshold `_ALL_IN_EFFECTIVE_THRESHOLD`
  partilhado com `hrc_node_offset.py`).
- **2ª opção:**
  - Original NÃO ALLIN + `effective_stack_at_action_bb <= 25` → `"ALLIN"`.
  - Original NÃO ALLIN + eff > 25 (ou None) → sem 2ª opção.
  - Original ALLIN + non-all-in default existe → o default por tipo (ver tabela abaixo).
  - Original ALLIN + default None → sem 2ª opção (`["ALLIN"]` só).

| Tipo | Non-all-in default | Condição |
|---|---|---|
| Open | 2 BB | `eff > 8 BB` E posição ≠ SB ≠ BB (HU `"BU/SB"` passa) |
| 3-bet clássico | 2.3 × `opener_to_bb` | `eff < 26` |
| 3-bet clássico | 2.7 × `opener_to_bb` | `26 ≤ eff < 35` |
| 3-bet clássico | 3.0 × `opener_to_bb` | `eff ≥ 35` |
| Squeeze | 3.0 × `opener_to_bb` | (sempre que `opener_to_bb` conhecido) |
| 4-bet | 2.3 × `previous_raise_to_bb` | (sempre) |
| 5-bet | 2.2 × `previous_raise_to_bb` | (sempre) |

#### 3.4.2.1 3-bet IP por posição (pt42b — re-abertura)

A regra do §3.4.2 para 3-bet clássico aplica-se à **posição que efectivamente
3-betou na HH**. Para as **outras posições candidatas IP** (entre opener+1 e
BU inclusive, excluindo SB/BB), o gerador também gera arrays — em variáveis
separadas `SIZES_3BET_<POSITION>` no template — com sizing baseado na **eff
spot-específica** entre cada candidato e o opener:

- **eff spot** = `min(opener_remaining, candidate_remaining) / BB` no
  snapshot pós-open.
- Multiplicador por bucket (mesmas constantes da tabela acima):
  2.3×opener / 2.7×opener / 3.0×opener.
- ALLIN como 2ª opção se eff spot ≤ 25 BB.

**Variáveis no template canónico:** `SIZES_3BET_EP / MP / HJ / CO / BU`.
EP1/EP2 (9-handed) partilham `SIZES_3BET_EP`. Fallback `SIZES_3BET_IP` mantido
para defensivo (posição não esperada).

**CASO A vs CASO B:**

- **CASO A** (posição fez 3-bet na HH): regra universal pt42 aplicada com eff
  spot (não eff dinâmica do parser). Sizing original como 1ª opção.
- **CASO B** (posição NÃO fez 3-bet — gera sempre): só o bucket default,
  sem sizing original (não houve).

Ordem do gerador: **CASO B** preenche todos os candidatos primeiro; **CASO A**
sobrescreve a entrada da posição que 3-betou.

**SB/BB intocados** (continuam em `SIZES_3BET_SB_VS_*` /
`SIZES_3BET_BB_VS_*`); squeeze intocado (continua em `SIZES_3BET_SQUEEZE_*`).

**Dispatch no template** (JS): `getSizings3Bets` chama
`getSizings3BetByPositionIP(ctx, player)` no branch IP — switch por
`positionLabelForIdx(player, n)` que consome `POSITION_LABELS_BY_N` (mirror
de `_POSITION_LABELS_BY_N` em `queue_export.py`).

#### 3.4.3 Efectiva dinâmica por acção (pt42)

`effective_stack_at_action_bb = min(raiser_remaining, max(active_opponents_remaining)) / BB`,
**recalculada por raise**. Substitui a `compute_effective_stack_bb` global (que ficou só
para retrocompat). É a referência única para: gate `eff > 8` do open default; buckets
3-bet 0-25/26-35/35+; threshold `eff <= 25` do ALLIN-como-2ª-opção.

Active players = set actualizado nos `folds` (parser walker); raiser_remaining e opp_remaining
lêem `initial_stacks[nick] - contributions[nick]` ANTES do raise actual.

#### 3.4.4 Campos novos do parser (pt42)

`_parse_preflop_actions` em `hrc_script_gen.py` passa a expor por acção:

| Campo | Significado |
|---|---|
| `previous_raise_to_bb` | `to_amount_bb` do raise imediatamente anterior na sequência. `None` para opens (não há anterior preflop). |
| `opener_to_bb` | `to_amount_bb` do open original (1º raise voluntário). `None` para o próprio open (auto-ref). |
| `is_all_in` | True sse `to_amount_chips >= seat_initial × 0.95`. Threshold inclusivo. |
| `effective_stack_at_action_bb` | min(raiser_remaining, max_opp_active_remaining) / BB. |

Os campos legacy (`bet_count`, `to_amount_bb`, `pot_fraction`, `callers_before`,
`opener_idx`, `previous_raiser_idx`, etc.) mantêm-se.

### 3.5 Página Finish

| Item | Valor |
|---|---|
| Botão | "Finish" (coord `BTN_FINISH = (568, 640)` relativa à wpos do wizard, validada empíricamente em pt29-v1/v2 no Beelink) |
| Após click bem sucedido | HRC fecha o wizard ("Hand Setup" desaparece do títulos de janelas) e abre a mesa preparada |
| Tempo de carregamento | ~30 segundos para o HRC estabilizar a mesa antes de poder iniciar cálculos |
| **Tipo de click exigido (descoberto pt29)** | **Slow-click obrigatório.** `pyautogui.click()` instantâneo (mouse-down + mouse-up em <50 ms) é frequentemente perdido pelo Java do HRC e o wizard persiste como se nada se tivesse passado. Solução validada: `mouseDown(button='left')` → `time.sleep(0.15)` → `mouseUp(button='left')` |
| **Activate pré-click (descoberto pt29)** | Necessário fazer `w.activate()` da janela "Hand Setup" antes do click (move o foco do SO para esta janela). Confirmado por log `foreground=hwnd=... title='Hand Setup'` no momento do click. **Activate sozinho não chega** sem o slow-click; ambos são necessários em conjunto. |
| **State check pós-click recomendado** | Após o click, verificar se a janela "Hand Setup" deixou de existir nos títulos de janelas do SO. Se ainda existe, o click falhou — log WARN e degradar conforme política do robot. Sem este state check, o robot prossegue cego com setup parado. |

### 3.5.1 Wizard recapitulado — Tree Statistics (página Betting Setup, pós-Scripting)

A última página do wizard antes do Finish é "Betting Setup → Scripting"
e mostra automaticamente, no fundo, um painel "Tree Statistics and
Abstractions":

| Campo | Significado |
|---|---|
| Total Nodes | Número total de nós da árvore que será construída |
| Total Tree Size | Memória estimada para a árvore inteira |
| HRC available | `X / Y` onde Y é a RAM máxima reservável (cap interno do HRC, observado 20.4 GB) e X é o quanto está livre no momento |
| Flop / Turn / River | Buckets de abstracção em cada street (defaults da config UI: 1024 / 256 / 256) |

Se `Total Tree Size > HRC available`, o Finish corre mas o cálculo
crasha logo a seguir por falta de memória. Validar tree size antes do
Finish é boa prática.

### 3.6 Outras páginas observadas no wizard

#### 3.6.1 Hand Mode (Max Players)

| Item | Valor |
|---|---|
| Função | Define quantos jogadores podem estar simultaneamente activos num pot durante o Monte Carlo |
| Observado no log do robot | `Hand Mode: Max Players = 6` |
| Valores típicos vistos | 4, 5, 6 |
| **Impacto descoberto em pt29** | **Mesas 8-handed deep PKO podem produzir pots 5-way.** Com Max 4 o cálculo trunca cenários relevantes; com Max 6 considera-os. Pode causar discrepâncias grandes de tree size entre PC principal e Beelink se os defaults forem diferentes. |
| Default no Beelink (config UI exportada pelo Rui) | Max 6 |
| Recomendação | Para PKO 8-max alinhar em **Max 6** em todas as máquinas de cálculo |

#### 3.6.2 Bounty Mode

| Item | Valor |
|---|---|
| Função | Define a percentagem do prize pool atribuída a bounties em PKO |
| Detecção automática pelo robot | "KO detetado — a selecionar Bounty Mode PKO 50%..." (heurística no source) |
| Valor habitual | "PKO 50%" |
| Ratios mapeados pelo backend | PKO 0.75 (Monster), PKO 0.50 (Bounty Hunters / Bounty Builder / Knockout), PKO 0.40 (Super KO), KO 0.33 (Mystery KO), None 0.0 (Vanilla). Estes são os valores que entram no `payouts.json` — **não confundir** com as opções do dropdown do HRC (lacuna em aberto). |
| Outros | **LACUNA — listar opções do dropdown do HRC** (Vanilla, PKO 25%, PKO 50%, Mystery KO, ...). Fechar só com print do Rui (dropdown do HRC aberto). |
| Observação | Em GG a percentagem real depende do `tournament_format` parsed do TS e **chega ao HRC via `payouts.json` data-driven** (`LOBBY_RATIO_LOOKUP` em `backend/app/services/lobby_vision.py`, 5 ratios conhecidos — ver linha acima). O que está hardcoded em 50% é o **dropdown do watcher** (`select_bounty_mode` legacy Baltazar OG), não o `progressiveFactor`. Validação parcial: só PKO 50% confirmado empiricamente (pt34 v1, caso degenerado). Estado e detalhe em `#HRC-BOUNTY-HARDCODED-50PCT` (TECH_DEBTS) |

## 4. Painel principal da mesa (pós-Finish)

| Item | Valor |
|---|---|
| Botão verde "Calculate" (play) | Coord rel **`(204, 64)`** — **origem = janela principal do HRC via `find_hrc()`** (`hrc.left + 204`, `hrc.top + 64`), NÃO a wpos do wizard |
| Atalho de teclado do Calculate | **`Alt+R`** (tooltip oficial confirmado pelo Rui). Só funciona com foco no painel principal das estratégias — **não** dentro do popup Nash |
| Função do Calculate | Abre o popup "Nash Calculation" |

> **Correcção pt32 (importante).** A coord do Play tinha dois erros que
> custaram dois smokes:
> - **pt32 v1:** o Y estava em `59` (herdado de pt26); a 1ª run do Baltazar
>   OG usa `64` e funciona. Corrigido para `64`.
> - **pt32 v2:** a **origem** estava errada. `_click_calculate_button` usava
>   a `wpos` do wizard "Hand Setup" — que já tinha **fechado** no Finish da
>   1ª run. O log provou-o: `coord=(1174,64)` com `wpos=(970,0,...)` →
>   1174 = 970 + 204, click em zona vazia, popup Nash nunca abria
>   (`#START-CALC-SELECTED-SUBTREE-NO-POPUP-OPEN`). A 1ª run usa `find_hrc()`
>   como origem; a 2ª passou a usar a mesma. Offsets são relativos a
>   `hrc.left` / `hrc.top`.

### 4.1 Sequência manual da 2ª run (Selected Subtree)

A 2ª run refina o cálculo na subtree do spot real da mão. Sequência que o
Rui faz à mão (e que o robot replica em
`start_calculation_selected_subtree`):

1. A 1ª run acaba; o HRC mostra os resultados com a **1ª linha da Strategy
   Table seleccionada** (UTG por defeito).
2. Seleccionar o **1º jogador com VPIP no pote** (a linha do agressor real;
   o robot navega lá com seta-baixo × `target_node_offset`).
3. Clicar o botão **Play** no topo do HRC (abre o popup "Nash Calculation").
4. No popup: pôr **Scope = "Selected Subtree"** e **CI = 10.0**.
5. **OK** → a 2ª run arranca.

> Os passos 3-5 são exactamente onde a cadeia pt32-pt34 vivia: pt32 fez o
> Play (passo 3) pegar; pt33 fez o OK (passo 5) pegar via BM_CLICK; pt34 fez
> a espera do fim da 2ª run usar o título certo. O passo 4 (Scope + CI)
> continua a depender de coord (ver §6).

## 5. Strategy Table (a tabela das estratégias, visível após cada corrida)

| Item | Valor |
|---|---|
| Quando aparece | Após uma corrida (run) terminar — fica a coluna do lado esquerdo do HRC |
| Foco do teclado por defeito | Já na própria Strategy Table — setas funcionam directamente sem precisar de click prévio |
| Linha seleccionada por defeito | Sempre a 1ª (UTG, primeira acção preflop) |
| Resposta às setas | Instantânea, sem necessidade de timing generoso entre presses |
| Comportamento no fim das linhas | Para. Não cicla |
| Coluna "Player" — labels canónicos | UTG / MP / HJ / CO / BU / SB / BB (usa "BU" não "BTN"). Para N=7+, aparece "MP" entre UTG e HJ |
| Estrutura típica observada (4-handed: CO/BU/SB/BB) | 7 linhas — 2 por posição não-blind (CO/BU = 4 linhas) + 3 para SB (Call/Complete + small raise + all-in) |
| Estrutura típica observada (5-handed: UTG/HJ/BU/SB/BB) | 9 linhas — 2 por não-blind (UTG/HJ/BU = 6 linhas) + 3 para SB |
| Convenção de índices em scripting | UTG = 0 (first-to-act), SB = N-2, BB = N-1 (segundo docs HRC oficiais) |

### Ordem dos nós e navegação (validado pt30-pt34)

Validado empiricamente pelo Rui na mão `GG-5944816316`:

- **Ordem das linhas, de cima para baixo:** `UTG → EP/MP/HJ → CO → BU → SB`
  — por ordem de actuação preflop. **A BB nunca aparece** como linha-base
  (é o defensor; não tem decisão de abertura própria na árvore).
- Cada posição ocupa **1 ou 2 linhas** conforme haja override de sizes
  (uma linha por sizing distinto).
- **Navegação automática:** `navigate_to_target_node(wpos, offset)` preme
  seta-baixo `N` vezes, com `N` pré-calculado pelo backend
  (`compute_target_node_offset`) e injectado em `meta.json.target_node_offset`.
  O cursor parte da 1ª linha (UTG) por defeito após a 1ª run; a seta-baixo
  move 1 linha e **não cicla** no fim.

### Atalhos de teclado da Strategy Table

| Atalho | Acção |
|---|---|
| `Ctrl+D` | Prune Action (na linha actual) |
| `Ctrl+Shift+D` | Prune Children |
| `Ctrl+Shift+A` | Add Action |
| `Alt+L` | Lock/Unlock Range |
| `Ctrl+C` / `Ctrl+Shift+C` | Copy Range / Strategy |
| `Ctrl+V` / `Ctrl+Shift+V` | Paste Range / Strategy |

## 6. Popup "Nash Calculation"

| Item | Valor |
|---|---|
| Quando abre | Ao clicar no botão verde Calculate do main UI |
| Tipo | Dialog modal **separado** do main HRC window (tem rect próprio) |
| Título exacto | `"Nash Calculation"` (case-insensitive para match) |
| Tempo até abrir após click | Tipicamente imediato (poucos segundos) |
| Rect observado 19 Maio | `left=590, top=337, width=436, height=230` |
| Rect observado 18 Maio | `width=416, height=214` |
| **Estabilidade do rect** | **Variável entre sessões** (~5% em width, ~7.5% em height entre 18 e 19 Maio). Não usar fracções; usar pixels rel ao top-left do popup |
| Estrutura do popup | 6 campos em layout vertical + 2 botões (OK, Cancel) em baixo |

### Anatomia Win32 do popup (descoberto pt33)

Snapshot via `EnumChildWindows`
(`_local_only/diag/check_nash_popup_children.py`):

| Elemento | Valor |
|---|---|
| Tipo de janela | Dialog **`#32770`** top-level (classe padrão de dialog Win32) |
| Containers internos | **6 × `SWT_Window0`** — onde vivem o dropdown de scope, o campo CI, os outros campos. **Não expõem widgets Win32 individuais** |
| Botões nativos expostos | **2 × `Button`**: `OK` e `Cancel` |

**Implicação prática (e por isso a 2ª run mistura duas técnicas):**
- O **dropdown Scope** e o **campo CI Target** estão dentro dos
  `SWT_Window0` e **não** têm hwnd próprio acessível → continuam a depender
  de **coordenadas** (pixels-rel ao top-left do popup).
- Os botões **OK / Cancel** são `Button` nativos → podem ser clicados por
  **`BM_CLICK`** (sem coord, sem foco). Foi o fix do pt33: o `Enter` não
  era registado pelo popup, mas o `BM_CLICK` no hwnd do OK é determinístico
  (análogo ao Save btn do export).

### Campos do popup, pela ordem visual (de cima para baixo)

| Posição | Campo | Tipo | Valor por defeito | O robot toca? |
|---|---|---|---|---|
| 1 | CFR Algorithm | dropdown | "HRC 4.0 (Default)" | Não — fica no default |
| 2 | Scope | dropdown | "Full Tree" | **Sim** — quer mudar para "Selected Subtree" na 2ª corrida |
| 3 | Run Sampling | dropdown | "Until CI value is reached" | Não — fica no default |
| 4 | CI Target | campo de texto | 10.0 (ou anterior) | **Sim** — escreve o CI da mão (lido do meta.json) |
| 5 | Reset Regret | checkbox | desligado | Não |
| 6 | Reset Strategies | checkbox | desligado | Não |
| — | OK | botão | — | **Sim** — confirma e fecha o popup |
| — | Cancel | botão | — | Não |

### Widgets do popup (coords pixels-rel ao top-left do popup)

| Widget | Coord rel actual | Origem | Estado |
|---|---|---|---|
| Dropdown "Scope" | `(278, 67)` | smoke 18 Maio pt25f | Suspeita de desfasamento (~12 pixels em Y baseado em estimativa visual de imagem pt28) |
| Opção "Selected Subtree" (lista flutuante do dropdown aberto) | `(274, 108)` | smoke 18 Maio pt25f | Idem |
| Campo "CI Target" | `(270, 109)` | derivado das fracções legacy do Baltazar (0.65×416, 0.51×214) | A funcionar — o robot escreve 10.0 OK |
| Botão OK | **não precisa de coord** | pt33 v1 | `Button` nativo → **`BM_CLICK` no hwnd** (`_find_ok_button` + `SendMessageW`). Coord deixou de ser necessária |
| Botão Cancel | **não precisa de coord** | pt33 (por analogia) | `Button` nativo exposto; clicável por BM_CLICK se algum dia for preciso |

### Dropdown Scope — comportamento

| Item | Valor |
|---|---|
| Opções disponíveis | 2: "Full Tree" (topo, default) e "Selected Subtree" (baixo) |
| Sequência para mudar para Selected Subtree | (a) click no dropdown (Y=67) para abrir; (b) click na opção "Selected Subtree" (Y=108) na lista flutuante |
| Comportamento se não se mudar | A corrida que arranca é Full Tree (igual à 1ª, inútil para refinamento) |
| Ordem natural do utilizador | "Indiferente" segundo o Rui, mas visualmente Scope aparece em cima e CI em baixo |

### Atalhos de teclado dentro do popup Nash

| Item | Valor |
|---|---|
| Atalhos funcionam? | **Não.** Confirmação visual do Rui: `Tab`/`Enter` e os atalhos do painel principal (`Alt+R`, etc.) **não actuam dentro do popup Nash**. Foi a causa do pt33 (o OK por `Enter` não pegava) |
| Implicação | OK/Cancel **têm** de ir por BM_CLICK (botões nativos); o dropdown Scope e o CI por coord. Não há caminho de teclado fiável dentro do popup |

### Cadeia da 2ª corrida — resolvida em pt32-pt34

A 2ª corrida (popup Nash → Selected Subtree) ficou funcional na sessão
pt30-pt34. Sequência de fixes (detalhe em
`docs/JOURNAL_2026-05-22-pt30-pt34.md`):

| Sintoma original | Fix | Onde |
|---|---|---|
| Popup Nash **não abria** (`#START-CALC-SELECTED-SUBTREE-NO-POPUP-OPEN`) | Play da 2ª run usava `wpos` do wizard já fechado; coord Y 59→64 + origem `wpos`→`find_hrc()` | pt32 v1 + v2 |
| Popup abria mas **OK não pegava** (`#START-CALC-SELECTED-SUBTREE-OK-CLICK-FAILS`) | `Enter` não funciona no popup → BM_CLICK no hwnd do Button OK | pt33 v1 |
| 2ª run disparava mas o robot **não esperava o fim** | janela de progresso da 2ª run é "Monte Carlo Sampling", não "Hand Setup" → match por substring | pt34 v1 |

> Reordenação Scope→CI→OK (pt28-v1) e logging defensivo já estavam em vigor;
> o que faltava era abrir o popup (pt32), confirmá-lo (pt33) e esperar a run
> (pt34). O Scope é mudado antes do CI para o caso de o popup re-renderizar.

## 7. Corridas (runs)

| Item | Valor |
|---|---|
| 1ª corrida | Tipicamente Scope = Full Tree |
| 2ª corrida | Tipicamente Scope = Selected Subtree, focada na linha do agressor real |
| CI Target — significado | "Confidence Interval" — quanto mais baixo, mais refinado, mais demorado |
| CI = 5 | Muito refinado, ~7.2h para 1ª run completa |
| CI = 10 | Menos refinado, ~76 minutos para 1ª run completa |
| Defaults do nosso software | 1ª e 2ª runs: CI = 10 (era 5/10 split antes de pt27, alinhado em pt27 fix Bloco B) |
| Dialog "Save As" entre runs | Aparece automaticamente entre fim da 1ª corrida e início da 2ª (workflow do Baltazar). O launcher faz `BM_CLICK + wait save as` para fechar este fluxo de export. Importante: este Save As mexe no clipboard como efeito secundário (ver §10) |

### 7.1 Mecânica de início e fim — factos descobertos em pt29

| Item | Valor |
|---|---|
| **Dispatch da run (início)** | O click no botão verde "Calculate" abre o popup Nash; carregar OK no popup **dispara** o cálculo. O HRC retorna o controlo ao processo controlador (robot ou utilizador) imediatamente após o disparo — não bloqueia. |
| **Sinal explícito de fim** | **Não existe.** O HRC não emite mensagem, popup, mudança de título de janela, nem qualquer outro sinal directo que indique "calculation done". |
| **Único indicador inferível** | **Uso de memória do processo HRC.** Durante o cálculo a memória oscila com alocações constantes. Quando o cálculo termina, estabiliza. |
| **Heurística usável (Baltazar OG, `wait_for_calculation()`)** | `mem > 100 MB` e variação `< 20 MB` durante 3 ciclos de 10 s consecutivos implica run terminada. Sleep inicial de 15 s antes de começar a verificar. Timeout global 300 s. |
| **Implicação para qualquer software que controle o HRC** | Após disparar uma run, **bloquear até a memória estabilizar** antes de tentar qualquer acção dependente do resultado (navegação para Selected Subtree, Save As, Export, leitura de Strategy Table). |
| **Pontos do fluxo onde aplicar a espera** | (a) Após 1ª run e antes de navegar para a 2ª. (b) Após 2ª run e antes do export. (c) Em qualquer outro ponto futuro em que uma acção HRC assíncrona seja seguida por outra dependente do resultado. |
| **Modos de falha da heurística** | (i) Memória pode estabilizar transitoriamente cedo demais (improvável mas possível em árvores muito pequenas). (ii) Memória pode continuar a oscilar por GC interno mesmo após o cálculo terminar (improvável). Em qualquer dos casos, afinar os thresholds com dados reais. |

> **Substituída em pt31.** A heurística de memória deu **falso positivo**
> no smoke pt30 (declarou o fim da 1ª run aos 48s — = 15s sleep + 3×10s —
> com a run ainda a correr). Foi trocada pelo polling da **janela de
> progresso** (§7.2), que é um sinal **binário** (existe / não existe), sem
> thresholds. `wait_for_calculation()` continua no namespace mas já não é
> chamada.

### 7.2 Janelas de progresso (descoberto pt31/pt34) — sinal binário de fim

Enquanto uma run corre, o HRC mostra uma janela top-level **de progresso**,
visualmente distinta do wizard e mutuamente exclusiva no tempo. **Aparece
quando a run arranca e desaparece quando termina** — sinal binário fiável.

| Run | Título da janela de progresso | Detecção |
|---|---|---|
| **1ª run** | `"Hand Setup"` (exacto) | `FindWindowW(None, "Hand Setup")` |
| **2ª run** (Selected Subtree) | `"H-<hand_id>: Monte Carlo Sampling"` | `EnumWindows` + **substring** "Monte Carlo Sampling" (case-insensitive) |

> **Armadilha (pt34).** A 1ª e a 2ª run **não** têm o mesmo título. A 1ª
> reutiliza "Hand Setup" (o mesmo nome do wizard de configuração — daí ser
> obrigatório só pollar isto **depois** de o wizard fechar no Finish). A 2ª
> run mostra "Monte Carlo Sampling". Procurar "Hand Setup" exacto na 2ª run
> dava timeout 30s e o robot avançava para o Save As com a 2ª run ainda a
> correr. Helper `_find_progress_window_title(match_substring)` cobre os
> dois casos.

Implementação: `_wait_for_run_completion(...)` — fase 1 aguarda a janela
aparecer (run arrancou; WARN graceful se não — run trivial/erro); fase 2
polla até desaparecer (run terminou; log minuto-a-minuto; raise no
timeout). Timeouts: 2h (1ª run), 8h (2ª run).

## 8. Export do resultado

| Item | Valor |
|---|---|
| Mecanismo | **(pt35)** A `export_strategies` é a do nosso `patched_funcs.py` (SWAP): muda o combo do diálogo Export Strategies de "Manual Selection" para **"Complete Export"** (Win32 `CB_SETCURSEL` idx 0→1 + `CBN_SELCHANGE` + read-back), clica OK por `BM_CLICK`, e trata o Save As via `_save_as_set_and_click` (clipboard + `BM_CLICK` no botão Save). **Até pt34** corria a versão do launcher (`make_patched_export`, modo "Manual Selection" = 1 nó) — ver armadilha abaixo. |
| Output | Ficheiro `.zip` (Complete Export ≈ 40-70 MB; smoke real pt35 `GG-5944816316` = 44 MB) |
| Path no Beelink | `C:\Users\Administrator\Documents\Teste completo\done\Exports\<hand_id>.zip` |
| Save As | `_save_as_set_and_click` (port pt35 do launcher): espera o file-picker, cola o path por clipboard (fallback typewrite), clica Save via `BM_CLICK` (fallback Enter) |

> **Armadilha (pt35, `#DOC-MAKE-PATCHED-EXPORT-OVERRIDES-SWAP`).** O launcher
> Baltazar (`hrc_watcher_apr19_launcher.pyc`) faz, no seu `main()`,
> `g['export_strategies'] = make_patched_export(g)` **depois** do `exec` do
> trampoline. Logo, **um SWAP de `export_strategies` em `patched_funcs.py` NÃO
> aterra em produção** — é sobrescrito pela versão do launcher (modo "Manual
> Selection" = 1 nó). Resolvido em pt35 fazendo o `wrapper.py` bootar o
> trampoline **sem** chamar `make_patched_export`, tornando canónica a nossa
> `export_strategies`. **Antes de assumir que um SWAP aterra, confirmar que o
> launcher não monkey-patcha a função pós-`exec`.**

## 9. Bugs e limitações observáveis (não nossos)

| Bug | Severidade | Workaround actual |
|---|---|---|
| Rect do popup Nash variável entre sessões | Média (afecta calibração de coordenadas) | Usar pixels-rel ao top-left do popup, nunca fracções absolutas |
| Tree pode chegar a >20 GB de RAM e crashar | Alta (mãos profundas + scripts largos) | Templates JS tight + prune via Selected Subtree |
| Caixa do HH no wizard fica com a última mão entre sessões | Baixa | Não interfere — paste sobrescreve sempre |
| Dialog "Save As" aparece entre runs | Baixa (fluxo previsto) | Launcher Baltazar tem patch para fechar |
| **HRC Java perde clicks instantâneos em botões críticos** (pt29) | **Alta** (afecta o Finish do wizard e potencialmente outros botões críticos) | Slow-click obrigatório: `mouseDown → sleep ≥100 ms → mouseUp`. Validado em pt29-v2 no Finish. Em **botões nativos SWT** (OK do popup, ver abaixo) a alternativa é BM_CLICK |
| **Ausência de sinal explícito de fim de cálculo** (pt29/pt31) | Alta (qualquer automação tem de inferir) | ~~Polling do uso de memória~~ (heurística, falso positivo pt30) → **polling da janela de progresso** (§7.2): sinal binário aparece/desaparece |
| **Toolkit SWT expõe widgets ao Win32** (pt30/pt33) | — (é uma **vantagem**, não um bug) | Botões nativos (Finish, OK/Cancel do popup) são enumeráveis e clicáveis por `BM_CLICK`; estado por `IsWindowEnabled`; janelas de progresso detectáveis por título. Ver §1, §6, §7.2 |

### 9.1 Erros conhecidos no flow do robot (não-bloqueantes)

Aparecem no log do robot mas **não impedem** o cálculo. Registados para o
próximo Claude não os confundir com falhas reais:

| Linha no log | O que é | Estado |
|---|---|---|
| `[WARN] verify_wizard_finished: janela "Hand Setup" ainda presente apos click + activate` | Falso positivo do state-check pós-Finish (pt29-v1) — verifica **cedo demais**, mas a 1ª run efectivamente arranca | `#WIZARD-FINISH-FALSE-POSITIVE-STATE-CHECK` (aberto) |
| `[WARN] CI Target initial: coords não calibrados (pt25e Bloco 2 pendente)` | O set do CI no main UI antes da 1ª run nunca foi calibrado (coords=0) → degrada para Enter, que funciona | `#CI-TARGET-INITIAL-NOT-CALIBRATED` (aberto) |
| `[WARN] Nash dialog não encontrado — a usar Enter` | Fallback do CI Target da **1ª run** (Baltazar OG); funciona | Aceite (legacy) |
| **Cursor anomaly após Save As** | Observação visual do Rui: após o Save As o cursor fica na **2ª linha (EP)** da Strategy Table. Origem desconhecida; não bloqueia | `#CURSOR-ANOMALY-POST-SAVE-AS` (novo, aberto) |

## 10. Clipboard — comportamento e armadilhas

O clipboard do Windows é um recurso **partilhado** entre todas as apps.
Várias coisas o usam, e ele tem armadilhas conhecidas que afectam o nosso
robot.

### Auto-import do clipboard pelo HRC

Descoberta em pt28: quando o wizard "New Hand" abre, o HRC **lê
automaticamente o clipboard imediatamente** e tenta importá-lo como HH.
Se o conteúdo for inválido, o popup azul "No valid hand-history" aparece
logo — antes de o robot ter chance de fazer Ctrl+V manualmente.

Implicação operacional: o robot tem de **garantir que o HH está no
clipboard ANTES de abrir o wizard**. A ordem das operações é:

1. `_set_clipboard_with_verify(hh_text)` — escreve HH e verifica com read-back.
2. Abrir wizard "New Hand" (atalho ou click).
3. HRC faz auto-import do clipboard → vê o HH válido → preenche campos.
4. `paste_hh` (Ctrl+V manual) corre como rede de segurança.

Antes do pt28, a ordem estava invertida (`open_wizard` → `paste_hh`), o
que causava falha sistemática se qualquer outra app tinha tocado no
clipboard nos segundos antes do robot abrir o wizard (ex: comando do
PowerShell que o utilizador colou para arrancar o robot ficava no
clipboard e o HRC tentava parseá-lo).

### Onde o robot escreve no clipboard

| Origem | Para quê | Quando |
|---|---|---|
| `paste_hh` (Baltazar OG) | Hand history → caixa do wizard | No setup_hand, antes do Ctrl+V |
| `paste_path` (Baltazar OG) | Paths de prizes/scripts | Em `import_prizes` e `setup_scripting` |
| `start_calculation` (Baltazar OG) | Valor do CI Target no popup Nash da 1ª corrida | Por cada corrida |
| `_save_as_set_and_click` (launcher) | Caminho do ficheiro `.zip` do export | No fim de cada mão |
| `_set_filename_via_win32` fallback (launcher) | Caminho do ficheiro (fallback) | Só se a via principal falhar |
| `clipboard_safe_paste` (nosso patch, pt27-v3) | Wrapper defensivo para os pastes do source | Substitui paste_hh, paste_path, _fill_ci_target_in_popup, _set_ci_target_common |

### Bug do `pyperclip 1.11.0` descoberto em pt28

`pyperclip.copy()` pode **falhar em silêncio** no Windows por causa de um
bug em `CheckedCall.__call__` (linha 314-318 de `pyperclip/__init__.py`):

```python
def __call__(self, *args):
    ret = self.f(*args)
    if not ret and get_errno():           # ← AND, devia ser OR e ler GetLastError
        raise PyperclipWindowsException(...)
    return ret
```

`get_errno()` lê o CRT errno, que não é actualizado por chamadas user32
do Windows. As falhas Win32 (do tipo `CreateWindowExA → NULL`) passam por
este guarda sem excepção. O `pyperclip.copy()` retorna normalmente como
se tivesse colado, mas o clipboard fica no estado anterior (ou esvaziado).

Quando isto acontece, o `Ctrl+V` seguinte cola o que estava no clipboard
antes (caminho do `.zip` da mão anterior, ou outro conteúdo), e o HRC
mostra "No valid hand-history found in the Clipboard".

### Porque o Baltazar OG nunca teve este problema

O bug do `pyperclip` está em ambos os builds (Baltazar OG e nosso, mesma
versão). A diferença está no contexto:

- **Baltazar OG**: o Rui usava manualmente, 1 mão de cada vez (abrir HRC,
  correr, fechar). Beelink "limpo", sem HM3 / Discord / RDP / Win+V
  cloud sync activos durante a corrida.
- **Nosso build**: corre em batch via adapter, mãos encadeadas. Beelink
  hoje tem stack completo do Rui — HM3, Discord, OneDrive, possíveis
  clipboard managers, etc. Mais competição pelo clipboard ownership.

A causa raiz do sintoma é uma combinação de:
1. Bug do `pyperclip` que esconde falhas Win32.
2. Várias apps competirem pelo clipboard (qualquer uma pode chamar
   `SetClipboardData` logo a seguir ao nosso e sobrescrever).
3. O nosso uso em batch expõe a flakiness com mais frequência.

### Defesa actual (pt27-v3)

`clipboard_safe_paste` faz: `pyperclip.copy(text)` → ler clipboard de
volta para verificar → retry com pausa entre tentativas (até 5×) → só
manda `Ctrl+V` quando confirma que o clipboard tem o conteúdo certo →
verifica novamente depois (regista warning se foi sobrescrito).

Cobre tanto o cenário interno (bug pyperclip) como o externo (apps
concorrentes). Não é fix da causa raiz, mas evita o sintoma.

### Apps tipicamente competidoras pelo clipboard

| Categoria | Suspeitos prováveis |
|---|---|
| Sync entre máquinas | Win+V cloud sync (Windows 11 default com MS account), RDP clipboard channel, Mouse Without Borders / Synergy / Barrier |
| Poker tools | HM3 (monitora clipboard para auto-import de HHs — suspeito principal), SharkScope HUD, Intuitive Tables |
| Comunicação | Discord (preview de paste de imagens), Slack |
| Clipboard managers | Ditto, ClipboardFusion, ClipX |
| Microsoft built-in | Snipping Tool, OneDrive Personal, Windows Search |
| Extensões browser | LastPass / Bitwarden auto-clear, Grammarly |

## 11. Tabela única de coordenadas calibradas

| Coordenada | Valor | Tipo | Origem | Notas |
|---|---|---|---|---|
| `EQUITY_MODEL_X/Y` | `(446, 561)` | rel à wpos | herdada do Baltazar | OK |
| `CALCULATE_BUTTON_X/Y` | `(204, 64)` | rel à **janela principal HRC (`find_hrc()`)**, NÃO à wpos | pt32 v1 (Y 59→64) + pt32 v2 (origem `find_hrc()`) | **Corrigido em pt32.** Era `(204,59)` rel à wpos do wizard (já fechado) → click em zona vazia |
| `SCOPE_DROPDOWN_REL_X/Y` | `(278, 67)` | rel ao top-left do popup Nash | smoke 18 Maio pt25f | A funcionar na 2ª run (pt32 v2+) |
| `SCOPE_OPTION_SELECTED_SUBTREE_REL_X/Y` | `(274, 108)` | rel ao top-left do popup Nash | smoke 18 Maio pt25f | A funcionar (pt32 v2+) |
| `CI_TARGET_POPUP_REL_X/Y` | `(270, 109)` | rel ao top-left do popup Nash | derivado das fracções legacy do Baltazar | Funciona (escreve "10.0" correctamente) |
| `STRATEGY_TABLE_FOCUS_X/Y` | (não calibrada) | rel à wpos | DEPRECATED em pt28 — Strategy Table já tem foco por default |
| `CI_TARGET_FIELD_X/Y` (main UI) | (não calibrada) | rel à wpos | DEPRECATED em pt25e — set CI no main UI é desnecessário |
| Campo "Remaining Players" (MTT Stacks) | `(977, 330)` abs / `(1230, 289)` rel | smoke 15 Maio pt25e/manhã | Coord abs assume wpos `(283, 65)` |
| Campo "Total Chips" (MTT Stacks) | `(677, 438)` rel à wpos | herdada do Baltazar | OK |
| Campo "Other Tables" (MTT Stacks) | **LACUNA** | — | precisa calibração |
| `SCRIPTING_TAB` | **LACUNA — está no .pyc Baltazar** | rel à wpos | — | Code pode descobrir do source decompilado |
| `SCRIPT_FOLDER` | **LACUNA — idem** | rel à wpos | — | Idem |
| `BTN_NEXT` | **LACUNA — idem** | rel à wpos | — | Idem |
| `BTN_FINISH` | `(568, 640)` | rel à wpos do wizard | observada empiricamente em pt29-v1/v2 nos smokes do Beelink | Funciona com slow-click obrigatório (ver §3.5). wpos do wizard observada `(943, 0, 741, 673)` |
| `OK button no popup Nash` | **não usa coord** | — (hwnd via Win32) | pt33 v1 | Resolvido. `Button` nativo SWT → `BM_CLICK` no hwnd (`_find_ok_button` + `SendMessageW`). Ver §6 |

**Nota sobre o Beelink:** A wpos do main HRC é `(left=283, top=65,
width=1050, height=850)` em janela não-maximizada. Coords absolutas
assumem esta configuração; mudanças invalidam coords absolutas. Coords
rel sobrevivem desde que o tamanho não mude.

---

## 12. Formato de HH aceite pelo HRC

Descoberto empiricamente em pt28 (20 Maio 2026) através de testes A/B no
HRC do Beelink e PC principal, com a mão GG-5944816316. A descoberta veio
em sequência ao bug "paste falha em silêncio": depois de garantirmos que
o clipboard tinha o HH correcto, o HRC continuou a rejeitar — porque a
HH em si tinha problemas de formato.

### 12.1 Como o HRC identifica o formato

O HRC parser examina o **prefixo da primeira linha** (header da mão)
para escolher qual parser usar. Cada parser tem regras próprias sobre o
que aceita no resto do documento.

Lista de sites suportados (do popup azul de erro):

> *Clipboard import works on tournament hands from: PokerStars, Fulltilt,
> PartyPoker, iPoker, Ongame, Cake, Merge, 888, Winamax, Bovada, Winning,
> PKR, GG, CoinPoker, Web Calculator URLs*

Mapping observado de prefixo → parser:

| Prefixo da 1ª linha | Parser activado | Aceita bounty na seat? |
|---|---|---|
| `PokerStars Hand #...` | PokerStars | **Sim** |
| `Winamax Poker - ...` | Winamax | **Sim** (formato próprio) |
| `Poker Hand #TM...` ou `Poker Hand #...` | GGPoker | **Não** |
| Outros | Não testados | — |

### 12.2 Formato GG aceite (HH original, sem bounty nas seats)

Header:

```
Poker Hand #TM<id>: Tournament #<id>, <name> - Level<N>(<sb>/<bb>(<ante>)) - <data>
```

Seats (SEM bounty info):

```
Seat N: <nick> (<chips_com_virgulas> in chips)
```

Observado: HHs originais do GGPoker (anonymized ou com nicks reais) são
aceites. A info de bounty teria de ser configurada via UI nos campos
`KO-T$` e `KO-P$` da página Basic Hand Data — mas o parser GG **rejeita**
qualquer tentativa de embutir bounty na linha Seat.

### 12.3 Formato PokerStars aceite (com bounty na seat)

Exemplo real do Rui (PokerStars `.eu`):

```
PokerStars Hand #260525949543: Tournament #3983883160, €57+€57+€11 EUR Hold'em No Limit - Level XX (4000/8000) - 2026/04/19 23:30:19 WET [2026/04/19 18:30:19 ET]
Table '3983883160 52' 6-max Seat #6 is the button
Seat 1: kokonakueka (457949 in chips, €171 bounty)
...
```

Convenções observadas:
- Espaço entre `Level` e o número (`Level XX`).
- Blinds entre parêntesis com `/` (`(4000/8000)`), sem ante explícito,
  sem vírgulas como separador de milhares.
- Chips na linha Seat **sem vírgulas**.
- Bounty na linha Seat com símbolo da moeda **antes** do valor
  (`€171 bounty`), sem decimais quando inteiro.
- **Hero também tem bounty** na linha Seat — não basta os outros terem.

### 12.4 Formato Winamax aceite (com bounty noutro layout)

Exemplo real do Rui:

```
Winamax Poker - Tournament "HIGHROLLER" buyIn: 232€ + 18€ level: 8 - HandId: #4714884320089604100-138-1779137598 - Holdem no limit (80/350/700) - 2026/05/18 20:53:18 UTC
Table: 'HIGHROLLER(1097769551)#003' 6-max (real money) Seat #3 is the button
Seat 1: thinvalium (92265, 107€ bounty)
...
```

Convenções diferentes do PokerStars:
- Sem `Hand #` literal — usa `HandId: #...` no meio do header.
- Sem `in chips` na linha Seat.
- Bounty com símbolo da moeda **depois** do valor (`107€` em vez de
  `€107`).
- Hero também tem bounty (`thinvalium` é Hero Winamax do Rui).

### 12.5 Rejeição confirmada empiricamente (testes pt28)

Variantes testadas com a mão GG-5944816316 no HRC. Resultado:

| # | Variante | HRC |
|---|---|---|
| 1 | HH GG original (anonymized, sem bounty) | **Aceita** |
| 2 | HH GG + nicks resolvidos (anonymized → reais), sem bounty | **Aceita** |
| 3 | HH GG + apenas bounty `$X.XX` nas seats (mantém vírgulas chips) | **Rejeita** |
| 4 | HH GG + bounty `$X` (sem vírgulas chips, formato PS-like) | **Rejeita** |
| 5 | HH GG + bounty `$X` em todas as seats incluindo Hero | **Rejeita** |
| 6 | HH GG + bounty `€X` em todas as seats | **Rejeita** |
| 7 | HH GG com header `PokerStars Hand #` + bounty `€X` | **Rejeita** |
| 8 | HH GG completamente convertida para formato PokerStars (todas as 11 transformações em §12.6) | **Aceita** |

Conclusão: o parser GG do HRC **não aceita bounty na linha Seat em
nenhuma variante**. Para passar bounty info via HH é obrigatório
**transformar a HH inteira em formato PokerStars** (ou Winamax).

### 12.6 Transformações necessárias GG → PokerStars

Para converter uma HH GG em formato PokerStars que o HRC engula, todas
estas transformações são necessárias (validadas empiricamente):

| # | Transformação | Origem (GG) | Destino (PS) |
|---|---|---|---|
| 1 | Prefixo do header | `Poker Hand #TM<id>` | `PokerStars Hand #<id>` |
| 2 | Level no header | `Level14(1,750/3,500(500))` | `Level 14 (1750/3500)` |
| 3 | Chips nas seats | `(63,483 in chips)` | `(63483 in chips, €250 bounty)` |
| 4 | Hero seat | `Seat 6: Hero (76,360 in chips)` | `Seat 6: Hero (76360 in chips, €250 bounty)` |
| 5 | Símbolo da moeda do bounty | `$` (USD) | `€` (rejeitou `$`) |
| 6 | Decimais no bounty | `$250.00` | `€250` (sem `.00` quando inteiro) |
| 7 | `Dealt to <other>` sem cartas | Presente para todos | Remover excepto Hero |
| 8 | `*** SHOWDOWN ***` em mão sem showdown | Presente | Remover |
| 9 | `<player>: doesn't show hand` depois de `collected` | Ausente | Adicionar |
| 10 | Total pot | `Total pot X \| Rake 0 \| Jackpot 0 \| Bingo 0 \| Fortune 0 \| Tax 0` | `Total pot X \| Rake 0` |
| 11 | Vírgulas em amounts (raises, bets, collected, blinds) | Presentes | Remover todas |

Implementação no backend: `convert_gg_hh_to_pokerstars_compatible` em
`backend/app/services/queue_export.py`. Estado em 20 Maio:
- Commit 078bf93 fez Fase 1 (remover bounty na seat, manter `_replace_hashes`
  e `_format_level_line`).
- Commit subsequente fará Fase 2 (adicionar transformações #7-#11 + re-adicionar
  bounty injection no formato PS).

### 12.7 Scope da conversão (importante)

A conversão GG → PokerStars **só pode ser aplicada na escrita do `hh.txt`
para a pasta da queue do HRC** (`Teste completo\GG-XXXX\hh.txt`). NÃO
pode tocar em:

- HHs de outras salas (PokerStars, Winamax, WPN) — já vêm em formato
  compatível, não precisam de conversão.
- Outros consumers da HH GG no backend: Estudo, Vilões, HM3, Discord
  page, hand_villains. Esses precisam da HH GG **canónica** (anonymized
  ou com nicks resolvidos) sem PS-isation.
- A HH armazenada na base de dados continua canónica. A conversão é
  uma camada de escrita final só para o output HRC.

### 12.8 Tech debt residual (inputs auxiliares incompletos)

Para o HRC calcular PKO equity correctamente precisa de **três** fontes
de informação, das quais hoje só uma chega completa:

**#HRC-GG-KOS-EXTRACTION — bounty por jogador**

Bounties variam ao longo do torneio: cada KO acumula bounty no jogador
que abate. Para uma mão num momento específico, o bounty correcto não é
o **inicial** ($250 base) — é o **acumulado** até esse ponto. Para
implementar isto seria preciso:

- Fonte: tournament_summaries + sequência de KOs antes da mão actual.
- Cálculo: bounty_inicial × (1 + Σ(0.5 × bounty_abatido_kn) / bounty_inicial).

Para a entrega pt28, usar bounty inicial como aproximação. O cálculo PKO
equity do HRC será ligeiramente off mas funcional.

**#HRC-PAYOUTS-INCOMPLETO — prize structure truncada**

O `payouts.json` actual termina no 10º lugar:
```json
"prizes": { "1": 42034.3, ..., "10": 5123.73 }
```

Em torneios com centenas de jogadores restantes (a GG-5944816316 tem 365),
o prize pool paga muito além de top 10. O lobby da própria mão mostra
**180 places paid** com a structure completa visível no painel "Prize
Pool" do screenshot do lobby (extraído em FASE A via Discord):

- Lugares 1-10: individuais (cada um com prémio próprio).
- Lugares agrupados em ranges: 11~12, 13~16, 17~22, 23~32, 33~48,
  49~73, 74~114, 115~180 (todos com o mesmo prémio dentro do range).

O Vision parser hoje captura os 10 individuais correctamente mas não
captura os ranges. Tech debt: estender o parser para apanhar os ranges
e expandir cada um em entries individuais no `payouts.json` (ex:
`"11~12: $3,880.46"` → `"11": 3880.46, "12": 3880.46`). Resultado: 180
entries no `prizes`.

**#HRC-TOTAL-CHIPS-MISSING — total_chips ausente**

Campo `chips: null` no `payouts.json` é o **total de fichas em jogo**
no torneio inteiro. O HRC usa-o para calcular o chip average (`total_chips
/ players_left`), que entra no cálculo ICM como referência para a
distribuição assumida de stacks nos jogadores das outras mesas (Other
Tables na página MTT Stacks).

A info está no **canto superior direito do lobby do torneio** no GGPoker:
- `Players Left: 365 / 1552` — jogadores actuais / cap inicial.
- `Average Stack: 179,530 (51.3 BB)` — chip average.

Cálculo: `total_chips = Average Stack × Players Left` (ex: 179,530 × 365 =
65,528,450 para a mão GG-5944816316).

Sem `total_chips`, o HRC ou usa um default interno (sem garantia de
correcção) ou pede ao utilizador para preencher manualmente. O cálculo
sai aproximado. Tech debt: Vision parser captura `Average Stack` e
`Players Left` do canto superior direito do lobby, multiplica, e
escreve no `payouts.json.chips`.

### 12.9 Lacunas sobre formato (a confirmar empiricamente no futuro)

| # | Lacuna |
|---|---|
| A | Símbolo da moeda para sites USD `.com` — `$` é rejeitado no bounty, mas a conversão para `€` parece incorrecta semanticamente. Investigar se o HRC aceita `$X bounty` em algum formato (ex: PokerStars `.com` em vez de `.eu`). |
| B | Header PokerStars completo — o nosso `PokerStars Hand #5944816316` passou, mas o PS real tem `WET [data ET]` no fim. Pode causar rejeição em casos mais finos. |
| C | Formato Winamax — não testado se o HRC engole HH GG convertida para formato Winamax (alternativa ao PS). |
| D | `*** ANTE/BLINDS ***` no Winamax separa essa fase do resto. PS não tem. Confirmar qual é exigido em cada formato. |

### 12.10 Pipeline WN bounty (pt42c) — conversão Winamax → PS-compat

Implementado em pt42c após descoberta no smoke pt42b de que **1232 mãos
PKO Winamax** chegavam ao HRC sem bounty (`payouts.json.bountyType="None"`,
sem injecção na HH).

**Trigger:** site=`Winamax` AND tournament_format ∈ `WINAMAX_BOUNTY_FORMATS`
(`"pko"`, `"super ko"`, `"ko"`; Mystery KO continua excluído via
`MYSTERY_FORMATS`).

**Transformações (subset das 11 do GG — só as necessárias para WN):**

| # | Transformação | Origem (WN) | Destino (PS-compat) |
|---|---|---|---|
| 1 | Chips nas seats | `(75308, 10€ bounty)` | `(75308 in chips, €10 bounty)` |
| 2 | Currency position | `10€` (depois do valor) | `€10` (antes do valor) |
| 3 | `in chips` literal | Ausente | Adicionado |
| 4 | Hero bounty value | `(<X>€ bounty)` literal | `max(Vision, HH)` (regra pt41) |

**Header WN + markers (`*** ANTE/BLINDS ***`, `*** PRE-FLOP ***`) NÃO são
convertidos** — pipeline minimal por decisão Web/Rui. Smoke real Beelink
em pt42d validará se HRC aceita o formato WN-converted; se rejeitar
(rejeita header não-PS, por exemplo), escalar para conversão completa.

**`payouts.json` no zip** ganha `_patch_winamax_payouts_bountytype`:
`bountyType="None"` → `"PKO"`, `progressiveFactor=0.0` → `0.5`. A BD
(`tournament_payouts.payouts_json`) **não é mutada** — o blob continua a
reflectir o que o lobby vision escreveu (audit trail).

**Audit Hero bounty no manifest:** `hero_bounty_source="hh"` (novo enum)
distingue WN pipeline pt42c de GG pipeline pt41 (`"ts"` ou `"vision"`).

**Source de truth para o audit:** HH crua (`hand.raw`), não o hh_text
convertido (que já não tem o regex `(<X>€ bounty)` original).

**Implementação:** `backend/app/services/queue_export.py` —
`convert_gg_hh_to_pokerstars_compatible` ganha branch WN PKO;
`build_queue_zip` orquestra patch + audit.

---

## Anexo A: Convenção de índices HRC scripting

Confirmado nos docs oficiais HRC, validado empiricamente em pt25d:

- `UTG = 0` (first-to-act preflop)
- `SB = N - 2`
- `BB = N - 1`
- Restantes: contíguos entre UTG e SB

Atenção: o nosso backend tinha bug pré-pt25d com convenção rotativa SB=0.
Está corrigido. Manifest field `prune_index_convention: "hrc_docs_v1"`
permite distinguir zips pré/pós-pt25d.

API JavaScript do HRC:
- `ctx.getActivePlayer()` devolve índice na convenção docs.
- `ctx.getPlayerIndexButton/SmallBlind/BigBlind()` devolvem índices na
  convenção docs.

## Anexo B: Labels canónicos de posição

Estes são os labels **visíveis na coluna Player da Strategy Table do HRC**,
não os internos do nosso software:

| N | Labels |
|---|---|
| 2 (HU) | `BU/SB` + `BB` |
| 3 | UTG / SB / BB |
| 4 | UTG / BU / SB / BB |
| 5 | UTG / HJ / BU / SB / BB |
| 6 | UTG / HJ / CO / BU / SB / BB |
| 7 | UTG / MP / HJ / CO / BU / SB / BB (confirmado empiricamente em screenshot Q6.hrcz) |
| 8 | UTG / EP / MP / HJ / CO / BU / SB / BB (**LACUNA — confirmar empiricamente**) |
| 9 | UTG / EP1 / EP2 / MP / HJ / CO / BU / SB / BB (**LACUNA — idem**) |

Para N=2 (HU), o agressor pré-flop é o **botão**, que aparece como
`BU/SB` (label dual porque o botão também é o SB em HU).

---

## Lacunas pendentes

Coisas que faltam ao documento, em ordem de prioridade:

| # | Lacuna | Quem responde |
|---|---|---|
| ~~1~~ | ~~Coords do popup Nash (Scope, Selected Subtree, OK)~~ **FECHADA pt32-pt34:** Scope/CI por coord (a funcionar); OK por BM_CLICK (sem coord). Ver §6 | — |
| 2 | Versão exacta do HRC instalado | Rui |
| 3 | Maximização da janela ao arrancar | Rui |
| 4 | 4º modelo no dropdown Equity Model | Rui (a foto que mandou em pt23 mostra 4 modelos) |
| 5 | Coord do campo "Other Tables" na página MTT Stacks | Smoke devagar |
| 6 | Valores literais de `SCRIPTING_TAB`, `SCRIPT_FOLDER`, `BTN_NEXT`, `BTN_FINISH` | Code (descobre no .pyc Baltazar — read-only) |
| ~~7~~ | ~~Coord rel do botão OK e Cancel no popup Nash~~ **FECHADA pt33:** botões nativos SWT → BM_CLICK, não precisam de coord. Ver §6 | — |
| 8 | Labels EP/MP para N=8 e N=9 | Rui se encontrar mãos reais 8/9-handed |
| 9 | Bounty para sites USD `.com` — confirmar se `$` é aceite em algum formato | Smoke real com HH PokerStars `.com` |
| 10 | Cálculo de bounty acumulado real (vs base $250) — fonte: tournament_summaries + KOs | Tech debt `#HRC-GG-KOS-EXTRACTION` |
| 11 | Confirmar formato Winamax como alternativa ao PS (para conversão GG → ?) | Smoke devagar |
| 12 | Prize structure completa em `payouts.json` (hoje termina no 10º; torneios grandes pagam 15-30% do field) | Tech debt `#HRC-PAYOUTS-INCOMPLETO` — Vision parser + pipeline Discord |
| 13 | `total_chips` em `payouts.json` (hoje `null`; necessário para chip average e ICM correcto) | Tech debt `#HRC-TOTAL-CHIPS-MISSING` — fonte: lobby do torneio |

---

## Como manter este documento vivo

- Qualquer descoberta nova sobre o HRC → acrescentar aqui antes de
  fechar o trabalho.
- Quando uma coord é re-calibrada, actualizar a tabela §11 e datar.
- Quando o HRC for actualizado (raro), validar todas as coords. Pode
  forçar reescrita de várias secções.
- Quando dois factos colidem, prevalece o mais recente, com nota
  explicativa.

## Cross-references

- `docs/REGRAS_NEGOCIO.md` §13 (pipeline HRC), §14 (tag-based equity)
- `docs/TECH_DEBTS_INVENTARIO.md` (bugs do nosso software)
- `tools/watcher_src/patched_funcs.py` (onde as coords vivem em código)
- Journals: pt22 (smoke original Baltazar), pt23 (descompilação + fixes
  A/B/C/E), pt25b-c-d (pré-Bloco 2), pt25e (Bloco 1 source-side),
  pt25f (Bloco 2 source-side), pt26 (smoke real pt26 + bugs descobertos),
  pt27 (backend fixes), pt28 (clipboard race + scope bug
  + descoberta formato HH PokerStars como conversão obrigatória GG → HRC),
  pt29 (cascata Finish slow-click + wait_for_calculation),
  **pt30-pt34** (`JOURNAL_2026-05-22-pt30-pt34.md` — fecho da cadeia da 2ª
  run: SWT, popup `#32770`, janelas de progresso, BM_CLICK no OK)
- `docs/WORKFLOW_OPERACIONAL.md` (como trabalhar cada tipo de mão / formato)
- `docs/RUNBOOK_SMOKE_BEELINK.md` (operação do smoke no Beelink)
