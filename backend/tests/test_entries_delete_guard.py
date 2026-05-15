"""Tests do guard DELETE para entries 'hm3_synthetic'
(#ORFA-HM3-SYNTHETIC-ENTRIES Peca 3)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.entries import router as entries_router
from app.auth import require_auth


def _make_app():
    app = FastAPI()
    app.include_router(entries_router)
    app.dependency_overrides[require_auth] = lambda: {"id": 1, "email": "t@t"}
    return app


class _GuardCursor:
    """Cursor que devolve `existing_source` no primeiro SELECT (single-delete
    guard) ou `bulk_synth_hits` no SELECT do bulk-delete guard, depois faz
    DELETE/UPDATE normais."""

    def __init__(self, existing_source=None, bulk_synth_hits=None):
        self.existing_source = existing_source
        self.bulk_synth_hits = bulk_synth_hits or []
        self.executed: list[tuple] = []
        self._next = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self.executed.append((sql.strip()[:80], params))
        s = sql.lower()
        if "select source from entries" in s:
            self._next = (
                {"source": self.existing_source}
                if self.existing_source is not None
                else None
            )
        elif "select id from entries" in s and "hm3_synthetic" in s:
            self._next_many = list(self.bulk_synth_hits)
        elif "delete from entries" in s or "delete from hands" in s:
            self.rowcount = 1
        else:
            self._next = None

    def fetchone(self):
        return self._next

    def fetchall(self):
        return getattr(self, "_next_many", [])


class _GuardConn:
    def __init__(self, cursor):
        self.cur = cursor
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return self.cur

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        pass


# ── DELETE individual ────────────────────────────────────────────────


def test_delete_single_hm3_synthetic_returns_400():
    cur = _GuardCursor(existing_source="hm3_synthetic")
    conn = _GuardConn(cur)
    app = _make_app()
    client = TestClient(app)
    with patch("app.db.get_conn", return_value=conn):
        r = client.delete("/api/entries/42")
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert "hm3" in detail.lower() or "sintetic" in detail.lower() or "sintét" in detail
    assert conn.rolled_back


def test_delete_single_discord_passes_guard():
    """source='discord' continua a permitir DELETE."""
    cur = _GuardCursor(existing_source="discord")
    conn = _GuardConn(cur)
    app = _make_app()
    client = TestClient(app)
    with patch("app.db.get_conn", return_value=conn):
        r = client.delete("/api/entries/42")
    assert r.status_code == 200
    assert conn.committed


def test_delete_single_entry_not_found_returns_404():
    cur = _GuardCursor(existing_source=None)  # SELECT devolve None
    conn = _GuardConn(cur)
    app = _make_app()
    client = TestClient(app)
    with patch("app.db.get_conn", return_value=conn):
        r = client.delete("/api/entries/999")
    assert r.status_code == 404


# ── Bulk delete ──────────────────────────────────────────────────────


def test_bulk_delete_with_hm3_synthetic_in_batch_returns_400():
    cur = _GuardCursor(bulk_synth_hits=[{"id": 42}])
    conn = _GuardConn(cur)
    app = _make_app()
    client = TestClient(app)
    with patch("app.db.get_conn", return_value=conn):
        r = client.post(
            "/api/entries/bulk-delete",
            json={"entry_ids": [40, 41, 42]},
        )
    assert r.status_code == 400
    assert "42" in r.json()["detail"]
    assert conn.rolled_back


def test_bulk_delete_sem_synthetic_passa_guard():
    cur = _GuardCursor(bulk_synth_hits=[])  # nenhum hit synthetic
    conn = _GuardConn(cur)
    app = _make_app()
    client = TestClient(app)
    with patch("app.db.get_conn", return_value=conn):
        r = client.post(
            "/api/entries/bulk-delete",
            json={"entry_ids": [1, 2, 3]},
        )
    assert r.status_code == 200
    assert conn.committed


def test_bulk_delete_empty_list_short_circuit():
    """Lista vazia retorna 200 sem tocar DB."""
    app = _make_app()
    client = TestClient(app)
    r = client.post("/api/entries/bulk-delete", json={"entry_ids": []})
    assert r.status_code == 200
    assert r.json() == {"ok": True, "deleted": 0}
