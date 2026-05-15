"""Tests para o parser de Complete Export HRC (services/hrc_import.py)
e para o router /api/hrc/import."""
from __future__ import annotations

import io
import json
import zipfile
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.hrc import router as hrc_router
from app.auth import require_auth
from app.services.hrc_import import (
    HRCImportError,
    iter_nodes,
    list_node_indices,
    open_hrc_zip,
    parse_hrc_zip_summary,
    read_equity,
    read_settings,
)


# ── Helpers ────────────────────────────────────────────────────────────


_DEFAULT_SETTINGS = {
    "handdata": {
        "stacks": [10000, 10000],
        "blinds": [100, 50, 0],
        "anteType": "REGULAR",
    },
    "eqmodel": {"id": "mtticm"},
}

_DEFAULT_EQUITY = {
    "equityUnit": "TABLE_EQUITY_PERCENT",
    "preHandEquity": [50.0, 50.0],
}

_DEFAULT_NODE_0 = {
    "player": 0,
    "street": 0,
    "children": 2,
    "sequence": [],
    "actions": [
        {"type": "F", "amount": 0, "node": 1},
        {"type": "R", "amount": 200, "node": 2},
    ],
    "hands": {
        "AA": {"weight": 1.0, "played": [0.0, 1.0], "evs": [0.0, 5.5]},
        "22": {"weight": 1.0, "played": [0.5, 0.5], "evs": [0.0, 0.1]},
    },
}

_DEFAULT_NODE_1 = {
    "player": 1,
    "street": 0,
    "children": 0,
    "sequence": [{"player": 0, "type": "F", "amount": 0, "street": 0}],
    "actions": [],
    "hands": {
        "AA": {"weight": 1.0, "played": [], "evs": []},
    },
}


def _make_hrc_zip(
    settings: dict | None = None,
    equity: dict | None = None,
    nodes: dict[int, dict] | None = None,
    extras: dict[str, bytes] | None = None,
    omit_settings: bool = False,
    omit_equity: bool = False,
) -> bytes:
    if settings is None:
        settings = _DEFAULT_SETTINGS
    if equity is None:
        equity = _DEFAULT_EQUITY
    if nodes is None:
        nodes = {0: _DEFAULT_NODE_0, 1: _DEFAULT_NODE_1}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        if not omit_settings:
            zf.writestr("settings.json", json.dumps(settings))
        if not omit_equity:
            zf.writestr("equity.json", json.dumps(equity))
        for idx, node in nodes.items():
            zf.writestr(f"nodes/{idx}.json", json.dumps(node))
        for name, content in (extras or {}).items():
            zf.writestr(name, content)
    return buf.getvalue()


# ── Parser: happy path ────────────────────────────────────────────────


def test_parse_summary_happy_path():
    raw = _make_hrc_zip()
    out = parse_hrc_zip_summary(raw)
    assert out["total_nodes"] == 2
    assert out["node_indices"] == [0, 1]
    assert out["settings"]["handdata"]["stacks"] == [10000, 10000]
    assert out["equity"]["preHandEquity"] == [50.0, 50.0]


def test_iter_nodes_yields_in_order():
    raw = _make_hrc_zip(nodes={2: _DEFAULT_NODE_1, 0: _DEFAULT_NODE_0, 1: _DEFAULT_NODE_1})
    zf = open_hrc_zip(raw)
    try:
        indices = list_node_indices(zf)
        assert indices == [0, 1, 2]
        out = [(idx, node["player"]) for idx, node in iter_nodes(zf, indices)]
    finally:
        zf.close()
    assert [i for i, _ in out] == [0, 1, 2]


def test_list_node_indices_ignores_non_node_files():
    raw = _make_hrc_zip(
        extras={
            "README.md": b"hello",
            "nodes/extra.txt": b"noise",
            "other/deep/0.json": b'{"player":0}',
        }
    )
    zf = open_hrc_zip(raw)
    try:
        assert list_node_indices(zf) == [0, 1]
    finally:
        zf.close()


# ── Parser: error paths ──────────────────────────────────────────────


def test_parse_summary_bad_zip():
    with pytest.raises(HRCImportError, match="Zip invalido"):
        parse_hrc_zip_summary(b"not a zip")


