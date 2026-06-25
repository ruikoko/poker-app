"""Tests para o multi-select "Enviar ao HRC" (pt68 backend / pt69 frontend):
POST /api/queue/hrc/release (release forçado) + POST /api/queue/hrc/states
(estado por mão para os badges da Estudo).

Mocka `query`/`execute`/`build_queue_zip` em `app.routers.queue` — sem BD real.
"""
import io
import json
import zipfile
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import require_auth_or_api_key
from app.routers.queue import router as queue_router
from app.services.hrc_queue import ALLOWED_SITES


def _make_app():
    app = FastAPI()
    app.include_router(queue_router)
    app.dependency_overrides[require_auth_or_api_key] = (
        lambda: {"id": None, "email": None, "auth_type": "api_key"}
    )
    return app


_OK_SITE = "GGPoker"
assert _OK_SITE in ALLOWED_SITES
_BAD_SITE = "NopeSite"
assert _BAD_SITE not in ALLOWED_SITES


def _zip_with_manifest(total_in_zip, skipped=None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("manifest.json", json.dumps({
            "total_in_zip": total_in_zip,
            "skipped": skipped or [],
        }))
    return buf.getvalue()


# ── /states — mapeamento de estado + exportável/motivo ──────────────────────

def test_states_maps_all_four_states():
    app = _make_app(); client = TestClient(app)
    rows = [
        # done → concluída
        {"hand_id": "GG-1", "site": _OK_SITE, "no_raw": False,
         "released": True, "job_status": "done"},
        # failed → falhou
        {"hand_id": "GG-2", "site": _OK_SITE, "no_raw": False,
         "released": True, "job_status": "failed"},
        # released sem job → na fila
        {"hand_id": "GG-3", "site": _OK_SITE, "no_raw": False,
         "released": True, "job_status": None},
        # nada
        {"hand_id": "GG-4", "site": _OK_SITE, "no_raw": False,
         "released": False, "job_status": None},
    ]
    with patch("app.routers.queue.query", return_value=rows):
        r = client.post("/api/queue/hrc/states",
                        json={"hand_ids": ["GG-1", "GG-2", "GG-3", "GG-4"]})
    assert r.status_code == 200
    st = r.json()["states"]
    assert st["GG-1"]["state"] == "concluída"
    assert st["GG-2"]["state"] == "falhou"
    assert st["GG-3"]["state"] == "na fila"
    assert st["GG-4"]["state"] == "nada"


def test_states_exportable_flags_and_reasons():
    app = _make_app(); client = TestClient(app)
    rows = [
        {"hand_id": "GG-OK", "site": _OK_SITE, "no_raw": False,
         "released": False, "job_status": None},
        {"hand_id": "GG-NORAW", "site": _OK_SITE, "no_raw": True,
         "released": False, "job_status": None},
        {"hand_id": "X-BADSITE", "site": _BAD_SITE, "no_raw": False,
         "released": False, "job_status": None},
    ]
    with patch("app.routers.queue.query", return_value=rows):
        r = client.post("/api/queue/hrc/states",
                        json={"hand_ids": ["GG-OK", "GG-NORAW", "X-BADSITE"]})
    st = r.json()["states"]
    assert st["GG-OK"]["exportable"] is True and st["GG-OK"]["reason"] is None
    assert st["GG-NORAW"]["exportable"] is False and st["GG-NORAW"]["reason"] == "sem HH"
    assert st["X-BADSITE"]["exportable"] is False
    assert st["X-BADSITE"]["reason"] == "site não suportado"


def test_states_empty_list_short_circuits():
    app = _make_app(); client = TestClient(app)
    # Não deve sequer tocar na BD.
    with patch("app.routers.queue.query") as q:
        r = client.post("/api/queue/hrc/states", json={"hand_ids": []})
    assert r.status_code == 200
    assert r.json() == {"states": {}}
    q.assert_not_called()


# ── /release — release forçado + guardas com motivo ─────────────────────────

def test_release_requires_non_empty_list():
    app = _make_app(); client = TestClient(app)
    r = client.post("/api/queue/hrc/release", json={"hand_ids": []})
    assert r.status_code == 400


def test_release_rejects_over_500():
    app = _make_app(); client = TestClient(app)
    r = client.post("/api/queue/hrc/release",
                    json={"hand_ids": [f"GG-{i}" for i in range(501)]})
    assert r.status_code == 400


def test_release_happy_path_inserts_and_returns_released():
    app = _make_app(); client = TestClient(app)
    hand_row = {"id": 7, "hand_id": "GG-1", "site": _OK_SITE, "raw": "PokerStars Hand...",
                "tournament_number": "T1", "tournament_name": "X",
                "tournament_format": "PKO", "player_names": {}, "played_at": None,
                "position": "BTN", "study_state": "new", "hm3_tags": [],
                "discord_tags": [], "context_table_ss_id": None}
    zb = _zip_with_manifest(1)
    with patch("app.routers.queue.query", return_value=[hand_row]), \
         patch("app.routers.queue.lookup_payouts", return_value={(_OK_SITE, "T1"): {"p": 1}}), \
         patch("app.routers.queue.lookup_bounties", return_value={}), \
         patch("app.routers.queue.build_queue_zip", return_value=zb), \
         patch("app.routers.queue.execute") as ex:
        r = client.post("/api/queue/hrc/release", json={"hand_ids": ["GG-1"]})
    assert r.status_code == 200
    body = r.json()
    assert body["released"] == ["GG-1"]
    assert body["skipped"] == []
    ex.assert_called_once()   # INSERT em hrc_queue_release


def test_release_rerelease_bumps_epoch():
    """#HRC-ADAPTER-STATE-DESYNC-SILENT: o re-envio tem de incrementar o
    requeue_epoch (ON CONFLICT DO UPDATE), senão o adapter salta a mão em silêncio.
    Release fresco = epoch 0 (INSERT); re-envio = +1 (servido > o do state →
    adapter re-puxa). O endpoint emite sempre o mesmo UPSERT: aqui validamos que
    o SQL faz o bump no conflito."""
    app = _make_app(); client = TestClient(app)
    hand_row = {"id": 7, "hand_id": "GG-1", "site": _OK_SITE, "raw": "PokerStars Hand...",
                "tournament_number": "T1", "tournament_name": "X",
                "tournament_format": "PKO", "player_names": {}, "played_at": None,
                "position": "BTN", "study_state": "new", "hm3_tags": [],
                "discord_tags": [], "context_table_ss_id": None}
    zb = _zip_with_manifest(1)
    with patch("app.routers.queue.query", return_value=[hand_row]), \
         patch("app.routers.queue.lookup_payouts", return_value={(_OK_SITE, "T1"): {"p": 1}}), \
         patch("app.routers.queue.lookup_bounties", return_value={}), \
         patch("app.routers.queue.build_queue_zip", return_value=zb), \
         patch("app.routers.queue.execute") as ex:
        r = client.post("/api/queue/hrc/release", json={"hand_ids": ["GG-1"]})
    assert r.status_code == 200
    assert r.json()["released"] == ["GG-1"]
    sql = ex.call_args.args[0]
    assert "INSERT INTO hrc_queue_release" in sql
    assert "ON CONFLICT (hand_db_id) DO UPDATE" in sql
    assert "requeue_epoch = hrc_queue_release.requeue_epoch + 1" in sql
    # NÃO usa o antigo DO NOTHING (que era a causa do bug).
    assert "DO NOTHING" not in sql
    # o id da mão e o batch_id vão como params (hand_db_id=7).
    assert ex.call_args.args[1][0] == 7


def test_release_skips_unknown_hand():
    app = _make_app(); client = TestClient(app)
    with patch("app.routers.queue.query", return_value=[]), \
         patch("app.routers.queue.execute") as ex:
        r = client.post("/api/queue/hrc/release", json={"hand_ids": ["GG-NOPE"]})
    assert r.status_code == 200
    body = r.json()
    assert body["released"] == []
    assert body["skipped"][0]["hand_id"] == "GG-NOPE"
    assert "não encontrada" in body["skipped"][0]["reason"]
    ex.assert_not_called()


def test_release_skips_unsupported_site_without_deep_guard():
    app = _make_app(); client = TestClient(app)
    hand_row = {"id": 9, "hand_id": "X-1", "site": _BAD_SITE, "raw": "x"}
    with patch("app.routers.queue.query", return_value=[hand_row]), \
         patch("app.routers.queue.build_queue_zip") as bz, \
         patch("app.routers.queue.execute") as ex:
        r = client.post("/api/queue/hrc/release", json={"hand_ids": ["X-1"]})
    body = r.json()
    assert body["released"] == []
    assert "site" in body["skipped"][0]["reason"]
    bz.assert_not_called()    # guarda leve curto-circuita antes do guard profundo
    ex.assert_not_called()


def test_release_skips_when_deep_guard_yields_empty_zip():
    app = _make_app(); client = TestClient(app)
    hand_row = {"id": 11, "hand_id": "GG-2", "site": _OK_SITE, "raw": "r",
                "tournament_number": "T2"}
    zb = _zip_with_manifest(0, skipped=[{"hand_id": "GG-2", "reason": "pko_without_ts_bounty"}])
    with patch("app.routers.queue.query", return_value=[hand_row]), \
         patch("app.routers.queue.lookup_payouts", return_value={}), \
         patch("app.routers.queue.lookup_bounties", return_value={}), \
         patch("app.routers.queue.build_queue_zip", return_value=zb), \
         patch("app.routers.queue.execute") as ex:
        r = client.post("/api/queue/hrc/release", json={"hand_ids": ["GG-2"]})
    body = r.json()
    assert body["released"] == []
    assert body["skipped"][0]["reason"] == "pko_without_ts_bounty"
    ex.assert_not_called()
