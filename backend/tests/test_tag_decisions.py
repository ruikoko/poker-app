"""SELO DA TAG (`tag_decisions`) — prova exigida pelo Rui:
- O Rui tira uma tag → NÃO volta depois do reprocessamento (testado contra os 10 writers:
  todos embrulham o RHS em apply_tag_decisions, cuja semântica é o apply_decisions_py).
- Uma tag legítima nova continua a entrar.
- O HM3 não é afectado (o selo só toca discord_tags).
- Lote com falha honesta (Peça 1): reporta quais falharam e porquê; nunca sucesso em bloco.
"""
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.services import tag_decisions as td
from app.routers import tag_decisions as tdr


# ── 1. Semântica pura: (base ∪ adds) − removes, removes por último, latest-wins ──
def test_apply_removes_win_over_base():
    # o writer re-acrescentou 'pos-pko' (base), mas há um remove selado → NÃO volta.
    out = td.apply_decisions_py(["pos-pko", "icm"], [{"tag": "pos-pko", "action": "remove", "id": 5}])
    assert out == ["icm"]


def test_apply_add_enters_even_without_capture():
    # mover A→B: B não tem captura com essa folder-tag; o add é a única fonte.
    out = td.apply_decisions_py([], [{"tag": "nota", "action": "add", "id": 1}])
    assert out == ["nota"]


def test_apply_latest_wins_remove_then_readd():
    # remove (id 1) depois add (id 2) → a mais recente manda: a tag fica.
    decs = [{"tag": "pos-pko", "action": "remove", "id": 1},
            {"tag": "pos-pko", "action": "add", "id": 2}]
    assert td.apply_decisions_py(["pos-pko"], decs) == ["pos-pko"]
    # e ao contrário: add (id 1) depois remove (id 2) → sai.
    decs2 = [{"tag": "x", "action": "add", "id": 1}, {"tag": "x", "action": "remove", "id": 2}]
    assert td.apply_decisions_py(["x"], decs2) == []


def test_apply_order_stable_and_dedups():
    out = td.apply_decisions_py(["a", "b", "a"], [{"tag": "c", "action": "add", "id": 1}])
    assert out == ["a", "b", "c"]


def test_apply_no_decisions_is_identity():
    assert td.apply_decisions_py(["pos-pko", "nota"], []) == ["pos-pko", "nota"]


# ── 2. Prova de roteamento: os 10 writers de discord_tags passam por apply_tag_decisions ──
_BACKEND = Path(__file__).resolve().parent.parent / "app"
# (ficheiro, nº de writers de discord_tags que TÊM de estar embrulhados)
_WRITERS = {
    "routers/table_ss.py": 1,
    "routers/capture_triage.py": 1,
    "routers/screenshot.py": 2,
    "discord_bot.py": 1,
    "services/hand_service.py": 2,
    "services/ft_boundary.py": 1,
    "routers/gg_health.py": 0,   # gg_health passa por seal_and_recompute (não wrap directo)
}


def test_all_appending_writers_wrapped():
    """Cada `discord_tags =` que ESCREVE (não filtro WHERE, não SELECT) tem de invocar
    apply_tag_decisions no mesmo statement — senão o reprocessamento ressuscita a tag tirada."""
    for rel, expected in _WRITERS.items():
        src = (_BACKEND / rel).read_text(encoding="utf-8")
        # writes = 'discord_tags =' seguido (em breve) de apply_tag_decisions no mesmo statement.
        wrapped = len(re.findall(r"discord_tags\s*=\s*apply_tag_decisions\(hand_id", src))
        assert wrapped == expected, f"{rel}: esperava {expected} writes embrulhados, achei {wrapped}"


def test_gg_health_routes_through_seal():
    # gg_health /tag e /untag selam decisões (add/remove) em vez de escrever o array cru.
    src = (_BACKEND / "routers/gg_health.py").read_text(encoding="utf-8")
    assert "seal_and_recompute(cur, r[\"hand_id\"]" in src
    assert 'UPDATE hands SET discord_tags=%s WHERE id=%s' not in src   # o write cru foi-se


# ── 3. seal_and_recompute: INSERT do rasto + UPDATE só em discord_tags (HM3 intacta) ──
def _cur_with_ids(ids, discord_tags=None):
    """Cursor mock: o SELECT de existência (fetchall) devolve as rows dadas; a leitura de
    discord_tags controla a deteção de 'já lá está' no add."""
    cur = MagicMock()
    cur.fetchall.return_value = [{"id": i, "discord_tags": discord_tags} for i in ids]
    return cur


