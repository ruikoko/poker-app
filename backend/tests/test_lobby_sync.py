"""Tests para services/lobby_sync — process_lobby_message + run_sync.

Pattern de mocks alinhado com tests/test_discord_lobby_handler.py:
asyncio.run() sem pytest-asyncio. Patches via unittest.mock.
"""
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.services import lobby_sync


# ── Helpers ─────────────────────────────────────────────────────────────────

def _async_iter(items):
    """Helper: faz uma sequência iterável funcionar com `async for`."""
    async def gen(*args, **kwargs):
        for x in items:
            yield x
    return gen


def _mock_msg(msg_id="100", attachments=1, content="", minutes_ago=10, has_image=True):
    m = MagicMock()
    m.id = int(msg_id) if str(msg_id).isdigit() else msg_id
    m.author = MagicMock()
    m.author.id = 12345  # not bot id (999)
    atts = []
    for i in range(attachments):
        att = MagicMock()
        att.content_type = "image/png" if has_image else "text/plain"
        att.filename = "ss.png" if has_image else "file.txt"
        att.read = AsyncMock(return_value=b"\x89PNG\r\n\x1a\n" + b"x" * 100)
        atts.append(att)
    m.attachments = atts
    m.content = content
    m.created_at = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return m


def _mock_bot_with_channel(history_msgs, channel_name="lobbys"):
    bot = MagicMock()
    bot.is_ready = MagicMock(return_value=True)

    channel = MagicMock()
    channel.id = "ch_lobby"
    channel.name = channel_name
    channel.guild = MagicMock()
    channel.guild.me = MagicMock()
    channel.guild.me.id = 999
    channel.history = _async_iter(history_msgs)

    guild = MagicMock()
    guild.text_channels = [channel]
    bot.guilds = [guild]
    return bot, channel


# ── 1-3. process_lobby_message ──────────────────────────────────────────────

@patch("app.services.lobby_sync._upsert_lobby_log")
@patch("app.services.payouts_service.upsert_payout",
       return_value={"action": "inserted"})
@patch("app.services.lobby_vision.build_hrc_payouts_blob",
       return_value={"name": "/", "folders": [],
                     "structures": [{"name": "X", "prizes": {"1": 1.0},
                                     "bountyType": "PKO",
                                     "progressiveFactor": 0.5}]})
@patch("app.services.tournament_resolver.resolve_tournament_number",
       return_value=("12345", []))
@patch("app.services.lobby_vision.parse_and_validate_lobby_json",
       return_value={"site": "GGPoker", "tournament_name": "X",
                     "prizes": {"1": 1.0}})
@patch("app.services.lobby_vision.extract_lobby_payout_json",
       return_value='{"site":"GGPoker","tournament_name":"X","prizes":{"1":1.0}}')
def test_process_success_writes_log_and_returns_success(
    _ex, _pa, _re, _bl, _up, mock_log
):
    r = asyncio.run(lobby_sync.process_lobby_message(
        b"\x89PNG", "image/png", "msg1", "ch1",
        datetime.now(timezone.utc), "",
    ))
    assert r["result"] == "success"
    assert r["tournament_number"] == "12345"
    assert r["bounty_type"] == "PKO"
    assert r["progressive_factor"] == 0.5
    assert r["action"] == "inserted"
    assert r["prizes_count"] == 1
    mock_log.assert_called_once()
    assert mock_log.call_args.kwargs["result"] == "success"


@patch("app.services.lobby_sync._upsert_lobby_log")
@patch("app.services.tournament_resolver.resolve_tournament_number",
       return_value=(None, []))
@patch("app.services.lobby_vision.parse_and_validate_lobby_json",
       return_value={"site": "Winamax", "tournament_name": "EXPLORER",
                     "prizes": {"1": 1}})
@patch("app.services.lobby_vision.extract_lobby_payout_json",
       return_value='{"...":""}')
