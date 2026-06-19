"""pt84 (#HRC-HANG-WATCHDOG) — vigia de mão pendurada (tools/watcher_src/patched_funcs.py).

Prova a LÓGICA (deteção de cada sinal + a cadeia de recuperação) com Win32/janelas
mockados. A deteção REAL de um congelamento (IsHungAppWindow num HRC frozen,
título do diálogo OOM) valida-se no re-smoke do Beelink (ver RUNBOOK).

Sinais: (1) diálogo fatal Java/OOM por título; (2) janela principal HUNG sustido;
(3) smoke-force (indução one-shot p/ provar a recuperação ponta-a-ponta sem OOM).
Recuperação: mark_failed(reason) → _restart_hrc → HRCWatchdogError (a fila avança).
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


def _win(title):
    return SimpleNamespace(title=title, left=0, top=0, width=400, height=200)


@pytest.fixture
def wd(tmp_path):
    if "patched_funcs" in sys.modules:
        del sys.modules["patched_funcs"]
    import patched_funcs as _pf  # noqa: E402

    # estado do vigia — limpo
    _pf._WATCHDOG_ENABLED = True
    _pf._WATCHDOG_HUNG_SINCE = None
    _pf._WATCHDOG_LAST_CHECK = 0.0
    _pf._WATCHDOG_SMOKE_FORCE = False
    _pf._WATCHDOG_SMOKE_FIRED = False
    _pf._WATCHDOG_HUNG_SUSTAIN_S = 1200.0
    _pf._CURRENT_HAND_PATH = str(tmp_path / "HAND01")
    _pf._HANDS_DONE_SINCE_RESTART = 3
    _pf._HRC_WINDOW_DIRTY = True

    # recuperação mockada
    _pf.mark_failed = MagicMock(name="mark_failed")
    _pf._restart_hrc = MagicMock(name="_restart_hrc")

    # time controlável (clock), sleep no-op
    _pf._clock = {"t": 1000.0}
    _pf.time = SimpleNamespace(
        time=lambda: _pf._clock["t"],
        sleep=MagicMock(name="sleep"),
    )

    # janelas: sem diálogos por defeito
    _pa = MagicMock(name="pyautogui")
    _pa.getAllWindows = MagicMock(return_value=[])
    _pf.pyautogui = _pa

    # Win32 + find_hrc: HRC responsivo por defeito (IsHungAppWindow=0)
    _u = MagicMock(name="user32")
    _u.IsHungAppWindow = MagicMock(return_value=0)
    _u.IsWindow = MagicMock(return_value=1)
    _pf._pt30_user32 = _u
    _pf.find_hrc = MagicMock(return_value=SimpleNamespace(_hWnd=999))

    # clean env do smoke
    import os as _os
    _os.environ.pop("HRC_WATCHDOG_SMOKE_FORCE", None)
    yield _pf


# ── (1) diálogo fatal Java/OOM ──────────────────────────────────────────────
def test_detect_fatal_dialog_oom(wd):
    wd.pyautogui.getAllWindows.return_value = [
        _win("HRC"), _win("java.lang.OutOfMemoryError: Java heap space")]
    t = wd._detect_fatal_hrc_window()
    assert t and "outofmemoryerror" in t


def test_detect_fatal_dialog_none_when_clean(wd):
    wd.pyautogui.getAllWindows.return_value = [_win("HRC"), _win("Hand Setup")]
    assert wd._detect_fatal_hrc_window() is None


def test_reason_fatal_dialog(wd):
    wd.pyautogui.getAllWindows.return_value = [_win("Out of memory")]
    r = wd._watchdog_reason()
    assert r and r.startswith("hrc_fatal_dialog:")


# ── (2) hung sustido ────────────────────────────────────────────────────────
def test_reason_hung_needs_sustain(wd):
    wd._pt30_user32.IsHungAppWindow.return_value = 1   # congelada
    # 1ª verificação: arranca o timer, ainda NÃO dispara
    assert wd._watchdog_reason() is None
    assert wd._WATCHDOG_HUNG_SINCE == 1000.0
    # ainda dentro do sustain (avança 1199s) → None
    wd._clock["t"] = 1000.0 + 1199
    assert wd._watchdog_reason() is None
    # passa o sustain (>=1200s contínuos) → dispara
    wd._clock["t"] = 1000.0 + 1201
    r = wd._watchdog_reason()
    assert r and r.startswith("hrc_hung_sustained:")


def test_reason_hung_resets_when_responsive(wd):
    wd._pt30_user32.IsHungAppWindow.return_value = 1
    wd._watchdog_reason()                 # arranca timer
    assert wd._WATCHDOG_HUNG_SINCE is not None
    wd._pt30_user32.IsHungAppWindow.return_value = 0   # voltou responsivo
    assert wd._watchdog_reason() is None
    assert wd._WATCHDOG_HUNG_SINCE is None  # timer reposto (não acumula)


def test_healthy_solve_no_false_positive(wd):
    """HRC responsivo + sem diálogo → NUNCA dispara (solve longo legítimo)."""
    for adv in (0, 600, 3600, 7200):       # 0..2h de solve saudável
        wd._clock["t"] = 1000.0 + adv
        assert wd._watchdog_reason() is None


# ── (3) smoke-force (indução one-shot) ──────────────────────────────────────
def test_smoke_force_flag_one_shot(wd):
    wd._WATCHDOG_SMOKE_FORCE = True
    r1 = wd._watchdog_reason()
    assert r1 and "smoke_force" in r1
    assert wd._watchdog_reason() is None   # one-shot por processo


def test_smoke_force_env(wd):
    import os
    os.environ["HRC_WATCHDOG_SMOKE_FORCE"] = "1"
    try:
        assert "smoke_force" in (wd._watchdog_reason() or "")
    finally:
        os.environ.pop("HRC_WATCHDOG_SMOKE_FORCE", None)


# ── recuperação: _watchdog_trip + _watchdog_sleep ───────────────────────────
def test_trip_marks_failed_restarts_and_raises(wd):
    with pytest.raises(wd.HRCWatchdogError):
        wd._watchdog_trip("hrc_fatal_dialog: oom")
    wd.mark_failed.assert_called_once()
    args = wd.mark_failed.call_args.args
    assert args[0] == wd._CURRENT_HAND_PATH   # marca a mão a decorrer
    assert "oom" in args[1]                   # reason específico (→ hrc_jobs.error)
    wd._restart_hrc.assert_called_once()


def test_sleep_trips_on_reason(wd):
    wd.pyautogui.getAllWindows.return_value = [_win("java.lang.OutOfMemoryError")]
    with pytest.raises(wd.HRCWatchdogError):
        wd._watchdog_sleep(0.5)
    wd.mark_failed.assert_called_once()
    wd._restart_hrc.assert_called_once()


def test_sleep_clean_does_not_raise(wd):
    wd._watchdog_sleep(0.5)               # HRC responsivo, sem diálogo
    wd.mark_failed.assert_not_called()
    wd.time.sleep.assert_called()          # dormiu normalmente


def test_sleep_throttle_skips_recheck_within_poll(wd):
    wd._WATCHDOG_LAST_CHECK = 1000.0       # já verificado agora
    wd._clock["t"] = 1002.0                # +2s (< _WATCHDOG_POLL_S=5)
    wd.pyautogui.getAllWindows.return_value = [_win("Out of memory")]
    wd._watchdog_sleep(0.5)                # NÃO re-verifica → não dispara
    wd.mark_failed.assert_not_called()


def test_disabled_watchdog_is_noop(wd):
    wd._WATCHDOG_ENABLED = False
    wd.pyautogui.getAllWindows.return_value = [_win("OutOfMemoryError")]
    assert wd._watchdog_reason() is None
    wd._watchdog_sleep(0.5)               # só dorme
    wd.mark_failed.assert_not_called()


# ── integração: a espera-mãe está mesmo vigiada ─────────────────────────────
def test_run_wait_is_watched_and_trips(wd):
    """_wait_for_run_completion (espera-mãe, multi-hora) chama _watchdog_sleep →
    com smoke-force, dispara e levanta HRCWatchdogError em vez de pendurar."""
    wd._WATCHDOG_SMOKE_FORCE = True
    wd._find_progress_window_hwnd = MagicMock(return_value=4242)  # janela presente
    wd._pt30_user32.IsWindow.return_value = 1                     # ainda a correr
    with pytest.raises(wd.HRCWatchdogError):
        wd._wait_for_run_completion(timeout_total_s=99999, run_label="1ª run")
    wd.mark_failed.assert_called_once()    # recuperou (não pendurou até ao timeout)
    wd._restart_hrc.assert_called_once()
