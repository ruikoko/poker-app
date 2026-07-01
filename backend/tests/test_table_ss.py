"""Tests para routers/table_ss + integração com queue_export/hrc_queue (pt38).

Pattern de mocks alinhado com test_lobby_sync.py (asyncio.run + unittest.mock).
"""
import asyncio
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import table_ss


CAP = datetime(2026, 5, 23, 16, 4, 0, tzinfo=timezone.utc)


def _cand(hid, tn, secs_off=0):
    return {
        "id": hid, "hand_id": f"WN-{hid}", "tournament_number": tn,
        "tournament_name": "ODYSSEY #013", "site": "Winamax",
        "played_at": CAP,
    }


# ── _resolve_match ───────────────────────────────────────────────────────────

def test_resolve_match_no_candidates():
    m = table_ss._resolve_match(CAP, {"tournament_name": "X"}, "Winamax", [])
    assert m["matched"] is None
    assert m["reason"] == "no_hands_in_window"
    assert m["ambiguous"] is False


def test_resolve_match_single_tn_matches_closest():
    # pt39 p2: nome da SS bate com o do torneio (ambos 'ODYSSEY #013' via _cand).
    cands = [_cand(10, "T1"), _cand(11, "T1")]
    m = table_ss._resolve_match(
        CAP, {"tournament_name": "ODYSSEY #013"}, "Winamax", cands)
    assert m["matched"]["id"] == 10  # primeira (mais próxima)
    assert m["tn"] == "T1"
    assert m["reason"] == "single_tn"


# ── pt39 parte 2/2: validação de nome no single_tn ──────────────────────────

def _candn(hid, tn, name):
    return {"id": hid, "hand_id": f"WN-{hid}", "tournament_number": tn,
            "tournament_name": name, "site": "Winamax", "played_at": CAP}


def test_resolve_match_single_tn_name_mismatch_rejects():
    """EXPLORER #010 (SS), janela só com mão de INTERSTELLAR → rejeita
    (colisão silenciosa do pt38)."""
    cands = [_candn(1, "1100185162", "INTERSTELLAR")]
    m = table_ss._resolve_match(
        CAP, {"tournament_name": "EXPLORER #010"}, "Winamax", cands)
    assert m["matched"] is None
    assert m["ambiguous"] is False
    assert m["reason"].startswith("single_tn_name_mismatch")


def test_resolve_match_single_tn_name_mismatch_odyssey_zenith():
    """ODYSSEY #013 (SS) → mão ZENITH na janela: 2ª colisão silenciosa real."""
    cands = [_candn(9, "1099830438", "ZENITH")]
    m = table_ss._resolve_match(
        CAP, {"tournament_name": "ODYSSEY #013"}, "Winamax", cands)
    assert m["matched"] is None
    assert m["reason"].startswith("single_tn_name_mismatch")


def test_resolve_match_single_tn_name_match_accepts():
    """INTERSTELLAR #005 (SS) → mão INTERSTELLAR: nome bate → aceita."""
    cands = [_candn(2, "1100185162", "INTERSTELLAR")]
    m = table_ss._resolve_match(
        CAP, {"tournament_name": "INTERSTELLAR #005"}, "Winamax", cands)
    assert m["matched"]["id"] == 2
    assert m["reason"] == "single_tn"


def test_resolve_match_single_tn_empty_ss_name_lenient_accepts():
    """SS sem nome lido (Vision falhou no nome) → leniente: aceita single_tn."""
    cands = [_candn(10, "T1", "ZENITH")]
    m = table_ss._resolve_match(CAP, {"tournament_name": None}, "Winamax", cands)
    assert m["matched"]["id"] == 10
    assert m["reason"] == "single_tn"


# ── #FIX-B2 (pt50): name-estrito site-gated (não partir salas de nome genérico) ─

def _candn_site(hid, tn, name, site):
    return {"id": hid, "hand_id": f"X-{hid}", "tournament_number": tn,
            "tournament_name": name, "site": site, "played_at": CAP}


def test_resolve_match_gg_name_mismatch_still_rejects():
    """GGPoker (nome fiável): SS com nome que NÃO bate → continua a rejeitar."""
    cands = [_candn_site(1, "T1", "ZENITH", "GGPoker")]
    m = table_ss._resolve_match(
        CAP, {"tournament_name": "ODYSSEY"}, "GGPoker", cands)
    assert m["matched"] is None
    assert m["reason"].startswith("single_tn_name_mismatch")


def test_resolve_match_wpn_generic_name_does_not_break_match():
    """WPN grava string de garantia genérica: o nome legível da SS NÃO bate o
    nome da mão, mas como WPN não tem nome fiável → NÃO rejeitar (cai no tempo).
    Sem o site-gating isto rejeitaria um match WPN válido."""
    cands = [_candn_site(2, "T2", "$5,000 GTD Guaranteed", "WPN")]
    m = table_ss._resolve_match(
        CAP, {"tournament_name": "Sunday Special"}, "WPN", cands)
    assert m["matched"]["id"] == 2
    assert m["reason"] == "single_tn"


def test_resolve_match_pokerstars_null_name_does_not_break_match():
    """PokerStars grava tournament_name NULL → sem nome p/ validar → aceita."""
    cands = [_candn_site(3, "T3", None, "PokerStars")]
    m = table_ss._resolve_match(
        CAP, {"tournament_name": "Bounty Builder"}, "PokerStars", cands)
    assert m["matched"]["id"] == 3
    assert m["reason"] == "single_tn"


@patch("app.routers.table_ss._upsert_table_ss_log", return_value=1)
@patch("app.routers.table_ss.resolve_tournament_number",
       return_value=("EXPLORER-TN", []))
@patch("app.routers.table_ss._find_candidate_hands",
       return_value=[{"id": 1, "hand_id": "WN-1", "tournament_number": "1100185162",
                      "tournament_name": "INTERSTELLAR", "site": "Winamax",
                      "played_at": CAP}])
@patch("app.routers.table_ss.tv.extract_table_ss_json",
       return_value='{"site":"Winamax","tournament_name":"EXPLORER #010",'
                    '"players_left":677}')
@patch("app.routers.table_ss.query", return_value=[])
def test_process_single_tn_mismatch_no_match_and_stores_tn(_q, _ex, _find, _res, _up):
    """E2E: SS EXPLORER, janela só com mão INTERSTELLAR → name mismatch →
    no_match_to_hand + tn real de EXPLORER guardado (limbo p/ re-link)."""
    out = _run_process()
    assert out["result"] == "no_match_to_hand"
    assert out["tournament_number"] == "EXPLORER-TN"
    assert out["hand_matched"] is None
    assert _up.call_args.kwargs.get("matched_hand_db_id") is None


