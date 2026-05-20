"""Patched watcher functions (pt23 fixes A/B/C).

Substitui via marshal code-object swap 4 funções do hrc_watcher_apr19.pyc
do Baltazar. Contexto + provenance + estratégia em README.md desta pasta.

GLOBAIS NÃO IMPORTADOS — resolução em runtime contra o module namespace
do watcher após swap. Detalhes em README.md §"Resolução de globais".
"""
import json
import os
import re
import time


def set_equity_model(wpos, equity_model):
    """Seleciona o Equity Model no HRC via typeahead no campo dropdown.

    pt23 fix Bug A: aceita identificadores estáveis do backend
    (poker-app `services/queue_export.py`) em vez do `stage` ('FT'/'MTT') do
    meta.json. O dropdown HRC tem 4 entradas (validado por Rui via foto):
    ChipEV in Big Blinds / Malmuth-Harville 'ICM' / Future Game Simulation
    'FGS' / Multi Table (MTSNG/MTT) 'ICM'. Apenas 2 são usadas pelo nosso
    pipeline; FGS fica fora do scope pt23.

    Valores aceites:
      - 'malmuth_harville_icm' → typeahead 'ma' → Malmuth-Harville ICM
      - 'multi_table_icm'      → typeahead 'mu' → Multi Table ICM (default p/ mid-MTT)
      - outro                  → fallback Multi Table ICM + print WARN
    """
    EQUITY_MODEL_X = 446
    EQUITY_MODEL_Y = 561
    click_rel(wpos, EQUITY_MODEL_X, EQUITY_MODEL_Y)
    time.sleep(0.8)
    pyautogui.press('home')
    time.sleep(0.15)
    if equity_model == 'malmuth_harville_icm':
        pyautogui.typewrite('ma', interval=0.15)
        label = 'Malmuth-Harville ICM'
    elif equity_model == 'multi_table_icm':
        pyautogui.typewrite('mu', interval=0.15)
        label = 'Multi Table ICM'
    else:
        print(f"   [WARN] equity_model desconhecido '{equity_model}' — fallback Multi Table ICM")
        pyautogui.typewrite('mu', interval=0.15)
        label = 'Multi Table ICM'
    time.sleep(0.2)
    pyautogui.press('enter')
    time.sleep(0.3)
    print(f'   Equity Model: {label}')


def get_player_count_from_hh(hh_text):
    """Extrai o nº de jogadores da hand history (apenas seats antes do SUMMARY).

    pt23 Bug B target: corpo idêntico ao original do Baltazar. O fix do Bug B
    está no caller (setup_hand) que prefere `max_players` do payouts.json
    quando disponível, e só cai para esta função como fallback.

    NOTA: o pycdc 0.x rendeu mal `m = re.search(...)` como `m = None.search(...)`
    por causa do NULL marker em LOAD_GLOBAL Python 3.12 — confirmado errado
    pelo dis manual. Esta versão usa `re.search` correcto.
    """
    pre_summary = hh_text.split('*** SUMMARY ***')[0]
    seats = re.findall(r'^Seat \d+: \S+ \(\d+ in chips', pre_summary, re.MULTILINE)
    if seats:
        return len(seats)
    m = re.search(r'(\d+)-max', hh_text)
    if m:
        return int(m.group(1))
    return None


def setup_scripting(wpos, script_path):
    """Activa o tab Scripting e carrega um script HRC Pro (.js).

    pt23 Bug C target: corpo idêntico ao original do Baltazar — a função
    já aceitava `script_path` como override do `SCRIPT_FILE` global (idiom
    `script_path or SCRIPT_FILE`). O fix do Bug C fica no caller
    (setup_hand) que passa hint `script_path` extraído do payouts.json
    quando o backend o escreve.
    """
    click_rel(wpos, *SCRIPTING_TAB)
    time.sleep(0.5)
    click_rel(wpos, *SCRIPT_FOLDER)
    time.sleep(1.5)
    paste_path(script_path or SCRIPT_FILE)


# pt25e Bug F (#WATCHER-BUG-F-CI-TARGET-2ND-RUN): coords do campo CI Target
# no main UI HRC pós-finish do wizard.
#
# IMPORTANTE — coords NÃO são herdadas de pt25d:
# Em pt25d, `start_calculation` (Baltazar original, não-patched) fazia set CI
# DENTRO da Nash dialog popup — coords computadas relativas ao `rect` do
# popup (`rect.left + int(w * 0.65)`, `rect.top + int(h * 0.51)`), não no
# main UI. Os helpers novos abaixo apontam para conceito diferente: campo
# CI Target no main UI antes de clicar Calculate. Nunca houve coords
# calibrados para este campo — daí placeholder (0,0) + early-return
# defensivo. Bloco 2 calibra com smoke devagar do Rui.
#
# `start_calculation` original continua a correr depois e ainda lida com a
# Nash dialog que aparece (seu próprio set CI no popup). Os 2 sets podem
# coexistir até que o Bloco 2 decida se mantém só um.
CI_TARGET_FIELD_X = 0  # TODO pt25e Bloco 2: calibrar (não-herdado de pt25d)
CI_TARGET_FIELD_Y = 0  # TODO pt25e Bloco 2: calibrar (não-herdado de pt25d)


