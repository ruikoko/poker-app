"""Tests para GET /api/queue/hrc/hand/{hand_id} (pt40 #HRC-PER-HAND-DOWNLOAD)
+ has_payout em eligible_hands."""
import io
import json
import zipfile
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.queue import router as queue_router
from app.auth import require_auth_or_api_key


def _make_app():
    app = FastAPI()
    app.include_router(queue_router)
    app.dependency_overrides[require_auth_or_api_key] = (
        lambda: {"id": None, "email": None, "auth_type": "api_key"}
    )
    return app


def _zip_with_manifest(total_in_zip, skipped=None, files=None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in (files or {}).items():
            zf.writestr(name, content)
        zf.writestr("manifest.json", json.dumps({
            "total_in_zip": total_in_zip,
            "skipped": skipped or [],
        }))
    return buf.getvalue()


_HAND = {"id": 1, "hand_id": "GG-1", "site": "GGPoker", "tournament_number": "T1"}


# ── 1. success → 200 zip com hh.txt + payouts.json ──────────────────────────

def test_hand_download_success():
    app = _make_app(); client = TestClient(app)
    zb = _zip_with_manifest(
        1, files={"GG-1/hh.txt": "PokerStars Hand #...", "GG-1/payouts.json": "{}"})
    with patch("app.routers.queue.query", return_value=[_HAND]), \
         patch("app.routers.queue.lookup_payouts",
               return_value={("GGPoker", "T1"): {"x": 1}}), \
         patch("app.routers.queue.lookup_bounties", return_value={}), \
         patch("app.routers.queue.build_queue_zip", return_value=zb) as bz:
        r = client.get("/api/queue/hrc/hand/GG-1")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    assert 'hrc_GG-1.zip' in r.headers["content-disposition"]
    # build_queue_zip chamado com lista de 1 mão + include_no_payout=False
    args, kwargs = bz.call_args
    assert len(args[0]) == 1 and args[0][0]["hand_id"] == "GG-1"
    assert kwargs["include_no_payout"] is False
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        names = zf.namelist()
    assert "GG-1/hh.txt" in names and "GG-1/payouts.json" in names


# ── 2. hand_id inexistente → 404 ────────────────────────────────────────────

def test_hand_download_404_unknown():
    app = _make_app(); client = TestClient(app)
    with patch("app.routers.queue.query", return_value=[]):
        r = client.get("/api/queue/hrc/hand/GG-NOPE")
    assert r.status_code == 404


# ── 3. sem payout → 409 (não build) ─────────────────────────────────────────

def test_hand_download_409_no_payout():
    app = _make_app(); client = TestClient(app)
    with patch("app.routers.queue.query", return_value=[_HAND]), \
         patch("app.routers.queue.lookup_payouts", return_value={}), \
         patch("app.routers.queue.build_queue_zip") as bz:
        r = client.get("/api/queue/hrc/hand/GG-1")
    assert r.status_code == 409
    bz.assert_not_called()  # short-circuit antes de construir


# ── 4. mão saltada (payout existe mas raw/seats falham) → 422 com reason ─────

def test_hand_download_422_skipped():
    app = _make_app(); client = TestClient(app)
    zb = _zip_with_manifest(0, skipped=[{"hand_id": "GG-1", "reason": "no_raw_hh"}])
    with patch("app.routers.queue.query", return_value=[_HAND]), \
         patch("app.routers.queue.lookup_payouts",
               return_value={("GGPoker", "T1"): {"x": 1}}), \
         patch("app.routers.queue.lookup_bounties", return_value={}), \
         patch("app.routers.queue.build_queue_zip", return_value=zb):
        r = client.get("/api/queue/hrc/hand/GG-1")
    assert r.status_code == 422
    assert "no_raw_hh" in r.json()["detail"]


# ── 5. eligible_hands inclui has_payout por mão ─────────────────────────────

def test_eligible_includes_has_payout_field():
    from app.services import hrc_queue
    rows = [
        {"id": 1, "hand_id": "GG-1", "site": "GGPoker", "tournament_number": "T1",
         "tournament_name": "X", "tournament_format": "PKO", "raw": "r",
         "player_names": {}, "played_at": None, "position": "BTN",
         "hm3_tags": [], "discord_tags": []},
        {"id": 2, "hand_id": "GG-2", "site": "GGPoker", "tournament_number": "T2",
         "tournament_name": "Y", "tournament_format": "PKO", "raw": "r",
         "player_names": {}, "played_at": None, "position": "BTN",
         "hm3_tags": [], "discord_tags": []},
    ]
    with patch("app.services.hrc_queue.select_andar1_rows", return_value=rows), \
         patch("app.services.hrc_queue.lookup_payouts",
               return_value={("GGPoker", "T1"): {"p": 1}}), \
         patch("app.services.hrc_queue.lookup_bounties", return_value={}), \
         patch("app.services.hrc_queue.convert_gg_hh_to_pokerstars_compatible",
               return_value="HH"), \
         patch("app.services.hrc_queue.derive_seats_in_preflop_order",
               return_value=["a", "b", "c"]), \
         patch("app.services.hrc_queue.strategy_table_positions",
               return_value=["UTG", "BTN", "BB"]), \
         patch("app.services.hrc_queue._extract_blinds_from_header",
               return_value=(100, 200)), \
         patch("app.services.hrc_queue.derive_aggressor_real_action",
               return_value={"position": "BTN"}), \
         patch("app.services.hrc_queue.classify_aggressor_source",
               return_value="real"):
        res = hrc_queue.eligible_hands(include_no_payout=True)
    by_id = {h["hand_id"]: h for h in res["hands"]}
    assert by_id["GG-1"]["has_payout"] is True
    assert by_id["GG-2"]["has_payout"] is False
