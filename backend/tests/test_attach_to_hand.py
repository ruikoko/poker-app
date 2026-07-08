"""OBRA 2b — /table-ss/attach-to-hand: compõe Vision(persist) + força link à mão
escolhida. Testa a WIRING (mock dos 2 primitivos já testados noutro lado)."""
import asyncio

from app.routers import table_ss as ts


class _FakeUpload:
    filename = "gold.png"

    async def read(self):
        return b"IMGBYTES"


def test_attach_to_hand_composes_process_then_link(monkeypatch):
    calls = {}

    async def fake_process(content, filename, *, source):
        calls["process"] = {"len": len(content), "filename": filename, "source": source}
        return {}

    def fake_query(sql, params=None):
        calls["query"] = (sql, params)
        return [{"id": 77}]

    def fake_link(ss_id, hand_id):
        calls["link"] = (ss_id, hand_id)
        return {"result": "success", "matched_hand_id": hand_id}

    monkeypatch.setattr(ts, "_process_table_ss", fake_process)
    monkeypatch.setattr(ts, "query", fake_query)
    monkeypatch.setattr(ts, "_manual_link_ss", fake_link)

    out = asyncio.run(ts.attach_ss_to_hand(file=_FakeUpload(), hand_id="GG-6083716159",
                                           filename=None))
    # 1) Vision + persist, com source dedicado
    assert calls["process"]["source"] == "manual_attach"
    assert calls["process"]["filename"] == "gold.png"
    # 2) força o link à mão ESCOLHIDA (ss_id vindo do lookup por file_hash)
    assert calls["link"] == (77, "GG-6083716159")
    # 3) devolve o url da imagem p/ a miniatura aparecer no lado do conflito
    assert out["ss_id"] == 77 and out["image_url"] == "/api/table-ss/image/77"
    assert out["result"] == "success"


def test_attach_to_hand_404_when_hand_missing(monkeypatch):
    from fastapi import HTTPException
    import pytest

    async def fake_process(content, filename, *, source):
        return {}

    monkeypatch.setattr(ts, "_process_table_ss", fake_process)
    monkeypatch.setattr(ts, "query", lambda *a, **k: [{"id": 5}])

    def fake_link(ss_id, hand_id):
        raise ValueError("hand_not_found")

    monkeypatch.setattr(ts, "_manual_link_ss", fake_link)
    with pytest.raises(HTTPException) as ei:
        asyncio.run(ts.attach_ss_to_hand(file=_FakeUpload(), hand_id="GG-none", filename=None))
    assert ei.value.status_code == 404
