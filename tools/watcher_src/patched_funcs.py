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
    """
    _set_ci_target_common(wpos, value, 'initial')


def set_ci_target_refine(wpos, value=10.0):
    """pt25e Bug F — set do CI Target para a 2ª run em Selected Subtree.

    Default 10.0 = refinamento de precisão útil (vs 5.0 da 1ª run que é
    para exploração rápida). Chamado em Bloco 2 entre Prune Action + Scope
    selection e o 2º Calculate.

    Não é chamado em Bloco 1 — fica disponível para a wiring de Bloco 2
    (ver stubs em `setup_hand`).
    """
    _set_ci_target_common(wpos, value, 'refine')


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

    # === pt25e Bloco 2 STUBS — Bug G + J + Bug F refine + 2ª run ===
    # Sequência completa após 1ª run, pendente de calibração de coords +
    # wiring em Bloco 2. Em Bloco 1 o setup_hand para aqui (não chama
    # finalize_after_second_run), por design — watcher fica pendurado em
    # `wait_for_export` se alguém arrancar este source recompilado. O
    # `.exe` em produção (Beelink) continua pt25d.
    #
    # aggressor_real_action = _payouts.get('aggressor_real_action')
    # if aggressor_real_action is not None:
    #     # Bug J (#WATCHER-BUG-J-PRUNE-ACTION-PER-LINE): Prune Action
    #     # manual em cada linha downstream da tree. DOWNSTREAM_POSITIONS
    #     # vem do script.js injectado pelo backend (pt25d) — watcher
    #     # itera a tree visual e aplica Prune Action em cada.
    #     for line_coords in _enumerate_downstream_lines(wpos):
    #         prune_action_on_line(wpos, line_coords)
    #
    #     # Bug G passo 1 (#WATCHER-BUG-G-SCOPE-SELECTED-SUBTREE): mudar
    #     # Scope do painel da 2ª run para "Selected Subtree".
    #     _set_scope_selected_subtree(wpos)
    #
    #     # Bug G passo 3: seleccionar a linha do sizing real do raiser
    #     # inicial na tree visual. `aggressor_real_action` (pt25e backend)
    #     # diz qual sizing clicar — e.g., {type:"raise", size_bb: 2.0} →
    #     # clicar linha do open 2bb na tree.
    #     _select_subtree_root_by_action(wpos, aggressor_real_action)
    #
    #     # Bug F refine: set CI Target 10.0 (vs 5.0 da 1ª run) para
    #     # refinamento de precisão útil na subtree.
    #     set_ci_target_refine(wpos, value=10.0)
    #
    #     # 2ª run em Selected Subtree.
    #     print('   A calcular (2ª run, Selected Subtree)...')
    #     start_calculation(10.0)
    #
    # # Bug H: finalize APÓS 2ª run, não a meio do setup_hand.
    # finalize_after_second_run(wpos, export_zip)
    # === FIM STUBS Bloco 2 ===

    print(f'   [QUEUED] {hand_name} → {os.path.basename(export_zip)} '
          f'(Bloco 1 — finalize Bloco 2)')
    return export_zip
