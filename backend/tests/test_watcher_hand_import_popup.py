"""pt28-v2 (#PASTE-FAILED-HRC-REJECTED-CLIPBOARD): tests para
`paste_hh` reagir ao popup "Hand Import: No valid hand-history found"
do HRC.

Smoke pt28-v1 (20 Maio 2026) expos cenario onde paste_hh marcou sucesso
mas HRC rejeitou o clipboard com popup azul. Robot ignorou-o e
configurou o resto do wizard (Equity Model / Bounty Mode / MTT Stacks /
Scripting) sobre dados FANTASMA da ultima mao em memoria. 1a corrida
arrancou sobre essa mao errada.

Mitigacao testada: apos clipboard_safe_paste, polla 800ms pelo popup
"Hand Import". Se encontrado:
  1. log defensivo (clipboard length/preview, foreground window)
  2. fecha popup via Enter
  3. retry 1x (re-click TEXT_AREA + select-all + paste)
  4. se popup persistir: raise RuntimeError("PASTE_FAILED_HRC_REJECTED_CLIPBOARD")

Mesmo padrao de path-injection que `test_watcher_set_scope.py` e
`test_watcher_clipboard_safe_paste.py`.
"""
import sys
import time as _real_time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

_HERE = Path(__file__).resolve().parent
_WATCHER_SRC = _HERE.parent.parent / "tools" / "watcher_src"
sys.path.insert(0, str(_WATCHER_SRC))


@pytest.fixture
def pf():
    """Carrega `patched_funcs` fresh + injecta mocks de globais.

    pyperclip eh stateful (igual a `test_watcher_set_scope.py`) para que
    clipboard_safe_paste dentro de _do_paste_hh_attempt sai do loop set+verify
    sem ir ate n_retries.

    Globais Win32 stub injectados: send_key / VK_CONTROL / VK_A para o
    select-all dentro de _do_paste_hh_attempt; TEXT_AREA para o 3-click.
    """
    if "patched_funcs" in sys.modules:
        del sys.modules["patched_funcs"]
    import patched_funcs as _pf  # noqa: E402
    _pf.click_rel = MagicMock(name="click_rel")
    _pf.pyautogui = MagicMock(name="pyautogui")
    # Default iteravel para getAllWindows — o bloco activate (pt29) e
    # _wizard_window_present iteram o resultado. Tests fazem override quando
    # precisam de janelas especificas.
    _pf.pyautogui.getAllWindows = MagicMock(return_value=[])

    _clipboard_state = {"value": ""}
    _pp = MagicMock(name="pyperclip")
    _pp.copy.side_effect = lambda text: _clipboard_state.__setitem__("value", text)
    _pp.paste.side_effect = lambda: _clipboard_state["value"]
    _pf.pyperclip = _pp

    _pf.send_key = MagicMock(name="send_key")
    _pf.VK_CONTROL = 0x11
    _pf.VK_A = 0x41
    _pf.TEXT_AREA = (100, 200)

    _pf.time = SimpleNamespace(
        time=_real_time.time,
        sleep=MagicMock(name="time.sleep"),
    )
    yield _pf


def _fake_popup_window(title="Hand Import", left=100, top=100, width=400, height=200):
    """Cria um pseudo-Window com a API de pygetwindow usada por
    _detect_hand_import_error_popup."""
    win = MagicMock()
    win.title = title
    win.left = left
    win.top = top
    win.width = width
    win.height = height
    return win


# == _detect_hand_import_error_popup ====================================

def test_detect_hand_import_error_popup_finds_window_by_title(pf):
    """Popup com title exacto "Hand Import" e dimensoes validas -> devolve
    rect + title."""
    popup_win = _fake_popup_window(title="Hand Import", left=200, top=300,
                                    width=420, height=180)
    pf.pyautogui.getAllWindows = MagicMock(return_value=[popup_win])

    rect = pf._detect_hand_import_error_popup(timeout=0.3)
    assert rect == (200, 300, 420, 180, "Hand Import")


def test_detect_hand_import_error_popup_matches_case_insensitively(pf):
    """Substring match case-insensitive (mesmo padrao que `_wait_for_nash_popup`)."""
    popup_win = _fake_popup_window(title="hand import - error",
                                    left=50, top=50, width=300, height=150)
    pf.pyautogui.getAllWindows = MagicMock(return_value=[popup_win])

    rect = pf._detect_hand_import_error_popup(timeout=0.3)
    assert rect is not None
    assert rect[:4] == (50, 50, 300, 150)
    assert "hand import" in rect[4].lower()


