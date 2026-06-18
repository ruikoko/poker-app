"""Derivador deanon_status (pt76) + presença nos 3 endpoints que mostram nomes."""
import pytest
from app.services.deanon_status import deanon_status, deanon_status_from_row


@pytest.mark.parametrize("site,mm,exp", [
    ("GGPoker", "table_ss", "unverified"),
    ("GGPoker", "anchors_stack_elimination_v2", "unverified"),
    ("GGPoker", "anchors_stack_elimination_v2_refix", "unverified"),
    ("GGPoker", "mtt_promote_v2", "unverified"),
    ("GGPoker", "mtt_import_v3", "unverified"),
    ("GGPoker", "position_v3", "verified"),
    ("GGPoker", None, None),
    ("GGPoker", "", None),
    ("GGPoker", "discord_placeholder_no_hh", None),
    ("GGPoker", "qualquer_desconhecido", None),
    ("Winamax", "position_v3", None),   # não-GG → sem aviso (nomes reais da HH)
    ("PokerStars", None, None),
    ("WPN", None, None),
])
def test_deanon_status(site, mm, exp):
    assert deanon_status(site, mm) == exp


def test_from_row_dict_e_str():
    assert deanon_status_from_row({"site": "GGPoker", "player_names": {"match_method": "table_ss"}}) == "unverified"
    assert deanon_status_from_row({"site": "GGPoker", "player_names": '{"match_method":"position_v3"}'}) == "verified"
    assert deanon_status_from_row({"site": "Winamax", "player_names": None}) is None
    assert deanon_status_from_row({"site": "GGPoker", "player_names": None}) is None


# ── Presença do campo nos 3 endpoints (mock DB) ─────────────────────────

from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _gg_row(mm, **extra):
    base = {
        "id": 1, "site": "GGPoker", "hand_id": "GG-1", "played_at": None,
        "stakes": None, "position": None, "hero_cards": [], "board": [], "result": 0,
        "currency": "$", "notes": None, "tags": [], "hm3_tags": [], "discord_tags": [],
        "study_state": "review", "entry_id": 5, "viewed_at": None, "studied_at": None,
        "created_at": None, "all_players_actions": {"_meta": {"bb": 1000}},
        "screenshot_url": None, "player_names": {"match_method": mm}, "raw": "x",
        "tournament_format": None, "tournament_name": None, "tournament_number": None,
        "buy_in": None, "folder_ft_source": None, "match_state": "matched",
        "has_screenshot_image": False, "discord_channel": None, "discord_posted_at": None,
        "discord_channel_name": None, "attachment_count": 0, "attachments": [],
    }
    base.update(extra)
    return base


def test_list_hands_inclui_deanon_status():
    from app.routers.hands import router
    from app.auth import require_auth
    app = FastAPI(); app.include_router(router)
    app.dependency_overrides[require_auth] = lambda: {"id": 1}
    client = TestClient(app)

    def fake_query(sql, params=None):
        s = sql.lower()
        if "count(*) as total" in s:
            return [{"total": 2}]
        if "from hands h" in s and "select h.id" in s:
            return [_gg_row("table_ss", id=1), _gg_row("position_v3", id=2)]
        return []  # meta/wn-raw lookups

    with patch("app.routers.hands.query", side_effect=fake_query):
        r = client.get("/api/hands?study_view=true")
    assert r.status_code == 200, r.text
    by_id = {h["id"]: h for h in r.json()["data"]}
    assert by_id[1]["deanon_status"] == "unverified"
    assert by_id[2]["deanon_status"] == "verified"


def test_villain_hands_inclui_deanon_status():
    from app.routers.villains import router
    from app.auth import require_auth
    app = FastAPI(); app.include_router(router)
    app.dependency_overrides[require_auth] = lambda: {"id": 1}
    client = TestClient(app)

    row = _gg_row("table_ss", id=3, all_players_actions={"_meta": {"bb": 1000}})
    def fake_query(sql, params=None):
        s = sql.lower()
        if "join hand_villains" in s and "select distinct" in s:
            return [row]
        if "count" in s:
            return [{"total": 1}]
        return []
    with patch("app.routers.villains.query", side_effect=fake_query):
        r = client.get("/api/villains/search/hands?nick=Alice")
    assert r.status_code == 200, r.text
    assert r.json()["data"][0]["deanon_status"] == "unverified"