def test_parse_summary_missing_settings():
    raw = _make_hrc_zip(omit_settings=True)
    with pytest.raises(HRCImportError, match="settings.json"):
        parse_hrc_zip_summary(raw)


def test_parse_summary_missing_equity():
    raw = _make_hrc_zip(omit_equity=True)
    with pytest.raises(HRCImportError, match="equity.json"):
        parse_hrc_zip_summary(raw)


def test_parse_summary_no_nodes():
    raw = _make_hrc_zip(nodes={})
    with pytest.raises(HRCImportError, match="nodes/N.json"):
        parse_hrc_zip_summary(raw)


def test_parse_summary_no_root_node():
    raw = _make_hrc_zip(nodes={1: _DEFAULT_NODE_1, 2: _DEFAULT_NODE_1})
    with pytest.raises(HRCImportError, match="nodes/0.json"):
        parse_hrc_zip_summary(raw)


def test_settings_invalid_json():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("settings.json", "{ not json")
        zf.writestr("equity.json", json.dumps(_DEFAULT_EQUITY))
        zf.writestr("nodes/0.json", json.dumps(_DEFAULT_NODE_0))
    with pytest.raises(HRCImportError, match="JSON invalido"):
        parse_hrc_zip_summary(buf.getvalue())


def test_settings_not_object():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("settings.json", "[1, 2, 3]")
        zf.writestr("equity.json", json.dumps(_DEFAULT_EQUITY))
        zf.writestr("nodes/0.json", json.dumps(_DEFAULT_NODE_0))
    with pytest.raises(HRCImportError, match="nao e objecto"):
        parse_hrc_zip_summary(buf.getvalue())


def test_settings_missing_handdata():
    raw = _make_hrc_zip(settings={"eqmodel": {}})
    with pytest.raises(HRCImportError, match="handdata"):
        parse_hrc_zip_summary(raw)


def test_node_missing_required_field():
    bad_node = {"player": 0, "street": 0}  # falta sequence/actions/hands
    raw = _make_hrc_zip(nodes={0: bad_node})
    zf = open_hrc_zip(raw)
    try:
        with pytest.raises(HRCImportError, match="campos obrigatorios"):
            list(iter_nodes(zf, [0]))
    finally:
        zf.close()


# ── Router /api/hrc/import + DB layer mocked ────────────────────────────


def _make_app():
    app = FastAPI()
    app.include_router(hrc_router)
    app.dependency_overrides[require_auth] = lambda: {"id": 1, "email": "t@t"}
    return app


class _FakeCursor:
    """Mock minimal cursor que captura execute_values e devolve id falso."""

    def __init__(self, store: dict):
        self.store = store
        self.last_sql = None
        self.last_params = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        self.last_sql = sql
        self.last_params = params
        if "INSERT INTO hrc_sessions" in sql:
            self.store["inserted_session"] = params
            self.store["row"] = {"id": 42}

    def fetchone(self):
        return self.store.get("row")


class _FakeConn:
    def __init__(self, store: dict):
        self.store = store
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return _FakeCursor(self.store)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        pass


def test_import_endpoint_happy_path():
    app = _make_app()
    client = TestClient(app)
    raw = _make_hrc_zip()
    store: dict = {}
    fake_conn = _FakeConn(store)

    captured_nodes = []

    def fake_execute_values(cur, sql, batch, template):
        # Capturar nodes inseridos para validacao
        captured_nodes.extend(batch)

    with patch("app.routers.hrc.get_conn", return_value=fake_conn), \
         patch("psycopg2.extras.execute_values", side_effect=fake_execute_values):
        r = client.post(
            "/api/hrc/import",
            files={"file": ("mko.zip", raw, "application/zip")},
            data={"source": "manual"},
        )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body == {"session_id": 42, "total_nodes": 2}
    assert fake_conn.committed
    assert not fake_conn.rolled_back

    # Nome derivado do filename sem extensao.
    inserted = store["inserted_session"]
    assert inserted[0] == "mko"
    assert inserted[3] == 2  # total_nodes
    assert inserted[4] == "manual"

    # 2 nodes inseridos em batch.
    assert len(captured_nodes) == 2
    node_idx_0 = next(n for n in captured_nodes if n[1] == 0)
    assert node_idx_0[2] == 0  # player
    assert node_idx_0[3] == 0  # street


