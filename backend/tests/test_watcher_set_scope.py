"""pt25e Bloco 2 piece 1 — tests para `_set_scope_in_popup` +
`start_calculation_selected_subtree` em `tools/watcher_src/patched_funcs.py`.

patched_funcs não corre standalone (ver `tools/watcher_src/README.md`
§"Não correr standalone"): os globais não-stdlib (`click_rel`, `pyautogui`,
`pyperclip`, etc.) são resolvidos em runtime via LOAD_GLOBAL contra o
namespace do watcher após marshal swap. Aqui injectamos mocks dos globais
relevantes no namespace do módulo antes de invocar as funções.

Mesmo padrão de path-injection que `test_hrc_adapter_helpers.py`.

Coords (fracções) calibradas em smoke 2026-05-18 com Rui no Beelink.
Tests validam o flow real (sem cair no defensive return) usando o
popup_rect literal capturado nessa smoke.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, call

import pytest

_HERE = Path(__file__).resolve().parent
_WATCHER_SRC = _HERE.parent.parent / "tools" / "watcher_src"
sys.path.insert(0, str(_WATCHER_SRC))


# Popup rect literal capturado no smoke 2026-05-18: top-left (666, 372),
# bottom-right (1082, 586) → width=416, height=214. Re-usado em vários tests
# para validar o cálculo absoluto contra os números reais.
_SMOKE_POPUP_RECT = (666, 372, 416, 214)

# Coords absolutas medidas no smoke (referência humana — Rui clicou em cada
# e confirmou o highlight). Computar-as a partir das fracções de
# patched_funcs dá ±1 px (rounding `int()`), aceitável para targets de UI.
_SMOKE_DROPDOWN_ABS = (944, 439)
_SMOKE_OPTION_SELECTED_SUBTREE_ABS = (940, 480)


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


# ── _set_scope_in_popup: defensive returns ──────────────────────────────

def test_set_scope_in_popup_early_returns_when_popup_rect_is_none(pf, capsys):
    """`popup_rect=None` → caller ainda não detecta popup (peça 2 wiring
    pendente). Função faz early-return com WARN; zero clicks."""
    pf._set_scope_in_popup(popup_rect=None)
    pf.pyautogui.click.assert_not_called()
    out = capsys.readouterr().out
    assert "[WARN]" in out
    assert "popup_rect" in out


def test_set_scope_in_popup_early_returns_when_all_fractions_zero(pf, capsys):
    """Regressão: se um dia voltarmos a 0.0 (rollback de calibração),
    defensive return continua a disparar."""
    pf.SCOPE_DROPDOWN_FRAC_X = 0.0
    pf.SCOPE_DROPDOWN_FRAC_Y = 0.0
    pf.SCOPE_OPTION_SELECTED_SUBTREE_FRAC_X = 0.0
    pf.SCOPE_OPTION_SELECTED_SUBTREE_FRAC_Y = 0.0

    pf._set_scope_in_popup(popup_rect=_SMOKE_POPUP_RECT)

    pf.pyautogui.click.assert_not_called()
    out = capsys.readouterr().out
    assert "[WARN]" in out
    assert "fracções não calibradas" in out


def test_set_scope_in_popup_early_returns_when_single_fraction_zero(pf):
    """Regressão: qualquer 1 das 4 fracções a 0.0 → defensive (não calibrar
    parcial)."""
    pf.SCOPE_OPTION_SELECTED_SUBTREE_FRAC_Y = 0.0  # rollback parcial
    pf._set_scope_in_popup(popup_rect=_SMOKE_POPUP_RECT)
    pf.pyautogui.click.assert_not_called()


# ── _set_scope_in_popup: click flow real ────────────────────────────────

def test_set_scope_in_popup_constants_are_calibrated_after_smoke(pf):
    """Sanity: depois do smoke 2026-05-18, as 4 fracções estão != 0.0."""
    assert 0.0 < pf.SCOPE_DROPDOWN_FRAC_X < 1.0
    assert 0.0 < pf.SCOPE_DROPDOWN_FRAC_Y < 1.0
    assert 0.0 < pf.SCOPE_OPTION_SELECTED_SUBTREE_FRAC_X < 1.0
    assert 0.0 < pf.SCOPE_OPTION_SELECTED_SUBTREE_FRAC_Y < 1.0


def test_set_scope_in_popup_clicks_at_smoke_absolute_coords(pf):
    """Com `popup_rect` real do smoke (666, 372, 416, 214), as fracções
    calibradas produzem clicks dentro de ±1 px dos valores medidos pelo Rui
    (944, 439) e (940, 480). Sem fallback ao defensive return — exercita o
    flow de clicks completo."""
    pf._set_scope_in_popup(popup_rect=_SMOKE_POPUP_RECT)

    # Deve haver exactamente 2 clicks, na ordem dropdown → opção.
    assert pf.pyautogui.click.call_count == 2
    (drop_x, drop_y), _ = pf.pyautogui.click.call_args_list[0]
    (opt_x, opt_y), _ = pf.pyautogui.click.call_args_list[1]

    # Tolerância ±2 px sobre as medições do smoke (int() do float introduz
    # ~1 px de rounding; 2px é folga para variação inter-render do Qt).
    assert abs(drop_x - _SMOKE_DROPDOWN_ABS[0]) <= 2
    assert abs(drop_y - _SMOKE_DROPDOWN_ABS[1]) <= 2
    assert abs(opt_x - _SMOKE_OPTION_SELECTED_SUBTREE_ABS[0]) <= 2
    assert abs(opt_y - _SMOKE_OPTION_SELECTED_SUBTREE_ABS[1]) <= 2


def test_set_scope_in_popup_uses_pyautogui_click_not_click_rel(pf):
    """Padrão correcto para clicks no popup Nash: `pyautogui.click(abs_x,
    abs_y)` (mesmo padrão pt25d para CI Target). `click_rel` opera sobre
    main HRC window rect e não é apropriado aqui."""
    pf._set_scope_in_popup(popup_rect=_SMOKE_POPUP_RECT)
    pf.click_rel.assert_not_called()
    assert pf.pyautogui.click.call_count == 2


def test_set_scope_in_popup_computes_coords_from_popup_rect_with_fractions(pf):
    """Confirmação algébrica: `abs = left + int(w * frac), top + int(h * frac)`.
    Usa popup rect sintético com tamanhos round para o cálculo ser óbvio."""
    pf.SCOPE_DROPDOWN_FRAC_X = 0.5
    pf.SCOPE_DROPDOWN_FRAC_Y = 0.25
    pf.SCOPE_OPTION_SELECTED_SUBTREE_FRAC_X = 0.5
    pf.SCOPE_OPTION_SELECTED_SUBTREE_FRAC_Y = 0.75

    pf._set_scope_in_popup(popup_rect=(100, 200, 400, 200))
    # Dropdown: (100 + int(400*0.5), 200 + int(200*0.25)) = (300, 250)
    # Opção:    (100 + int(400*0.5), 200 + int(200*0.75)) = (300, 350)
    assert pf.pyautogui.click.call_args_list == [
        call(300, 250),
        call(300, 350),
    ]


def test_set_scope_in_popup_sleeps_between_clicks(pf):
    """Padrão click+wait idêntico a `set_equity_model`: sleep depois de
    cada click (2 sleeps no total)."""
    pf._set_scope_in_popup(popup_rect=_SMOKE_POPUP_RECT)
    assert pf.time.sleep.call_count == 2


def test_set_scope_in_popup_logs_success_after_clicks(pf, capsys):
    """Após clicks, log positivo (não-WARN) confirma scope set."""
    pf._set_scope_in_popup(popup_rect=_SMOKE_POPUP_RECT)
    out = capsys.readouterr().out
    assert "Scope: Selected Subtree" in out
    assert "[WARN]" not in out


# ── start_calculation_selected_subtree (wiring) ─────────────────────────

def test_start_calculation_selected_subtree_invokes_set_scope_in_popup(pf):
    """Wiring piece 1: a função paralela invoca `_set_scope_in_popup` uma
    vez. Em piece 1, `popup_rect` passado é None (peça 2 substitui pelo rect
    detectado)."""
    pf._set_scope_in_popup = MagicMock(name="_set_scope_in_popup")
    wpos = (10, 10, 1024, 768)

    pf.start_calculation_selected_subtree(wpos, ci_target=10.0)

    pf._set_scope_in_popup.assert_called_once_with(None)


def test_start_calculation_selected_subtree_does_not_call_click_rel_or_pyautogui(pf):
    """Piece 1 com popup_rect=None: a função paralela invoca o helper, que
    faz defensive return. Nenhum click chega ao pyautogui."""
    pf.start_calculation_selected_subtree(wpos=(0, 0, 1024, 768), ci_target=10.0)
    pf.pyautogui.click.assert_not_called()
    pf.click_rel.assert_not_called()


def test_start_calculation_selected_subtree_logs_piece1_marker(pf, capsys):
    """Print final confirma que estamos no estado piece 1 (sem o click flow
    full do popup)."""
    pf.start_calculation_selected_subtree(wpos=(0, 0, 1024, 768), ci_target=10.0)
    out = capsys.readouterr().out
    assert "Bloco 2 piece 1" in out
    assert "scope set only" in out
