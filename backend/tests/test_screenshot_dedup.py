"""Dedup server-side por file_hash em POST /api/screenshots (gold images).
Re-importar a MESMA imagem não cria entry novo nem re-dispara Vision."""
from unittest.mock import patch, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.screenshot import router as ss_router
from app.auth import require_auth


def _client():
    app = FastAPI()
    app.include_router(ss_router)
    app.dependency_overrides[require_auth] = lambda: {"id": 1, "email": "t@t"}
    return TestClient(app)


def test_dedup_hit_nao_cria_entry_nem_vision():
    """file_hash já existe → status='duplicate', devolve o entry existente, NÃO
    abre get_conn (sem INSERT) nem agenda Vision."""
    client = _client()
    with patch("app.routers.screenshot.query", return_value=[{"id": 77}]) as q, \
         patch("app.routers.screenshot.get_conn") as gc, \
         patch("app.routers.screenshot._run_vision_for_entry") as vis:
        r = client.post("/api/screenshots",
                        files={"file": ("hand_#5754140681.png", b"GOLDBYTES", "image/png")})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "duplicate"
    assert body["entry_id"] == 77
    gc.assert_not_called()        # nenhum INSERT
    vis.assert_not_called()       # nenhuma Vision agendada
    # a SELECT de dedup correu por file_hash
    assert any("file_hash" in (c.args[0] if c.args else "") for c in q.call_args_list)


def test_upload_fresco_guarda_file_hash_e_enfileira():
    """Sem dedup hit → cria entry com file_hash no raw_json e responde 'queued'."""
    client = _client()
    captured = {}

    class _Cur:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, sql, params=None): captured["sql"] = sql; captured["params"] = params
        def fetchone(self): return {"id": 99}

    conn = MagicMock(); conn.cursor.return_value = _Cur()
    with patch("app.routers.screenshot.query", return_value=[]), \
         patch("app.routers.screenshot.get_conn", return_value=conn), \
         patch("app.routers.screenshot._run_vision_for_entry"), \
         patch("app.routers.screenshot._compress_image", return_value=("Yg==", "image/jpeg")):
        r = client.post("/api/screenshots",
                        files={"file": ("hand_#5754140681.png", b"GOLDBYTES", "image/png")})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "queued"
    # o INSERT levou file_hash no raw_json
    import json
    params = captured["params"]
    raw_json = next((p for p in params if isinstance(p, str) and "file_hash" in p), None)
    assert raw_json is not None, "INSERT não incluiu file_hash no raw_json"
    assert json.loads(raw_json).get("file_hash"), "file_hash vazio no raw_json"


def test_dois_uploads_iguais_segundo_e_duplicate():
    """Simula 2 importações da mesma imagem: 1ª insere (query=[]), 2ª vê o
    file_hash (query=[id]) → 'duplicate'. (O hash é determinístico do conteúdo.)"""
    client = _client()
    # 1ª: sem dedup → insere
    class _Cur:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, *a, **k): pass
        def fetchone(self): return {"id": 5}
    conn = MagicMock(); conn.cursor.return_value = _Cur()
    with patch("app.routers.screenshot.query", return_value=[]), \
         patch("app.routers.screenshot.get_conn", return_value=conn), \
         patch("app.routers.screenshot._run_vision_for_entry"), \
         patch("app.routers.screenshot._compress_image", return_value=("Yg==", "image/jpeg")):
        r1 = client.post("/api/screenshots", files={"file": ("h_#1.png", b"SAME", "image/png")})
    assert r1.json()["status"] == "queued"
    # 2ª: o mesmo conteúdo já existe → dedup
    with patch("app.routers.screenshot.query", return_value=[{"id": 5}]), \
         patch("app.routers.screenshot.get_conn") as gc, \
         patch("app.routers.screenshot._run_vision_for_entry") as vis:
        r2 = client.post("/api/screenshots", files={"file": ("h_#1.png", b"SAME", "image/png")})
    assert r2.json()["status"] == "duplicate" and r2.json()["entry_id"] == 5
    gc.assert_not_called(); vis.assert_not_called()
