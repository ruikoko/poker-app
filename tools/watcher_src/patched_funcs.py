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

# ── pt61 (#HRC-2ND-RUN-BLIND-CLICKS) — Scope/CI via Win32 (não pyautogui) ──
# O popup Nash (#32770) tem os widgets como child windows nativas (pt33). Os
# cliques pyautogui de Scope/opção/CI não registam de forma fiável neste popup
# SWT/Java (só o OK via BM_CLICK funcionava). Passa-se Scope e CI a Win32, à
# imagem do combo do export_strategies (pt35), com read-back de verificação.
CB_GETCOUNT = 0x0146       # nº de itens no ComboBox
CB_GETLBTEXT = 0x0148      # texto do item i (para achar o combo "Selected Subtree")
CB_GETLBTEXTLEN = 0x0149   # comprimento do texto do item i
WM_SETTEXT = 0x000C        # escrever texto num Edit (CI Target)
WM_GETTEXT = 0x000D        # ler texto de um Edit (read-back do CI)
WM_GETTEXTLENGTH = 0x000E

_FINISH_WAIT_PHASE1_TIMEOUT_S = 5.0    # aguardar Finish disabled (calc arrancou)
_FINISH_WAIT_PHASE2_TIMEOUT_S = 60.0   # aguardar Finish re-enabled (calc terminou)
_FINISH_WAIT_POLL_S = 0.1


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
# legacy do Baltazar), `_set_ci_target_common`, `_fill_ci_target_in_popup`
# (já em patched_funcs). O `start_calculation` legacy (1ª run, dentro do
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
        time.sleep(_FINISH_WAIT_POLL_S)
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
            print('   [finish-wait] tree estavel em %.1fs (Finish enabled)'
                  % (time.time() - f2_start))
            return
        time.sleep(_FINISH_WAIT_POLL_S)
    raise RuntimeError(
        'WIZARD_FINISH_NEVER_RE_ENABLED: calculo do tree size nao terminou '
        'em %.0fs (Finish ficou disabled)' % _FINISH_WAIT_PHASE2_TIMEOUT_S
    )


_RUN_WAIT_POLL_S = 0.5
_RUN_WAIT_PROGRESS_LOG_S = 60.0


def _find_progress_window_title(match_substring=None):
    """pt34 v1: devolve o titulo COMPLETO da janela de progresso do HRC, ou
    None se nao existir.

    - `match_substring=None` -> match exacto "Hand Setup" via FindWindowW
      (comportamento pt31, usado pela 1a run cujo titulo de progresso e'
      "Hand Setup").
    - `match_substring` preenchido -> substring case-insensitive sobre os
      titulos top-level via EnumWindows (2a run: o HRC mostra
      "H-<hand_id>: Monte Carlo Sampling", nao "Hand Setup").

    Devolve o titulo (str) em vez de bool para logging diagnostico (o titulo
    pode mudar entre versoes do HRC).
    """
    if match_substring is None:
        if _pt30_user32.FindWindowW(None, "Hand Setup"):
            return "Hand Setup"
        return None
    needle = match_substring.lower()
    found = []

    def _enum_top(hwnd, lparam):
        n = _pt30_user32.GetWindowTextLengthW(hwnd)
        if n > 0:
            buf = ctypes.create_unicode_buffer(n + 1)
            _pt30_user32.GetWindowTextW(hwnd, buf, n + 1)
            if needle in buf.value.lower():
                found.append(buf.value)
                return False  # encontrado — para a enumeracao
        return True

    _pt30_user32.EnumWindows(_PT30_WNDENUMPROC(_enum_top), 0)
    return found[0] if found else None