def test_process_tm_not_found_logs_failure(_ex, _pa, _re, mock_log):
    r = asyncio.run(lobby_sync.process_lobby_message(
        b"x", "image/png", "m", None,
        datetime.now(timezone.utc), "",
    ))
    assert r["result"] == "tm_not_found"
    assert r["site"] == "Winamax"
    assert r["tournament_name"] == "EXPLORER"
    mock_log.assert_called_once()
    assert mock_log.call_args.kwargs["result"] == "tm_not_found"


def test_process_pre_2026_skip_no_log():
    with patch("app.services.lobby_sync._upsert_lobby_log") as mock_log:
        r = asyncio.run(lobby_sync.process_lobby_message(
            b"x", "image/png", "m", None,
            datetime(2025, 12, 31, tzinfo=timezone.utc), "",
        ))
    assert r["result"] == "pre_2026_skip"
    mock_log.assert_not_called()


# ── 4-9. run_sync ───────────────────────────────────────────────────────────

@patch("app.services.lobby_sync.process_lobby_message", new_callable=AsyncMock)
@patch("app.services.lobby_sync.query")
@patch("app.discord_bot.get_bot")
def test_run_sync_dry_run_no_vision_calls(mock_get_bot, mock_query, mock_proc):
    """dry_run=True não chama process_lobby_message."""
    mock_query.return_value = [{"n": 0}]  # generic fallback
    # gather_candidates query has 2 cols; já_success_q tem "n".
    # Reusamos uma side_effect simples:
    mock_query.side_effect = [
        [],            # SELECT discord_message_id, result FROM lobby_processing_log
        [{"n": 0}],    # SELECT COUNT(*) ... already success
    ]
    bot, _ = _mock_bot_with_channel([_mock_msg(msg_id="1")])
    mock_get_bot.return_value = bot
    now = datetime.now(timezone.utc)
    r = asyncio.run(lobby_sync.run_sync(
        since=now - timedelta(hours=1), until=now, dry_run=True,
    ))
    mock_proc.assert_not_called()
    assert r["dry_run"] is True
    assert r["processed"] == 0
    assert r["candidates"] == 1


@patch("app.services.lobby_sync.process_lobby_message", new_callable=AsyncMock)
@patch("app.services.lobby_sync.query")
@patch("app.discord_bot.get_bot")
def test_run_sync_skips_existing_success(mock_get_bot, mock_query, mock_proc):
    """Msg com prior result='success' não é candidata."""
    mock_query.side_effect = [
        [{"discord_message_id": "1", "result": "success"}],
        [{"n": 1}],
    ]
    bot, _ = _mock_bot_with_channel([_mock_msg(msg_id="1")])
    mock_get_bot.return_value = bot
    now = datetime.now(timezone.utc)
    r = asyncio.run(lobby_sync.run_sync(
        since=now - timedelta(hours=1), until=now,
    ))
    mock_proc.assert_not_called()
    assert r["candidates"] == 0


@patch("app.services.lobby_sync.process_lobby_message", new_callable=AsyncMock)
@patch("app.services.lobby_sync.query")
@patch("app.discord_bot.get_bot")
def test_run_sync_retry_success_includes_success(mock_get_bot, mock_query, mock_proc):
    """retry_success=True inclui mensagens com prior success."""
    mock_query.side_effect = [
        [{"discord_message_id": "1", "result": "success"}],
        [{"n": 1}],
        # cada candidata processada → mais 1 query SELECT attempt_count;
        # devolvemos algo plausível
        [{"attempt_count": 1, "attempted_at": datetime.now(timezone.utc)}],
    ]
    bot, _ = _mock_bot_with_channel([_mock_msg(msg_id="1")])
    mock_get_bot.return_value = bot
    mock_proc.return_value = {
        "result": "success", "reason_detail": None,
        "site": "GGPoker", "tournament_name": "X", "tournament_number": "1",
        "vision_json": None, "prizes_count": 1,
        "candidates": [], "bounty_type": "PKO", "progressive_factor": 0.5,
        "action": "updated",
    }
    now = datetime.now(timezone.utc)
    r = asyncio.run(lobby_sync.run_sync(
        since=now - timedelta(hours=1), until=now, retry_success=True,
    ))
    assert r["candidates"] == 1
    assert r["results"]["success_new"] == 1


