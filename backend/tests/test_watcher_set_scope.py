"""pt25e Bloco 2 piece 1 — tests para `_set_scope_in_popup` +
`start_calculation_selected_subtree` em `tools/watcher_src/patched_funcs.py`.

patched_funcs não corre standalone (ver `tools/watcher_src/README.md`
§"Não correr standalone"): os globais não-stdlib (`click_rel`, `pyautogui`,
`pyperclip`, etc.) são resolvidos em runtime via LOAD_GLOBAL contra o
namespace do watcher após marshal swap. Aqui injectamos mocks dos globais
relevantes no namespace do módulo antes de invocar as funções.

Mesmo padrão de path-injection que `test_hrc_adapter_helpers.py`.

Coords (pixels-rel ao popup top-left) derivadas da medição absoluta do
smoke 2026-05-18 com Rui no Beelink. Convenção migrou de fracções para
pixels-rel em pt26 (smoke 19 Maio detectou popup com tamanho diferente:
416×214 → 436×230). Justificação no bloco de constantes de patched_funcs.
"""
import sys
import time as _real_time
from pathlib import Path
from types import SimpleNamespace
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
    das funções resolve via LOAD_GLOBAL contra o module namespace.

    pt29 (#PT25D-WATCHER-FRAGILE-CLIPBOARD-OR-RESTORE): `pyperclip` precisa
    de ser stateful (paste devolve o último copy) porque
    `_fill_ci_target_in_popup` e `_set_ci_target_common` passaram a usar
    `clipboard_safe_paste`, que faz set + read-back de verificação. Com
    `pyperclip` como `MagicMock` puro, `paste()` devolve outro MagicMock
    (!= target) → mismatch → n_retries → RuntimeError. Stateful mock evita
    isto sem perder a capacidade de `pyperclip.copy.assert_called_once_with(...)`.
    """
    if "patched_funcs" in sys.modules:
        del sys.modules["patched_funcs"]
    import patched_funcs as _pf  # noqa: E402
    _pf.click_rel = MagicMock(name="click_rel")
    _pf.pyautogui = MagicMock(name="pyautogui")

    _clipboard_state = {"value": ""}
    _pp = MagicMock(name="pyperclip")
    _pp.copy.side_effect = lambda text: _clipboard_state.__setitem__("value", text)
    _pp.paste.side_effect = lambda: _clipboard_state["value"]
    _pf.pyperclip = _pp

    # Manter `time.time()` real (necessário para timeout loops em
    # `_wait_for_nash_popup`); apenas `time.sleep` é no-op (suite rápida).
    _pf.time = SimpleNamespace(
        time=_real_time.time,
        sleep=MagicMock(name="time.sleep"),
    )
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


def test_set_scope_in_popup_early_returns_when_all_rels_zero(pf, capsys):
    """Regressão: se um dia voltarmos a 0 (rollback de calibração),
    defensive return continua a disparar."""
    pf.SCOPE_DROPDOWN_REL_X = 0
    pf.SCOPE_DROPDOWN_REL_Y = 0
    pf.SCOPE_OPTION_SELECTED_SUBTREE_REL_X = 0
    pf.SCOPE_OPTION_SELECTED_SUBTREE_REL_Y = 0

    pf._set_scope_in_popup(popup_rect=_SMOKE_POPUP_RECT)

    pf.pyautogui.click.assert_not_called()
    out = capsys.readouterr().out
    assert "[WARN]" in out
    assert "pixels-rel não calibrados" in out


def test_set_scope_in_popup_early_returns_when_single_rel_zero(pf):
    """Regressão: qualquer 1 dos 4 RELs a 0 → defensive (não calibrar
    parcial)."""
    pf.SCOPE_OPTION_SELECTED_SUBTREE_REL_Y = 0  # rollback parcial
    pf._set_scope_in_popup(popup_rect=_SMOKE_POPUP_RECT)
    pf.pyautogui.click.assert_not_called()


# ── _set_scope_in_popup: click flow real ────────────────────────────────

def test_set_scope_in_popup_constants_are_calibrated_after_smoke(pf):
    """Sanity: depois do smoke 2026-05-18, os 4 RELs estão != 0 e dentro de
    bounds plausíveis para um popup Nash típico (popup width/height
    observados nos smokes ficam entre ~400 e ~450 px; valores acima de 400
    seriam suspeitos)."""
    assert 0 < pf.SCOPE_DROPDOWN_REL_X < 400
    assert 0 < pf.SCOPE_DROPDOWN_REL_Y < 400
    assert 0 < pf.SCOPE_OPTION_SELECTED_SUBTREE_REL_X < 400
    assert 0 < pf.SCOPE_OPTION_SELECTED_SUBTREE_REL_Y < 400


def test_set_scope_in_popup_clicks_at_smoke_absolute_coords(pf):
    """Com `popup_rect` real do smoke 18 Maio (666, 372, 416, 214), os
    pixels-rel calibrados produzem clicks dentro de ±2 px dos valores
    absolutos medidos pelo Rui (944, 439) e (940, 480). Por construção
    pixels-rel não introduzem rounding; tolerância ±2 px é folga para
    variação inter-render do Qt no smoke."""
    pf._set_scope_in_popup(popup_rect=_SMOKE_POPUP_RECT)

    # Deve haver exactamente 2 clicks, na ordem dropdown → opção.
    assert pf.pyautogui.click.call_count == 2
    (drop_x, drop_y), _ = pf.pyautogui.click.call_args_list[0]
    (opt_x, opt_y), _ = pf.pyautogui.click.call_args_list[1]

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


def test_set_scope_in_popup_computes_coords_from_popup_rect_with_rels(pf):
    """Confirmação algébrica: `abs = left + REL_X, top + REL_Y`. Pixels-rel
    são invariantes a `width`/`height` do popup — propriedade chave que
    motivou a migração de fracções em pt26."""
    pf.SCOPE_DROPDOWN_REL_X = 200
    pf.SCOPE_DROPDOWN_REL_Y = 50
    pf.SCOPE_OPTION_SELECTED_SUBTREE_REL_X = 200
    pf.SCOPE_OPTION_SELECTED_SUBTREE_REL_Y = 150

    pf._set_scope_in_popup(popup_rect=(100, 200, 400, 200))
    # Dropdown: (100 + 200, 200 + 50)  = (300, 250)
    # Opção:    (100 + 200, 200 + 150) = (300, 350)
    assert pf.pyautogui.click.call_args_list == [
        call(300, 250),
        call(300, 350),
    ]


def test_set_scope_in_popup_invariant_to_popup_size(pf):
    """Propriedade chave da convenção pt26: o mesmo REL produz o mesmo
    OFFSET ao top-left, independente de o popup crescer (416×214 → 436×230
    em smokes consecutivos). Fracções driftavam ~13px X neste cenário."""
    rects = [
        (666, 372, 416, 214),   # smoke 18 Maio
        (590, 337, 436, 230),   # smoke 19 Maio
        (100, 100, 600, 400),   # sintético maior ainda
    ]
    for rect in rects:
        pf.pyautogui.click.reset_mock()
        pf._set_scope_in_popup(popup_rect=rect)
        left, top, _w, _h = rect
        (drop_x, drop_y), _ = pf.pyautogui.click.call_args_list[0]
        assert (drop_x, drop_y) == (
            left + pf.SCOPE_DROPDOWN_REL_X,
            top + pf.SCOPE_DROPDOWN_REL_Y,
        )


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

def test_start_calculation_selected_subtree_full_flow_with_popup(pf):
    """Piece 2 end-to-end: com popup detectado, todos os passos disparam na
    ordem pt28-v1: Calculate → wait popup → set scope → fill CI → OK Enter.

    A ordem scope-antes-de-CI é validada com mais rigor em
    `test_start_calculation_selected_subtree_calls_scope_before_ci_fill_pt28v1`.
    Aqui só validamos o sumário (3 clicks + Enter).
    """
    # Mock _wait_for_nash_popup to return a fake rect (popup detected).
    fake_rect = (666, 372, 416, 214)
    pf._wait_for_nash_popup = MagicMock(return_value=fake_rect)
    wpos = (10, 10, 1024, 768)

    pf.start_calculation_selected_subtree(wpos, ci_target=10.0)

    # Calculate button clicked via click_rel with calibrated pt26 coords.
    pf.click_rel.assert_called_with(wpos, pf.CALCULATE_BUTTON_X, pf.CALCULATE_BUTTON_Y)
    # Popup detection invoked.
    pf._wait_for_nash_popup.assert_called_once()
    # Pyautogui clicks: 2 scope + 1 fill CI = 3 clicks total.
    assert pf.pyautogui.click.call_count == 3
    # Enter pressed for OK.
    pf.pyautogui.press.assert_any_call('enter')


def test_start_calculation_selected_subtree_calls_scope_before_ci_fill_pt28v1(pf):
    """pt28-v1: regressão para a nova ordem Scope → CI → OK.

    Em pt27 a ordem era CI → Scope → OK. Mudar Scope DEPOIS do CI pode
    causar re-render do popup ao seleccionar "Selected Subtree" e
    resetar o campo CI para o default do scope novo. pt28-v1 inverte
    para Scope PRIMEIRO; o re-render acontece antes do CI ser escrito.

    Verifica a ordem via spies em `_set_scope_in_popup` +
    `_fill_ci_target_in_popup` + `_click_ok_in_popup`. A primeira call
    a `_set_scope_in_popup` deve preceder a primeira a
    `_fill_ci_target_in_popup`, que deve preceder a primeira a
    `_click_ok_in_popup`.
    """
    fake_rect = (666, 372, 416, 214)
    pf._wait_for_nash_popup = MagicMock(return_value=fake_rect)

    call_order = []
    pf._set_scope_in_popup = MagicMock(
        side_effect=lambda *a, **kw: call_order.append("scope")
    )
    pf._fill_ci_target_in_popup = MagicMock(
        side_effect=lambda *a, **kw: call_order.append("ci")
    )
    pf._click_ok_in_popup = MagicMock(
        side_effect=lambda *a, **kw: call_order.append("ok")
    )

    pf.start_calculation_selected_subtree((10, 10, 1024, 768), ci_target=10.0)

    assert call_order == ["scope", "ci", "ok"], (
        f"pt28-v1 requer ordem Scope→CI→OK; got {call_order}"
    )


def test_set_scope_in_popup_logs_absolute_dropdown_coords_pt28v1(pf, capsys):
    """pt28-v1: logging defensivo regista coord absoluta do dropdown click
    antes do click. Permite diagnóstico cruzado com screenshot pós-smoke
    sem re-calibrar especulativamente as REL."""
    pf._set_scope_in_popup(popup_rect=(666, 372, 416, 214))
    out = capsys.readouterr().out

    # Dropdown abs = 666 + 278 = 944, 372 + 67 = 439 (REL pt26)
    expected_dropdown_x = 666 + pf.SCOPE_DROPDOWN_REL_X
    expected_dropdown_y = 372 + pf.SCOPE_DROPDOWN_REL_Y
    assert "dropdown click @" in out
    assert f"({expected_dropdown_x},{expected_dropdown_y})" in out


def test_set_scope_in_popup_logs_absolute_option_coords_pt28v1(pf, capsys):
    """pt28-v1: logging da option (Selected Subtree) click @ coords absolutas."""
    pf._set_scope_in_popup(popup_rect=(666, 372, 416, 214))
    out = capsys.readouterr().out

    expected_option_x = 666 + pf.SCOPE_OPTION_SELECTED_SUBTREE_REL_X
    expected_option_y = 372 + pf.SCOPE_OPTION_SELECTED_SUBTREE_REL_Y
    assert "option click @" in out
    assert f"({expected_option_x},{expected_option_y})" in out


def test_set_scope_in_popup_logs_include_popup_rect_for_diagnostics(pf, capsys):
    """pt28-v1: log inclui o popup_rect completo + as REL aplicadas.
    Permite reproduzir a aritmética sem assumir o rect do smoke."""
    pf._set_scope_in_popup(popup_rect=(100, 200, 416, 214))
    out = capsys.readouterr().out

    # popup_rect aparece em formato legível
    assert "popup_rect=(100,200,416,214)" in out
    # REL aparecem para cruzar com constantes
    assert (f"rel=({pf.SCOPE_DROPDOWN_REL_X},{pf.SCOPE_DROPDOWN_REL_Y})") in out


def test_fill_ci_target_in_popup_logs_absolute_field_coord_pt28v1(pf, capsys):
    """pt28-v1: `_fill_ci_target_in_popup` regista coord absoluta do field
    click antes do click. Mesma razão que `_set_scope_in_popup`."""
    pf._fill_ci_target_in_popup(popup_rect=(666, 372, 416, 214), ci_target=10.0)
    out = capsys.readouterr().out

    expected_x = 666 + pf.CI_TARGET_POPUP_REL_X
    expected_y = 372 + pf.CI_TARGET_POPUP_REL_Y
    assert "field click @" in out
    assert f"({expected_x},{expected_y})" in out


def test_start_calculation_selected_subtree_aborts_if_popup_not_detected(pf, capsys):
    """Popup detection devolve None (timeout) → early-return WARN, sem
    fill CI / scope / OK."""
    pf._wait_for_nash_popup = MagicMock(return_value=None)

    pf.start_calculation_selected_subtree(wpos=(0, 0, 1024, 768), ci_target=10.0)

    # Calculate foi clicado mas nada mais.
    pf.click_rel.assert_called_once()  # apenas Calculate
    pf.pyautogui.click.assert_not_called()
    pf.pyautogui.press.assert_not_called()
    out = capsys.readouterr().out
    assert "popup não detectado" in out


def test_start_calculation_selected_subtree_skips_calculate_when_placeholder(pf, capsys):
    """Regressão: se Calculate button coord um dia voltar a 0 (rollback de
    calibração pt26), early-return WARN sem click_rel."""
    pf._wait_for_nash_popup = MagicMock(return_value=None)
    pf.CALCULATE_BUTTON_X = 0
    pf.CALCULATE_BUTTON_Y = 0

    pf.start_calculation_selected_subtree(wpos=(0, 0, 1024, 768), ci_target=10.0)

    pf.click_rel.assert_not_called()  # placeholder → defensive
    out = capsys.readouterr().out
    assert "_click_calculate_button" in out
    assert "não calibrados" in out


def test_calculate_button_constants_calibrated_after_pt26_smoke(pf):
    """Sanity: pt26 smoke 19 Maio calibrou (204, 59) rel à wpos."""
    assert pf.CALCULATE_BUTTON_X > 0
    assert pf.CALCULATE_BUTTON_Y > 0


# ── _wait_for_nash_popup ────────────────────────────────────────────────

def test_wait_for_nash_popup_returns_rect_when_title_matches(pf):
    """Janela com título exacto "Nash Calculation" (capturado em smoke
    19 Maio via `pyautogui.getAllWindows()`) e dimensões válidas → devolve
    rect."""
    fake_win = MagicMock()
    fake_win.title = "Nash Calculation"
    fake_win.left = 590
    fake_win.top = 337
    fake_win.width = 436
    fake_win.height = 230
    pf.pyautogui.getAllWindows = MagicMock(return_value=[fake_win])

    rect = pf._wait_for_nash_popup(timeout=0.5, poll_interval=0.05)
    assert rect == (590, 337, 436, 230)


def test_wait_for_nash_popup_matches_case_insensitively(pf):
    """Substring match é case-insensitive — robustez face a casing
    inesperado do título Qt."""
    fake_win = MagicMock()
    fake_win.title = "nash calculation"
    fake_win.left = 100
    fake_win.top = 200
    fake_win.width = 400
    fake_win.height = 250
    pf.pyautogui.getAllWindows = MagicMock(return_value=[fake_win])

    rect = pf._wait_for_nash_popup(timeout=0.3, poll_interval=0.05)
    assert rect == (100, 200, 400, 250)


def test_wait_for_nash_popup_rejects_unrelated_calculate_window(pf):
    """Título contendo só "Calculate" (sem "Nash Calculation") já NÃO
    matcha em pt26 — hint refinado reduz falsos positivos vs pt25e
    (que matchava "Calculate" sozinho)."""
    win = MagicMock()
    win.title = "Calculate Strategy"
    win.left = 100
    win.top = 200
    win.width = 400
    win.height = 250
    pf.pyautogui.getAllWindows = MagicMock(return_value=[win])

    rect = pf._wait_for_nash_popup(timeout=0.3, poll_interval=0.05)
    assert rect is None


def test_wait_for_nash_popup_rejects_partial_nash_window(pf):
    """"Nash Equilibrium" (substring "Nash" sozinho) já NÃO matcha em
    pt26 — exige "Nash Calculation" completo."""
    win = MagicMock()
    win.title = "Nash Equilibrium"
    win.left = 0
    win.top = 0
    win.width = 400
    win.height = 200
    pf.pyautogui.getAllWindows = MagicMock(return_value=[win])

    rect = pf._wait_for_nash_popup(timeout=0.3, poll_interval=0.05)
    assert rect is None


def test_wait_for_nash_popup_returns_none_on_timeout(pf):
    """Nenhuma janela com hint match → None após timeout."""
    other_win = MagicMock()
    other_win.title = "Some Other Window"
    other_win.left = 0
    other_win.top = 0
    other_win.width = 800
    other_win.height = 600
    pf.pyautogui.getAllWindows = MagicMock(return_value=[other_win])

    rect = pf._wait_for_nash_popup(timeout=0.3, poll_interval=0.05)
    assert rect is None


def test_wait_for_nash_popup_skips_minimized_windows(pf):
    """Janela com width/height 0 (minimizada) é ignorada mesmo com title
    match."""
    minimized = MagicMock()
    minimized.title = "Nash Calculation"
    minimized.left = 0
    minimized.top = 0
    minimized.width = 0
    minimized.height = 0
    pf.pyautogui.getAllWindows = MagicMock(return_value=[minimized])

    rect = pf._wait_for_nash_popup(timeout=0.3, poll_interval=0.05)
    assert rect is None


def test_wait_for_nash_popup_skips_empty_title(pf):
    """Janela sem título (compositor/system) é ignorada."""
    empty_title = MagicMock()
    empty_title.title = ""
    empty_title.left = 100
    empty_title.top = 100
    empty_title.width = 500
    empty_title.height = 300
    pf.pyautogui.getAllWindows = MagicMock(return_value=[empty_title])

    rect = pf._wait_for_nash_popup(timeout=0.3, poll_interval=0.05)
    assert rect is None


def test_wait_for_nash_popup_survives_getAllWindows_exception(pf):
    """`getAllWindows` raises (race condition) → log + retry; eventual None."""
    pf.pyautogui.getAllWindows = MagicMock(side_effect=RuntimeError("race"))
    rect = pf._wait_for_nash_popup(timeout=0.3, poll_interval=0.05)
    assert rect is None


# ── _fill_ci_target_in_popup ────────────────────────────────────────────

def test_fill_ci_target_in_popup_clicks_then_pastes_value(pf):
    """popup_rect=(666,372,416,214) + pixels-rel (270, 109) → click em
    (666+270, 372+109)=(936, 481). Depois ctrl+a + paste + ctrl+v."""
    pf._fill_ci_target_in_popup(popup_rect=(666, 372, 416, 214), ci_target=10.0)

    # 1 click + 2 hotkeys (ctrl+a, ctrl+v) + 1 pyperclip.copy
    assert pf.pyautogui.click.call_count == 1
    (click_x, click_y), _ = pf.pyautogui.click.call_args
    assert (click_x, click_y) == (666 + pf.CI_TARGET_POPUP_REL_X,
                                   372 + pf.CI_TARGET_POPUP_REL_Y)
    assert pf.pyautogui.hotkey.call_args_list == [
        call('ctrl', 'a'), call('ctrl', 'v'),
    ]
    pf.pyperclip.copy.assert_called_once_with("10.0")


def test_fill_ci_target_in_popup_defensive_on_none_rect(pf, capsys):
    pf._fill_ci_target_in_popup(popup_rect=None, ci_target=10.0)
    pf.pyautogui.click.assert_not_called()
    out = capsys.readouterr().out
    assert "[WARN]" in out


# ── _click_ok_in_popup ─────────────────────────────────────────────────

def test_click_ok_in_popup_presses_enter(pf):
    """OK do popup Nash via Enter (convenção universal Qt default-button)."""
    pf._click_ok_in_popup(popup_rect=(666, 372, 416, 214))
    pf.pyautogui.press.assert_called_once_with('enter')


# ── navigate_to_target_node (B1) ───────────────────────────────────────

def test_navigate_to_target_node_none_skips(pf, capsys):
    """`target_node_offset=None` → 0 presses, log skip."""
    pf.navigate_to_target_node(wpos=(0, 0, 1024, 768), target_node_offset=None)
    pf.pyautogui.press.assert_not_called()
    pf.click_rel.assert_not_called()  # sem focus click
    assert "skip" in capsys.readouterr().out.lower()


def test_navigate_to_target_node_zero_skips(pf):
    """`target_node_offset=0` → 0 presses (cursor já na 1ª linha)."""
    pf.navigate_to_target_node(wpos=(0, 0, 1024, 768), target_node_offset=0)
    pf.pyautogui.press.assert_not_called()


def test_navigate_to_target_node_presses_down_N_times(pf):
    """pt28 (#FOCUS-CLICK-REMOVAL): `target_node_offset=5` → 5 ↓ presses,
    SEM focus click (Strategy Table tem foco por default pós-1ª-run no
    .exe pt26; ver docstring DEPRECATED em `_focus_strategy_table`)."""
    pf.navigate_to_target_node(wpos=(0, 0, 1024, 768), target_node_offset=5)
    pf.click_rel.assert_not_called()  # pt28: SEM focus click
    assert pf.pyautogui.press.call_count == 5
    for call_args in pf.pyautogui.press.call_args_list:
        assert call_args == call('down')


def test_navigate_to_target_node_negative_skips_with_warn(pf, capsys):
    """Negativo é bug no compute → log WARN, skip."""
    pf.navigate_to_target_node(wpos=(0, 0, 1024, 768), target_node_offset=-3)
    pf.pyautogui.press.assert_not_called()
    out = capsys.readouterr().out
    assert "[WARN]" in out


def test_navigate_to_target_node_huge_offset_skips(pf, capsys):
    """Sanity: offset > 100 é improvável e indica bug → skip."""
    pf.navigate_to_target_node(wpos=(0, 0, 1024, 768), target_node_offset=150)
    pf.pyautogui.press.assert_not_called()
    out = capsys.readouterr().out
    assert "[WARN]" in out


def test_navigate_to_target_node_non_int_skips_with_warn(pf, capsys):
    """Tipo errado (e.g., float) → WARN, skip. (bool é subclass de int em
    Python — esses passam silenciosamente, mas o backend nunca devolve
    bool.)"""
    pf.navigate_to_target_node(wpos=(0, 0, 1024, 768), target_node_offset=3.5)
    pf.pyautogui.press.assert_not_called()
    out = capsys.readouterr().out
    assert "[WARN]" in out


# ── pt28 fixes (#FOCUS-CLICK-REMOVAL + #FINALIZE-NEVER-FIRES-ON-NO-OP) ─

def test_navigate_to_target_node_never_calls_focus_strategy_table_after_pt28(pf):
    """Regressão para causa raiz pt27 GG-5944816316.

    Antes de pt28, `navigate_to_target_node` chamava `_focus_strategy_table`
    como passo intermédio (click em STRATEGY_TABLE_FOCUS_X/Y, coords nunca
    calibradas em smoke). Este click tirava o foco que estava bom no .exe
    pt26 (Strategy Table tem foco por default pós-1ª-run), as 4 setas-down
    iam para sítio nenhum, cursor não descia até à linha do raiser real,
    2º Calculate clicava sobre selecção inválida → popup Nash nunca abria
    → `_wait_for_nash_popup` timeout silencioso → finalize exportava zip
    da 1ª run sem WARN.

    Pós-pt28 o focus click foi removido. Esta regressão garante que
    qualquer offset válido (testados 1, 3, 7, 42 — cobre boundaries baixo,
    típico mid-MTT, alto-mas-plausível, sanity acima do típico) chega às
    setas-down SEM passar por focus click.
    """
    for offset in (1, 3, 7, 42):
        pf.click_rel.reset_mock()
        pf.pyautogui.press.reset_mock()

        pf.navigate_to_target_node(wpos=(0, 0, 1024, 768), target_node_offset=offset)

        pf.click_rel.assert_not_called()
        assert pf.pyautogui.press.call_count == offset
        for c in pf.pyautogui.press.call_args_list:
            assert c == call('down')


def test_start_calculation_selected_subtree_returns_true_when_popup_detected(pf):
    """pt28 (#FINALIZE-NEVER-FIRES-ON-NO-OP): retorno bool.

    Popup detectado (passos 1-4 completam) → `True`. Caller (`setup_hand`)
    interpreta como "2ª run em curso — finalize exporta zip pós-2ª-run".
    """
    pf._wait_for_nash_popup = MagicMock(return_value=(666, 372, 416, 214))

    result = pf.start_calculation_selected_subtree(
        wpos=(10, 10, 1024, 768), ci_target=10.0
    )

    assert result is True


def test_start_calculation_selected_subtree_returns_false_when_popup_timeout(pf, capsys):
    """pt28 (#FINALIZE-NEVER-FIRES-ON-NO-OP): retorno bool — caminho de
    falha.

    Popup não detectado (`_wait_for_nash_popup` devolve None) → `False`,
    sem fill CI / scope / OK. Caller (`setup_hand`) interpreta como "2ª run
    falhou — finalize vai exportar zip da 1ª run apenas, com WARN explícito"
    (vs comportamento pré-pt28 onde o falhanço era silencioso e
    `finalize_after_second_run` corria sempre).
    """
    pf._wait_for_nash_popup = MagicMock(return_value=None)

    result = pf.start_calculation_selected_subtree(
        wpos=(10, 10, 1024, 768), ci_target=10.0
    )

    assert result is False
    pf.pyautogui.click.assert_not_called()  # sem fill CI / scope clicks
    pf.pyautogui.press.assert_not_called()  # sem OK Enter
    assert "popup não detectado" in capsys.readouterr().out