def _wait_for_run_completion(timeout_appear_s=30, timeout_total_s=7200,
                             run_label="run", match_substring=None):
    """pt31 (#WAIT-FOR-CALCULATION-FALSE-POSITIVE-MEMORY-HEURISTIC): aguarda
    uma run do HRC terminar via polling Win32 da janela top-level de PROGRESSO
    (a que o HRC mostra durante o calculo). Sinal binario, sem heuristica —
    substitui `wait_for_calculation` (memoria), que dava falso positivo (smoke
    pt30: declarou fim aos 48s mas a run ainda corria).

    pt34 v1: `match_substring` distingue 1a vs 2a run. A 1a run usa o titulo
    exacto "Hand Setup" (match_substring=None); a 2a run usa substring
    "Monte Carlo Sampling" porque a janela de progresso da 2a run tem titulo
    "H-<hand_id>: Monte Carlo Sampling", nao "Hand Setup" (confirmado visual
    no Beelink, smoke pt33 v1: sem isto a fase 1 dava falso negativo aos 30s e
    o robot avancava para o Save As com a 2a run ainda a correr).

    IMPORTANTE — assume que o wizard 'Hand Setup' de CONFIGURACAO ja fechou
    (chamada apos `start_calculation`). Para a 1a run, a janela de progresso
    reutiliza o titulo 'Hand Setup' do wizard; se esta funcao for chamada com
    o wizard ainda aberto, o polling detecta-o falsamente. Sequencia correcta:
        Finish -> wizard fecha -> Sleep(30) -> set_ci_initial ->
        start_calculation -> _wait_for_run_completion AQUI.

    Fase 1 (timeout_appear_s, default 30s): aguardar a janela aparecer
      (run arrancou). Se nao aparecer = run trivial ou erro; WARN e devolve
      graceful (mesmo padrao do pt30).
    Fase 2 (timeout_total_s): pollar enquanto a janela existir; quando
      desaparecer = run terminou. Log periodico de minuto-a-minuto. Timeout
      = run preso; raise RuntimeError.
    """
    # Fase 1: aguardar a janela de progresso aparecer.
    appear_deadline = time.time() + timeout_appear_s
    appeared_title = None
    while time.time() < appear_deadline:
        appeared_title = _find_progress_window_title(match_substring)
        if appeared_title is not None:
            break
        time.sleep(_RUN_WAIT_POLL_S)
    if appeared_title is None:
        print('   [WARN] [run-wait] %s: janela de progresso nao apareceu em '
              '%ds — run trivial ou erro; a continuar'
              % (run_label, timeout_appear_s))
        return
    print('   [run-wait] %s: janela detectada title=%r'
          % (run_label, appeared_title))

    # Fase 2: aguardar a janela desaparecer (run terminou).
    f2_start = time.time()
    deadline = f2_start + timeout_total_s
    next_log = f2_start + _RUN_WAIT_PROGRESS_LOG_S
    while time.time() < deadline:
        if _find_progress_window_title(match_substring) is None:
            elapsed = time.time() - f2_start
            print('   [run-wait] %s: run terminou em %.0fs (%.1f min)'
                  % (run_label, elapsed, elapsed / 60.0))
            return
        now = time.time()
        if now >= next_log:
            mins = int((now - f2_start) / 60.0)
            print('   [run-wait] %s: ainda a correr ha %d minutos'
                  % (run_label, mins))
            next_log = now + _RUN_WAIT_PROGRESS_LOG_S
        time.sleep(_RUN_WAIT_POLL_S)
    raise RuntimeError(
        'RUN_NEVER_COMPLETED: %s nao terminou em %ds'
        % (run_label, timeout_total_s)
    )


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
    clipboard_safe_paste(str(float(value)))  # pt29: set+verify+Ctrl+V atómico
    time.sleep(0.2)                          # preserva timing legacy pós-paste
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
# ⚠️ pt61: estes pixels-rel são apenas BASELINE/FALLBACK. O caminho activo do
# Scope e do CI passou a ser **Win32** (CB_SETCURSEL / WM_SETTEXT + read-back),
# que NÃO depende de coords (ver `_set_scope_in_popup` / `_fill_ci_target_in_popup`).
# A calibração pt61 (popup 436×230) mostrou que mesmo com as coords certas o
# clique pyautogui não selecciona neste popup → o fix real é o método, não a
# coord. Estes valores ficam só para o fallback pyautogui se o Win32 falhar.
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


# pt25e Bloco 2 piece 2 — CI Target dentro do popup Nash. BASELINE/FALLBACK
# (caminho activo = Win32 WM_SETTEXT; ver nota acima). Calibração pt61 436×230.
CI_TARGET_POPUP_REL_X = 297
CI_TARGET_POPUP_REL_Y = 108


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
        time.sleep(poll_interval)
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