@patch("app.services.lobby_sync.process_lobby_message", new_callable=AsyncMock)
@patch("app.services.lobby_sync.query")
@patch("app.discord_bot.get_bot")
def test_run_sync_failure_types_filter(mock_get_bot, mock_query, mock_proc):
    """failure_types=['tm_not_found'] inclui só essas; exclui outras."""
    mock_query.side_effect = [
        [
            {"discord_message_id": "1", "result": "tm_not_found"},
            {"discord_message_id": "2", "result": "json_invalid"},
            {"discord_message_id": "3", "result": "tm_not_found"},
        ],
        [{"n": 0}],
        [{"attempt_count": 2, "attempted_at": datetime.now(timezone.utc)}],
        [{"attempt_count": 2, "attempted_at": datetime.now(timezone.utc)}],
    ]
    msgs = [_mock_msg(msg_id="1"), _mock_msg(msg_id="2"), _mock_msg(msg_id="3")]
    bot, _ = _mock_bot_with_channel(msgs)
    mock_get_bot.return_value = bot
    mock_proc.return_value = {
        "result": "tm_not_found", "reason_detail": "x",
        "site": "GG", "tournament_name": "Y", "tournament_number": None,
        "vision_json": None, "prizes_count": 0,
        "candidates": [], "bounty_type": None, "progressive_factor": None,
        "action": None,
    }
    now = datetime.now(timezone.utc)
    r = asyncio.run(lobby_sync.run_sync(
        since=now - timedelta(hours=1), until=now,
        failure_types=["tm_not_found"],
    ))
    # msgs 1 e 3 entram (tm_not_found); msg 2 sai (json_invalid não está no filtro)
    assert r["candidates"] == 2


@patch("app.services.lobby_sync.process_lobby_message", new_callable=AsyncMock)
@patch("app.services.lobby_sync.query")
@patch("app.discord_bot.get_bot")
def test_run_sync_rate_limit_pauses_count(mock_get_bot, mock_query, mock_proc):
    """rate_limit_pauses == número de processed quando throttle>0."""
    mock_query.side_effect = [
        [],
        [{"n": 0}],
        [{"attempt_count": 1, "attempted_at": datetime.now(timezone.utc)}],
        [{"attempt_count": 1, "attempted_at": datetime.now(timezone.utc)}],
    ]
    msgs = [_mock_msg(msg_id="1"), _mock_msg(msg_id="2")]
    bot, _ = _mock_bot_with_channel(msgs)
    mock_get_bot.return_value = bot
    mock_proc.return_value = {
        "result": "tm_not_found", "reason_detail": "x",
        "site": "GG", "tournament_name": "Y", "tournament_number": None,
        "vision_json": None, "prizes_count": 0,
        "candidates": [], "bounty_type": None, "progressive_factor": None,
        "action": None,
    }
    now = datetime.now(timezone.utc)
    r = asyncio.run(lobby_sync.run_sync(
        since=now - timedelta(hours=1), until=now,
        throttle_seconds=0.001,  # qualquer >0
    ))
    assert r["rate_limit_pauses"] == 2


@patch("app.services.lobby_sync.process_lobby_message", new_callable=AsyncMock)
@patch("app.services.lobby_sync.query")
@patch("app.discord_bot.get_bot")
def test_run_sync_max_messages_hard_cap(mock_get_bot, mock_query, mock_proc):
    """gather_candidates respeita max_messages."""
    mock_query.side_effect = [
        [],
        [{"n": 0}],
    ]
    msgs = [_mock_msg(msg_id=str(i)) for i in range(10)]
    bot, _ = _mock_bot_with_channel(msgs)
    mock_get_bot.return_value = bot
    now = datetime.now(timezone.utc)
    r = asyncio.run(lobby_sync.run_sync(
        since=now - timedelta(hours=1), until=now,
        max_messages=3, dry_run=True,
    ))
    assert r["candidates"] == 3


