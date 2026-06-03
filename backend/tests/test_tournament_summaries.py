"""Unit tests para routers/tournament_summaries (FASE B B1).

Fixtures sao sinteticas mas estruturalmente identicas aos samples reais
analisados pelo Web (vanilla, PKO 3-partes, Mystery 3-partes, re-entry,
nome com brackets). Tests do endpoint usam mocks de get_conn — sem DB
real, consistente com test_tournament_resolver.py.
"""
import asyncio
import io
import zipfile
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch, MagicMock

import pytest

from pathlib import Path

from app.routers.tournament_summaries import (
    parse_tournament_summary,
    parse_winamax_tournament_summary,
    _parse_ts_by_site,
    _parse_buy_in,
    import_tournament_summaries,
)

_FIXTURES = Path(__file__).parent / "fixtures"


# ── Fixtures (sinteticas) ────────────────────────────────────────────

TS_VANILLA = """\
Tournament #273674859, Daily Hyper $80, Hold'em No Limit
Buy-in: $73.6+$6.4
108 Players
Total Prize Pool: $7,948.8
Tournament started 2026/03/31 19:45:00
42th : Hero, $0
You finished the tournament in 42th place.
You received a total of $0.
"""

TS_PKO_3PARTS = """\
Tournament #282066003, Bounty Hunters Deepstack Turbo $88, Hold'em No Limit
Buy-in: $40.96+$7.04+$40
523 Players
Total Prize Pool: $46,024.0
Tournament started 2026/05/01 14:00:00
12th : Hero, $40
You finished the tournament in 12th place.
You received a total of $40.
"""

TS_MYSTERY_3PARTS = """\
Tournament #281143347, 12-M: $55 Sunday Showdown [Mystery Bounty], Hold'em No Limit
Buy-in: $25.3+$4.4+$25.3
12104 Players
Total Prize Pool: $604,214.6
Tournament started 2026/05/03 17:00:00
358th : Hero, $0
You finished the tournament in 358th place.
You received a total of $0.
"""

TS_RE_ENTRY = """\
Tournament #281797410, Daily Hyper $80, Hold'em No Limit
Buy-in: $73.6+$6.4
93 Players
Total Prize Pool: $13,690.4
Tournament started 2026/05/05 17:10:00
3rd : Hero, $185.56
You finished the tournament in 3rd place.
You made 1 re-entries and received a total of $185.56.
"""

TS_BRACKETS = """\
Tournament #281017175, Speed Racer Bounty Europe $108 [10 BB], Hold'em No Limit
Buy-in: $49.36+$8.64+$50
260 Players
Total Prize Pool: $13,520.0
Tournament started 2026/05/03 21:45:00
55th : Hero, $0
You finished the tournament in 55th place.
You received a total of $0.
"""

TS_PRE_2026 = """\
Tournament #99999999, Old Tournament, Hold'em No Limit
Buy-in: $10+$1
50 Players
Total Prize Pool: $500
Tournament started 2025/12/15 18:00:00
20th : Hero, $0
You finished the tournament in 20th place.
You received a total of $0.
"""

TS_MISSING_TN = """\
Buy-in: $10+$1
Tournament started 2026/03/31 19:45:00
"""

TS_MISSING_START = """\
Tournament #99999998, Some Tournament, Hold'em No Limit
Buy-in: $10+$1
50 Players
Total Prize Pool: $500
1st : Hero, $250
You received a total of $250.
"""


# ── Parser tests (vanilla + edge cases) ──────────────────────────────

def test_parse_vanilla_sample_real():
    p = parse_tournament_summary(TS_VANILLA, "vanilla.txt")
    assert p["site"] == "GGPoker"
    assert p["tournament_number"] == "273674859"
    assert p["tournament_name"] == "Daily Hyper $80"
    assert p["buy_in_text"] == "$73.6+$6.4"
    assert p["buy_in_total"] == Decimal("80.0")
    assert p["buy_in_currency"] == "USD"
    assert p["total_players"] == 108
    assert p["prize_pool"] == Decimal("7948.8")
    assert p["start_time"] == datetime(2026, 3, 31, 19, 45)  # pt51: Lisboa naive
    assert p["hero_position"] == 42
    assert p["hero_payout"] == Decimal("0")
    assert p["hero_re_entries"] == 0
    assert p["source_filename"] == "vanilla.txt"
    assert p["raw_text"] == TS_VANILLA
    # B1.x — 12 campos novos
    assert p["game_type"] == "Hold'em No Limit"
    assert p["buy_in_entry"] == Decimal("73.6")
    assert p["buy_in_rake"] == Decimal("6.4")
    assert p["buy_in_bounty"] is None
    assert p["hero_total_received"] == Decimal("0")
    assert p["hero_finish_phrase_position"] == 42
    assert p["tournament_modifiers"] == []
    assert p["tournament_series"] is None
    assert p["tournament_speed"] == "Hyper"
    assert p["tournament_schedule"] == "Daily"
    assert p["tournament_format"] == "None"
    assert p["tournament_pko_ratio"] is None


