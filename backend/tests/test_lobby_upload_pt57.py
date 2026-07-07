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


# ── #LOBBY-FORCE-REVISION — force=true refresca só o vision_json ──────────────

@patch("app.routers.lobbys.process_lobby_message", new_callable=AsyncMock)
@patch("app.routers.lobbys.query",
       return_value=[{"result": "success", "tournament_number": "295219051"}])
def test_upload_force_bypasses_dedup_and_refreshes(mq, mproc):
    # row já existe MAS force=true → não devolve o dedup; re-corre a Vision em
    # modo refresh-only (refresh_vision_only=True).
    mproc.return_value = {"result": "vision_refreshed", "site": "GGPoker",
                          "tournament_name": "Daily Hyper $60", "tournament_number": None,
                          "vision_json": {"open_tab": "Info", "final_table_size": 7},
                          "action": None, "reason_detail": None}
    r = _post(TestClient(_app()), force="true")
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["dedup"] is False and j["forced"] is True
    assert j["result"] == "vision_refreshed"
    mproc.assert_called_once()
    assert mproc.call_args.kwargs["refresh_vision_only"] is True


@patch("app.routers.lobbys.process_lobby_message", new_callable=AsyncMock)
@patch("app.routers.lobbys.query",
       return_value=[{"result": "success", "tournament_number": "999"}])
def test_upload_no_force_still_dedups(mq, mproc):
    # sem force, row existente → dedup como sempre (não re-corre a Vision).
    r = _post(TestClient(_app()))
    assert r.json()["dedup"] is True
    mproc.assert_not_called()


@patch("app.routers.lobbys.process_lobby_message", new_callable=AsyncMock)
@patch("app.routers.lobbys.query", return_value=[])
def test_upload_force_on_fresh_file_is_full_process(mq, mproc):
    # force=true mas o ficheiro é novo (não existia) → processo COMPLETO
    # (refresh_vision_only=False), não o refresh-only.
    mproc.return_value = {"result": "success", "site": "GGPoker",
                          "tournament_name": "X", "tournament_number": "1", "action": "inserted"}
    r = _post(TestClient(_app()), force="true")
    assert r.status_code == 200
    assert mproc.call_args.kwargs["refresh_vision_only"] is False
    assert r.json()["forced"] is False


@patch("app.services.lobby_sync.payouts_service.upsert_payout")
@patch("app.services.lobby_sync._refresh_lobby_vision_json", return_value=1)
@patch("app.services.lobby_sync.lobby_vision.parse_and_validate_lobby_json")
@patch("app.services.lobby_sync.lobby_vision.extract_lobby_payout_json", return_value="raw")
def test_refresh_vision_only_writes_vision_not_payouts(mext, mparse, mrefresh, mpay):
    # refresh-only: reescreve vision_json (+players_left) e NÃO toca payouts.
    from app.services.lobby_sync import process_lobby_message
    mparse.return_value = {"site": "GGPoker", "open_tab": "Info",
                           "final_table_size": 7, "players_left": 7, "prizes": {}}
    res = asyncio.run(process_lobby_message(
        PNG, "image/png", message_id="hash-info", channel_id=None,
        posted_at=datetime(2026, 7, 2, 19, 19, 25), refresh_vision_only=True))
    assert res["result"] == "vision_refreshed"
    assert res["vision_json"]["final_table_size"] == 7
    mrefresh.assert_called_once_with("hash-info", mparse.return_value, 7)
    mpay.assert_not_called()   # payouts NUNCA tocados no refresh-only


def test_refresh_helper_updates_only_vision_columns():
    # _refresh_lobby_vision_json faz UPDATE só de vision_json/players_left.
    from unittest.mock import MagicMock
    from app.services import lobby_sync
    mconn, mcur = MagicMock(), MagicMock()
    mconn.cursor.return_value.__enter__.return_value = mcur
    mcur.rowcount = 1
    with patch.object(lobby_sync, "get_conn", return_value=mconn):
        n = lobby_sync._refresh_lobby_vision_json("h", {"open_tab": "Info"}, 7)
    assert n == 1
    sql = mcur.execute.call_args[0][0]
    assert "UPDATE lobby_processing_log" in sql
    assert "vision_json" in sql and "players_left" in sql
    assert "tournament_payouts" not in sql          # nunca toca payouts
    assert "tournament_number" not in sql            # nem re-resolve
    assert "result " not in sql                      # nem mexe no result
    mconn.commit.assert_called_once()
