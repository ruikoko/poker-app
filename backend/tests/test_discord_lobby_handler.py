"""Unit tests para PokerBot._handle_lobby_message (FASE A COMMIT 3).

Mocks: discord.Message + attachments, lobby_vision functions, tournament_resolver,
payouts_service. Sem ligacao Discord nem Anthropic real.
"""
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.discord_bot import PokerBot


def _bot():
    """Instancia PokerBot sem chamar __init__ (que precisa intents Discord)."""
    return PokerBot.__new__(PokerBot)


def _mock_message(
    *, attachment_urls=None, content_bytes=b"FAKE_PNG_BYTES",
    msg_id=12345, channel_name="lobbys",
    posted_at=datetime(2026, 5, 9, 12, 0, tzinfo=timezone.utc),
):
    msg = MagicMock()
    msg.id = msg_id
    msg.content = ""
    msg.created_at = posted_at
    msg.author = MagicMock(id=999)
    msg.channel = MagicMock()
    msg.channel.name = channel_name
    msg.attachments = []
    for url in (attachment_urls or []):
        att = MagicMock()
        att.url = url
        att.content_type = "image/png"
        att.read = AsyncMock(return_value=content_bytes)
        msg.attachments.append(att)
    msg.reply = AsyncMock()
    return msg


_GOOD_VJ = {
    "site": "GGPoker",
    "tournament_name": "Bounty Hunters Big Game $215",
    "start_time_iso": "2026-05-05T18:30:00Z",
    "starting_stack": 25000,
    "entrants": 2996,
    "prizes": {"1": 9119.22, "2": 9118.84},
    "bounty_type_text": "PKO 50%",
}

_GOOD_BLOB = {
    "name": "/", "folders": [],
    "structures": [{
        "name": "Bounty Hunters Big Game $215",
        "chips": 74900000.0,
        "prizes": {"1": 9119.22, "2": 9118.84},
        "bountyType": "PKO",
        "progressiveFactor": 0.5,
    }],
}


def test_lobby_success_inserted():
    bot = _bot()
    msg = _mock_message(attachment_urls=["http://cdn/lobby.png"])
    upsert_result = {
        "site": "GGPoker", "tournament_number": "281416137",
        "source": "discord_lobby_vision:12345",
        "uploaded_at": datetime(2026, 5, 9, 12, 0, tzinfo=timezone.utc),
        "action": "inserted",
    }
    with patch("app.services.lobby_vision.extract_lobby_payout_json",
               return_value='{"...":""}'), \
         patch("app.services.lobby_vision.parse_and_validate_lobby_json",
               return_value=_GOOD_VJ), \
         patch("app.services.lobby_vision.build_hrc_payouts_blob",
               return_value=_GOOD_BLOB), \
         patch("app.services.tournament_resolver.resolve_tournament_number",
               return_value=("281416137", [], "summaries")), \
         patch("app.services.payouts_service.upsert_payout",
               return_value=upsert_result) as m_upsert, \
         patch("app.services.lobby_sync.query", return_value=[]):
        asyncio.run(bot._handle_lobby_message(msg))

    msg.reply.assert_called_once()
    reply_text = msg.reply.call_args[0][0]
    assert "✅" in reply_text
    assert "Adicionado" in reply_text
    assert "281416137" in reply_text
    assert "PKO 50%" in reply_text
    assert "2 posições" in reply_text
    kwargs = m_upsert.call_args.kwargs
    assert kwargs["source"] == "discord_lobby_vision:12345"


def test_lobby_vision_returns_none_replies_error():
    bot = _bot()
    msg = _mock_message(attachment_urls=["http://cdn/lobby.png"])
    with patch("app.services.lobby_vision.extract_lobby_payout_json",
               return_value=None):
        asyncio.run(bot._handle_lobby_message(msg))
    msg.reply.assert_called_once()
    assert "❌" in msg.reply.call_args[0][0]
    assert "Vision falhou" in msg.reply.call_args[0][0]


def test_lobby_invalid_json_replies_error():
    bot = _bot()
    msg = _mock_message(attachment_urls=["http://cdn/lobby.png"])
    with patch("app.services.lobby_vision.extract_lobby_payout_json",
               return_value="{garbage"), \
         patch("app.services.lobby_vision.parse_and_validate_lobby_json",
               return_value=None):
        asyncio.run(bot._handle_lobby_message(msg))
    assert "❌" in msg.reply.call_args[0][0]
    assert "Estrutura" in msg.reply.call_args[0][0]


def test_lobby_tm_ambiguous_lists_candidates():
    bot = _bot()
    msg = _mock_message(attachment_urls=["http://cdn/lobby.png"])
    candidates = [
        {"tournament_number": "111", "tournament_name": "BBG $215",
         "start_time": datetime(2026, 5, 5, 18, 30, tzinfo=timezone.utc)},
        {"tournament_number": "222", "tournament_name": "BBG $215",
         "start_time": datetime(2026, 5, 5, 19, 30, tzinfo=timezone.utc)},
    ]
    with patch("app.services.lobby_vision.extract_lobby_payout_json",
               return_value='{"...":""}'), \
         patch("app.services.lobby_vision.parse_and_validate_lobby_json",
               return_value=_GOOD_VJ), \
         patch("app.services.tournament_resolver.resolve_tournament_number",
               return_value=(None, candidates, "summaries")):
        asyncio.run(bot._handle_lobby_message(msg))
    reply = msg.reply.call_args[0][0]
    assert "❌" in reply
    assert "2 candidatos" in reply
    assert "#111" in reply
    assert "#222" in reply


def test_lobby_tm_not_found_replies_error():
    bot = _bot()
    msg = _mock_message(attachment_urls=["http://cdn/lobby.png"])
    with patch("app.services.lobby_vision.extract_lobby_payout_json",
               return_value='{"...":""}'), \
         patch("app.services.lobby_vision.parse_and_validate_lobby_json",
               return_value=_GOOD_VJ), \
         patch("app.services.tournament_resolver.resolve_tournament_number",
               return_value=(None, [], None)):
        asyncio.run(bot._handle_lobby_message(msg))
    reply = msg.reply.call_args[0][0]
    assert "❌" in reply
    assert "Sem match" in reply


def test_lobby_message_without_images_no_reply():
    bot = _bot()
    msg = _mock_message(attachment_urls=[])
    asyncio.run(bot._handle_lobby_message(msg))
    msg.reply.assert_not_called()
