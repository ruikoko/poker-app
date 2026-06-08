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


# ── _set_scope_in_popup: defensive returns ──────────────────────────────

def test_set_scope_in_popup_early_returns_when_popup_rect_is_none(pf, capsys):
    """`popup_rect=None` → caller ainda não detecta popup (peça 2 wiring
    pendente). Função faz early-return com WARN; zero clicks."""
    pf._set_scope_in_popup(popup_rect=None)
    pf.pyautogui.click.assert_not_called()
    out = capsys.readouterr().out
    assert "[WARN]" in out
    assert "popup_rect" in out


def test_set_scope_in_popup_win32_setcursel_and_readback_confirms(pf, capsys):
    """pt61: caminho activo Win32. Acha o combo pelo item "Selected Subtree",
    seta por CB_SETCURSEL, notifica CBN_SELCHANGE e confirma por read-back
    (CB_GETCURSEL == idx) → devolve True, SEM pyautogui."""
    pf._find_nash_popup_hwnd = MagicMock(return_value=4242)
    pf._find_combo_with_item = MagicMock(return_value=(8484, 1))
    pf._pt30_user32 = MagicMock()
    pf._pt30_user32.GetDlgCtrlID.return_value = 55
    # CB_GETCURSEL (read-back) devolve o idx setado (1) → confirmado.
    pf._pt30_user32.SendMessageW.return_value = 1

    ok = pf._set_scope_in_popup(popup_rect=_SMOKE_POPUP_RECT)

    assert ok is True
    pf._find_combo_with_item.assert_called_once_with(4242, "selected subtree")
    # CB_SETCURSEL(combo, 1) foi enviado.
    pf._pt30_user32.SendMessageW.assert_any_call(8484, pf.CB_SETCURSEL, 1, 0)
    pf.pyautogui.click.assert_not_called()  # Win32: sem clique pyautogui
    out = capsys.readouterr().out
    assert "Selected Subtree" in out and "[WARN]" not in out


def test_set_scope_in_popup_win32_readback_mismatch_falls_back_to_pyautogui(pf, capsys):
    """Win32 não confirma (read-back != idx) → fallback pyautogui (baseline
    coords) + devolve False (não confirmado = caller aborta)."""
    pf._find_nash_popup_hwnd = MagicMock(return_value=4242)
    pf._find_combo_with_item = MagicMock(return_value=(8484, 1))
    pf._pt30_user32 = MagicMock()
    pf._pt30_user32.GetDlgCtrlID.return_value = 55
    pf._pt30_user32.SendMessageW.return_value = 0  # read-back devolve 0 != 1

    ok = pf._set_scope_in_popup(popup_rect=_SMOKE_POPUP_RECT)

    assert ok is False
    assert pf.pyautogui.click.call_count == 2  # fallback: dropdown + opção
    out = capsys.readouterr().out
    assert "[WARN]" in out and "read-back" in out


def test_set_scope_in_popup_fallback_unavailable_when_rect_none_and_no_popup(pf, capsys):
    """Sem popup Win32 E sem popup_rect → fallback indisponível → False, 0 clicks."""
    pf._find_nash_popup_hwnd = MagicMock(return_value=None)
    ok = pf._set_scope_in_popup(popup_rect=None)
    assert ok is False
    pf.pyautogui.click.assert_not_called()
    assert "[WARN]" in capsys.readouterr().out


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


def test_set_scope_in_popup_fallback_clicks_at_baseline_rel(pf):
    """pt61: quando o Win32 não está disponível (sem popup hwnd), o FALLBACK
    pyautogui clica nos baseline coords (left+REL). Self-consistente com as
    constantes actuais (popup 436×230)."""
    pf._find_nash_popup_hwnd = MagicMock(return_value=None)
    left, top, _w, _h = _SMOKE_POPUP_RECT
    pf._set_scope_in_popup(popup_rect=_SMOKE_POPUP_RECT)

    assert pf.pyautogui.click.call_args_list == [
        call(left + pf.SCOPE_DROPDOWN_REL_X, top + pf.SCOPE_DROPDOWN_REL_Y),
        call(left + pf.SCOPE_OPTION_SELECTED_SUBTREE_REL_X,
             top + pf.SCOPE_OPTION_SELECTED_SUBTREE_REL_Y),
    ]


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