@patch("app.routers.table_ss.resolve_tournament_number", return_value=("T2", []))
def test_resolve_match_multi_tn_disambiguated_by_name(_mock_res):
    cands = [_cand(10, "T1"), _cand(20, "T2")]
    m = table_ss._resolve_match(
        CAP, {"tournament_name": "ODYSSEY #013"}, "Winamax", cands,
    )
    assert m["matched"]["id"] == 20
    assert m["tn"] == "T2"
    assert m["reason"] == "disambiguated_by_name"


def test_resolve_match_multi_tn_direct_name_disambiguation():
    """pt54 (caso GALACTICA #034): 2 torneios na janela (GALACTICA + HIGHROLLER),
    SS = 'GALACTICA' → desambigua DIRECTO pelo nome contra os candidatos, sem
    precisar do resolver (cuja janela excluía o torneio iniciado <30min antes)."""
    cands = [
        _candn(1, "1103534384", "GALACTICA"),    # mais próxima
        _candn(2, "1103534384", "GALACTICA"),
        _candn(3, "1103131976", "HIGHROLLER"),
    ]
    # resolver NÃO mockado de propósito — o directo tem de resolver sozinho.
    m = table_ss._resolve_match(CAP, {"tournament_name": "GALACTICA"}, "Winamax", cands)
    assert m["matched"]["id"] == 1
    assert m["tn"] == "1103534384"
    assert m["reason"] == "disambiguated_by_name_direct"


def test_resolve_match_truncated_title_links_unique_candidate():
    """pt58 (caso id=134): título truncado '[Mystery Bo...]'; só o 268-M na janela
    bate os tokens restantes → liga (sem inventar)."""
    cands = [
        _candn(1, "286729346", "268-M: $150 Saturday Secret KO [Mystery Bounty]"),
        _candn(2, "287027219", "Bounty Hunters Deepstack Turbo $54"),
        _candn(3, "287017027", "Saturday Session: GGMasters Bounty $108"),
    ]
    m = table_ss._resolve_match(
        CAP, {"tournament_name": "268-M: $150 Saturday Secret KO [Mystery Bo...]"},
        "GGPoker", cands)
    assert m["matched"]["id"] == 1
    assert m["tn"] == "286729346"
    assert m["reason"] == "disambiguated_by_name_direct"


@patch("app.routers.table_ss.resolve_tournament_number", return_value=(None, []))
def test_resolve_match_truncated_prefixing_two_stays_ambiguous(_res):
    """pt58: título truncado 'Tu...' prefixa Turbo $54 E $88 (2 torneios) → NÃO
    inventa match, FICA ambíguo."""
    cands = [
        _candn(1, "A", "Bounty Hunters Deepstack Turbo $54"),
        _candn(2, "B", "Bounty Hunters Deepstack Turbo $88"),
    ]
    m = table_ss._resolve_match(
        CAP, {"tournament_name": "Bounty Hunters Deepstack Tu..."}, "GGPoker", cands)
    assert m["matched"] is None
    assert m["ambiguous"] is True
    assert m["reason"].startswith("multi_tn_unresolved")


@patch("app.routers.table_ss.resolve_tournament_number", return_value=(None, []))
def test_resolve_match_multi_tn_resolver_none_ambiguous(_mock_res):
    cands = [_cand(10, "T1"), _cand(20, "T2")]
    m = table_ss._resolve_match(CAP, {"tournament_name": "X"}, "Winamax", cands)
    assert m["matched"] is None
    assert m["ambiguous"] is True
    assert m["reason"].startswith("multi_tn_unresolved")


@patch("app.routers.table_ss.resolve_tournament_number", return_value=("T9", []))
def test_resolve_match_multi_tn_resolver_outside_set_ambiguous(_mock_res):
    cands = [_cand(10, "T1"), _cand(20, "T2")]
    m = table_ss._resolve_match(CAP, {"tournament_name": "X"}, "Winamax", cands)
    assert m["matched"] is None
    assert m["ambiguous"] is True


# ── _upsert_table_ss_log ─────────────────────────────────────────────────────

def test_upsert_invalid_result_raises():
    with pytest.raises(ValueError, match="invalid result"):
        table_ss._upsert_table_ss_log(
            file_hash="h", source="manual_upload", original_filename=None,
            file_size=None, result="gibberish",
        )


@patch("app.routers.table_ss.get_conn")
def test_upsert_insert_on_conflict_and_links_hand(mock_get_conn):
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = {"id": 7}
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_get_conn.return_value = mock_conn

    rid = table_ss._upsert_table_ss_log(
        file_hash="abc", source="manual_upload", original_filename="x.png",
        file_size=123, result="success", site="Winamax",
        tournament_name="ODYSSEY #013", tournament_number="T1",
        players_left=71, total_entries=124, captured_at=CAP,
        matched_hand_id="WN-10", vision_json={"a": 1}, matched_hand_db_id=10,
    )
    assert rid == 7
    sqls = [" ".join(c[0][0].split()) for c in mock_cur.execute.call_args_list]
    assert any("ON CONFLICT (file_hash)" in s for s in sqls)
    assert any(
        "attempt_count = table_ss_processing_log.attempt_count + 1" in s
        for s in sqls
    )
    # Liga a mão na mesma transacção.
    assert any("UPDATE hands SET context_table_ss_id = %s" in s for s in sqls)
    mock_conn.commit.assert_called_once()