def test_seal_and_recompute_inserts_rasto_and_recomputes():
    cur = _cur_with_ids([7])
    affected = td.seal_and_recompute(cur, "GG-1", "pos-pko", "remove",
                                     actor="rui@x", origin=td.ORIGIN_BATCH)
    assert affected == [7]
    sqls = " ".join(c.args[0] for c in cur.execute.call_args_list)
    assert "INSERT INTO tag_decisions" in sqls                 # rasto append-only
    assert "apply_tag_decisions(hand_id" in sqls               # recompute
    assert "hm3_tags" not in sqls                              # HM3 NÃO é tocada


def test_seal_rejects_bad_action():
    with pytest.raises(ValueError):
        td.seal_and_recompute(MagicMock(), "GG-1", "t", "banir", actor="x", origin="o")


# ── 4. Endpoint remove (botão da página da mão) ──────────────────────────────
def test_remove_endpoint_seals_and_returns():
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = _cur_with_ids([3])
    with patch.object(tdr, "get_conn", return_value=conn), \
         patch.object(tdr, "seal_and_recompute", return_value=[3]) as seal, \
         patch.object(tdr, "_refresh_villains") as vr:
        res = tdr.remove_tag({"hand_id": "GG-1", "tag": "pos-pko"}, current_user={"email": "rui@x"})
    assert res == {"status": "removed", "hand_id": "GG-1", "tag": "pos-pko"}
    assert seal.call_args.args[1:] == ("GG-1", "pos-pko", "remove")
    vr.assert_called_once_with([3])
    conn.commit.assert_called_once()


def test_remove_endpoint_hand_not_found_400():
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = _cur_with_ids([])   # 0 mãos afectadas
    with patch.object(tdr, "get_conn", return_value=conn), \
         patch.object(tdr, "seal_and_recompute", return_value=[]):
        with pytest.raises(HTTPException) as ei:
            tdr.remove_tag({"hand_id": "GG-NADA", "tag": "pos-pko"}, current_user={})
    assert ei.value.status_code == 400
    conn.rollback.assert_called_once()


def test_remove_endpoint_missing_fields_400():
    with patch.object(tdr, "get_conn", return_value=MagicMock()):
        with pytest.raises(HTTPException):
            tdr.remove_tag({"hand_id": "GG-1"}, current_user={})       # sem tag


# ── 5. add HONESTO: "já lá está" não escreve em duplicado nem finge ───────────
def test_apply_one_add_already_present_is_noop():
    cur = _cur_with_ids([5], discord_tags=["nota", "pos-pko"])
    with patch.object(tdr, "seal_and_recompute") as seal:
        res = tdr._apply_one(cur, "GG-1", "nota", "add", actor="x", origin="o")
    assert res["already_present"] is True and res["changed"] is False
    seal.assert_not_called()                    # não escreve em duplicado


def test_apply_one_add_absent_seals():
    cur = _cur_with_ids([5], discord_tags=["nota"])
    with patch.object(tdr, "seal_and_recompute", return_value=[5]) as seal:
        res = tdr._apply_one(cur, "GG-1", "pos-pko", "add", actor="x", origin="o")
    assert res["already_present"] is False and res["changed"] is True
    seal.assert_called_once()


def test_apply_one_remove_seals_even_if_absent():
    # o remove sela SEMPRE (mesmo ausente agora) → impede o writer de repor no reprocessamento.
    cur = _cur_with_ids([5], discord_tags=[])
    with patch.object(tdr, "seal_and_recompute", return_value=[5]) as seal:
        res = tdr._apply_one(cur, "GG-1", "pos-pko", "remove", actor="x", origin="o")
    assert res["changed"] is True
    seal.assert_called_once()


def test_apply_one_hand_not_found():
    with pytest.raises(ValueError):
        tdr._apply_one(_cur_with_ids([]), "GG-NADA", "nota", "add", actor="x", origin="o")


def test_add_endpoint_already_present_honest():
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = _cur_with_ids([3], discord_tags=["nota"])
    with patch.object(tdr, "get_conn", return_value=conn), \
         patch.object(tdr, "seal_and_recompute") as seal, \
         patch.object(tdr, "_refresh_villains") as vr:
        res = tdr.add_tag({"hand_id": "GG-1", "tag": "nota"}, current_user={})
    assert res["status"] == "already_present" and res["already_present"] is True
    seal.assert_not_called()
    vr.assert_not_called()


