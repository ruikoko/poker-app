"""Tests das Ações da Saúde GG (#GG-HEALTH-ACTIONS): tagar / linkar / swap-review."""
import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException

from app.routers import gg_health, table_ss


# ── Ação 1 — tagar ───────────────────────────────────────────────────────────
def test_tag_format_conflict_detection():
    assert gg_health._tag_format_conflict("icm-pko", "Vanilla") == "pko_tag_on_vanilla"
    assert gg_health._tag_format_conflict("icm", "PKO") == "vanilla_tag_on_bounty"
    assert gg_health._tag_format_conflict("pos-nko", "Mystery KO") == "vanilla_tag_on_bounty"
    assert gg_health._tag_format_conflict("icm-pko", "PKO") is None      # consistente
    assert gg_health._tag_format_conflict("nota", "Vanilla") is None     # neutra


def test_tag_needs_confirm_on_format_conflict_no_write():
    rows = [{"id": 1, "hand_id": "GG-1", "discord_tags": [], "tournament_format": "Vanilla"}]
    with patch.object(gg_health, "query", return_value=rows), \
         patch.object(gg_health, "get_conn") as mconn:
        res = gg_health.gg_health_tag({"hand_ids": ["GG-1"], "tag": "icm-pko"})
    assert res["needs_confirm"] is True and res["applied"] == 0
    mconn.assert_not_called()                 # não escreve sem confirm


def test_tag_idempotent_when_already_present():
    rows = [{"id": 1, "hand_id": "GG-1", "discord_tags": ["icm-pko"], "tournament_format": "PKO"}]
    with patch.object(gg_health, "query", return_value=rows), \
         patch.object(gg_health, "get_conn", return_value=MagicMock()), \
         patch.object(gg_health, "seal_and_recompute") as seal:
        res = gg_health.gg_health_tag({"hand_ids": ["GG-1"], "tag": "icm-pko"})
    assert res["applied"] == 0                 # já tem → no-op
    seal.assert_not_called()                   # nada a selar


def test_tag_applies_new_tag_seals_add():
    # SELO DA TAG: o array final é computado na BD por apply_tag_decisions — o teste
    # verifica que se SELOU a decisão (add) da tag certa, não o array (que a BD calcula).
    rows = [{"id": 1, "hand_id": "GG-1", "discord_tags": [], "tournament_format": "PKO"}]
    with patch.object(gg_health, "query", return_value=rows), \
         patch.object(gg_health, "get_conn", return_value=MagicMock()), \
         patch.object(gg_health, "seal_and_recompute", return_value=[1]) as seal, \
         patch("app.services.villain_rules.apply_villain_rules"):
        res = gg_health.gg_health_tag({"hand_ids": ["GG-1"], "tag": "icm-pko"})
    assert res["applied"] == 1 and res["tags"] == ["icm-pko"]
    args, kwargs = seal.call_args
    assert args[1:] == ("GG-1", "icm-pko", "add")   # (cur, hand_id, tag, action)


def test_tag_invalid_rejected():
    with pytest.raises(HTTPException):
        gg_health.gg_health_tag({"hand_ids": ["GG-1"], "tag": "xpto-nonsense"})


def test_tag_multi_appends_all_selected():
    # `tags` (lista): SELA as DUAS que faltam (a 'nota' que já lá está não é re-selada).
    conn = MagicMock()
    rows = [{"id": 1, "hand_id": "GG-1", "discord_tags": ["nota"], "tournament_format": "PKO"}]
    with patch.object(gg_health, "query", return_value=rows), \
         patch.object(gg_health, "get_conn", return_value=conn), \
         patch.object(gg_health, "seal_and_recompute", return_value=[1]) as seal, \
         patch("app.services.villain_rules.apply_villain_rules"):
        res = gg_health.gg_health_tag({"hand_ids": ["GG-1"], "tags": ["icm", "pos-pko"], "confirm": True})
    assert res["applied"] == 2 and res["hands"] == 1 and res["tags"] == ["icm", "pos-pko"]
    sealed = [(c.args[1], c.args[2], c.args[3]) for c in seal.call_args_list]
    assert sealed == [("GG-1", "icm", "add"), ("GG-1", "pos-pko", "add")]  # só as novas