@patch("app.routers.table_ss.get_conn")
def test_upsert_unlinks_when_no_match(mock_get_conn):
    """#FIX-B3 (pt50): sem match (matched_hand_db_id=None), o upsert desliga
    qualquer mão obsoleta que ainda aponte para esta SS (não cria link)."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = {"id": 8}
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_get_conn.return_value = mock_conn

    table_ss._upsert_table_ss_log(
        file_hash="abc", source="manual_upload", original_filename="x.png",
        file_size=1, result="no_match_to_hand", matched_hand_db_id=None,
    )
    sqls = [" ".join(c[0][0].split()) for c in mock_cur.execute.call_args_list]
    # desliga (SET NULL) — nunca liga.
    assert any("UPDATE hands SET context_table_ss_id = NULL WHERE context_table_ss_id = %s" in s for s in sqls)
    assert not any("SET context_table_ss_id = %s WHERE id" in s for s in sqls)


# ── _process_table_ss (orquestração) ─────────────────────────────────────────

def _run_process(**patches):
    return asyncio.run(table_ss._process_table_ss(
        b"\x89PNG\r\n\x1a\nx", "Shot1-Winamax-20260523170400.png",
    ))


@patch("app.routers.table_ss._upsert_table_ss_log", return_value=1)
@patch("app.routers.table_ss.tv.extract_table_ss_json", return_value=None)
@patch("app.routers.table_ss.query", return_value=[])
def test_process_vision_failed(_q, _ex, _up):
    out = _run_process()
    assert out["result"] == "vision_failed"
    _up.assert_called_once()


# ── pt73 — auditoria read-only verify-recovery ────────────────────────────────

def test_verify_is_strong_classifier():
    assert table_ss._verify_is_strong("disambiguated_by_name_direct") is True
    assert table_ss._verify_is_strong("filename_tn") is True
    assert table_ss._verify_is_strong("closest_by_time") is False
    assert table_ss._verify_is_strong("stack_arithmetic") is False
    assert table_ss._verify_is_strong(None) is False


def test_verify_recovery_assembles_and_detects_swap():
    # 7 chamadas a query(), por ordem: method, weak, pc, partial_list, amap,
    # samples, total. amap tem 1 torneio com 2 mãos e o MESMO hash com 2 nomes
    # diferentes → conflito (swap) detectado.
    side = [
        [{"method": "disambiguated_by_name_direct", "n": 160},
         {"method": "closest_by_time", "n": 6}],                       # method
        [{"hand_id": "GG-1", "tournament_name": "X", "played_at": "2026-06-14",
          "ss_id": 1, "method": "closest_by_time"}],                   # weak
        [{"partial": False, "n": 164}, {"partial": True, "n": 2}],     # pc
        [{"hand_id": "GG-2", "tournament_name": "Y", "played_at": "2026-06-14",
          "ss_id": 2}],                                                # partial_list
        [{"hand_id": "GG-3", "tournament_number": "T1", "anon_map": {"ab": "Joana"}},
         {"hand_id": "GG-4", "tournament_number": "T1", "anon_map": {"ab": "Pedro"}}],  # amap (swap!)
        [{"hand_id": "GG-3", "tournament_name": "X", "tournament_number": "T1",
          "played_at": "2026-06-14", "ss_id": 3, "anon_map": {"ab": "Joana"},
          "hero": "thinvalium"}],                                      # samples
        [{"n": 166}],                                                  # total
    ]
    with patch("app.routers.table_ss.query", side_effect=side):
        out = table_ss.verify_recovery(samples=4, current_user={"id": 1})
    assert out["total_deanon_table_ss"] == 166
    assert out["partial_vs_complete"] == {"complete": 164, "partial": 2}
    assert len(out["weak_matches"]) == 1
    assert out["cross_tournament"]["conflicts"] == 1          # swap apanhado
    assert out["cross_tournament"]["conflict_detail"][0]["names"] == ["Joana", "Pedro"]
    assert out["samples"][0]["capture_url"] == "/api/table-ss/image/3"


def test_deanon_debug_detail_lines_up_hh_vs_gravado():
    raw = (
        "Table 'Mesa' 6-max Seat #3 is the button\n"
        "Seat 1: Hero (220146 in chips)\n"
        "Seat 2: 89ef4cba (450924 in chips)\n"
        "Seat 3: aa11bb22 (61500 in chips)\n"
    )
    apa = {
        "_meta": {"bb": 7000},
        "Lauro Dermio": {"seat": 1, "position": "SB", "stack_bb": 31.4, "is_hero": True},
        "TeaFoxxx": {"seat": 2, "position": "BB", "stack_bb": 64.4, "is_hero": False},
        "Evil249": {"seat": 3, "position": "BTN", "stack_bb": 8.8, "is_hero": False},
    }
    pn = {"hero": "Lauro Dermio",
          "anon_map": {"89ef4cba": "TeaFoxxx", "aa11bb22": "Evil249"}}
    hand_row = {"hand_id": "GG-X", "raw": raw, "all_players_actions": apa,
                "player_names": pn, "context_table_ss_id": 5}
    vis_row = {"vision_json": {"seats": [
        {"nick": "Lauro Dermio", "stack_bb": 31.4, "is_hero": True},
        {"nick": "TeaFoxxx", "stack_bb": 64.4, "is_hero": False},
        {"nick": "Evil249", "stack_bb": 8.8, "is_hero": False}]}}
    with patch("app.routers.table_ss.query", side_effect=[[hand_row], [vis_row]]):
        out = table_ss.deanon_debug(hand_id="GG-X", current_user={"id": 1})
    assert out["button_seat"] == 3
    by_seat = {s["seat"]: s for s in out["hh_seats_with_gravado"]}
    assert by_seat[1]["nick_gravado"] == "Lauro Dermio" and by_seat[1]["position"] == "SB"
    assert by_seat[2]["nick_gravado"] == "TeaFoxxx" and by_seat[2]["stack_bb"] == 64.4
    assert by_seat[3]["nick_gravado"] == "Evil249" and by_seat[3]["position"] == "BTN"
    assert len(out["vision_seats_lidos"]) == 3


def test_deanon_debug_scan_flags_close_stacks():
    apa = {
        "_meta": {"bb": 1000},
        "Hero": {"seat": 1, "stack_bb": 30.0, "is_hero": True},
        "A": {"seat": 2, "stack_bb": 10.0, "is_hero": False},
        "B": {"seat": 3, "stack_bb": 10.8, "is_hero": False},   # gap 0.8 < 2.0 → flag
        "C": {"seat": 4, "stack_bb": 50.0, "is_hero": False},
    }
    row = {"hand_id": "GG-Y", "tournament_name": "T", "all_players_actions": apa}
    with patch("app.routers.table_ss.query", return_value=[row]):
        out = table_ss.deanon_debug(hand_id=None, mode="gap", gap_bb=2.0, current_user={"id": 1})
    assert out["n_swap_risk"] == 1
    assert out["flagged"][0]["hand_id"] == "GG-Y"
    assert out["flagged"][0]["close_pairs"][0]["gap_bb"] == 0.8


def test_deanon_debug_fit_flags_hero_allin_mismatch():
    # SS de OUTRA mão: hero ALLIN na imagem mas 31.4bb na HH → misfit.
    apa = {
        "_meta": {"bb": 7000},
        "Lauro Dermio": {"seat": 4, "stack_bb": 31.4, "is_hero": True},
        "TeaFoxxx": {"seat": 5, "stack_bb": 64.4, "is_hero": False},
        "Evil249": {"seat": 3, "stack_bb": 8.8, "is_hero": False},
    }
    vj = {"seats": [
        {"nick": "Lauro Dermio", "stack_bb": "ALLIN", "is_hero": True},
        {"nick": "x", "stack_bb": 44.7, "is_hero": False},
        {"nick": "y", "stack_bb": 21.8, "is_hero": False}]}
    row = {"hand_id": "GG-Z", "tournament_name": "T", "all_players_actions": apa, "vision_json": vj}
    with patch("app.routers.table_ss.query", return_value=[row]):
        out = table_ss.deanon_debug(hand_id=None, mode="fit", current_user={"id": 1})
    assert out["mode"] == "fit"
    assert out["n_hero_allin_mismatch"] == 1
    assert out["n_misfit"] == 1
    assert out["flagged"][0]["hero_vision_bb"] == "ALLIN"
    assert out["flagged"][0]["hero_hh_bb"] == 31.4


def test_hand_seats_maps_seats_and_flags_unmapped():
    # APA com hero (mapeado) + 1 vilão mapeado + 1 assento POR MAPEAR (hash).
    apa = {
        "_meta": {"sb": 100, "bb": 200, "level": 5},
        "Lauro Dermio": {"seat": 1, "position": "BTN", "stack": 20000,
                         "stack_bb": 100.0, "is_hero": True, "real_name": "Lauro Dermio"},
        "Niklas Astedt": {"seat": 3, "position": "BB", "stack": 9000,
                          "stack_bb": 45.0, "is_hero": False, "real_name": "Niklas Astedt"},
        "89ef4cba": {"seat": 5, "position": "CO", "stack": 0, "stack_bb": 0,
                     "is_hero": False, "real_name": "89ef4cba"},  # all-in / por mapear
    }
    pn = {"anon_map": {"h1": "Lauro Dermio", "h2": "Niklas Astedt"}, "match_method": "table_ss"}
    row = {"hand_id": "GG-9", "tournament_name": "X", "played_at": "2026-06-09",
           "ss_id": 9, "all_players_actions": apa, "player_names": pn}
    with patch("app.routers.table_ss.query", return_value=[row]):
        out = table_ss.hand_seats(hand_ids="GG-9", current_user={"id": 1})
    h = out["hands"][0]
    assert h["n_seats"] == 3 and h["n_mapped"] == 2
    assert h["capture_url"] == "/api/table-ss/image/9"
    s = {x["seat"]: x for x in h["seats"]}
    assert s[1]["nick"] == "Lauro Dermio" and s[1]["is_hero"] is True and s[1]["mapped"]
    assert s[3]["nick"] == "Niklas Astedt" and s[3]["position"] == "BB"
    assert s[5]["mapped"] is False and s[5]["nick"] is None and s[5]["raw_hash"] == "89ef4cba"
    # ordenado por seat
    assert [x["seat"] for x in h["seats"]] == [1, 3, 5]


# ── pt73 — reprocesso server-side de capturas vision_failed (recuperação) ─────

def _failed_row():
    return {"id": 7, "original_filename": "GGPoker-X(123)(#1)-20260614231443-9.png",
            "folder_tag": "icm-pko", "captured_at": CAP, "img_b64": "aGVsbG8="}


@patch("app.routers.table_ss._apply_folder_tag_to_hand")
@patch("app.routers.table_ss._deanon_after_match")
@patch("app.routers.table_ss._persist_table_ss_match", return_value=True)
@patch("app.routers.table_ss._store_recovered_vision")
@patch("app.routers.table_ss.compute_table_ss_match",
       return_value={"result": "success", "reason_detail": "filename_tn",
                     "site": "GGPoker", "tournament_number": "123",
                     "matched_hand_id": "GG-9", "matched_hand_db_id": 9})
@patch("app.routers.table_ss.parse_table_ss_filename",
       return_value={"site": "GGPoker", "tournament_number": "123"})
@patch("app.routers.table_ss.tv.parse_and_validate_table_ss_json",
       return_value={"site": "GGPoker", "tournament_name": "X", "players_left": 50,
                     "seats": [{"nick": "a"}]})
@patch("app.routers.table_ss.tv.extract_table_ss_json", return_value='{"site":"GGPoker"}')
def test_reprocess_failed_row_success_applies_folder_tag(
    _ex, _pv, _pf, _cm, _store, _persist, _deanon, _apply):
    out = asyncio.run(table_ss._reprocess_failed_row(_failed_row()))
    assert out["result"] == "success"
    # desanon + folder_tag aplicados à mão casada
    _deanon.assert_called_once()
    _apply.assert_called_once()
    assert _apply.call_args[0][0] == 9          # matched_hand_db_id
    assert _apply.call_args[0][1] == "icm-pko"  # folder_tag preservado
    _store.assert_called_once()                  # vision_json gravado in-place


@patch("app.routers.table_ss._update_failed_reason")
@patch("app.routers.table_ss.tv.extract_table_ss_json", return_value=None)
def test_reprocess_failed_row_still_failing_updates_reason(_ex, _upd):
    # Vision ainda falha (ex. crédito ainda em falta) → só actualiza reason,
    # NÃO cria mão nem aplica tag; fica vision_failed para nova tentativa.
    def _se(content, mime, err_out=None):
        if err_out is not None:
            err_out["error"] = "Vision API: BadRequestError: credit balance too low"
        return None
    with patch("app.routers.table_ss.tv.extract_table_ss_json", side_effect=_se):
        out = asyncio.run(table_ss._reprocess_failed_row(_failed_row()))
    assert out["result"] == "vision_failed"
    _upd.assert_called_once()
    assert "credit balance too low" in _upd.call_args[0][1]


@patch("app.routers.table_ss._upsert_table_ss_log", return_value=1)
@patch("app.routers.table_ss.query", return_value=[])
def test_process_vision_failed_propagates_real_error(_q, _up):
    # pt73 — a causa REAL (escrita no err_out pela Vision) chega ao reason_detail.
    def _se(content, mime, err_out=None):
        if err_out is not None:
            err_out["error"] = "Vision API: BadRequestError: credit balance is too low"
        return None
    with patch("app.routers.table_ss.tv.extract_table_ss_json", side_effect=_se):
        out = _run_process()
    assert out["result"] == "vision_failed"
    assert out["reason_detail"] == "Vision API: BadRequestError: credit balance is too low"


@patch("app.routers.table_ss._upsert_table_ss_log", return_value=1)
@patch("app.routers.table_ss.tv.extract_table_ss_json", return_value="not json at all")
@patch("app.routers.table_ss.query", return_value=[])
def test_process_json_invalid(_q, _ex, _up):
    out = _run_process()
    assert out["result"] == "json_invalid"


@patch("app.routers.table_ss.tv._correct_site", side_effect=lambda name, site: site)
@patch("app.routers.table_ss._upsert_table_ss_log", return_value=1)
@patch("app.routers.table_ss.tv.extract_table_ss_json",
       return_value='{"site":"PartyPoker","tournament_name":"X","players_left":50}')
@patch("app.routers.table_ss.query", return_value=[])
def test_process_site_undetected(_q, _ex, _up, _mcorrect):
    # pt56: nome SEM token de site → fallback Vision ('PartyPoker', não suportado).
    out = asyncio.run(table_ss._process_table_ss(b"\x89PNGx", "screenshot.png"))
    assert out["result"] == "site_undetected"
    assert out["site"] == "PartyPoker"


@patch("app.routers.table_ss.tv._correct_site", side_effect=lambda name, site: site)
@patch("app.routers.table_ss._upsert_table_ss_log", return_value=1)
@patch("app.routers.table_ss._find_candidate_hands",
       return_value=[{"id": 10, "hand_id": "WN-10", "tournament_number": "T1",
                      "tournament_name": "ODYSSEY #013", "site": "Winamax",
                      "played_at": CAP}])
@patch("app.routers.table_ss.tv.extract_table_ss_json",
       return_value='{"site":"Winamax","tournament_name":"ODYSSEY #013",'
                    '"players_left":71,"total_entries":124}')
@patch("app.routers.table_ss.query", return_value=[])
def test_process_success_links_hand(_q, _ex, _find, _up, _mcorrect):
    out = _run_process()
    assert out["result"] == "success"
    assert out["hand_matched"] == "WN-10"
    assert out["players_left"] == 71
    assert out["tournament_number"] == "T1"
    # _upsert chamado com matched_hand_db_id=10 (liga a mão)
    assert _up.call_args.kwargs["matched_hand_db_id"] == 10


@patch("app.routers.table_ss.tv._correct_site", side_effect=lambda name, site: site)
@patch("app.routers.table_ss._upsert_table_ss_log", return_value=1)
@patch("app.routers.table_ss.resolve_tournament_number", return_value=("T9", []))
@patch("app.routers.table_ss._find_candidate_hands", return_value=[])
@patch("app.routers.table_ss.tv.extract_table_ss_json",
       return_value='{"site":"Winamax","tournament_name":"ODYSSEY #013","players_left":71}')
@patch("app.routers.table_ss.query", return_value=[])
def test_process_no_match_stores_resolver_tn(_q, _ex, _find, _res, _up, _mcorrect):
    out = _run_process()
    assert out["result"] == "no_match_to_hand"
    assert out["tournament_number"] == "T9"  # guardado p/ limbo linkável
    assert out["hand_matched"] is None


@patch("app.routers.table_ss.tv.extract_table_ss_json")
@patch("app.routers.table_ss.query",
       return_value=[{"result": "success", "site": "Winamax",
                      "tournament_name": "ODYSSEY #013", "tournament_number": "T1",
                      "players_left": 71, "total_entries": 124,
                      "matched_hand_id": "WN-10", "captured_at": CAP,
                      "vision_json": {"a": 1}}])
def test_process_dedup_success_short_circuits(_q, _ex):
    out = _run_process()
    assert out["dedup"] is True
    assert out["result"] == "success"
    assert out["players_left"] == 71
    _ex.assert_not_called()  # não re-corre a Vision


# ── Endpoint ─────────────────────────────────────────────────────────────────

def _make_app():
    from app.auth import require_auth
    app = FastAPI()
    app.include_router(table_ss.router)
    app.dependency_overrides[require_auth] = lambda: {"id": 1, "email": "t@t"}
    return app


def test_endpoint_unauthorized_401():
    app = FastAPI()
    app.include_router(table_ss.router)
    client = TestClient(app)
    r = client.post("/api/table-ss/upload",
                    files={"file": ("x.png", b"x", "image/png")})
    assert r.status_code == 401


def test_endpoint_empty_file_400():
    app = _make_app()
    client = TestClient(app)
    r = client.post("/api/table-ss/upload",
                    files={"file": ("x.png", b"", "image/png")})
    assert r.status_code == 400


@patch("app.routers.table_ss._process_table_ss", new_callable=AsyncMock)
def test_endpoint_success_returns_process_dict(mock_proc):
    mock_proc.return_value = {"result": "success", "hand_matched": "WN-10",
                             "players_left": 71}
    app = _make_app()
    client = TestClient(app)
    r = client.post("/api/table-ss/upload",
                    files={"file": ("x.png", b"\x89PNGdata", "image/png")})
    assert r.status_code == 200
    assert r.json()["result"] == "success"
    assert r.json()["hand_matched"] == "WN-10"


# ── Integração _resolve_players_left (queue_export) ──────────────────────────

def test_resolve_players_left_prefers_context_table_ss():
    from app.services import queue_export
    with patch("app.db.query", return_value=[{"players_left": 71}]) as mq:
        v = queue_export._resolve_players_left(
            {"context_table_ss_id": 5, "tournament_number": "T1"}, None,
        )
    assert v == 71
    # query foi à table_ss_processing_log
    assert "table_ss_processing_log" in mq.call_args[0][0]


def test_resolve_players_left_falls_back_to_lobby_when_no_context():
    from app.services import queue_export
    with patch("app.db.query", return_value=[{"players_left": 99}]) as mq:
        v = queue_export._resolve_players_left(
            {"tournament_number": "T1"}, None,
        )
    assert v == 99
    assert "lobby_processing_log" in mq.call_args[0][0]


def test_resolve_players_left_none_when_nothing():
    from app.services import queue_export
    v = queue_export._resolve_players_left({}, None)
    assert v is None


# ── hrc_queue SELECT inclui context_table_ss_id ─────────────────────────────

def test_select_andar1_selects_context_table_ss_id():
    from app.services import hrc_queue
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    with patch("app.services.hrc_queue.query", return_value=[]) as mq:
        hrc_queue.select_andar1_rows(["icm"], ["new"], now - timedelta(days=1), now)
    sql = mq.call_args[0][0]
    assert "context_table_ss_id" in sql


# ── #FIX-B3 (pt50): R — match único determinístico (compute) ────────────────

def _ss_row(rid=1, site="Winamax", result="no_match_to_hand", matched=None,
            name="ODYSSEY #013"):
    return {"id": rid, "captured_at": CAP, "site": site,
            "vision_json": {"tournament_name": name}, "result": result,
            "matched_hand_id": matched}


def test_compute_match_single_tn_success():
    """R puro: 1 torneio na janela, nome bate → success com o hand_db_id."""
    with patch("app.routers.table_ss.tv._correct_site", side_effect=lambda n, s: s), \
         patch("app.routers.table_ss._find_candidate_hands", return_value=[
             {"id": 10, "hand_id": "WN-10", "tournament_number": "T1",
              "tournament_name": "ODYSSEY #013", "site": "Winamax", "played_at": CAP}]):
        d = table_ss.compute_table_ss_match(
            CAP, "Winamax", {"tournament_name": "ODYSSEY #013"})
    assert d["result"] == "success"
    assert d["matched_hand_id"] == "WN-10"
    assert d["matched_hand_db_id"] == 10
    assert d["tournament_number"] == "T1"


def test_compute_match_no_hands_resolves_tn_for_limbo():
    with patch("app.routers.table_ss.tv._correct_site", side_effect=lambda n, s: s), \
         patch("app.routers.table_ss._find_candidate_hands", return_value=[]), \
         patch("app.routers.table_ss.resolve_tournament_number", return_value=("T9", [])):
        d = table_ss.compute_table_ss_match(
            CAP, "Winamax", {"tournament_name": "ODYSSEY #013"})
    assert d["result"] == "no_match_to_hand"
    assert d["matched_hand_db_id"] is None
    assert d["tournament_number"] == "T9"


def test_compute_match_trusts_passed_site():
    """pt56: o site já é autoritário (do nome) — compute confia nele e procura
    candidatos nesse site, SEM re-corrigir (_correct_site não é chamado)."""
    seen = {}
    def fake_find(captured_at, site, table=None):
        seen["site"] = site
        return []
    with patch("app.routers.table_ss.tv._correct_site") as mcorrect, \
         patch("app.routers.table_ss._find_candidate_hands", side_effect=fake_find), \
         patch("app.routers.table_ss.resolve_tournament_number", return_value=(None, [])):
        d = table_ss.compute_table_ss_match(
            CAP, "PokerStars", {"tournament_name": "Sunday Bounty"})
    assert d["site"] == "PokerStars"          # usa o site passado, intacto
    assert seen["site"] == "PokerStars"
    mcorrect.assert_not_called()               # já não re-corrige no matching


# ── #IT-MATCHER-CASCADE: número do nome (Tier 1), regra física, colisões ─────

_FN_FULL = ("GGPoker-Daily Hyper $50 _ Buy-in $50 - Blinds 125 _ 250 - Table 8"
            "_!)@(#_$&%^_6083293101-20260616171101-4.png")
_FN_TRUNC = ("GGPoker-Speed Racer Bounty Europe $108 [10 BB] _ Buy-in $108 - "
             "Blinds 5,000 _ 10,000 - Table 8_!)@(#_$&%^_61-20260626204636-117.png")


def test_parse_it_hand_fields_full_and_truncated():
    f = table_ss._parse_it_hand_fields(_FN_FULL)
    assert f == {"hand_num": "6083293101", "table": 8, "sb": 125, "bb": 250}
    t = table_ss._parse_it_hand_fields(_FN_TRUNC)
    assert t == {"hand_num": "61", "table": 8, "sb": 5000, "bb": 10000}


def test_tier1_matches_by_filename_hand_id():
    cand = {"id": 42, "hand_id": "GG-6083293101", "tournament_number": "T9",
            "tournament_name": "Daily Hyper $50", "site": "GGPoker",
            "played_at": CAP, "raw": "Table '8' 6-max Seat #5 is the button"}
    with patch("app.routers.table_ss._hand_by_exact_id", return_value=cand):
        d = table_ss.compute_table_ss_match(CAP, "GGPoker", {}, filename=_FN_FULL)
    assert d["result"] == "success"
    assert d["reason_detail"] == "filename_hand_id"
    assert d["matched_hand_id"] == "GG-6083293101"
    assert d["matched_hand_db_id"] == 42


def test_tier1_rejects_when_table_mismatch():
    # HH diz mesa 8; o nome diz mesa 9 → Tier 1 recusa e cai para os seguintes.
    fn = _FN_FULL.replace("- Table 8", "- Table 9")
    cand = {"id": 42, "hand_id": "GG-6083293101", "tournament_number": "T9",
            "tournament_name": "X", "site": "GGPoker", "played_at": CAP,
            "raw": "Table '8' 6-max Seat #5 is the button"}
    with patch("app.routers.table_ss._hand_by_exact_id", return_value=cand), \
         patch("app.routers.table_ss._find_candidate_hands", return_value=[]), \
         patch("app.routers.table_ss.resolve_tournament_number", return_value=(None, [])):
        d = table_ss.compute_table_ss_match(CAP, "GGPoker", {}, filename=fn)
    assert d["reason_detail"] != "filename_hand_id"


def test_tier1_skips_when_number_truncated():
    # número truncado (<10 díg.) NÃO aciona Tier 1 → nem consulta a mão por id.
    with patch("app.routers.table_ss._hand_by_exact_id") as mex, \
         patch("app.routers.table_ss._find_candidate_hands", return_value=[]), \
         patch("app.routers.table_ss.resolve_tournament_number", return_value=(None, [])):
        table_ss.compute_table_ss_match(CAP, "GGPoker", {}, filename=_FN_TRUNC)
    mex.assert_not_called()


def test_principal_rank_ordering():
    assert table_ss._principal_rank("filename_hand_id") == 3
    assert table_ss._principal_rank("single_tn") == 2
    assert table_ss._principal_rank("disambiguated_by_name") == 2
    assert table_ss._principal_rank(None) == 1


def test_collision_number_beats_time_and_earlier_wins():
    cur = MagicMock()
    # Tier 1 (nova) vence tempo (actual), por rank.
    cur.fetchall.return_value = [
        {"id": 100, "reason_detail": "filename_hand_id", "captured_at": CAP},
        {"id": 50, "reason_detail": "single_tn", "captured_at": CAP},
    ]
    assert table_ss._new_capture_wins_principal(cur, 100, 50) is True
    # empate de rank → captured_at mais cedo vence (a nova é mais tarde → perde).
    cur.fetchall.return_value = [
        {"id": 100, "reason_detail": "single_tn", "captured_at": CAP + timedelta(minutes=1)},
        {"id": 50, "reason_detail": "single_tn", "captured_at": CAP},
    ]
    assert table_ss._new_capture_wins_principal(cur, 100, 50) is False


# ── pt56: site a partir do NOME do ficheiro (determinístico) ────────────────

def test_site_from_filename_all_sites_and_stars_alias():
    assert table_ss._site_from_filename("Shot1-GGPoker-20260601174446.png") == "GGPoker"
    assert table_ss._site_from_filename("Shot2-Winamax-20260523170400.png") == "Winamax"
    assert table_ss._site_from_filename("Shot25-WPN-20260601223005.png") == "WPN"
    # único alias: Stars → PokerStars
    assert table_ss._site_from_filename("Shot12-Stars-20260531182134.png") == "PokerStars"


def test_site_from_filename_unrecognized_or_malformed_returns_none():
    assert table_ss._site_from_filename("Shot29-CoinPoker-20260526212332.png") is None
    assert table_ss._site_from_filename("semtraco.png") is None
    assert table_ss._site_from_filename(None) is None
    assert table_ss._site_from_filename("") is None


@patch("app.routers.table_ss.tv._correct_site", return_value="GGPoker")
@patch("app.routers.table_ss.compute_table_ss_match",
       return_value={"result": "no_match_to_hand", "reason_detail": "x", "site": "PokerStars",
                     "tournament_number": None, "matched_hand_id": None, "matched_hand_db_id": None})
@patch("app.routers.table_ss._upsert_table_ss_log", return_value=1)
@patch("app.routers.table_ss.tv.extract_table_ss_json",
       return_value='{"site":"GGPoker","tournament_name":"Sunday Bounty €100","players_left":92}')
@patch("app.routers.table_ss.query", return_value=[])
def test_upload_filename_site_overrides_vision(_q, _ex, _up, _comp, _mcorrect):
    """A Vision leu GGPoker, mas o nome diz Stars → grava PokerStars (autoritário)
    e NÃO chama _correct_site (caminho do nome)."""
    out = asyncio.run(table_ss._process_table_ss(
        b"\x89PNGx", "Shot12-Stars-20260531182134.png"))
    assert out["site"] == "PokerStars"
    _mcorrect.assert_not_called()
    # compute foi chamado com o site do nome.
    assert _comp.call_args[0][1] == "PokerStars"


def test_compute_match_no_captured_at_resolves_tn():
    with patch("app.routers.table_ss.tv._correct_site", side_effect=lambda n, s: s), \
         patch("app.routers.table_ss.resolve_tournament_number", return_value=("T5", [])):
        d = table_ss.compute_table_ss_match(None, "Winamax", {"tournament_name": "X"})
    assert d["result"] == "no_match_to_hand"
    assert d["tournament_number"] == "T5"
    assert d["matched_hand_db_id"] is None


# ── _apply_hand_link — primitiva única (des)ligação ─────────────────────────

def test_apply_hand_link_links_and_unlinks_stale():
    cur = MagicMock()
    table_ss._apply_hand_link(cur, ss_id=7, matched_hand_db_id=10)
    sqls = [" ".join(c[0][0].split()) for c in cur.execute.call_args_list]
    # desliga obsoletas (id <> match) E liga a mão casada.
    assert any("SET context_table_ss_id = NULL WHERE context_table_ss_id = %s AND id <> %s" in s for s in sqls)
    assert any("SET context_table_ss_id = %s WHERE id = %s" in s for s in sqls)


def test_apply_hand_link_none_unlinks_all():
    cur = MagicMock()
    table_ss._apply_hand_link(cur, ss_id=7, matched_hand_db_id=None)
    sqls = [" ".join(c[0][0].split()) for c in cur.execute.call_args_list]
    assert sqls == ["UPDATE hands SET context_table_ss_id = NULL WHERE context_table_ss_id = %s"]


# ── reconcile_table_ss (R sobre TODAS as SS, pós-import) ────────────────────

@patch("app.routers.table_ss.query")
def test_reconcile_empty_hand_ids_short_circuits(mq):
    res = table_ss.reconcile_table_ss(hand_ids=[])
    assert res == {"checked": 0, "changed": 0, "success": 0, "orphan": 0, "ambiguous": 0}
    mq.assert_not_called()


@patch("app.routers.table_ss.query")
def test_reconcile_select_includes_success_for_correction(mq):
    # #FIX-B3: re-avalia TODAS (incl. success) → SELECT cobre os 3 results.
    mq.return_value = []
    table_ss.reconcile_table_ss()
    sql = " ".join(mq.call_args[0][0].split())
    assert "result IN ('success', 'no_match_to_hand', 'tm_ambiguous')" in sql
    assert "vision_json IS NOT NULL" in sql


@patch("app.routers.table_ss._persist_table_ss_match", return_value=True)
@patch("app.routers.table_ss.compute_table_ss_match")
@patch("app.routers.table_ss.query")
def test_reconcile_recomputes_and_persists_each_row(mq, mcompute, mpersist):
    mq.return_value = [_ss_row(1, result="no_match_to_hand"),
                       _ss_row(2, result="success", matched="WN-10")]
    mcompute.return_value = {
        "result": "success", "matched_hand_id": "WN-10", "matched_hand_db_id": 10,
        "tournament_number": "T1", "site": "Winamax", "reason_detail": "single_tn"}
    res = table_ss.reconcile_table_ss()
    assert res["checked"] == 2
    assert res["success"] == 2
    assert mpersist.call_count == 2   # recalcula+persiste cada row (de raiz)


# back-compat: o nome antigo do trigger delega no reconcile.
@patch("app.routers.table_ss.reconcile_table_ss", return_value={"checked": 0})
def test_relink_alias_delegates_to_reconcile(mrec):
    table_ss.relink_orphan_table_ss(hand_ids=[1, 2])
    mrec.assert_called_once_with([1, 2])


@patch("app.routers.table_ss.get_conn")
def test_persist_match_updates_fields_and_links(mock_get_conn):
    """_persist_table_ss_match grava os campos de match + reconcilia o link."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_get_conn.return_value = mock_conn
    desired = {"result": "success", "reason_detail": "single_tn", "site": "Winamax",
               "tournament_number": "T1", "matched_hand_id": "WN-10",
               "matched_hand_db_id": 10}
    changed = table_ss._persist_table_ss_match(
        5, desired, prev_result="no_match_to_hand", prev_matched_hand_id=None)
    assert changed is True   # mudou de no_match→success
    sqls = [" ".join(c[0][0].split()) for c in mock_cur.execute.call_args_list]
    assert any("UPDATE table_ss_processing_log SET result = %s" in s for s in sqls)
    assert any("SET context_table_ss_id = %s WHERE id = %s" in s for s in sqls)
    mock_conn.commit.assert_called_once()


