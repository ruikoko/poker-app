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
import ctypes
from ctypes import wintypes


# ---------------------------------------------------------------------------
# pt30 (#WIZARD-FINISH-DISABLED-DURING-TREE-CALC): bloco Win32 para polling do
# estado do botao Finish do wizard "Hand Setup".
#
# IMPORTANTE — instancia WinDLL PROPRIA, nao `ctypes.windll.user32`:
# o launcher Baltazar (hrc_watcher_apr19_launcher.pyc) ja usa
# `EnumChildWindows` com um callback de assinatura DIFERENTE
# (`WINFUNCTYPE(c_bool, c_int, POINTER(c_int))`). `ctypes.windll.user32` e um
# singleton cached partilhado por todo o processo — configurar `.argtypes`
# nele afectaria as chamadas do launcher e podia parti-las (mismatch de tipo
# do callback). Uma instancia `ctypes.WinDLL("user32")` separada tem os seus
# proprios objectos-funcao, isolando os nossos argtypes do resto do processo.
#
# argtypes/restype explicitos sao obrigatorios em Windows 64-bit: HANDLE/HWND
# e LPARAM sao 64-bit; sem isto o ctypes assume int de 32-bit e trunca os
# handles, devolvendo lixo.
# ---------------------------------------------------------------------------
_pt30_user32 = ctypes.WinDLL("user32")
_PT30_WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

_pt30_user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
_pt30_user32.FindWindowW.restype = wintypes.HWND
_pt30_user32.EnumWindows.argtypes = [_PT30_WNDENUMPROC, wintypes.LPARAM]
_pt30_user32.EnumWindows.restype = wintypes.BOOL
_pt30_user32.EnumChildWindows.argtypes = [wintypes.HWND, _PT30_WNDENUMPROC, wintypes.LPARAM]
_pt30_user32.EnumChildWindows.restype = wintypes.BOOL
_pt30_user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
_pt30_user32.GetClassNameW.restype = ctypes.c_int
_pt30_user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
_pt30_user32.GetWindowTextW.restype = ctypes.c_int
_pt30_user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
_pt30_user32.GetWindowTextLengthW.restype = ctypes.c_int
_pt30_user32.IsWindowEnabled.argtypes = [wintypes.HWND]
_pt30_user32.IsWindowEnabled.restype = wintypes.BOOL
_pt30_user32.GetForegroundWindow.argtypes = []
_pt30_user32.GetForegroundWindow.restype = wintypes.HWND
# pt33 v1: SendMessageW para BM_CLICK no Button OK do popup Nash (análogo ao
# Save btn do export). LRESULT == LONG_PTR; `wintypes` não expõe LRESULT, por
# isso usa-se LPARAM como restype (mesmo width/signedness em 64-bit).
_pt30_user32.SendMessageW.argtypes = [
    wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
]
_pt30_user32.SendMessageW.restype = wintypes.LPARAM

BM_CLICK = 0x00F5  # mensagem Win32 que simula um click num Button nativo

# ── pt35 (GTO Brain Fase 1 — SWAP export_strategies) ──────────────────────
# Diálogo "Export Strategies": #32770 nativo de título VAZIO, com ComboBox +
# Buttons nativos (diagnóstico v2 no Beelink). Setamos o modo de export e
# clicamos OK por Win32 (sem coords), à imagem do BM_CLICK do popup Nash (pt33).
_pt30_user32.SetForegroundWindow.argtypes = [wintypes.HWND]
_pt30_user32.SetForegroundWindow.restype = wintypes.BOOL
_pt30_user32.GetDlgCtrlID.argtypes = [wintypes.HWND]
_pt30_user32.GetDlgCtrlID.restype = ctypes.c_int
_pt30_user32.IsWindowVisible.argtypes = [wintypes.HWND]
_pt30_user32.IsWindowVisible.restype = wintypes.BOOL
# pt84 (#HRC-HANG-WATCHDOG) — IsHungAppWindow: TRUE se a janela parou de bombear
# mensagens (~5s) = congelada. Usado pelo vigia para detectar HRC frozen (OOM).
_pt30_user32.IsHungAppWindow.argtypes = [wintypes.HWND]
_pt30_user32.IsHungAppWindow.restype = wintypes.BOOL
_pt30_user32.IsWindow.argtypes = [wintypes.HWND]
_pt30_user32.IsWindow.restype = wintypes.BOOL

CB_GETCURSEL = 0x0147   # lê o índice seleccionado (read-back de verificação)
CB_SETCURSEL = 0x014E   # selecciona item por índice
WM_COMMAND = 0x0111
CBN_SELCHANGE = 1       # notificação ao diálogo após mudar a selecção do combo
# Diagnóstico v2 (HRC actual no Beelink): combo de modo tem 4 itens —
#   [0] 'Manual Selection' (default)    [1] 'Complete Export'
#   [2] 'All Strategies, Limited depth' [3] 'Selected Spot, Limited Depth'
# Se uma futura versão do HRC reordenar, re-correr diag_export_hrc.bat e
# actualizar este índice.
EXPORT_MODE_COMPLETE_INDEX = 1

# ── pt61/pt64/pt66 — Scope da 2ª run via Win32 ─────────────────────────────
# O popup Nash (#32770) tem widgets SWT opacos; os cliques pyautogui de
# Scope/opção não registam de forma fiável. O Scope passou a Win32 via a
# SysListView32 do dropdown (pt64, ver bloco abaixo). pt66: o antigo caminho
# Edit/ComboBox do CI/Scope (CB_GETCOUNT/GETLBTEXT/GETLBTEXTLEN + WM_SETTEXT/
# GETTEXT/GETTEXTLENGTH + `_find_combo_with_item` + `_fill_ci_target_in_popup`)
# foi REMOVIDO — o watcher já NÃO escreve o CI (o default do popup é sempre
# 10.0 = o alvo). (CB_SETCURSEL/CB_GETCURSEL ficam — usados pelo
# export_strategies, ver topo.)

# ── pt64 (#HRC-SCOPE-CCOMBO-SWT) — Scope via SysListView32 do dropdown ──────
# Diag pt64 (Beelink, popup Nash 436×230): o controlo Scope é um SWT CCombo —
# canvas opaco SWT_Window0, SEM ComboBox/Edit nativo nem pattern UIA. MAS ao
# abrir cria uma janela top-level nova (#32770, ~250×40) com uma SysListView32
# NATIVA cujos itens são 'Full Tree' (idx 0) e 'Selected Subtree' (idx 1).
# Conduzimo-lo por imitação humana (foco + F4 + setas/typing + Enter) e fazemos
# read-back BARATO via LVM_GETNEXTITEM (int, sem buffer cross-process, sem
# comtypes). Mapa idx→texto (0=Full Tree, 1=Selected Subtree) é a calibração
# pt64; se uma futura versão do HRC reordenar/adicionar itens, re-correr
# diag_nash_popup.py (modo dropdown) e actualizar o índice/gate.
LVM_FIRST = 0x1000
LVM_GETITEMCOUNT = LVM_FIRST + 4    # 0x1004 — nº de itens (int, sem buffer)
LVM_GETNEXTITEM = LVM_FIRST + 12    # 0x100C — devolve índice do item seleccionado
LVNI_SELECTED = 0x0002             # flag p/ LVM_GETNEXTITEM = item seleccionado
SCOPE_LIST_SELECTED_SUBTREE_INDEX = 1   # calibração pt64 (Full Tree=0, Sel.Subtree=1)

_FINISH_WAIT_PHASE1_TIMEOUT_S = 5.0    # aguardar Finish disabled (calc arrancou)
_FINISH_WAIT_PHASE2_TIMEOUT_S = 60.0   # aguardar Finish re-enabled (calc terminou)
_FINISH_WAIT_POLL_S = 0.1

# pt90 (#HRC-TREE-GIGANTE) — abort preventivo de trees gigantes ANTES da 1ª run.
# Stats lidas via OCR read-only do painel "Tree Statistics" (tree_stats.py), logo
# após a Fase 2 do finish-wait (Finish re-enabled = tree size já computado).
TREE_GB_ABORT_LIMIT = 15.0     # GB. Acima disto (com confiança) → .failed.
OCR_REREAD_GAP_S = 0.25        # intervalo entre as 2 leituras OCR de confirmação.


# ---------------------------------------------------------------------------
# pt29 (#PT25D-WATCHER-FRAGILE-CLIPBOARD-OR-RESTORE) — clipboard race fix
#
# Vector observado em smoke real 14 Maio 2026: o Rui usa RDP/sync entre PC
# principal e Beelink. Qualquer Ctrl+C em qualquer dos PCs (incluindo
# comandos PowerShell colados durante arranque) compete com o clipboard que
# o watcher escreveu para o paste no HRC. Janela vulnerável: entre
# SetClipboardData e Ctrl+V. Sintoma: paste chega ao HRC vazio, watcher
# continua silenciosamente, corrida fica corrupta. Mapeado para 40 de 41
# mãos perdidas em 14 Maio.
#
# Mitigação: `clipboard_safe_paste` faz set + read-back imediato. Se
# mismatch, sleep 50ms + retry. Sucesso -> sleep 10ms + Ctrl+V + sanity
# pós-paste. n_retries esgotados -> WARN explícito + raise (failure
# explícito é estritamente melhor que paste silencioso -> corrupção da
# corrida).
#
# Call sites cobertos por este patch: `paste_hh`, `paste_path` (swap dos
# legacy do Baltazar). O `start_calculation` legacy (1ª run, dentro do
# .pyc Baltazar, fora do nosso source-side) também tem o vector mas fica
# como tech debt residual sob #PT25D-WATCHER-FRAGILE-CLIPBOARD-OR-RESTORE
# — a 1ª run tem funcionado consistentemente em produção pelo que o swap
# completo da função não vale o risco.
# ---------------------------------------------------------------------------


def _set_clipboard_with_verify(target_text, n_retries=5):
    """pt28-v3 (#PASTE-FAILED-HRC-REJECTED-CLIPBOARD root cause):
    set + read-back verify do clipboard, SEM Ctrl+V.

    Mesma blindagem que `clipboard_safe_paste` contra o bug CheckedCall
    do pyperclip 1.11.0 (silent fail Win32 com errno=0) e race RDP/sync,
    mas para casos onde o consumer eh outra app (e.g., HRC auto-import
    no abrir do wizard "New Hand"), nao o Ctrl+V do robot.

    Smoke pt28-v2 (20 Maio) provou que o HRC le o clipboard
    automaticamente ao abrir o wizard. Se nesse momento o clipboard
    ainda tem lixo (e.g. comando PowerShell que o Rui colou para
    arrancar o robot), o HRC mostra popup azul "Hand Import: No valid
    hand-history found" e o paste manual subsequente nao recupera
    (foreground passa a ser o popup). Solucao: preparar clipboard com
    HH valido ANTES de chamar `open_wizard()`.

    Sequencia (igual ao set+verify de `clipboard_safe_paste`):
      1. pyperclip.copy(target_text)
      2. pyperclip.paste() -- read-back imediato
      3. Mismatch => sleep 50ms => retry (ate n_retries)
      4. Sucesso => return (caller decide o que fazer com o clipboard)

    n_retries esgotados => RuntimeError com WARN explicito (failure
    explicito > corrupcao silenciosa).
    """
    preview = target_text[:30].replace('\n', ' ').replace('\r', ' ')
    if len(target_text) > 30:
        preview = preview + '...'

    actual = None
    last_error = None
    for attempt in range(1, n_retries + 1):
        try:
            pyperclip.copy(target_text)
        except Exception as _e:
            last_error = _e
            print(f'   [WARN] _set_clipboard_with_verify copy raised ({_e}); '
                  f'attempt {attempt}/{n_retries}')
            time.sleep(0.05)
            continue
        try:
            actual = pyperclip.paste()
        except Exception as _e:
            last_error = _e
            print(f'   [WARN] _set_clipboard_with_verify read-back raised '
                  f'({_e}); attempt {attempt}/{n_retries}')
            actual = None
        if actual == target_text:
            if attempt > 1:
                print(f'   [clipboard] _set_clipboard_with_verify locked after '
                      f'{attempt} attempt(s) (len={len(target_text)}): {preview!r}')
            return
        time.sleep(0.05)

    print(f'   [WARN] _set_clipboard_with_verify: failed to lock clipboard '
          f'after {n_retries} attempts; last actual={actual!r}, '
          f'target={preview!r}, last_error={last_error!r}')
    raise RuntimeError(
        f'clipboard race unresolved after {n_retries} attempts '
        f'(target preview={preview!r})'
    )


def clipboard_safe_paste(target_text, n_retries=5):
    """Set clipboard + verify + Ctrl+V atomicamente, blindando contra a
    race RDP/sync descrita no header desta secção.

    Sequência:
      1. pyperclip.copy(target_text)
      2. pyperclip.paste() — read-back imediato
      3. Mismatch => sleep 50ms => retry (até n_retries)
      4. Sucesso => sleep 10ms => Ctrl+V via pyautogui.hotkey
      5. Sleep 50ms => read-back de sanity (apenas WARN se mudou,
         não raise — o Ctrl+V já aconteceu)

    n_retries esgotados => RuntimeError com WARN explícito. Por design,
    failure explícito > corrupção silenciosa: o caller (e o log) ficam a
    saber que algo correu mal em vez de o HRC processar paste vazio.

    Logging: print do preview (primeiros 30 chars do target) + número de
    tentativas necessárias. Em recuperação (attempt > 1) o log diz
    "locked after N attempt(s)" para facilitar a contagem de races em
    produção.
    """
    preview = target_text[:30].replace('\n', ' ').replace('\r', ' ')
    if len(target_text) > 30:
        preview = preview + '...'

    actual = None
    last_error = None
    for attempt in range(1, n_retries + 1):
        try:
            pyperclip.copy(target_text)
        except Exception as _e:
            last_error = _e
            print(f'   [WARN] clipboard_safe_paste copy raised ({_e}); '
                  f'attempt {attempt}/{n_retries}')
            time.sleep(0.05)
            continue
        try:
            actual = pyperclip.paste()
        except Exception as _e:
            last_error = _e
            print(f'   [WARN] clipboard_safe_paste read-back raised '
                  f'({_e}); attempt {attempt}/{n_retries}')
            actual = None
        if actual == target_text:
            if attempt > 1:
                print(f'   [clipboard] locked after {attempt} attempt(s) '
                      f'(len={len(target_text)}): {preview!r}')
            break
        time.sleep(0.05)
    else:
        print(f'   [WARN] clipboard_safe_paste: failed to lock clipboard '
              f'after {n_retries} attempts; last actual={actual!r}, '
              f'target={preview!r}, last_error={last_error!r}')
        raise RuntimeError(
            f'clipboard race unresolved after {n_retries} attempts '
            f'(target preview={preview!r})'
        )

    time.sleep(0.01)
    pyautogui.hotkey('ctrl', 'v')
    time.sleep(0.05)
    try:
        post = pyperclip.paste()
    except Exception:
        post = None
    if post != target_text:
        print(f'   [WARN] clipboard_safe_paste: clipboard mutated '
              f'post-paste (actual={post!r}, target={preview!r}) — paste '
              f'may have been raced')


# ---------------------------------------------------------------------------
# pt28-v2 (#PASTE-FAILED-HRC-REJECTED-CLIPBOARD) — HRC paste rejection detection
#
# Smoke pt28-v1 (20 Maio 2026) expôs falha grave: robot fez paste_hh + log
# "A colar HH..." normalmente, mas HRC mostrou popup azul:
#   "Hand Import: No valid hand-history found in the Clipboard."
# Robot ignorou-o (provavelmente fechou-o automaticamente com Enter que
# chegou por outra via), continuou a configurar Equity Model / Bounty Mode /
# MTT Stacks / Scripting sobre dados FANTASMA da ultima mao em memoria do
# HRC (4 jogadores, stacks 38801/105180/96368/171654 da mao anterior do
# smoke, em vez dos 8 jogadores da GG-5944816316). 1a corrida arrancou
# sobre essa mao errada.
#
# Causa do Ctrl+V nao chegar ao campo nao isolada (foco fora, race, silent
# fail no pyperclip). Causa raiz fica como tech debt; o que NAO pode
# acontecer e o robot continuar em silencio.
#
# Mitigacao pt28-v2: apos paste_hh, polla 800ms pelo popup "Hand Import".
# Se encontrado:
#   1. log defensivo (clipboard length/preview, foreground window)
#   2. fecha popup via Enter
#   3. retry 1x (re-click TEXT_AREA + select-all + paste)
#   4. se popup persistir: raise RuntimeError("PASTE_FAILED_HRC_REJECTED_CLIPBOARD")
#      -> watcher marca .failed em vez de processar sobre lixo
# ---------------------------------------------------------------------------

_HAND_IMPORT_ERROR_POPUP_TITLE_HINTS = ("Hand Import",)
_HAND_IMPORT_POPUP_WAIT_S = 0.8
_HAND_IMPORT_POPUP_POLL_S = 0.15


