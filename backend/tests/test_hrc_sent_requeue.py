"""pt83 (#HRC-SENT-LIST-AND-REQUEUE) — GET /hrc/sent + POST /hrc/requeue.

Estado por mão derivado do JOIN hands ⨝ hrc_queue_release ⨝ hrc_jobs:
resolvida (done) / cancelada (failed) / por_resolver (released sem job). Re-queue
apaga o job failed + bump do requeue_epoch (servido no manifest → dedup
epoch-aware do adapter). DB mockada (sem Postgres local).
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.queue import router, _derive_sent_state
from app.auth import require_auth_or_api_key


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[require_auth_or_api_key] = lambda: {"id": 1}
    return TestClient(app)


# ── função pura ──
def test_derive_sent_state():
    assert _derive_sent_state("done") == "resolvida"
    assert _derive_sent_state("failed") == "cancelada"
    assert _derive_sent_state(None) == "por_resolver"      # released, sem job
    assert _derive_sent_state("submitted") == "por_resolver"


# ── GET /hrc/sent ──
@patch("app.routers.queue.query")
def test_sent_lists_three_states(mq):
    # Contrato do row de /hrc/sent (pós-enriquecimento): inclui id + colunas ricas
    # (tournament_number/raw ausentes → enriquecimento fica offline, campos ricos None).
    base = dict(site="GGPoker", tournament_name="Daily", hero_cards=["Ah", "Ks"],
                played_at=datetime(2026, 6, 16, 17, 10), released_at=datetime(2026, 6, 18, 9, 0),
                batch_id="b1", requeue_epoch=0, completed_at=None,
                tournament_format=None, position=None)
    mq.return_value = [
        {**base, "id": 1, "hand_id": "GG-1", "job_status": "done", "error": None, "result_zip_size": 123},
        {**base, "id": 2, "hand_id": "GG-2", "job_status": "failed", "error": "setup failed", "result_zip_size": None},
        {**base, "id": 3, "hand_id": "GG-3", "job_status": None, "error": None, "result_zip_size": None},
    ]
    r = _client().get("/api/queue/hrc/sent")
    assert r.status_code == 200
    d = r.json()
    assert d["total"] == 3
    by = {x["hand_id"]: x for x in d["sent"]}
    assert by["GG-1"]["state"] == "resolvida" and by["GG-1"]["result_zip_size"] == 123
    assert by["GG-2"]["state"] == "cancelada" and by["GG-2"]["error"] == "setup failed"
    assert by["GG-3"]["state"] == "por_resolver"
    # error só na cancelada; result_zip só na resolvida
    assert by["GG-1"]["error"] is None
    assert by["GG-3"]["result_zip_size"] is None
    assert by["GG-2"]["result_zip_size"] is None
    # campos ricos presentes no contrato (None quando sem dado)
    for k in ("position_hero", "first_vpip_position", "tournament_format",
              "tournament_speed", "total_players", "players_left", "stack_hero_bb"):
        assert k in by["GG-1"]


# ── POST /hrc/requeue ──
@patch("app.routers.queue.execute")
@patch("app.routers.queue.query")
def test_requeue_failed_hand(mq, mex):
    mq.return_value = [{"id": 5, "released": True, "job_status": "failed"}]
    r = _client().post("/api/queue/hrc/requeue", json={"hand_ids": ["GG-2"]})
    assert r.status_code == 200
    assert r.json()["requeued"] == ["GG-2"]
    assert r.json()["skipped"] == []
    # DELETE job failed + UPDATE requeue_epoch → 2 execute()
    assert mex.call_count == 2
    sqls = " ".join(c.args[0] for c in mex.call_args_list)
    assert "DELETE FROM hrc_jobs" in sqls and "requeue_epoch = requeue_epoch + 1" in sqls


@patch("app.routers.queue.execute")
@patch("app.routers.queue.query")
def test_requeue_skips_non_failed(mq, mex):
    mq.return_value = [{"id": 5, "released": True, "job_status": "done"}]
    r = _client().post("/api/queue/hrc/requeue", json={"hand_ids": ["GG-1"]})
    assert r.json()["requeued"] == []
    assert "não é falhada" in r.json()["skipped"][0]["reason"]
    mex.assert_not_called()             # não toca em nada se não é failed


@patch("app.routers.queue.execute")
@patch("app.routers.queue.query")
def test_requeue_skips_not_released(mq, mex):
    mq.return_value = [{"id": 5, "released": False, "job_status": None}]
    r = _client().post("/api/queue/hrc/requeue", json={"hand_ids": ["GG-9"]})
    assert r.json()["requeued"] == []
    assert "não está na fila" in r.json()["skipped"][0]["reason"]
    mex.assert_not_called()


@patch("app.routers.queue.execute")
@patch("app.routers.queue.query")
def test_requeue_skips_unknown_hand(mq, mex):
    mq.return_value = []
    r = _client().post("/api/queue/hrc/requeue", json={"hand_ids": ["GG-X"]})
    assert "não encontrada" in r.json()["skipped"][0]["reason"]
    mex.assert_not_called()


def test_requeue_empty_body_400():
    r = _client().post("/api/queue/hrc/requeue", json={"hand_ids": []})
    assert r.status_code == 400


# ── POST /hrc/set-aside (mão-veneno: des-libertar + nota; NÃO re-enfileirável) ──
@patch("app.routers.queue.execute")
@patch("app.routers.queue.query")
def test_set_aside_unreleases_and_notes(mq, mex):
    mq.return_value = [{"id": 681}]
    r = _client().post("/api/queue/hrc/set-aside",
                       json={"hand_ids": ["GG-6083125360"], "note": "pendura o HRC"})
    assert r.status_code == 200
    assert r.json()["set_aside"] == ["GG-6083125360"]
    # DELETE do release + UPSERT do hrc_job failed = 2 execute()
    assert mex.call_count == 2
    sqls = " ".join(c.args[0] for c in mex.call_args_list)
    assert "DELETE FROM hrc_queue_release" in sqls
    assert "INSERT INTO hrc_jobs" in sqls and "'failed'" in sqls
    # a nota vai para o error do job
    insert_args = [c.args[1] for c in mex.call_args_list if "INSERT INTO hrc_jobs" in c.args[0]][0]
    assert "pendura o HRC" in insert_args[1]


@patch("app.routers.queue.execute")
@patch("app.routers.queue.query")
def test_set_aside_skips_unknown(mq, mex):
    mq.return_value = []
    r = _client().post("/api/queue/hrc/set-aside", json={"hand_ids": ["GG-X"]})
    assert r.json()["set_aside"] == []
    assert "não encontrada" in r.json()["skipped"][0]["reason"]
    mex.assert_not_called()


def test_set_aside_empty_body_400():
    r = _client().post("/api/queue/hrc/set-aside", json={"hand_ids": []})
    assert r.status_code == 400
