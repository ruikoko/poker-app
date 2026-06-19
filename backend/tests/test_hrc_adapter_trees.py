"""pt82 (#HRC-TREES-PERSIST-BEELINK) — `_copy_to_trees` do adapter.

COPIA (não move) o zip de output para C:\\hrc\\trees\\<nome legível>, ANTES do
move-para-replied. Best-effort (não bloqueia a fila). Sem limpeza automática.
"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_TOOLS = _HERE.parent.parent / "tools" / "hrc_adapter"
sys.path.insert(0, str(_TOOLS))

import hrc_adapter  # noqa: E402


def _make_zip(tmp_path: Path, name: str = "GG-1.zip", data: bytes = b"PK\x03\x04zip") -> Path:
    p = tmp_path / name
    p.write_bytes(data)
    return p


def test_copy_uses_readable_name(tmp_path, monkeypatch):
    trees = tmp_path / "trees"
    monkeypatch.setattr(hrc_adapter, "TREES_DIR", trees)
    src = _make_zip(tmp_path, "GG-6083184245.zip", b"TREEDATA")

    hrc_adapter._copy_to_trees(src, "SpeedRacer_AhKs_2026-06-16_17h10_GG-6083184245.zip")

    dest = trees / "SpeedRacer_AhKs_2026-06-16_17h10_GG-6083184245.zip"
    assert dest.is_file()
    assert dest.read_bytes() == b"TREEDATA"
    assert src.is_file()  # COPIA — o original mantém-se (para o move-para-replied)


def test_copy_fallback_hand_id_when_no_name(tmp_path, monkeypatch):
    trees = tmp_path / "trees"
    monkeypatch.setattr(hrc_adapter, "TREES_DIR", trees)
    src = _make_zip(tmp_path, "GG-999.zip")

    hrc_adapter._copy_to_trees(src, None)        # sem nome legível
    assert (trees / "GG-999.zip").is_file()      # fallback <hand_id>.zip


def test_copy_empty_name_falls_back(tmp_path, monkeypatch):
    trees = tmp_path / "trees"
    monkeypatch.setattr(hrc_adapter, "TREES_DIR", trees)
    src = _make_zip(tmp_path, "WN-7.zip")
    hrc_adapter._copy_to_trees(src, "   ")       # whitespace → fallback
    assert (trees / "WN-7.zip").is_file()


def test_copy_overwrites_idempotent(tmp_path, monkeypatch):
    trees = tmp_path / "trees"
    monkeypatch.setattr(hrc_adapter, "TREES_DIR", trees)
    src = _make_zip(tmp_path, "GG-1.zip", b"V1")
    hrc_adapter._copy_to_trees(src, "x.zip")
    src.write_bytes(b"V2")
    hrc_adapter._copy_to_trees(src, "x.zip")     # re-export → sobrescreve
    assert (trees / "x.zip").read_bytes() == b"V2"


def test_copy_best_effort_does_not_raise(tmp_path, monkeypatch):
    """Source inexistente → OSError apanhado, sem raise (a fila segue)."""
    monkeypatch.setattr(hrc_adapter, "TREES_DIR", tmp_path / "trees")
    hrc_adapter._copy_to_trees(tmp_path / "nao_existe.zip", "y.zip")  # não levanta
