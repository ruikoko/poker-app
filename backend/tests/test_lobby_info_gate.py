"""#LOBBY-INFO-NO-PAYOUT (regra 7 Jul) — o print da aba Info marca só o ARRANQUE da
FT (fronteira + final_table_size) e NUNCA escreve tournament_payouts; resolve o tn e
grava vision_json/players_left. Prints de outras abas mantêm o comportamento (payout
+ D11). Gate em process_lobby_message E reconcile_lobby_logs."""
import asyncio
from datetime import datetime
from unittest.mock import patch

PNG = b"\x89PNG\r\n\x1a\nx"
POSTED = datetime(2026, 7, 2, 19, 19, 25)   # Lisboa naive, 2026


def _run_full(vj, **kw):
    """process_lobby_message com Vision/resolver/payout mockados; devolve
    (res, upsert_payout_mock, log_mock)."""
    from app.services import lobby_sync
    with patch.object(lobby_sync, "_upsert_lobby_log") as mlog, \
         patch.object(lobby_sync, "_resolve_via_hero_anchor", return_value=None), \
         patch.object(lobby_sync, "query", return_value=[]), \
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


# ── _is_info_tab ─────────────────────────────────────────────────────────────
def test_is_info_tab_unit():
    from app.services.lobby_sync import _is_info_tab
    assert _is_info_tab({"open_tab": "Info"}) is True
    assert _is_info_tab({"open_tab": " Info "}) is True    # trim
    assert _is_info_tab({"open_tab": "Prize Pool"}) is False
    assert _is_info_tab({"open_tab": None}) is False
    assert _is_info_tab({}) is False
    assert _is_info_tab(None) is False


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