# ── #TABLE-SS-FILENAME-TN — parser do nome + match autoritário por tn ─────────

def test_parse_filename_new_winamax_with_tn():
    out = table_ss.parse_table_ss_filename(
        "Winamax-Winamax ODYSSEY(1106616980)(#011)-20260605170038-1")
    assert out["site"] == "Winamax"
    assert out["tournament_number"] == "1106616980"
    assert out["tournament_name"] == "Winamax ODYSSEY"
    assert out["table"] == "011"


def test_parse_filename_new_with_extension():
    out = table_ss.parse_table_ss_filename(
        "Winamax-Winamax ODYSSEY(1106616980)(#011)-20260605170038-1.png")
    assert out["tournament_number"] == "1106616980"


def test_parse_filename_name_with_hyphen_and_dollar_keeps_tn():
    out = table_ss.parse_table_ss_filename(
        "GGPoker-W SERIES - DAY 1 $215(287872812)(#02)-20260603183000-3")
    assert out["site"] == "GGPoker"
    assert out["tournament_number"] == "287872812"
    assert out["tournament_name"] == "W SERIES - DAY 1 $215"


def test_parse_filename_digits_paren_in_title_picks_tn_before_table():
    # tn = parêntese só-dígitos imediatamente antes do (#mesa), não o (123) do nome
    out = table_ss.parse_table_ss_filename(
        "Winamax-FOO (123) BAR(999888777)(#05)-20260605170038-1")
    assert out["tournament_number"] == "999888777"
    assert out["tournament_name"] == "FOO (123) BAR"


