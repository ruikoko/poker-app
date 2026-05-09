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

from app.routers.tournament_summaries import (
    parse_tournament_summary,
    _parse_buy_in,
    import_tournament_summaries,
)


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
    assert p["start_time"] == datetime(2026, 3, 31, 19, 45, tzinfo=timezone.utc)
    assert p["hero_position"] == 42
    assert p["hero_payout"] == Decimal("0")
    assert p["hero_re_entries"] == 0
    assert p["source_filename"] == "vanilla.txt"
    assert p["raw_text"] == TS_VANILLA


def test_parse_pre_2026_returns_dt_unfiltered():
    """Parser nao rejeita pre-2026 — filter e responsabilidade do endpoint."""
    p = parse_tournament_summary(TS_PRE_2026)
    assert p["start_time"] == datetime(2025, 12, 15, 18, 0, tzinfo=timezone.utc)


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


def test_parse_mystery_3_parts_buyin():
    p = parse_tournament_summary(TS_MYSTERY_3PARTS)
    assert p["tournament_number"] == "281143347"
    assert p["buy_in_total"] == Decimal("55.0")
    assert p["prize_pool"] == Decimal("604214.6")


def test_parse_re_entries_count():
    p = parse_tournament_summary(TS_RE_ENTRY)
    assert p["hero_re_entries"] == 1


def test_parse_complex_tournament_name_brackets():
    p = parse_tournament_summary(TS_BRACKETS)
    assert p["tournament_name"] == "Speed Racer Bounty Europe $108 [10 BB]"


def test_parse_prize_pool_with_thousands_separator():
    p = parse_tournament_summary(TS_MYSTERY_3PARTS)
    assert p["prize_pool"] == Decimal("604214.6")


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
    """Mock conn cujo cursor.fetchone segue side_effect (lista de tuplas)."""
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
    conn = _mock_conn([(True,)])  # só 1 INSERT chega ao SQL

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
    conn = _mock_conn([(True,), (False,)])  # 1ª insert, 2ª update

    with patch("app.routers.tournament_summaries.get_conn", return_value=conn):
        r1 = asyncio.run(import_tournament_summaries(
            file=_FakeUploadFile("ts.txt", payload), current_user={"id": 1}
        ))
        r2 = asyncio.run(import_tournament_summaries(
            file=_FakeUploadFile("ts.txt", payload), current_user={"id": 1}
        ))

    assert r1["inserted"] == 1 and r1["updated"] == 0
    assert r2["inserted"] == 0 and r2["updated"] == 1