def test_add_endpoint_adds_when_absent():
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = _cur_with_ids([3], discord_tags=["nota"])
    with patch.object(tdr, "get_conn", return_value=conn), \
         patch.object(tdr, "seal_and_recompute", return_value=[3]) as seal, \
         patch.object(tdr, "_refresh_villains"):
        res = tdr.add_tag({"hand_id": "GG-1", "tag": "pos-pko"}, current_user={"email": "rui@x"})
    assert res["status"] == "added" and res["already_present"] is False
    assert seal.call_args.args[1:] == ("GG-1", "pos-pko", "add")


# ── 6. Lote: FALHA HONESTA + MOVER (tirar de A, pôr em B) ─────────────────────
def test_batch_reports_partial_failure_honestly():
    # 3 itens: 2 ok, 1 falha (mão inexistente → ValueError). Reporta a verdade.
    def fake_apply(cur, hand_id, tag, action, **kw):
        if hand_id == "GG-BAD":
            raise ValueError(f"mão {hand_id} não encontrada")
        return {"hand_id": hand_id, "tag": tag, "action": action,
                "changed": True, "already_present": False, "hand_db_ids": [1]}
    conn = MagicMock()
    with patch.object(tdr, "get_conn", return_value=conn), \
         patch.object(tdr, "_apply_one", side_effect=fake_apply), \
         patch.object(tdr, "_refresh_villains"):
        res = tdr.batch({"items": [
            {"hand_id": "GG-1", "tag": "pos-pko", "action": "remove"},
            {"hand_id": "GG-BAD", "tag": "pos-pko", "action": "remove"},
            {"hand_id": "GG-2", "tag": "nota", "action": "remove"},
        ]}, current_user={"email": "rui@x"})
    assert res["n_ok"] == 2 and res["n_failed"] == 1
    bad = [r for r in res["results"] if not r["ok"]]
    assert len(bad) == 1 and bad[0]["hand_id"] == "GG-BAD" and "não encontrada" in bad[0]["error"]
    assert conn.commit.call_count == 2         # o falho não impede os outros


def test_batch_move_remove_from_a_add_to_b():
    # O caso real: tirar 'nota' da A + pô-la na B (dona certa), num só lote.
    def fake_apply(cur, hand_id, tag, action, **kw):
        return {"hand_id": hand_id, "tag": tag, "action": action,
                "changed": True, "already_present": False, "hand_db_ids": [1]}
    conn = MagicMock()
    with patch.object(tdr, "get_conn", return_value=conn), \
         patch.object(tdr, "_apply_one", side_effect=fake_apply), \
         patch.object(tdr, "_refresh_villains"):
        res = tdr.batch({"items": [
            {"hand_id": "GG-A", "tag": "nota", "action": "remove"},
            {"hand_id": "GG-B", "tag": "nota", "action": "add"},
        ]}, current_user={})
    assert res["n_ok"] == 2 and res["n_failed"] == 0
    got = {(r["hand_id"], r["action"]) for r in res["results"]}
    assert got == {("GG-A", "remove"), ("GG-B", "add")}


def test_batch_empty_400():
    with pytest.raises(HTTPException):
        tdr.batch({"items": []}, current_user={})


# ── 6. Preview: custo antes de correr (read-only) ────────────────────────────
def test_preview_cost_read_only():
    rows = [{"hand_id": "GG-1", "discord_tags": ["pos-pko", "nota"]},
            {"hand_id": "GG-2", "discord_tags": ["icm"]}]
    with patch.object(tdr, "query", return_value=rows):
        res = tdr.preview_batch({"items": [
            {"hand_id": "GG-1", "tag": "pos-pko", "action": "remove"},   # sai (tem)
            {"hand_id": "GG-2", "tag": "pos-pko", "action": "remove"},   # não muda (não tem)
            {"hand_id": "GG-NADA", "tag": "x", "action": "remove"},      # não existe
        ]}, current_user={})
    assert res["n_hands"] == 2 and res["n_ops"] == 1 and res["n_items"] == 3
    by = {i["hand_id"]: i for i in res["items"]}
    assert by["GG-1"]["will_change"] is True
    assert by["GG-2"]["will_change"] is False
    assert by["GG-NADA"]["exists"] is False and by["GG-NADA"]["reason"] == "mão não encontrada"