def test_parse_pre_2026_returns_dt_unfiltered():
    """Parser nao rejeita pre-2026 — filter e responsabilidade do endpoint."""
    p = parse_tournament_summary(TS_PRE_2026)
    assert p["start_time"] == datetime(2025, 12, 15, 18, 0)  # pt51: Lisboa naive


def test_parse_missing_tournament_number_raises():
    with pytest.raises(ValueError, match="missing tournament_number"):
        parse_tournament_summary(TS_MISSING_TN)


def test_parse_missing_start_time_raises():
    with pytest.raises(ValueError, match="missing start_time"):
        parse_tournament_summary(TS_MISSING_START)


@pytest.mark.parametrize("ord_str,expected_pos", [
    ("1st", 1), ("2nd", 2), ("3rd", 3), ("42th", 42), ("108th", 108),
])
def test_parse_hero_position_ordinals(ord_str, expected_pos):
    txt = (
        "Tournament #99, X, Hold'em No Limit\n"
        "Buy-in: $10+$1\n"
        "100 Players\n"
        "Total Prize Pool: $1000\n"
        "Tournament started 2026/03/31 19:45:00\n"
        f"{ord_str} : Hero, $50\n"
        "You received a total of $50.\n"
    )
    p = parse_tournament_summary(txt)
    assert p["hero_position"] == expected_pos


def test_parse_buy_in_with_rake():
    total, currency = _parse_buy_in("$73.6+$6.4")
    assert total == Decimal("80.0")
    assert currency == "USD"


# ── Tests baseados em variantes confirmadas pelo Web ─────────────────

def test_parse_pko_3_parts_buyin():
    p = parse_tournament_summary(TS_PKO_3PARTS)
    assert p["tournament_number"] == "282066003"
    assert p["buy_in_total"] == Decimal("88.00")
    assert p["hero_payout"] == Decimal("40")
    # B1.x
    assert p["buy_in_entry"] == Decimal("40.96")
    assert p["buy_in_rake"] == Decimal("7.04")
    assert p["buy_in_bounty"] == Decimal("40")
    assert p["tournament_speed"] == "Turbo"  # "turbo" bate antes de "deepstack"
    assert p["tournament_format"] == "PKO"
    assert p["tournament_pko_ratio"] == Decimal("0.50")
    assert p["tournament_modifiers"] == []


def test_parse_mystery_3_parts_buyin():
    p = parse_tournament_summary(TS_MYSTERY_3PARTS)
    assert p["tournament_number"] == "281143347"
    assert p["buy_in_total"] == Decimal("55.0")
    assert p["prize_pool"] == Decimal("604214.6")
    # B1.x
    assert p["buy_in_entry"] == Decimal("25.3")
    assert p["buy_in_rake"] == Decimal("4.4")
    assert p["buy_in_bounty"] == Decimal("25.3")
    assert p["tournament_modifiers"] == ["Mystery Bounty"]
    assert p["tournament_series"] == "12-M"
    assert p["tournament_schedule"] == "Sunday"
    assert p["tournament_format"] == "KO"
    assert p["tournament_pko_ratio"] == Decimal("0.33")


def test_parse_re_entries_count():
    p = parse_tournament_summary(TS_RE_ENTRY)
    assert p["hero_re_entries"] == 1
    # B1.x — cross-check: total_received bate com hero_payout mesmo com re-entry
    assert p["hero_total_received"] == Decimal("185.56")
    assert p["hero_total_received"] == p["hero_payout"]


