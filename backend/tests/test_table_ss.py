"""Tests para routers/table_ss + integração com queue_export/hrc_queue (pt38).

Pattern de mocks alinhado com test_lobby_sync.py (asyncio.run + unittest.mock).
"""
import asyncio
import json
from datetime import datetime, timezone
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
    def fake_find(captured_at, site):
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