def test_tag_multi_idempotent_skips_existing():
    # uma das duas já lá está → só sela a que falta.
    conn = MagicMock()
    rows = [{"id": 1, "hand_id": "GG-1", "discord_tags": ["icm"], "tournament_format": "PKO"}]
    with patch.object(gg_health, "query", return_value=rows), \
         patch.object(gg_health, "get_conn", return_value=conn), \
         patch.object(gg_health, "seal_and_recompute", return_value=[1]) as seal, \
         patch("app.services.villain_rules.apply_villain_rules"):
        res = gg_health.gg_health_tag({"hand_ids": ["GG-1"], "tags": ["icm", "nota"], "confirm": True})
    assert res["applied"] == 1 and res["hands"] == 1               # só 'nota' era nova
    sealed = [(c.args[1], c.args[2], c.args[3]) for c in seal.call_args_list]
    assert sealed == [("GG-1", "nota", "add")]


# ── detetor de rotação: truncação ≠ troca ────────────────────────────────────
def test_same_name_trunc_tolera_truncacao():
    f = gg_health._same_name_trunc
    # truncação da Vision = MESMO nome (não é troca de vizinho)
    assert f("Tobias Schwecht", "Tobias Schw..") is True
    assert f("Tobias Schw..", "Tobias Schwecht") is True
    assert f("R Romanovsk", "R Romanovsky") is True
    assert f("ciupy1234", "ciupy1234") is True
    # nomes GENUINAMENTE diferentes = potencial troca
    assert f("msxiter", "ciupy1234") is False
    assert f("mufasa", "R Romanovsk") is False
    assert f("166X", "Pedro Borges") is False
    # prefixo curto (<4 chars) NÃO casa por acaso ('Ann' prefixo de 'Anna' mas len 3)
    assert f("Ann", "Anna") is False
    assert f(None, "x") is False and f("", "y") is False


# ── untag — remover tag espúria (oposto de tagar) ────────────────────────────
def test_untag_removes_selected_tag():
    # SELO DA TAG: sela um 'remove' da forma EXACTA gravada — a BD recompõe o array.
    conn = MagicMock()
    rows = [{"id": 1, "hand_id": "GG-1", "discord_tags": ["nota", "pos-pko"]}]
    with patch.object(gg_health, "query", return_value=rows), \
         patch.object(gg_health, "get_conn", return_value=conn), \
         patch.object(gg_health, "seal_and_recompute", return_value=[1]) as seal, \
         patch("app.services.villain_rules.apply_villain_rules"):
        res = gg_health.gg_health_untag({"hand_ids": ["GG-1"], "tag": "pos-pko"})
    assert res["removed"] == 1 and res["hands"] == 1
    args = seal.call_args.args
    assert args[1:] == ("GG-1", "pos-pko", "remove")    # só 'pos-pko' selada p/ remoção


def test_untag_idempotent_when_absent():
    conn = MagicMock()
    rows = [{"id": 1, "hand_id": "GG-1", "discord_tags": ["nota"]}]
    with patch.object(gg_health, "query", return_value=rows), \
         patch.object(gg_health, "get_conn", return_value=conn), \
         patch.object(gg_health, "seal_and_recompute") as seal:
        res = gg_health.gg_health_untag({"hand_ids": ["GG-1"], "tag": "pos-pko"})
    assert res["removed"] == 0 and res["hands"] == 0    # não tinha → no-op
    seal.assert_not_called()
    conn.cursor.assert_not_called()


def test_untag_invalid_rejected():
    with pytest.raises(HTTPException):
        gg_health.gg_health_untag({"hand_ids": ["GG-1"], "tag": "xpto-nonsense"})


# ── Ação 2 — link manual (Gold manda vive dentro do _deanon_after_match) ─────
def test_manual_link_success_deanons_and_tags():
    log = [{"id": 5, "site": "GGPoker", "vision_json": {"seats": [{"nick": "a"}]},
            "folder_tag": "pos-pko", "result": "no_match_to_hand", "matched_hand_id": None}]
    hand = [{"id": 42, "hand_id": "GG-9", "tournament_number": "T1"}]

    def q(sql, params=None):
        return log if "table_ss_processing_log" in sql else (hand if "FROM hands" in sql else [])

    with patch.object(table_ss, "query", side_effect=q), \
         patch.object(table_ss, "_persist_table_ss_match") as mp, \
         patch.object(table_ss, "_deanon_after_match") as md, \
         patch.object(table_ss, "_apply_folder_tag_to_hand") as mt:
        res = table_ss._manual_link_ss(5, "GG-9")
    assert res == {"result": "success", "matched_hand_id": "GG-9"}
    mp.assert_called_once()
    md.assert_called_once_with(42, {"seats": [{"nick": "a"}]})   # deanon (com guarda Gold)
    mt.assert_called_once()


