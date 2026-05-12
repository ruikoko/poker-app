"""Tests para POST /api/queue/hrc/results — G2."""
import io
import json
import zipfile
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.queue import router as queue_router
from app.auth import require_auth_or_api_key


def _make_meta_zip(meta: dict | None = None) -> bytes:
    """Zip in-memory com meta.json no root. Helper dos tests."""
    if meta is None:
        meta = {"rank": 17, "players_left": 8, "stage": "FT", "ci": 0.0023}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("meta.json", json.dumps(meta))
    return buf.getvalue()


def _make_app():
    app = FastAPI()
    app.include_router(queue_router)
    app.dependency_overrides[require_auth_or_api_key] = (
        lambda: {"id": None, "email": None, "auth_type": "api_key"}
    )
    return app


# ── 1. Sem auth → 401 ──────────────────────────────────────────────────────

def test_no_auth_returns_401():
    app = FastAPI()
    app.include_router(queue_router)
    # SEM override de require_auth_or_api_key
    client = TestClient(app)
    r = client.post("/api/queue/hrc/results?hand_id=GG-1&status=done")
    assert r.status_code == 401


# ── 2. Done com zip sintético → 200 inserted ──────────────────────────────

def test_bearer_done_with_synthetic_zip():
    app = _make_app()
    client = TestClient(app)
    zip_bytes = _make_meta_zip()
    with patch("app.routers.queue.query", return_value=[{"id": 99}]), \
         patch(
             "app.routers.queue.upsert_hrc_job_result",
             return_value={"id": 1, "inserted": True},
         ) as up:
        r = client.post(
            "/api/queue/hrc/results?hand_id=GG-281416137&status=done",
            files={"file": ("result.zip", zip_bytes, "application/zip")},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["hand_db_id"] == 99
    assert body["status"] == "done"
    assert body["action"] == "inserted"
    assert body["meta"]["rank"] == 17
    assert body["meta"]["hand_id"] == "GG-281416137"
    assert body["meta"]["received_from"] == "watcher"
    up.assert_called_once()


# ── 3. hand_id não existe → 404 ────────────────────────────────────────────

def test_hand_id_not_found_returns_404():
    app = _make_app()
    client = TestClient(app)
    with patch("app.routers.queue.query", return_value=[]):
        r = client.post(
            "/api/queue/hrc/results?hand_id=GG-UNKNOWN&status=done",
            files={"file": ("result.zip", _make_meta_zip(), "application/zip")},
        )
    assert r.status_code == 404
    assert "não encontrado" in r.json()["detail"]


# ── 4. status inválido → 400 ───────────────────────────────────────────────

def test_invalid_status_returns_400():
    app = _make_app()
    client = TestClient(app)
    r = client.post("/api/queue/hrc/results?hand_id=GG-1&status=running")
    assert r.status_code == 400
    assert "status inválido" in r.json()["detail"]


# ── 5. status=failed sem error → 400 ──────────────────────────────────────

def test_failed_requires_error_text():
    app = _make_app()
    client = TestClient(app)
    r = client.post("/api/queue/hrc/results?hand_id=GG-1&status=failed")
    assert r.status_code == 400
    assert "error obrigatório" in r.json()["detail"]


# ── 6. status=failed com error → 200, sem file ─────────────────────────────

def test_failed_with_error_no_file():
    app = _make_app()
    client = TestClient(app)
    with patch("app.routers.queue.query", return_value=[{"id": 42}]), \
         patch(
             "app.routers.queue.upsert_hrc_job_result",
             return_value={"id": 5, "inserted": True},
         ):
        r = client.post(
            "/api/queue/hrc/results"
            "?hand_id=GG-42&status=failed&error=export_timeout"
        )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "failed"
    assert body["meta"]["failure_reported_by"] == "watcher"


# ── 7. status=done sem file → 400 ─────────────────────────────────────────

def test_done_without_file_returns_400():
    app = _make_app()
    client = TestClient(app)
    with patch("app.routers.queue.query", return_value=[{"id": 1}]):
        r = client.post("/api/queue/hrc/results?hand_id=GG-1&status=done")
    assert r.status_code == 400
    assert "file obrigatório" in r.json()["detail"]


# ── 8. file não-zip → 400 ──────────────────────────────────────────────────

def test_invalid_zip_returns_400():
    app = _make_app()
    client = TestClient(app)
    with patch("app.routers.queue.query", return_value=[{"id": 1}]):
        r = client.post(
            "/api/queue/hrc/results?hand_id=GG-1&status=done",
            files={"file": ("trash.zip", b"not a zip", "application/zip")},
        )
    assert r.status_code == 400
    assert "invalid zip" in r.json()["detail"]


# ── 9. zip sem meta.json → 400 ────────────────────────────────────────────

def test_zip_missing_meta_returns_400():
    app = _make_app()
    client = TestClient(app)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("other.txt", "no meta here")
    with patch("app.routers.queue.query", return_value=[{"id": 1}]):
        r = client.post(
            "/api/queue/hrc/results?hand_id=GG-1&status=done",
            files={"file": ("r.zip", buf.getvalue(), "application/zip")},
        )
    assert r.status_code == 400
    assert "meta.json missing" in r.json()["detail"]


# ── 10. UPSERT idempotente (action=updated) + submitted_at preservado ─────

def test_upsert_overwrites_previous_preserving_submitted_at():
    """2ª submissão da mesma mão devolve action=updated; SQL emitido
    NÃO inclui submitted_at no DO UPDATE SET (D-G2-EXTRA-2)."""
    app = _make_app()
    client = TestClient(app)
    zip_bytes = _make_meta_zip()

    captured_sql: list[str] = []

    def fake_exec(sql, params):
        captured_sql.append(sql)
        return {"id": 1, "inserted": (len(captured_sql) == 1)}

    with patch("app.routers.queue.query", return_value=[{"id": 1}]), \
         patch("app.services.hrc_jobs.execute_returning", side_effect=fake_exec):
        r1 = client.post(
            "/api/queue/hrc/results?hand_id=GG-1&status=done",
            files={"file": ("r.zip", zip_bytes, "application/zip")},
        )
        r2 = client.post(
            "/api/queue/hrc/results?hand_id=GG-1&status=done",
            files={"file": ("r.zip", zip_bytes, "application/zip")},
        )

    assert r1.json()["action"] == "inserted"
    assert r2.json()["action"] == "updated"

    # SQL captado: DO UPDATE SET clause NÃO pode mexer em submitted_at
    assert len(captured_sql) == 2
    for sql in captured_sql:
        assert "ON CONFLICT (hand_db_id) DO UPDATE SET" in sql
        update_clause = sql.split("DO UPDATE SET")[1].split("RETURNING")[0]
        assert "submitted_at" not in update_clause, (
            "submitted_at NÃO deve estar em DO UPDATE SET (preserva 1ª submissão)"
        )


# ── 11. Bonus: file >50MB (cap) → 413 ─────────────────────────────────────

def test_oversized_returns_413():
    app = _make_app()
    client = TestClient(app)
    with patch("app.routers.queue._MAX_RESULT_ZIP_BYTES", 100), \
         patch("app.routers.queue.query", return_value=[{"id": 1}]):
        r = client.post(
            "/api/queue/hrc/results?hand_id=GG-1&status=done",
            files={"file": ("big.zip", b"x" * 200, "application/zip")},
        )
    assert r.status_code == 413
    assert "excede" in r.json()["detail"]
