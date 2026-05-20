"""pt29 (#PT25D-WATCHER-FRAGILE-CLIPBOARD-OR-RESTORE): tests para
`clipboard_safe_paste` em `tools/watcher_src/patched_funcs.py`.

Vector observado em smoke real 14 Maio 2026: o Rui usa RDP/sync entre PC
principal e Beelink. Qualquer Ctrl+C em qualquer dos PCs (incluindo
comandos PowerShell colados) compete com o clipboard que o watcher
escreveu para o paste no HRC. Janela vulnerável: entre SetClipboardData
e Ctrl+V. Sintoma: paste chega ao HRC vazio, watcher continua
silenciosamente, corrida fica corrupta. Mapeado para 40 de 41 mãos
perdidas em 14 Maio.

Mitigação testada: `clipboard_safe_paste(target, n_retries=5)` faz
set + read-back imediato. Mismatch ⇒ sleep 50ms + retry (até n_retries).
Sucesso ⇒ sleep 10ms + Ctrl+V + sleep 50ms + read-back sanity (apenas
WARN se mudou). n_retries esgotados ⇒ WARN explícito + RuntimeError
(failure explícito > corrupção silenciosa).

Mesmo padrão de path-injection que `test_watcher_set_scope.py`:
`patched_funcs` não corre standalone — globais resolvidos via LOAD_GLOBAL
contra o namespace do módulo após marshal swap. Aqui injectamos mocks
controlados antes de invocar.
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
    """Carrega `patched_funcs` fresh. Cada teste configura
    `pf.pyperclip.copy.side_effect` / `paste.side_effect` à medida — não
    queremos clipboard stateful por defeito porque os tests de race
    precisam de simular mismatches deterministicamente."""
    if "patched_funcs" in sys.modules:
        del sys.modules["patched_funcs"]
    import patched_funcs as _pf  # noqa: E402
    _pf.click_rel = MagicMock(name="click_rel")
    _pf.pyautogui = MagicMock(name="pyautogui")
    _pf.pyperclip = MagicMock(name="pyperclip")
    _pf.time = SimpleNamespace(
        time=_real_time.time,
        sleep=MagicMock(name="time.sleep"),
    )
    yield _pf


def _wire_clipboard(pf, target, mismatch_returns):
    """Configura pyperclip.copy + pyperclip.paste para simular race.

    `pyperclip.paste()` devolve os valores em `mismatch_returns` na ordem
    em que é chamado, depois cai em `target` para todos os calls seguintes.
    Permite testar:
      - mismatch_returns=[]                → sucesso na 1ª tentativa
      - mismatch_returns=["wrong"] * 2     → mismatch nas 2 primeiras
                                             tentativas, sucesso na 3ª
      - mismatch_returns=["wrong"] * 10    → falha total (>= n_retries)
    """
    paste_responses = list(mismatch_returns)

    def _paste():
        if paste_responses:
            return paste_responses.pop(0)
        return target

    pf.pyperclip.copy.side_effect = lambda _t: None
    pf.pyperclip.paste.side_effect = _paste


# ── Spec test 1: «set falha nas primeiras 2 tentativas, sucede na 3ª» ──

def test_clipboard_safe_paste_succeeds_after_2_set_failures(pf, capsys):
    """3 copies (1 success após 2 mismatches no read-back) + 1 Ctrl+V."""
    _wire_clipboard(pf, "hello", mismatch_returns=["WRONG1", "WRONG2"])

    pf.clipboard_safe_paste("hello", n_retries=5)

    assert pf.pyperclip.copy.call_count == 3
    # 3 readbacks no loop + 1 sanity pós-paste = 4 pastes
    assert pf.pyperclip.paste.call_count == 4
    pf.pyautogui.hotkey.assert_called_once_with('ctrl', 'v')
    out = capsys.readouterr().out
    assert "locked after 3" in out


# ── Spec test 2: «mocka mismatch entre set e get, confirma retry» ──────

def test_clipboard_safe_paste_retries_on_set_get_mismatch(pf):
    """1 mismatch ⇒ pelo menos 1 retry. Sucesso na 2ª tentativa."""
    _wire_clipboard(pf, "target", mismatch_returns=["mismatched_value"])

    pf.clipboard_safe_paste("target")

    # 2 copies (1 mismatch + 1 success)
    assert pf.pyperclip.copy.call_count == 2
    # 2 readbacks no loop + 1 sanity pós-paste
    assert pf.pyperclip.paste.call_count == 3
    pf.pyautogui.hotkey.assert_called_once_with('ctrl', 'v')


# ── Spec test 3: «n_retries esgotados → warning + raise» ───────────────

def test_clipboard_safe_paste_raises_after_n_retries_exhausted(pf, capsys):
    """5 mismatches consecutivos → WARN + RuntimeError. Ctrl+V NÃO dispara
    (raise antes do paste — corrupção evitada)."""
    _wire_clipboard(pf, "target", mismatch_returns=["x"] * 5)

    with pytest.raises(RuntimeError, match="clipboard race"):
        pf.clipboard_safe_paste("target", n_retries=5)

    assert pf.pyperclip.copy.call_count == 5
    pf.pyautogui.hotkey.assert_not_called()
    out = capsys.readouterr().out
    assert "[WARN]" in out
    assert "failed to lock clipboard" in out


# ── Cobertura extra ────────────────────────────────────────────────────

def test_clipboard_safe_paste_succeeds_on_first_attempt_without_log_noise(pf, capsys):
    """Sem race: 1 copy + 1 read-back + Ctrl+V + 1 sanity. Sem "locked
    after" log (só logamos recovery se attempt > 1 — evita spam em ops
    saudáveis)."""
    _wire_clipboard(pf, "hello", mismatch_returns=[])

    pf.clipboard_safe_paste("hello")

    pf.pyperclip.copy.assert_called_once_with("hello")
    assert pf.pyperclip.paste.call_count == 2  # readback + sanity
    pf.pyautogui.hotkey.assert_called_once_with('ctrl', 'v')
    out = capsys.readouterr().out
    assert "locked after" not in out
    assert "[WARN]" not in out


def test_clipboard_safe_paste_default_n_retries_is_5(pf):
    """Signature `clipboard_safe_paste(target, n_retries=5)`: default 5
    tentativas. Sem arg explícito + 10 mismatches → falha após 5."""
    _wire_clipboard(pf, "target", mismatch_returns=["x"] * 10)

    with pytest.raises(RuntimeError):
        pf.clipboard_safe_paste("target")

    assert pf.pyperclip.copy.call_count == 5


def test_clipboard_safe_paste_retries_sleep_50ms_between_attempts(pf):
    """Spec: «sleep 50ms» entre attempts após mismatch."""
    _wire_clipboard(pf, "target", mismatch_returns=["x", "y", "z"])

    pf.clipboard_safe_paste("target", n_retries=5)

    sleep_args = [c.args[0] for c in pf.time.sleep.call_args_list]
    # 3 retries × 50ms inter-attempt sleeps
    assert sleep_args.count(0.05) >= 3
    # Pré-Ctrl+V 10ms (spec passo 4)
    assert 0.01 in sleep_args


def test_clipboard_safe_paste_handles_copy_raising_exception(pf, capsys):
    """`pyperclip.copy` pode levantar (e.g., clipboard ownership conflict
    em Windows). 2 raises seguidos de sucesso ⇒ 3 tentativas totais, WARN
    em cada raise, sem propagação da excepção."""
    copy_counter = {"n": 0}

    def _copy(text):
        copy_counter["n"] += 1
        if copy_counter["n"] <= 2:
            raise RuntimeError("clipboard locked by another app")

    pf.pyperclip.copy.side_effect = _copy
    pf.pyperclip.paste.side_effect = lambda: "hello"

    pf.clipboard_safe_paste("hello", n_retries=5)

    assert copy_counter["n"] == 3
    out = capsys.readouterr().out
    assert "copy raised" in out
    assert "[WARN]" in out


def test_clipboard_safe_paste_warns_on_post_paste_mutation_without_raising(pf, capsys):
    """Spec passo 5: «log warning se mudou». Race entre Ctrl+V e o
    read-back de sanity ⇒ WARN mas NÃO raise (paste já aconteceu, o dano
    se houver já foi feito; raise aqui não desfaz nada e mascara o log)."""
    call_n = {"n": 0}

    def _paste():
        call_n["n"] += 1
        if call_n["n"] == 1:
            return "target"  # readback inicial OK → loop sai
        return "RACED_VALUE"  # sanity mostra mutação pós-paste

    pf.pyperclip.copy.side_effect = lambda _t: None
    pf.pyperclip.paste.side_effect = _paste

    # NÃO deve raise.
    pf.clipboard_safe_paste("target")

    pf.pyautogui.hotkey.assert_called_once_with('ctrl', 'v')
    out = capsys.readouterr().out
    assert "[WARN]" in out
    assert "mutated post-paste" in out


def test_clipboard_safe_paste_logs_first_30_chars_preview(pf, capsys):
    """Log usa preview truncado (primeiros 30 chars) — protege contra spam
    de strings gigantes (HH text tem ~2-5 KB)."""
    long_text = "A" * 200
    _wire_clipboard(pf, long_text, mismatch_returns=["x"] * 5)

    with pytest.raises(RuntimeError):
        pf.clipboard_safe_paste(long_text, n_retries=5)

    out = capsys.readouterr().out
    # 30 A's + "..." aparecem no log; os outros 170 não.
    assert "A" * 30 in out
    assert "A" * 31 not in out  # truncado a 30


def test_clipboard_safe_paste_newline_in_preview_is_sanitized(pf, capsys):
    """Preview escapa \\n para espaço (HH text tem newlines; literais
    quebram o log)."""
    multi_line = "line1\nline2\nline3" + "x" * 50  # >30 chars total
    _wire_clipboard(pf, multi_line, mismatch_returns=["bad"] * 5)

    with pytest.raises(RuntimeError):
        pf.clipboard_safe_paste(multi_line, n_retries=5)

    out = capsys.readouterr().out
    # Não deve aparecer \n literal no preview do WARN final.
    # Procura uma linha que contenha "target=" e checka que essa linha
    # não tem newline interno em formato literal.
    target_line = next(
        (line for line in out.splitlines() if "target=" in line and "failed" in line),
        "",
    )
    assert target_line, f"WARN line not found in output: {out!r}"
    # O preview é dentro de repr() → \n aparece como literal "\\n" no
    # repr OU como espaço pelo replace(). O sanitize substitui por espaço
    # primeiro, depois repr → o preview NÃO deve conter "\\n".
    assert "\\n" not in target_line


def test_clipboard_safe_paste_does_not_invoke_hotkey_until_set_verified(pf):
    """Garantia crítica: Ctrl+V só dispara depois do read-back devolver o
    target. Sem isto, o paste podia partir antes do clipboard estabilizar,
    perpetuando o bug original."""
    _wire_clipboard(pf, "target", mismatch_returns=["x", "y"])

    hotkey_call_times = []

    def _hotkey(*args):
        # Capturar quantos copies já tinham acontecido quando Ctrl+V dispara
        hotkey_call_times.append(pf.pyperclip.copy.call_count)

    pf.pyautogui.hotkey.side_effect = _hotkey

    pf.clipboard_safe_paste("target", n_retries=5)

    assert len(hotkey_call_times) == 1
    # Ctrl+V só após o copy bem-sucedido (attempt 3): copy.call_count == 3.
    assert hotkey_call_times[0] == 3