def test_detect_hand_import_error_popup_returns_none_on_timeout(pf):
    """Sem janela com hint match -> None apos timeout."""
    other = _fake_popup_window(title="HRC Pro - Main Window", width=800, height=600)
    pf.pyautogui.getAllWindows = MagicMock(return_value=[other])

    rect = pf._detect_hand_import_error_popup(timeout=0.2)
    assert rect is None


def test_detect_hand_import_error_popup_rejects_minimized_windows(pf):
    """Janela com width/height 0 (minimizada) eh ignorada mesmo com title match."""
    minimized = _fake_popup_window(title="Hand Import", width=0, height=0)
    pf.pyautogui.getAllWindows = MagicMock(return_value=[minimized])

    rect = pf._detect_hand_import_error_popup(timeout=0.2)
    assert rect is None


def test_detect_hand_import_error_popup_skips_empty_title(pf):
    """Janela sem titulo (compositor / system) ignorada."""
    empty = _fake_popup_window(title="", width=400, height=200)
    pf.pyautogui.getAllWindows = MagicMock(return_value=[empty])

    rect = pf._detect_hand_import_error_popup(timeout=0.2)
    assert rect is None


def test_detect_hand_import_error_popup_survives_getAllWindows_exception(pf):
    """getAllWindows raises (race condition) -> log WARN + retry; eventual None."""
    pf.pyautogui.getAllWindows = MagicMock(side_effect=RuntimeError("race"))
    rect = pf._detect_hand_import_error_popup(timeout=0.2)
    assert rect is None


# == _close_hand_import_error_popup =====================================

def test_close_hand_import_error_popup_presses_enter(pf):
    """OK do popup via Enter (Qt default-button)."""
    popup = (200, 300, 420, 180, "Hand Import")
    pf._close_hand_import_error_popup(popup)
    pf.pyautogui.press.assert_called_once_with('enter')


def test_close_hand_import_error_popup_handles_none(pf):
    """popup=None -> no-op (sem press)."""
    pf._close_hand_import_error_popup(None)
    pf.pyautogui.press.assert_not_called()


# == paste_hh com popup detection =======================================

def test_paste_hh_proceeds_when_no_popup_detected(pf):
    """Caminho feliz: popup nao aparece -> paste_hh retorna sem retry,
    sem raise. Exactamente 1 attempt."""
    pf.pyautogui.getAllWindows = MagicMock(return_value=[])

    # Spy em _do_paste_hh_attempt para contar tentativas
    attempt_log = []
    real_do_attempt = pf._do_paste_hh_attempt
    pf._do_paste_hh_attempt = MagicMock(
        side_effect=lambda wpos, hh, label: attempt_log.append(label)
    )

    pf.paste_hh(wpos=(0, 0, 1024, 768), hh_text="PokerStars Hand #123 ...")

    assert attempt_log == ["attempt-1"]


def test_paste_hh_retries_once_when_popup_detected_then_succeeds(pf, capsys):
    """Popup na 1a tentativa, nao na 2a -> retry, sem raise."""
    detect_calls = {"n": 0}

    def _detect():
        detect_calls["n"] += 1
        if detect_calls["n"] == 1:
            return (100, 100, 400, 200, "Hand Import")  # 1a tentativa: popup
        return None                                       # 2a: limpo

    pf._detect_hand_import_error_popup = MagicMock(side_effect=lambda *a, **kw: _detect())

    attempt_log = []
    pf._do_paste_hh_attempt = MagicMock(
        side_effect=lambda wpos, hh, label: attempt_log.append(label)
    )

    pf.paste_hh(wpos=(0, 0, 1024, 768), hh_text="PokerStars Hand #456 ...")

    # 2 attempts feitos
    assert attempt_log == ["attempt-1", "attempt-2-retry"]
    # Popup foi fechado entre as tentativas (Enter)
    pf.pyautogui.press.assert_called_with('enter')
    out = capsys.readouterr().out
    assert "HRC rejected clipboard" in out
    assert "retry succeeded" in out


