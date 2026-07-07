"""#PAYOUT-COHERENCE — guarda de sanidade dos payouts Vision (a)+(b)+(c).

Unit da regra + lookup da referência + integração nos 3 call-sites (lobby live já
está em test_lobby_info_gate; aqui reconcile + backoffice)."""
from datetime import datetime
from unittest.mock import patch

from app.services import payout_coherence as pc
from app.services.payout_coherence import assert_payout_coherent

POSTED = datetime(2026, 7, 2, 19, 19, 25)


# ── assert_payout_coherent (a)+(b)+(c) ───────────────────────────────────────
def test_coherent_ladder_passes():
    prizes = {"1": 1998.54, "2": 1482.55, "3": 1099.81, "4": 815.87}
    assert assert_payout_coherent(prizes, 10000.0) == (True, None)


def test_a_prize_greater_than_pool():
    # fichas lidas como prémios: 269061 > pool 9494
    ok, reason = assert_payout_coherent({"1": 269061.0, "2": 242139.0}, 9494.0)
    assert ok is False and reason == "prize_gt_pool"


def test_b_sum_greater_than_pool_with_tolerance():
    # cada prémio < pool, mas a SOMA fura pool×1.05
    ok, reason = assert_payout_coherent({"1": 600.0, "2": 600.0}, 1000.0)
    assert ok is False and reason == "sum_gt_pool"
    # dentro da folga ×1.05 passa (soma 1040 <= 1050)
    assert assert_payout_coherent({"1": 540.0, "2": 500.0}, 1000.0) == (True, None)


def test_c_non_monotonic_ladder():
    # rank 2 > rank 1 → a escada sobe → incoerente
    ok, reason = assert_payout_coherent({"1": 100.0, "2": 200.0}, 10000.0)
    assert ok is False and reason == "non_monotonic"


def test_c_ties_are_allowed():
    # patamares iguais (ranks 3-5 = 50) são normais → passa
    prizes = {"1": 100.0, "2": 70.0, "3": 50.0, "4": 50.0, "5": 50.0}
    assert assert_payout_coherent(prizes, 10000.0) == (True, None)


def test_no_reference_or_no_prizes_does_not_judge():
    assert assert_payout_coherent({"1": 999999.0}, None) == (True, None)   # sem ref
    assert assert_payout_coherent({}, 1000.0) == (True, None)              # sem prémios
    assert assert_payout_coherent({"1": 1.0}, 0) == (True, None)           # ref <= 0


# ── _pool_ref: TS manda, senão a Vision ──────────────────────────────────────
def test_pool_ref_prefers_ts_over_vision():
    with patch.object(pc, "query", return_value=[{"prize_pool": 8000.0}]):
        assert pc._pool_ref("GGPoker", "1", {"prize_pool": 5000.0}) == 8000.0


def test_pool_ref_falls_back_to_vision_when_no_ts():
    with patch.object(pc, "query", return_value=[]):
        assert pc._pool_ref("GGPoker", "1", {"prize_pool": 5000.0}) == 5000.0


def test_pool_ref_survives_db_error():
    # DB indisponível → não rebenta, cai no prize_pool da Vision
    with patch.object(pc, "query", side_effect=RuntimeError("no db")):
        assert pc._pool_ref("GGPoker", "1", {"prize_pool": 5000.0}) == 5000.0


def test_check_vj_expands_ranges_before_judging():
    # prize_ranges desenrolados entram no juízo (o que vai para o blob)
    vj = {"prizes": {"1": 500.0}, "prize_ranges": [
        {"rank_from": 2, "rank_to": 3, "amount": 300.0}]}
    with patch.object(pc, "query", return_value=[{"prize_pool": 2000.0}]):
        assert pc.check_vj_payout_coherent("GGPoker", "1", vj) == (True, None)
    # se a faixa fura o pool → apanha
    with patch.object(pc, "query", return_value=[{"prize_pool": 900.0}]):
        ok, reason = pc.check_vj_payout_coherent("GGPoker", "1", vj)
        assert ok is False


# ── reconcile: incoerente não escreve ────────────────────────────────────────
def test_reconcile_incoherent_not_written():
    from app.services import lobby_sync
    row = {"discord_message_id": "h9", "site": "GGPoker",
           "tournament_name": "X", "posted_at": POSTED,
           "vision_json": {"site": "GGPoker", "prizes": {"1": 269061.0}},
           "result": "tm_not_found"}
    with patch.object(lobby_sync, "query", return_value=[row]), \
         patch.object(lobby_sync.tournament_resolver, "resolve_tournament_number",
                      return_value=("12345", [], "tier0")), \
         patch.object(lobby_sync, "_resolve_via_hero_anchor", return_value=None), \
         patch.object(lobby_sync, "check_vj_payout_coherent",
                      return_value=(False, "prize_gt_pool")), \
         patch.object(lobby_sync.payouts_service, "upsert_payout") as mpay, \
         patch.object(lobby_sync, "_upsert_lobby_log") as mlog:
        res = lobby_sync.reconcile_lobby_logs()
    assert res["incoherent"] == 1 and res["written"] == 0
    assert res["items"][0]["action"] == "payout_incoherent"
    mpay.assert_not_called()
    assert mlog.call_args.kwargs["result"] == "payout_incoherent"


# ── backoffice: incoerente não escreve ───────────────────────────────────────
def test_backoffice_incoherent_not_written():
    import asyncio
    from app.routers import tournament_results as tr
    vj = {"tournament_name": "X", "prize_pool": 9494.0, "total_players": 100,
          "prizes": {"1": 269061.0}}
    with patch.object(tr.bv, "extract_backoffice_payout_json", return_value="{}"), \
         patch.object(tr.bv, "parse_and_validate_backoffice_json", return_value=vj), \
         patch.object(tr.tournament_resolver, "resolve_tournament_number",
                      return_value=("12345", [])), \
         patch.object(tr, "_lookup_ts_meta", return_value={"tournament_format": "Vanilla"}), \
         patch.object(tr, "check_vj_payout_coherent",
                      return_value=(False, "prize_gt_pool")), \
         patch.object(tr.payouts_service, "upsert_payout") as mpay:
        out = asyncio.run(tr._process_one(
            "shot.png", b"x", dry_run=False, skip_existing=False, throttle=0.0))
    assert out["result"] == "payout_incoherent"
    assert out["error"] == "prize_gt_pool"
    mpay.assert_not_called()