def _log_paste_diagnostics(wpos, hh_text, label):
    """pt28-v2: logging defensivo imediatamente antes do Ctrl+V em paste_hh.

    Regista no stdout (a) wpos do main HRC window onde achamos que estamos
    a colar, (b) titulo + hwnd da janela em foreground neste momento (se
    nao for HRC, paste vai para sitio errado), (c) clipboard length +
    preview dos primeiros 80 chars para confirmar que o clipboard tem o
    que esperamos.

    Tolerante a falhas dos getters: cada bloco em try/except devolvendo
    placeholder em vez de propagar; o log nao deve ser uma fonte de
    crashes.
    """
    try:
        active = pyautogui.getActiveWindow()
        if active is not None:
            active_title = getattr(active, 'title', '?') or '?'
            active_hwnd = getattr(active, '_hWnd', None)
            if active_hwnd is None:
                active_hwnd = getattr(active, 'hwnd', '?')
        else:
            active_title = '<none>'
            active_hwnd = '<none>'
    except Exception as _e:
        active_title = f'<err: {_e}>'
        active_hwnd = '?'
    try:
        cb_now = pyperclip.paste()
        cb_len = len(cb_now) if cb_now else 0
        cb_preview = (cb_now[:80].replace('\n', ' ').replace('\r', ' ')
                      if cb_now else '<empty>')
    except Exception as _e:
        cb_len = -1
        cb_preview = f'<err: {_e}>'
    print(f'   [paste-diag {label}] wpos={wpos} '
          f'foreground=hwnd={active_hwnd} title={active_title!r}')
    print(f'   [paste-diag {label}] clipboard len={cb_len} '
          f'expected_len={len(hh_text)} preview={cb_preview!r}')