def _fill_ci_target_in_popup(popup_rect, ci_target):
    """Preenche o CI Target no popup Nash — pt61: via Win32 (WM_SETTEXT) com
    read-back (WM_GETTEXT). Conservador: só usa Win32 se houver EXACTAMENTE 1
    controlo Edit no popup (= o CI Target, inequívoco); senão cai no fallback
    pyautogui (baseline coords pt61). NÃO depende de coords no caminho activo.

    Passo 3 do flow (após `_set_scope_in_popup`). Devolve `True` SÓ se o
    read-back confirmar o valor; `False` caso contrário (Win32 falhou e fallback
    pyautogui não é confirmável). `popup_rect` é usado SÓ pelo fallback.
    """
    # Inteiro sem ".0" (o Edit do HRC aceita "10"); fracção preserva o float.
    target = (str(int(ci_target)) if float(ci_target).is_integer()
              else str(float(ci_target)))
    hwnd_popup = _find_nash_popup_hwnd()
    edit = _find_single_edit(hwnd_popup) if hwnd_popup else None
    if edit:
        sbuf = ctypes.create_unicode_buffer(target)
        _pt30_user32.SendMessageW(edit, WM_SETTEXT, 0, ctypes.addressof(sbuf))
        time.sleep(0.2)
        got = _read_edit_text(edit).strip()
        if got == target:
            print('   [ci] Win32 WM_SETTEXT "%s" confirmado (read-back)' % target)
            return True
        print('   [WARN] [ci] read-back não bate (got=%r != %r) '
              '— fallback pyautogui' % (got, target))
    else:
        print('   [WARN] [ci] Edit único do CI não identificado '
              '— fallback pyautogui')
    # Fallback pyautogui (baseline coords pt61) — best-effort, NÃO confirmável.
    if popup_rect is None or CI_TARGET_POPUP_REL_X == 0:
        print('   [WARN] [ci] fallback indisponível (popup_rect/coords) '
              '— CI NÃO confirmado')
        return False
    left, top, _w, _h = popup_rect
    pyautogui.click(left + CI_TARGET_POPUP_REL_X, top + CI_TARGET_POPUP_REL_Y)
    time.sleep(0.3)
    pyautogui.hotkey('ctrl', 'a')
    time.sleep(0.1)
    clipboard_safe_paste(target)  # pt29: set+verify+Ctrl+V atómico
    time.sleep(0.2)
    print('   [ci] fallback pyautogui aplicado (NÃO confirmado por read-back)')
    return False


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


def _find_combo_with_item(hwnd_popup, item_text_lower):
    """pt61: enumera os ComboBox filhos do popup Nash e devolve `(hwnd, idx)` do
    PRIMEIRO combo que contém um item cujo texto normalizado == `item_text_lower`.

    No popup Nash há >1 ComboBox (CFR Algorithm, Scope, ...) — por isso achamos o
    Scope pelo CONTEÚDO ("Selected Subtree"), não pela ordem. `(None, None)` se
    nenhum combo tiver o item. Read-only (não muda selecção). Buffers passados a
    `CB_GETLBTEXT*` via `addressof` (lParam = LONG_PTR aceita o endereço)."""
    if not hwnd_popup:
        return (None, None)
    result = [None, None]

    def _enum(ch, lparam):
        cls_buf = ctypes.create_unicode_buffer(256)
        _pt30_user32.GetClassNameW(ch, cls_buf, 256)
        if cls_buf.value.lower() != "combobox":
            return True
        count = _pt30_user32.SendMessageW(ch, CB_GETCOUNT, 0, 0)
        count = count if isinstance(count, int) and count > 0 else 0
        for i in range(count):
            n = _pt30_user32.SendMessageW(ch, CB_GETLBTEXTLEN, i, 0)
            if not isinstance(n, int) or n <= 0:
                continue
            buf = ctypes.create_unicode_buffer(n + 1)
            _pt30_user32.SendMessageW(ch, CB_GETLBTEXT, i, ctypes.addressof(buf))
            if buf.value.strip().lower() == item_text_lower:
                result[0] = ch
                result[1] = i
                return False
        return True

    _pt30_user32.EnumChildWindows(hwnd_popup, _PT30_WNDENUMPROC(_enum), 0)
    return (result[0], result[1])


def _find_single_edit(hwnd_popup):
    """pt61: hwnd do ÚNICO controlo Edit do popup Nash (= o campo CI Target),
    ou None se houver 0 ou >1 Edits (ambíguo → caller cai no fallback pyautogui).
    Conservador de propósito: só usa Win32 no CI quando é inequívoco."""
    if not hwnd_popup:
        return None
    edits = []

    def _enum(ch, lparam):
        cls_buf = ctypes.create_unicode_buffer(256)
        _pt30_user32.GetClassNameW(ch, cls_buf, 256)
        if cls_buf.value.lower() == "edit":
            edits.append(ch)
        return True

    _pt30_user32.EnumChildWindows(hwnd_popup, _PT30_WNDENUMPROC(_enum), 0)
    return edits[0] if len(edits) == 1 else None


