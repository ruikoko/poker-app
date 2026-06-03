"""Convenção de fuso = LISBOA naive (pt51).

GG/PokerStars: a HH já vem em Lisboa → played_at gravado VERBATIM (naive, sem
conversão; a ambiguidade de Inverno deixa de existir). Winamax/WPN: a HH vem em
UTC → converte-se UTC→Lisboa. Testa a LÓGICA, independente dos dados.
"""
from datetime import datetime, timezone

from app.utils.timezones import lisbon_naive_verbatim, utc_to_lisbon_naive
from app.parsers.gg_hands import parse_hands
from app.routers.hm3 import _parse_hand


# ── helpers de fuso ─────────────────────────────────────────────────────────

def test_verbatim_strips_tz_keeps_wallclock():
    # GG/PS: naive in → naive out, mesmo wall-clock.
    assert lisbon_naive_verbatim(datetime(2026, 5, 31, 17, 42, 42)) == datetime(2026, 5, 31, 17, 42, 42)
    # aware in → tz descartado, wall-clock intacto (NUNCA converte).
    assert lisbon_naive_verbatim(datetime(2026, 5, 31, 17, 42, 42, tzinfo=timezone.utc)) == datetime(2026, 5, 31, 17, 42, 42)


def test_utc_to_lisbon_summer_adds_1h():
    # Verão (WEST): UTC 19:40 → Lisboa 20:40, naive.
    assert utc_to_lisbon_naive(datetime(2026, 5, 31, 19, 40, 15, tzinfo=timezone.utc)) == datetime(2026, 5, 31, 20, 40, 15)


def test_utc_to_lisbon_winter_no_offset():
    # Inverno (WET=UTC): sem mudança.
    assert utc_to_lisbon_naive(datetime(2026, 1, 15, 17, 42, 42, tzinfo=timezone.utc)) == datetime(2026, 1, 15, 17, 42, 42)


def test_utc_to_lisbon_naive_assumes_utc_for_naive_input():
    # input naive é assumido UTC.
    assert utc_to_lisbon_naive(datetime(2026, 7, 1, 19, 0, 0)) == datetime(2026, 7, 1, 20, 0, 0)


def test_results_are_naive():
    assert lisbon_naive_verbatim(datetime(2026, 5, 31, 17, 42, 42)).tzinfo is None
    assert utc_to_lisbon_naive(datetime(2026, 5, 31, 19, 40, 15, tzinfo=timezone.utc)).tzinfo is None


# ── GG: parse_hands devolve played_at em Lisboa naive (verbatim) ────────────

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


def test_gg_played_at_lisbon_verbatim_summer():
    hands, _ = parse_hands(_GG_BLOCK.encode("utf-8"), "t.txt")
    # Verbatim: o wall-clock da HH (17:42:42) é o played_at, SEM offset.
    assert hands and hands[0]["played_at"] == "2026-05-31T17:42:42"


def test_gg_played_at_lisbon_verbatim_winter():
    block = _GG_BLOCK.replace("2026/05/31 17:42:42", "2026/01/15 17:42:42")
    hands, _ = parse_hands(block.encode("utf-8"), "t.txt")
    assert hands and hands[0]["played_at"] == "2026-01-15T17:42:42"


# ── PS: _parse_hand grava a 1ª timestamp (WET/Lisboa) VERBATIM ──────────────

_PS_BLOCK = (
    "PokerStars Hand #260988837997: Tournament #4002440970, €45+€45+€10 EUR "
    "Hold'em No Limit - Level VIII (500/1000) - 2026/05/31 18:20:32 WET "
    "[2026/05/31 13:20:32 ET]\n"
    "Table '4002440970 5' 9-max Seat #1 is the button\n"
    "Seat 1: Hero (100000 in chips)\n"
    "*** HOLE CARDS ***\n"
    "*** SUMMARY ***\n"
)


def test_ps_played_at_lisbon_verbatim():
    r = _parse_hand(_PS_BLOCK, "PokerStars")
    # 18:20:32 (Lisboa) verbatim; o bracket ET é ignorado.
    assert r and r["played_at"] == "2026-05-31T18:20:32"


# ── Winamax: UTC explícito → converter UTC→Lisboa ───────────────────────────

_WN_BLOCK = (
    'Winamax Poker - Tournament "MAIN" buyIn: 5€ level: 1 - '
    "HandId: #4742042240115802195-78-1780256415 - Holdem no limit (10/20) - "
    "2026/05/31 19:40:15 UTC\n"
    "Table: 'MAIN(287)#3' 6-max\n"
    "Seat 1: Hero (6000)\n"
    "*** PRE-FLOP ***\n"
)


def test_winamax_played_at_converted_utc_to_lisbon():
    r = _parse_hand(_WN_BLOCK, "Winamax")
    # 19:40:15 UTC → Verão → 20:40:15 Lisboa, naive.
    assert r and r["played_at"] == "2026-05-31T20:40:15"


# ── Convergência do match em Lisboa: SS de mesa ↔ mão na MESMA referência ────

def test_match_anchor_aligns_with_played_at_in_lisbon():
    """O `captured_at` da SS de mesa (filename Lisboa naive) e o `played_at` da
    mão GG (HH Lisboa naive) ficam na MESMA referência → match temporal directo,
    sem offset. (Antes do pt51: SS em UTC vs HH em UTC — também batia, mas a
    pt49 destapou o risco de mistura ±1h; agora não há conversão de nenhum lado.)
    """
    from datetime import datetime
    from app.services.table_ss_vision import derive_captured_at

    # Mesma hora de relógio (17:42:42 de 2026/05/31, Verão) dos dois lados.
    hands, _ = parse_hands(_GG_BLOCK.encode("utf-8"), "t.txt")
    played_at = datetime.fromisoformat(hands[0]["played_at"])          # 17:42:42 naive
    captured_at = derive_captured_at("Table-GGPoker-20260531174242.png")  # 17:42:42 naive

    assert played_at.tzinfo is None and captured_at.tzinfo is None
    assert played_at == captured_at                                    # 0s de diferença
    assert abs((captured_at - played_at).total_seconds()) <= 300       # dentro da janela ±5min
