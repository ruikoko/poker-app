"""pt25 — tests para tools/hrc_adapter/payouts_helpers.py

`rewrite_script_path_in_meta` (pt42d — renomeado de
`rewrite_script_path_in_payouts`) reescreve a key `script_path` num
meta.json on-disk; o adapter chama-o pós-unzip quando o backend
incluiu `script.js` no zip (prune-in-gap-downstream)."""
import json
import os
import sys
import tempfile
from pathlib import Path

# Import direto via path adicionado a sys.path (tools/hrc_adapter/ pure stdlib
# no payouts_helpers — não puxa requests/urllib3 do hrc_adapter.py top).
_HERE = Path(__file__).resolve().parent
_TOOLS = _HERE.parent.parent / "tools" / "hrc_adapter"
sys.path.insert(0, str(_TOOLS))

from payouts_helpers import rewrite_script_path_in_meta  # noqa: E402


def _write_temp_json(payload: dict) -> Path:
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    p = Path(path)
    p.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return p


def test_rewrite_script_path_basic():
    """Reescrita simples: script_path muda; outras keys preservadas.
    pt42d — target = meta.json (era payouts.json pré-pt42d)."""
    p = _write_temp_json({
        "script_path": None,
        "stage": "MTT",
        "players_left": 200,
        "equity_model": "multi_table_icm",
        "max_players": 6,
    })
    ok = rewrite_script_path_in_meta(p, r"C:\hrc\queue\GG-X\script.js")
    assert ok is True
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["script_path"] == r"C:\hrc\queue\GG-X\script.js"
    # Outras keys intactas
    assert data["stage"] == "MTT"
    assert data["players_left"] == 200
    assert data["equity_model"] == "multi_table_icm"
    assert data["max_players"] == 6


def test_rewrite_script_path_overwrites_existing():
    """Se já há script_path (e.g. backend escreveu 'script.js' relative),
    sobrescreve com path absoluto."""
    p = _write_temp_json({"script_path": "script.js"})
    ok = rewrite_script_path_in_meta(p, r"C:\abs\full\path.js")
    assert ok is True
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["script_path"] == r"C:\abs\full\path.js"


def test_rewrite_script_path_missing_file_returns_false():
    """Ficheiro inexistente → False, sem crash."""
    missing = Path(tempfile.gettempdir()) / "definitely_does_not_exist_pt25.json"
    if missing.exists():
        missing.unlink()
    ok = rewrite_script_path_in_meta(missing, r"C:\abs.js")
    assert ok is False


def test_rewrite_script_path_invalid_json_returns_false():
    """Conteúdo não-JSON → False, sem crash."""
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    Path(path).write_text("not valid json {{{", encoding="utf-8")
    ok = rewrite_script_path_in_meta(path, r"C:\abs.js")
    assert ok is False


def test_rewrite_script_path_non_dict_returns_false():
    """Top-level não-dict (lista, string) → False."""
    p = _write_temp_json([])  # JSON válido mas não é dict
    ok = rewrite_script_path_in_meta(p, r"C:\abs.js")
    assert ok is False
