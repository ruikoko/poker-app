"""pt79 (#HRC-RESTART-POST-WINDOW-FAILURE) — testes para o reinício do HRC
após falha PÓS-abertura-de-janela em `setup_hand` (tools/watcher_src/patched_funcs.py).

Contexto (incidente Beelink): a mão falhou em `_wait_for_finish_ready`
(WIZARD_FINISH_NEVER_RE_ENABLED — tree size não acabou). Esse RuntimeError
propagava e a fila avançava, mas o HRC NÃO era reiniciado → ficava sujo
(diálogo "Hand Setup"/"Open" preso + memória alta) → mãos seguintes falhavam
por arrasto. O fix marca `_HRC_WINDOW_DIRTY=True` assim que o wizard abre e
reinicia o HRC no ARRANQUE da mão seguinte (generaliza a rung 2, que só cobre
wizard-não-abriu). Loop guard: 1 restart por mão; a falhada é sempre `.failed`.

patched_funcs não corre standalone (README §"Não correr standalone"): injectamos
mocks dos globais/funções resolvidos via LOAD_GLOBAL contra o namespace do
módulo. Mesmo padrão de `test_watcher_set_scope.py`.
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


def _make_hand(tmp_path, name="HAND01", meta=None):
    """Cria uma pasta de mão com 1 .txt (HH) + meta.json opcional. Devolve
    (hand_name, hand_path)."""
    import json as _json
    d = tmp_path / name
    d.mkdir()
    (d / "hh.txt").write_text("PokerStars Hand #1: ...\nSeat 1: Hero\n", encoding="utf-8")
    if meta is not None:
        (d / "meta.json").write_text(_json.dumps(meta), encoding="utf-8")
    return name, str(d)


@pytest.fixture
def pf(tmp_path):
    """Carrega `patched_funcs` fresh + injecta mocks de TODAS as dependências de
    `setup_hand`, configuradas para o CAMINHO DE SUCESSO. Cada teste sobrepõe o
    que precisa para forçar a falha pós-janela."""
    if "patched_funcs" in sys.modules:
        del sys.modules["patched_funcs"]
    import patched_funcs as _pf  # noqa: E402

    # estado de higiene — começa limpo
    _pf._HANDS_DONE_SINCE_RESTART = 0
    _pf._HRC_WINDOW_DIRTY = False
    _pf._RESTART_EVERY_N_HANDS = 5

    # constantes module-level do watcher original (resolvidas via LOAD_GLOBAL)
    _pf.BTN_NEXT = (677, 438)
    _pf.BTN_FINISH = (300, 500)
    _pf.SCRIPT_FILE = "default.js"
    _pf.DONE_DIR = str(tmp_path / "done")

    # time: sleep no-op, time real (loops de timeout dos helpers, aqui mockados)
    _pf.time = SimpleNamespace(time=_real_time.time, sleep=MagicMock(name="sleep"))

    # log a ficheiro: no-op (evita IO)
    _pf._ensure_file_logging = MagicMock(name="_ensure_file_logging")

    # higiene / arranque
    _pf._restart_hrc = MagicMock(name="_restart_hrc")
    _pf._wait_hrc_responsive = MagicMock(name="_wait_hrc_responsive", return_value=True)
    _pf.ensure_hrc = MagicMock(name="ensure_hrc", return_value=object())
    _pf._set_clipboard_with_verify = MagicMock(name="_set_clipboard_with_verify")

    # wizard aberto (sucesso): janela fake com _hWnd
    _pf._open_wizard_confirmed = MagicMock(
        name="_open_wizard_confirmed",
        return_value=SimpleNamespace(_hWnd=123, activate=MagicMock()),
    )
    _pf.get_win_pos = MagicMock(name="get_win_pos", return_value=(10, 10, 1024, 768))
    _pf._detect_hand_import_error_popup = MagicMock(return_value=None)
    _pf._close_hand_import_error_popup = MagicMock()
    _pf._resolve_wizard_hwnd = MagicMock(return_value=123)

    # corpo do wizard
    _pf.get_player_count_from_hh = MagicMock(return_value=6)
    _pf.paste_hh = MagicMock(name="paste_hh")
    _pf.set_hand_mode_players = MagicMock(name="set_hand_mode_players")
    _pf.set_equity_model = MagicMock(name="set_equity_model")
    _pf.import_prizes = MagicMock(name="import_prizes")
    _pf.click_rel = MagicMock(name="click_rel")
    _pf.handle_mtt_stacks_page = MagicMock(name="handle_mtt_stacks_page")
    _pf.setup_scripting = MagicMock(name="setup_scripting")

    # finish / runs / export
    _pf._wait_for_finish_ready = MagicMock(name="_wait_for_finish_ready")
    _pf._wait_for_run_completion = MagicMock(name="_wait_for_run_completion")
    _pf.navigate_to_target_node = MagicMock(name="navigate_to_target_node")
    _pf.start_calculation_selected_subtree = MagicMock(return_value=True)
    _pf._ci_target_readback_warn = MagicMock()
    _pf.finalize_after_second_run = MagicMock(name="finalize_after_second_run")
    _pf._close_hand_tab = MagicMock(name="_close_hand_tab")

    # pyautogui: getAllWindows iterável vazio, getActiveWindow None
    _pa = MagicMock(name="pyautogui")
    _pa.getAllWindows = MagicMock(return_value=[])
    _pa.getActiveWindow = MagicMock(return_value=None)
    _pf.pyautogui = _pa

    yield _pf


# ── caminho de sucesso / higiene base ──────────────────────────────────────

def test_success_no_restart_and_dirty_stays_clean(pf, tmp_path):
    name, path = _make_hand(tmp_path)
    res = pf.setup_hand(name, path)
    assert res and res.endswith("HAND01.zip")
    pf._restart_hrc.assert_not_called()          # limpo + counter<N → sem restart
    assert pf._HRC_WINDOW_DIRTY is False          # fim limpo
    assert pf._HANDS_DONE_SINCE_RESTART == 1      # contou a mão


def test_restart_every_n_still_triggers_pt68(pf, tmp_path):
    """Regressão pt68: o reinício a cada N mãos continua a disparar."""
    pf._HANDS_DONE_SINCE_RESTART = pf._RESTART_EVERY_N_HANDS
    name, path = _make_hand(tmp_path)
    pf.setup_hand(name, path)
    pf._restart_hrc.assert_called_once()


# ── pt79: dirty (falha pós-janela na mão anterior) → restart no arranque ────

def test_dirty_flag_triggers_restart_below_threshold(pf, tmp_path, capsys):
    pf._HRC_WINDOW_DIRTY = True            # mão anterior falhou pós-janela
    pf._HANDS_DONE_SINCE_RESTART = 0       # abaixo do N — só o dirty justifica
    name, path = _make_hand(tmp_path)
    res = pf.setup_hand(name, path)
    pf._restart_hrc.assert_called_once()
    pf._wait_hrc_responsive.assert_called()           # health-check pós-arranque
    assert pf._HRC_WINDOW_DIRTY is False              # consumido + fim limpo
    out = capsys.readouterr().out
    assert "[HRC-RESTART]" in out and "pós-abertura-de-janela" in out
    assert res and res.endswith("HAND01.zip")


# ── pt79: falha PÓS-abertura marca dirty e propaga (mão .failed) ────────────

def test_post_window_finish_failure_sets_dirty_and_propagates(pf, tmp_path):
    """O caso real: _wait_for_finish_ready levanta RuntimeError → setup_hand
    propaga (mão marcada .failed) E deixa _HRC_WINDOW_DIRTY=True → a seguinte
    reinicia."""
    pf._wait_for_finish_ready.side_effect = RuntimeError(
        "WIZARD_FINISH_NEVER_RE_ENABLED: ..."
    )
    name, path = _make_hand(tmp_path)
    with pytest.raises(RuntimeError, match="WIZARD_FINISH_NEVER_RE_ENABLED"):
        pf.setup_hand(name, path)
    assert pf._HRC_WINDOW_DIRTY is True
    # esta mão não reiniciou no arranque (estava limpa ao entrar)
    pf._restart_hrc.assert_not_called()


def test_post_window_popup_failure_sets_dirty(pf, tmp_path):
    """Popup HRC pós-open (PASTE_FAILED) também é pós-janela → marca dirty."""
    pf._detect_hand_import_error_popup = MagicMock(
        return_value=(0, 0, 0, 0, "Hand Import")
    )
    name, path = _make_hand(tmp_path)
    with pytest.raises(RuntimeError, match="PASTE_FAILED_HRC_REJECTED_CLIPBOARD"):
        pf.setup_hand(name, path)
    assert pf._HRC_WINDOW_DIRTY is True


# ── pt79: bail limpo de wizard-não-abriu NÃO marca dirty (sem duplicar rung 2) ─

def test_clean_wizard_bail_does_not_set_dirty(pf, tmp_path):
    pf._open_wizard_confirmed = MagicMock(return_value=None)   # wizard não abriu
    name, path = _make_hand(tmp_path)
    res = pf.setup_hand(name, path)
    assert res is False
    assert pf._HRC_WINDOW_DIRTY is False        # NÃO marcou dirty (rung 2 trata)
    pf._restart_hrc.assert_not_called()         # entrou limpo; sem restart aqui


# ── pt79: scope_unconfirmed (abort pós-janela) deixa dirty=True ─────────────

def test_scope_unconfirmed_leaves_dirty_true(pf, tmp_path):
    pf.start_calculation_selected_subtree = MagicMock(return_value="scope_unconfirmed")
    name, path = _make_hand(
        tmp_path, meta={"aggressor_real_action": {"position": "CO"},
                        "target_node_offset": 0}
    )
    res = pf.setup_hand(name, path)
    assert res is None                          # abortou a mão
    assert pf._HRC_WINDOW_DIRTY is True         # post-window → reinicia a seguinte


# ── pt79: loop guard — 1 restart por mão, sem ciclo sem fim ─────────────────

def test_consecutive_failures_restart_once_each_no_loop(pf, tmp_path):
    """Mão A falha pós-janela (dirty=True). Mão B: reinicia 1x no arranque e
    falha também → dirty fica True. O restart é 1x por mão (nunca em ciclo);
    cada mão propaga (a fila avança com .failed)."""
    pf._wait_for_finish_ready.side_effect = RuntimeError("WIZARD_FINISH_NEVER_RE_ENABLED")

    # Mão A
    nameA, pathA = _make_hand(tmp_path, name="A")
    with pytest.raises(RuntimeError):
        pf.setup_hand(nameA, pathA)
    assert pf._HRC_WINDOW_DIRTY is True
    pf._restart_hrc.assert_not_called()         # A entrou limpa

    # Mão B — entra dirty → reinicia 1x no arranque, depois volta a falhar
    nameB, pathB = _make_hand(tmp_path, name="B")
    with pytest.raises(RuntimeError):
        pf.setup_hand(nameB, pathB)
    pf._restart_hrc.assert_called_once()        # exactamente 1 restart (no arranque de B)
    assert pf._HRC_WINDOW_DIRTY is True         # falhou outra vez → a próxima reinicia
