"""#LOBBY-INFO-NO-PAYOUT (regra 7 Jul; POR SALA desde 23 Jul) — na GG o print da aba
Info marca só o ARRANQUE da FT (fronteira + final_table_size) e NUNCA escreve
tournament_payouts; resolve o tn e grava vision_json/players_left. É lei DA GG:
nas outras salas (Winamax, …) o lobby é vista única e o print Info É a fonte
legítima de prémios — escreve normalmente. Prints de outras abas mantêm o
comportamento (payout + D11). Gate em process_lobby_message E reconcile_lobby_logs."""
import asyncio
from datetime import datetime
from unittest.mock import patch

PNG = b"\x89PNG\r\n\x1a\nx"
POSTED = datetime(2026, 7, 2, 19, 19, 25)   # Lisboa naive, 2026


def _run_full(vj, coherence=(True, None), **kw):
    """process_lobby_message com Vision/resolver/payout/coerência mockados; devolve
    (res, upsert_payout_mock, log_mock). `coherence` = veredicto da guarda de payouts."""
    from app.services import lobby_sync
    with patch.object(lobby_sync, "_upsert_lobby_log") as mlog, \
         patch.object(lobby_sync, "_resolve_via_hero_anchor", return_value=None), \
         patch.object(lobby_sync, "query", return_value=[]), \
         patch.object(lobby_sync, "check_vj_payout_coherent", return_value=coherence), \
         patch.object(lobby_sync.lobby_vision, "extract_lobby_payout_json", return_value="{}"), \
         patch.object(lobby_sync.lobby_vision, "parse_and_validate_lobby_json", return_value=vj), \
         patch.object(lobby_sync.lobby_vision, "build_hrc_payouts_blob",
                      return_value={"structures": [{}]}), \
         patch.object(lobby_sync.tournament_resolver, "resolve_tournament_number",
                      return_value=("295219051", [], "tier0")), \
         patch.object(lobby_sync.payouts_service, "upsert_payout",
                      return_value={"action": "inserted"}) as mpay:
        res = asyncio.run(lobby_sync.process_lobby_message(
            PNG, "image/png", message_id="h", channel_id=None, posted_at=POSTED, **kw))
    return res, mpay, mlog


# ── _is_info_tab (regra POR SALA: só a GG bloqueia) ──────────────────────────
def test_is_info_tab_unit():
    from app.services.lobby_sync import _is_info_tab
    assert _is_info_tab({"open_tab": "Info"}, "GGPoker") is True
    assert _is_info_tab({"open_tab": " Info "}, "GGPoker") is True    # trim
    assert _is_info_tab({"open_tab": "Prize Pool"}, "GGPoker") is False
    assert _is_info_tab({"open_tab": None}, "GGPoker") is False
    assert _is_info_tab({}, "GGPoker") is False
    assert _is_info_tab(None, "GGPoker") is False
    # regra do Rui (23 Jul): Info-não-escreve é lei DA GG — outras salas passam
    assert _is_info_tab({"open_tab": "Info"}, "Winamax") is False
    assert _is_info_tab({"open_tab": "Info"}, "PokerStars") is False
    assert _is_info_tab({"open_tab": "Info"}, None) is False


# ── process_lobby_message ─────────────────────────────────────────────────────
def test_info_tab_resolves_but_writes_no_payout():
    vj = {"site": "GGPoker", "tournament_name": "Daily Hyper $60",
          "open_tab": "Info", "final_table_size": 7, "players_left": 7}
    res, mpay, mlog = _run_full(vj)
    assert res["result"] == "success"
    assert res["reason_detail"] == "info_tab_no_payout"
    assert res["tournament_number"] == "295219051"   # resolve o tn na mesma
    assert res["action"] is None
    mpay.assert_not_called()                          # NUNCA escreve payout
    # grava o log com o tn + vision_json (o motor FT lê open_tab/final_table_size daí)
    assert mlog.call_args.kwargs["tournament_number"] == "295219051"
    assert mlog.call_args.kwargs["vision_json"] == vj
    assert mlog.call_args.kwargs["players_left"] == 7


def test_winamax_info_tab_writes_payout():
    # regra POR SALA (23 Jul): na WN o lobby é vista única (info + escada juntas,
    # a Vision marca 'Info' na mesma) e o print É a fonte legítima de prémios —
    # o gate do Info NÃO dispara fora da GG.
    vj = {"site": "Winamax", "tournament_name": "ZENITH",
          "open_tab": "Info", "final_table_size": 7, "players_left": 86,
          "prizes": {"1": 1495.18}, "prize_pool": 18270.0}
    res, mpay, _ = _run_full(vj)
    assert res["result"] == "success"
    assert res["reason_detail"] != "info_tab_no_payout"
    mpay.assert_called_once()                          # ESCREVE payout