def _set_ci_target_common(wpos, value, label):
    """Helper privado partilhado por `set_ci_target_initial` /
    `set_ci_target_refine`: estrutura click+wait idêntica, diferindo apenas
    no valor e no label de log.

    Defensiva: se coords ainda não foram calibrados (ambos == 0), faz
    early-return com WARN em vez de clicar (0, 0) — evita race conditions
    com outras janelas e mantém o flow seguro até Bloco 2 calibrar.
    """
    if CI_TARGET_FIELD_X == 0 and CI_TARGET_FIELD_Y == 0:
        print(f'   [WARN] CI Target {label}: coords não calibrados '
              f'(pt25e Bloco 2 pendente) — set ignorado, value={value}')
        return
    click_rel(wpos, CI_TARGET_FIELD_X, CI_TARGET_FIELD_Y)
    time.sleep(0.3)
    pyautogui.hotkey('ctrl', 'a')
    time.sleep(0.1)
    pyperclip.copy(str(float(value)))
    pyautogui.hotkey('ctrl', 'v')
    time.sleep(0.2)
    pyautogui.press('tab')  # commit edit + leave focus
    time.sleep(0.3)
    print(f'   CI Target {label}: {value}')


def set_ci_target_initial(wpos, value=5.0):
    """pt25e Bug F — set do CI Target no main UI HRC para a 1ª run.

    Default 5.0 = exploração rápida da árvore (configuração canónica do
    flow do Baltazar). Chamado em `setup_hand` antes do 1º Calculate.

    Era parte do flow monolítico de `start_calculation`; split aqui para
    permitir 2 sets distintos (initial pre-1ª run, refine pre-2ª run após
    Prune Action manual + Scope=Selected Subtree). Ver Bug F em
    `docs/TECH_DEBTS_INVENTARIO.md`.

    DEPRECATED (Bloco 2 piece 1): o popup Nash gere o CI internamente
    (`start_calculation` original do Baltazar faz set CI relativo ao rect
    do popup). Esta função era um experimento de mover o set para o main UI
    antes de Calculate. Não calibrada (coords = 0). Mantida no source
    apenas para preservar a slot do marshal swap até peça 2 confirmar
    in-popup CI suficiente; remoção planeada após validação.
    """
    _set_ci_target_common(wpos, value, 'initial')


def set_ci_target_refine(wpos, value=10.0):
    """pt25e Bug F — set do CI Target para a 2ª run em Selected Subtree.

    Default 10.0 = refinamento de precisão útil (vs 5.0 da 1ª run que é
    para exploração rápida). Chamado em Bloco 2 entre Prune Action + Scope
    selection e o 2º Calculate.

    Não é chamado em Bloco 1 — fica disponível para a wiring de Bloco 2
    (ver stubs em `setup_hand`).

    DEPRECATED (Bloco 2 piece 1): mesma razão que `set_ci_target_initial`.
    O refinamento de CI para a 2ª run deve passar a ser feito dentro do
    popup Nash pela própria `start_calculation_selected_subtree`. Mantida
    até peça 2 confirmar.
    """
    _set_ci_target_common(wpos, value, 'refine')


# pt25e Bloco 2 piece 1 (#WATCHER-BUG-G-SCOPE-SELECTED-SUBTREE):
# Dropdown "Scope" dentro do popup Nash que abre quando o watcher clica
# Calculate. Default do HRC é "Full Tree"; queremos "Selected Subtree" para
# a 2ª run após Prune Action ter ficado aplicado nas linhas downstream.
#
# CONVENÇÃO: pixels relativos ao TOP-LEFT do popup rect
# (`left + REL_X`, `top + REL_Y` no click time).
#
# Mudança em pt26 (19 Maio 2026): convenção migrou de fracções para
# pixels-rel. Razão: smoke 19 Maio capturou popup rect 436×230, vs popup
# 416×214 do smoke 18 Maio — variação +4.8% width / +7.5% height.
# Dialogs Qt anchoram widgets em posição fixa em pixels ao top-left
# (resize adiciona margem, não escala widgets), pelo que fracções drift
# ~13px X quando o popup cresce. Pixels-rel preservam directamente a
# medição empírica do smoke 18 Maio.
#
# Smoke devagar 2026-05-18 com Rui no Beelink contra popup Nash 416×214:
#   - Dropdown abs (944, 439); top-left popup (666, 372) → rel (278, 67).
#   - "Selected Subtree" opção abs (940, 480); rel (274, 108) — highlight
#     visualmente confirmado pelo Rui.
#   - Popup tinha exactamente 2 opções no menu (Full Tree / Selected Subtree).
#
# Defensive return: se algum REL for 0 OU se `popup_rect` for None.
# Pós-calibração os defensivos ficam dormant em produção mas regridem-se
# via tests.
SCOPE_DROPDOWN_REL_X = 278
SCOPE_DROPDOWN_REL_Y = 67
SCOPE_OPTION_SELECTED_SUBTREE_REL_X = 274
SCOPE_OPTION_SELECTED_SUBTREE_REL_Y = 108