@patch("app.discord_bot.get_bot")
def test_run_sync_bot_offline_raises(mock_get_bot):
    mock_get_bot.return_value = None
    now = datetime.now(timezone.utc)
    with pytest.raises(RuntimeError, match="bot_offline"):
        asyncio.run(lobby_sync.run_sync(
            since=now - timedelta(hours=1), until=now,
        ))


@patch("app.discord_bot.get_bot")
def test_run_sync_channel_not_found_raises(mock_get_bot):
    """LOBBY_CHANNEL_NAME não existe em nenhuma guild → RuntimeError."""
    bot = MagicMock()
    bot.is_ready = MagicMock(return_value=True)
    guild = MagicMock()
    other_ch = MagicMock()
    other_ch.name = "general"
    guild.text_channels = [other_ch]
    bot.guilds = [guild]
    mock_get_bot.return_value = bot
    now = datetime.now(timezone.utc)
    with pytest.raises(RuntimeError, match="lobby_channel_not_found"):
        asyncio.run(lobby_sync.run_sync(
            since=now - timedelta(hours=1), until=now,
        ))


# ── 10-11. lobby_processing_log specifics ──────────────────────────────────

def test_upsert_lobby_log_invalid_result_raises():
    with pytest.raises(ValueError, match="invalid result"):
        lobby_sync._upsert_lobby_log(
            message_id="m", channel_id=None, result="gibberish",
        )


@patch("app.services.lobby_sync.get_conn")
def test_upsert_lobby_log_executes_insert_with_on_conflict(mock_get_conn):
    """Verifica que o SQL ON CONFLICT é executado uma vez. attempt_count
    real é responsabilidade da BD; aqui só validamos o call path."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_get_conn.return_value = mock_conn
    lobby_sync._upsert_lobby_log(
        message_id="msgA", channel_id="ch1", result="tm_not_found",
        reason_detail="start=None", site="GG", tournament_name="X",
        posted_at=datetime.now(timezone.utc),
    )
    assert mock_cur.execute.called
    sql_executed = mock_cur.execute.call_args[0][0]
    # Normaliza whitespace para tolerar alinhamento na string SQL.
    sql_norm = " ".join(sql_executed.split())
    assert "ON CONFLICT (discord_message_id)" in sql_norm
    assert "attempt_count = lobby_processing_log.attempt_count + 1" in sql_norm
    mock_conn.commit.assert_called_once()


# ── 12-14. Endpoint ────────────────────────────────────────────────────────

def _make_test_app():
    """FastAPI minimal com router lobbys + override de require_auth."""
    from app.routers.lobbys import router as lobbys_router
    from app.auth import require_auth
    app = FastAPI()
    app.include_router(lobbys_router)
    app.dependency_overrides[require_auth] = lambda: {"id": 1, "email": "t@t"}
    return app


def test_endpoint_invalid_since_until_400():
    app = _make_test_app()
    client = TestClient(app)
    r = client.post("/api/lobbys/sync-recent", json={
        "since": "2026-05-11T10:00:00Z",
        "until": "2026-05-11T09:00:00Z",  # before since
    })
    assert r.status_code == 400
    assert "since must be" in r.json()["detail"]


def test_endpoint_unauthorized_401_without_override():
    from app.routers.lobbys import router as lobbys_router
    app = FastAPI()
    app.include_router(lobbys_router)
    # SEM override de require_auth → 401 esperado
    client = TestClient(app)
    r = client.post("/api/lobbys/sync-recent", json={})
    assert r.status_code == 401


@patch("app.discord_bot.get_bot", return_value=None)
def test_endpoint_bot_offline_returns_503(mock_get_bot):
    app = _make_test_app()
    client = TestClient(app)
    r = client.post("/api/lobbys/sync-recent", json={})
    assert r.status_code == 503
    assert "not online" in r.json()["detail"].lower()
