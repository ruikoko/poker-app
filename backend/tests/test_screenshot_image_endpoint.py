"""Regressão #REPLAYER-IMG-HH-FIRST (pt46): /api/screenshots/image/{entry_id}
serve img_b64 de entries 'screenshot' E 'replayer_link' (imagem captada do
replayer GG no caminho HH-primeiro), mantendo 404 para tipos sem imagem."""
from __future__ import annotations

import base64
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.screenshot import router as ss_router
from app.auth import require_auth

_PNG = base64.b64encode(b"\x89PNG\r\n\x1a\nFAKEBYTES").decode()


def _make_app():
    app = FastAPI()
    app.include_router(ss_router)
    app.dependency_overrides[require_auth] = lambda: {"id": 1, "email": "t@t"}
    return app


def test_image_endpoint_sql_accepts_screenshot_and_replayer_link():
    """A SQL do endpoint deixou de filtrar só 'screenshot' — aceita os dois tipos."""
    sqls = []

    def fake_query(sql, params=None):
        sqls.append(sql)
        return [{"raw_json": {"img_b64": _PNG, "mime_type": "image/png"}}]

    app = _make_app()
    with patch("app.routers.screenshot.query", side_effect=fake_query):
        r = TestClient(app).get("/api/screenshots/image/2357")

    assert r.status_code == 200
    assert "screenshot" in sqls[0]
    assert "replayer_link" in sqls[0]


def test_image_endpoint_serves_replayer_link_b64():
    """replayer_link com img_b64 -> 200 + bytes correctos + mime do raw_json."""
    def fake_query(sql, params=None):
        # Simula a row que a SQL (entry_type IN ('screenshot','replayer_link'))
        # devolveria para um entry replayer_link com imagem captada.
        return [{"raw_json": {"img_b64": _PNG, "mime_type": "image/png"}}]

    app = _make_app()
    with patch("app.routers.screenshot.query", side_effect=fake_query):
        r = TestClient(app).get("/api/screenshots/image/2357")

    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/png")
    assert r.content == base64.b64decode(_PNG)


def test_image_endpoint_404_when_type_not_served():
    """hand_history (excluído pela SQL) -> sem rows -> 404."""
    def fake_query(sql, params=None):
        return []   # WHERE entry_type IN (...) exclui hand_history/HM3

    app = _make_app()
    with patch("app.routers.screenshot.query", side_effect=fake_query):
        r = TestClient(app).get("/api/screenshots/image/2327")

    assert r.status_code == 404


def test_image_endpoint_404_when_no_img_b64():
    """Entry servível mas sem img_b64 -> 404 (não ícone partido)."""
    def fake_query(sql, params=None):
        return [{"raw_json": {"mime_type": "image/png"}}]

    app = _make_app()
    with patch("app.routers.screenshot.query", side_effect=fake_query):
        r = TestClient(app).get("/api/screenshots/image/999")

    assert r.status_code == 404