def _read_edit_text(hwnd_edit):
    """Texto actual de um Edit via WM_GETTEXT (read-back). '' se vazio/erro."""
    if not hwnd_edit:
        return ""
    n = _pt30_user32.SendMessageW(hwnd_edit, WM_GETTEXTLENGTH, 0, 0)
    n = n if isinstance(n, int) and n > 0 else 0
    if n == 0:
        return ""
    buf = ctypes.create_unicode_buffer(n + 1)
    _pt30_user32.SendMessageW(hwnd_edit, WM_GETTEXT, n + 1, ctypes.addressof(buf))
    return buf.value


def _set_scope_in_popup(popup_rect):
    """Muda o Scope no popup Nash para "Selected Subtree" — pt61: via Win32.

    Caminho activo (pt61, #HRC-2ND-RUN-BLIND-CLICKS): Win32. Acha o ComboBox do
    Scope pelo CONTEÚDO (item "Selected Subtree"), seta por índice via
    `CB_SETCURSEL`, notifica o popup (`WM_COMMAND`/`CBN_SELCHANGE`) e CONFIRMA
    por read-back (`CB_GETCURSEL`). NÃO depende de coords — o clique pyautogui
    não registava de forma fiável neste popup SWT (só o OK por `BM_CLICK`
    funcionava). Mesmo padrão do combo de `export_strategies` (pt35).

    Devolve `True` SÓ se o read-back confirmar "Selected Subtree". Em falha do
    Win32 (popup/combo não encontrados ou read-back não bate) tenta o fallback
    pyautogui (baseline coords pt61, best-effort) e devolve `False` — o caller
    deve abortar a 2ª run em vez de a correr em Full Tree silenciosamente.

    `popup_rect` (left, top, w, h) é usado SÓ pelo fallback pyautogui.
    """
    hwnd_popup = _find_nash_popup_hwnd()
    if hwnd_popup:
        combo, idx = _find_combo_with_item(hwnd_popup, "selected subtree")
        if combo and idx is not None:
            _pt30_user32.SendMessageW(combo, CB_SETCURSEL, idx, 0)
            ctrl_id = _pt30_user32.GetDlgCtrlID(combo)
            _pt30_user32.SendMessageW(
                hwnd_popup, WM_COMMAND,
                (CBN_SELCHANGE << 16) | (ctrl_id & 0xFFFF), combo)
            time.sleep(0.3)
            now = _pt30_user32.SendMessageW(combo, CB_GETCURSEL, 0, 0)
            if now == idx:
                print('   [scope] Win32 CB_SETCURSEL idx=%d confirmado '
                      '(read-back) — Scope: Selected Subtree' % idx)
                return True
            print('   [WARN] [scope] read-back falhou (now=%r != %d) '
                  '— fallback pyautogui' % (now, idx))
        else:
            print('   [WARN] [scope] ComboBox com item "Selected Subtree" '
                  'não encontrado — fallback pyautogui')
    else:
        print('   [WARN] [scope] popup Nash hwnd não encontrado '
              '— fallback pyautogui')
    # Fallback pyautogui (baseline coords pt61) — best-effort, NÃO confirmável.
    if popup_rect is None or SCOPE_DROPDOWN_REL_X == 0:
        print('   [WARN] [scope] fallback indisponível (popup_rect/coords) '
              '— scope NÃO confirmado')
        return False
    left, top, _w, _h = popup_rect
    pyautogui.click(left + SCOPE_DROPDOWN_REL_X, top + SCOPE_DROPDOWN_REL_Y)
    time.sleep(0.3)
    pyautogui.click(left + SCOPE_OPTION_SELECTED_SUBTREE_REL_X,
                    top + SCOPE_OPTION_SELECTED_SUBTREE_REL_Y)
    time.sleep(0.3)
    print('   [scope] fallback pyautogui aplicado (NÃO confirmado por read-back)')
    return False


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
      1. Click Calculate (abre popup).
      2. _set_scope_in_popup(popup_rect)            [pt28-v1: Scope PRIMEIRO]
      3. Fill CI Target no popup.                   [pt28-v1: CI DEPOIS]
      4. Click OK / Enter.

    pt28-v1 reordering: Scope -> CI -> OK (era CI -> Scope -> OK). Razão:
    suspeita de que ao mudar Scope DEPOIS de fill CI, o re-render do
    popup ao seleccionar "Selected Subtree" pode resetar o CI Target
    para o default do scope novo (10.0 vs 5.0). Pôr Scope primeiro
    garante que o re-render acontece antes do CI ser escrito, eliminando
    o vector. Sem mexer em coords — fix puramente de ordem. O smoke
    real seguinte valida; logging defensivo em `_set_scope_in_popup`
    regista coords absolutas para diagnóstico se ainda falhar.

    `wpos` é o win_pos do main HRC window (mesmo objecto que
    `start_calculation` recebe via globals). `ci_target` é o CI a usar na
    2ª run (default product: 10.0).

    Defensive em cada passo: se `_click_calculate_button` não tem coords
    (placeholder), `_wait_for_nash_popup` devolve None por timeout, e os
    helpers downstream (scope / fill CI / OK) fazem early-return. O flow
    inteiro degrada para no-op com WARN logs em vez de cliques errantes.

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
    # CI: não confirmar NÃO aborta (a run continua em Selected Subtree; só a
    # precisão pode ficar no default do HRC). Sinaliza e segue.
    ci_ok = _fill_ci_target_in_popup(popup_rect, ci_target)  # passo 3 (Win32 + read-back)
    if not ci_ok:
        print('   [WARN] [calc] CI Target NÃO confirmado — segue com o default do HRC')
    _click_ok_in_popup(popup_rect)                        # passo 4 (BM_CLICK)
    print('   start_calculation_selected_subtree(ci=%s) — 2ª run disparada '
          '(scope_ok=True ci_ok=%s)' % (ci_target, ci_ok))
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
    exp = ''
    if isinstance(aggressor_real_action, dict):
        exp = ' (esperado: %s %s %sbb)' % (
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
    export_strategies(export_zip)


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

    save_btn = _find_save_button(save_dlg)
    if save_btn:
        print('   [SAVE-AS] Save btn hwnd=%s -> BM_CLICK' % save_btn)
        _pt30_user32.SendMessageW(save_btn, BM_CLICK, 0, 0)
        time.sleep(1.5)
        return True
    print('   [SAVE-AS] Save btn nao encontrado, Enter')
    try:
        pyautogui.press("enter")
        time.sleep(1.5)
        return True
    except Exception as e:
        print('   [SAVE-AS] enter erro: %s' % e)
        return True


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
    _save_as_set_and_click(export_path)
    print('   [export] _save_as_set_and_click concluído: %s' % export_path)
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
    hrc = ensure_hrc()
    if not hrc:
        print('   ERRO: HRC Pro não iniciou!')
        return False

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
    win = open_wizard()
    if not win:
        print('   ERRO: Wizard não encontrado!')
        return False

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
    time.sleep(5)

    # WARN-only state check pos-click (pt29). Sem raise nesta versao: o smoke
    # mostra no log se o activate resolveu (sem WARN) ou se Finish ainda falha
    # (WARN -> hipotese de foco descartada, investigar greyed/timing).
    if _wizard_window_present():
        print('   [WARN] verify_wizard_finished: janela "Hand Setup" ainda presente '
              'apos click + activate — Finish ainda falhou. Hipotese de foco descartada.')
    else:
        print('   [finish-diag pos-click] OK — wizard fechou.')

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

    # pt31 (#WAIT-FOR-CALCULATION-FALSE-POSITIVE-MEMORY-HEURISTIC): esperar a
    # 1a run terminar via polling da janela 'Hand Setup' de progresso (sinal
    # binario), em vez de wait_for_calculation (memoria, falso positivo no
    # smoke pt30). start_calculation apenas DISPARA; nao bloqueia. Timeout 2h
    # (1a run = ~10M iteracoes + preparacao).
    print('   A aguardar fim da 1ª run...')
    _wait_for_run_completion(timeout_total_s=7200, run_label="1ª run")
    print('   1ª run terminou.')

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
    finalize_after_second_run(wpos, export_zip)
    # === FIM Bloco 2 piece 2 ===

    print(f'   [QUEUED] {hand_name} -> {os.path.basename(export_zip)} '
          f'(Bloco 1 — finalize Bloco 2)')
    return export_zip
