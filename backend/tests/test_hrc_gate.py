"""pt41 #HERO-BOUNTY-FROM-TS-DERIVATION — gate Andar 1 (bounty exige TS, Mystery
excluído) + lookup_bounties + pending_ts_hands. Mocka `query` (sem DB)."""
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch

from app.services import hrc_queue


def test_andar1_sql_has_bounty_gate_and_params():
    """O SQL do Andar 1 aplica: Mystery fora + GG bounty-gated exige TS com
    buy_in_bounty. Params terminam em MYSTERY_FORMATS, TS_GATED_FORMATS."""
    captured = {}

    def fake_query(sql, params):
        captured["sql"] = sql
        captured["params"] = params
        return []

    dt = datetime(2026, 5, 1, tzinfo=timezone.utc)
    with patch("app.services.hrc_queue.query", side_effect=fake_query):
        hrc_queue.select_andar1_rows(["icm pko"], ["new"], dt, dt)

    sql = captured["sql"]
    assert "tournament_summaries" in sql
    assert "buy_in_bounty IS NOT NULL" in sql
    assert "<> ALL(%s::text[])" in sql            # mystery + ts_gated exclusions
    assert "site <> 'GGPoker'" in sql             # gate é GG-only (Winamax/PS passam)
    assert captured["params"][-2] == list(hrc_queue.MYSTERY_FORMATS)
    assert captured["params"][-1] == list(hrc_queue.TS_GATED_FORMATS)


def test_lookup_bounties_maps_and_coerces_decimal():
    rows = [
        {"site": "GGPoker", "tournament_number": "T1",
         "buy_in_bounty": Decimal("100.00"), "tournament_format": "PKO"},
        {"site": "GGPoker", "tournament_number": "T2",
         "buy_in_bounty": None, "tournament_format": "None"},
    ]
    with patch("app.services.hrc_queue.query", return_value=rows):
        out = hrc_queue.lookup_bounties([
            {"site": "GGPoker", "tournament_number": "T1"},
            {"site": "GGPoker", "tournament_number": "T2"},
        ])
    assert out[("GGPoker", "T1")]["starting_bounty"] == 100.0
    assert isinstance(out[("GGPoker", "T1")]["starting_bounty"], float)
    assert out[("GGPoker", "T2")]["starting_bounty"] is None


def test_lookup_bounties_empty_without_keys():
    assert hrc_queue.lookup_bounties([]) == {}
    assert hrc_queue.lookup_bounties(
        [{"site": None, "tournament_number": None}]) == {}


def test_pending_ts_hands_reason_mapping():
    rows = [
        {"tn": "T1", "tournament_name": "Bounty Hunters $88",
         "fmt": "pko", "n_hands": 99},
        {"tn": "T2", "tournament_name": "Sunday [Mystery Bounty]",
         "fmt": "mystery ko", "n_hands": 214},
    ]
    with patch("app.services.hrc_queue.query", return_value=rows):
        out = hrc_queue.pending_ts_hands()
    by_tn = {g["tournament_number"]: g for g in out}
    assert by_tn["T1"]["reason"] == "needs_ts_import"
    assert by_tn["T2"]["reason"] == "mystery_unsupported"
    assert by_tn["T1"]["n_hands"] == 99
