"""pt57 — 2ª via de lobby por upload (POST /api/lobbys/upload) + params novos
do process_lobby_message (source_prefix, log_on_failure)."""
import asyncio
from datetime import datetime
from unittest.mock import patch, AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

PNG = b"\x89PNG\r\n\x1a\nx"


def _app():
    from app.routers.lobbys import router
    from app.auth import require_auth
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[require_auth] = lambda: {"id": 1, "email": "t@t"}
    return app


def _post(client, **data):
    return client.post(
        "/api/lobbys/upload",
        files={"file": ("Captura de ecra 2026-06-04 153012.png", PNG, "image/png")},
        data=data,
    )


@patch("app.routers.lobbys.process_lobby_message", new_callable=AsyncMock)
@patch("app.routers.lobbys.query", return_value=[])
def test_upload_lobby_success_reuses_pipeline(mq, mproc):
    mproc.return_value = {"result": "success", "site": "GGPoker",
                          "tournament_name": "Daily Hyper $50",
                          "tournament_number": "287210981", "action": "inserted",
                          "reason_detail": None}
    r = _post(TestClient(_app()), captured_at="2026-06-04T15:30:12")
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["is_lobby"] is True
    assert j["tournament_number"] == "287210981"
    kw = mproc.call_args.kwargs
    assert kw["source_prefix"] == "file_lobby_vision"   # fonte distinta do Discord
    assert kw["log_on_failure"] is False                # não-lobby não persiste
    assert kw["channel_id"] is None
    assert kw["posted_at"].tzinfo is None               # Lisboa naive
    assert kw["posted_at"] == datetime(2026, 6, 4, 15, 30, 12)


@patch("app.routers.lobbys.process_lobby_message", new_callable=AsyncMock)
@patch("app.routers.lobbys.query", return_value=[])
def test_upload_non_lobby_ignored(mq, mproc):
    # Vision não encontra torneio → json_invalid → NÃO é lobby.
    mproc.return_value = {"result": "json_invalid", "site": None,
                          "tournament_name": None, "tournament_number": None,
                          "action": None, "reason_detail": "x"}
    r = _post(TestClient(_app()))
    assert r.status_code == 200
    assert r.json()["is_lobby"] is False
    # log_on_failure=False → o process não persistiu nada (garantido no serviço).
    assert mproc.call_args.kwargs["log_on_failure"] is False


@patch("app.routers.lobbys.process_lobby_message", new_callable=AsyncMock)
@patch("app.routers.lobbys.query",
       return_value=[{"result": "success", "tournament_number": "999"}])
def test_upload_dedup_skips_revision(mq, mproc):
    r = _post(TestClient(_app()))
    assert r.status_code == 200
    j = r.json()
    assert j["dedup"] is True and j["tournament_number"] == "999"
    mproc.assert_not_called()   # rede de segurança: não re-corre a Vision


def test_upload_empty_file_400():
    client = TestClient(_app())
    r = client.post("/api/lobbys/upload", files={"file": ("x.png", b"", "image/png")})
    assert r.status_code == 400


# ── params novos do process_lobby_message ────────────────────────────────────

@patch("app.services.lobby_sync._upsert_lobby_log")
@patch("app.services.lobby_sync.lobby_vision.extract_lobby_payout_json", return_value=None)
def test_log_on_failure_false_skips_log(mext, mlog):
    from app.services.lobby_sync import process_lobby_message
    res = asyncio.run(process_lobby_message(
        PNG, "image/png", message_id="h", channel_id=None,
        posted_at=datetime(2026, 6, 4, 15, 0, 0), log_on_failure=False))
    assert res["result"] == "vision_failed"
    mlog.assert_not_called()


@patch("app.services.lobby_sync._upsert_lobby_log")
@patch("app.services.lobby_sync.lobby_vision.extract_lobby_payout_json", return_value=None)
def test_log_on_failure_true_logs(mext, mlog):
    from app.services.lobby_sync import process_lobby_message
    res = asyncio.run(process_lobby_message(
        PNG, "image/png", message_id="h", channel_id=None,
        posted_at=datetime(2026, 6, 4, 15, 0, 0)))   # default True
    assert res["result"] == "vision_failed"
    mlog.assert_called_once()