def test_parse_filename_pokerstars_full_name_new():
    out = table_ss.parse_table_ss_filename(
        "PokerStars-Sunday Million(555444)(#01)-20260605170038-1")
    assert out["site"] == "PokerStars"
    assert out["tournament_number"] == "555444"


def test_parse_filename_old_shot_no_tn_fallback():
    out = table_ss.parse_table_ss_filename("Shot1-Stars-20260603221723.png")
    assert out["site"] == "PokerStars"
    assert out["tournament_number"] is None


def test_parse_filename_new_without_tn_fallback():
    out = table_ss.parse_table_ss_filename("Winamax-Algo Sem Tn-20260605170038-1")
    assert out["site"] == "Winamax"
    assert out["tournament_number"] is None


# ── pt62: prefixo do EXECUTÁVEL do IT (GGnet.exe / Winamax.exe) ─────────────

def test_normalize_site_token_exe_and_clean_prefixes():
    # prefixos limpos (qualquer caixa) passam tal e qual
    assert table_ss._normalize_site_token("GGPoker") == "GGPoker"
    assert table_ss._normalize_site_token("Winamax") == "Winamax"
    assert table_ss._normalize_site_token("WPN") == "WPN"
    assert table_ss._normalize_site_token("PokerStars") == "PokerStars"
    assert table_ss._normalize_site_token("Stars") == "PokerStars"
    # prefixos do executável do IT → site canónico (sufixo .exe aparado)
    assert table_ss._normalize_site_token("GGnet.exe") == "GGPoker"
    assert table_ss._normalize_site_token("Winamax.exe") == "Winamax"
    # desconhecido / vazio → None (cai no fallback Vision a jusante)
    assert table_ss._normalize_site_token("CoinPoker") is None
    assert table_ss._normalize_site_token(None) is None
    assert table_ss._normalize_site_token("") is None


