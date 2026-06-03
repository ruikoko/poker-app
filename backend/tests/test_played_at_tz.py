"""Fuso de played_at (#GG-PLAYED-AT-LOCAL-NOT-UTC).

GG e PS gravam a hora da HH em hora local de Lisboa; os parsers normalizam para
UTC DST-aware (Verão −1h, Inverno 0h). Winamax/WPN trazem UTC explícito → naive
sem conversão. Testa a LÓGICA, independente dos dados.
"""
from datetime import datetime, timezone

from app.utils.timezones import lisbon_local_to_utc
from app.parsers.gg_hands import parse_hands
from app.routers.hm3 import _parse_hand


def _utc(y, mo, d, h, mi, s):
    return datetime(y, mo, d, h, mi, s, tzinfo=timezone.utc)


# ── helper partilhado lisbon_local_to_utc ───────────────────────────────────

def test_summer_subtracts_1h():
    assert lisbon_local_to_utc(datetime(2026, 5, 31, 17, 42, 42)) == _utc(2026, 5, 31, 16, 42, 42)


def test_winter_no_offset():
    assert lisbon_local_to_utc(datetime(2026, 1, 15, 17, 42, 42)) == _utc(2026, 1, 15, 17, 42, 42)


def test_dst_aware_uses_hand_date_not_fixed_offset():
    """Mesma hora-de-relógio → UTC diferente consoante a data: DST-aware (não é
    offset fixo nem a data de 'agora')."""
    summer = lisbon_local_to_utc(datetime(2026, 7, 1, 20, 0, 0))
    winter = lisbon_local_to_utc(datetime(2026, 12, 1, 20, 0, 0))
    assert summer == _utc(2026, 7, 1, 19, 0, 0)
    assert winter == _utc(2026, 12, 1, 20, 0, 0)
    assert (summer.hour, winter.hour) == (19, 20)


def test_just_after_spring_forward_is_summer():
    # DST UE 2026: spring-forward 29 Mar → 30 Mar já é WEST (−1h).
    assert lisbon_local_to_utc(datetime(2026, 3, 30, 12, 0, 0)) == _utc(2026, 3, 30, 11, 0, 0)


def test_just_before_spring_forward_is_winter():
    assert lisbon_local_to_utc(datetime(2026, 3, 28, 12, 0, 0)) == _utc(2026, 3, 28, 12, 0, 0)


def test_result_is_utc_tzaware():
    r = lisbon_local_to_utc(datetime(2026, 5, 31, 17, 42, 42))
    assert r.utcoffset().total_seconds() == 0


# ── GG: parse_hands devolve played_at em UTC ────────────────────────────────

_GG_BLOCK = (
    "Poker Hand #TM6021825338: Tournament #287210981, Daily Hyper $50 Hold'em "
    "No Limit - Level11(250/500(60)) - 2026/05/31 17:42:42\n"
    "Table '31' 6-max Seat #2 is the button\n"
    "Seat 1: 769c1d67 (6000 in chips)\n"
    "Seat 4: Hero (6000 in chips)\n"
    "*** HOLE CARDS ***\n"
    "Dealt to Hero [Ah Kh]\n"
    "*** SUMMARY ***\n"
)


def test_gg_played_at_utc_summer():
    hands, _ = parse_hands(_GG_BLOCK.encode("utf-8"), "t.txt")
    assert hands and hands[0]["played_at"].startswith("2026-05-31T16:42:42")


def test_gg_played_at_utc_winter():
    block = _GG_BLOCK.replace("2026/05/31 17:42:42", "2026/01/15 17:42:42")
    hands, _ = parse_hands(block.encode("utf-8"), "t.txt")
    assert hands and hands[0]["played_at"].startswith("2026-01-15T17:42:42")


# ── PS: _parse_hand converte a 1ª timestamp (WET/Lisboa) → UTC ──────────────

_PS_BLOCK = (
    "PokerStars Hand #260988837997: Tournament #4002440970, €45+€45+€10 EUR "
    "Hold'em No Limit - Level VIII (500/1000) - 2026/05/31 18:20:32 WET "
    "[2026/05/31 13:20:32 ET]\n"
    "Table '4002440970 5' 9-max Seat #1 is the button\n"
    "Seat 1: Hero (100000 in chips)\n"
    "*** HOLE CARDS ***\n"
    "*** SUMMARY ***\n"
)


def test_ps_played_at_utc_summer():
    # 18:20:32 WET (Verão = WEST) → 17:20:32 UTC. (O bracket ET é ignorado.)
    r = _parse_hand(_PS_BLOCK, "PokerStars")
    assert r and r["played_at"].startswith("2026-05-31T17:20:32")


def test_ps_played_at_utc_winter():
    block = _PS_BLOCK.replace("2026/05/31 18:20:32 WET", "2026/01/15 18:20:32 WET")
    r = _parse_hand(block, "PokerStars")
    # Inverno (WET=UTC) → sem mudança.
    assert r and r["played_at"].startswith("2026-01-15T18:20:32")


# ── Winamax: UTC explícito → NÃO converter (guard) ──────────────────────────

_WN_BLOCK = (
    'Winamax Poker - Tournament "MAIN" buyIn: 5€ level: 1 - '
    "HandId: #4742042240115802195-78-1780256415 - Holdem no limit (10/20) - "
    "2026/05/31 19:40:15 UTC\n"
    "Table: 'MAIN(287)#3' 6-max\n"
    "Seat 1: Hero (6000)\n"
    "*** PRE-FLOP ***\n"
)


def test_winamax_played_at_unchanged_utc():
    r = _parse_hand(_WN_BLOCK, "Winamax")
    # Já é UTC na HH; o parser mantém-no (sem subtrair 1h).
    assert r and r["played_at"].startswith("2026-05-31T19:40:15")
