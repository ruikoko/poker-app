"""Fase 1 do editor Saúde GG — A (suspeitas 2-candidatas + revert-à-anónima) + E
(verificada por mim). Foco nas GUARDAS de segurança: nunca reverter position_v3
(Gold-manda), dry-run antes de gravar, flag verified aditivo."""
import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException

from app.routers import table_ss
from app.services.deanon_status import deanon_status, deanon_status_from_row


# ── E — verified_by_user vence o match_method (só o badge) ───────────────────
def test_verified_by_user_overrides_match_method():
    assert deanon_status("GGPoker", "table_ss") == "unverified"
    assert deanon_status("GGPoker", "table_ss", verified_by_user=True) == "verified"
    assert deanon_status("GGPoker", None, verified_by_user=True) == "verified"
    # não-GG continua sem badge mesmo com o flag (não faz sentido lá)
    assert deanon_status("Winamax", "table_ss", verified_by_user=True) is None


def test_deanon_status_from_row_reads_verified_flag():
    row = {"site": "GGPoker",
           "player_names": {"match_method": "table_ss", "verified_by_user": True}}
    assert deanon_status_from_row(row) == "verified"
    row2 = {"site": "GGPoker", "player_names": '{"match_method":"table_ss"}'}
    assert deanon_status_from_row(row2) == "unverified"


def test_verify_deanon_sets_flag_and_returns_verified():
    rows = [{"id": 7, "site": "GGPoker",
             "player_names": {"match_method": "table_ss", "anon_map": {"x": "N"}}}]
    with patch.object(table_ss, "query", return_value=rows), \
         patch.object(table_ss, "get_conn", return_value=MagicMock()):
        res = table_ss.verify_deanon({"hand_id": "GG-1", "verified": True})
    assert res["verified_by_user"] is True
    assert res["deanon_status"] == "verified"


def test_verify_deanon_unset_removes_flag():
    rows = [{"id": 7, "site": "GGPoker",
             "player_names": {"match_method": "table_ss", "verified_by_user": True}}]
    with patch.object(table_ss, "query", return_value=rows), \
         patch.object(table_ss, "get_conn", return_value=MagicMock()):
        res = table_ss.verify_deanon({"hand_id": "GG-1", "verified": False})
    assert res["verified_by_user"] is False
    assert res["deanon_status"] == "unverified"   # volta ao derivado do match_method


# ── A — GUARDA do revert: NUNCA tocar position_v3 (Gold) nem null ────────────
def test_revert_skips_position_v3_no_write():
    rows = [{"raw": "x", "player_names": {"match_method": "position_v3"}}]
    with patch.object(table_ss, "query", return_value=rows), \
         patch.object(table_ss, "get_conn") as mconn:
        res = table_ss._revert_hand_to_anonymous(99)
    assert res["reverted"] is False and res["reason"] == "not_table_ss"
    mconn.assert_not_called()                     # Gold-manda: não escreve


def test_revert_skips_anonymous_null_match_no_write():
    rows = [{"raw": "x", "player_names": {}}]
    with patch.object(table_ss, "query", return_value=rows), \
         patch.object(table_ss, "get_conn") as mconn:
        res = table_ss._revert_hand_to_anonymous(99)
    assert res["reverted"] is False and res["reason"] == "not_table_ss"
    mconn.assert_not_called()


# ── A — resolve-owner dry-run (pré-visualização, não grava) ──────────────────
def _q_resolve(log_matched, owner_exists=True, current_mm="table_ss"):
    def q(sql, params=None):
        if "table_ss_processing_log" in sql:
            return [{"id": 81, "matched_hand_id": log_matched}]
        if "FROM hands WHERE hand_id" in sql:
            hid = params[0]
            if hid == log_matched:                # a antiga (current)
                return [{"id": 10, "mm": current_mm}]
            return [{"id": 20, "mm": None}] if owner_exists else []
        return []
    return q


def test_resolve_dry_keep_when_owner_is_current():
    with patch.object(table_ss, "query", side_effect=_q_resolve("GG-A")):
        res = table_ss.resolve_owner(81, {"owner_hand_id": "GG-A", "dry_run": True})
    assert res["dry_run"] is True
    assert res["plan"]["keep"] is True
    assert res["plan"]["will_revert"] is None      # confirma actual → nada a reverter


def test_resolve_dry_reverts_old_table_ss():
    with patch.object(table_ss, "query", side_effect=_q_resolve("GG-OLD", current_mm="table_ss")):
        res = table_ss.resolve_owner(81, {"owner_hand_id": "GG-NEW", "dry_run": True})
    rp = res["plan"]["will_revert"]
    assert rp and rp["hand_id"] == "GG-OLD"        # a antiga table_ss vai ser revertida
    assert res["plan"]["will_link"] == "GG-NEW"


def test_resolve_dry_does_not_revert_old_position_v3():
    with patch.object(table_ss, "query", side_effect=_q_resolve("GG-OLD", current_mm="position_v3")):
        res = table_ss.resolve_owner(81, {"owner_hand_id": "GG-NEW", "dry_run": True})
    assert res["plan"]["will_revert"] is None      # Gold-manda: não reverte a antiga gold


def test_resolve_owner_not_found_422():
    with patch.object(table_ss, "query", side_effect=_q_resolve("GG-A", owner_exists=False)):
        with pytest.raises(HTTPException) as e:
            table_ss.resolve_owner(81, {"owner_hand_id": "GG-NOPE", "dry_run": True})
    assert e.value.status_code == 422


# ── A — swap-candidates (read-only, as 2 mãos p/ comparar) ───────────────────
def test_swap_candidates_returns_both():
    def q(sql, params=None):
        if "table_ss_processing_log" in sql:
            return [{"id": 81, "original_filename": "f.png", "matched_hand_id": "GG-CUR"}]
        if "FROM hands WHERE hand_id" in sql:
            return [{"id": 1, "mm": "table_ss"}]
        return []
    with patch.object(table_ss, "query", side_effect=q), \
         patch.object(table_ss, "_parse_it_hand_fields",
                      return_value={"hand_num": "6083717709"}), \
         patch.object(table_ss, "_hand_seats_for_id", return_value=[{"seat": 1}]):
        res = table_ss.swap_candidates(81)
    roles = {c["role"]: c for c in res["candidates"]}
    assert roles["current"]["hand_id"] == "GG-CUR"
    assert roles["filename"]["hand_id"] == "GG-6083717709"
    assert res["capture"]["filename_num"] == "6083717709"
