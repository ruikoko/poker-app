"""Tests para require_auth_or_api_key — dual-path cookie + bearer."""
import os
from unittest.mock import patch

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.auth import require_auth_or_api_key, create_session_token


_TEST_KEY = "test-key-" + "x" * 50  # >=48 chars realista


def _make_app():
    app = FastAPI()

    @app.get("/protected")
    def _protected(user=Depends(require_auth_or_api_key)):
        return {"auth_type": user.get("auth_type", "cookie"), "id": user.get("id")}

    return app


# ── 1. Header válido ───────────────────────────────────────────────────────

def test_bearer_valid_authenticates_as_api_key():
    app = _make_app()
    client = TestClient(app)
    with patch.dict(os.environ, {"HRC_WATCHER_API_KEY": _TEST_KEY}):
        r = client.get("/protected", headers={"Authorization": f"Bearer {_TEST_KEY}"})
    assert r.status_code == 200
    body = r.json()
    assert body["auth_type"] == "api_key"
    assert body["id"] is None


# ── 2. Header malformado ou inválido ───────────────────────────────────────

@pytest.mark.parametrize("header,desc", [
    ("Bearer wrong_token_value", "wrong token"),
    ("Bearer ", "empty token"),
    ("Banana abc", "wrong scheme"),
    ("Bearer", "no token"),
])
def test_bearer_invalid_returns_401(header, desc):
    app = _make_app()
    client = TestClient(app)
    with patch.dict(os.environ, {"HRC_WATCHER_API_KEY": _TEST_KEY}):
        r = client.get("/protected", headers={"Authorization": header})
    assert r.status_code == 401, f"{desc} should 401"


# ── 3. Cookie válido continua a funcionar (regressão) ──────────────────────

def test_cookie_valid_still_works():
    """Garante que o caminho cookie-only não regrediu."""
    app = _make_app()
    client = TestClient(app)
    with patch.dict(os.environ, {"SESSION_SECRET": "test-secret-for-tests"}):
        token = create_session_token(user_id=42)
        with patch("app.auth.query", return_value=[{"id": 42, "email": "t@t"}]):
            r = client.get("/protected", cookies={"session": token})
    assert r.status_code == 200
    body = r.json()
    assert body["auth_type"] == "cookie"
    assert body["id"] == 42


# ── 4. Sem cookie e sem header → 401 ───────────────────────────────────────

def test_no_auth_returns_401():
    app = _make_app()
    client = TestClient(app)
    r = client.get("/protected")
    assert r.status_code == 401
    assert "Não autenticado" in r.json()["detail"]