def test_manual_link_unlink_does_not_deanon():
    log = [{"id": 5, "site": "GGPoker", "vision_json": {}, "folder_tag": None,
            "result": "success", "matched_hand_id": "GG-9"}]
    with patch.object(table_ss, "query",
                      side_effect=lambda s, p=None: log if "processing_log" in s else []), \
         patch.object(table_ss, "_persist_table_ss_match"), \
         patch.object(table_ss, "_deanon_after_match") as md:
        res = table_ss._manual_link_ss(5, None)
    assert res["result"] == "no_match_to_hand"
    md.assert_not_called()


def test_manual_link_hand_not_found_raises():
    log = [{"id": 5, "site": "GGPoker", "vision_json": {}, "folder_tag": None,
            "result": "x", "matched_hand_id": None}]
    with patch.object(table_ss, "query",
                      side_effect=lambda s, p=None: log if "processing_log" in s else []):
        with pytest.raises(ValueError):
            table_ss._manual_link_ss(5, "GG-inexistente")


# ── Ação 3 — swap-review ─────────────────────────────────────────────────────
_TRUNC = "GGPoker-Speed Racer $108 - Table 8_!)@(#_$&%^_61-20260626204636-117.png"
_FULL = "GGPoker-Daily Hyper $50 - Table 8_!)@(#_$&%^_6083293101-20260616171101-4.png"


def test_swap_accept_truncated_number_422():
    log = [{"id": 5, "original_filename": _TRUNC}]
    with patch.object(table_ss, "query", return_value=log):
        with pytest.raises(HTTPException) as e:
            table_ss.swap_review_table_ss(5, {"decision": "accept"})
    assert e.value.status_code == 422


def test_swap_accept_full_number_moves_and_marks():
    log = [{"id": 5, "original_filename": _FULL}]
    with patch.object(table_ss, "query", return_value=log), \
         patch.object(table_ss, "_manual_link_ss",
                      return_value={"result": "success", "matched_hand_id": "GG-6083293101"}) as ml, \
         patch.object(table_ss, "_set_swap_review") as ms:
        res = table_ss.swap_review_table_ss(5, {"decision": "accept"})
    ml.assert_called_once_with(5, "GG-6083293101")
    ms.assert_called_once_with(5, "moved")
    assert res["decision"] == "accept"


def test_swap_accept_hand_not_found_returns_404():
    # #SWAP-ACCEPT-GUARD: mão do número não existe → 404 (não falha em silêncio).
    log = [{"id": 5, "original_filename": _FULL}]
    with patch.object(table_ss, "query", return_value=log), \
         patch.object(table_ss, "_manual_link_ss", side_effect=ValueError("hand_not_found")):
        with pytest.raises(HTTPException) as e:
            table_ss.swap_review_table_ss(5, {"decision": "accept"})
    assert e.value.status_code == 404


def _it_row(fname, **extra):
    base = {"ss_id": 9, "fname": fname, "matched_hand_id": "GG-6083717670",
            "swap_review": None, "hand_db_id": 22, "hand_id": "GG-6083717670",
            "discord_tags": [], "hm3_tags": [], "dup_db_id": None, "dup_hand_id": None,
            "dup_discord_tags": None, "dup_hm3_tags": None}
    base.update(extra)
    return base


def test_it_rows_flags_accept_target_missing():
    # #SWAP-ACCEPT-GUARD: a mão do número (GG-6083717709) NÃO existe → accept off.
    main = [_it_row("x_6083717709-20260616220741-156.png")]

    def q(sql, params=None):
        return [] if "WHERE hand_id = ANY" in sql else main
    with patch.object(gg_health, "query", side_effect=q):
        out = gg_health._it_rows()
    assert out[0]["filename_num"] == "6083717709"
    assert out[0]["accept_target_exists"] is False


def test_it_rows_flags_accept_target_present():
    main = [_it_row("x_6083717709-20260616220741-156.png")]

    def q(sql, params=None):
        return [{"hand_id": "GG-6083717709"}] if "WHERE hand_id = ANY" in sql else main
    with patch.object(gg_health, "query", side_effect=q):
        out = gg_health._it_rows()
    assert out[0]["accept_target_exists"] is True


def test_swap_reject_sets_kept():
    with patch.object(table_ss, "query", return_value=[{"id": 5, "original_filename": "x.png"}]), \
         patch.object(table_ss, "_set_swap_review") as ms:
        res = table_ss.swap_review_table_ss(5, {"decision": "reject"})
    assert res["decision"] == "reject"
    ms.assert_called_once_with(5, "kept")


def test_swap_review_clears_mark():
    with patch.object(table_ss, "query", return_value=[{"id": 5, "original_filename": "x.png"}]), \
         patch.object(table_ss, "_set_swap_review") as ms:
        table_ss.swap_review_table_ss(5, {"decision": "review"})
    ms.assert_called_once_with(5, None)
