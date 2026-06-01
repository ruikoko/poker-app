"""Tests do flag has_screenshot_image nos endpoints /api/hands
(#ORFA-HM3-SYNTHETIC-ENTRIES Peca 4)."""
from __future__ import annotations

from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.hands import router as hands_router
from app.auth import require_auth


def _make_app():
    app = FastAPI()
    app.include_router(hands_router)
    app.dependency_overrides[require_auth] = lambda: {"id": 1, "email": "t@t"}
    return app


def test_list_hands_sql_inclui_has_screenshot_image_column():
    """SQL do /api/hands list inclui a coluna derivada has_screenshot_image."""
    sqls_captured = []

    def fake_query(sql, params=None):
        sqls_captured.append(sql)
        # primeira query e o COUNT, depois a query principal — devolvemos []
        # para o COUNT e [] para data; FastAPI lida bem com isso.
        if "COUNT(*)" in sql:
            return [{"total": 0}]
        return []

    app = _make_app()
    client = TestClient(app)
    with patch("app.routers.hands.query", side_effect=fake_query), \
         patch("app.db.query", side_effect=fake_query):
        r = client.get("/api/hands")

    assert r.status_code == 200
    # Pelo menos uma SQL emitida pelo endpoint inclui o flag.
    matches = [s for s in sqls_captured if "has_screenshot_image" in s]
    assert matches, (
        "Endpoint /api/hands deve incluir a coluna has_screenshot_image "
        "(derivada de e.entry_type='screenshot'). SQLs emitidas:\n"
        + "\n---\n".join(sqls_captured)
    )
    # Verifica que a derivacao usa o JOIN com entries.
    # #REPLAYER-IMG-HH-FIRST (pt46): aceita também replayer_link com img_b64.
    assert "e.entry_type = 'screenshot'" in matches[0]
    assert "replayer_link" in matches[0]
    assert "img_b64" in matches[0]


def test_get_hand_detail_sql_inclui_has_screenshot_image_column():
    """SQL do GET /api/hands/{id} inclui has_screenshot_image."""
    sqls_captured = []
    hand_row = {
        "id": 42,
        "raw": None,
        "all_players_actions": None,
        "screenshot_url": None,
        "has_screenshot_image": False,
        "viewed_at": "2026-05-15T10:00:00Z",  # skip viewed_at UPDATE
        "site": "GGPoker",
        "tournament_id": None,
        "result": None,
        "hand_id": "GG-x",
        "played_at": None,
        "stakes": None,
    }

    def fake_query(sql, params=None):
        sqls_captured.append(sql)
        if "FROM hand_attachments" in sql:
            return []
        return [hand_row]

    app = _make_app()
    client = TestClient(app)
    with patch("app.routers.hands.query", side_effect=fake_query), \
         patch("app.db.query", side_effect=fake_query), \
         patch("app.routers.hands.execute"), \
         patch("app.routers.hands.compute_ire", return_value=None) if False else patch("app.services.ire.compute_ire", return_value=None):
        r = client.get("/api/hands/42")

    assert r.status_code == 200, r.text
    body = r.json()
    # Coluna chega ao frontend como flag boolean.
    assert "has_screenshot_image" in body
    # SQL contem a derivacao.
    matches = [s for s in sqls_captured if "has_screenshot_image" in s]
    assert matches, sqls_captured