def test_parse_filename_gg_table_exe_prefix_no_tn():
    """MESA GG do IT com prefixo GGnet.exe (sem '(tn)(#mesa)') → site GGPoker,
    tn None (cai no fluxo Vision+resolver, como qualquer MESA GG)."""
    out = table_ss.parse_table_ss_filename(
        "GGnet.exe-Bounty Hunters Hyper Special $108 _ Buy-in $108 - Blinds 250 "
        "_ 500 - Table 24_!)@(#_$&%^_6057220262-20260608223525-49.png")
    assert out["site"] == "GGPoker"
    assert out["tournament_number"] is None


def test_parse_filename_gg_table_clean_prefix_no_tn():
    out = table_ss.parse_table_ss_filename(
        "GGPoker-Bounty Hunters Hyper Special $108 _ Buy-in $108 - Blinds 1,000 "
        "_ 2,000 - Table 2_!)@(#_$&%^_60564155-20260608231443-57.png")
    assert out["site"] == "GGPoker"
    assert out["tournament_number"] is None


def test_parse_filename_new_winamax_exe_prefix_keeps_tn():
    """O regex tolera o sufixo .exe no token de site e ainda extrai o tn."""
    out = table_ss.parse_table_ss_filename(
        "Winamax.exe-Winamax HIGHROLLER(1108710761)(#001)-20260609002319-68.png")
    assert out["site"] == "Winamax"
    assert out["tournament_number"] == "1108710761"