# pt25e Bloco 2 piece 2 — CI Target dentro do popup Nash.
# Pixels-rel derivados das fracções legacy `start_calculation` (Baltazar
# pt25d): `rect.left + int(w * 0.65)`, `rect.top + int(h * 0.51)` ×
# popup 416×214 = (270, 109). Migrado para REL em pt26 pelo mesmo motivo
# do dropdown Scope acima (popup com tamanho variável).
CI_TARGET_POPUP_REL_X = 270
CI_TARGET_POPUP_REL_Y = 109


# pt26 Bloco 2 piece 2 — Botão verde Calculate no main UI HRC.
# Calibrado em smoke 2026-05-19 com Rui no Beelink: posição absoluta
# (487, 124), main HRC window wpos (left=283, top=65, w=1050, h=850) →
# rel (204, 59). Convenção: pixels relativos à wpos, mesma de
# `EQUITY_MODEL_X/Y`, `STRATEGY_TABLE_FOCUS_X/Y`, e usada por `click_rel`.
# Fracções ficam reservadas para o popup Nash (rect variável); o main
# HRC window é fixo durante uma sessão (wpos capturado uma vez no wizard).
CALCULATE_BUTTON_X = 204
CALCULATE_BUTTON_Y = 59


# pt26 Bloco 2 piece 2 — heurística de título para identificar a Nash
# dialog. Smoke 19 Maio capturou o título exacto "Nash Calculation"
# (via `pyautogui.getAllWindows()`). Substring case-insensitive sobre
# este token reduz falsos positivos vs hints provisórios pt25e
# `("Nash", "Calculate")` — "Calculate" sozinho podia colidir com outras
# dialogs HRC genéricas.
_NASH_POPUP_TITLE_HINTS = ("Nash Calculation",)
_NASH_POPUP_WAIT_TIMEOUT_S = 5.0
_NASH_POPUP_WAIT_POLL_S = 0.2