def test_paste_hh_raises_when_popup_persists_after_retry(pf, capsys):
    """Popup em ambas as tentativas -> raise loud
    PASTE_FAILED_HRC_REJECTED_CLIPBOARD."""
    pf._detect_hand_import_error_popup = MagicMock(
        return_value=(100, 100, 400, 200, "Hand Import")
    )

    attempt_log = []
    pf._do_paste_hh_attempt = MagicMock(
        side_effect=lambda wpos, hh, label: attempt_log.append(label)
    )

    with pytest.raises(RuntimeError, match="PASTE_FAILED_HRC_REJECTED_CLIPBOARD"):
        pf.paste_hh(wpos=(0, 0, 1024, 768), hh_text="bad text")

    # Exactamente 2 tentativas antes do raise
    assert attempt_log == ["attempt-1", "attempt-2-retry"]
    out = capsys.readouterr().out
    assert "[ERROR]" in out
    assert "Raising loud" in out
    # 2 popups detectados -> 2 Enter presses para fechar antes do raise
    assert pf.pyautogui.press.call_count == 2


def test_paste_hh_does_not_retry_when_first_attempt_succeeds(pf):
    """Spy explicito: sem popup -> _do_paste_hh_attempt chamado uma vez,
    nao duas. Protege contra regressao que faca retry sempre."""
    pf._detect_hand_import_error_popup = MagicMock(return_value=None)
    pf._do_paste_hh_attempt = MagicMock()

    pf.paste_hh(wpos=(0, 0, 1024, 768), hh_text="ok text")

    assert pf._do_paste_hh_attempt.call_count == 1


# == _log_paste_diagnostics =============================================

def test_log_paste_diagnostics_writes_wpos_and_clipboard_preview(pf, capsys):
    """Log inclui wpos, foreground window titulo, clipboard length +
    preview. Tudo num formato grep-amigavel."""
    active = MagicMock()
    active.title = "HRC Pro"
    active._hWnd = 0x12345
    pf.pyautogui.getActiveWindow = MagicMock(return_value=active)

    # Coloca algo no clipboard via mock stateful
    pf.pyperclip.copy("some hand text here")

    pf._log_paste_diagnostics(wpos=(283, 65, 1050, 850),
                              hh_text="some hand text here", label="attempt-1")

    out = capsys.readouterr().out
    assert "[paste-diag attempt-1]" in out
    assert "wpos=(283, 65, 1050, 850)" in out
    assert "HRC Pro" in out
    assert "clipboard len=" in out
    assert "expected_len=" in out


def test_log_paste_diagnostics_tolerates_getActiveWindow_exception(pf, capsys):
    """Diagnostic log eh para diagnostico; nao deve crashar se getters
    falham (e.g., pygetwindow version sem API)."""
    pf.pyautogui.getActiveWindow = MagicMock(side_effect=RuntimeError("no window api"))
    pf.pyperclip.copy("text")

    # NAO deve raise
    pf._log_paste_diagnostics(wpos=(0, 0, 100, 100), hh_text="text", label="x")

    out = capsys.readouterr().out
    assert "[paste-diag x]" in out
    # foreground tem err placeholder
    assert "err" in out.lower() or "<err" in out


def test_log_paste_diagnostics_tolerates_no_active_window(pf, capsys):
    """getActiveWindow devolve None -> fallback gracioso."""
    pf.pyautogui.getActiveWindow = MagicMock(return_value=None)
    pf.pyperclip.copy("text")

    pf._log_paste_diagnostics(wpos=(0, 0, 100, 100), hh_text="text", label="x")

    out = capsys.readouterr().out
    assert "<none>" in out


def test_log_paste_diagnostics_truncates_clipboard_preview_to_80_chars(pf, capsys):
    """Preview limitado a 80 chars (HH text tem ~2-5 KB; nao queremos
    log spam)."""
    long_text = "A" * 500
    pf.pyperclip.copy(long_text)

    pf._log_paste_diagnostics(wpos=(0, 0, 100, 100), hh_text=long_text, label="x")

    out = capsys.readouterr().out
    # 80 A's no preview
    assert "A" * 80 in out
    # mas nao 81 (truncado)
    assert "A" * 81 not in out


# == pt28-v3: setup_hand wiring (clipboard prep + popup guard) ==========

def _make_minimal_hand_dir(tmp_path, name="GG-TEST-99999",
                            hh_body="PokerStars Hand #demo\n*** SUMMARY ***\n"):
    """Cria a estrutura minima de hand_path que setup_hand consegue ler:
    .txt + payouts.json opcional. Devolve hand_path como string."""
    hand_path = tmp_path / name
    hand_path.mkdir()
    (hand_path / f"{name}.txt").write_text(hh_body, encoding="utf-8")
    return str(hand_path)


