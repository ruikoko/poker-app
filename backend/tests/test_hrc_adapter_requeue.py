"""pt83 (#HRC-SENT-LIST-AND-REQUEUE) — dedup epoch-aware do adapter.

D10 deixa de ser `if hand_id in state: skip` e passa a comparar o `requeue_epoch`
servido no manifest com o guardado no state → o re-queue do backend (epoch++)
faz o adapter RE-puxar uma mão já em state (ex.: falhada).
"""
from __future__ import annotations

import io
import json
import sys
import zipfile
from pathlib import Path
from unittest.mock import MagicMock

_HERE = Path(__file__).resolve().parent
_TOOLS = _HERE.parent.parent / "tools" / "hrc_adapter"
sys.path.insert(0, str(_TOOLS))

import hrc_adapter  # noqa: E402


def _zip_bytes(hand_id="GG-1", epoch=0, with_epoch=True):
    buf = io.BytesIO()
    entry = {"hand_id": hand_id}
    if with_epoch:
        entry["requeue_epoch"] = epoch
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("manifest.json", json.dumps({"hands_included": [entry]}))
        zf.writestr(f"{hand_id}/hh.txt", "PokerStars Hand #1")
        zf.writestr(f"{hand_id}/meta.json", json.dumps({"tree_filename": "x.zip"}))
    return buf.getvalue()


def _session(zip_bytes):
    s = MagicMock()
    s.get.return_value = MagicMock(status_code=200, content=zip_bytes)
    return s


def _patch(monkeypatch):
    monkeypatch.setattr(hrc_adapter, "_persist_manifest", lambda *_: None)


def test_pull_new_hand_stores_epoch(tmp_path, monkeypatch):
    _patch(monkeypatch)
    state = {}
    n = hrc_adapter.pull_queue(_session(_zip_bytes(epoch=2)), "http://x", tmp_path, state)
    assert n == 1
    assert state["GG-1"]["requeue_epoch"] == 2
    assert (tmp_path / "GG-1" / "hh.txt").is_file()


def test_pull_skips_same_epoch(tmp_path, monkeypatch):
    _patch(monkeypatch)
    state = {"GG-1": {"status": "failed", "requeue_epoch": 0}}
    n = hrc_adapter.pull_queue(_session(_zip_bytes(epoch=0)), "http://x", tmp_path, state)
    assert n == 0                                  # served 0 <= state 0 → skip
    assert state["GG-1"]["status"] == "failed"     # state intacto


def test_pull_requeue_higher_epoch_repulls(tmp_path, monkeypatch):
    _patch(monkeypatch)
    # mão falhada no state (epoch 0); backend re-queue → manifest epoch 1 → re-puxa
    state = {"GG-1": {"status": "failed", "requeue_epoch": 0}}
    n = hrc_adapter.pull_queue(_session(_zip_bytes(epoch=1)), "http://x", tmp_path, state)
    assert n == 1
    assert state["GG-1"]["status"] == hrc_adapter.STATUS_PULLED
    assert state["GG-1"]["requeue_epoch"] == 1
    assert (tmp_path / "GG-1" / "hh.txt").is_file()


def test_pull_repull_clears_stale_folder(tmp_path, monkeypatch):
    _patch(monkeypatch)
    # pasta stale com marker .failed → re-pull limpa-a antes de re-escrever
    stale = tmp_path / "GG-1"
    stale.mkdir()
    (stale / ".failed").write_text("setup failed")
    (stale / "lixo_antigo.txt").write_text("velho")
    state = {"GG-1": {"status": "failed", "requeue_epoch": 0}}
    hrc_adapter.pull_queue(_session(_zip_bytes(epoch=1)), "http://x", tmp_path, state)
    assert not (stale / ".failed").exists()        # marker stale removido
    assert not (stale / "lixo_antigo.txt").exists()
    assert (stale / "hh.txt").is_file()            # pack fresco


def test_pull_legacy_manifest_no_epoch_backcompat(tmp_path, monkeypatch):
    _patch(monkeypatch)
    # manifest antigo sem requeue_epoch → served 0; state sem epoch → 0 ≤ 0 → skip
    state = {"GG-1": {"status": "done"}}
    n = hrc_adapter.pull_queue(_session(_zip_bytes(with_epoch=False)), "http://x", tmp_path, state)
    assert n == 0                                  # comportamento antigo preservado
