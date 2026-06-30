"""pt92 ② (#HRC-QUEUE-SLOW-OPEN) — cache do verdict de verificação.

Cobre `_compute_verify_entry` (a entry cacheada que o /hrc/verify devolve):
merge do output de `verify_hand` + origem (`_verify_origin`).
"""
from unittest.mock import patch
import app.routers.queue as q


def test_compute_verify_entry_merges_fields_and_ss_origin():
    hand = {"hand_id": "GG-1", "site": "GGPoker", "context_table_ss_id": 7}
    fake = {"hand_id": "GG-1", "verdict": "ok", "scale": 1.0,
            "checks": [{"k": "x", "ok": True}]}
    with patch("app.services.hrc_verify.verify_hand", return_value=fake):
        e = q._compute_verify_entry(hand, b"zip-bytes")
    assert e["hand_id"] == "GG-1"
    assert e["site"] == "GGPoker"
    assert e["verdict"] == "ok"
    assert e["scale"] == 1.0
    assert e["checks"] == [{"k": "x", "ok": True}]
    # origem por SS (tem context_table_ss_id)
    assert e["origin_kind"] == "ss"
    assert e["capture_url"] == "/api/table-ss/image/7"


def test_compute_verify_entry_hh_text_origin_when_no_ss():
    hand = {"hand_id": "WN-1", "site": "Winamax", "context_table_ss_id": None}
    fake = {"hand_id": "WN-1", "verdict": "warn", "scale": 0.5, "checks": []}
    with patch("app.services.hrc_verify.verify_hand", return_value=fake):
        e = q._compute_verify_entry(hand, b"zip-bytes")
    assert e["origin_kind"] == "hh_text"
    assert e["capture_url"] is None
    assert e["verdict"] == "warn"


def test_cache_verify_for_hand_returns_none_when_no_done_row(monkeypatch):
    # query devolve [] (mão sem job done/zip) → None, sem levantar.
    monkeypatch.setattr(q, "query", lambda *a, **k: [])
    assert q.cache_verify_for_hand(123) is None