def _stub_setup_hand_globals(pf, tmp_root_str):
    """Substitui todos os globais que setup_hand chama por stubs/spies.
    Reutilizado nos 2 tests pt28-v3 abaixo."""
    pf.ensure_hrc = MagicMock(return_value=True)
    pf.open_wizard = MagicMock(return_value="mock_win")
    pf.get_win_pos = MagicMock(return_value=(0, 0, 800, 600))
    pf.paste_hh = MagicMock()
    pf.set_hand_mode_players = MagicMock()
    pf.set_equity_model = MagicMock()
    pf.import_prizes = MagicMock()
    pf.is_ko_tournament = MagicMock(return_value=False)
    pf.select_bounty_mode = MagicMock()
    pf.handle_mtt_stacks_page = MagicMock()
    pf.setup_scripting = MagicMock()
    pf.start_calculation = MagicMock()
    pf.export_strategies = MagicMock()
    pf.SCRIPT_FILE = "fake_script.js"
    pf.BTN_NEXT = (1, 2)
    pf.BTN_FINISH = (3, 4)
    pf.DONE_DIR = tmp_root_str + "/OUT"


def test_setup_hand_prepares_clipboard_before_open_wizard_pt28v3(pf, tmp_path):
    """pt28-v3 root-cause fix: _set_clipboard_with_verify(hh_text) DEVE
    correr ANTES de open_wizard(). HRC le clipboard ao abrir o wizard;
    se ainda tem lixo, popup azul abre. Preparar clipboard primeiro
    elimina o vector."""
    _stub_setup_hand_globals(pf, str(tmp_path))

    call_order = []
    pf._set_clipboard_with_verify = MagicMock(
        side_effect=lambda *a, **kw: call_order.append("set_clipboard")
    )
    pf.open_wizard = MagicMock(
        side_effect=lambda *a, **kw: (call_order.append("open_wizard"), "mock_win")[1]
    )
    pf._detect_hand_import_error_popup = MagicMock(return_value=None)

    hand_path = _make_minimal_hand_dir(tmp_path)
    pf.setup_hand("GG-TEST-99999", hand_path)

    # _set_clipboard_with_verify chamado uma vez, ANTES de open_wizard
    assert "set_clipboard" in call_order
    assert "open_wizard" in call_order
    assert call_order.index("set_clipboard") < call_order.index("open_wizard"), (
        f"pt28-v3: clipboard deve ser preparado ANTES de open_wizard; got {call_order}"
    )
    # _set_clipboard_with_verify chamado com o hh_text completo
    pf._set_clipboard_with_verify.assert_called_once()
    (args, _kw) = pf._set_clipboard_with_verify.call_args
    assert "PokerStars Hand" in args[0]


def test_setup_hand_raises_when_popup_after_open_wizard_pt28v3(pf, tmp_path):
    """pt28-v3 guard: se o HRC ainda dispara popup azul mesmo com
    clipboard preparado (HH realmente invalido OU bug HRC), bail loud
    com PASTE_FAILED_HRC_REJECTED_CLIPBOARD ANTES de paste_hh tocar em foco."""
    _stub_setup_hand_globals(pf, str(tmp_path))

    pf._set_clipboard_with_verify = MagicMock()
    pf._detect_hand_import_error_popup = MagicMock(
        return_value=(100, 100, 400, 200, "Hand Import")
    )

    hand_path = _make_minimal_hand_dir(tmp_path)

    with pytest.raises(RuntimeError, match="PASTE_FAILED_HRC_REJECTED_CLIPBOARD"):
        pf.setup_hand("GG-TEST-99999", hand_path)

    # paste_hh NAO deve ter sido chamado (raise antes)
    pf.paste_hh.assert_not_called()
    # Popup fechado antes do raise (Enter)
    pf.pyautogui.press.assert_called_with('enter')


def test_setup_hand_proceeds_to_paste_hh_when_no_popup_pt28v3(pf, tmp_path):
    """Caminho feliz pt28-v3: clipboard preparado + open_wizard + sem
    popup azul -> setup_hand continua a paste_hh normalmente."""
    _stub_setup_hand_globals(pf, str(tmp_path))

    pf._set_clipboard_with_verify = MagicMock()
    pf._detect_hand_import_error_popup = MagicMock(return_value=None)

    hand_path = _make_minimal_hand_dir(tmp_path)
    pf.setup_hand("GG-TEST-99999", hand_path)

    pf.paste_hh.assert_called_once()  # continua a correr como rede de seguranca


