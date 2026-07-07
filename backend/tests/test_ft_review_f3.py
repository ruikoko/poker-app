"""F3 — preview + revisão/quarentena + promoção da fronteira FT (gg-health /ft/*).

Confirmar/corrigir FIXA a fronteira mas NÃO promove; a escrita (promote) é sempre um
2º passo explícito (dry_run default, confirm=true escreve)."""
from datetime import datetime
from unittest.mock import patch, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

T0 = datetime(2026, 7, 2, 19, 18, 36)
_D = {"boundary": T0, "source": "manual_ft_tag", "status": "manual", "n": 7,
      "cross_check": {"n": 7, "hh_seats": 7, "match": True}}


def _app():
    from app.routers.gg_health import router
    from app.auth import require_auth_or_api_key
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[require_auth_or_api_key] = lambda: {"id": 1, "email": "t@t"}
    return app


# ── _ft_map_status ───────────────────────────────────────────────────────────
def test_map_status():
    from app.routers.gg_health import _ft_map_status
    assert _ft_map_status("manual", {"match": True}) == "match"
    assert _ft_map_status("lobby", {"match": False}) == "mismatch"
    assert _ft_map_status("coherent", {"match": None}) == "n_unavailable"
    assert _ft_map_status("quarantine_disagreement", None) == "mismatch"
    assert _ft_map_status("incoherent_signal", None) == "incoherent"
    assert _ft_map_status("none", None) == "none"


# ── GET /ft/preview ──────────────────────────────────────────────────────────
@patch("app.routers.gg_health.via_b_diagnostics", return_value=None)
@patch("app.routers.gg_health.propagate_ft",
       return_value={"changed": [{"hand_id": "GG-1", "from": ["icm"], "to": ["icm-ft"]}]})
@patch("app.routers.gg_health.query", return_value=[])
@patch("app.routers.gg_health.compute_ft_boundary", return_value=_D)
def test_preview_single_tn(mc, mq, mp, mv):
    r = TestClient(_app()).get("/api/gg-health/ft/preview?tn=T1")
    assert r.status_code == 200, r.text
    t = r.json()["tournaments"][0]
    assert t["status"] == "match" and t["source"] == "manual_ft_tag"
    assert t["boundary"] == T0.isoformat() and t["n_lobby"] == 7 and t["seats_first_hand"] == 7
    assert t["n_changes"] == 1 and t["decision"] == "pending"
    # preview é SÓ LEITURA: só corre propagate em dry_run
    assert mp.call_args.kwargs.get("dry_run") is True


# ── POST /ft/confirm — fixa, NÃO promove ─────────────────────────────────────
@patch("app.routers.gg_health.via_b_diagnostics", return_value=None)
@patch("app.routers.gg_health.propagate_ft", return_value={"changed": []})
@patch("app.routers.gg_health.query", return_value=[])
@patch("app.routers.gg_health.get_conn")
@patch("app.routers.gg_health.compute_ft_boundary", return_value=_D)
def test_confirm_persists_confirmed_no_write(mc, mconn, mq, mp, mv):
    mcur = MagicMock()
    mconn.return_value.cursor.return_value.__enter__.return_value = mcur
    r = TestClient(_app()).post("/api/gg-health/ft/confirm", json={"tournament_number": "T1"})
    assert r.status_code == 200, r.text
    sql, params = mcur.execute.call_args[0][0], mcur.execute.call_args[0][1]
    assert "INSERT INTO ft_boundary_review" in sql and "confirmed" in params
    # nunca promove (escrita real = dry_run=False) — só o dry-run do preview corre
    assert all(c.kwargs.get("dry_run") is True for c in mp.call_args_list)


# ── POST /ft/correct — override, decision='corrected' ────────────────────────
@patch("app.routers.gg_health.via_b_diagnostics", return_value=None)
@patch("app.routers.gg_health.propagate_ft", return_value={"changed": []})
@patch("app.routers.gg_health.query", return_value=[])
@patch("app.routers.gg_health.get_conn")
@patch("app.routers.gg_health.compute_ft_boundary", return_value=_D)
def test_correct_persists_override(mc, mconn, mq, mp, mv):
    mcur = MagicMock()
    mconn.return_value.cursor.return_value.__enter__.return_value = mcur
    r = TestClient(_app()).post("/api/gg-health/ft/correct", json={
        "tournament_number": "T1", "override_boundary": "2026-07-02T19:18:00", "override_n": 8})
    assert r.status_code == 200, r.text
    params = mcur.execute.call_args[0][1]
    assert "corrected" in params and 8 in params


# ── POST /ft/promote — 2º passo, exige decisão prévia ────────────────────────
@patch("app.routers.gg_health._ft_get_review", return_value=None)
def test_promote_without_decision_422(mrev):
    r = TestClient(_app()).post("/api/gg-health/ft/promote", json={"tournament_number": "T1"})
    assert r.status_code == 422


@patch("app.routers.gg_health.propagate_ft",
       return_value={"changed": [{"hand_id": "GG-1"}], "n_changed": 1})
@patch("app.routers.gg_health._ft_get_review",
       return_value={"decision": "confirmed", "override_boundary": None, "boundary": T0})
def test_promote_dryrun_then_write(mrev, mp):
    c = TestClient(_app())
    r = c.post("/api/gg-health/ft/promote", json={"tournament_number": "T1"})
    assert r.status_code == 200 and r.json()["dry_run"] is True
    assert mp.call_args.kwargs["dry_run"] is True
    with patch("app.routers.gg_health._ft_mark_promoted") as mmark:
        r2 = c.post("/api/gg-health/ft/promote",
                    json={"tournament_number": "T1", "confirm": True})
    assert r2.json()["dry_run"] is False and mmark.called
    assert mp.call_args.kwargs["dry_run"] is False


@patch("app.routers.gg_health.propagate_ft", return_value={"changed": [], "n_changed": 0})
@patch("app.routers.gg_health._ft_mark_promoted")
@patch("app.routers.gg_health._ft_get_review",
       return_value={"decision": "corrected", "override_boundary": T0, "boundary": None})
def test_promote_corrected_uses_override_boundary(mrev, mmark, mp):
    c = TestClient(_app())
    c.post("/api/gg-health/ft/promote", json={"tournament_number": "T1", "confirm": True})
    # a fronteira CORRIGIDA (override) é passada ao propagate
    assert mp.call_args.kwargs["boundary_override"] == T0