def test_import_explicit_name_overrides_filename():
    app = _make_app()
    client = TestClient(app)
    raw = _make_hrc_zip()
    store: dict = {}
    fake_conn = _FakeConn(store)
    with patch("app.routers.hrc.get_conn", return_value=fake_conn), \
         patch("psycopg2.extras.execute_values"):
        r = client.post(
            "/api/hrc/import",
            files={"file": ("anything.zip", raw, "application/zip")},
            data={"name": "Custom Session 1", "source": "watcher"},
        )
    assert r.status_code == 200
    inserted = store["inserted_session"]
    assert inserted[0] == "Custom Session 1"
    assert inserted[4] == "watcher"


def test_import_invalid_source():
    app = _make_app()
    client = TestClient(app)
    r = client.post(
        "/api/hrc/import",
        files={"file": ("mko.zip", b"x", "application/zip")},
        data={"source": "bogus"},
    )
    assert r.status_code == 400
    assert "source" in r.json()["detail"]


def test_import_empty_file():
    app = _make_app()
    client = TestClient(app)
    r = client.post(
        "/api/hrc/import",
        files={"file": ("mko.zip", b"", "application/zip")},
    )
    assert r.status_code == 400


def test_import_bad_zip():
    app = _make_app()
    client = TestClient(app)
    r = client.post(
        "/api/hrc/import",
        files={"file": ("mko.zip", b"not a zip", "application/zip")},
    )
    assert r.status_code == 400
    assert "Zip invalido" in r.json()["detail"]


def test_import_no_root_node_rejected():
    app = _make_app()
    client = TestClient(app)
    raw = _make_hrc_zip(nodes={1: _DEFAULT_NODE_1, 2: _DEFAULT_NODE_1})
    r = client.post(
        "/api/hrc/import",
        files={"file": ("mko.zip", raw, "application/zip")},
    )
    assert r.status_code == 400
    assert "nodes/0.json" in r.json()["detail"]


def test_import_no_auth():
    app = FastAPI()
    app.include_router(hrc_router)
    # SEM override
    client = TestClient(app)
    r = client.post(
        "/api/hrc/import",
        files={"file": ("mko.zip", b"x", "application/zip")},
    )
    assert r.status_code == 401


# ── DELETE /api/hrc/sessions/{id} ────────────────────────────────────────


class _DeleteCursor:
    def __init__(self, store: dict):
        self.store = store

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        self.store["sql"] = sql
        self.store["params"] = params
        # store["found"] controla se devolvemos row ou None
        if self.store.get("found", True):
            self.store["row"] = {"id": params[0], "name": "mko"}
        else:
            self.store["row"] = None

    def fetchone(self):
        return self.store.get("row")


class _DeleteConn:
    def __init__(self, store: dict):
        self.store = store
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return _DeleteCursor(self.store)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        pass


def test_delete_session_happy_path():
    app = _make_app()
    client = TestClient(app)
    store: dict = {"found": True}
    fake_conn = _DeleteConn(store)
    with patch("app.routers.hrc.get_conn", return_value=fake_conn):
        r = client.delete("/api/hrc/sessions/42")
    assert r.status_code == 200
    body = r.json()
    assert body == {"deleted": True, "session_id": 42, "name": "mko"}
    assert fake_conn.committed
    assert not fake_conn.rolled_back
    assert "DELETE FROM hrc_sessions" in store["sql"]
    assert store["params"] == (42,)


def test_delete_session_not_found_returns_404():
    app = _make_app()
    client = TestClient(app)
    store: dict = {"found": False}
    fake_conn = _DeleteConn(store)
    with patch("app.routers.hrc.get_conn", return_value=fake_conn):
        r = client.delete("/api/hrc/sessions/999")
    assert r.status_code == 404
    assert fake_conn.rolled_back
    assert not fake_conn.committed


def test_delete_session_no_auth():
    app = FastAPI()
    app.include_router(hrc_router)
    # SEM override
    client = TestClient(app)
    r = client.delete("/api/hrc/sessions/1")
    assert r.status_code == 401
