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
    de ser stateful (paste devolve o último copy) porque `paste_hh` /
    `paste_path` usam `clipboard_safe_paste`, que faz set + read-back de
    verificação. Com
    `pyperclip` como `MagicMock` puro, `paste()` devolve outro MagicMock
    (!= target) → mismatch → n_retries → RuntimeError. Stateful mock evita
    isto sem perder a capacidade de `pyperclip.copy.assert_called_once_with(...)`.
    """
    if "patched_funcs" in sys.modules:
        del sys.modules["patched_funcs"]
    import patched_funcs as _pf  # noqa: E402
    _pf.click_rel = MagicMock(name="click_rel")
    _pf.pyautogui = MagicMock(name="pyautogui")
    # pt32 v2: `_click_calculate_button` resolve `find_hrc()` (global Baltazar
    # do .pyc, ausente no import standalone) para a origem da coord. Default:
    # janela principal HRC fake. Tests de coord/None sobrepõem.
    _pf.find_hrc = MagicMock(
        name="find_hrc",
        return_value=SimpleNamespace(left=300, top=70, width=1050, height=850),
    )

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


# ── _set_scope_in_popup (pt64: SysListView32 do dropdown) ───────────────
#
# Helpers mockados como o antigo `_find_combo_with_item`: `_find_nash_popup_hwnd`,
# `_find_scope_dropdown_listview`, `_lv_item_count`, `_lv_selected_index`. O
# `pf.pyautogui` mock captura click/press/typewrite. O índice do read-back é
# 1 (Full Tree=0, Selected Subtree=1 — calibração pt64).

def _wire_scope(pf, lv=7777, count=2, sel_seq=(0, 1)):
    """Configura os mocks comuns do happy/abort path do `_set_scope_in_popup`."""
    pf._find_nash_popup_hwnd = MagicMock(return_value=4242)
    pf._find_scope_dropdown_listview = MagicMock(return_value=lv)
    pf._lv_item_count = MagicMock(return_value=count)
    pf._lv_selected_index = MagicMock(side_effect=list(sel_seq))
    pf._pt30_user32 = MagicMock()


def test_set_scope_none_rect_returns_false_no_click(pf, capsys):
    """`popup_rect=None` → WARN + early-return False, zero clicks/presses."""
    ok = pf._set_scope_in_popup(popup_rect=None)
    assert ok is False
    pf.pyautogui.click.assert_not_called()
    out = capsys.readouterr().out
    assert "[WARN]" in out and "popup_rect" in out


def test_set_scope_no_popup_hwnd_returns_false(pf, capsys):
    """popup Nash hwnd não encontrado → False, sem abrir dropdown."""
    pf._find_nash_popup_hwnd = MagicMock(return_value=None)
    ok = pf._set_scope_in_popup(popup_rect=_SMOKE_POPUP_RECT)
    assert ok is False
    pf.pyautogui.click.assert_not_called()
    assert "[WARN]" in capsys.readouterr().out


def test_set_scope_happy_path_typesearch_confirms(pf, capsys):
    """Dropdown abre, count=2, type-search 'Selected' move a selecção 0→1, o
    read-back LVM confirma idx==1 → Enter (commit) → True, sem fallback Down."""
    _wire_scope(pf, sel_seq=(0, 1))   # before=0, após typewrite=1
    ok = pf._set_scope_in_popup(popup_rect=_SMOKE_POPUP_RECT)
    assert ok is True
    # foco-click no campo Scope (rel pt61) + F4 p/ abrir
    left, top, _w, _h = _SMOKE_POPUP_RECT
    pf.pyautogui.click.assert_any_call(left + pf.SCOPE_DROPDOWN_REL_X,
                                       top + pf.SCOPE_DROPDOWN_REL_Y)
    presses = [c.args[0] for c in pf.pyautogui.press.call_args_list]
    assert "f4" in presses and "enter" in presses
    assert "down" not in presses          # type-search bastou, sem fallback
    pf.pyautogui.typewrite.assert_called_once()
    assert "Selected Subtree" in capsys.readouterr().out


def test_set_scope_fallback_arrow_when_typesearch_misses(pf):
    """type-search não move (fica 0); fallback determinístico Home→Down leva a
    idx 1; read-back confirma → True, com 'home'+'down'+'enter'."""
    _wire_scope(pf, sel_seq=(0, 0, 1))    # before=0, pós-type=0, pós-down=1
    ok = pf._set_scope_in_popup(popup_rect=_SMOKE_POPUP_RECT)
    assert ok is True
    presses = [c.args[0] for c in pf.pyautogui.press.call_args_list]
    assert presses.count("home") == 1 and presses.count("down") == 1
    assert "enter" in presses


def test_set_scope_aborts_when_dropdown_never_opens(pf, capsys):
    """`_find_scope_dropdown_listview` devolve None nas 2 tentativas → False,
    NÃO faz Enter (não commita nada)."""
    pf._find_nash_popup_hwnd = MagicMock(return_value=4242)
    pf._find_scope_dropdown_listview = MagicMock(return_value=None)
    pf._pt30_user32 = MagicMock()
    ok = pf._set_scope_in_popup(popup_rect=_SMOKE_POPUP_RECT)
    assert ok is False
    presses = [c.args[0] for c in pf.pyautogui.press.call_args_list]
    assert presses.count("f4") == 2 and "enter" not in presses
    assert "[WARN]" in capsys.readouterr().out


def test_set_scope_aborts_when_count_not_two(pf, capsys):
    """count≠2 (UI mudou) → Esc + False, sem ler selecção nem Enter."""
    _wire_scope(pf, count=3)
    ok = pf._set_scope_in_popup(popup_rect=_SMOKE_POPUP_RECT)
    assert ok is False
    presses = [c.args[0] for c in pf.pyautogui.press.call_args_list]
    assert "escape" in presses and "enter" not in presses
    pf._lv_selected_index.assert_not_called()
    out = capsys.readouterr().out
    assert "[WARN]" in out and "count" in out


def test_set_scope_aborts_when_readback_never_reaches_target(pf, capsys):
    """A selecção nunca chega a idx 1 (type-search e fallback falham) → Esc +
    False, sem Enter — o caller aborta a 2ª run."""
    _wire_scope(pf, sel_seq=(0, 0, 0))    # nunca sai do 0
    ok = pf._set_scope_in_popup(popup_rect=_SMOKE_POPUP_RECT)
    assert ok is False
    presses = [c.args[0] for c in pf.pyautogui.press.call_args_list]
    assert "escape" in presses and "enter" not in presses
    out = capsys.readouterr().out
    assert "[WARN]" in out and "read-back" in out


def test_set_scope_target_index_constant_is_calibrated_pt64(pf):
    """Calibração pt64: Full Tree=0, Selected Subtree=1. Guarda contra um
    rollback acidental do mapa idx→texto."""
    assert pf.SCOPE_LIST_SELECTED_SUBTREE_INDEX == 1
    # os RELs de foco do campo Scope continuam calibrados (reusados como ponto
    # de foco-click antes do F4).
    assert 0 < pf.SCOPE_DROPDOWN_REL_X < 400
    assert 0 < pf.SCOPE_DROPDOWN_REL_Y < 400


def test_set_scope_uses_pyautogui_not_click_rel_pt64(pf):
    """O foco-click é `pyautogui.click(abs)`, nunca `click_rel` (que opera sobre
    a janela principal do HRC, não o popup)."""
    _wire_scope(pf, sel_seq=(0, 1))
    pf._set_scope_in_popup(popup_rect=_SMOKE_POPUP_RECT)
    pf.click_rel.assert_not_called()
    assert pf.pyautogui.click.called


# ── start_calculation_selected_subtree (wiring) ─────────────────────────

def test_start_calculation_selected_subtree_full_flow_with_popup(pf):
    """Piece 2 end-to-end (pt66): com popup detectado E Scope confirmado, os
    passos disparam na ordem Calculate → wait popup → scope → OK. O CI já NÃO é
    escrito (default do popup = 10.0). Validamos o fluxo + que o OK é invocado
    quando o Scope confirma."""
    pf._wait_for_nash_popup = MagicMock(return_value=(666, 372, 416, 214))
    pf._set_scope_in_popup = MagicMock(return_value=True)   # pt61: Win32 confirmou
    pf._click_ok_in_popup = MagicMock()
    wpos = (10, 10, 1024, 768)

    result = pf.start_calculation_selected_subtree(wpos, ci_target=10.0)

    # pt32 v2: Calculate via pyautogui.click na origem find_hrc() (504, 134).
    pf.pyautogui.click.assert_any_call(504, 134)
    pf.click_rel.assert_not_called()
    pf._wait_for_nash_popup.assert_called_once()
    pf._set_scope_in_popup.assert_called_once()
    pf._click_ok_in_popup.assert_called_once()       # OK só porque Scope confirmou
    assert result is True


def test_start_calculation_selected_subtree_aborts_when_scope_unconfirmed(pf, capsys):
    """pt61 (#HRC-2ND-RUN-BLIND-CLICKS): popup detectado mas Scope NÃO confirma
    (_set_scope_in_popup → False) → ABORTA: NÃO clica OK, cancela o popup,
    devolve "scope_unconfirmed". Evita Full-Tree disfarçado de Selected Subtree
    na biblioteca de estudo."""
    pf._wait_for_nash_popup = MagicMock(return_value=(666, 372, 416, 214))
    pf._set_scope_in_popup = MagicMock(return_value=False)  # NÃO confirma
    pf._click_ok_in_popup = MagicMock()
    pf._cancel_nash_popup = MagicMock()

    result = pf.start_calculation_selected_subtree((10, 10, 1024, 768), ci_target=10.0)

    assert result == "scope_unconfirmed"
    pf._click_ok_in_popup.assert_not_called()         # NÃO clica OK
    pf._cancel_nash_popup.assert_called_once()        # cancela o popup
    assert "[ABORT]" in capsys.readouterr().out


def test_start_calculation_selected_subtree_calls_scope_before_ok_pt66(pf):
    """pt66: ordem Scope → OK (o passo de CI foi removido — o watcher já não
    escreve o CI; default do popup = 10.0).

    Verifica a ordem via spies em `_set_scope_in_popup` + `_click_ok_in_popup`.
    A primeira call a `_set_scope_in_popup` deve preceder a primeira a
    `_click_ok_in_popup` (o OK só dispara porque o Scope confirmou).
    """
    fake_rect = (666, 372, 416, 214)
    pf._wait_for_nash_popup = MagicMock(return_value=fake_rect)

    call_order = []
    # Scope devolve True (confirmado) p/ o flow prosseguir até ao OK.
    pf._set_scope_in_popup = MagicMock(
        side_effect=lambda *a, **kw: (call_order.append("scope"), True)[1]
    )
    pf._click_ok_in_popup = MagicMock(
        side_effect=lambda *a, **kw: call_order.append("ok")
    )

    pf.start_calculation_selected_subtree((10, 10, 1024, 768), ci_target=10.0)

    assert call_order == ["scope", "ok"], (
        f"pt66 requer ordem Scope→OK (sem CI); got {call_order}"
    )


# pt66: testes de `_fill_ci_target_in_popup` (Win32 WM_SETTEXT + read-back e
# mismatch→fallback) REMOVIDOS — o watcher já não escreve o CI (função removida;
# o default do popup é sempre 10.0). A salvaguarda passou a ser só-leitura
# (`_ci_target_readback_warn`, testada em test_watcher_hand_import_popup.py).


def test_start_calculation_selected_subtree_aborts_if_popup_not_detected(pf, capsys):
    """Popup detection devolve None (timeout) → early-return WARN, sem
    scope / OK."""
    pf._wait_for_nash_popup = MagicMock(return_value=None)

    pf.start_calculation_selected_subtree(wpos=(0, 0, 1024, 768), ci_target=10.0)

    # pt32 v2: Calculate clicado via pyautogui.click (1x) mas nada mais.
    pf.pyautogui.click.assert_called_once()  # apenas Calculate
    pf.click_rel.assert_not_called()
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

    pf.pyautogui.click.assert_not_called()  # placeholder → defensive (pt32 v2)
    pf.find_hrc.assert_not_called()  # early-return ANTES de find_hrc
    out = capsys.readouterr().out
    assert "_click_calculate_button" in out
    assert "não calibrados" in out


def test_calculate_button_constants_calibrated_after_pt26_smoke(pf):
    """Sanity: pt26 calibrou X=204; pt32 v1 alinhou Y=64 com o Baltazar OG.
    pt32 v2 não mexe nos valores — só a ORIGEM (find_hrc em vez de wpos)."""
    assert pf.CALCULATE_BUTTON_X == 204
    assert pf.CALCULATE_BUTTON_Y == 64


def test_click_calculate_button_uses_find_hrc_origin_and_logs_pt32v2(pf, capsys):
    """pt32 v2: a coord é calculada a partir de find_hrc() (janela principal),
    NÃO de wpos (que era o wizard fechado). Regista [calc-diag pre-click] com
    coord absoluta + hrc_window + foreground; click via pyautogui.click."""
    pf.find_hrc = MagicMock(
        return_value=SimpleNamespace(left=283, top=65, width=1050, height=850)
    )
    pf._pt30_user32 = MagicMock()
    pf._pt30_user32.GetForegroundWindow.return_value = 7777
    pf._pt30_user32.GetWindowTextLengthW.return_value = 0  # titulo vazio: simplifica

    # wpos passado mas IGNORADO (pt32 v2): valores propositadamente != find_hrc.
    pf._click_calculate_button((9999, 8888, 1, 1))

    out = capsys.readouterr().out
    assert "[calc-diag pre-click]" in out
    # coord absoluta = (283+204, 65+64) = (487, 129), origem find_hrc não wpos
    assert "coord=(487,129)" in out
    assert "hrc_window=(283,65,1050,850)" in out
    assert "hwnd=7777" in out
    # click cego via pyautogui.click nas coords absolutas; click_rel já não usado
    pf.pyautogui.click.assert_called_once_with(487, 129)
    pf.click_rel.assert_not_called()


def test_click_calculate_button_tolerates_foreground_exception_pt32(pf, capsys):
    """Logging defensivo: se GetForegroundWindow falhar, WARN inline mas o
    click acontece na mesma (nao bloqueia o flow). pt32 v2: coord via find_hrc."""
    pf.find_hrc = MagicMock(
        return_value=SimpleNamespace(left=100, top=50, width=1050, height=850)
    )
    pf._pt30_user32 = MagicMock()
    pf._pt30_user32.GetForegroundWindow.side_effect = RuntimeError("boom")

    pf._click_calculate_button((0, 0, 800, 600))

    out = capsys.readouterr().out
    assert "[calc-diag pre-click]" in out
    assert "falhou" in out
    # click acontece nas coords da janela HRC (100+204, 50+64) = (304, 114)
    pf.pyautogui.click.assert_called_once_with(304, 114)


def test_click_calculate_button_raises_when_find_hrc_none_pt32v2(pf, capsys):
    """pt32 v2: find_hrc() devolve None (janela principal HRC desapareceu) ->
    WARN + raise, sem click silencioso (queremos saber, não no-op)."""
    pf.find_hrc = MagicMock(return_value=None)

    with pytest.raises(RuntimeError, match="HRC_MAIN_WINDOW_NOT_FOUND"):
        pf._click_calculate_button((0, 0, 800, 600))

    out = capsys.readouterr().out
    assert "[WARN]" in out
    assert "find_hrc() devolveu None" in out
    pf.pyautogui.click.assert_not_called()


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


# ── _click_ok_in_popup (pt33 v1: BM_CLICK Win32) ───────────────────────

def test_click_ok_popup_nash_uses_bm_click_pt33(pf):
    """pt33 v1: OK do popup Nash via enumeração Win32 + BM_CLICK no hwnd do
    Button OK (não Enter, que não funciona no popup — smoke pt32 v2)."""
    pf._pt30_user32 = MagicMock()
    pf._find_nash_popup_hwnd = MagicMock(return_value=4242)
    pf._find_ok_button = MagicMock(return_value=8484)

    pf._click_ok_in_popup(popup_rect=(666, 372, 416, 214))

    pf._find_ok_button.assert_called_once_with(4242)
    pf._pt30_user32.SendMessageW.assert_called_once_with(8484, pf.BM_CLICK, 0, 0)
    pf.pyautogui.press.assert_not_called()  # pt33: já não usa Enter


def test_click_ok_in_popup_warns_when_popup_hwnd_not_found_pt33(pf, capsys):
    """find_nash_popup_hwnd None -> WARN, sem SendMessage (failure explícito)."""
    pf._pt30_user32 = MagicMock()
    pf._find_nash_popup_hwnd = MagicMock(return_value=None)

    pf._click_ok_in_popup(popup_rect=(0, 0, 1, 1))

    out = capsys.readouterr().out
    assert "[WARN]" in out
    assert "[ok-click]" in out
    pf._pt30_user32.SendMessageW.assert_not_called()


def test_click_ok_in_popup_warns_when_ok_button_not_found_pt33(pf, capsys):
    """Popup encontrado mas sem Button OK -> WARN, sem SendMessage."""
    pf._pt30_user32 = MagicMock()
    pf._find_nash_popup_hwnd = MagicMock(return_value=4242)
    pf._find_ok_button = MagicMock(return_value=None)

    pf._click_ok_in_popup(popup_rect=(0, 0, 1, 1))

    out = capsys.readouterr().out
    assert "[WARN]" in out
    assert "Button OK" in out
    pf._pt30_user32.SendMessageW.assert_not_called()


def test_find_ok_button_none_for_falsy_popup_pt33(pf):
    """Guard: hwnd_popup falsy -> None (sem enumeração). Mesma anatomia que
    `_find_finish_button(None)`."""
    assert pf._find_ok_button(None) is None
    assert pf._find_ok_button(0) is None


# ── navigate_to_target_node (B1) ───────────────────────────────────────

def test_navigate_to_target_node_none_skips(pf, capsys):
    """`target_node_offset=None` → 0 presses, log skip."""
    pf.navigate_to_target_node(wpos=(0, 0, 1024, 768), target_node_offset=None)
    pf.pyautogui.press.assert_not_called()
    pf.click_rel.assert_not_called()  # sem focus click
    assert "skip" in capsys.readouterr().out.lower()


def test_navigate_to_target_node_zero_focuses_root(pf):
    """pt61: offset 0 = o alvo É o nó-raiz → foco-click na raiz + 0 setas
    (find_hrc mock left=300,top=70 + ROOT_REL)."""
    pf.navigate_to_target_node(wpos=(0, 0, 1024, 768), target_node_offset=0)
    pf.pyautogui.click.assert_called_once_with(
        300 + pf.STRATEGY_TABLE_ROOT_REL_X, 70 + pf.STRATEGY_TABLE_ROOT_REL_Y)
    pf.pyautogui.press.assert_not_called()


def test_navigate_to_target_node_focus_root_then_presses_down_N(pf):
    """pt61 (#FOCO + offset): `target_node_offset=5` → foco-click no nó-raiz
    (fix do foco/início descoberto na re-smoke) + 5 ↓ presses. Usa
    pyautogui.click (janela principal via find_hrc), não click_rel."""
    pf.navigate_to_target_node(wpos=(0, 0, 1024, 768), target_node_offset=5)
    pf.click_rel.assert_not_called()
    pf.pyautogui.click.assert_called_once_with(
        300 + pf.STRATEGY_TABLE_ROOT_REL_X, 70 + pf.STRATEGY_TABLE_ROOT_REL_Y)
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

    Popup detectado + Scope confirmado (passos 1-4 completam) → `True`. Caller
    (`setup_hand`) interpreta como "2ª run em curso — finalize exporta zip".
    pt61: Scope/CI Win32 mockados a True (sem popup real no test machine).
    """
    pf._wait_for_nash_popup = MagicMock(return_value=(666, 372, 416, 214))
    pf._set_scope_in_popup = MagicMock(return_value=True)
    pf._click_ok_in_popup = MagicMock()

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
    # pt32 v2: Calculate via pyautogui.click (1x); sem fill CI / scope depois.
    pf.pyautogui.click.assert_called_once()  # apenas Calculate
    pf.pyautogui.press.assert_not_called()  # sem OK Enter
    assert "popup não detectado" in capsys.readouterr().out