@patch("app.routers.table_ss.query")
def test_compute_filename_tn_authoritative_resolves(mock_q):
    """Novo Winamax com tn → resolve por tn (sem resolver-por-nome → sem ambíguo)."""
    mock_q.return_value = [{
        "id": 42, "hand_id": "WN-x", "tournament_number": "1106616980",
        "tournament_name": "ODYSSEY", "site": "Winamax",
        "played_at": datetime(2026, 6, 5, 17, 0, 40),
    }]
    cap = datetime(2026, 6, 5, 17, 0, 38)
    out = table_ss.compute_table_ss_match(
        cap, "Winamax", {"tournament_name": "ODYSSEY"}, filename_tn="1106616980")
    assert out["result"] == "success"
    assert out["tournament_number"] == "1106616980"
    assert out["matched_hand_db_id"] == 42
    assert out["reason_detail"] == "filename_tn"


@patch("app.routers.table_ss.query", return_value=[])
def test_compute_filename_tn_no_hand_for_tn(mock_q):
    cap = datetime(2026, 6, 5, 17, 0, 38)
    out = table_ss.compute_table_ss_match(
        cap, "Winamax", {"tournament_name": "ODYSSEY"}, filename_tn="9999999999")
    assert out["result"] == "no_match_to_hand"
    assert out["tournament_number"] == "9999999999"
    assert "no_hand_for_tn" in out["reason_detail"]