# == pt29 (#WIZARD-FINISH-NO-STATE-CHECK): _wizard_window_present ==========

def _fake_window(title="Hand Setup", width=741, height=673):
    win = MagicMock()
    win.title = title
    win.width = width
    win.height = height
    return win


def test_wizard_window_present_true_when_hand_setup_exists(pf):
    """Janela com 'Hand Setup' no titulo -> True (wizard ainda aberto)."""
    pf.pyautogui.getAllWindows = MagicMock(return_value=[_fake_window()])
    assert pf._wizard_window_present() is True


def test_wizard_window_present_substring_match(pf):
    """Match por substring (titulo pode ter sufixo/prefixo)."""
    pf.pyautogui.getAllWindows = MagicMock(
        return_value=[_fake_window(title="HRC Pro - Hand Setup Wizard")]
    )
    assert pf._wizard_window_present() is True


def test_wizard_window_present_false_when_no_hand_setup(pf):
    """Sem janela 'Hand Setup' -> False (wizard fechou / avancou)."""
    pf.pyautogui.getAllWindows = MagicMock(
        return_value=[_fake_window(title="HRC Pro - Solver")]
    )
    assert pf._wizard_window_present() is False


def test_wizard_window_present_false_on_getallwindows_none(pf):
    """getAllWindows devolve None (mock env) -> False (sem WARN espurio)."""
    pf.pyautogui.getAllWindows = MagicMock(return_value=None)
    assert pf._wizard_window_present() is False


def test_wizard_window_present_false_on_getallwindows_exception(pf, capsys):
    """getAllWindows raises -> WARN + False (nao queremos gritar 'wizard
    presente' por erro de enumeracao)."""
    pf.pyautogui.getAllWindows = MagicMock(side_effect=RuntimeError("boom"))
    assert pf._wizard_window_present() is False
    assert "[WARN]" in capsys.readouterr().out


def test_wizard_window_present_tolerates_empty_titles(pf):
    """Janelas sem titulo (compositor) ignoradas; so a 'Hand Setup' conta."""
    blank = _fake_window(title="")
    setup = _fake_window(title="Hand Setup")
    pf.pyautogui.getAllWindows = MagicMock(return_value=[blank, setup])
    assert pf._wizard_window_present() is True


def test_setup_hand_warns_when_wizard_persists_after_finish_pt29(pf, tmp_path):
    """pt29 WARN-only: se 'Hand Setup' persiste apos click Finish, loga WARN
    mas NAO faz raise (1a versao). setup_hand continua ate ao fim."""
    _stub_setup_hand_globals(pf, str(tmp_path))
    pf._set_clipboard_with_verify = MagicMock()
    pf._detect_hand_import_error_popup = MagicMock(return_value=None)
    # Wizard SEMPRE presente -> simula Finish que falhou.
    pf._wizard_window_present = MagicMock(return_value=True)

    hand_path = _make_minimal_hand_dir(tmp_path)
    # NAO deve raise (WARN-only nesta versao).
    pf.setup_hand("GG-TEST-99999", hand_path)

    # Confirma que chegou ao fim (paste_hh correu apos o check WARN-only).
    pf.paste_hh.assert_called_once()


def test_setup_hand_finish_uses_slow_click_pt29v2(pf, tmp_path):
    """pt29-v2: o click do Finish usa slow-click (mouseDown + mouseUp) em vez
    do click instantaneo, para a janela Java do HRC registar o press."""
    _stub_setup_hand_globals(pf, str(tmp_path))
    pf._set_clipboard_with_verify = MagicMock()
    pf._detect_hand_import_error_popup = MagicMock(return_value=None)
    pf._wizard_window_present = MagicMock(return_value=False)

    hand_path = _make_minimal_hand_dir(tmp_path)
    pf.setup_hand("GG-TEST-99999", hand_path)

    # slow-click: mouseDown + mouseUp ambos chamados (button left).
    pf.pyautogui.mouseDown.assert_called_with(button='left')
    pf.pyautogui.mouseUp.assert_called_with(button='left')
    # moveTo posiciona no botao antes do press.
    assert pf.pyautogui.moveTo.called
