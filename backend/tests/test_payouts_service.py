"""Unit tests para services/payouts_service.upsert_payout (FASE A COMMIT 1)."""
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from app.services.payouts_service import upsert_payout


def _ok_blob():
    return {
        "name": "/",
        "folders": [],
        "structures": [{
            "name": "Test BBG $54",
            "chips": 1000000.0,
            "prizes": {"1": 100.0, "2": 50.0},
            "bountyType": "PKO",
            "progressiveFactor": 0.5,
        }],
    }


def test_upsert_inserts_new_row():
    fake_row = {
        "site": "GGPoker",
        "tournament_number": "281416137",
        "source": "manual_upload",
        "uploaded_at": datetime(2026, 5, 9, 0, 33, tzinfo=timezone.utc),
        "inserted": True,
    }
    with patch(
        "app.services.payouts_service.execute_returning",
        return_value=fake_row,
    ) as m:
        result = upsert_payout("GGPoker", "281416137", _ok_blob(), "manual_upload")
    m.assert_called_once()
    assert result["action"] == "inserted"
    assert result["site"] == "GGPoker"
    assert result["tournament_number"] == "281416137"
    assert result["source"] == "manual_upload"
    assert result["uploaded_at"].year == 2026


def test_upsert_updates_existing():
    fake_row = {
        "site": "GGPoker",
        "tournament_number": "281416137",
        "source": "discord_lobby_vision",
        "uploaded_at": datetime(2026, 5, 9, 1, 0, tzinfo=timezone.utc),
        "inserted": False,
    }
    with patch(
        "app.services.payouts_service.execute_returning",
        return_value=fake_row,
    ):
        result = upsert_payout(
            "GGPoker", "281416137", _ok_blob(), "discord_lobby_vision"
        )
    assert result["action"] == "updated"


def test_upsert_strips_whitespace_in_site_and_tn():
    fake_row = {
        "site": "GGPoker",
        "tournament_number": "281416137",
        "source": None,
        "uploaded_at": datetime(2026, 5, 9, tzinfo=timezone.utc),
        "inserted": True,
    }
    with patch(
        "app.services.payouts_service.execute_returning",
        return_value=fake_row,
    ) as m:
        upsert_payout("  GGPoker  ", "  281416137  ", _ok_blob())
    args = m.call_args[0]
    assert args[1][0] == "GGPoker"
    assert args[1][1] == "281416137"


def test_upsert_rejects_empty_site():
    with pytest.raises(ValueError, match="site"):
        upsert_payout("", "281416137", _ok_blob())


def test_upsert_rejects_whitespace_site():
    with pytest.raises(ValueError, match="site"):
        upsert_payout("   ", "281416137", _ok_blob())


def test_upsert_rejects_empty_tn():
    with pytest.raises(ValueError, match="tournament_number"):
        upsert_payout("GGPoker", "", _ok_blob())


def test_upsert_rejects_null_blob():
    with pytest.raises(ValueError, match="null"):
        upsert_payout("GGPoker", "281416137", None)