def test_parse_complex_tournament_name_brackets():
    p = parse_tournament_summary(TS_BRACKETS)
    assert p["tournament_name"] == "Speed Racer Bounty Europe $108 [10 BB]"
    # B1.x
    assert p["tournament_modifiers"] == ["10 BB"]
    assert p["tournament_speed"] == "Hyper"  # "speed racer" branded -> Hyper
    assert p["tournament_format"] == "PKO"   # "Bounty" no nome
    assert p["tournament_pko_ratio"] == Decimal("0.50")


def test_parse_prize_pool_with_thousands_separator():
    p = parse_tournament_summary(TS_MYSTERY_3PARTS)
    assert p["prize_pool"] == Decimal("604214.6")


# ── B1.x: cross-check defensivos ────────────────────────────────────

def test_parse_buy_in_split_sums_to_total():
    """Cross-check: buy_in_entry + buy_in_rake + (buy_in_bounty or 0)
    deve igualar buy_in_total para todos os 5 samples."""
    for fixture_name, fixture in [
        ("TS_VANILLA", TS_VANILLA),
        ("TS_PKO_3PARTS", TS_PKO_3PARTS),
        ("TS_MYSTERY_3PARTS", TS_MYSTERY_3PARTS),
        ("TS_RE_ENTRY", TS_RE_ENTRY),
        ("TS_BRACKETS", TS_BRACKETS),
    ]:
        p = parse_tournament_summary(fixture)
        parts_sum = (
            (p["buy_in_entry"] or Decimal(0))
            + (p["buy_in_rake"] or Decimal(0))
            + (p["buy_in_bounty"] or Decimal(0))
        )
        assert parts_sum == p["buy_in_total"], \
            f"split mismatch in {fixture_name}: parts={parts_sum} total={p['buy_in_total']}"


def test_parse_hero_total_received_matches_hero_payout():
    """Cross-check: hero_total_received da ultima linha == hero_payout
    da linha 'Nth : Hero, $X' em todos os samples (mesmo com re-entry)."""
    for fixture_name, fixture in [
        ("TS_VANILLA", TS_VANILLA),
        ("TS_PKO_3PARTS", TS_PKO_3PARTS),
        ("TS_MYSTERY_3PARTS", TS_MYSTERY_3PARTS),
        ("TS_RE_ENTRY", TS_RE_ENTRY),
        ("TS_BRACKETS", TS_BRACKETS),
    ]:
        p = parse_tournament_summary(fixture)
        assert p["hero_total_received"] == p["hero_payout"], \
            f"discrepancy in {fixture_name}: total_received={p['hero_total_received']} hero_payout={p['hero_payout']}"


# ── Endpoint tests (mocked DB) ───────────────────────────────────────

class _FakeUploadFile:
    """Stub mínimo para UploadFile sem dependências da Starlette internals."""
    def __init__(self, filename: str, content: bytes):
        self.filename = filename
        self._content = content

    async def read(self) -> bytes:
        return self._content


