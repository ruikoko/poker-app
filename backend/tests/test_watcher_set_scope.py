"""pt25e Bloco 2 piece 1 — tests para `_set_scope_in_popup` +
`start_calculation_selected_subtree` em `tools/watcher_src/patched_funcs.py`.

patched_funcs não corre standalone (ver `tools/watcher_src/README.md`
§"Não correr standalone"): os globais não-stdlib (`click_rel`, `pyautogui`,
`pyperclip`, etc.) são resolvidos em runtime via LOAD_GLOBAL contra o
namespace do watcher após marshal swap. Aqui injectamos mocks dos globais
relevantes no namespace do módulo antes de invocar as funções.

Mesmo padrão de path-injection que `test_hrc_adapter_helpers.py`.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, call

import pytest

_HERE = Path(__file__).resolve().parent
_WATCHER_SRC = _HERE.parent.parent / "tools" / "watcher_src"
sys.path.insert(0, str(_WATCHER_SRC))


@pytest.fixture
def pf():
    """Carrega `patched_funcs` fresh + injecta mocks de globais que o body
    das funções resolve via LOAD_GLOBAL contra o module namespace."""
    if "patched_funcs" in sys.modules:
        del sys.modules["patched_funcs"]
    import patched_funcs as _pf  # noqa: E402
    _pf.click_rel = MagicMock(name="click_rel")
    _pf.pyautogui = MagicMock(name="pyautogui")
    _pf.pyperclip = MagicMock(name="pyperclip")
    # Anular sleeps reais — os bodies usam time.sleep e queremos suite fast.
    _pf.time = MagicMock(name="time")
    yield _pf


# ── _set_scope_in_popup ─────────────────────────────────────────────────

def test_set_scope_in_popup_early_returns_when_all_coords_zero(pf, capsys):
    """Coords placeholder (0,0,0,0) → não clica, log WARN."""
    # Defaults do módulo são todos 0 — confirma estado inicial.
    assert pf.SCOPE_DROPDOWN_X == 0
    assert pf.SCOPE_DROPDOWN_Y == 0
    assert pf.SCOPE_OPTION_SELECTED_SUBTREE_X == 0
    assert pf.SCOPE_OPTION_SELECTED_SUBTREE_Y == 0

    pf._set_scope_in_popup(wpos=(0, 0, 1024, 768))

    pf.click_rel.assert_not_called()
    out = capsys.readouterr().out
    assert "[WARN]" in out
    assert "_set_scope_in_popup" in out


def test_set_scope_in_popup_early_returns_when_dropdown_x_only_zero(pf):
    """Apenas 1 dos 4 coords ainda placeholder → early-return defensivo
    (todos têm de estar calibrados juntos)."""
    pf.SCOPE_DROPDOWN_X = 0  # ainda placeholder
    pf.SCOPE_DROPDOWN_Y = 200
    pf.SCOPE_OPTION_SELECTED_SUBTREE_X = 120
    pf.SCOPE_OPTION_SELECTED_SUBTREE_Y = 230

    pf._set_scope_in_popup(wpos=(0, 0, 1024, 768))

    pf.click_rel.assert_not_called()


def test_set_scope_in_popup_early_returns_when_option_y_only_zero(pf):
    """Edge case: 3 calibrados + 1 zero → ainda defensive return."""
    pf.SCOPE_DROPDOWN_X = 500
    pf.SCOPE_DROPDOWN_Y = 200
    pf.SCOPE_OPTION_SELECTED_SUBTREE_X = 520
    pf.SCOPE_OPTION_SELECTED_SUBTREE_Y = 0  # placeholder

    pf._set_scope_in_popup(wpos=(0, 0, 1024, 768))

    pf.click_rel.assert_not_called()


def test_set_scope_in_popup_clicks_dropdown_then_option_when_calibrated(pf):
    """Coords calibrados → 2 clicks na ordem: dropdown → opção."""
    pf.SCOPE_DROPDOWN_X = 500
    pf.SCOPE_DROPDOWN_Y = 200
    pf.SCOPE_OPTION_SELECTED_SUBTREE_X = 520
    pf.SCOPE_OPTION_SELECTED_SUBTREE_Y = 230
    wpos = (0, 0, 1024, 768)

    pf._set_scope_in_popup(wpos)

    assert pf.click_rel.call_args_list == [
        call(wpos, 500, 200),
        call(wpos, 520, 230),
    ]


def test_set_scope_in_popup_sleeps_between_and_after_clicks(pf):
    """Padrão idêntico a `set_equity_model`: sleep curto entre dropdown
    open e option click + sleep pós-option."""
    pf.SCOPE_DROPDOWN_X = 1
    pf.SCOPE_DROPDOWN_Y = 1
    pf.SCOPE_OPTION_SELECTED_SUBTREE_X = 2
    pf.SCOPE_OPTION_SELECTED_SUBTREE_Y = 2

    pf._set_scope_in_popup(wpos=(0, 0, 1024, 768))

    # 2 sleeps esperados (entre dropdown e option + pós-option).
    assert pf.time.sleep.call_count == 2


# ── start_calculation_selected_subtree (wiring) ─────────────────────────

def test_start_calculation_selected_subtree_invokes_set_scope_in_popup(pf):
    """Wiring piece 1: a função paralela invoca `_set_scope_in_popup` com
    o mesmo `wpos` que recebeu. Outros passos (1/2/4) ficam stub até peça 2."""
    pf._set_scope_in_popup = MagicMock(name="_set_scope_in_popup")
    wpos = (10, 10, 1024, 768)

    pf.start_calculation_selected_subtree(wpos, ci_target=10.0)

    pf._set_scope_in_popup.assert_called_once_with(wpos)


def test_start_calculation_selected_subtree_scope_call_happens_before_return(pf):
    """Ordering check piece 1: na ausência dos passos 1/2/4 (TODO peça 2),
    `_set_scope_in_popup` é o ÚNICO call observável no body — confirma que
    está no sítio certo (não-comentado) e que a função não retorna antes
    de o chamar.
    """
    call_log = []
    pf._set_scope_in_popup = MagicMock(
        name="_set_scope_in_popup",
        side_effect=lambda w: call_log.append(("scope", w)),
    )
    wpos = (0, 0, 1024, 768)

    pf.start_calculation_selected_subtree(wpos, ci_target=10.0)

    assert call_log == [("scope", wpos)]


def test_start_calculation_selected_subtree_works_with_default_placeholders(pf, capsys):
    """Integração defensive: chamada end-to-end com coords zero não levanta
    e não dispara cliques (early-return de `_set_scope_in_popup`)."""
    # Default coords são placeholder (0). `_set_scope_in_popup` real é
    # invocada e faz o early-return.
    pf.start_calculation_selected_subtree(wpos=(0, 0, 1024, 768), ci_target=10.0)

    pf.click_rel.assert_not_called()
    out = capsys.readouterr().out
    assert "[WARN]" in out  # WARN de _set_scope_in_popup
    assert "Bloco 2 piece 1" in out  # confirma o print envolvente
