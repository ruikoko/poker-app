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


def _wait_for_run_completion(timeout_appear_s=30, timeout_total_s=7200,
                             run_label="run"):
    """pt31 (#WAIT-FOR-CALCULATION-FALSE-POSITIVE-MEMORY-HEURISTIC): aguarda
    uma run do HRC terminar via polling Win32 da janela top-level 'Hand Setup'
    de PROGRESSO (a que o HRC mostra durante o calculo). Sinal binario, sem
    heuristica — substitui `wait_for_calculation` (memoria), que dava falso
    positivo (smoke pt30: declarou fim aos 48s mas a run ainda corria).

    IMPORTANTE — assume que o wizard 'Hand Setup' de CONFIGURACAO ja fechou
    (chamada apos `start_calculation`). A janela de progresso reutiliza o
    mesmo titulo 'Hand Setup' do wizard; se esta funcao for chamada com o
    wizard ainda aberto, o polling detecta-o falsamente como janela de
    progresso. Sequencia correcta:
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
    appeared = False
    while time.time() < appear_deadline:
        if _pt30_user32.FindWindowW(None, "Hand Setup"):
            appeared = True
            break
        time.sleep(_RUN_WAIT_POLL_S)
    if not appeared:
        print('   [WARN] [run-wait] %s: janela de progresso nao apareceu em '
              '%ds — run trivial ou erro; a continuar'
              % (run_label, timeout_appear_s))
        return
    print('   [run-wait] %s: janela de progresso detectada, run a correr'
          % run_label)

    # Fase 2: aguardar a janela desaparecer (run terminou).
    f2_start = time.time()
    deadline = f2_start + timeout_total_s
    next_log = f2_start + _RUN_WAIT_PROGRESS_LOG_S
    while time.time() < deadline:
        if not _pt30_user32.FindWindowW(None, "Hand Setup"):
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
# Smoke devagar 2026-05-18 com Rui no Beelink contra popup Nash 416×214:
#   - Dropdown abs (944, 439); top-left popup (666, 372) -> rel (278, 67).
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
    """Preenche CI Target dentro do popup Nash. Pixels-rel ao top-left do
    popup (convenção pt26; bloco de constantes acima). Valores derivados
    das fracções legacy `start_calculation` (Baltazar pt25d) sobre o popup
    416×214 do smoke 18 Maio.

    pt28-v1 reordering: agora **passo 3** do flow (após `_set_scope_in_popup`).
    Pré-condição: popup Nash aberto + Scope já = "Selected Subtree". Pôr CI
    depois do Scope garante que se o popup re-renderiza ao mudar Scope, o CI
    é escrito sobre o estado já estabilizado.

    Defensive: `popup_rect=None` -> early-return.

    Logging defensivo (pt28-v1): coord absoluta do click registada antes
    para permitir diagnóstico cruzado com screenshot pós-smoke.
    """
    if popup_rect is None:
        print('   [WARN] _fill_ci_target_in_popup: popup_rect ausente — fill ignorado')
        return
    left, top, _width, _height = popup_rect
    abs_x = left + CI_TARGET_POPUP_REL_X
    abs_y = top + CI_TARGET_POPUP_REL_Y
    print(f'   _fill_ci_target_in_popup: field click @ ({abs_x},{abs_y}) '
          f'[popup_rect=({left},{top},{_width},{_height}), '
          f'rel=({CI_TARGET_POPUP_REL_X},{CI_TARGET_POPUP_REL_Y})]')
    pyautogui.click(abs_x, abs_y)
    time.sleep(0.3)
    pyautogui.hotkey('ctrl', 'a')
    time.sleep(0.1)
    clipboard_safe_paste(str(float(ci_target)))  # pt29: set+verify+Ctrl+V atómico
    time.sleep(0.2)                              # preserva timing legacy pós-paste
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
    """Muda o dropdown Scope no popup Nash de "Full Tree" -> "Selected Subtree".

    Layout do popup Nash (validado por Rui em smokes pt25e/pt26):
      6 campos editáveis: CFR Algorithm, Scope, Run Sampling, CI Target,
      Reset Regret, Reset Strategies. 2 botões: OK | Cancel.
    O robot interage com apenas 2 campos (Scope, CI Target) + 1 botão (OK).
    Os outros 4 campos ficam nos defaults do HRC, que são apropriados para
    o nosso flow (CFR Algorithm = default; Run Sampling = default; Reset
    Regret/Strategies não-marcados — preservam estado da 1ª run para
    refinement em Selected Subtree).

    pt28-v1 reordering: esta função passa a ser o **passo 2** do flow
    (`start_calculation_selected_subtree`), ANTES de
    `_fill_ci_target_in_popup`. Razão: ao mudar Scope o popup pode
    re-renderizar e resetar campos editáveis ao default do scope novo;
    com Scope primeiro, qualquer reset acontece antes de escrevermos o
    CI Target.

    Pré-condição: popup Nash já aberto. Pós-condição: Scope = "Selected
    Subtree", pronto para fill CI + OK.

    `popup_rect` é `(left, top, width, height)` do popup Nash; caller é
    responsável pela detecção do rect. Coord absoluta de cada click é
    `(left + REL_X, top + REL_Y)` — pixels-rel ao top-left do popup
    (convenção pt26; ver bloco de constantes acima).

    Defensivos:
      - Qualquer REL == 0 -> coords não-calibrados -> early-return WARN.
      - popup_rect is None -> caller ainda não detecta popup -> early-return WARN.

    Logging defensivo (pt28-v1): regista coords absolutas de cada click
    no stdout. Permite diagnóstico cirúrgico em smoke real sem precisar
    de re-calibrar especulativamente as REL — basta cruzar as coords
    com screenshot do popup pós-smoke.

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
    print(f'   _set_scope_in_popup: dropdown click @ ({dropdown_x},{dropdown_y}) '
          f'[popup_rect=({left},{top},{_width},{_height}), '
          f'rel=({SCOPE_DROPDOWN_REL_X},{SCOPE_DROPDOWN_REL_Y})]')
    pyautogui.click(dropdown_x, dropdown_y)
    time.sleep(0.3)
    option_x = left + SCOPE_OPTION_SELECTED_SUBTREE_REL_X
    option_y = top + SCOPE_OPTION_SELECTED_SUBTREE_REL_Y
    print(f'   _set_scope_in_popup: option click @ ({option_x},{option_y}) '
          f'[rel=({SCOPE_OPTION_SELECTED_SUBTREE_REL_X},'
          f'{SCOPE_OPTION_SELECTED_SUBTREE_REL_Y})]')
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
    _set_scope_in_popup(popup_rect)                       # passo 2 (pt28-v1: era passo 3)
    _fill_ci_target_in_popup(popup_rect, ci_target)       # passo 3 (pt28-v1: era passo 2)
    _click_ok_in_popup(popup_rect)                        # passo 4

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