def _wait_for_nash_popup(timeout=_NASH_POPUP_WAIT_TIMEOUT_S,
                         poll_interval=_NASH_POPUP_WAIT_POLL_S):
    """Polls pela janela do popup Nash (separado do main HRC window) e
    devolve `(left, top, width, height)` ou `None` em timeout.

    Estratégia: substring case-insensitive contra `_NASH_POPUP_TITLE_HINTS`
    sobre os títulos de janelas top-level via `pyautogui.getAllWindows()`.
    Em caso de match com width × height válido (popup é dialog modal, não
    minimizada), devolve o rect. Caso contrário polla a cada
    `poll_interval` segundos até `timeout`.

    Robustez:
      - Janelas com title vazio ignoradas (compositor, system).
      - Janelas com width <= 0 ou height <= 0 ignoradas (minimizadas).
      - Falhas ao chamar getAllWindows → log WARN e tenta de novo na
        próxima iteração (pode acontecer em race condition de janela a
        abrir).

    Falsos positivos teóricos: outras dialogs HRC com "Nash" ou
    "Calculate" no título. Em prática, no flow pós-1ª-run, o único popup
    aberto é o Nash dialog que aparece ao clicar Calculate.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            windows = pyautogui.getAllWindows()
        except Exception as _e:
            print(f'   [WARN] _wait_for_nash_popup: getAllWindows falhou ({_e}); retry')
            time.sleep(poll_interval)
            continue
        for w in windows:
            title = (getattr(w, 'title', '') or '').strip()
            if not title:
                continue
            width = getattr(w, 'width', 0) or 0
            height = getattr(w, 'height', 0) or 0
            if width <= 0 or height <= 0:
                continue
            title_lower = title.lower()
            for hint in _NASH_POPUP_TITLE_HINTS:
                if hint.lower() in title_lower:
                    left = getattr(w, 'left', 0) or 0
                    top = getattr(w, 'top', 0) or 0
                    print(f'   _wait_for_nash_popup: matched title={title!r} '
                          f'rect=({left},{top},{width},{height})')
                    return (left, top, width, height)
        time.sleep(poll_interval)
    print(f'   [WARN] _wait_for_nash_popup: timeout {timeout}s — '
          'popup não detectado')
    return None


def _click_calculate_button(wpos):
    """Click no botão verde Calculate no main UI HRC. Coords em pixels
    relativos à wpos (mesma convenção que `EQUITY_MODEL_X/Y`, usada por
    `click_rel`). Calibrado em smoke pt26 — ver bloco de constantes.

    Defensive: ambos a 0 (regressão de calibração) → early-return WARN.
    """
    if CALCULATE_BUTTON_X == 0 and CALCULATE_BUTTON_Y == 0:
        print('   [WARN] _click_calculate_button: coords não calibrados '
              '— click ignorado')
        return
    click_rel(wpos, CALCULATE_BUTTON_X, CALCULATE_BUTTON_Y)
    time.sleep(0.3)


def _fill_ci_target_in_popup(popup_rect, ci_target):
    """Preenche CI Target dentro do popup Nash. Pixels-rel ao top-left do
    popup (convenção pt26; bloco de constantes acima). Valores derivados
    das fracções legacy `start_calculation` (Baltazar pt25d) sobre o popup
    416×214 do smoke 18 Maio.

    Defensive: `popup_rect=None` → early-return.
    """
    if popup_rect is None:
        print('   [WARN] _fill_ci_target_in_popup: popup_rect ausente — fill ignorado')
        return
    left, top, _width, _height = popup_rect
    abs_x = left + CI_TARGET_POPUP_REL_X
    abs_y = top + CI_TARGET_POPUP_REL_Y
    pyautogui.click(abs_x, abs_y)
    time.sleep(0.3)
    pyautogui.hotkey('ctrl', 'a')
    time.sleep(0.1)
    pyperclip.copy(str(float(ci_target)))
    pyautogui.hotkey('ctrl', 'v')
    time.sleep(0.2)
    print(f'   CI Target (popup): {ci_target}')


def _click_ok_in_popup(popup_rect):
    """Confirma o popup Nash. Usa Enter — convenção universal Qt para
    dialog modal default-button=OK. Evita calibração de coord do botão
    OK em específico.

    `popup_rect` aceito por consistência de assinatura com o resto do
    flow; não usado (Enter é global).
    """
    pyautogui.press('enter')
    time.sleep(0.3)
    print('   OK (popup Nash)')


def _set_scope_in_popup(popup_rect):
    """Muda o dropdown Scope no popup Nash de "Full Tree" → "Selected Subtree".

    Pré-condição: popup Nash já aberto + CI Target preenchido. Pós-condição:
    Scope = "Selected Subtree", pronto a clicar OK.

    `popup_rect` é `(left, top, width, height)` do popup Nash; caller é
    responsável pela detecção do rect. Coord absoluta de cada click é
    `(left + REL_X, top + REL_Y)` — pixels-rel ao top-left do popup
    (convenção pt26; ver bloco de constantes acima).

    Defensivos:
      - Qualquer REL == 0 → coords não-calibrados → early-return WARN.
      - popup_rect is None → caller ainda não detecta popup → early-return WARN.

    Implementação: 2 clicks sequenciais com `pyautogui.click(abs_x, abs_y)`
    (NÃO `click_rel`, porque os REL aplicam-se ao popup_rect, não ao main
    HRC window).
    """
    if (SCOPE_DROPDOWN_REL_X == 0 or SCOPE_DROPDOWN_REL_Y == 0
            or SCOPE_OPTION_SELECTED_SUBTREE_REL_X == 0
            or SCOPE_OPTION_SELECTED_SUBTREE_REL_Y == 0):
        print('   [WARN] _set_scope_in_popup: pixels-rel não calibrados '
              '— set ignorado, scope fica Full Tree')
        return
    if popup_rect is None:
        print('   [WARN] _set_scope_in_popup: popup_rect não fornecido '
              '— set ignorado, scope fica Full Tree')
        return
    left, top, _width, _height = popup_rect
    dropdown_x = left + SCOPE_DROPDOWN_REL_X
    dropdown_y = top + SCOPE_DROPDOWN_REL_Y
    pyautogui.click(dropdown_x, dropdown_y)
    time.sleep(0.3)
    option_x = left + SCOPE_OPTION_SELECTED_SUBTREE_REL_X
    option_y = top + SCOPE_OPTION_SELECTED_SUBTREE_REL_Y
    pyautogui.click(option_x, option_y)
    time.sleep(0.3)
    print('   Scope: Selected Subtree')


def start_calculation_selected_subtree(wpos, ci_target):
    """Parallel a `start_calculation` para o flow Scope=Selected Subtree.

    Decisão arquitectural pt25e Bloco 2 piece 1: abordagem (b) — manter o
    `start_calculation` original (Baltazar, dentro do .pyc) intacto para o
    flow Full Tree, e construir esta função paralela para o flow Selected
    Subtree. Justificação: não temos source de `start_calculation`; uma
    decomposição cirúrgica em peças (`_click_calculate_button` /
    `_fill_ci_target_in_popup` / `_click_ok_in_popup`) exigiria recuperar
    timing constants + popup-rect logic do bytecode — o `pycdc` já provou
    falhar em pelo menos um sítio importante (ver nota em
    `get_player_count_from_hh` linha 60-61). Função paralela isola o risco:
    se peça 2 tiver bugs nos passos 1/2/5, o Full Tree path original
    continua a funcionar.

    Sequência alvo dentro do popup Nash:
      1. Click Calculate (abre popup).             [piece 2 — calibração]
      2. Fill CI Target no popup.                  [piece 2 — calibração]
      3. _set_scope_in_popup(wpos)                 [piece 1 — esta função]
      4. Click OK / Enter.                          [piece 2 — calibração]

    `wpos` é o win_pos do main HRC window (mesmo objecto que
    `start_calculation` recebe via globals). `ci_target` é o CI a usar na
    2ª run (default product: 10.0).

    Defensive em cada passo: se `_click_calculate_button` não tem coords
    (placeholder), `_wait_for_nash_popup` devolve None por timeout, e os
    helpers downstream (fill CI / scope / OK) fazem early-return. O flow
    inteiro degrada para no-op com WARN logs em vez de cliques errantes.

    pt28 (#FINALIZE-NEVER-FIRES-ON-NO-OP): devolve `bool`:
      - `True` se passos 1-4 completaram (popup detectado + fill CI + set
        scope + OK Enter). Caller (`setup_hand`) interpreta como "2ª run
        em curso — finalize exporta zip pós-2ª-run".
      - `False` se popup_rect é None (timeout do `_wait_for_nash_popup`).
        Caller deve fazer finalize com WARN explícito em vez de exportar
        zip parcial silenciosamente (cenário pt27 GG-5944816316).
    """
    _click_calculate_button(wpos)                         # passo 1a
    popup_rect = _wait_for_nash_popup()                   # passo 1b
    if popup_rect is None:
        print(f'   [WARN] start_calculation_selected_subtree(ci={ci_target}): '
              'popup não detectado; flow degrada para no-op')
        return False
    _fill_ci_target_in_popup(popup_rect, ci_target)       # passo 2
    _set_scope_in_popup(popup_rect)                        # passo 3
    _click_ok_in_popup(popup_rect)                         # passo 4

    print(f'   start_calculation_selected_subtree(ci={ci_target}) — '
          '2ª run em Selected Subtree disparada')
    return True


# pt25e Bug J (#WATCHER-BUG-J-PRUNE-ACTION-PER-LINE): stub para Prune Action
# linha-a-linha no context menu HRC. Coords + ordem das entradas no menu
# pendentes de calibração em smoke devagar pt25e Bloco 2. Não chamado neste
# bloco; existe para receber wiring + tests downstream.
def prune_action_on_line(wpos, line_coords):
    """pt25e Bug J — Prune Action manual sobre uma linha downstream da tree.

    Plano (Bloco 2):
    1. right-click em `line_coords` (posição da linha do sizing na tree visual)
    2. esperar context menu aparecer
    3. seleccionar a entrada *exacta* "Prune Action" (NÃO o Prune global —
       há 2 entradas com "Prune" no menu; armadilha conhecida).
    4. esperar refresh da tree.

    Body intencionalmente vazio em Bloco 1. Calibração de coords das entradas
    do menu + texto exacto é trabalho de Bloco 2 (Rui faz smoke devagar e
    regista). Estrutura template = `setup_scripting` (mesma anatomia
    click+wait, alvo diferente).
    """
    # TODO pt25e Bloco 2: implementar (right-click + select "Prune Action")
    pass


# pt25e Bloco 2 piece 2 (#WATCHER-BUG-G-NAV-TO-RAISER-NODE): foco na
# Strategy Table HRC para receber as seta-down presses. Click numa coord
# neutra DENTRO da tabela (qualquer linha) garante o foco; ESC-style
# pyautogui.click no main wpos+offset assumido seguro.
#
# Coord escolhida: (50, 200) relativos ao main HRC window — área da
# 1ª linha da Strategy Table, à esquerda do scroll bar e longe dos botões.
# Não muda o cursor da Strategy Table (a 1ª linha já está seleccionada
# por default após 1ª run; click sobre ela é no-op de seleção e dá foco
# ao widget). Coord pode precisar refinement em smoke piece 2 — early-
# return defensivo se algum dia esta heurística falhar.
STRATEGY_TABLE_FOCUS_X = 50
STRATEGY_TABLE_FOCUS_Y = 200


def _focus_strategy_table(wpos):
    """DEPRECATED (pt28): NÃO CHAMAR. Mantido apenas para preservar o slot
    do marshal swap em hrc_watcher_apr19.pyc (a posição da função no module
    table não pode ser removida sem partir o swap).

    Razão da desactivação: em pt27 (smoke real GG-5944816316) o popup Nash
    da 2ª run nunca abria. Causa raiz isolada por colaboração Web+Rui: pt26
    `.exe` corre Strategy Table que **já tem foco do teclado por default
    pós-1ª-run**; as setas funcionam directamente. Este click intermédio
    cai em STRATEGY_TABLE_FOCUS_X/Y que **nunca foram calibrados em smoke**
    — o click acertava em coords não-validadas, tirava o foco que estava
    bom, as 4 setas-down a seguir iam para sítio nenhum, cursor não descia
    até à linha do raiser, 2º Calculate clicava sobre selecção inválida e
    o popup Nash não abria → `_wait_for_nash_popup` timeout silencioso.

    `navigate_to_target_node` deixou de chamar esta função em pt28. A
    definição fica no source para o marshal swap não regredir; chamadores
    foram removidos. Se algum dia houver evidência de que o foco da
    Strategy Table NÃO é default, abrir tech debt nova com smoke calibrado
    e re-wirar (não basta descomentar — STRATEGY_TABLE_FOCUS_X/Y continuam
    sem calibração validada).
    """
    click_rel(wpos, STRATEGY_TABLE_FOCUS_X, STRATEGY_TABLE_FOCUS_Y)
    time.sleep(0.2)


def navigate_to_target_node(wpos, target_node_offset):
    """pt25e Bloco 2 piece 2 — preme seta-para-baixo `target_node_offset`
    vezes para mover o cursor da Strategy Table HRC do default (1ª linha)
    até à linha do raiser real.

    `target_node_offset` é o campo `meta.json.target_node_offset` calculado
    pelo backend (`hrc_node_offset.compute_target_node_offset`).

    Defensive:
      - `None` ou `0` → skip (cursor fica na 1ª linha; sem foco set
        para evitar interacções desnecessárias).
      - Inteiro negativo → log WARN, skip.
      - Inteiro > 100 → log WARN, skip (sanity; tabela com 100+ linhas
        é improvável e indica bug no compute).

    Comportamento empírico da Strategy Table (validado em smoke):
      - Cursor por defeito na 1ª linha após 1ª run.
      - Seta-baixo move 1 linha (não cycles no fim).
      - Pequeno delay entre presses evita key drops em ambientes
        com input throttling.
    """
    if target_node_offset is None or target_node_offset == 0:
        print('   navigate_to_target_node: offset is None/0 — skip')
        return
    if not isinstance(target_node_offset, int):
        print(f'   [WARN] navigate_to_target_node: offset não-int '
              f'({type(target_node_offset).__name__}) — skip')
        return
    if target_node_offset < 0 or target_node_offset > 100:
        print(f'   [WARN] navigate_to_target_node: offset {target_node_offset} '
              'fora de [1, 100] — skip')
        return
    # pt28: SEM call a _focus_strategy_table — Strategy Table já tem foco
    # por default pós-1ª-run (validado por Rui no .exe pt26). Ver docstring
    # DEPRECATED em `_focus_strategy_table`.
    for _ in range(target_node_offset):
        pyautogui.press('down')
        time.sleep(0.05)
    print(f'   navigate_to_target_node: {target_node_offset} ↓ presses')


def finalize_after_second_run(wpos, export_zip):
    """pt25e Bug H — fecho do flow após 2ª run completa.

    Faz `export_strategies(export_zip)` que era o último passo do `setup_hand`
    original. Movido para função separada porque deve correr APÓS Prune
    Action + Scope=Selected Subtree + set_ci_target_refine + 2º Calculate
    (ver ordem em Bug H, `docs/TECH_DEBTS_INVENTARIO.md`).

    Não é chamado em Bloco 1 — `setup_hand` retorna export_zip sem ter
    feito export. O watcher fica pendurado em `wait_for_export` por design
    (Bloco 1 valida arquitectura; `.exe` em produção continua pt25d).
    """
    print('   A fazer queue do export (finalize após 2ª run)...')
    export_strategies(export_zip)


def setup_hand(hand_name, hand_path):
    """Fase 1 do watcher: wizard → calcular → queue export.

    Retorna o path do `export_zip` se chegou ao fim do wizard, ou False se
    bailou cedo (HH ausente / HRC não iniciou / wizard não encontrado).

    pt23 fix A+B+C: lê hints `equity_model`/`max_players`/`script_path` de
    payouts.json (escritos pelo backend `services/queue_export.py`) e
    despacha para `set_equity_model`/`set_hand_mode_players`/`setup_scripting`.
    Restante fluxo idêntico ao original — confirmado linha-a-linha contra
    `setup_hand_dis.txt` (665 linhas bytecode).
    """
    print('\n==================================================')
    print(f'  [SETUP] {hand_name}')
    print('==================================================')

    # localizar o ficheiro .txt (hand history)
    hh_path = None
    for fname in os.listdir(hand_path):
        if fname.endswith('.txt'):
            hh_path = os.path.join(hand_path, fname)
    if not hh_path:
        print('   ERRO: Nenhum .txt encontrado!')
        return False

    with open(hh_path, 'r', encoding='utf-8') as f:
        hh_text = f.read().strip()

    print(f'   HH: {os.path.basename(hh_path)} ({len(hh_text)} chars)')

    # localizar prize/payout JSON: 1ª passagem por padrão Baltazar,
    # 2ª passagem fallback para qualquer .json que não seja meta.json
    prize_path = None
    for fname in os.listdir(hand_path):
        if fname.endswith('_hrc.json') or ('payout' in fname.lower() and fname.endswith('.json')):
            prize_path = os.path.join(hand_path, fname)
    if not prize_path:
        for fname in os.listdir(hand_path):
            if fname.endswith('.json') and fname != 'meta.json':
                prize_path = os.path.join(hand_path, fname)

    # meta.json opcional (stage/players_left/total_chips/ci)
    hand_meta = {}
    meta_path = os.path.join(hand_path, 'meta.json')
    if os.path.exists(meta_path):
        with open(meta_path) as f:
            hand_meta = json.load(f)

    stage = hand_meta.get('stage', 'FT')
    players_left = hand_meta.get('players_left')
    if players_left is not None:
        if stage != 'MTT':
            print(f"   [override] stage '{stage}' -> 'MTT' because players_left={players_left} is set")
        stage = 'MTT'

    players_in_hand = get_player_count_from_hh(hh_text)
    total_chips = hand_meta.get('total_chips')
    ci_target = float(hand_meta.get('ci') or 5.0)
    print(f'   Stage: {stage} | In hand: {players_in_hand} | Players left: {players_left} | Total chips: {total_chips} | CI: {ci_target}')

    # auto-discovery de script .js no hand_path (mecanismo Baltazar) —
    # preservado para fidelidade ao original; em pt23 não é utilizado
    # quando há hint `script_path` no payouts.json
    custom_script = None
    for fname in os.listdir(hand_path):
        if fname.endswith('.js'):
            custom_script = os.path.join(hand_path, fname)
            print(f'   Script custom: {fname}')

    # === pt23 fix A/B/C: hints do payouts.json ===
    _payouts = {}
    if prize_path:
        try:
            with open(prize_path, 'r', encoding='utf-8') as f:
                _loaded = json.load(f)
            if isinstance(_loaded, dict):
                _payouts = _loaded
        except Exception as _e:
            print(f"   [WARN] payouts.json load falhou ({_e}); usando defaults pt23")
    equity_model = _payouts.get('equity_model', 'multi_table_icm')
    max_players = _payouts.get('max_players')
    if max_players is None:
        max_players = players_in_hand
    script_path = _payouts.get('script_path')
    # === end pt23 ===

    # arrancar HRC
    hrc = ensure_hrc()
    if not hrc:
        print('   ERRO: HRC Pro não iniciou!')
        return False

    print('   A abrir wizard...')
    win = open_wizard()
    if not win:
        print('   ERRO: Wizard não encontrado!')
        return False

    wpos = get_win_pos(win)

    print('   A colar HH...')
    paste_hh(wpos, hh_text)

    # pt23 fix B + fix A: hints substituem inputs do original
    set_hand_mode_players(wpos, max_players)        # original: players_in_hand
    set_equity_model(wpos, equity_model)            # original: stage

    if prize_path:
        print(f'   Prizes: {os.path.basename(prize_path)}')
        import_prizes(wpos, prize_path)
        if is_ko_tournament(prize_path):
            print('   KO detetado — a selecionar Bounty Mode PKO 50%...')
            select_bounty_mode(wpos)

    if stage == 'MTT' and total_chips:
        print(f'   Total Chips: {total_chips:,}')
        click_rel(wpos, 677, 438)
        time.sleep(0.2)
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.1)
        pyautogui.typewrite(str(total_chips), interval=0.05)
        time.sleep(0.3)

    print('   Next...')
    click_rel(wpos, *BTN_NEXT)
    time.sleep(1.5)

    if stage == 'MTT' and (players_left or players_in_hand):
        print('   MTT Stacks...')
        handle_mtt_stacks_page(wpos, players_left or players_in_hand)
    elif equity_model == 'multi_table_icm':
        # pt23 fix Bug E: HRC mostra página MTT Stacks SEMPRE que o equity
        # model é Multi Table ICM (precisa info de outras mesas), independente
        # do nosso `stage`. Quando não temos players_left (ex: mão FT marcada
        # como tag não-FT mas sem meta MTT), saltamos a página clicando Next
        # directo — Other Tables fica em 0 (default HRC). Sem este branch o
        # watcher tentaria clicar SCRIPTING_TAB sobre a página MTT Stacks e
        # ficava pendurado. Tech debt #HRC-MTT-OTHER-TABLES-INFO.
        print('   MTT Stacks (default, skip)...')
        click_rel(wpos, *BTN_NEXT)
        time.sleep(1.5)

    # pt23 fix C: script_path hint vence; sem hint cai no SCRIPT_FILE global
    # (via idiom `script_path or SCRIPT_FILE` dentro de setup_scripting)
    print(f'   Scripting: {os.path.basename(script_path or SCRIPT_FILE)}')
    setup_scripting(wpos, script_path)              # original: custom_script

    print('   Finish...')
    click_rel(wpos, *BTN_FINISH)
    time.sleep(5)

    print('   A aguardar carregamento da mão (30s)...')
    time.sleep(30)

    # pt25e Bug F: set CI Target inicial (5.0) ANTES do 1º Calculate.
    # Split do flow monolítico antigo (start_calculation fazia tudo numa
    # call: click Calculate + Nash dialog + set CI + OK). Agora o set CI
    # acontece primeiro no main UI, e `start_calculation` continua a
    # dispatch o 1º cálculo (Nash dialog ainda aparece + confirma via Enter
    # se nash_found, ou fallback Enter).
    print('   Set CI Target inicial...')
    set_ci_target_initial(wpos, value=ci_target)

    print('   A calcular (1ª run)...')
    start_calculation(ci_target)

    exports_dir = os.path.join(DONE_DIR, 'Exports')
    os.makedirs(exports_dir, exist_ok=True)
    export_zip = os.path.join(exports_dir, hand_name + '.zip')

    # === pt25e Bloco 2 piece 2 — flow Selected Subtree end-to-end ===
    # Sequência completa após a 1ª run:
    #   1. (Bug J) Prune Action linha-a-linha downstream — pendente
    #      calibração de coords do context menu (smoke devagar futura).
    #      Por agora `prune_action_on_line` é stub (pass); chamada
    #      comentada até calibração.
    #   2. Navegar Strategy Table até linha do raiser real via seta-down
    #      × `target_node_offset` (calculado pelo backend e injectado em
    #      meta.json) — `navigate_to_target_node`.
    #   3. 2ª run em Selected Subtree — `start_calculation_selected_subtree`
    #      abre o popup Nash, fill CI, set Scope, click OK.
    #   4. (Bug H) Finalize → export zip.
    #
    # Defensive completo: cada passo tem fallback se algum coord ainda
    # estiver placeholder ou se popup detection falhar. O watcher degrada
    # para no-op com WARN logs em vez de cliques errantes.
    aggressor_real_action = _payouts.get('aggressor_real_action')
    target_node_offset = hand_meta.get('target_node_offset')
    second_run_dispatched = None  # None = não tentada; True/False = resultado
    if aggressor_real_action is not None:
        # Bug J — Prune Action downstream. CALIBRAÇÃO PENDENTE → comentado.
        # for line_coords in _enumerate_downstream_lines(wpos):
        #     prune_action_on_line(wpos, line_coords)

        # Navegação até linha do raiser real (#WATCHER-BUG-G-NAV).
        navigate_to_target_node(wpos, target_node_offset)

        # 2ª run em Selected Subtree (popup Nash gere fill CI + scope + OK).
        print('   A calcular (2ª run, Selected Subtree)...')
        second_run_dispatched = start_calculation_selected_subtree(wpos, 10.0)

    # pt28 (#FINALIZE-NEVER-FIRES-ON-NO-OP): se a 2ª run foi tentada mas
    # falhou (popup Nash não detectado), avisar antes do finalize — o zip
    # exportado será da 1ª run apenas, não da 2ª run em Selected Subtree.
    # Sem este WARN o failure era silencioso (cenário pt27 GG-5944816316:
    # `finalize_after_second_run` corria sempre e exportava o que estivesse).
    if second_run_dispatched is False:
        print(f'   [WARN] {hand_name}: 2ª run não disparou (popup Nash '
              'não abriu); finalize vai exportar zip da 1ª run apenas')

    # Bug H: finalize após 2ª run (ou skip da 2ª run se sem aggressor,
    # ou após WARN se 2ª run falhou em pt28).
    finalize_after_second_run(wpos, export_zip)
    # === FIM Bloco 2 piece 2 ===

    print(f'   [QUEUED] {hand_name} → {os.path.basename(export_zip)} '
          f'(Bloco 1 — finalize Bloco 2)')
    return export_zip
