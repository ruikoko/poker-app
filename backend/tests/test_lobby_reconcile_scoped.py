"""pt81 — `POST /api/lobbys/reconcile` passa a aceitar `message_ids` (lote
específico, não-global). Omisso = comportamento GLOBAL de sempre. O
`reconcile_lobby_logs` já suportava `message_ids`; só faltava expô-lo no endpoint
(para o reconcile a sério de um lote sem tocar nos outros pendentes).
"""
from __future__ import annotations

from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient


def _client():
    from app.routers.lobbys import router
    from app.auth import require_auth
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[require_auth] = lambda: {"id": 1, "email": "t@t"}
    return TestClient(app)


_RES = {"scanned": 2, "resolved": 2, "written": 2, "skipped_precedence": 0,
        "still_unresolved": 0, "dry_run": False, "items": []}


@patch("app.routers.lobbys.reconcile_lobby_logs", return_value=_RES)
def test_reconcile_forwards_message_ids_scoped(mrec):
    r = _client().post("/api/lobbys/reconcile?dry_run=false",
                       json={"message_ids": ["aaa", "bbb"]})
    assert r.status_code == 200, r.text
    mrec.assert_called_once_with(message_ids=["aaa", "bbb"], dry_run=False)


@patch("app.routers.lobbys.reconcile_lobby_logs", return_value={**_RES, "dry_run": True})
def test_reconcile_dry_run_with_message_ids(mrec):
    r = _client().post("/api/lobbys/reconcile?dry_run=true",
                       json={"message_ids": ["x"]})
    assert r.status_code == 200, r.text
    mrec.assert_called_once_with(message_ids=["x"], dry_run=True)


@patch("app.routers.lobbys.reconcile_lobby_logs", return_value=_RES)
def test_reconcile_without_message_ids_is_global(mrec):
    """Sem body / sem message_ids → None → comportamento GLOBAL (como antes)."""
    r = _client().post("/api/lobbys/reconcile")
    assert r.status_code == 200, r.text
    mrec.assert_called_once_with(message_ids=None, dry_run=False)


@patch("app.routers.lobbys.reconcile_lobby_logs", return_value=_RES)
def test_reconcile_empty_message_ids_forwarded(mrec):
    """message_ids=[] é encaminhado tal-qual (reconcile_lobby_logs curto-circuita
    → no-op); não vira global por acidente."""
    r = _client().post("/api/lobbys/reconcile", json={"message_ids": []})
    assert r.status_code == 200, r.text
    mrec.assert_called_once_with(message_ids=[], dry_run=False)