def test_set_scope_in_popup_fallback_logs_not_confirmed(pf, capsys):
    """pt61: o fallback pyautogui é best-effort e NÃO confirmável → loga
    explicitamente que não foi confirmado por read-back (não simula sucesso)."""
    pf._find_nash_popup_hwnd = MagicMock(return_value=None)
    ok = pf._set_scope_in_popup(popup_rect=_SMOKE_POPUP_RECT)
    out = capsys.readouterr().out
    assert ok is False
    assert "NÃO confirmado" in out


# ── start_calculation_selected_subtree (wiring) ─────────────────────────

def test_start_calculation_selected_subtree_full_flow_with_popup(pf):
    """Piece 2 end-to-end: com popup detectado E Scope confirmado, todos os
    passos disparam na ordem pt28-v1: Calculate → wait popup → scope → CI → OK.
    pt61: Scope/CI são Win32 (mockados a True aqui); só validamos o fluxo +
    que o OK é invocado quando o Scope confirma."""
    pf._wait_for_nash_popup = MagicMock(return_value=(666, 372, 416, 214))
    pf._set_scope_in_popup = MagicMock(return_value=True)   # pt61: Win32 confirmou
    pf._fill_ci_target_in_popup = MagicMock(return_value=True)
    pf._click_ok_in_popup = MagicMock()
    wpos = (10, 10, 1024, 768)

    result = pf.start_calculation_selected_subtree(wpos, ci_target=10.0)

    # pt32 v2: Calculate via pyautogui.click na origem find_hrc() (504, 134).
    pf.pyautogui.click.assert_any_call(504, 134)
    pf.click_rel.assert_not_called()
    pf._wait_for_nash_popup.assert_called_once()
    pf._set_scope_in_popup.assert_called_once()
    pf._fill_ci_target_in_popup.assert_called_once()
    pf._click_ok_in_popup.assert_called_once()       # OK só porque Scope confirmou
    assert result is True


def test_start_calculation_selected_subtree_aborts_when_scope_unconfirmed(pf, capsys):
    """pt61 (#HRC-2ND-RUN-BLIND-CLICKS): popup detectado mas Scope NÃO confirma
    (_set_scope_in_popup → False) → ABORTA: NÃO clica OK, NÃO preenche CI, cancela
    o popup, devolve "scope_unconfirmed". Evita Full-Tree disfarçado de Selected
    Subtree na biblioteca de estudo."""
    pf._wait_for_nash_popup = MagicMock(return_value=(666, 372, 416, 214))
    pf._set_scope_in_popup = MagicMock(return_value=False)  # NÃO confirma
    pf._fill_ci_target_in_popup = MagicMock()
    pf._click_ok_in_popup = MagicMock()
    pf._cancel_nash_popup = MagicMock()

    result = pf.start_calculation_selected_subtree((10, 10, 1024, 768), ci_target=10.0)

    assert result == "scope_unconfirmed"
    pf._fill_ci_target_in_popup.assert_not_called()   # não chega ao CI
    pf._click_ok_in_popup.assert_not_called()         # NÃO clica OK
    pf._cancel_nash_popup.assert_called_once()        # cancela o popup
    assert "[ABORT]" in capsys.readouterr().out


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
    # pt61: scope/ci devolvem True (confirmado) p/ o flow prosseguir até ao OK.
    pf._set_scope_in_popup = MagicMock(
        side_effect=lambda *a, **kw: (call_order.append("scope"), True)[1]
    )
    pf._fill_ci_target_in_popup = MagicMock(
        side_effect=lambda *a, **kw: (call_order.append("ci"), True)[1]
    )
    pf._click_ok_in_popup = MagicMock(
        side_effect=lambda *a, **kw: call_order.append("ok")
    )

    pf.start_calculation_selected_subtree((10, 10, 1024, 768), ci_target=10.0)

    assert call_order == ["scope", "ci", "ok"], (
        f"pt28-v1 requer ordem Scope→CI→OK; got {call_order}"
    )