def _zip_bytes(files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files:
            zf.writestr(name, content)
    return buf.getvalue()


def _mock_conn(fetchone_side_effect):
    """Mock conn cujo cursor.fetchone segue side_effect (lista de dicts).

    Reflecte RealDictCursor (default do projecto): cur.fetchone()
    devolve dict com chaves de coluna, não tupla.
    """
    cur = MagicMock()
    cur.fetchone.side_effect = list(fetchone_side_effect)
    cur.__enter__ = MagicMock(return_value=cur)
    cur.__exit__ = MagicMock(return_value=False)
    conn = MagicMock()
    conn.cursor.return_value = cur
    return conn


def test_endpoint_zip_with_mixed_pre_post_2026():
    """ZIP com 1 valido 2026 + 1 pre-2026 -> inserted=1, skipped=1."""
    zip_bytes = _zip_bytes([
        ("ts1.txt", TS_VANILLA),
        ("ts2_pre.txt", TS_PRE_2026),
    ])
    upload = _FakeUploadFile("batch.zip", zip_bytes)
    conn = _mock_conn([{"inserted": True}])  # só 1 INSERT chega ao SQL

    with patch("app.routers.tournament_summaries.get_conn", return_value=conn):
        result = asyncio.run(
            import_tournament_summaries(file=upload, current_user={"id": 1})
        )

    assert result["total"] == 2
    assert result["inserted"] == 1
    assert result["updated"] == 0
    assert result["skipped_pre_2026"] == 1
    assert result["failed"] == []


def test_endpoint_idempotency():
    """1ª upload = inserted; 2ª upload mesmo TS = updated."""
    payload = TS_VANILLA.encode("utf-8")
    conn = _mock_conn([{"inserted": True}, {"inserted": False}])  # 1ª insert, 2ª update

    with patch("app.routers.tournament_summaries.get_conn", return_value=conn):
        r1 = asyncio.run(import_tournament_summaries(
            file=_FakeUploadFile("ts.txt", payload), current_user={"id": 1}
        ))
        r2 = asyncio.run(import_tournament_summaries(
            file=_FakeUploadFile("ts.txt", payload), current_user={"id": 1}
        ))

    assert r1["inserted"] == 1 and r1["updated"] == 0
    assert r2["inserted"] == 0 and r2["updated"] == 1


# ── #WINAMAX-TOURNAMENT-SUMMARIES-PIPELINE — parser WN (fixture ZENITH real) ──

def test_parse_winamax_ts_zenith_real():
    """ZENITH(1102500091) real. Ordem buy-in WN [entry, bounty, rake]."""
    txt = (_FIXTURES / "winamax_ts_zenith.txt").read_text(encoding="utf-8")
    d = parse_winamax_tournament_summary(txt, "winamax_ts_zenith.txt")
    assert d["site"] == "Winamax"
    assert d["tournament_number"] == "1102500091"
    assert d["tournament_name"] == "ZENITH"
    # split 40€ + 50€ + 10€ -> [entry, bounty, rake]
    assert d["buy_in_entry"] == Decimal("40")
    assert d["buy_in_bounty"] == Decimal("50")
    assert d["buy_in_rake"] == Decimal("10")
    assert d["buy_in_total"] == Decimal("100")
    assert d["buy_in_currency"] == "EUR"
    assert d["total_players"] == 133
    assert d["prize_pool"] == Decimal("6240")
    # pt51: TS WN traz 16:00:00 UTC → Lisboa (Verão) = 17:00:00 naive.
    assert d["start_time"] == datetime(2026, 5, 28, 17, 0, 0)
    assert d["hero_position"] == 6
    assert d["hero_payout"] == Decimal("278.95")
    assert d["hero_total_received"] == Decimal("342.95")   # prize + bounty 64
    assert d["tournament_format"] == "PKO"
    assert d["tournament_speed"] == "normal"   # valor cru, sem mapa GG
    assert d["tournament_pko_ratio"] is None   # decisão: split carrega a info
    assert d["game_type"] is None


def test_winamax_ts_tn_matches_hh():
    """Cross-validação: o TN do TS bate com o do HH (Table name)."""
    import re
    ts = (_FIXTURES / "winamax_ts_zenith.txt").read_text(encoding="utf-8")
    hh = (_FIXTURES / "winamax_hh_zenith.txt").read_text(encoding="utf-8")
    ts_tn = parse_winamax_tournament_summary(ts)["tournament_number"]
    hh_tn = re.search(r"Table:\s*'[^(]+\((\d+)\)#", hh).group(1)
    assert ts_tn == hh_tn == "1102500091"


def test_parse_winamax_ts_two_components_no_bounty():
    """TS WN não-KO (2 componentes) -> sem bounty, format Vanilla."""
    synthetic = (
        "Winamax Poker - Tournament summary : DAILY FREEROLL(999000111)\n"
        "Buy-In : 9€ + 1€\n"
        "Registered players : 50\n"
        "Type : normal\n"
        "Speed : turbo\n"
        "Prizepool : 450€\n"
        "Tournament started 2026/04/10 20:00:00 UTC\n"
        "You finished in 3rd place\n"
        "You won 60€\n"
    )
    d = parse_winamax_tournament_summary(synthetic, "x.txt")
    assert d["buy_in_entry"] == Decimal("9")
    assert d["buy_in_rake"] == Decimal("1")
    assert d["buy_in_bounty"] is None
    assert d["tournament_format"] == "Vanilla"
    assert d["tournament_speed"] == "turbo"
    assert d["hero_payout"] == Decimal("60")
    assert d["hero_total_received"] == Decimal("60")


def test_parse_ts_by_site_dispatch():
    """Sniff de conteúdo: WN -> parser WN; GG -> parser GG (default)."""
    wn = (_FIXTURES / "winamax_ts_zenith.txt").read_text(encoding="utf-8")
    assert _parse_ts_by_site(wn)["site"] == "Winamax"
    assert _parse_ts_by_site(TS_VANILLA)["site"] == "GGPoker"
