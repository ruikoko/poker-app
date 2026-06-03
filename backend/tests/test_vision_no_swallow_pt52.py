"""pt52 — Vision falhada NÃO marca vision_done='true' (deixa retry-able).

Antes (pt51): _extract_hand_data_from_image devolvia None em 429/excepção e o
worker marcava vision_done=true com TM=None → 250 entries presas. O fix faz
return cedo sem tocar na BD.
"""
import asyncio
from unittest.mock import patch

from app.routers.screenshot import _run_vision_for_entry


def test_vision_failure_does_not_touch_db_nor_mark_done():
    """_extract devolve None (falha) → o worker sai sem escrever na BD."""
    with patch("app.routers.screenshot._extract_hand_data_from_image", return_value=None), \
         patch("app.routers.screenshot.get_conn") as mgc, \
         patch("app.routers.screenshot.query") as mq:
        asyncio.run(_run_vision_for_entry(
            entry_id=1, content=b"\x89PNG", mime_type="image/png",
            tm_number=None, file_meta={}, img_b64="Zm9v"))
    # Sem db_update → get_conn nunca chamado (não marcou vision_done) e sem match.
    mgc.assert_not_called()
    mq.assert_not_called()


def test_vision_success_marks_done():
    """Vision OK (texto válido, sem TM) → marca vision_done=true (db_update corre)."""
    from unittest.mock import MagicMock
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = MagicMock()
    with patch("app.routers.screenshot._extract_hand_data_from_image", return_value="TM: None\nPLAYERS:"), \
         patch("app.routers.screenshot._parse_vision_response", return_value={"tm": None, "players_list": []}), \
         patch("app.routers.screenshot._compress_image", return_value=("Yg==", "image/jpeg")), \
         patch("app.routers.screenshot.get_conn", return_value=conn):
        asyncio.run(_run_vision_for_entry(
            entry_id=2, content=b"\x89PNG", mime_type="image/png",
            tm_number=None, file_meta={}, img_b64="Zm9v"))
    # db_update correu → UPDATE entries com vision_done=true.
    sqls = " ".join(" ".join(c[0][0].split()) for c in conn.cursor.return_value.__enter__.return_value.execute.call_args_list)
    assert "UPDATE entries SET raw_json" in sqls
    conn.commit.assert_called()