def test_fill_ci_target_win32_settext_and_readback_confirms(pf, capsys):
    """pt61: CI via Win32. Acha o Edit único, WM_SETTEXT "10" e confirma por
    read-back (WM_GETTEXT == "10") → True, sem pyautogui. CI inteiro = "10"
    (sem ".0")."""
    pf._find_nash_popup_hwnd = MagicMock(return_value=4242)
    pf._find_single_edit = MagicMock(return_value=9999)
    pf._read_edit_text = MagicMock(return_value="10")  # read-back bate
    pf._pt30_user32 = MagicMock()

    ok = pf._fill_ci_target_in_popup(popup_rect=_SMOKE_POPUP_RECT, ci_target=10.0)

    assert ok is True
    pf._find_single_edit.assert_called_once_with(4242)
    # WM_SETTEXT enviado ao Edit (wParam 0, lParam = endereço do buffer).
    sent = [c for c in pf._pt30_user32.SendMessageW.call_args_list
            if c.args[1] == pf.WM_SETTEXT]
    assert len(sent) == 1 and sent[0].args[0] == 9999
    pf.pyautogui.click.assert_not_called()
    assert "[WARN]" not in capsys.readouterr().out


def test_fill_ci_target_win32_readback_mismatch_falls_back(pf, capsys):
    """Read-back do CI não bate → fallback pyautogui + False."""
    pf._find_nash_popup_hwnd = MagicMock(return_value=4242)
    pf._find_single_edit = MagicMock(return_value=9999)
    pf._read_edit_text = MagicMock(return_value="")  # não confirma
    pf._pt30_user32 = MagicMock()

    ok = pf._fill_ci_target_in_popup(popup_rect=_SMOKE_POPUP_RECT, ci_target=10.0)

    assert ok is False
    assert pf.pyautogui.click.call_count == 1  # fallback: 1 click no campo
    out = capsys.readouterr().out
    assert "[WARN]" in out and "read-back" in out


def test_start_calculation_selected_subtree_aborts_if_popup_not_detected(pf, capsys):
    """Popup detection devolve None (timeout) → early-return WARN, sem
    fill CI / scope / OK."""
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


# ── _fill_ci_target_in_popup ────────────────────────────────────────────

def test_fill_ci_target_fallback_clicks_then_pastes_value(pf):
    """pt61: sem Edit Win32 identificável → fallback pyautogui. Click no baseline
    coord + ctrl+a + paste. CI inteiro = "10" (sem ".0"; o Edit do HRC aceita)."""
    pf._find_nash_popup_hwnd = MagicMock(return_value=None)  # força fallback
    pf._fill_ci_target_in_popup(popup_rect=(666, 372, 416, 214), ci_target=10.0)

    assert pf.pyautogui.click.call_count == 1
    (click_x, click_y), _ = pf.pyautogui.click.call_args
    assert (click_x, click_y) == (666 + pf.CI_TARGET_POPUP_REL_X,
                                   372 + pf.CI_TARGET_POPUP_REL_Y)
    assert pf.pyautogui.hotkey.call_args_list == [
        call('ctrl', 'a'), call('ctrl', 'v'),
    ]
    pf.pyperclip.copy.assert_called_once_with("10")


def test_fill_ci_target_in_popup_defensive_on_none_rect(pf, capsys):
    pf._fill_ci_target_in_popup(popup_rect=None, ci_target=10.0)
    pf.pyautogui.click.assert_not_called()
    out = capsys.readouterr().out
    assert "[WARN]" in out


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
    pf._fill_ci_target_in_popup = MagicMock(return_value=True)
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