def _detect_hand_import_error_popup(timeout=_HAND_IMPORT_POPUP_WAIT_S):
    """pt28-v2: deteta o popup "Hand Import: No valid hand-history found"
    que o HRC mostra quando o clipboard nao tem HH parseable no momento
    do paste.

    Polla `pyautogui.getAllWindows()` ate `timeout` segundos por uma
    janela cujo titulo case-insensitive contem qualquer dos hints em
    `_HAND_IMPORT_ERROR_POPUP_TITLE_HINTS`. Mesma estrategia que
    `_wait_for_nash_popup` (provada robusta no flow Scope).

    Robustez:
      - Janelas com title vazio ignoradas (compositor, system).
      - Janelas com width/height <= 0 ignoradas (minimizadas).
      - getAllWindows pode levantar race condition; log WARN + retry.

    Devolve `(left, top, width, height, title)` se encontrou, `None`
    em timeout.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            windows = pyautogui.getAllWindows()
        except Exception as _e:
            print(f'   [WARN] _detect_hand_import_error_popup: '
                  f'getAllWindows falhou ({_e}); retry')
            time.sleep(_HAND_IMPORT_POPUP_POLL_S)
            continue
        # pt28-v3 defensive: alguns mock environments (e.g. smoke harness do
        # swap_and_smoke.py com CallRec) devolvem None de getAllWindows.
        if windows is None:
            time.sleep(_HAND_IMPORT_POPUP_POLL_S)
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
            for hint in _HAND_IMPORT_ERROR_POPUP_TITLE_HINTS:
                if hint.lower() in title_lower:
                    left = getattr(w, 'left', 0) or 0
                    top = getattr(w, 'top', 0) or 0
                    return (left, top, width, height, title)
        time.sleep(_HAND_IMPORT_POPUP_POLL_S)
    return None


def _close_hand_import_error_popup(popup):
    """Fecha o popup "Hand Import" via press Enter (default-button OK em
    dialogos Qt modais). `popup` so e usado para log; nenhuma coord
    necessaria para o Enter global.
    """
    if popup is None:
        return
    print(f'   _close_hand_import_error_popup: closing popup title={popup[4]!r} '
          f'rect=({popup[0]},{popup[1]},{popup[2]},{popup[3]})')
    pyautogui.press('enter')
    time.sleep(0.4)


def _wizard_window_present():
    """pt29 (#WIZARD-FINISH-NO-STATE-CHECK): True se ainda existe janela
    top-level com 'Hand Setup' no titulo (mesmo sinal que open_wizard usa
    para detectar o wizard). Usado como state check pos-click do Finish:
    se o wizard ainda esta presente, o click Finish nao teve efeito.

    getAllWindows falha OU None -> trata como 'nao presente' (return False)
    para nao gerar WARN espurio em erro de enumeracao — o caller so grita
    quando ha certeza de que o wizard persiste.
    """
    try:
        windows = pyautogui.getAllWindows()
    except Exception as _e:
        print(f'   [WARN] _wizard_window_present: getAllWindows falhou ({_e})')
        return False
    if windows is None:
        return False
    for w in windows:
        title = (getattr(w, 'title', '') or '')
        if 'Hand Setup' in title:
            return True
    return False


def _is_enabled(hwnd):
    """pt30: wrapper read-only sobre IsWindowEnabled (instancia WinDLL isolada)."""
    return bool(_pt30_user32.IsWindowEnabled(hwnd))


def _resolve_wizard_hwnd():
    """pt30: hwnd da janela 'Hand Setup' via FindWindowW (match exacto) com
    fallback substring via EnumWindows (titulo pode ter prefixo/sufixo).
    None se nao houver. Auto-contido — nao depende do objecto pygetwindow.
    """
    h = _pt30_user32.FindWindowW(None, "Hand Setup")
    if h:
        return h
    matches = []

    def _enum_top(hwnd, lparam):
        n = _pt30_user32.GetWindowTextLengthW(hwnd)
        if n > 0:
            buf = ctypes.create_unicode_buffer(n + 1)
            _pt30_user32.GetWindowTextW(hwnd, buf, n + 1)
            if "hand setup" in buf.value.lower():
                matches.append(hwnd)
                return False
        return True

    _pt30_user32.EnumWindows(_PT30_WNDENUMPROC(_enum_top), 0)
    return matches[0] if matches else None


def _find_finish_button(hwnd_wizard):
    """pt30: enumera child windows do wizard e devolve o hwnd do botao Finish
    (class 'Button', texto contem 'finish' case-insensitive, ignora o
    accelerator '&'). None se nao encontrar. Read-only.

    Diagnostico SWT pt30 (check_wizard_children_polling) confirmou que o HRC
    usa SWT e expoe os widgets como child windows nativas: o Finish aparece
    como class 'Button', text '&Finish'.
    """
    if not hwnd_wizard:
        return None
    found = []

    def _enum(ch, lparam):
        cls_buf = ctypes.create_unicode_buffer(256)
        _pt30_user32.GetClassNameW(ch, cls_buf, 256)
        if cls_buf.value == "Button":
            n = _pt30_user32.GetWindowTextLengthW(ch)
            if n > 0:
                txt_buf = ctypes.create_unicode_buffer(n + 1)
                _pt30_user32.GetWindowTextW(ch, txt_buf, n + 1)
                if "finish" in txt_buf.value.lower():
                    found.append(ch)
                    return False  # encontrado — para a enumeracao
        return True

    _pt30_user32.EnumChildWindows(hwnd_wizard, _PT30_WNDENUMPROC(_enum), 0)
    return found[0] if found else None


def _merge_meta_json(updates):
    """pt90 — merge defensivo de `updates` no meta.json da mão a decorrer
    (_CURRENT_HAND_PATH). Nunca rebenta o watcher."""
    hp = globals().get('_CURRENT_HAND_PATH')
    if not hp:
        print('   [tree-stats][WARN] sem _CURRENT_HAND_PATH — meta.json nao actualizado')
        return
    mp = os.path.join(hp, 'meta.json')
    try:
        data = {}
        if os.path.exists(mp):
            with open(mp) as f:
                data = json.load(f) or {}
        data.update(updates)
        with open(mp, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        print('   [tree-stats][WARN] meta.json update falhou: %s' % e)


def _capture_tree_stats_safe(hwnd):
    """pt90 — lazy-import + chamada a tree_stats.capture_tree_stats. Fail-open
    TOTAL: qualquer erro (módulo ausente, winsdk, OCR) → ok=False (nunca aborta)."""
    try:
        import tree_stats
        return tree_stats.capture_tree_stats(top_hwnd=hwnd)
    except Exception as e:
        return {"ok": False, "nodes": None, "gb": None,
                "hrc_available_gb": None, "raw": "err:import_or_call:%s" % e}


def _record_tree_stats_and_maybe_abort(hwnd_wizard, build_seconds):
    """pt90 (#HRC-TREE-GIGANTE): lê stats da tree (OCR read-only) e:
      1) regista SEMPRE no meta.json (audit), mesmo com OCR falhado;
      2) ABORTA (raise RuntimeError → main loop marca .failed, EXACTAMENTE como
         a Fase 2 timeout faz hoje) SÓ com CONFIANÇA por DUPLA LEITURA: duas
         leituras seguidas (~OCR_REREAD_GAP_S) têm de ambas ok=True E CONCORDAR
         que a tree está acima do limite (ambas gb>TREE_GB_ABORT_LIMIT OU >available).
      OCR falhado, OU leituras a DISCORDAR (uma over, outra under) → NUNCA aborta
      (instável/suspeita); deixa correr + log + ocr_ok:false.
    build_seconds NÃO é gate (gigantes 2-3s / normais <1s — janela cega); fica só
    registado no meta.json para histórico."""

    def _over(s):
        gb = s.get("gb")
        if gb is None:
            return False
        avail = s.get("hrc_available_gb")
        return gb > TREE_GB_ABORT_LIMIT or (avail is not None and gb > avail)

    read1 = _capture_tree_stats_safe(hwnd_wizard)
    time.sleep(OCR_REREAD_GAP_S)
    read2 = _capture_tree_stats_safe(hwnd_wizard)

    over1, over2 = _over(read1), _over(read2)
    both_ok = bool(read1.get("ok")) and bool(read2.get("ok"))
    confident = both_ok and (over1 == over2)        # ambas ok E concordam na classificação

    # meta.json: valores da leitura ok (read1 preferida); ocr_ok = leitura confiável.
    primary = read1 if read1.get("ok") else (read2 if read2.get("ok") else read1)
    _merge_meta_json({
        "tree_nodes": primary.get("nodes"),
        "tree_size_gb": primary.get("gb"),
        "hrc_available_gb": primary.get("hrc_available_gb"),
        "build_seconds": round(build_seconds, 1),
        "ocr_ok": confident,
    })
    print('   [tree-stats] r1(ok=%s gb=%s avail=%s) r2(ok=%s gb=%s) '
          'build=%.1fs over=(%s,%s) confident=%s'
          % (read1.get("ok"), read1.get("gb"), read1.get("hrc_available_gb"),
             read2.get("ok"), read2.get("gb"), build_seconds, over1, over2, confident))

    if not both_ok:
        print('   [tree-stats] OCR falhado/ambiguo numa das leituras '
              '(r1=%r / r2=%r) — NAO aborta, deixa correr'
              % (read1.get("raw"), read2.get("raw")))
        return
    if over1 != over2:
        print('   [tree-stats] leituras DISCORDAM (over1=%s gb1=%s | over2=%s gb2=%s) '
              '— instavel, NAO aborta'
              % (over1, read1.get("gb"), over2, read2.get("gb")))
        return
    if not (over1 and over2):
        return                                       # ambas under → corre normal

    # ambas ok E concordam que está ACIMA → abort com confiança.
    gb1, gb2 = read1.get("gb"), read2.get("gb")
    avail = read1.get("hrc_available_gb")
    over_limit = gb1 is not None and gb1 > TREE_GB_ABORT_LIMIT
    why = ('> %.1f GB' % TREE_GB_ABORT_LIMIT) if over_limit \
          else ('> %.1f GB disponiveis' % (avail if avail is not None else -1.0))
    raise RuntimeError(
        'tree gigante: %.1f/%.1f GB %s (nodes=%s, build=%.0fs, dupla leitura) '
        '— abort antes da 1a run'
        % (gb1, gb2, why, read1.get("nodes"), build_seconds))


def _wait_for_finish_ready(hwnd_wizard):
    """pt30 (#WIZARD-FINISH-DISABLED-DURING-TREE-CALC): aguarda a transicao
    enabled->disabled->enabled do botao Finish, para confirmar que o HRC
    reagiu ao paste do script (arrancou o calculo do tree size) e que o
    calculo terminou — antes do slow-click.

    Fase 1 (timeout 5s): pollar ate Finish DISABLED — confirma que o calc
      arrancou. Timeout = calc provavelmente instantaneo (tree=0) ou botao
      nao encontrado; WARN e continua (nao bloqueia).
    Fase 2 (timeout 60s): pollar ate Finish ENABLED — confirma fim do calc.
      Timeout = calc preso; raise RuntimeError (melhor parar a mao do que
      clicar num Finish disabled).

    Defensivo: botao Finish nao encontrado -> WARN e devolve sem bloquear
    (cai no comportamento legado, slow-click cego com os sleeps existentes).
    """
    btn = _find_finish_button(hwnd_wizard)
    if not btn:
        print('   [WARN] [finish-wait] botao Finish nao encontrado via Win32 '
              '(hwnd_wizard=%r); polling saltado, slow-click segue cego'
              % (hwnd_wizard,))
        return

    deadline = time.time() + _FINISH_WAIT_PHASE1_TIMEOUT_S
    saw_disabled = False
    while time.time() < deadline:
        if not _is_enabled(btn):
            saw_disabled = True
            break
        _watchdog_sleep(_FINISH_WAIT_POLL_S)   # pt84 — vigia (OOM/hung) no Hand Setup
    if not saw_disabled:
        print('   [WARN] [finish-wait] Finish nunca ficou disabled em %.0fs — '
              'calculo provavelmente instantaneo (tree=0); a continuar'
              % _FINISH_WAIT_PHASE1_TIMEOUT_S)
        return
    print('   [finish-wait] calculo do tree size comecou (Finish disabled)')

    f2_start = time.time()
    deadline = f2_start + _FINISH_WAIT_PHASE2_TIMEOUT_S
    while time.time() < deadline:
        if _is_enabled(btn):
            build_seconds = time.time() - f2_start
            print('   [finish-wait] tree estavel em %.1fs (Finish enabled)'
                  % build_seconds)
            # pt90 (#HRC-TREE-GIGANTE): tree size já computado, ANTES da 1ª run →
            # regista stats + abort preventivo (dupla leitura). Pode raise →
            # .failed (mesmo caminho que a Fase 2 timeout abaixo).
            _record_tree_stats_and_maybe_abort(hwnd_wizard, build_seconds)
            return
        _watchdog_sleep(_FINISH_WAIT_POLL_S)   # pt84 — vigia (OOM/hung) no build da árvore
    raise RuntimeError(
        'WIZARD_FINISH_NEVER_RE_ENABLED: calculo do tree size nao terminou '
        'em %.0fs (Finish ficou disabled)' % _FINISH_WAIT_PHASE2_TIMEOUT_S
    )


_RUN_WAIT_POLL_S = 0.5
_RUN_WAIT_PROGRESS_LOG_S = 60.0
# pt67 (#HRC-RUN-WINDOW-DETECTION-BLIND): grace de ARRANQUE. Se a janela de
# progresso nunca for vista durante este tempo de ecrã limpo, a run foi muito
# curta (terminou entre polls) ou não arrancou — a navegação seguinte confirma.
# É o ÚNICO parâmetro de tempo e NÃO decide a duração da run; calibrável na
# re-smoke (logging incluído).
_RUN_WAIT_GRACE_CLEAN_S = 30.0


def _find_progress_window_title(match_substring=None):
    """pt34/pt66: devolve o titulo COMPLETO da janela de progresso do HRC, ou
    None se nao existir.

    - `match_substring=None` -> match exacto "Hand Setup" via FindWindowW
      (comportamento pt31 legado).
    - `match_substring` str -> substring case-insensitive sobre os titulos
      top-level via EnumWindows (2a run: "H-<hand_id>: Monte Carlo Sampling").
    - `match_substring` tuple/list de str -> QUALQUER um dos substrings (pt66):
      a 1a run pode mostrar "Hand Setup" OU "Monte Carlo Sampling"; passar os
      dois torna o run-wait robusto ao titulo exacto (que varia entre
      runs/versoes do HRC) -> deixa de declarar "trivial" por nao reconhecer.

    Devolve o titulo (str) em vez de bool para logging diagnostico (o titulo
    pode mudar entre versoes do HRC).
    """
    if match_substring is None:
        if _pt30_user32.FindWindowW(None, "Hand Setup"):
            return "Hand Setup"
        return None
    needles = ((match_substring,) if isinstance(match_substring, str)
               else tuple(match_substring))
    needles = tuple(s.lower() for s in needles)
    found = []

    def _enum_top(hwnd, lparam):
        n = _pt30_user32.GetWindowTextLengthW(hwnd)
        if n > 0:
            buf = ctypes.create_unicode_buffer(n + 1)
            _pt30_user32.GetWindowTextW(hwnd, buf, n + 1)
            low = buf.value.lower()
            if any(nd in low for nd in needles):
                found.append(buf.value)
                return False  # encontrado — para a enumeracao
        return True

    _pt30_user32.EnumWindows(_PT30_WNDENUMPROC(_enum_top), 0)
    return found[0] if found else None


def _find_progress_window_hwnd(match_substring=None):
    """pt67: HWND da 1ª janela top-level de progresso cujo título casa, ou None.

    Igual a `_find_progress_window_title` mas devolve o HWND (para tracking).
    `match_substring`: None -> 'Hand Setup' exacto (FindWindowW); str -> substring;
    tuple -> qualquer-um (EnumWindows). Tracking por hwnd é robusto ao morph
    wizard→run (que mantém o mesmo título).
    """
    if match_substring is None:
        h = _pt30_user32.FindWindowW(None, "Hand Setup")
        return h or None
    needles = ((match_substring,) if isinstance(match_substring, str)
               else tuple(match_substring))
    needles = tuple(s.lower() for s in needles)
    found = []

    def _enum_top(hwnd, lparam):
        n = _pt30_user32.GetWindowTextLengthW(hwnd)
        if n > 0:
            buf = ctypes.create_unicode_buffer(n + 1)
            _pt30_user32.GetWindowTextW(hwnd, buf, n + 1)
            if any(nd in buf.value.lower() for nd in needles):
                found.append(hwnd)
                return False
        return True

    _pt30_user32.EnumWindows(_PT30_WNDENUMPROC(_enum_top), 0)
    return found[0] if found else None


def _wait_for_run_completion(timeout_total_s=7200, run_label="run",
                             match_substring=None,
                             grace_clean_s=_RUN_WAIT_GRACE_CLEAN_S):
    """pt67 (#HRC-RUN-WINDOW-DETECTION-BLIND): vigia a janela de progresso do HRC
    **DESDE a chamada** (o caller já NÃO faz sleep cego). Invariante (Rui):
    corrida a decorrer ⇔ janela de progresso no ecrã.

    Fase A (captar): poll 0.5s à procura da janela; capta o **HWND** quando a vê.
      Se NUNCA aparecer durante `grace_clean_s` consecutivos de ecrã limpo → a
      run foi muito curta (terminou entre polls) OU não arrancou; loga e devolve
      (fail-open; a navegação seguinte confirma o 2º caso).
    Fase B (esperar fim): espera o HWND captado desaparecer. "Desapareceu" =
      `IsWindow(hwnd)` falso **E** não há já nenhuma janela de progresso pelo
      título (defesa contra morph para um hwnd novo). Log minuto-a-minuto.
      Timeout total → RuntimeError (backstop; a mão falha e a fila avança).

    pt66 → pt67: o run-wait antigo assumia o wizard fechado + um sleep(30) cego
    antes da chamada → engolia runs curtas (~5s): a janela aparecia e morria
    durante o sleep e a fase 1 declarava "nunca apareceu". Agora vigia desde o
    Finish. O título "Hand Setup" da 1ª run mantém-se do início ao fim (morfa da
    config para a run sem fechar) — por isso o tracking é por hwnd.

    ⚠️ `grace_clean_s` é o ÚNICO parâmetro de tempo e é só um GRACE de arranque —
    NÃO decide a duração da run. Sem heurísticas de desempenho/memória.
    ⚠️ NUNCA marcar "Always run in background" no HRC — esconde as janelas e cega
    este polling (runbook §2.7).

    `match_substring`: tuple ("Hand Setup","Monte Carlo Sampling") p/ a 1ª run;
    str "Monte Carlo Sampling" p/ a 2ª.
    """
    # Fase A — captar a janela (vigia desde já).
    a_start = time.time()
    hwnd = None
    while time.time() - a_start < grace_clean_s:
        hwnd = _find_progress_window_hwnd(match_substring)
        if hwnd:
            break
        _watchdog_sleep(_RUN_WAIT_POLL_S)   # pt84 — vigia (OOM/hung) durante o grace
    if not hwnd:
        print('   [run-wait] %s: janela de progresso NUNCA vista em %.0fs de ecrã '
              'limpo — run muito curta (terminou entre polls) ou não arrancou; a '
              'continuar (a navegação confirma).' % (run_label, grace_clean_s))
        return
    print('   [run-wait] %s: janela detectada (hwnd=%d) — a aguardar fim...'
          % (run_label, hwnd))

    # Fase B — esperar o hwnd captado desaparecer (run terminou).
    b_start = time.time()
    deadline = b_start + timeout_total_s
    next_log = b_start + _RUN_WAIT_PROGRESS_LOG_S
    while time.time() < deadline:
        gone = (not _pt30_user32.IsWindow(hwnd)
                and _find_progress_window_hwnd(match_substring) is None)
        if gone:
            elapsed = time.time() - b_start
            print('   [run-wait] %s: run terminou em %.0fs (%.1f min)'
                  % (run_label, elapsed, elapsed / 60.0))
            return
        now = time.time()
        if now >= next_log:
            print('   [run-wait] %s: ainda a correr ha %d minutos'
                  % (run_label, int((now - b_start) / 60.0)))
            next_log = now + _RUN_WAIT_PROGRESS_LOG_S
        _watchdog_sleep(_RUN_WAIT_POLL_S)   # pt84 — vigia (OOM/hung) durante a run
    raise RuntimeError(
        'RUN_NEVER_COMPLETED: %s nao terminou em %ds'
        % (run_label, timeout_total_s)
    )


# pt66/pt67 — salvaguarda SÓ-LEITURA do CI (o watcher já não escreve o CI).
# pt67: WM_GETTEXT/WM_GETTEXTLENGTH re-adicionados (removidos em pt66 com o Edit
# do CI) para ler CHILD CONTROLS — o "Target CI" vive num label interior.
WM_GETTEXT = 0x000D
WM_GETTEXTLENGTH = 0x000E
_CI_READBACK_TIMEOUT_S = 20.0
_CI_TARGET_RE = re.compile(r'Target\s*CI\s*[<:=]?\s*([0-9]+(?:\.[0-9]+)?)', re.I)


def _read_hwnd_text(hwnd):
    """pt67: texto de uma janela/controlo via WM_GETTEXT. '' se vazio/erro."""
    if not hwnd:
        return ""
    n = _pt30_user32.SendMessageW(hwnd, WM_GETTEXTLENGTH, 0, 0)
    n = n if isinstance(n, int) and n > 0 else 0
    if n == 0:
        return ""
    buf = ctypes.create_unicode_buffer(n + 1)
    _pt30_user32.SendMessageW(hwnd, WM_GETTEXT, n + 1, ctypes.addressof(buf))
    return buf.value


def _scan_target_ci_in_window(hwnd):
    """pt67 (#HRC-CI-SAFEGUARD-CHILD-CONTROLS): procura "Target CI < X" no título
    E nos CHILD CONTROLS (labels interiores) de `hwnd`. Devolve o float X ou None.

    Diagnóstico pt66: o "MC-CFR [Target CI < 10.00]" vive num **label INTERIOR**
    do dialog de progresso, NÃO no título — por isso enumeramos os filhos."""
    texts = [_read_hwnd_text(hwnd)]  # o próprio título/texto da janela

    def _enum_child(child, lparam):
        texts.append(_read_hwnd_text(child))
        return True

    try:
        _pt30_user32.EnumChildWindows(hwnd, _PT30_WNDENUMPROC(_enum_child), 0)
    except Exception:
        pass
    for t in texts:
        if not t:
            continue
        m = _CI_TARGET_RE.search(t)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                return None
    return None


def _ci_target_readback_warn(expected_ci=10.0):
    """pt66/pt67: SALVAGUARDA SÓ-LEITURA do CI. O watcher já NÃO escreve o CI (o
    default do popup Nash é sempre 10.0 = o alvo). Lê o "Target CI" da janela de
    progresso da run (Monte Carlo) — pt67: pelos **child controls** (label
    interior), não só pelo título — e emite WARN FORTE se ≠ `expected_ci`. Pura
    detecção, ZERO interação.

    Protege contra o default sticky do HRC mudado à mão. **Fail-safe:** se não
    achar o "Target CI" (formato diferente / janela ausente), NÃO alarma. Regra
    operacional: ninguém altera o CI à mão no HRC do Beelink (runbook §2.6).
    """
    deadline = time.time() + _CI_READBACK_TIMEOUT_S
    while time.time() < deadline:
        hwnd = _find_progress_window_hwnd(("Monte Carlo", "MC-CFR", "Hand Setup"))
        if hwnd:
            got = _scan_target_ci_in_window(hwnd)
            if got is not None:
                if abs(got - float(expected_ci)) > 1e-6:
                    print('   [WARN] [ci] Target CI lido = %s (esperado %s)! O '
                          'default do HRC pode ter sido mudado à mão — REPOR %s '
                          'no popup Nash.' % (got, expected_ci, expected_ci))
                else:
                    print('   [ci] Target CI = %s confirmado por leitura '
                          '(child controls; sem escrita)' % got)
                return
        time.sleep(_RUN_WAIT_POLL_S)
    # "Target CI" não lido no tempo -> fail-safe, sem alarme.
    print('   [ci] (salvaguarda) "Target CI" não lido em %ds — sem verificação '
          '(fail-safe, sem alarme)' % int(_CI_READBACK_TIMEOUT_S))


def _do_paste_hh_attempt(wpos, hh_text, label):
    """Helper interno: 1 tentativa completa de paste do HH no TEXT_AREA.
    Extraido para permitir retry limpo em `paste_hh` sem duplicar logica.

    Sequencia: 3-click no TEXT_AREA (focus) -> Ctrl+A via send_key Win32
    (select-all do que la estiver) -> log diagnostico -> clipboard_safe_paste.
    """
    pyautogui.click(wpos[0] + TEXT_AREA[0], wpos[1] + TEXT_AREA[1], clicks=3)
    time.sleep(1)
    send_key(VK_CONTROL, True)
    time.sleep(0.05)
    send_key(VK_A, True)
    time.sleep(0.05)
    send_key(VK_A, False)
    time.sleep(0.05)
    send_key(VK_CONTROL, False)
    time.sleep(0.5)
    _log_paste_diagnostics(wpos, hh_text, label)
    clipboard_safe_paste(hh_text)
    time.sleep(2)


def paste_hh(wpos, hh_text):
    """Cola a hand history no `TEXT_AREA` do wizard HRC.

    pt29 swap do legacy Baltazar: trocado o pyperclip.copy + send_key Ctrl+V
    por `clipboard_safe_paste`. Restante sequencia (3-click para focus,
    select-all via send_key Win32) preservada -- esses passos sao
    independentes do vector clipboard race.

    pt28-v2 (#PASTE-FAILED-HRC-REJECTED-CLIPBOARD): apos o paste verifica
    se HRC mostrou o popup azul "Hand Import: No valid hand-history found".
    Se sim, fecha + retry 1x. Se 2a tentativa tambem dispara popup:
    raise RuntimeError("PASTE_FAILED_HRC_REJECTED_CLIPBOARD") para o
    watcher marcar a mao como .failed em vez de processar sobre dados
    fantasma. Logging defensivo em cada tentativa regista wpos, foreground
    window, e clipboard preview para diagnostico no smoke seguinte.
    """
    _do_paste_hh_attempt(wpos, hh_text, label='attempt-1')

    popup = _detect_hand_import_error_popup()
    if popup is None:
        return  # OK, paste aceite pelo HRC

    print(f'   [WARN] paste_hh: HRC rejected clipboard -- popup detected '
          f'title={popup[4]!r}. Retrying once.')
    _close_hand_import_error_popup(popup)

    _do_paste_hh_attempt(wpos, hh_text, label='attempt-2-retry')

    popup2 = _detect_hand_import_error_popup()
    if popup2 is None:
        print('   paste_hh: retry succeeded -- clipboard accepted on attempt 2')
        return

    print(f'   [ERROR] paste_hh: HRC rejected clipboard on retry too -- '
          f'popup={popup2[4]!r}. Raising loud to prevent processing fantasma data.')
    _close_hand_import_error_popup(popup2)
    raise RuntimeError('PASTE_FAILED_HRC_REJECTED_CLIPBOARD')


def paste_path(path):
    """Type file path into Open/Save dialog.

    pt29 swap do legacy Baltazar: trocado o pyperclip.copy + hotkey por
    `clipboard_safe_paste`. Restante (sleep inicial + press Enter final)
    preservado.
    """
    time.sleep(1)
    clipboard_safe_paste(path)
    time.sleep(1)
    pyautogui.press('enter')
    time.sleep(2)


def set_equity_model(wpos, equity_model):
    """Seleciona o Equity Model no HRC via typeahead no campo dropdown.

    pt23 fix Bug A: aceita identificadores estáveis do backend
    (poker-app `services/queue_export.py`) em vez do `stage` ('FT'/'MTT') do
    meta.json. O dropdown HRC tem 4 entradas (validado por Rui via foto):
    ChipEV in Big Blinds / Malmuth-Harville 'ICM' / Future Game Simulation
    'FGS' / Multi Table (MTSNG/MTT) 'ICM'. Apenas 2 são usadas pelo nosso
    pipeline; FGS fica fora do scope pt23.

    Valores aceites:
      - 'malmuth_harville_icm' -> typeahead 'ma' -> Malmuth-Harville ICM
      - 'multi_table_icm'      -> typeahead 'mu' -> Multi Table ICM (default p/ mid-MTT)
      - outro                  -> fallback Multi Table ICM + print WARN
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
    # pt67 (#WATCHER-PLAYER-COUNT-SPACE-NICKS): `.+?` (lazy) em vez de `\S+` —
    # o `\S+` saltava nicks com espaços (nomes reais GG, ex.: "Andrii Novak") →
    # "In hand: 4" numa mão de 8. Alinha com o `_SEAT_ALL_RE` (`.+?`) do backend.
    seats = re.findall(r'^Seat \d+: .+? \(\d+ in chips', pre_summary, re.MULTILINE)
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


# pt66 — set do CI Target no main UI REMOVIDO. As funções `set_ci_target_initial`
# / `set_ci_target_refine` / `_set_ci_target_common` + as coords
# `CI_TARGET_FIELD_*` eram do flow Bloco 2 (nunca calibradas, coords 0 →
# no-op). Já não há lugar para elas: a 1ª run é lançada pelo Finish (sem set CI
# no main UI) e a 2ª run usa o CI default do popup Nash, que é SEMPRE 10.0 (= o
# alvo) — o watcher deixou de escrever o CI (ver `start_calculation_selected_subtree`
# e a regra operacional "ninguém altera o CI à mão no Beelink" no runbook).


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
# ⚠️ pt61/pt64: estes pixels-rel do Scope são apenas BASELINE/FALLBACK. O
# caminho activo do Scope é Win32 (foco + F4 + SysListView32 do dropdown +
# read-back LVM, pt64), que NÃO depende de coords. A calibração pt61 (popup
# 436×230) mostrou que mesmo com as coords certas o clique pyautogui não
# selecciona neste popup → o fix real é o método, não a coord. Estes valores
# ficam só para o foco-click inicial do Scope.
#
# Calibração pt61 (Rui, Beelink, popup Nash 436×230):
#   - Dropdown Scope: rel (308, 69)        [era (278, 67) @416×214]
#   - "Selected Subtree" opção: rel (290, 107)  [era (274, 108)]
#   - CI Target: rel (297, 108)            [era (270, 109)]
# Defensive return: se algum REL for 0 OU se `popup_rect` for None.
SCOPE_DROPDOWN_REL_X = 308
SCOPE_DROPDOWN_REL_Y = 69
SCOPE_OPTION_SELECTED_SUBTREE_REL_X = 290
SCOPE_OPTION_SELECTED_SUBTREE_REL_Y = 107

# pt66: CI_TARGET_POPUP_REL_* removido — o watcher já não escreve o CI no popup
# (default = 10.0); ver `start_calculation_selected_subtree`.


# pt61 — Strategy Table (janela PRINCIPAL do HRC, não o popup): nó-raiz (offset 0)
# + pitch entre linhas, para o clique de foco/início do navigate. Calibração pt61
# (Rui, MAIN rel): 1º nó (HJ R2.0) @ (221, 131); alvo (SB R4.5, 8º nó) @ (222, 262)
# → pitch = (262−131)/7 = 18.71 px/linha. Direct-click do alvo: (222, 131+off×pitch).
STRATEGY_TABLE_ROOT_REL_X = 221
STRATEGY_TABLE_ROOT_REL_Y = 131
STRATEGY_TABLE_ROW_PITCH_PX = 18.71
# Método do navigate: False = foco-no-raiz + setas×offset (primário, independente
# de geometria); True = direct-click no alvo (reserva, se as setas falharem na
# re-smoke). Flag para o Rui alternar ao vivo sem rebuild.
_NAV_USE_DIRECT_CLICK = False


# pt26 Bloco 2 piece 2 — Botão verde Calculate (Play) no main UI HRC.
# Calibrado em smoke 2026-05-19 com Rui no Beelink: posição absoluta
# (487, 124), main HRC window (left=283, top=65, w=1050, h=850) -> rel
# (204, 64). Convenção: pixels relativos à **janela principal do HRC**
# (a que `find_hrc()` devolve), mesma origem que a 1ª run do Baltazar OG.
#
# pt32 v1: Y 59 -> 64 (a 1ª run usa hrc.top+64 e funciona; a 2ª usava 59).
# pt32 v2: a ORIGEM passa a ser `find_hrc()`, não `wpos`. Smoke pt32 v1
# provou que `wpos` aqui era a geometria do wizard "Hand Setup" (já fechado
# no Finish da 1ª run): log coord=(1174,64) com wpos=(970,0,...) -> 1174=
# 970+204, click em zona vazia, popup Nash nunca abria
# (#START-CALC-SELECTED-SUBTREE-NO-POPUP-OPEN). Estes offsets são relativos
# ao hrc.left/hrc.top de `find_hrc()`, idêntico ao `start_calculation` OG.
CALCULATE_BUTTON_X = 204
CALCULATE_BUTTON_Y = 64


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
      - Falhas ao chamar getAllWindows -> log WARN e tenta de novo na
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
        _watchdog_sleep(poll_interval)   # pt85 B — vigia (OOM/hung) na espera do popup Nash
    print(f'   [WARN] _wait_for_nash_popup: timeout {timeout}s — '
          'popup não detectado')
    return None


def _click_calculate_button(wpos=None):
    """Click no botão verde Calculate (Play) no main UI HRC.

    pt32 v2 (#START-CALC-SELECTED-SUBTREE-NO-POPUP-OPEN): a origem das coords
    passa a ser `find_hrc()` (janela principal do HRC), NÃO `wpos`. Smoke
    pt32 v1 no Beelink provou empiricamente que `wpos` aqui era a geometria
    do wizard "Hand Setup" — que já FECHOU no Finish da 1ª run — logo o click
    caía em zona vazia (log: coord=(1174,64) com wpos=(970,0,...): 1174=
    970+204; foreground era o HRC certo, mas o ponto não era o Play). A 1ª
    run do Baltazar OG (`start_calculation`) usa
    `pyautogui.click(hrc.left+204, hrc.top+64)` via `find_hrc()` e funciona —
    esta função alinha-se com esse padrão. Offsets relativos a hrc.left/top.

    `wpos` mantém-se na assinatura (caller `start_calculation_selected_subtree`
    inalterado) mas é IGNORADO em pt32 v2.

    pt32 v1: logging [calc-diag pre-click] (coord absoluta + foreground), agora
    (v2) também a janela HRC encontrada (hrc_window), para diagnóstico futuro.

    Defensive:
      - CALCULATE_BUTTON_X/Y ambos 0 (regressão de calibração) -> WARN +
        early-return (ANTES do find_hrc, p/ o teste de placeholder).
      - find_hrc() devolve None -> WARN + raise (não no-op silencioso:
        queremos saber se a janela principal do HRC desapareceu).
    """
    if CALCULATE_BUTTON_X == 0 and CALCULATE_BUTTON_Y == 0:
        print('   [WARN] _click_calculate_button: coords não calibrados '
              '— click ignorado')
        return
    hrc = find_hrc()
    if not hrc:
        print('   [WARN] _click_calculate_button: find_hrc() devolveu None '
              '— janela principal do HRC não encontrada; click abortado')
        raise RuntimeError('HRC_MAIN_WINDOW_NOT_FOUND')
    abs_x = hrc.left + CALCULATE_BUTTON_X
    abs_y = hrc.top + CALCULATE_BUTTON_Y
    try:
        fg = _pt30_user32.GetForegroundWindow()
        n = _pt30_user32.GetWindowTextLengthW(fg)
        if n > 0:
            buf = ctypes.create_unicode_buffer(n + 1)
            _pt30_user32.GetWindowTextW(fg, buf, n + 1)
            fg_title = buf.value
        else:
            fg_title = ''
        fg_info = 'hwnd=%s title=%r' % (fg, fg_title)
    except Exception as _e:
        fg_info = 'GetForegroundWindow falhou (%s)' % (_e,)
    print('   [calc-diag pre-click] coord=(%d,%d) hrc_window=(%d,%d,%d,%d) '
          'foreground=%s'
          % (abs_x, abs_y, hrc.left, hrc.top, hrc.width, hrc.height, fg_info))
    pyautogui.click(abs_x, abs_y)
    time.sleep(0.3)


# pt66: `_fill_ci_target_in_popup` REMOVIDO — o watcher já NÃO escreve o CI no
# popup Nash. O default do popup é sempre 10.0 (= o alvo), por isso escrever era
# uma interação a mais (e o campo é um Caso-3 SWT sem Edit nativo → o read-back
# Win32 nunca confirmava). A salvaguarda passou a ser SÓ-LEITURA: ver
# `_ci_target_readback_warn` (lê o "Target CI" da janela de progresso e avisa se
# ≠ 10). Regra operacional: ninguém altera o CI à mão no HRC do Beelink.


def _find_nash_popup_hwnd():
    """pt33 v1: hwnd do popup Nash via FindWindowW (match exacto) com fallback
    substring via EnumWindows (mesma detecção que `_wait_for_nash_popup`, mas
    devolve o hwnd em vez do rect). None se não houver. Auto-contido.

    Snapshot Win32 pt33 (check_nash_popup_children) confirmou que o popup é um
    dialog #32770 top-level com os widgets expostos como child windows nativas
    (Button OK incluído), à imagem do wizard "Hand Setup" descoberto em pt30.
    """
    h = _pt30_user32.FindWindowW(None, "Nash Calculation")
    if h:
        return h
    matches = []

    def _enum_top(hwnd, lparam):
        n = _pt30_user32.GetWindowTextLengthW(hwnd)
        if n > 0:
            buf = ctypes.create_unicode_buffer(n + 1)
            _pt30_user32.GetWindowTextW(hwnd, buf, n + 1)
            if "nash calculation" in buf.value.lower():
                matches.append(hwnd)
                return False
        return True

    _pt30_user32.EnumWindows(_PT30_WNDENUMPROC(_enum_top), 0)
    return matches[0] if matches else None


def _find_ok_button(hwnd_popup):
    """pt33 v1: enumera child windows do popup Nash e devolve o hwnd do Button
    OK (class 'Button', texto normalizado == 'ok', ignora accelerator '&').
    None se não encontrar. Read-only. Mesma anatomia que `_find_finish_button`.

    Snapshot pt33 mostrou o Button OK como class='Button' text='OK'. Match
    exacto (normalizado) evita colidir com 'Cancel' ou outros botões.
    """
    if not hwnd_popup:
        return None
    found = []

    def _enum(ch, lparam):
        cls_buf = ctypes.create_unicode_buffer(256)
        _pt30_user32.GetClassNameW(ch, cls_buf, 256)
        if cls_buf.value == "Button":
            n = _pt30_user32.GetWindowTextLengthW(ch)
            if n > 0:
                txt_buf = ctypes.create_unicode_buffer(n + 1)
                _pt30_user32.GetWindowTextW(ch, txt_buf, n + 1)
                if txt_buf.value.replace("&", "").strip().lower() == "ok":
                    found.append(ch)
                    return False  # encontrado — para a enumeração
        return True

    _pt30_user32.EnumChildWindows(hwnd_popup, _PT30_WNDENUMPROC(_enum), 0)
    return found[0] if found else None


def _click_ok_in_popup(popup_rect=None):
    """Confirma o popup Nash.

    pt33 v1 (#START-CALC-SELECTED-SUBTREE-OK-CLICK-FAILS): substitui o
    `pyautogui.press('enter')` por enumeração Win32 + BM_CLICK no hwnd do
    Button OK. Smoke pt32 v2 mostrou que o popup abre e os cliques intra-popup
    (scope, option Selected Subtree, field CI + escrita) funcionam, mas o OK
    por Enter NÃO é registado pelo HRC (Tab/Enter não funcionam no popup) ->
    popup fica aberto e parado, 2ª run não dispara. BM_CLICK directo no hwnd é
    determinístico (sem coord, sem foco), análogo ao Save btn do export.

    `popup_rect` aceito por consistência de assinatura com o resto do flow;
    não usado (o hwnd é resolvido via `_find_nash_popup_hwnd`).

    Defensive: popup hwnd ou Button OK não encontrados -> WARN, sem fallback
    (failure explícito > Enter silencioso, que já provou não funcionar).
    """
    hwnd_popup = _find_nash_popup_hwnd()
    if not hwnd_popup:
        print('   [WARN] [ok-click] popup Nash hwnd não encontrado '
              '— OK não clicado')
        return
    btn = _find_ok_button(hwnd_popup)
    if not btn:
        print('   [WARN] [ok-click] Button OK não encontrado no popup '
              '(hwnd_popup=%r) — OK não clicado' % (hwnd_popup,))
        return
    _pt30_user32.SendMessageW(btn, BM_CLICK, 0, 0)
    print('   [ok-click] hwnd=%d result=BM_CLICK_sent' % btn)
    time.sleep(0.3)


def _cancel_nash_popup():
    """pt61: fecha o popup Nash SEM disparar a run (Cancel via BM_CLICK). Usado
    no ABORT quando o Scope não confirma — evita deixar o popup aberto a pendurar
    a mão seguinte. Reusa `_find_export_button` (acha Button por label normalizado).
    Best-effort: se não houver Cancel, WARN (a mão já vai marcada falhada)."""
    hwnd_popup = _find_nash_popup_hwnd()
    if not hwnd_popup:
        print('   [WARN] [cancel] popup Nash hwnd não encontrado')
        return
    btn = _find_export_button(hwnd_popup, "cancel")
    if not btn:
        print('   [WARN] [cancel] Button Cancel não encontrado '
              '— popup pode ficar aberto')
        return
    _pt30_user32.SendMessageW(btn, BM_CLICK, 0, 0)
    print('   [cancel] popup Nash cancelado (BM_CLICK hwnd=%d)' % btn)
    time.sleep(0.3)


# pt66: `_find_combo_with_item` (CB_* do Scope — caminho morto desde o pt64
# SysListView32), `_find_single_edit` e `_read_edit_text` (Edit do CI) REMOVIDOS
# — o Scope usa a SysListView32 do dropdown e o CI já não é escrito.


def _find_scope_dropdown_listview():
    """pt64: hwnd da `SysListView32` do dropdown do CCombo do Scope, ou None.

    Quando o Scope abre, nasce uma janela top-level NOVA (#32770) que contém uma
    SysListView32 nativa (diag pt64). O popup Nash (também #32770) NÃO tem
    SysListView32, por isso "a janela top-level que contém uma SysListView32" é
    inequivocamente o dropdown. Read-only. None se o dropdown não estiver aberto.
    """
    found = [None]

    def _enum_lv(ch, lparam):
        cls_buf = ctypes.create_unicode_buffer(256)
        _pt30_user32.GetClassNameW(ch, cls_buf, 256)
        if cls_buf.value == "SysListView32":
            found[0] = ch
            return False
        return True

    def _enum_top(hwnd, lparam):
        if not _pt30_user32.IsWindowVisible(hwnd):
            return True
        cls_buf = ctypes.create_unicode_buffer(256)
        _pt30_user32.GetClassNameW(hwnd, cls_buf, 256)
        if cls_buf.value == "#32770":
            _pt30_user32.EnumChildWindows(hwnd, _PT30_WNDENUMPROC(_enum_lv), 0)
            if found[0] is not None:
                return False  # achámos a listview do dropdown — para
        return True

    _pt30_user32.EnumWindows(_PT30_WNDENUMPROC(_enum_top), 0)
    return found[0]


def _lv_item_count(hwnd_lv):
    """pt64: nº de itens da SysListView32 (LVM_GETITEMCOUNT — int, sem buffer)."""
    if not hwnd_lv:
        return None
    n = _pt30_user32.SendMessageW(hwnd_lv, LVM_GETITEMCOUNT, 0, 0)
    return n if isinstance(n, int) else None


def _lv_selected_index(hwnd_lv):
    """pt64: índice do item SELECCIONADO (LVM_GETNEXTITEM/LVNI_SELECTED — int,
    sem buffer cross-process). Devolve -1 se nada seleccionado, None se sem hwnd.

    É o read-back BARATO que substitui o `CB_GETCURSEL` (o CCombo não responde a
    CB_*): confirma a selecção no dropdown ABERTO antes do commit, sem precisar
    de ler o texto do item (que exigiria VirtualAllocEx cross-process)."""
    if not hwnd_lv:
        return None
    # wParam = -1 (começar do início da lista); devolve o índice (ou -1).
    return _pt30_user32.SendMessageW(hwnd_lv, LVM_GETNEXTITEM, -1, LVNI_SELECTED)


def _set_scope_in_popup(popup_rect):
    """Muda o Scope no popup Nash para "Selected Subtree" — pt64: SysListView32.

    O Scope é um SWT CCombo: canvas opaco, sem ComboBox/Edit nativo nem pattern
    UIA (Caso 3 do diag pt64) — por isso o caminho Win32 CB_* de pt61 não pegava
    (`_find_combo_with_item` devolvia (None,None) → abort). MAS ao abrir, o
    CCombo cria uma janela top-level com uma **SysListView32 nativa** (itens
    'Full Tree' idx0 / 'Selected Subtree' idx1). Conduzimo-lo por imitação
    humana, com read-back barato por LVM (int, sem buffer, sem comtypes):

      1. foreground do popup + foco-click no campo Scope (rel pt61);
      2. abrir o dropdown por F4 (retry 1×);
      3. confirmar a abertura achando a SysListView32 do dropdown;
      4. seleccionar 'Selected Subtree': type-search "Selected" (text-driven) com
         fallback determinístico Home→Down (Full Tree 0 → 1);
      5. READ-BACK: LVM_GETNEXTITEM(LVNI_SELECTED) confirma idx==1 (≠ default 0)
         numa lista de 2 itens — ANTES do commit;
      6. Enter confirma o item destacado.

    Devolve `True` só com a confirmação do passo 5; em qualquer falha fecha a
    lista (Esc) e devolve `False` — o caller ABORTA a 2ª run (inalterado), nunca
    corre Full Tree disfarçado de Selected Subtree.
    """
    if popup_rect is None:
        print('   [WARN] [scope] popup_rect None — scope NÃO confirmado')
        return False
    hwnd_popup = _find_nash_popup_hwnd()
    if not hwnd_popup:
        print('   [WARN] [scope] popup Nash hwnd não encontrado '
              '— scope NÃO confirmado')
        return False
    if SCOPE_DROPDOWN_REL_X == 0:
        print('   [WARN] [scope] coord de foco não calibrada — scope NÃO confirmado')
        return False

    left, top, _w, _h = popup_rect
    focus_x, focus_y = left + SCOPE_DROPDOWN_REL_X, top + SCOPE_DROPDOWN_REL_Y
    try:
        _pt30_user32.SetForegroundWindow(hwnd_popup)
    except Exception as e:
        print('   [WARN] [scope] SetForegroundWindow falhou (%s) — continua'
              % type(e).__name__)
    time.sleep(0.2)

    # Passos 1-3: foco no campo Scope + abrir dropdown (F4) + achar a listview.
    lv = None
    for attempt in (1, 2):
        pyautogui.click(focus_x, focus_y)        # foco no campo Scope
        time.sleep(0.25)
        pyautogui.press('f4')                    # abre o dropdown do CCombo
        _watchdog_sleep(0.4)                     # pt85 B — vigia (OOM/hung) ao abrir o scope
        lv = _find_scope_dropdown_listview()
        if lv:
            break
        print('   [WARN] [scope] dropdown não abriu (tentativa %d/2)' % attempt)
    if not lv:
        print('   [WARN] [scope] SysListView32 do dropdown não encontrada '
              '— scope NÃO confirmado')
        return False

    count = _lv_item_count(lv)
    if not isinstance(count, int) or count != 2:
        # diag pt64: a lista do Scope tem exactamente 2 itens. count≠2 = UI mudou
        # → sem confiança no mapa idx→texto → abort (não adivinha).
        print('   [WARN] [scope] lista com count=%r (esperado 2) — abort '
              '(re-correr diag se o HRC mudou)' % count)
        pyautogui.press('escape')
        return False

    before = _lv_selected_index(lv)              # default no open = 0 (Full Tree)
    # Passo 4: selecção text-driven, com fallback determinístico.
    pyautogui.typewrite('Selected', interval=0.04)
    time.sleep(0.3)
    sel = _lv_selected_index(lv)
    if sel != SCOPE_LIST_SELECTED_SUBTREE_INDEX:
        # fallback determinístico: normaliza ao topo e desce 1 (Full Tree→Sel.Sub.)
        pyautogui.press('home')
        time.sleep(0.1)
        pyautogui.press('down')
        time.sleep(0.2)
        sel = _lv_selected_index(lv)

    # Passo 5: read-back barato (int) — gate do abort.
    if sel != SCOPE_LIST_SELECTED_SUBTREE_INDEX:
        print('   [WARN] [scope] read-back falhou (sel=%r, before=%r, '
              'esperado %d) — scope NÃO confirmado' %
              (sel, before, SCOPE_LIST_SELECTED_SUBTREE_INDEX))
        pyautogui.press('escape')
        return False

    # Passo 6: commit do item destacado.
    pyautogui.press('enter')
    time.sleep(0.3)
    print('   [scope] SysListView32 idx=%d confirmado (read-back LVM) '
          '— Scope: Selected Subtree' % sel)
    return True


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

    Sequência alvo dentro do popup Nash (pt66):
      1. Click Calculate (abre popup).
      2. _set_scope_in_popup(popup_rect)  — Scope = Selected Subtree (Win32).
      3. Click OK (BM_CLICK).
    O CI já NÃO é escrito (pt66): o default do popup é sempre 10.0 (= `ci_target`),
    por isso o passo de fill CI foi removido — menos uma interação no popup SWT.
    A confirmação do CI passou a ser SÓ-LEITURA, feita pós-dispatch pelo caller
    (`_ci_target_readback_warn`, lê o "Target CI" da janela de progresso e avisa
    se ≠ 10).

    `wpos` é o win_pos do main HRC window (mesmo objecto que
    `start_calculation` recebe via globals). `ci_target` é o CI alvo da 2ª run
    (10.0); agora só informa o log e a salvaguarda de leitura — não é escrito.

    Defensive em cada passo: se `_click_calculate_button` não tem coords
    (placeholder), `_wait_for_nash_popup` devolve None por timeout, e os
    helpers downstream (scope / OK) fazem early-return. O flow inteiro degrada
    para no-op com WARN logs em vez de cliques errantes.

    pt28 (#FINALIZE-NEVER-FIRES-ON-NO-OP): devolve `bool`:
      - `True` se passos 1-4 completaram (popup detectado + set scope +
        fill CI + OK Enter). Caller (`setup_hand`) interpreta como "2ª run
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
    # pt61: Scope por Win32 com read-back. Se NÃO confirmar, ABORTA a 2ª run
    # (não clica OK). Um OK com Scope=Full Tree geraria um Full-Tree DISFARÇADO
    # de Selected Subtree que iria parar à biblioteca de estudo como se fosse
    # bom — pior que falhar. Devolve "scope_unconfirmed"; o caller marca a mão
    # falhada e avança (sem export).
    scope_ok = _set_scope_in_popup(popup_rect)            # passo 2 (Win32 + read-back)
    if not scope_ok:
        print('   [ABORT] [calc] Scope NÃO confirmado em "Selected Subtree" — '
              '2ª run ABORTADA (sem OK, sem export). Cancela o popup.')
        _cancel_nash_popup()
        return "scope_unconfirmed"
    # pt66: o CI já NÃO é escrito — o default do popup Nash é sempre 10.0 (= o
    # alvo `ci_target`). Menos uma interação no popup SWT. A salvaguarda é
    # só-leitura, feita pós-dispatch pelo caller (`_ci_target_readback_warn`).
    _click_ok_in_popup(popup_rect)                        # passo 3 (BM_CLICK)
    print('   start_calculation_selected_subtree(ci=%s) — 2ª run disparada '
          '(scope_ok=True; CI no default do popup, sem escrita)' % (ci_target,))
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
    o popup Nash não abria -> `_wait_for_nash_popup` timeout silencioso.

    `navigate_to_target_node` deixou de chamar esta função em pt28. A
    definição fica no source para o marshal swap não regredir; chamadores
    foram removidos. Se algum dia houver evidência de que o foco da
    Strategy Table NÃO é default, abrir tech debt nova com smoke calibrado
    e re-wirar (não basta descomentar — STRATEGY_TABLE_FOCUS_X/Y continuam
    sem calibração validada).
    """
    click_rel(wpos, STRATEGY_TABLE_FOCUS_X, STRATEGY_TABLE_FOCUS_Y)
    time.sleep(0.2)


def navigate_to_target_node(wpos, target_node_offset, aggressor_real_action=None):
    """pt61: leva o cursor da Strategy Table até ao nó do raiser real.

    Dois fixes (ambos necessários — descobertos na re-smoke pt61):
      1. FOCO/INÍCIO: clica o nó-raiz (1ª linha) da Strategy Table na janela
         PRINCIPAL do HRC ANTES de navegar — fixa o ponto de partida. As setas
         sozinhas (pt28-pt35), sem foco nem início conhecido, aterravam no nó
         errado (o foco default pós-1ª-run afinal não era fiável).
      2. OFFSET certo: vem do backend já no espaço dos nós principais
         (#HRC-NODE-OFFSET-SB-JAM-OFFBY1 corrigido em pt61).

    Método (flag de módulo `_NAV_USE_DIRECT_CLICK`):
      - False (PRIMÁRIO): foco-no-raiz + `offset` setas-baixo. Independente da
        geometria (só precisa do nó-raiz + foco).
      - True (RESERVA): direct-click no alvo em
        `(ROOT_X, ROOT_Y + offset × PITCH)`. Calibração pt61: pitch 18.71 px/linha
        ((262−131)/7 do par 1º-nó/alvo medido). Sidestepa setas/foco mas depende
        de pitch/topo estáveis.

    Read-back: loga o nó ESPERADO (`aggressor_real_action`: position+type+size)
    para verificação **visual** na re-smoke. A leitura do CONTEÚDO da Strategy
    Table (widget SWT) não está disponível sem um snapshot do controlo no Beelink
    (à imagem dos snapshots de child-windows do popup em pt33) → fica como
    `#HRC-NAV-TABLE-READBACK-PENDING`; até lá, verificação visual.

    `target_node_offset` = `meta.json.target_node_offset` (backend). `None` →
    skip; non-int / <0 / >100 → WARN skip; `0` → foca a raiz (0 setas).
    """
    if target_node_offset is None:
        print('   navigate_to_target_node: offset None — skip')
        return
    if not isinstance(target_node_offset, int):
        print('   [WARN] navigate_to_target_node: offset não-int (%s) — skip'
              % type(target_node_offset).__name__)
        return
    if target_node_offset < 0 or target_node_offset > 100:
        print('   [WARN] navigate_to_target_node: offset %d fora de [0, 100] '
              '— skip' % target_node_offset)
        return
    hrc = find_hrc()
    if not hrc:
        print('   [WARN] navigate_to_target_node: HRC não encontrado — skip')
        return
    # pt67 (#HRC-NAV-LABEL-MISLEADING): o label mostra o ALVO REAL da navegação
    # — posição + sizing + Nº DA LINHA (offset) — não só a acção do agressor. O
    # label antigo "(esperado: HJ raise 9.01bb)" descrevia a acção e lia-se como
    # "o nó esperado", mascarando o offset (a verdadeira variável de navegação);
    # foi o que induziu o off-by-one da 3ª volta a passar despercebido. A linha é
    # 1-based (linha 1 = offset 0). A acção real do agressor = o nó-alvo sob a lei
    # provisória "sizing real" (REGRAS_NEGOCIO §16).
    exp = ''
    if isinstance(aggressor_real_action, dict):
        exp = ' [ALVO nav: linha %d (offset %d) | accao real do agressor: %s %s %sbb]' % (
            target_node_offset + 1, target_node_offset,
            aggressor_real_action.get('position'),
            aggressor_real_action.get('type'),
            aggressor_real_action.get('size_bb'))
    root_x = hrc.left + STRATEGY_TABLE_ROOT_REL_X
    root_y = hrc.top + STRATEGY_TABLE_ROOT_REL_Y
    if _NAV_USE_DIRECT_CLICK:
        ty = int(round(root_y + target_node_offset * STRATEGY_TABLE_ROW_PITCH_PX))
        print('   navigate_to_target_node: DIRECT-CLICK alvo @ (%d,%d) offset=%d%s'
              % (root_x, ty, target_node_offset, exp))
        pyautogui.click(root_x, ty)
        time.sleep(0.2)
    else:
        print('   navigate_to_target_node: foco-raiz @ (%d,%d) + %d setas%s'
              % (root_x, root_y, target_node_offset, exp))
        pyautogui.click(root_x, root_y)   # foco + selecciona o nó-raiz (offset 0)
        time.sleep(0.2)
        for _ in range(target_node_offset):
            pyautogui.press('down')
            time.sleep(0.05)
    print('   navigate_to_target_node: concluído — VERIFICAR visualmente o nó na '
          're-smoke%s' % exp)


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
    return export_strategies(export_zip)


def _find_export_combo(dialog_hwnd):
    """pt35: hwnd do ComboBox de modo de export (class 'ComboBox'). Diagnóstico
    v2: nativo, 4 itens. None se não encontrar. Read-only (não muda selecção)."""
    if not dialog_hwnd:
        return None
    found = []

    def _enum(ch, lparam):
        cls_buf = ctypes.create_unicode_buffer(256)
        _pt30_user32.GetClassNameW(ch, cls_buf, 256)
        if cls_buf.value.lower() == "combobox":
            found.append(ch)
            return False
        return True

    _pt30_user32.EnumChildWindows(dialog_hwnd, _PT30_WNDENUMPROC(_enum), 0)
    return found[0] if found else None


def _find_export_button(dialog_hwnd, label):
    """pt35: hwnd de um Button do diálogo de export cujo texto normalizado
    (sem '&') == label.lower(). Mesma anatomia que `_find_ok_button` (pt33).
    Usado para OK e Cancel. None se não encontrar."""
    if not dialog_hwnd:
        return None
    target = label.strip().lower()
    found = []

    def _enum(ch, lparam):
        cls_buf = ctypes.create_unicode_buffer(256)
        _pt30_user32.GetClassNameW(ch, cls_buf, 256)
        if cls_buf.value == "Button":
            n = _pt30_user32.GetWindowTextLengthW(ch)
            if n > 0:
                txt_buf = ctypes.create_unicode_buffer(n + 1)
                _pt30_user32.GetWindowTextW(ch, txt_buf, n + 1)
                if txt_buf.value.replace("&", "").strip().lower() == target:
                    found.append(ch)
                    return False
        return True

    _pt30_user32.EnumChildWindows(dialog_hwnd, _PT30_WNDENUMPROC(_enum), 0)
    return found[0] if found else None


def _find_export_ok_button(dialog_hwnd):
    """pt35: hwnd do Button OK do diálogo de export (diagnóstico v2: text='OK')."""
    return _find_export_button(dialog_hwnd, "ok")


def _find_export_dialog():
    """pt35: hwnd do diálogo Export Strategies.

    O diálogo é um #32770 nativo de TÍTULO VAZIO (diagnóstico v2), por isso o
    `_find_export_hwnd` da OG NÃO o encontra — esse faz match por TÍTULO
    (disassembly confirmou: `_find_hwnd_by_keywords._cb` usa GetWindowTextW e
    salta janelas sem título). Aqui matchamos por CLASSE '#32770' + presença de
    um ComboBox filho (filtra message boxes genéricas). Em tempo de export o
    popup Nash já fechou, logo sem colisão. None se não houver.
    """
    matches = []

    def _enum_top(hwnd, lparam):
        cls_buf = ctypes.create_unicode_buffer(256)
        _pt30_user32.GetClassNameW(hwnd, cls_buf, 256)
        if cls_buf.value == "#32770" and _find_export_combo(hwnd):
            matches.append(hwnd)
            return False
        return True

    _pt30_user32.EnumWindows(_PT30_WNDENUMPROC(_enum_top), 0)
    return matches[0] if matches else None


def _cancel_export_dialog(dialog_hwnd):
    """pt35: fecha o diálogo de export via BM_CLICK no Button Cancel — evita
    deixá-lo aberto a bloquear a mão seguinte quando abortamos por erro.
    WARN se não encontrar (não silencia)."""
    btn = _find_export_button(dialog_hwnd, "cancel")
    if not btn:
        print('   [WARN] [export] Button Cancel não encontrado — diálogo pode '
              'ficar aberto (hwnd=%r)' % (dialog_hwnd,))
        return
    _pt30_user32.SendMessageW(btn, BM_CLICK, 0, 0)
    print('   [export] Cancel hwnd=%d BM_CLICK enviado' % btn)
    time.sleep(0.3)


def _find_top_by_substr(*needles):
    """pt35 (port launcher): 1ª janela top-level VISÍVEL cujo título contém
    qualquer needle (case-insensitive). Devolve (hwnd, title) ou None.
    Usa _pt30_user32 (HWND/LPARAM 64-bit-safe, ao contrário do c_int do
    launcher original)."""
    needles_lc = [n.lower() for n in needles]
    found = []

    def _enum(hwnd, lparam):
        if _pt30_user32.IsWindowVisible(hwnd):
            n = _pt30_user32.GetWindowTextLengthW(hwnd)
            if n > 0:
                buf = ctypes.create_unicode_buffer(n + 1)
                _pt30_user32.GetWindowTextW(hwnd, buf, n + 1)
                tl = buf.value.lower()
                if any(needle in tl for needle in needles_lc):
                    found.append((hwnd, buf.value))
                    return False
        return True

    _pt30_user32.EnumWindows(_PT30_WNDENUMPROC(_enum), 0)
    return found[0] if found else None


def _find_save_button(dialog_hwnd):
    """pt35 (port do `_find_ok_button` do launcher, renomeado para não colidir
    com o nosso `_find_ok_button` pt33, que é do popup Nash): botão Save do
    file-picker. Match: class contém 'button', visível+enabled, texto (sem '&')
    em {ok, save, export, guardar}, por ordem de preferência. None se não houver."""
    if not dialog_hwnd:
        return None
    targets = ("ok", "save", "export", "guardar")
    found = []

    def _enum(ch, lparam):
        cls_buf = ctypes.create_unicode_buffer(256)
        _pt30_user32.GetClassNameW(ch, cls_buf, 256)
        if "button" not in cls_buf.value.lower():
            return True
        if not (_pt30_user32.IsWindowVisible(ch) and _pt30_user32.IsWindowEnabled(ch)):
            return True
        n = _pt30_user32.GetWindowTextLengthW(ch)
        if n > 0:
            txt_buf = ctypes.create_unicode_buffer(n + 1)
            _pt30_user32.GetWindowTextW(ch, txt_buf, n + 1)
            txt = txt_buf.value.replace("&", "").strip().lower()
            if txt in targets:
                found.append((ch, txt))
        return True

    _pt30_user32.EnumChildWindows(dialog_hwnd, _PT30_WNDENUMPROC(_enum), 0)
    for pref in targets:
        for h, t in found:
            if t == pref:
                return h
    return found[0][0] if found else None


def _confirm_overwrite_if_present(timeout_s=2.0):
    """pt87 — se o Save abriu um 'Confirm Save As' (ficheiro já existe → Replace?),
    clica Yes/Save via BM_CLICK. No-op se não houver. True se tratou."""
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        found = _find_top_by_substr('confirm save as', 'guardar como', 'replace')
        if found:
            btn = _find_button_by_text(
                found[0], lambda t: t in ('yes', 'sim', 'save', 'guardar'))
            if btn:
                _pt30_user32.SendMessageW(btn, BM_CLICK, 0, 0)
                print('   [SAVE-AS] overwrite confirmado (Yes/Save BM_CLICK)')
                return True
        time.sleep(0.3)
    return False


def _verify_export_zip(target_path, settle_s=2.0, wait_total_s=180.0):
    """pt85 C' (ii) + pt87 (#HRC-WATCHER-SAVE-NOT-PERSISTED) — logo após o [SAVE-AS],
    espera o ficheiro existir + estabilizar (tamanho igual em 2 leituras espaçadas
    >= settle_s) e corre testzip().

    pt87: passa a DEVOLVER bool (antes era só observabilidade). True = ficheiro
    persistido E zip íntegro; False = não apareceu/instável em wait_total_s OU
    testzip falhou. O caller usa-o como BARREIRA antes do close-tab (mata a corrida
    com o Ctrl+F4). Continua a logar [SAVE-AS-CHECK] OK/INVÁLIDO. wait_total_s
    subido 30→180s (trees grandes 40-70 MB)."""
    import zipfile as _zf
    deadline = time.time() + wait_total_s
    last_size = -1
    stable_since = None
    persisted = False
    while time.time() < deadline:
        try:
            sz = os.path.getsize(target_path)
        except OSError:
            time.sleep(0.5)
            continue
        if sz == last_size and sz > 0:
            if stable_since is None:
                stable_since = time.time()
            elif time.time() - stable_since >= settle_s:
                persisted = True
                break
        else:
            stable_since = None
            last_size = sz
        time.sleep(0.5)
    base = os.path.basename(target_path)
    if not persisted:
        print('   [SAVE-AS-CHECK] INVÁLIDO: %s — ficheiro nao persistiu em %.0fs '
              '(ultimo size=%s)' % (base, wait_total_s, last_size))
        return False
    try:
        with _zf.ZipFile(target_path) as z:
            bad = z.testzip()
        if bad is None:
            print('   [SAVE-AS-CHECK] OK: %s (%s bytes)' % (base, last_size))
            return True
        print('   [SAVE-AS-CHECK] INVÁLIDO: %s — entrada corrompida %r' % (base, bad))
        return False
    except Exception as e:
        print('   [SAVE-AS-CHECK] INVÁLIDO: %s — %s' % (base, e))
        return False


def _save_as_set_and_click(target_path):
    """pt35 (port do `_save_as_set_and_click` do launcher) — trata o file-picker
    "Save As" do export: aguarda o diálogo (≤20s), cola o path por clipboard
    (com fallback typewrite), e clica Save via BM_CLICK (fallback Enter).
    Self-contained (não depende do launcher). Devolve True/False.

    Edge cases preservados do original:
      - 40 tentativas × 0.5s a achar o diálogo (title 'save as'/'guardar'/
        'save a copy').
      - clipboard paste em try/except → fallback typewrite (também em try/except).
      - Save btn via BM_CLICK; se não achar → Enter (em try/except).
    """
    import pyperclip
    import pyautogui

    save_dlg = None
    for _ in range(40):
        time.sleep(0.5)
        found = _find_top_by_substr("save as", "guardar", "save a copy")
        if not found:
            continue
        save_dlg, t = found
        print('   [SAVE-AS] dialog "%s" hwnd=%s' % (t, save_dlg))
        _pt30_user32.SetForegroundWindow(save_dlg)
        time.sleep(0.4)
        break
    if not save_dlg:
        print('   [SAVE-AS] WARN: dialog nao apareceu em 20s')
        return False

    def _paste_filename():
        try:
            pyperclip.copy(target_path)
            time.sleep(0.3)
            pyautogui.hotkey("ctrl", "a")
            time.sleep(0.15)
            pyautogui.hotkey("ctrl", "v")
            time.sleep(0.5)
            print('   [SAVE-AS] filename pasted via clipboard: %s' % target_path)
        except Exception as e:
            print('   [SAVE-AS] WARN: clipboard paste falhou (%s), fallback typewrite' % e)
            try:
                pyautogui.hotkey("ctrl", "a")
                time.sleep(0.1)
                pyautogui.typewrite(target_path, interval=0.005)
                time.sleep(0.3)
            except Exception as e2:
                print('   [SAVE-AS] typewrite fallback tambem falhou: %s' % e2)

    def _click_save():
        save_btn = _find_save_button(save_dlg)
        if save_btn:
            print('   [SAVE-AS] Save btn hwnd=%s -> BM_CLICK' % save_btn)
            _pt30_user32.SendMessageW(save_btn, BM_CLICK, 0, 0)
        else:
            print('   [SAVE-AS] Save btn nao encontrado, Enter')
            try:
                pyautogui.press("enter")
            except Exception as e:
                print('   [SAVE-AS] enter erro: %s' % e)
        time.sleep(0.5)
        _confirm_overwrite_if_present()

    # 1ª tentativa: paste → Save → (overwrite) → BARREIRA (persistência+integridade).
    _paste_filename()
    _click_save()
    if _verify_export_zip(target_path):
        return True

    # pt87 — 1 retry: SÓ se o diálogo Save As ainda está aberto (o Save não pegou).
    if _find_top_by_substr("save as", "guardar", "save a copy"):
        print('   [SAVE-AS] retry: dialogo ainda aberto — re-Save via Enter')
        _paste_filename()
        try:
            pyautogui.press("enter")
            time.sleep(0.5)
            _confirm_overwrite_if_present()
        except Exception as e:
            print('   [SAVE-AS] retry enter erro: %s' % e)
        if _verify_export_zip(target_path):
            return True

    print('   [SAVE-AS] FALHOU: zip nao persistiu/integro apos retry: %s' % target_path)
    return False


def export_strategies(export_path):
    """pt35 (GTO Brain Fase 1) — SWAP da export_strategies OG.

    Muda o modo de export de 'Manual Selection' (default → exporta 1 nó) para
    'Complete Export' (exporta a árvore toda; o Depth é IGNORADO neste modo —
    confirmado por smoke do Rui). Preserva o resto do fluxo OG: abrir o menu
    Hand → Export Strategies e, no fim, paste_path no file-picker.

    Diferenças vs OG (decompiled/hrc_watcher.py:427):
      - REMOVE o bloco home/down/tab/ctrl+a/type('10')/enter (era a navegação
        de Manual Selection + Depth). Já não é usado.
      - LOCALIZA o diálogo por classe #32770 (título vazio) em vez de
        `_find_export_hwnd` (match por título, falha aqui).
      - SETA o ComboBox de modo para 'Complete Export' via CB_SETCURSEL +
        notificação CBN_SELCHANGE ao diálogo, com read-back de verificação.
      - OK via BM_CLICK no Button OK (determinístico, padrão pt33) em vez de Enter.
      - Erro em qualquer passo → WARN + Cancel do diálogo (não silencia).
    """
    hrc = find_hrc()
    if not hrc:
        print('   [export] ERRO: HRC não encontrado')
        return None

    # 1) Abrir menu Hand → Export Strategies (sequência OG preservada)
    pyautogui.click(hrc.left + 300, hrc.top + 154)
    time.sleep(0.5)
    pyautogui.press('escape')
    time.sleep(0.3)
    pyautogui.click(hrc.left + 60, hrc.top + 43)
    time.sleep(0.6)
    for _ in range(4):
        pyautogui.press('down')
        time.sleep(0.15)
    pyautogui.press('enter')

    # 2) Localizar o diálogo #32770 (título vazio → não via _find_export_hwnd)
    dlg = None
    for _ in range(16):
        time.sleep(0.5)
        dlg = _find_export_dialog()
        if dlg:
            break
    if not dlg:
        print('   [WARN] [export] diálogo Export Strategies (#32770) não '
              'encontrado em ~8s — export desta mão abortado')
        return None
    print('   [export] diálogo #32770 hwnd=%d' % dlg)
    _pt30_user32.SetForegroundWindow(dlg)
    time.sleep(0.4)

    # 3) Setar modo = 'Complete Export'
    combo = _find_export_combo(dlg)
    if not combo:
        print('   [WARN] [export] ComboBox de modo não encontrado — Cancel + abort')
        _cancel_export_dialog(dlg)
        return None
    prev = _pt30_user32.SendMessageW(combo, CB_GETCURSEL, 0, 0)
    _pt30_user32.SendMessageW(combo, CB_SETCURSEL, EXPORT_MODE_COMPLETE_INDEX, 0)
    # CB_SETCURSEL não notifica o pai; enviar CBN_SELCHANGE para o diálogo
    # reagir à selecção programática (senão pode exportar o modo antigo).
    ctrl_id = _pt30_user32.GetDlgCtrlID(combo)
    _pt30_user32.SendMessageW(
        dlg, WM_COMMAND, (CBN_SELCHANGE << 16) | (ctrl_id & 0xFFFF), combo)
    time.sleep(0.4)
    now = _pt30_user32.SendMessageW(combo, CB_GETCURSEL, 0, 0)
    print('   [export] combo modo: prev_idx=%d → now_idx=%d (alvo=%d "Complete Export")'
          % (prev, now, EXPORT_MODE_COMPLETE_INDEX))
    if now != EXPORT_MODE_COMPLETE_INDEX:
        print('   [WARN] [export] CB_SETCURSEL não confirmou (now=%d != %d) — '
              'Cancel + abort para não exportar o modo errado'
              % (now, EXPORT_MODE_COMPLETE_INDEX))
        _cancel_export_dialog(dlg)
        return None

    # 4) OK via BM_CLICK (determinístico, padrão pt33)
    ok = _find_export_ok_button(dlg)
    if not ok:
        print('   [WARN] [export] Button OK não encontrado — Cancel + abort')
        _cancel_export_dialog(dlg)
        return None
    _pt30_user32.SendMessageW(ok, BM_CLICK, 0, 0)
    print('   [export] OK hwnd=%d BM_CLICK enviado' % ok)
    time.sleep(1.5)   # dar tempo ao file-picker para aparecer

    # 5) File-picker: Save As robusto (port self-contained do launcher)
    saved = _save_as_set_and_click(export_path)
    if saved:
        print('   [export] _save_as_set_and_click concluído (persistido+íntegro): %s' % export_path)
    else:
        print('   [WARN] [export] _save_as_set_and_click NAO persistiu/integro: %s' % export_path)
    return saved


# ── pt68 — higiene do HRC (incidente madrugada 11 Jun) ──────────────────────
# Degradação progressiva: acumulação de tabs/memória do HRC ao longo da fornada
# (setup-failed 02:14 cold start → 3 OK → derail ~02:35). 3 correções (ordem Rui):
#  1. fechar a tab da mão após export (_close_hand_tab); 2. reiniciar o HRC a
#  cada N mãos (_restart_hrc) + health-check pós-arranque (_wait_hrc_responsive,
#  mitiga o cold start); 3. log a ficheiro com rotação (_ensure_file_logging).
_HANDS_DONE_SINCE_RESTART = 0
_RESTART_EVERY_N_HANDS = 5
# pt79 (#HRC-RESTART-POST-WINDOW-FAILURE): True quando a mão anterior falhou
# DEPOIS de o wizard abrir (cálculo/finish/export) — o HRC pode ter ficado sujo
# (diálogo "Hand Setup"/"Open" preso + memória alta) e arrasta as seguintes
# ("setup failed"). Reiniciado no arranque da mão seguinte. Lido via
# globals().get(...,False) para ser SEGURO mesmo sem APPEND no marshal-swap
# (ver README §"Resolução de globais"); a 1ª escrita cria a chave no namespace.
_HRC_WINDOW_DIRTY = False
# pt79 — HOOK DE INDUÇÃO do re-smoke (#HRC-RESTART-POST-WINDOW-FAILURE). Activado
# pela env `HRC_WATCHER_SMOKE_FAIL_FIRST` (ou pondo `_SMOKE_FAIL_FIRST=True` num
# build de smoke). Na 1ª mão (one-shot por PROCESSO do watcher), `setup_hand`
# levanta o RuntimeError pós-janela LOGO APÓS o wizard abrir — determinístico,
# INDEPENDENTE do tamanho da árvore (não depende do finish-wait, que escapava em
# árvores triviais). INERTE em produção (env unset + flag False). Não re-arma no
# `_restart_hrc` (o flag vive no processo do watcher, não no HRC).
_SMOKE_FAIL_FIRST = False
_SMOKE_FAIL_FIRST_FIRED = False
_HRC_COLDSTART_GRACE_S = 8
_CLOSE_TAB_AFTER_EXPORT = True
_FILE_LOGGING_READY = False
_WATCHER_LOG_DIR = r'C:\hrc\watcher_logs'
# pt85 (#HRC-EXPORT-WAIT-TIMEOUT) — Peça A: a main-loop Baltazar fica em `Activas`
# à espera do zip em `replied/` (handshake do adapter) até `EXPORT_WAIT_TIMEOUT`;
# o ramo `elapsed > EXPORT_WAIT_TIMEOUT → mark_failed` já existe, mas o default
# Baltazar (86400 = 24h) = "pendura para sempre" se o export sair inválido ou o
# adapter recusar. Override aqui (o trampoline corre Baltazar=_O e depois
# patched_funcs=_P no MESMO globals → este valor vence). 1800s = 30 min (pt87): handshake
# parada/zip mau falha ESSA mão + a fila avança; zip bom mas lento fica em disco e
# o adapter POSTa-o depois (upsert sobre o failed). Provado em prod: GG-6082958318
# pendurou ~1h46 (export corrompido recusado pelo adapter, nunca foi a replied/).
EXPORT_WAIT_TIMEOUT = 1800

# ── pt84 (#HRC-HANG-WATCHDOG) — vigia de mão pendurada ───────────────────────
# Detecta HRC congelado/OOM DURANTE as esperas e RECUPERA: mark_failed(reason)
# (→ adapter POSTa failed → hrc_jobs failed → re-queue) + kill+restart do HRC +
# segue para a mão seguinte. Sinais: (1) diálogo fatal Java/OOM por título;
# (2) janela principal HUNG (IsHungAppWindow) sustido; (3) backstop wall-clock já
# existente na espera-mãe (7200s). X FOLGADO de propósito — solves legítimos de CI
# chegam a ~78 min; NÃO matar solves bons. Calibrar no re-smoke; desligável por env.
_WATCHDOG_ENABLED = (os.environ.get('HRC_WATCHDOG_DISABLED', '') == '')
_WATCHDOG_POLL_S = 5.0          # throttle: 1 verificação a cada 5s, no máximo
# diálogo fatal: substrings de título (getAllWindows). Conservador — confirmar o
# título REAL do popup OOM no Beelink no re-smoke e afinar esta tupla.
_WATCHDOG_FATAL_TITLE_HINTS = (
    'outofmemoryerror', 'out of memory', 'java.lang.', 'java exception',
    'fatal error', 'unexpected error',
)
# HUNG sustido: a janela tem de estar congelada CONTINUAMENTE este tempo antes de
# disparar (guard contra falso-positivo se o HRC bloqueia a UI num build de árvore
# legítimo). FOLGADO. Override por env HRC_WATCHDOG_HUNG_SUSTAIN_S.
_WATCHDOG_HUNG_SUSTAIN_S = float(os.environ.get('HRC_WATCHDOG_HUNG_SUSTAIN_S') or 1200.0)
_WATCHDOG_HUNG_SINCE = None     # timestamp do início do hung contínuo (ou None)
_WATCHDOG_LAST_CHECK = 0.0      # último instante em que se correu a deteção
_CURRENT_HAND_PATH = None       # mão a decorrer (mark_failed sem threading o path)
# hook de smoke: força um reason na 1ª verificação (env HRC_WATCHDOG_SMOKE_FORCE).
# One-shot por PROCESSO. Prova a cadeia de recuperação ponta-a-ponta SEM OOM real.
_WATCHDOG_SMOKE_FORCE = False
_WATCHDOG_SMOKE_FIRED = False


class HRCWatchdogError(Exception):
    """Disparada quando o vigia deteta HRC pendurado/OOM. _watchdog_trip já marcou
    a mão .failed (reason específico) + reiniciou o HRC ANTES de propagar; o
    try_setup.except do Baltazar devolve None (NÃO re-marca) e a fila avança."""


def _find_hrc_main_hwnd():
    """HWND da janela principal do HRC: find_hrc() (Baltazar) se devolver hwnd,
    senão EnumWindows ao título. None se não encontrar."""
    fh = globals().get('find_hrc')
    if fh:
        try:
            w = fh()
            for attr in ('_hWnd', 'hWnd', 'handle'):
                h = getattr(w, attr, None)
                if isinstance(h, int) and h:
                    return h
            if isinstance(w, int) and w:
                return w
        except Exception:
            pass
    found = []
    def _enum(hwnd, lparam):
        try:
            n = _pt30_user32.GetWindowTextLengthW(hwnd)
            if n > 0:
                buf = ctypes.create_unicode_buffer(n + 1)
                _pt30_user32.GetWindowTextW(hwnd, buf, n + 1)
                t = (buf.value or '').lower()
                if 'holdem resources' in t or t.strip() == 'hrc':
                    found.append(hwnd)
        except Exception:
            pass
        return True
    try:
        _pt30_user32.EnumWindows(_PT30_WNDENUMPROC(_enum), 0)
    except Exception:
        return None
    return found[0] if found else None


def _detect_fatal_hrc_window():
    """Procura um diálogo fatal Java/OOM por título (getAllWindows). Devolve o
    título (lower) ou None. Mesmo padrão de _detect_hand_import_error_popup."""
    try:
        windows = pyautogui.getAllWindows()
    except Exception:
        return None
    if not windows:
        return None
    for w in windows:
        title = (getattr(w, 'title', '') or '').strip().lower()
        if not title:
            continue
        for hint in _WATCHDOG_FATAL_TITLE_HINTS:
            if hint in title:
                return title
    return None


def _watchdog_reason():
    """reason (str) se o HRC está pendurado/OOM, senão None.
    Ordem: smoke-force > diálogo fatal > hung sustido."""
    if not _WATCHDOG_ENABLED:
        return None
    if (not globals().get('_WATCHDOG_SMOKE_FIRED', False)
            and (_WATCHDOG_SMOKE_FORCE or os.environ.get('HRC_WATCHDOG_SMOKE_FORCE'))):
        globals()['_WATCHDOG_SMOKE_FIRED'] = True
        return 'watchdog_smoke_force (indução one-shot pt84)'
    fatal = _detect_fatal_hrc_window()
    if fatal:
        return 'hrc_fatal_dialog: %s' % fatal[:80]
    hwnd = _find_hrc_main_hwnd()
    if hwnd and bool(_pt30_user32.IsHungAppWindow(hwnd)):
        since = globals().get('_WATCHDOG_HUNG_SINCE')
        if since is None:
            globals()['_WATCHDOG_HUNG_SINCE'] = time.time()
        elif time.time() - since >= _WATCHDOG_HUNG_SUSTAIN_S:
            return ('hrc_hung_sustained: janela principal congelada >= %ds'
                    % int(_WATCHDOG_HUNG_SUSTAIN_S))
    else:
        globals()['_WATCHDOG_HUNG_SINCE'] = None   # responsiva → reset do timer
    return None


def _watchdog_trip(reason):
    """Recupera de um pendurar: mark_failed(reason) + restart do HRC + levanta
    HRCWatchdogError. mark_failed ANTES de propagar para o reason específico
    sobreviver (try_setup.except não re-marca)."""
    print('   [WATCHDOG] DISPARO: %s — marcar failed, kill+restart HRC, seguir.' % reason)
    hp = globals().get('_CURRENT_HAND_PATH')
    mf = globals().get('mark_failed')
    if hp and mf:
        try:
            mf(hp, reason)
        except Exception as _e:
            print('   [WATCHDOG] mark_failed falhou: %s' % _e)
    else:
        print('   [WATCHDOG] sem _CURRENT_HAND_PATH/mark_failed — não marcou (anómalo).')
    try:
        _restart_hrc()
        globals()['_HANDS_DONE_SINCE_RESTART'] = 0
        globals()['_HRC_WINDOW_DIRTY'] = False
    except Exception as _e:
        print('   [WATCHDOG] _restart_hrc falhou: %s' % _e)
    globals()['_WATCHDOG_HUNG_SINCE'] = None
    raise HRCWatchdogError(reason)


def _watchdog_sleep(seconds):
    """Drop-in para time.sleep(seconds) nas esperas longas: corre a deteção do
    vigia no máximo a cada _WATCHDOG_POLL_S; se disparar, recupera e levanta
    HRCWatchdogError. Inofensivo com o vigia desligado."""
    if not _WATCHDOG_ENABLED:
        time.sleep(seconds)
        return
    now = time.time()
    if now - globals().get('_WATCHDOG_LAST_CHECK', 0.0) >= _WATCHDOG_POLL_S:
        globals()['_WATCHDOG_LAST_CHECK'] = now
        reason = _watchdog_reason()
        if reason:
            _watchdog_trip(reason)   # levanta HRCWatchdogError
    time.sleep(seconds)


class _Tee:
    """Escreve em vários streams (consola + ficheiro). Robusto a falhas."""
    def __init__(self, *streams):
        self._streams = [s for s in streams if s is not None]
    def write(self, data):
        for s in self._streams:
            try:
                s.write(data); s.flush()
            except Exception:
                pass
    def flush(self):
        for s in self._streams:
            try:
                s.flush()
            except Exception:
                pass
    def isatty(self):
        return False


def _ensure_file_logging():
    """change 3 (#WATCHER-LOG-TO-FILE): espelha stdout/stderr para um ficheiro
    por sessão em _WATCHER_LOG_DIR (fim das consolas perdidas). Corre 1x;
    mantém os últimos 14 ficheiros."""
    global _FILE_LOGGING_READY
    if _FILE_LOGGING_READY:
        return
    _FILE_LOGGING_READY = True
    try:
        import sys
        os.makedirs(_WATCHER_LOG_DIR, exist_ok=True)
        ts = time.strftime('%Y%m%d_%H%M%S')
        path = os.path.join(_WATCHER_LOG_DIR, 'hrc_watcher_%s.log' % ts)
        f = open(path, 'a', encoding='utf-8', buffering=1)
        sys.stdout = _Tee(getattr(sys, '__stdout__', None) or sys.stdout, f)
        sys.stderr = _Tee(getattr(sys, '__stderr__', None) or sys.stderr, f)
        try:
            logs = sorted(x for x in os.listdir(_WATCHER_LOG_DIR)
                          if x.startswith('hrc_watcher_') and x.endswith('.log'))
            for old in logs[:-14]:
                try:
                    os.remove(os.path.join(_WATCHER_LOG_DIR, old))
                except OSError:
                    pass
        except OSError:
            pass
        print('   [log] a gravar em %s' % path)
    except Exception as e:
        print('   [WARN] _ensure_file_logging falhou (%s) — só consola' % e)


def _running_hrc_path():
    """Path do hrc.exe a correr (robusto — não hardcode; o HRC mudou de path
    entre instalações). None se não encontrar."""
    try:
        import subprocess
        out = subprocess.run(
            ['powershell', '-NoProfile', '-Command',
             "(Get-Process hrc -ErrorAction SilentlyContinue | "
             "Select-Object -First 1 -ExpandProperty Path)"],
            capture_output=True, text=True, timeout=15)
        p = (out.stdout or '').strip()
        return p or None
    except Exception:
        return None


def _restart_hrc():
    """change 2 (#HRC-WATCHER-TAB-ACCUMULATION): mata o hrc.exe e relança-o do
    MESMO path (capturado antes do kill; fallback ao HRC_EXE do módulo). Higiene
    de memória — a cada _RESTART_EVERY_N_HANDS mãos."""
    import subprocess
    exe = _running_hrc_path()
    print('   [HRC-RESTART] hrc.exe path=%r — a matar...' % exe)
    try:
        subprocess.run(['taskkill', '/F', '/IM', 'hrc.exe'],
                       capture_output=True, text=True, timeout=20)
    except Exception as e:
        print('   [WARN] taskkill hrc.exe: %s' % e)
    time.sleep(4)
    launch = exe or globals().get('HRC_EXE')
    if not launch:
        print('   [WARN] _restart_hrc: sem path do HRC — ensure_hrc tentará abrir')
        return
    try:
        subprocess.Popen([launch])
        print('   [HRC-RESTART] relançado: %s' % launch)
    except Exception as e:
        print('   [WARN] _restart_hrc relançar (%s): %s' % (launch, e))


def _wait_hrc_responsive(stable_cycles=3, timeout_s=45):
    """change 2b (mitigação cold start — o setup-failed das 02:14): esperar o HRC
    responsivo — find_hrc() com wpos ESTÁVEL N ciclos — + grace antes do 1º
    setup. Cobre cold start e pós-reinício."""
    last = None
    stable = 0
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        try:
            hrc = find_hrc()
        except Exception:
            hrc = None
        if hrc:
            pos = (hrc.left, hrc.top, hrc.width, hrc.height)
            if pos == last and all(pos):
                stable += 1
            else:
                stable = 1
                last = pos
            if stable >= stable_cycles:
                time.sleep(_HRC_COLDSTART_GRACE_S)
                print('   [HRC] responsivo (wpos estável) + grace %ds.'
                      % _HRC_COLDSTART_GRACE_S)
                return True
        time.sleep(1)
    print('   [WARN] _wait_hrc_responsive: timeout %ds — sigo na mesma' % timeout_s)
    return False


def _find_button_by_text(hwnd_dialog, pred):
    """Botão (class 'Button') cujo texto normalizado (sem '&', lower, strip)
    satisfaz `pred`. None se não encontrar. Mesma anatomia que `_find_ok_button`
    (pt33)."""
    if not hwnd_dialog:
        return None
    found = []

    def _enum(ch, lparam):
        cls_buf = ctypes.create_unicode_buffer(256)
        _pt30_user32.GetClassNameW(ch, cls_buf, 256)
        if cls_buf.value == "Button":
            n = _pt30_user32.GetWindowTextLengthW(ch)
            if n > 0:
                txt_buf = ctypes.create_unicode_buffer(n + 1)
                _pt30_user32.GetWindowTextW(ch, txt_buf, n + 1)
                t = txt_buf.value.replace("&", "").strip().lower()
                if pred(t):
                    found.append(ch)
                    return False
        return True

    _pt30_user32.EnumChildWindows(hwnd_dialog, _PT30_WNDENUMPROC(_enum), 0)
    return found[0] if found else None


def _click_dont_save_dialog(timeout_s=6):
    """Espera o diálogo SWT "Save Resource — Save 'Hand N'?" (após Ctrl+F4) e
    clica **Don't Save** via Win32 BM_CLICK (como o OK do popup Nash, pt33). O
    export zip já tem tudo; gravar = lixo no workspace. True se clicou."""
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        dlg = _find_top_by_substr('save resource', "save '", 'save ‘')
        if dlg:
            btn = _find_button_by_text(
                dlg[0], lambda t: 'don' in t and 'save' in t)  # "Don't Save"
            if btn:
                _pt30_user32.SendMessageW(btn, BM_CLICK, 0, 0)
                print('   [tab] "Don\'t Save" clicado (hwnd=%d, dlg=%r)'
                      % (btn, dlg[1]))
                return True
            print('   [WARN] [tab] diálogo %r sem botão Don\'t Save' % (dlg[1],))
        time.sleep(0.4)
    return False


def _restore_hrc_main_focus(timeout_dialog_s=3.0):
    """pt69 (#HRC-CLOSE-TAB-BREAKS-CHORD-FOCUS): repõe a PRÉ-CONDIÇÃO que o
    `open_wizard()` OG assume antes de disparar o chord Ctrl+W,M — a janela
    PRINCIPAL do HRC com foreground+foco e SEM modal residual por cima.

    Causa-raiz (mão 1 OK → mão 2 hwnd_wizard=None): o `_close_hand_tab` fecha
    a tab e dispensa o "Save Resource" via BM_CLICK (mensagem, NÃO um click que
    foca). Sem repor o foco, o foreground fica indeterminado / pode sobrar o
    modal → o `pyautogui.click(centro)` + chord do open_wizard da mão seguinte
    é bloqueado/desviado → o wizard nunca abre → o main loop ('active'/Activas)
    fica preso (HRC vivo idle). `open_wizard` faz exactamente este center-click
    como 1ª acção (hrc_watcher.py:134) — espelhamo-lo aqui para garantir o
    estado limpo já no fecho.

    1) Confirma que o diálogo "Save Resource" desapareceu (poll); se ficar, WARN.
    2) Activa a janela principal + click no CENTRO (mesmo gesto do open_wizard)
       + settle, para o chord da próxima mão acertar no editor focado.
    """
    # 1) Esperar o modal "Save Resource" sumir de vez.
    t0 = time.time()
    while time.time() - t0 < timeout_dialog_s:
        if _find_top_by_substr('save resource', "save '", 'save ‘') is None:
            break
        time.sleep(0.3)
    else:
        print('   [WARN] [tab] "Save Resource" ainda presente após %.0fs — o '
              'foco da próxima mão pode falhar (open_wizard chord).'
              % timeout_dialog_s)
    # 2) Repor foreground+foco na janela principal (espelho do open_wizard).
    try:
        hrc = find_hrc()
        if not hrc:
            return
        try:
            hrc.activate()
        except Exception:
            pass
        time.sleep(0.3)
        cx = hrc.left + hrc.width // 2
        cy = hrc.top + hrc.height // 2
        pyautogui.click(cx, cy)
        time.sleep(0.6)
        print('   [tab] foco reposto na janela principal do HRC '
              '(pré-condição do chord da próxima mão).')
    except Exception as e:
        print('   [WARN] _restore_hrc_main_focus: %s' % e)


def _close_hand_tab():
    """change 1 (#HRC-WATCHER-TAB-ACCUMULATION, fix de raiz): fecha a tab da mão
    após o export (anti-acumulação). **Ctrl+F4** (o Ctrl+W no HRC é chord de
    nova-mão — NUNCA usar) → diálogo SWT "Save Resource" → **Don't Save**.
    Guard: se o HRC desaparecer, avisa LOUD (o ensure_hrc da mão seguinte
    relança). O reinício a cada N limita a acumulação mesmo que isto falhe.

    pt69: termina sempre por repor o foco na janela principal
    (`_restore_hrc_main_focus`) — o `open_wizard` OG depende desse estado para
    o chord Ctrl+W,M da mão seguinte (ver #HRC-CLOSE-TAB-BREAKS-CHORD-FOCUS)."""
    if not _CLOSE_TAB_AFTER_EXPORT:
        return
    try:
        hrc = find_hrc()
        if not hrc:
            print('   [tab] HRC não encontrado — skip close')
            return
        try:
            hrc.activate()
        except Exception:
            pass
        time.sleep(0.4)
        pyautogui.hotkey('ctrl', 'f4')
        clicked = _click_dont_save_dialog()
        time.sleep(0.6)
        if find_hrc() is None:
            print('   [WARN] [tab] o HRC desapareceu após Ctrl+F4! '
                  'ensure_hrc relança na próxima mão.')
            return
        elif clicked:
            print('   [tab] tab da mão fechada (Ctrl+F4 + Don\'t Save).')
        else:
            print('   [WARN] [tab] diálogo Save Resource não tratado — a tab pode '
                  'ter ficado aberta (o reinício a cada %d limita a acumulação).'
                  % _RESTART_EVERY_N_HANDS)
        # pt69 — repor a pré-condição de foco do open_wizard (chord da próxima mão).
        _restore_hrc_main_focus()
    except Exception as e:
        print('   [WARN] _close_hand_tab: %s' % e)


def _scan_handsetup_window(poll_s=6.0, interval=0.5):
    """pt70 (#OPEN-WIZARD-CHORD-FALLBACK-BLIND): devolve o OBJECTO da janela
    top-level cujo titulo contem 'Hand Setup' (o sinal autoritario que o
    open_wizard OG usa para confirmar o wizard), ou None apos `poll_s`.

    Gemeo do `_wizard_window_present` (pt29) mas devolve a janela em vez de bool
    — para o `_open_wizard_confirmed` obter o wpos da janela REAL, nunca o
    WizardPos FABRICADO pelo fallback cego do open_wizard. Foi exactamente este
    sinal que discriminou a smoke pt69 (mao 1 enumerou 'Hand Setup'; mao 2
    nunca, em 2 retries) — logo e a base correcta da confirmacao.
    """
    t0 = time.time()
    while time.time() - t0 < poll_s:
        try:
            windows = pyautogui.getAllWindows()
        except Exception as _e:
            windows = None
        if windows:
            for w in windows:
                if 'Hand Setup' in (getattr(w, 'title', '') or ''):
                    return w
        time.sleep(interval)
    return None


def _open_wizard_confirmed(hh_text):
    """pt70 (#OPEN-WIZARD-CHORD-FALLBACK-BLIND): wrapper autoritario sobre o
    `open_wizard` OG. O OG, ao fim de 2 chords Ctrl+W,M falhados, DESISTE e
    devolve um WizardPos FABRICADO ('Wizard assumed at ...') sem confirmar que o
    wizard abriu — o pipeline a jusante opera entao contra a janela principal
    'HRC Pro' (cola/navega no vazio, export cancela, zip nunca nasce, deadlock
    no loop Activas). Provado na smoke pt69: mao 1 OK; mao 2 (logo apos o fecho
    de aba) `Wizard assumed`, foreground 'HRC Pro' a mao toda, hwnd_wizard=None.

    Causa provada pelo log: o comando do chord NAO disparou na mao 2 — a janela
    'Hand Setup' nunca foi enumerada em 2 retries x 4s (refuta 'wizard atras' e
    'timing de deteccao'; em mao 1 os mesmos sleeps funcionaram). O diferenciador
    vs cold start e o estado de foco/contexto do chord multi-stroke SWT
    pos-fecho-de-aba; o `_restore_hrc_main_focus` (pt69) repos o foreground mas
    nao o contexto do chord — necessario, nao suficiente.

    Escada (cold start = unico estado 100% fiavel; prova empirica: mao 1 e todo
    cold start sempre abriu):
      rung 0: open_wizard (gesto OG) + confirma via janela 'Hand Setup' REAL.
      rung 1: Esc (limpa chord meio-entrado / modal residual) + repor foco
              (`_restore_hrc_main_focus`) + novo open_wizard.
      rung 2: `_restart_hrc` + `_wait_hrc_responsive` + re-armar clipboard com a
              HH (auto-import do HRC no cold start) + zerar o contador de higiene
              + novo open_wizard no HRC fresco.
      rung 3: nem o cold start abriu -> None. `setup_hand` ja trata (guard
              `if not win`): bail LIMPO, sem deadlock; o adapter marca `.failed`.

    O WizardPos fabricado do OG e SEMPRE descartado — confiamos so na janela
    real devolvida pelo `_scan_handsetup_window`. `hh_text` e parametro (e local
    do `setup_hand`) porque o rung 2 re-arma o clipboard para o auto-import.
    """
    for attempt in range(3):
        try:
            open_wizard()  # gesto best-effort; retorno (incl. WizardPos fabricado) ignorado
        except Exception as _e:
            print('   [WARN] _open_wizard_confirmed: open_wizard levantou %s' % _e)
        win = _scan_handsetup_window()
        if win is not None:
            try:
                win.activate()
            except Exception:
                pass
            if attempt > 0:
                print('   [wizard] wizard confirmado no rung %d.' % attempt)
            return win
        if attempt == 0:
            print('   [WARN] [wizard] chord falhou (janela "Hand Setup" nao '
                  'confirmada) — Esc + repor foco + re-chord.')
            try:
                pyautogui.press('escape')
            except Exception:
                pass
            time.sleep(0.4)
            _restore_hrc_main_focus()
            continue
        if attempt == 1:
            print('   [WARN] [wizard] chord falhou 2x — a reiniciar o HRC '
                  '(cold start e o unico estado 100%% fiavel).')
            _restart_hrc()
            _wait_hrc_responsive()
            globals()['_HANDS_DONE_SINCE_RESTART'] = 0
            try:
                _set_clipboard_with_verify(hh_text)
            except Exception as _e:
                print('   [WARN] _open_wizard_confirmed re-armar clipboard: %s' % _e)
            continue
    print('   [ERRO] [wizard] nem o cold start abriu o wizard — bail limpo da mao.')
    return None


def setup_hand(hand_name, hand_path):
    """Fase 1 do watcher: wizard -> calcular -> queue export.

    Retorna o path do `export_zip` se chegou ao fim do wizard, ou False se
    bailou cedo (HH ausente / HRC não iniciou / wizard não encontrado).

    pt23 fix A+B+C: lê hints `equity_model`/`max_players`/`script_path` de
    payouts.json (escritos pelo backend `services/queue_export.py`) e
    despacha para `set_equity_model`/`set_hand_mode_players`/`setup_scripting`.
    Restante fluxo idêntico ao original — confirmado linha-a-linha contra
    `setup_hand_dis.txt` (665 linhas bytecode).

    pt68: + log a ficheiro (change 3) + reinício do HRC a cada N mãos com
    health-check (change 2) + fecho da tab após export (change 1).
    """
    _ensure_file_logging()  # pt68 change 3 — espelha consola para ficheiro
    # pt84 (#HRC-HANG-WATCHDOG): regista a mão a decorrer (o vigia marca-a .failed
    # sem threading o path) + reseta o timer de hung-sustido por mão.
    globals()['_CURRENT_HAND_PATH'] = hand_path
    globals()['_WATCHDOG_HUNG_SINCE'] = None
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
    # quando há hint `script_path` no meta.json (pt42d)
    custom_script = None
    for fname in os.listdir(hand_path):
        if fname.endswith('.js'):
            custom_script = os.path.join(hand_path, fname)
            print(f'   Script custom: {fname}')

    # === pt23 fix A/B/C (revisto pt42d): hints lidos de `meta.json` em vez
    # de `payouts.json` (HRC rejeita campos extra no payouts.json — pt42d
    # #WN-BOUNTY-NULL-IN-HRC-PIPELINE v2). `hand_meta` já carregado acima
    # (linha ~1749) com defensivo `{}` quando meta.json ausente.
    equity_model = hand_meta.get('equity_model', 'multi_table_icm')
    max_players = hand_meta.get('max_players')
    if max_players is None:
        max_players = players_in_hand
    script_path = hand_meta.get('script_path')
    # === end pt23 (pt42d revisto) ===

    # arrancar HRC
    # pt68 change 2 — reiniciar o HRC a cada N mãos (higiene de memória contra a
    # acumulação de tabs). O reinício corre ANTES do ensure_hrc, que depois
    # encontra (ou relança) o HRC fresco.
    # pt79 (#HRC-RESTART-POST-WINDOW-FAILURE): + reiniciar quando a mão ANTERIOR
    # falhou DEPOIS de o wizard abrir (cálculo/finish/export). Generaliza o
    # restart da rung 2 (que só cobre wizard-NÃO-abriu). O bail limpo de
    # wizard-não-abriu NÃO marca _HRC_WINDOW_DIRTY → sem restart duplicado.
    # Loop guard: a mão falhada é sempre marcada .failed e a fila avança; o
    # restart é 1x por mão (aqui, no arranque) — nunca um ciclo de restart sem fim.
    _post_window_dirty = globals().get('_HRC_WINDOW_DIRTY', False)
    if _post_window_dirty or _HANDS_DONE_SINCE_RESTART >= _RESTART_EVERY_N_HANDS:
        _why = ('mão anterior falhou pós-abertura-de-janela (cálculo/finish/export)'
                if _post_window_dirty
                else '%d mãos desde o último reinício (>= %d)'
                     % (_HANDS_DONE_SINCE_RESTART, _RESTART_EVERY_N_HANDS))
        print('   [HRC-RESTART] %s — a reiniciar o HRC...' % _why)
        _restart_hrc()
        globals()['_HANDS_DONE_SINCE_RESTART'] = 0
        globals()['_HRC_WINDOW_DIRTY'] = False
        # _wait_hrc_responsive corre logo abaixo (health-check pós-arranque).
    hrc = ensure_hrc()
    if not hrc:
        print('   ERRO: HRC Pro não iniciou!')
        return False
    # pt68 change 2b — health-check (mitiga o cold-start race do setup-failed
    # 02:14): esperar o HRC responsivo + grace ANTES do 1º setup.
    _wait_hrc_responsive()

    # pt28-v3 (#PASTE-FAILED-HRC-REJECTED-CLIPBOARD root cause):
    # Smoke pt28-v2 expos que o HRC le o clipboard automaticamente quando
    # `open_wizard()` abre o wizard "New Hand". Se nesse momento o
    # clipboard tem lixo (e.g. comando PowerShell que o Rui colou para
    # arrancar o robot), o HRC dispara popup azul "Hand Import: No valid
    # hand-history found" -- foreground passa a ser o popup e o paste
    # manual subsequente nao recupera (Ctrl+V vai para o popup, nao para
    # o campo HH).
    # Mitigacao: preparar clipboard com HH valido ANTES de abrir o
    # wizard. HRC auto-importa o clipboard limpo e o popup nunca aparece.
    print('   A preparar clipboard com HH (pre-open-wizard)...')
    _set_clipboard_with_verify(hh_text)

    print('   A abrir wizard...')
    # pt70 (#OPEN-WIZARD-CHORD-FALLBACK-BLIND): confirmacao autoritaria via
    # janela 'Hand Setup' real + escada re-chord -> restart -> bail. O OG
    # devolvia um WizardPos fabricado ('Wizard assumed') quando o chord falhava
    # pos-fecho-de-aba -> deadlock. hh_text passa para o rung 2 re-armar o
    # clipboard apos restart.
    win = _open_wizard_confirmed(hh_text)
    if not win:
        print('   ERRO: Wizard não encontrado!')
        return False

    # pt79 (#HRC-RESTART-POST-WINDOW-FAILURE): a partir daqui o wizard ESTÁ aberto
    # — qualquer falha pós-abertura (popup HRC / paste / finish / cálculo / export
    # / scope) deixa o HRC potencialmente sujo. Marca dirty; só se LIMPA no fim
    # de sucesso (abaixo). O bail `if not win` acima NÃO chega aqui → não marca
    # dirty (a rung 2 já tratou o wizard-não-abriu) → sem restart duplicado.
    globals()['_HRC_WINDOW_DIRTY'] = True

    # pt79 — HOOK DE INDUÇÃO do re-smoke (one-shot por processo). Se activado
    # (env HRC_WATCHER_SMOKE_FAIL_FIRST ou flag _SMOKE_FAIL_FIRST), levanta o
    # RuntimeError pós-janela LOGO AQUI (wizard já aberto) na 1ª mão →
    # determinístico, independente da árvore. As mãos seguintes NÃO disparam
    # (one-shot) → a 2ª reinicia (via _HRC_WINDOW_DIRTY acima) E processa limpa,
    # provando a auto-cura. Inerte em produção (env unset + flag False).
    if (not globals().get('_SMOKE_FAIL_FIRST_FIRED', False)
            and (_SMOKE_FAIL_FIRST or os.environ.get('HRC_WATCHER_SMOKE_FAIL_FIRST'))):
        globals()['_SMOKE_FAIL_FIRST_FIRED'] = True
        print('   [SMOKE] hook one-shot ACTIVO — a forçar falha pós-janela na 1ª '
              'mão (re-smoke do [HRC-RESTART]). Inerte em produção.')
        raise RuntimeError(
            'WIZARD_FINISH_NEVER_RE_ENABLED: SMOKE pt79 one-shot (pós-abertura-de-janela)'
        )

    wpos = get_win_pos(win)

    # pt28-v3 guard: se o HRC ainda assim disparou popup azul (clipboard
    # estava preparado mas HRC rejeitou na mesma -- HH realmente
    # invalido, ou bug HRC), bail loud antes de paste_hh tocar em foco.
    popup_after_open = _detect_hand_import_error_popup()
    if popup_after_open is not None:
        print(f'   [ERROR] setup_hand: HRC rejected prepared clipboard '
              f'(post-open-wizard popup detected title={popup_after_open[4]!r}). '
              f'Raising loud.')
        _close_hand_import_error_popup(popup_after_open)
        raise RuntimeError('PASTE_FAILED_HRC_REJECTED_CLIPBOARD')

    print('   A colar HH...')
    paste_hh(wpos, hh_text)

    # pt23 fix B + fix A: hints substituem inputs do original
    set_hand_mode_players(wpos, max_players)        # original: players_in_hand
    set_equity_model(wpos, equity_model)            # original: stage

    if prize_path:
        print(f'   Prizes: {os.path.basename(prize_path)}')
        # pt66 (#HRC-BOUNTY-HARDCODED-50PCT): import_prizes carrega a estrutura
        # payouts.json e é o HRC que põe o Bounty Mode (PKO factor X / Mystery /
        # sem KO) a partir dela. O `select_bounty_mode` legacy corria A SEGUIR e
        # ESMAGAVA-o para um PKO 50% cego (só em KO) — errado para PKO 25%, Super
        # KO, etc. Removido: o modo da estrutura passa a prevalecer em todos os
        # formatos. is_ko_tournament/select_bounty_mode (Baltazar, no .pyc) ficam
        # órfãos no fluxo. Ver TECH_DEBTS pt62-pt64.
        import_prizes(wpos, prize_path)

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

    # pt30 (#WIZARD-FINISH-DISABLED-DURING-TREE-CALC): apos carregar o script,
    # o HRC dispara o calculo do tree size e DESABILITA o botao Finish ate
    # terminar. Aguardar a transicao enabled->disabled->enabled antes do
    # slow-click, senao o click cai num botao disabled (causa do smoke pt29-v3
    # falhar). Diagnostico SWT pt30 confirmou que o Win32 ve o Finish.
    _hwnd_wizard = getattr(win, '_hWnd', None) or _resolve_wizard_hwnd()
    _wait_for_finish_ready(_hwnd_wizard)

    # pt29 (#WIZARD-FINISH-NO-STATE-CHECK): forcar foco no wizard antes do
    # click Finish. Observacao visual no smoke pt29: rato na posicao correcta
    # do botao mas click sem efeito — comportamento classico do Windows com
    # janela inactiva (primeiro click activa, nao acciona controlo).
    # setup_scripting que vem antes fecha um Open dialog e pode deixar foco
    # fora do wizard.
    try:
        activated = False
        for w in pyautogui.getAllWindows():
            if 'Hand Setup' in (getattr(w, 'title', '') or ''):
                w.activate()
                activated = True
                time.sleep(0.3)  # dar tempo ao Windows para processar o focus change
                break
        if not activated:
            print('   [WARN] pre-Finish: janela "Hand Setup" nao encontrada para activate')
    except Exception as _e:
        print(f'   [WARN] activate wizard pre-Finish falhou ({_e})')

    # Logging defensivo do estado pre-click
    print(f'   [finish-diag pre-click] wpos={wpos}')
    try:
        fg = pyautogui.getActiveWindow()
        fg_info = f'hwnd={fg._hWnd} title={fg.title!r}' if fg else 'none'
    except Exception as _e:
        fg_info = f'getActiveWindow falhou ({_e})'
    print(f'   [finish-diag pre-click] foreground={fg_info}')

    # pt29-v2: HRC (Java) perde eventos de click instantaneo (foreground OK
    # no momento do click via pt29-v1 activate, mas wizard nao fechou; botao
    # visualmente normal + tree estavel, descartando Finish-greyed).
    # Substituir click_rel (mouse-down+up em <50ms) por slow-click:
    # moveTo + mouseDown + sleep + mouseUp, dando tempo a janela Java para
    # registar o press.
    abs_x = wpos[0] + BTN_FINISH[0]
    abs_y = wpos[1] + BTN_FINISH[1]

    print('   Finish...')
    pyautogui.moveTo(abs_x, abs_y, duration=0.1)
    time.sleep(0.1)
    pyautogui.mouseDown(button='left')
    time.sleep(0.15)  # janela Java tem tempo para registar o press
    pyautogui.mouseUp(button='left')
    time.sleep(1)  # pt67: settle mínimo p/ o slow-click registar (NÃO o sleep cego)

    # pt66 (#HRC-REDUNDANT-SECOND-RUN-OLD-CONFIGS): a 1ª run é lançada pelo
    # próprio Finish (slow-click acima) — spec canónico (WATCHER_FLUXO). O
    # `start_calculation(ci_target)` redundante foi removido em pt66: vamos
    # DIRETO do fim da 1ª run ao navigate + Selected Subtree (exatamente 2 runs).
    #
    # pt67 (#HRC-RUN-WINDOW-DETECTION-BLIND): SEM sleep cego. O sleep(30) antigo
    # engolia runs curtas (~5s): a janela "Hand Setup" pós-Finish MORFA na run
    # (mesmo título/hwnd) sem fechar, aparecia e morria durante o sleep, e o
    # run-wait declarava "nunca apareceu". Agora vigiamos DESDE o Finish (poll
    # 0.5s, tracking por hwnd) — ver `_wait_for_run_completion`. Também removido
    # o check `_wizard_window_present` ("wizard fechou") — com o morph a janela
    # NÃO fecha, o check era enganador. ⚠️ NUNCA "Always run in background" no
    # HRC (esconde as janelas; runbook §2.7).
    print('   A aguardar fim da 1ª run (lançada pelo Finish; vigia desde o Finish)...')
    _run1_t0 = time.time()
    _wait_for_run_completion(
        timeout_total_s=7200, run_label="1ª run",
        match_substring=("Hand Setup", "Monte Carlo Sampling"),
    )
    print('   1ª run terminou.')
    _merge_meta_json({"solve_seconds": round(time.time() - _run1_t0, 1)})  # pt90

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
    #   4. (Bug H) Finalize -> export zip.
    #
    # Defensive completo: cada passo tem fallback se algum coord ainda
    # estiver placeholder ou se popup detection falhar. O watcher degrada
    # para no-op com WARN logs em vez de cliques errantes.
    aggressor_real_action = hand_meta.get('aggressor_real_action')
    target_node_offset = hand_meta.get('target_node_offset')
    second_run_dispatched = None  # None = não tentada; True/False = resultado
    if aggressor_real_action is not None:
        # Bug J — Prune Action downstream. CALIBRAÇÃO PENDENTE -> comentado.
        # for line_coords in _enumerate_downstream_lines(wpos):
        #     prune_action_on_line(wpos, line_coords)

        # Navegação até linha do raiser real (#WATCHER-BUG-G-NAV).
        # pt61: passa aggressor_real_action p/ log do nó esperado (read-back visual).
        navigate_to_target_node(wpos, target_node_offset, aggressor_real_action)

        # 2ª run em Selected Subtree (popup Nash gere fill CI + scope + OK).
        print('   A calcular (2ª run, Selected Subtree)...')
        second_run_dispatched = start_calculation_selected_subtree(wpos, 10.0)

        # pt61: Scope não confirmado → ABORTA a mão (sem OK, sem export) para
        # não gerar um Full-Tree disfarçado de Selected Subtree na biblioteca de
        # estudo. `return None` → `try_setup` (main loop) marca a pasta `.failed`
        # e avança para a mão seguinte; o adaptador posta o failed e limpa a
        # pasta (sem loop). NÃO bloqueia a fila.
        if second_run_dispatched == "scope_unconfirmed":
            print('   [ABORT] %s: Scope não confirmado — 2ª run abortada, mão '
                  'marcada FALHADA (sem export). Avança para a seguinte.'
                  % hand_name)
            return None

    # pt28 (#FINALIZE-NEVER-FIRES-ON-NO-OP): se a 2ª run foi tentada mas
    # falhou (popup Nash não detectado), avisar antes do finalize — o zip
    # exportado será da 1ª run apenas, não da 2ª run em Selected Subtree.
    # Sem este WARN o failure era silencioso (cenário pt27 GG-5944816316:
    # `finalize_after_second_run` corria sempre e exportava o que estivesse).
    if second_run_dispatched is False:
        print(f'   [WARN] {hand_name}: 2ª run não disparou (popup Nash '
              'não abriu); finalize vai exportar zip da 1ª run apenas')
    elif second_run_dispatched is True:
        # pt29-v3 follow-up + pt31: a 2a run tambem so DISPARA
        # (start_calculation_selected_subtree nao bloqueia). Esperar a 2a run
        # terminar antes do export, senao o zip sai com resultados parciais.
        # Mesmo padrao da 1a run (janela de progresso 'Hand Setup'). Só quando
        # a 2a run foi de facto disparada (True) — em False (popup nao abriu)
        # ou None (sem aggressor) o estado vigente e o da 1a run, ja terminada
        # pelo wait acima. Timeout 8h (Selected Subtree pode demorar horas).
        # pt66: salvaguarda SÓ-LEITURA do CI (o watcher já não o escreve) —
        # avisa se o "Target CI" da run ≠ 10 (default do HRC mudado à mão).
        _ci_target_readback_warn(10.0)
        print('   A aguardar fim da 2ª run...')
        # pt34 v1: a 2a run tem janela de progresso "H-<hand_id>: Monte Carlo
        # Sampling" (nao "Hand Setup"); match por substring.
        _wait_for_run_completion(
            timeout_total_s=28800, run_label="2ª run",
            match_substring="Monte Carlo Sampling",
        )
        print('   2ª run terminou.')

    # Bug H: finalize após 2ª run (ou skip da 2ª run se sem aggressor,
    # ou após WARN se 2ª run falhou em pt28).
    saved = finalize_after_second_run(wpos, export_zip)
    # === FIM Bloco 2 piece 2 ===

    # pt87 — fechar a tab é seguro AGORA: a barreira de persistência+integridade
    # (_verify_export_zip dentro do _save_as_set_and_click) já bloqueou até o zip
    # existir+íntegro (ou desistir após retry), logo o Ctrl+F4 já não corre contra
    # o write. Fecha em ambos os casos (no falhado não há nada a perder).
    _close_hand_tab()
    # pt68 change 2 — contar a mão processada (gatilho do reinício a cada N).
    globals()['_HANDS_DONE_SINCE_RESTART'] = _HANDS_DONE_SINCE_RESTART + 1
    print('   [hrc-hygiene] mãos desde o último reinício: %d/%d'
          % (_HANDS_DONE_SINCE_RESTART, _RESTART_EVERY_N_HANDS))

    # pt79: fim LIMPO — o HRC não ficou sujo; cancela o restart-antes-da-próxima.
    globals()['_HRC_WINDOW_DIRTY'] = False

    # pt87 — só [QUEUED] se o zip está mesmo no disco e íntegro. Senão devolve
    # None → try_setup (main loop) marca .failed e o watcher AVANÇA (sem congelar
    # à espera de um zip inexistente; EXPORT_WAIT_TIMEOUT cobre o handshake).
    if not saved:
        print('   [WARN] %s: export NAO persistiu/integro apos retry — mao '
              'marcada FALHADA (sem [QUEUED]); watcher avanca.' % hand_name)
        return None

    print(f'   [QUEUED] {hand_name} -> {os.path.basename(export_zip)} '
          f'(Bloco 1 — finalize Bloco 2)')
    return export_zip