def test_prizepool_tab_still_writes_payout():
    vj = {"site": "GGPoker", "tournament_name": "Daily Hyper $60",
          "open_tab": "Prize Pool", "players_left": 107, "prizes": {"1": 100.0}}
    res, mpay, _ = _run_full(vj)
    assert res["result"] == "success"
    mpay.assert_called_once()                          # comportamento actual preservado


def test_no_open_tab_still_writes_payout():
    # prints antigos / Discord (sem open_tab) → comportamento inalterado
    vj = {"site": "GGPoker", "tournament_name": "Daily Hyper $60",
          "players_left": 50, "prizes": {"1": 100.0}}
    _, mpay, _ = _run_full(vj)
    mpay.assert_called_once()


def test_incoherent_payout_not_written():
    # #PAYOUT-COHERENCE — guarda diz incoerente → NÃO escreve, log payout_incoherent.
    vj = {"site": "GGPoker", "tournament_name": "Daily Hyper $60",
          "open_tab": "Prize Pool", "prizes": {"1": 269061.0}}
    res, mpay, mlog = _run_full(vj, coherence=(False, "prize_gt_pool"))
    assert res["result"] == "payout_incoherent"
    assert res["reason_detail"] == "prize_gt_pool"
    mpay.assert_not_called()
    assert mlog.call_args.kwargs["result"] == "payout_incoherent"


# ── reconcile_lobby_logs ──────────────────────────────────────────────────────
def test_reconcile_info_tab_resolves_without_payout():
    from app.services import lobby_sync
    row = {"discord_message_id": "h1", "site": "GGPoker",
           "tournament_name": "Daily Hyper $60", "posted_at": POSTED,
           "vision_json": {"site": "GGPoker", "open_tab": "Info",
                           "final_table_size": 7, "players_left": 7},
           "result": "tm_not_found"}
    with patch.object(lobby_sync, "query", return_value=[row]), \
         patch.object(lobby_sync.tournament_resolver, "resolve_tournament_number",
                      return_value=("295219051", [], "tier0")), \
         patch.object(lobby_sync, "_resolve_via_hero_anchor", return_value=None), \
         patch.object(lobby_sync.payouts_service, "upsert_payout") as mpay, \
         patch.object(lobby_sync, "_upsert_lobby_log") as mlog:
        res = lobby_sync.reconcile_lobby_logs()
    assert res["resolved"] == 1 and res["written"] == 0
    assert res["items"][0]["action"] == "info_ft_marker"
    mpay.assert_not_called()                           # reconcile também não escreve
    assert mlog.call_args.kwargs["tournament_number"] == "295219051"


def test_reconcile_winamax_info_tab_writes_payout():
    # regra POR SALA (23 Jul): no reconcile, um print WN com open_tab='Info'
    # escreve os prémios (era a única fonte da WN; a guarda global matava-a).
    from app.services import lobby_sync
    row = {"discord_message_id": "w1", "site": "Winamax",
           "tournament_name": "ZENITH", "posted_at": POSTED,
           "vision_json": {"site": "Winamax", "open_tab": "Info",
                           "players_left": 86, "prize_pool": 18270.0,
                           "prizes": {"1": 1495.18}},
           "result": "success"}

    def _q(sql, params=None):
        if "FROM lobby_processing_log" in sql:
            return [row]
        return []                                       # sem payout existente (D11 passa)

    with patch.object(lobby_sync, "query", side_effect=_q), \
         patch.object(lobby_sync.tournament_resolver, "resolve_tournament_number",
                      return_value=("1115698797", [], "tier2")), \
         patch.object(lobby_sync, "_resolve_via_hero_anchor", return_value=None), \
         patch.object(lobby_sync, "check_vj_payout_coherent", return_value=(True, None)), \
         patch.object(lobby_sync.lobby_vision, "build_hrc_payouts_blob",
                      return_value={"structures": [{}]}), \
         patch.object(lobby_sync.payouts_service, "upsert_payout",
                      return_value={"action": "inserted"}) as mpay, \
         patch.object(lobby_sync, "_upsert_lobby_log"):
        res = lobby_sync.reconcile_lobby_logs(message_ids=["w1"])
    assert res["written"] == 1
    mpay.assert_called_once()
    assert mpay.call_args.kwargs.get("site") == "Winamax" \
        or "Winamax" in mpay.call_args.args