def navigate_to_target_node(wpos, target_node_offset):
    """pt25e Bloco 2 piece 2 — preme seta-para-baixo `target_node_offset`
    vezes para mover o cursor da Strategy Table HRC do default (1ª linha)
    até à linha do raiser real.

    `target_node_offset` é o campo `meta.json.target_node_offset` calculado
    pelo backend (`hrc_node_offset.compute_target_node_offset`).

    Defensive:
      - `None` ou `0` -> skip (cursor fica na 1ª linha; sem foco set
        para evitar interacções desnecessárias).
      - Inteiro negativo -> log WARN, skip.
      - Inteiro > 100 -> log WARN, skip (sanity; tabela com 100+ linhas
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
    print(f'   navigate_to_target_node: {target_node_offset} (down) presses')


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
    aggressor_real_action = _payouts.get('aggressor_real_action')
    target_node_offset = hand_meta.get('target_node_offset')
    second_run_dispatched = None  # None = não tentada; True/False = resultado
    if aggressor_real_action is not None:
        # Bug J — Prune Action downstream. CALIBRAÇÃO PENDENTE -> comentado.
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
    elif second_run_dispatched is True:
        # pt29-v3 follow-up + pt31: a 2a run tambem so DISPARA
        # (start_calculation_selected_subtree nao bloqueia). Esperar a 2a run
        # terminar antes do export, senao o zip sai com resultados parciais.
        # Mesmo padrao da 1a run (janela de progresso 'Hand Setup'). Só quando
        # a 2a run foi de facto disparada (True) — em False (popup nao abriu)
        # ou None (sem aggressor) o estado vigente e o da 1a run, ja terminada
        # pelo wait acima. Timeout 8h (Selected Subtree pode demorar horas).
        print('   A aguardar fim da 2ª run...')
        _wait_for_run_completion(timeout_total_s=28800, run_label="2ª run")
        print('   2ª run terminou.')

    # Bug H: finalize após 2ª run (ou skip da 2ª run se sem aggressor,
    # ou após WARN se 2ª run falhou em pt28).
    finalize_after_second_run(wpos, export_zip)
    # === FIM Bloco 2 piece 2 ===

    print(f'   [QUEUED] {hand_name} -> {os.path.basename(export_zip)} '
          f'(Bloco 1 — finalize Bloco 2)')
    return export_zip
