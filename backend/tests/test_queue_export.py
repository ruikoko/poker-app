"""Unit tests para services/queue_export.py — FASE 1 conversor HH."""
from app.services.queue_export import (
    convert_gg_hh_to_pokerstars_compatible,
    _format_level_line,
    _replace_hashes,
)


# ── Sample 1: GG raw HH com anon_map cheio ────────────────────────────────────
# Baseado em hand prod id=21384 (GG-5891642943, $54 BBG Daily Main).
# Header level: 350/700/100 (ante embutido nos parens externos).
SAMPLE_GG_RAW_FULL = """Poker Hand #TM5891642943: Tournament #280446581, Bounty Hunters Daily Main $54 Hold'em No Limit - Level7(350/700(100)) - 2026/04/30 19:08:52
Table '118' 8-max Seat #2 is the button
Seat 1: Hero (40,492 in chips)
Seat 2: 96c226b8 (26,167 in chips)
Seat 3: d2ca5b9a (32,511 in chips)
e0627537: posts the ante 100
96c226b8: posts the ante 100
*** HOLE CARDS ***
Dealt to Hero [3h 8d]
96c226b8: folds
d2ca5b9a: raises 1400 to 2100
Hero: folds
*** SUMMARY ***
Seat 2: 96c226b8 folded before Flop
Seat 3: d2ca5b9a collected (3500)
"""

SAMPLE_GG_ANON_MAP = {
    "Hero": "Lauro Dermio",
    "96c226b8": "msthtb66",
    "d2ca5b9a": "EitAAn",
    "e0627537": "habibi777",
}


def test_format_level_drops_ante_and_commas():
    s = "Level17(2,500/5,000(600))"
    assert _format_level_line(s) == "Level17 (2500/5000)"


def test_format_level_handles_small_numbers():
    s = "Level7(350/700(100))"
    assert _format_level_line(s) == "Level7 (350/700)"


def test_format_level_no_match_passthrough():
    s = "Level XXII (6000/12000)"  # PS-style ja convertido
    assert _format_level_line(s) == s


def test_replace_hashes_substitutes_known_only():
    text = "Seat 2: 96c226b8 (26,167 in chips)\nSeat 3: unknown123 (...)"
    out = _replace_hashes(text, {"96c226b8": "msthtb66"})
    assert "msthtb66" in out
    assert "96c226b8" not in out
    assert "unknown123" in out  # nao mapeado, fica


def test_replace_hashes_skips_hero_and_empty():
    text = "Seat 1: Hero (...)\nSeat 2: deadbeef (...)"
    out = _replace_hashes(text, {"Hero": "Lauro", "deadbeef": "msthtb66"})
    assert "Hero" in out  # Hero permanece literal
    assert "deadbeef" not in out
    assert "msthtb66" in out


def test_replace_hashes_no_map_passthrough():
    text = "Seat 2: 96c226b8 (...)"
    assert _replace_hashes(text, {}) == text


def test_convert_gg_full_pipeline():
    hand = {
        "site": "GGPoker",
        "raw": SAMPLE_GG_RAW_FULL,
        "player_names": {"anon_map": SAMPLE_GG_ANON_MAP},
    }
    out = convert_gg_hh_to_pokerstars_compatible(hand)

    # Level reformatado.
    assert "Level7 (350/700)" in out
    assert "Level7(350/700(100))" not in out

    # Hashes substituidos.
    assert "msthtb66" in out
    assert "EitAAn" in out
    assert "habibi777" in out
    assert "96c226b8" not in out
    assert "d2ca5b9a" not in out
    assert "e0627537" not in out

    # Hero + estrutura preservados.
    assert "Seat 1: Hero" in out
    assert "*** HOLE CARDS ***" in out
    assert "*** SUMMARY ***" in out


def test_convert_gg_without_anon_map_keeps_hashes():
    hand = {
        "site": "GGPoker",
        "raw": SAMPLE_GG_RAW_FULL,
        "player_names": {},  # sem anon_map
    }
    out = convert_gg_hh_to_pokerstars_compatible(hand)
    # Level ainda reformata.
    assert "Level7 (350/700)" in out
    # Hashes intactos (degrade graceful).
    assert "96c226b8" in out
    assert "d2ca5b9a" in out


def test_convert_non_gg_passthrough():
    raw = "PokerStars Hand #123: Tournament ..."
    hand = {"site": "PokerStars", "raw": raw, "player_names": {}}
    assert convert_gg_hh_to_pokerstars_compatible(hand) == raw


def test_convert_empty_raw_returns_empty():
    hand = {"site": "GGPoker", "raw": "", "player_names": {}}
    assert convert_gg_hh_to_pokerstars_compatible(hand) == ""


def test_player_names_as_string_is_parsed():
    """player_names em BD pode vir como JSON string (nao decoded). Cobertura
    do _coerce_player_names."""
    import json as _json
    hand = {
        "site": "GGPoker",
        "raw": SAMPLE_GG_RAW_FULL,
        "player_names": _json.dumps({"anon_map": SAMPLE_GG_ANON_MAP}),
    }
    out = convert_gg_hh_to_pokerstars_compatible(hand)
    assert "msthtb66" in out
    assert "96c226b8" not in out


# ── pt24: bounty injection nas Seat lines (#HRC-GG-KOS-EXTRACTION) ──────────

from app.services.queue_export import _inject_bounties_into_seat_lines


# 8 players com bounty extraído por Vision pt24 da coroa dourada (ground truth
# real do GG-5914506215, smoke pt24 validou 8/8 contra a SS).
_PLAYERS_LIST_GG_5914506215 = [
    {"name": "malmilion",     "bounty_value_usd": 125.0,  "bounty_pct": 28},
    {"name": "Vlad Martyn..", "bounty_value_usd": 75.0,   "bounty_pct": 23},
    {"name": "Dennis Volz",   "bounty_value_usd": 112.50, "bounty_pct": 28},
    {"name": "LTMR",          "bounty_value_usd": 50.0,   "bounty_pct": 20},
    {"name": "batya777",      "bounty_value_usd": 50.0,   "bounty_pct": 32},
    {"name": "Lauro Dermio",  "bounty_value_usd": 75.0,   "bounty_pct": 35},
    {"name": "R Aziz Alves",  "bounty_value_usd": 100.0,  "bounty_pct": 38},
    {"name": "InnerFireX",    "bounty_value_usd": 125.0,  "bounty_pct": 25},
]


_HH_GG_8_SEATS_USD = """Poker Hand #TM5914506215: Tournament #281416137, Bounty Hunters Big Game $215 Hold'em No Limit - Level12 (3500/7000) - 2026/05/05 21:38:14
Table '5' 8-max Seat #4 is the button
Seat 1: Vlad Martyn.. (406,118 in chips)
Seat 2: malmilion (271,970 in chips)
Seat 3: batya777 (272,102 in chips)
Seat 4: Hero (235,287 in chips)
Seat 5: R Aziz Alves (228,179 in chips)
Seat 6: InnerFireX (257,246 in chips)
Seat 7: LTMR (386,014 in chips)
Seat 8: Dennis Volz (272,264 in chips)
*** HOLE CARDS ***
Dealt to Hero [Kh Jc]
"""


_HH_GG_8_SEATS_EUR_HEADER = _HH_GG_8_SEATS_USD.replace(
    "Bounty Hunters Big Game $215", "Bounty Hunters Big Game €200"
)


def test_inject_bounties_8_of_8_enriched():
    """pt24 caso nominal: 8 seats, 8 bounties em players_list → 8 enriquecidas."""
    anon_map = {"Hero": "Lauro Dermio"}
    out = _inject_bounties_into_seat_lines(
        _HH_GG_8_SEATS_USD, _PLAYERS_LIST_GG_5914506215, anon_map,
    )
    # Cada um dos 8 nicks (anon_map já resolvido + Hero literal) deve ter o
    # seu valor de bounty com 2 decimais e símbolo $.
    assert "Seat 1: Vlad Martyn.. (406,118 in chips, $75.00 bounty)" in out
    assert "Seat 2: malmilion (271,970 in chips, $125.00 bounty)" in out
    assert "Seat 3: batya777 (272,102 in chips, $50.00 bounty)" in out
    assert "Seat 4: Hero (235,287 in chips, $75.00 bounty)" in out
    assert "Seat 5: R Aziz Alves (228,179 in chips, $100.00 bounty)" in out
    assert "Seat 6: InnerFireX (257,246 in chips, $125.00 bounty)" in out
    assert "Seat 7: LTMR (386,014 in chips, $50.00 bounty)" in out
    assert "Seat 8: Dennis Volz (272,264 in chips, $112.50 bounty)" in out
    # Sanity: 8 bounty markers no total
    assert out.count(" bounty)") == 8


def test_inject_bounties_empty_players_list_noop():
    """pt24 caso defensivo: sem players_list (Vision falhou / mão pre-pt24)
    → HH inalterada. Zero crashes, zero linhas modificadas."""
    out = _inject_bounties_into_seat_lines(_HH_GG_8_SEATS_USD, [], {"Hero": "Lauro Dermio"})
    assert out == _HH_GG_8_SEATS_USD
    # Também com None / dict vazio
    out2 = _inject_bounties_into_seat_lines(_HH_GG_8_SEATS_USD, None, None)
    assert out2 == _HH_GG_8_SEATS_USD


def test_inject_bounties_6_of_8_partial_match():
    """pt24 caso parcial: 2 dos 8 players sem bounty_value_usd → só 6
    Seat lines enriquecidas. As outras 2 ficam exactamente intactas."""
    partial = [p for p in _PLAYERS_LIST_GG_5914506215]
    # Drop bounty de 2 players (Vision pode falhar crown em players específicos)
    partial = [
        {**p, "bounty_value_usd": 0.0} if p["name"] in ("LTMR", "batya777") else p
        for p in partial
    ]
    out = _inject_bounties_into_seat_lines(
        _HH_GG_8_SEATS_USD, partial, {"Hero": "Lauro Dermio"},
    )
    # 6 enriquecidas
    assert " bounty)" in out
    assert out.count(" bounty)") == 6
    # LTMR e batya777 ficam intactas
    assert "Seat 7: LTMR (386,014 in chips)" in out
    assert "Seat 3: batya777 (272,102 in chips)" in out
    # Os outros 6 enriquecidos
    assert "Seat 2: malmilion (271,970 in chips, $125.00 bounty)" in out
    assert "Seat 4: Hero (235,287 in chips, $75.00 bounty)" in out


def test_inject_bounties_currency_USD_from_dollar_in_header():
    """pt24 currency: header com '$' → símbolo $."""
    out = _inject_bounties_into_seat_lines(
        _HH_GG_8_SEATS_USD, _PLAYERS_LIST_GG_5914506215, {"Hero": "Lauro Dermio"},
    )
    assert " $125.00 bounty)" in out
    assert " €" not in out  # nenhum euro símbolo


def test_inject_bounties_currency_EUR_from_euro_in_header():
    """pt24 currency: header com '€' → símbolo €."""
    out = _inject_bounties_into_seat_lines(
        _HH_GG_8_SEATS_EUR_HEADER, _PLAYERS_LIST_GG_5914506215,
        {"Hero": "Lauro Dermio"},
    )
    assert " €125.00 bounty)" in out
    # Sem $ except no header (que ainda contém o original... espera, replaced)
    # Header foi substituído de $215 para €200; o resto da HH não tem $.
    seat_lines = "\n".join(ln for ln in out.split("\n") if ln.startswith("Seat "))
    assert "$" not in seat_lines


# ── pt25: #HRC-PRUNE-IN-GAP-DOWNSTREAM helpers ─────────────────────────────

import os as _os
from app.services.queue_export import (
    derive_real_aggressor_position,
    derive_prune_downstream,
    generate_hrc_script,
)


# ── derive_real_aggressor_position ──────────────────────────────────────────

# Helper builder para HHs de teste. 8-max, button configurável.
# HRC convention para 8-max com button = Seat #4:
#   SB=Seat 5 (idx 0), BB=Seat 6 (idx 1), UTG=Seat 7 (idx 2),
#   UTG+1/EP=Seat 8 (idx 3), MP=Seat 1 (idx 4), HJ=Seat 2 (idx 5),
#   CO=Seat 3 (idx 6), BTN=Seat 4 (idx 7).

def _hh_8max_btn4(preflop_actions: list[str]) -> str:
    """Constrói uma HH 8-max minimal com button Seat #4 e acções preflop
    customizáveis."""
    lines = [
        "Poker Hand #TM1: Tournament #100, Test - Level5 (200/400) - 2026/05/01 00:00:00",
        "Table 'A' 8-max Seat #4 is the button",
        "Seat 1: MPplayer (10000 in chips)",      # MP, HRC idx 4
        "Seat 2: HJplayer (10000 in chips)",      # HJ, HRC idx 5
        "Seat 3: COplayer (10000 in chips)",      # CO, HRC idx 6
        "Seat 4: Hero (10000 in chips)",          # BTN, HRC idx 7
        "Seat 5: SBplayer (10000 in chips)",      # SB, HRC idx 0
        "Seat 6: BBplayer (10000 in chips)",      # BB, HRC idx 1
        "Seat 7: UTGplayer (10000 in chips)",     # UTG, HRC idx 2
        "Seat 8: EPplayer (10000 in chips)",      # UTG+1/EP, HRC idx 3
        "SBplayer: posts small blind 200",
        "BBplayer: posts big blind 400",
        "*** HOLE CARDS ***",
        "Dealt to Hero [As Kd]",
    ]
    lines.extend(preflop_actions)
    lines.append("*** SUMMARY ***")
    return "\n".join(lines) + "\n"


def test_aggressor_UTG_opens():
    """8-max, UTG raise first → HRC idx 2."""
    hh = _hh_8max_btn4(["UTGplayer: raises 800 to 1200"])
    assert derive_real_aggressor_position(hh) == 2


def test_aggressor_EP_opens():
    """UTG folds, EP (UTG+1) raises → HRC idx 3."""
    hh = _hh_8max_btn4([
        "UTGplayer: folds",
        "EPplayer: raises 800 to 1200",
    ])
    assert derive_real_aggressor_position(hh) == 3


def test_aggressor_MP_opens():
    """UTG/EP fold, MP raises → HRC idx 4."""
    hh = _hh_8max_btn4([
        "UTGplayer: folds",
        "EPplayer: folds",
        "MPplayer: raises 800 to 1200",
    ])
    assert derive_real_aggressor_position(hh) == 4


def test_aggressor_HJ_opens():
    """UTG/EP/MP fold, HJ raises → HRC idx 5."""
    hh = _hh_8max_btn4([
        "UTGplayer: folds",
        "EPplayer: folds",
        "MPplayer: folds",
        "HJplayer: raises 800 to 1200",
    ])
    assert derive_real_aggressor_position(hh) == 5


def test_aggressor_CO_opens():
    """UTG/EP/MP/HJ fold, CO raises → HRC idx 6."""
    hh = _hh_8max_btn4([
        "UTGplayer: folds",
        "EPplayer: folds",
        "MPplayer: folds",
        "HJplayer: folds",
        "COplayer: raises 800 to 1200",
    ])
    assert derive_real_aggressor_position(hh) == 6


def test_aggressor_SB_completes_returns_None():
    """Limp pot — todos foldam até SB, SB completa, BB checks → None
    (sem raise voluntário; também não é SB-opens-excepção, é literalmente
    sem aggressor)."""
    hh = _hh_8max_btn4([
        "UTGplayer: folds",
        "EPplayer: folds",
        "MPplayer: folds",
        "HJplayer: folds",
        "COplayer: folds",
        "Hero: folds",
        "SBplayer: calls 200",
        "BBplayer: checks",
    ])
    assert derive_real_aggressor_position(hh) is None


def test_aggressor_SB_opens_returns_None_per_exception():
    """Todos foldam até SB, SB faz raise — regra pt23 excepção "SB-aberto"
    devolve None (sem prune downstream porque ninguém depois excepto BB)."""
    hh = _hh_8max_btn4([
        "UTGplayer: folds",
        "EPplayer: folds",
        "MPplayer: folds",
        "HJplayer: folds",
        "COplayer: folds",
        "Hero: folds",
        "SBplayer: raises 600 to 1200",
        "BBplayer: folds",
    ])
    assert derive_real_aggressor_position(hh) is None


def test_aggressor_BU_opens_returns_idx7():
    """UTG..CO fold, BTN (Hero, idx 7) raises → 7. Test crítico para
    GG-5914506215 real (Hero=BTN opens, smoke pt23)."""
    hh = _hh_8max_btn4([
        "UTGplayer: folds",
        "EPplayer: folds",
        "MPplayer: folds",
        "HJplayer: folds",
        "COplayer: folds",
        "Hero: raises 800 to 1200",
    ])
    assert derive_real_aggressor_position(hh) == 7


# ── pt25b: cross-site marker + action format compat ────────────────────────

from app.services.queue_export import find_preflop_marker


def test_find_preflop_marker_PS_GG_HOLE_CARDS():
    """PS/GG: `*** HOLE CARDS ***`."""
    hh = "... header ...\n*** HOLE CARDS ***\nDealt to Hero [As Kd]\n..."
    pos = find_preflop_marker(hh)
    assert pos is not None
    assert hh[pos:pos + 18] == "*** HOLE CARDS ***"


def test_find_preflop_marker_WN_PRE_FLOP():
    """Winamax: `*** PRE-FLOP ***`."""
    hh = "... header ...\n*** ANTE/BLINDS ***\n[antes]\n*** PRE-FLOP ***\nplayer raises 100\n..."
    pos = find_preflop_marker(hh)
    assert pos is not None
    assert hh[pos:pos + 16] == "*** PRE-FLOP ***"


def test_find_preflop_marker_none_returns_None():
    """Sem nenhum marker → None."""
    assert find_preflop_marker("just header text\nno markers here\n") is None
    assert find_preflop_marker("") is None
    assert find_preflop_marker(None) is None  # type: ignore[arg-type]


def test_find_preflop_marker_both_returns_earlier():
    """Se ambos markers existirem (defensive), devolve o mais cedo."""
    # PS marker primeiro
    hh1 = "x\n*** HOLE CARDS ***\nstuff\n*** PRE-FLOP ***\nmore\n"
    assert find_preflop_marker(hh1) == hh1.find("*** HOLE CARDS ***")
    # WN marker primeiro (improvável real, mas testa o min())
    hh2 = "y\n*** PRE-FLOP ***\nstuff\n*** HOLE CARDS ***\nmore\n"
    assert find_preflop_marker(hh2) == hh2.find("*** PRE-FLOP ***")


# Samples reais (snippets minimalistas) de cada site para validar end-to-end.
# Estrutura essencial preservada: header com Seat #N is the button + N-max,
# Seat lines com nicks, marker preflop, primeira action raise/bet.

_HH_PS_REAL = """PokerStars Hand #260299428000: Tournament #3983882920, €45+€45+€10 EUR Hold'em No Limit - Level XXVI (12500/25000) - 2026/03/31 23:40:45 WET [2026/03/31 18:40:45 ET]
Table '3983882920 23' 6-max Seat #5 is the button
Seat 1: kokonakueka (736340 in chips, €196.87 bounty)
Seat 2: carlos8surf (925129 in chips, €292.50 bounty)
Seat 4: QuimDiamond (763155 in chips, €163.12 bounty)
Seat 5: Votsarrr (633451 in chips, €323.43 bounty)
Seat 6: UltraLoubard (391164 in chips, €191.25 bounty)
kokonakueka: posts the ante 3250
*** HOLE CARDS ***
Dealt to Hero [Ah As]
carlos8surf: folds
QuimDiamond: folds
Votsarrr: raises 605201 to 630201 and is all-in
UltraLoubard: folds
kokonakueka: folds
*** SUMMARY ***
"""


_HH_GG_REAL = """Poker Hand #TM5939385803: Tournament #282699155, Bounty Hunters Forty Stack $44 Hold'em No Limit - Level3(150/300(45)) - 2026/05/11 17:16:38
Table '155' 8-max Seat #1 is the button
Seat 1: Hero (40,000 in chips)
Seat 5: b839c780 (90,299 in chips)
Seat 6: 3343ebc6 (47,788 in chips)
Seat 7: 8db88342 (44,636 in chips)
Seat 8: 221ebf0d (42,483 in chips)
*** HOLE CARDS ***
Dealt to Hero [As Kd]
8db88342: folds
221ebf0d: raises 300 to 600
Hero: calls 600
b839c780: folds
*** SUMMARY ***
"""


_HH_WN_REAL = """Winamax Poker - Tournament "INTERSTELLAR" buyIn: 90€ + 10€ level: 22 - HandId: #4699459877053923331-277-1778535900 - Holdem no limit (1000/4000/8000) - 2026/05/11 21:45:00 UTC
Table: 'INTERSTELLAR(1094178268)#002' 6-max (real money) Seat #2 is the button
Seat 1: yousnouf75 (163754, 194.40€ bounty)
Seat 2: imbagosu (615675, 532.70€ bounty)
Seat 3: Beu_Teu (663845, 311.97€ bounty)
Seat 4: thinvalium (351657, 244.20€ bounty)
Seat 5: blueballs67 (354758, 140€ bounty)
*** ANTE/BLINDS ***
Beu_Teu posts ante 1000
*** PRE-FLOP ***
blueballs67 raises 8000 to 16000
yousnouf75 calls 16000
imbagosu folds
Beu_Teu raises 48000 to 64000
*** SUMMARY ***
"""


_HH_WPN_REAL = """Game Hand #2735377673 - $60,000 GTD Tournament #35005597 - Holdem (No Limit) - Level 4 (800.00/1600.00) - 2026/05/11 16:51:23 UTC
Table '39' 8-max Seat #1 is the button
Seat 1: Jetsies (448465.00)
Seat 2: cringemeariver (130314.00)
Seat 3: AbamaAbezyana (100200.00)
Seat 4: TuuusTuuuuus (89400.00)
Seat 5: egegey1 (112340.00)
Seat 6: pocahontas94 (79244.00)
Seat 7: DAVIDSBAGOFICE (110968.00)
Seat 8: eagle47 (34502.00)
Jetsies posts ante 200.00
*** HOLE CARDS ***
TuuusTuuuuus folds
egegey1 folds
pocahontas94 folds
DAVIDSBAGOFICE raises 1600.00 to 3200.00
*** SUMMARY ***
"""


def test_aggressor_PS_real_sample():
    """PS sample (PS-260299428000, 6-max BTN=Seat 5): preflop UTG-style raiser
    é Votsarrr@Seat5 — mas espera, Votsarrr=BTN (Seat #5 is the button).
    HRC index: BTN=Seat 5, SB=Seat 6 (idx 0), BB=Seat 1 (idx 1), UTG=Seat 2
    (idx 2), HJ=Seat 4 (idx 3), CO/BTN=Seat 5 (idx 4)
    Mas Votsarrr=Seat 5 = BTN → idx 4 em 5-sentados-6-max."""
    out = derive_real_aggressor_position(_HH_PS_REAL)
    # Validação: aggressor deve ser identificado (não None) e mapear para
    # alguém na BTN-side (Votsarrr@Seat5).
    assert out is not None
    # Compute expected: button=Seat5; seat_list=[1,2,4,5,6] (5 sentados);
    # btn_idx_in_list=3; sb_idx_in_list=(3+1)%5=4 → Seat 6 (UltraLoubard=SB);
    # walking: hrc0=Seat6(UltraLoubard,SB), hrc1=Seat1(kokonakueka,BB),
    #          hrc2=Seat2(carlos8surf,UTG), hrc3=Seat4(QuimDiamond,HJ),
    #          hrc4=Seat5(Votsarrr,BTN). Votsarrr opens → idx 4. ✓
    assert out == 4


def test_aggressor_GG_real_sample():
    """GG sample (GG real, 8-max BTN=Seat 1, 5 sentados): 1º raise é
    221ebf0d@Seat8."""
    out = derive_real_aggressor_position(_HH_GG_REAL)
    assert out is not None
    # Compute: button=Seat1; seat_list=[1,5,6,7,8]; btn_idx_in_list=0;
    # sb_idx_in_list=1 → Seat5 (b839c780=SB).
    # hrc0=Seat5(SB), hrc1=Seat6(BB), hrc2=Seat7(8db88342,UTG),
    # hrc3=Seat8(221ebf0d,UTG+1 / EP), hrc4=Seat1(Hero,BTN).
    # 221ebf0d raises = idx 3 (EP).
    assert out == 3


def test_aggressor_WN_real_sample_INTERSTELLAR():
    """Winamax sample (INTERSTELLAR target do smoke pt25b): 6-max 5-sentados
    BTN=Seat 2; blueballs67@Seat5 raises first."""
    out = derive_real_aggressor_position(_HH_WN_REAL)
    assert out is not None
    # Compute: seat_list=[1,2,3,4,5]; btn_idx_in_list=1; sb_idx_in_list=2 → Seat3
    # hrc0=Seat3(Beu_Teu,SB), hrc1=Seat4(thinvalium,BB), hrc2=Seat5(blueballs67,UTG),
    # hrc3=Seat1(yousnouf75,HJ?), hrc4=Seat2(imbagosu,BTN).
    # blueballs67 raises = idx 2 (UTG). ✓ Matches dry-run expectation.
    assert out == 2


def test_aggressor_WPN_real_sample():
    """WPN sample (8-max BTN=Seat 1, 8 sentados full): DAVIDSBAGOFICE@Seat7
    raises after 3 folds."""
    out = derive_real_aggressor_position(_HH_WPN_REAL)
    assert out is not None
    # Compute: 8 sentados, btn=Seat1, sb=Seat2, bb=Seat3, ..., btn-1=Seat8 (idx 7).
    # btn_idx_in_list=0; sb_idx_in_list=1 → Seat2 (cringemeariver=SB).
    # hrc0=Seat2(SB), hrc1=Seat3(BB), hrc2=Seat4(UTG), hrc3=Seat5,
    # hrc4=Seat6, hrc5=Seat7(DAVIDSBAGOFICE), hrc6=Seat8, hrc7=Seat1(BTN).
    # DAVIDSBAGOFICE raises after Seat4/5/6 fold (idx 2/3/4). DAVIDSBAGOFICE = idx 5 (CO).
    assert out == 5


# ── pt25b ETAPA 3: derive_seats_in_preflop_order + derive_table_format ──────

from app.services.queue_export import (
    derive_seats_in_preflop_order,
    derive_table_format,
)


def test_seats_PS_real_sample():
    """PS-260299428000: 6-max BTN=Seat 5, 5 sentados (Seat 3 missing)."""
    seats = derive_seats_in_preflop_order(_HH_PS_REAL)
    assert len(seats) == 5
    # SB=Seat 6 (btn+1 wrapping), BB=Seat 1, UTG=Seat 2, HJ=Seat 4, BTN=Seat 5
    assert seats[0] == {"seat": 6, "position": "SB",  "hrc_idx": 0, "nick": "UltraLoubard"}
    assert seats[1] == {"seat": 1, "position": "BB",  "hrc_idx": 1, "nick": "kokonakueka"}
    assert seats[2] == {"seat": 2, "position": "UTG", "hrc_idx": 2, "nick": "carlos8surf"}
    assert seats[3] == {"seat": 4, "position": "HJ",  "hrc_idx": 3, "nick": "QuimDiamond"}
    assert seats[4] == {"seat": 5, "position": "BTN", "hrc_idx": 4, "nick": "Votsarrr"}


def test_seats_GG_real_sample():
    """GG-5939385803: 8-max BTN=Seat 1, 5 sentados (Seats 2,3,4 missing)."""
    seats = derive_seats_in_preflop_order(_HH_GG_REAL)
    assert len(seats) == 5
    # btn_idx=0 (Seat 1 first in [1,5,6,7,8]), sb_idx=1 → Seat 5
    nicks = [s["nick"] for s in seats]
    assert nicks == ["b839c780", "3343ebc6", "8db88342", "221ebf0d", "Hero"]
    positions = [s["position"] for s in seats]
    assert positions == ["SB", "BB", "UTG", "HJ", "BTN"]  # 5-handed labels


def test_seats_WN_real_sample_INTERSTELLAR():
    """WN-INTERSTELLAR: 6-max BTN=Seat 2, 5 sentados (Seat 6 missing).
    Smoke target pt25b."""
    seats = derive_seats_in_preflop_order(_HH_WN_REAL)
    assert len(seats) == 5
    nicks = [s["nick"] for s in seats]
    assert nicks == ["Beu_Teu", "thinvalium", "blueballs67", "yousnouf75", "imbagosu"]
    positions = [s["position"] for s in seats]
    assert positions == ["SB", "BB", "UTG", "HJ", "BTN"]
    # blueballs67 = UTG = hrc_idx 2 (aggressor confirmado por ETAPA 1)
    assert next(s for s in seats if s["nick"] == "blueballs67")["hrc_idx"] == 2


def test_seats_WPN_real_sample():
    """WPN: 8-max BTN=Seat 1, 8 sentados full."""
    seats = derive_seats_in_preflop_order(_HH_WPN_REAL)
    assert len(seats) == 8
    nicks = [s["nick"] for s in seats]
    # btn=Seat 1, sb=Seat 2 (cringemeariver), bb=Seat 3, ..., btn=Seat 1 (Jetsies)
    assert nicks[0] == "cringemeariver"   # SB
    assert nicks[1] == "AbamaAbezyana"    # BB
    assert nicks[2] == "TuuusTuuuuus"     # UTG
    assert nicks[7] == "Jetsies"          # BTN
    positions = [s["position"] for s in seats]
    assert positions == ["SB", "BB", "UTG", "EP", "MP", "HJ", "CO", "BTN"]


def test_seats_no_button_returns_empty():
    """Defensive: header sem 'Seat #N is the button' → []."""
    hh = "Some HH header without button info\nSeat 1: Foo (100 in chips)\nSeat 2: Bar (200 in chips)\n*** HOLE CARDS ***\n"
    assert derive_seats_in_preflop_order(hh) == []


def test_seats_no_seats_returns_empty():
    """Defensive: HH sem seat lines parseable → []."""
    assert derive_seats_in_preflop_order("") == []
    assert derive_seats_in_preflop_order("Just a header\n*** HOLE CARDS ***\n") == []


# ── derive_table_format ─────────────────────────────────────────────────────

def test_table_format_PS():
    assert derive_table_format(_HH_PS_REAL) == 6


def test_table_format_GG():
    assert derive_table_format(_HH_GG_REAL) == 8


def test_table_format_WN():
    assert derive_table_format(_HH_WN_REAL) == 6


def test_table_format_WPN():
    assert derive_table_format(_HH_WPN_REAL) == 8


def test_table_format_no_N_max_fallback_8():
    assert derive_table_format("Just some text without max format\n") == 8
    assert derive_table_format("") == 8
    assert derive_table_format(None) == 8  # type: ignore[arg-type]


# ── derive_prune_downstream com seated_hrc_indices (pt25b ETAPA 3 core) ────

def test_prune_8max_full_seated_uses_8():
    """seated=[0..7] (8 sentados) — UTG aggressor → 6 downstream (BB excluded)."""
    assert derive_prune_downstream(2, 6, 200, seated_hrc_indices=[0,1,2,3,4,5,6,7]) == [3,4,5,6,7,0]


def test_prune_6max_full_seated_uses_6():
    """seated=[0..5] (6 sentados full) — UTG aggressor → [HJ=3, CO=4, BTN=5, SB=0]."""
    assert derive_prune_downstream(2, 6, 200, seated_hrc_indices=[0,1,2,3,4,5]) == [3,4,5,0]


def test_prune_INTERSTELLAR_5_seated_6max():
    """SMOKE TARGET pt25b: seated=[0..4] (5 sentados em 6-max table),
    aggressor UTG (idx 2) = blueballs67 → downstream [HJ=3, BTN=4, SB=0].
    Note: 5-handed labels têm BTN=hrc_idx 4 (não 5), porque CO desaparece."""
    out = derive_prune_downstream(2, 6, 36, seated_hrc_indices=[0,1,2,3,4])
    assert out == [3, 4, 0]


def test_prune_5_seated_SB_aggressor_returns_empty():
    """SB-aberto excepção: aggressor=0 → [] mesmo com seated populated."""
    assert derive_prune_downstream(0, 5, 200, seated_hrc_indices=[0,1,2,3,4]) == []


def test_prune_FT_phase_with_seated_returns_empty():
    """FT phase: players_left <= 3*max_players → [] mesmo com seated populated."""
    assert derive_prune_downstream(2, 6, 18, seated_hrc_indices=[0,1,2,3,4,5]) == []


def test_prune_BTN_aggressor_5_seated():
    """5-handed: BTN aggressor (idx 4) → downstream [SB=0]."""
    assert derive_prune_downstream(4, 6, 200, seated_hrc_indices=[0,1,2,3,4]) == [0]


def test_prune_legacy_no_seated_falls_back_to_table_format():
    """Sem seated_hrc_indices: usa table_format=8 (default). Preserva
    chamadas pt25 sintéticas."""
    assert derive_prune_downstream(2, 6, 200) == [3,4,5,6,7,0]
    # Com table_format override
    assert derive_prune_downstream(2, 6, 200, table_format=6) == [3,4,5,0]


# ── derive_prune_downstream ─────────────────────────────────────────────────

def test_prune_UTG_aggressor_8max():
    """UTG (idx 2) → [EP=3, MP=4, HJ=5, CO=6, BU=7, SB=0]."""
    assert derive_prune_downstream(2, 6, 200) == [3, 4, 5, 6, 7, 0]


def test_prune_EP_aggressor_8max():
    assert derive_prune_downstream(3, 6, 200) == [4, 5, 6, 7, 0]


def test_prune_MP_aggressor_8max():
    assert derive_prune_downstream(4, 6, 200) == [5, 6, 7, 0]


def test_prune_HJ_aggressor_8max():
    assert derive_prune_downstream(5, 6, 200) == [6, 7, 0]


def test_prune_CO_aggressor_8max():
    assert derive_prune_downstream(6, 6, 200) == [7, 0]


def test_prune_BU_aggressor_8max():
    assert derive_prune_downstream(7, 6, 200) == [0]


def test_prune_SB_aggressor_exception_returns_empty():
    """SB (idx 0) → [] (excepção regra)."""
    assert derive_prune_downstream(0, 6, 200) == []


def test_prune_FT_phase_no_prune():
    """players_left ≤ 3 × max_players → [] (FT phase, não prune)."""
    # max_players=6, threshold=18
    assert derive_prune_downstream(2, 6, 18) == []
    assert derive_prune_downstream(2, 6, 10) == []
    # = threshold → no prune (≤, não strict)
    assert derive_prune_downstream(2, 6, 18) == []


def test_prune_None_aggressor_returns_empty():
    """aggressor None → [] (defensivo)."""
    assert derive_prune_downstream(None, 6, 200) == []


def test_prune_missing_threshold_returns_empty():
    """max_players ou players_left None → [] (defensivo)."""
    assert derive_prune_downstream(2, None, 200) == []
    assert derive_prune_downstream(2, 6, None) == []


# ── generate_hrc_script ─────────────────────────────────────────────────────

_TEMPLATE_PATH = _os.path.join(
    _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
    "app", "services", "hrc_scripts",
    "mtt_advanced_20211029 - 2 flats + bb close action size open 2x - 3x bvb.js",
)


def test_generate_hrc_script_with_hint():
    """Com hint válido: hint block presente, valores reais injectados."""
    out = generate_hrc_script(_TEMPLATE_PATH, aggressor_pos=2,
                              downstream_positions=[3, 4, 5, 6, 7, 0])
    assert "let REAL_AGGRESSOR_POS = 2;" in out
    assert "let DOWNSTREAM_POSITIONS = [3, 4, 5, 6, 7, 0];" in out
    assert "pt25 prune-in-gap-downstream hints" in out
    # Marker do template ainda existe (não destruímos)
    assert "let ALLIN = 9999;" in out
    # Template original preservado (procurar uma const conhecida)
    assert "SIZES_OPEN_OTHERS" in out


def test_generate_hrc_script_without_hint():
    """Sem hint (aggressor None ou downstream empty): defaults null/[]
    inseridos → no-op behavior (JS comporta-se idêntico ao original)."""
    out_none = generate_hrc_script(_TEMPLATE_PATH, aggressor_pos=None,
                                   downstream_positions=[])
    assert "let REAL_AGGRESSOR_POS = null;" in out_none
    assert "let DOWNSTREAM_POSITIONS = [];" in out_none

    out_empty_ds = generate_hrc_script(_TEMPLATE_PATH, aggressor_pos=2,
                                       downstream_positions=[])
    assert "let REAL_AGGRESSOR_POS = null;" in out_empty_ds


# ── pt25b: generate_hrc_script — anti-duplicate-let + idempotência ─────────

import tempfile as _tempfile


def test_generate_hrc_script_no_duplicate_let_with_hint():
    """pt25b core: template real (com placeholder B2) + hint → output tem
    EXACTAMENTE 1 declaração let por variável (sem duplicate que causaria
    SyntaxError no Nashorn)."""
    out = generate_hrc_script(_TEMPLATE_PATH, aggressor_pos=2,
                              downstream_positions=[3, 4, 0])
    # Conta ocorrências EXACTAS — qualquer duplicate aparece >1
    n_agg = out.count("let REAL_AGGRESSOR_POS")
    n_ds = out.count("let DOWNSTREAM_POSITIONS")
    assert n_agg == 1, f"duplicate REAL_AGGRESSOR_POS: {n_agg} occurrences"
    assert n_ds == 1, f"duplicate DOWNSTREAM_POSITIONS: {n_ds} occurrences"
    # Valores reais presentes (não os defaults)
    assert "let REAL_AGGRESSOR_POS = 2;" in out
    assert "let DOWNSTREAM_POSITIONS = [3, 4, 0];" in out
    # Comment do template B2 preservado
    assert "pt25 prune-in-gap-downstream hints" in out


def test_generate_hrc_script_idempotent():
    """pt25b: chamar 2× consecutivas com MESMOS args → output byte-idêntico.
    Garante que re-runs do queue_export não corrompem o JS."""
    out1 = generate_hrc_script(_TEMPLATE_PATH, aggressor_pos=4,
                               downstream_positions=[5, 6, 7, 0])
    # 2ª chamada com os mesmos args — escreve para tmp e re-gera
    tmp_path = _os.path.join(_tempfile.mkdtemp(), "stage1.js")
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(out1)
    out2 = generate_hrc_script(tmp_path, aggressor_pos=4,
                               downstream_positions=[5, 6, 7, 0])
    assert out1 == out2, "non-idempotent: 2nd call produced different output"


def test_generate_hrc_script_substitutes_after_prior_injection():
    """pt25b: template ALREADY com hint (e.g. {REAL=2, DS=[3,4,0]}) + nova
    chamada com diferentes args (e.g. {REAL=5, DS=[6,7,0]}) → substitui pelos
    novos, sem duplicate."""
    # Stage 1: inject {REAL=2, DS=[3,4,0]} no template real
    stage1 = generate_hrc_script(_TEMPLATE_PATH, aggressor_pos=2,
                                 downstream_positions=[3, 4, 0])
    tmp_path = _os.path.join(_tempfile.mkdtemp(), "stage1.js")
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(stage1)
    # Stage 2: re-inject {REAL=5, DS=[6,7,0]} sobre o output do stage 1
    stage2 = generate_hrc_script(tmp_path, aggressor_pos=5,
                                 downstream_positions=[6, 7, 0])
    # Novos valores presentes
    assert "let REAL_AGGRESSOR_POS = 5;" in stage2
    assert "let DOWNSTREAM_POSITIONS = [6, 7, 0];" in stage2
    # Stage 1 valores ausentes (substituídos)
    assert "let REAL_AGGRESSOR_POS = 2;" not in stage2
    assert "let DOWNSTREAM_POSITIONS = [3, 4, 0];" not in stage2
    # Ainda só 1 occurrence cada
    assert stage2.count("let REAL_AGGRESSOR_POS") == 1
    assert stage2.count("let DOWNSTREAM_POSITIONS") == 1


def test_generate_hrc_script_legacy_template_fallback():
    """pt25b: template legacy (sem placeholder B2) + hint → fallback insere
    bloco hint antes de `let ALLIN = 9999;` (mantém compat com templates
    antigos ou variantes que não passaram pela edit B2)."""
    legacy = (
        "// legacy template — sem hints declarados\n"
        "let ALLIN = 9999;\n"
        "let SIZES_OPEN_OTHERS = [2, ALLIN];\n"
        "function getSizingsPreflop(ctx) { return SIZES_OPEN_OTHERS; }\n"
    )
    tmp_path = _os.path.join(_tempfile.mkdtemp(), "legacy.js")
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(legacy)
    out = generate_hrc_script(tmp_path, aggressor_pos=2,
                              downstream_positions=[3, 4, 0])
    # Fallback inserts bloco hint ANTES de `let ALLIN`
    allin_pos = out.find("let ALLIN = 9999;")
    agg_pos = out.find("let REAL_AGGRESSOR_POS")
    ds_pos = out.find("let DOWNSTREAM_POSITIONS")
    assert allin_pos > 0
    assert 0 < agg_pos < allin_pos
    assert 0 < ds_pos < allin_pos
    # 1 occurrence cada
    assert out.count("let REAL_AGGRESSOR_POS") == 1
    assert out.count("let DOWNSTREAM_POSITIONS") == 1
    # Comment fallback adicionado (legacy não tinha)
    assert "pt25 prune-in-gap-downstream hints" in out
    # Conteúdo original preservado
    assert "let SIZES_OPEN_OTHERS = [2, ALLIN];" in out


# ── build_queue_zip ───────────────────────────────────────────────────────────

import io as _io
import json as _json
import zipfile as _zipfile

from app.services.queue_export import build_queue_zip


def _fake_payout_blob():
    return {
        "name": "/",
        "folders": [],
        "structures": [{
            "name": "Test BBG $54",
            "chips": 1000000.0,
            "prizes": {"1": 100.0, "2": 50.0},
            "bountyType": "PKO",
            "progressiveFactor": 0.5,
        }],
    }


def test_build_queue_zip_basic_includes_hh_payouts_manifest():
    hand = {
        "id": 1, "hand_id": "GG-X", "site": "GGPoker",
        "tournament_number": "111",
        "raw": SAMPLE_GG_RAW_FULL,
        "player_names": {"anon_map": SAMPLE_GG_ANON_MAP},
    }
    blob = build_queue_zip([hand], {("GGPoker", "111"): _fake_payout_blob()})
    zf = _zipfile.ZipFile(_io.BytesIO(blob))
    names = set(zf.namelist())
    assert "GG-X/hh.txt" in names
    assert "GG-X/payouts.json" in names
    assert "manifest.json" in names
    manifest = _json.loads(zf.read("manifest.json"))
    assert manifest["total_in_zip"] == 1
    assert manifest["hands_included"][0]["has_payouts"] is True
    assert manifest["hands_included"][0]["converted_format"] == "pokerstars_compat"


def test_build_queue_zip_excludes_missing_payouts_by_default():
    hand = {
        "id": 1, "hand_id": "GG-Y", "site": "GGPoker",
        "tournament_number": "999",
        "raw": SAMPLE_GG_RAW_FULL,
        "player_names": {"anon_map": SAMPLE_GG_ANON_MAP},
    }
    blob = build_queue_zip([hand], {})
    zf = _zipfile.ZipFile(_io.BytesIO(blob))
    assert "GG-Y/hh.txt" not in set(zf.namelist())
    manifest = _json.loads(zf.read("manifest.json"))
    assert manifest["total_in_zip"] == 0
    assert manifest["missing_payouts"][0]["hand_id"] == "GG-Y"
    assert manifest["missing_payouts"][0]["reason"] == "no_row_in_tournament_payouts"


def test_build_queue_zip_includes_no_payout_when_flag_set():
    """pt23: mesmo sem payout_blob, escrevemos payouts.json só com os 3 hints
    do watcher (equity_model, max_players, script_path). `has_payouts` no
    manifest reflecte a presença do blob, não do hints-file."""
    hand = {
        "id": 1, "hand_id": "GG-Z", "site": "GGPoker",
        "tournament_number": "999",
        "raw": SAMPLE_GG_RAW_FULL,
        "player_names": {"anon_map": SAMPLE_GG_ANON_MAP},
    }
    blob = build_queue_zip([hand], {}, include_no_payout=True)
    zf = _zipfile.ZipFile(_io.BytesIO(blob))
    names = set(zf.namelist())
    assert "GG-Z/hh.txt" in names
    # pt23: payouts.json escrito SEMPRE (mesmo sem blob) para entregar hints
    assert "GG-Z/payouts.json" in names
    payouts = _json.loads(zf.read("GG-Z/payouts.json"))
    # hints presentes, sem dados de payout
    assert payouts["equity_model"] in ("malmuth_harville_icm", "multi_table_icm")
    assert isinstance(payouts["max_players"], int)
    assert payouts["script_path"] is None
    assert "CompletedTournament" not in payouts  # sem blob, só hints
    manifest = _json.loads(zf.read("manifest.json"))
    assert manifest["total_in_zip"] == 1
    assert manifest["hands_included"][0]["has_payouts"] is False


def test_build_queue_zip_hints_merged_with_payouts():
    """pt23: quando há payout_blob, hints são merged como top-level keys
    no payouts.json (sem destruir CompletedTournament/structures)."""
    hand = {
        "id": 1, "hand_id": "GG-HINT", "site": "GGPoker",
        "tournament_number": "111",
        "raw": SAMPLE_GG_RAW_FULL,
        "player_names": {"anon_map": SAMPLE_GG_ANON_MAP},
        "hm3_tags": ["ICM FT"],          # → equity_model = malmuth_harville_icm
        "discord_tags": None,
    }
    blob = build_queue_zip([hand], {("GGPoker", "111"): _fake_payout_blob()})
    zf = _zipfile.ZipFile(_io.BytesIO(blob))
    payouts = _json.loads(zf.read("GG-HINT/payouts.json"))
    # payout blob preservado
    assert payouts["structures"][0]["name"] == "Test BBG $54"
    assert payouts["structures"][0]["bountyType"] == "PKO"
    # hints presentes
    assert payouts["equity_model"] == "malmuth_harville_icm"
    assert isinstance(payouts["max_players"], int)
    assert payouts["script_path"] is None


def test_build_queue_zip_default_equity_when_no_FT_tags():
    """pt23: sem tags FT (HM3 ou Discord), default = multi_table_icm."""
    hand = {
        "id": 1, "hand_id": "GG-DEF", "site": "GGPoker",
        "tournament_number": "111",
        "raw": SAMPLE_GG_RAW_FULL,
        "player_names": {"anon_map": SAMPLE_GG_ANON_MAP},
        "hm3_tags": ["icm-pko"],         # tag não-FT
        "discord_tags": ["sqz-pko"],     # tag não-FT
    }
    blob = build_queue_zip([hand], {("GGPoker", "111"): _fake_payout_blob()})
    zf = _zipfile.ZipFile(_io.BytesIO(blob))
    payouts = _json.loads(zf.read("GG-DEF/payouts.json"))
    assert payouts["equity_model"] == "multi_table_icm"


def test_build_queue_zip_skips_hand_without_raw():
    hand = {
        "id": 1, "hand_id": "GG-NORAW", "site": "GGPoker",
        "tournament_number": "111", "raw": "", "player_names": {},
    }
    blob = build_queue_zip(
        [hand], {("GGPoker", "111"): _fake_payout_blob()},
    )
    zf = _zipfile.ZipFile(_io.BytesIO(blob))
    manifest = _json.loads(zf.read("manifest.json"))
    assert manifest["total_in_zip"] == 0
    assert manifest["skipped"][0]["reason"] == "no_raw_hh"


def test_build_queue_zip_manifest_filters_echo():
    blob = build_queue_zip(
        [], {},
        filters_meta={"tags": ["icm-pko"], "include_no_payout": False},
    )
    zf = _zipfile.ZipFile(_io.BytesIO(blob))
    manifest = _json.loads(zf.read("manifest.json"))
    assert manifest["filters"] == {
        "tags": ["icm-pko"], "include_no_payout": False,
    }
    assert manifest["total_hands_queried"] == 0
    assert manifest["hands_included"] == []


# ── pt25: prune-in-gap-downstream integration nos zips ─────────────────────

# HH UTG-open com 8 seats, 6 voluntários (UTG raise + 5 calls), hero=BB FT-ish.
# 6 players relevantes na mão (max_players=6, derive_max_players). Para
# o prune disparar: players_left > 3 × 6 = 18 → usar 200.
_HH_UTG_OPEN_8MAX = """Poker Hand #TM999: Tournament #99999, Test Tournament $100 - Level5 (200/400) - 2026/05/01 00:00:00
Table 'X' 8-max Seat #4 is the button
Seat 1: P1 (10000 in chips)
Seat 2: P2 (10000 in chips)
Seat 3: P3 (10000 in chips)
Seat 4: P4 (10000 in chips)
Seat 5: P5 (10000 in chips)
Seat 6: Hero (10000 in chips)
Seat 7: UTGopener (10000 in chips)
Seat 8: P8 (10000 in chips)
P5: posts small blind 200
Hero: posts big blind 400
*** HOLE CARDS ***
Dealt to Hero [As Kd]
UTGopener: raises 800 to 1200
P8: calls 1200
P1: calls 1200
P2: calls 1200
P3: calls 1200
P4: calls 1200
P5: folds
Hero: folds
*** SUMMARY ***
"""


def test_build_queue_zip_includes_script_js_when_prune_fires():
    """pt25: aggressor=UTG (idx 2), max_players=6, players_left=200 (200 > 3*6=18)
    → script.js no zip + payouts.script_path='script.js' + manifest tem
    prune_aggressor=2, prune_downstream=[3,4,5,6,7,0]."""
    hand = {
        "id": 1, "hand_id": "GG-PRUNE", "site": "GGPoker",
        "tournament_number": "111",
        "raw": _HH_UTG_OPEN_8MAX,
        "player_names": {},
        "players_left": 200,  # > 3*6 → prune fires
    }
    blob = build_queue_zip([hand], {("GGPoker", "111"): _fake_payout_blob()})
    zf = _zipfile.ZipFile(_io.BytesIO(blob))
    names = set(zf.namelist())
    assert "GG-PRUNE/script.js" in names
    assert "GG-PRUNE/payouts.json" in names

    # payouts.json contém script_path apontando para "script.js" (relativo)
    payouts = _json.loads(zf.read("GG-PRUNE/payouts.json"))
    assert payouts["script_path"] == "script.js"

    # script.js contém hints injectados (não defaults)
    js = zf.read("GG-PRUNE/script.js").decode("utf-8")
    assert "let REAL_AGGRESSOR_POS = 2;" in js
    assert "let DOWNSTREAM_POSITIONS = [3, 4, 5, 6, 7, 0];" in js

    # manifest tem metadata do prune
    manifest = _json.loads(zf.read("manifest.json"))
    entry = manifest["hands_included"][0]
    assert entry["prune_aggressor"] == 2
    assert entry["prune_downstream"] == [3, 4, 5, 6, 7, 0]
    assert entry["has_prune_script"] is True


def test_build_queue_zip_excludes_script_js_when_no_players_left():
    """pt25: aggressor identificado mas players_left None → derive_prune
    devolve [] → sem script.js no zip + script_path mantém None."""
    hand = {
        "id": 1, "hand_id": "GG-NOPL", "site": "GGPoker",
        "tournament_number": "111",
        "raw": _HH_UTG_OPEN_8MAX,
        "player_names": {},
        # SEM players_left → fallback None
    }
    blob = build_queue_zip([hand], {("GGPoker", "111"): _fake_payout_blob()})
    zf = _zipfile.ZipFile(_io.BytesIO(blob))
    names = set(zf.namelist())
    assert "GG-NOPL/script.js" not in names

    payouts = _json.loads(zf.read("GG-NOPL/payouts.json"))
    assert payouts["script_path"] is None  # hint default mantém

    manifest = _json.loads(zf.read("manifest.json"))
    entry = manifest["hands_included"][0]
    # aggressor ainda foi computed (UTG=2) mas downstream=[] → no script
    assert entry["prune_aggressor"] == 2
    assert entry["prune_downstream"] == []
    assert entry["has_prune_script"] is False


def test_build_queue_zip_excludes_script_js_when_FT_phase():
    """pt25: aggressor=UTG, max_players=6, players_left=18 (= threshold 3*6=18,
    não strict-greater) → [] → sem script.js."""
    hand = {
        "id": 1, "hand_id": "GG-FT", "site": "GGPoker",
        "tournament_number": "111",
        "raw": _HH_UTG_OPEN_8MAX,
        "player_names": {},
        "players_left": 18,  # = threshold → não dispara
    }
    blob = build_queue_zip([hand], {("GGPoker", "111"): _fake_payout_blob()})
    zf = _zipfile.ZipFile(_io.BytesIO(blob))
    assert "GG-FT/script.js" not in set(zf.namelist())

    manifest = _json.loads(zf.read("manifest.json"))
    entry = manifest["hands_included"][0]
    assert entry["has_prune_script"] is False


# ── pt25c: manifest field prune_script_error + escalation OSError ─────────

def test_build_queue_zip_prune_script_error_None_when_downstream_empty():
    """pt25c: caso normal (FT phase, downstream=[]) → `prune_script_error=None`
    no manifest. Condição-não-satisfeita, não-erro."""
    hand = {
        "id": 1, "hand_id": "GG-FT2", "site": "GGPoker",
        "tournament_number": "111",
        "raw": _HH_UTG_OPEN_8MAX,
        "player_names": {},
        "players_left": 18,  # FT phase
    }
    blob = build_queue_zip([hand], {("GGPoker", "111"): _fake_payout_blob()})
    zf = _zipfile.ZipFile(_io.BytesIO(blob))
    manifest = _json.loads(zf.read("manifest.json"))
    entry = manifest["hands_included"][0]
    assert entry["has_prune_script"] is False
    assert entry["prune_script_error"] is None  # not-applicable, not-error


def test_build_queue_zip_prune_script_error_populated_on_template_io_failure(monkeypatch):
    """pt25c: força OSError em generate_hrc_script (template inexistente)
    via monkeypatch ao path module-level. `downstream` é populated mas
    `js` falha → `prune_script_error` capta o erro no manifest."""
    from app.services import queue_export as qe
    monkeypatch.setattr(
        qe, "_PRUNE_JS_TEMPLATE_PATH",
        "/nonexistent/path/to/template.js",
    )

    hand = {
        "id": 1, "hand_id": "GG-PRUNE-FAIL", "site": "GGPoker",
        "tournament_number": "111",
        "raw": _HH_UTG_OPEN_8MAX,
        "player_names": {},
        "players_left": 200,  # > 3*6=18 → prune fires
    }
    blob = build_queue_zip([hand], {("GGPoker", "111"): _fake_payout_blob()})
    zf = _zipfile.ZipFile(_io.BytesIO(blob))
    names = set(zf.namelist())
    # script.js NÃO escrito (porque generate_hrc_script falhou)
    assert "GG-PRUNE-FAIL/script.js" not in names

    manifest = _json.loads(zf.read("manifest.json"))
    entry = manifest["hands_included"][0]
    # Mas downstream está populated (mostra que prune lógica correu)
    assert entry["prune_aggressor"] == 2
    assert entry["prune_downstream"] == [3, 4, 5, 6, 7, 0]
    assert entry["has_prune_script"] is False
    # E o erro é capturado no manifest (vs silent warning anterior)
    assert entry["prune_script_error"] is not None
    err = entry["prune_script_error"]
    assert "FileNotFoundError" in err
    assert "/nonexistent/path" in err


# ── pt25-revisado: _resolve_players_left via lobby_processing_log ───────────

from app.services.queue_export import _resolve_players_left


def test_resolve_players_left_inline_hand_wins():
    """Branch 1: se hand['players_left'] tem int → devolve directo, sem DB."""
    assert _resolve_players_left({"players_left": 87}, None) == 87
    # Mesmo com tournament_number presente, inline tem prioridade.
    assert _resolve_players_left(
        {"players_left": 50, "tournament_number": "ZZZ"}, None,
    ) == 50


def test_resolve_players_left_via_lobby_lookup(monkeypatch):
    """Branch 2: hand sem players_left inline → query lobby_processing_log
    por tournament_number; mock devolve row com players_left."""
    calls: list = []

    def fake_query(sql, params=None):
        calls.append((sql, params))
        return [{"players_left": 42}]

    monkeypatch.setattr("app.db.query", fake_query)

    out = _resolve_players_left({"tournament_number": "281416137"}, None)
    assert out == 42
    # Confirma que query foi disparada com o tn correcto.
    assert len(calls) == 1
    assert calls[0][1] == ("281416137",)
    assert "lobby_processing_log" in calls[0][0]
    assert "result = 'success'" in calls[0][0]
    assert "players_left IS NOT NULL" in calls[0][0]


def test_resolve_players_left_no_lobby_row(monkeypatch):
    """Branch 2 mas 0 rows → None (prune off, graceful)."""
    monkeypatch.setattr("app.db.query", lambda *a, **kw: [])
    out = _resolve_players_left({"tournament_number": "281416137"}, None)
    assert out is None


def test_resolve_players_left_no_tournament_number():
    """Sem tn → None imediato (não chega a tocar DB)."""
    assert _resolve_players_left({"hand_id": "GG-X"}, None) is None
    assert _resolve_players_left({}, None) is None
    assert _resolve_players_left(None, None) is None


def test_resolve_players_left_db_error_returns_None(monkeypatch):
    """Excepção no query (BD down, schema mismatch) → None (graceful)."""

    def raising(*a, **kw):
        raise RuntimeError("simulated DB error")

    monkeypatch.setattr("app.db.query", raising)
    out = _resolve_players_left({"tournament_number": "281416137"}, None)
    assert out is None


def test_resolve_players_left_non_int_row_returns_None(monkeypatch):
    """Row devolve coluna mas com tipo inesperado → None (defensivo)."""
    monkeypatch.setattr("app.db.query", lambda *a, **kw: [{"players_left": "not_an_int"}])
    out = _resolve_players_left({"tournament_number": "281416137"}, None)
    assert out is None


# ── pt25-revisado: lobby_vision parse passa por players_left ────────────────

from app.services.lobby_vision import parse_and_validate_lobby_json


def test_lobby_vision_parses_players_left():
    """Vision JSON com players_left int → parser preserva-o intacto."""
    raw = (
        '{"site": "GGPoker", "tournament_name": "Bounty Hunters Big Game $215",'
        ' "prizes": {"1": 100.0, "2": 50.0},'
        ' "entrants": 500, "players_left": 87, "starting_stack": 10000}'
    )
    parsed = parse_and_validate_lobby_json(raw)
    assert parsed is not None
    assert parsed["players_left"] == 87
    assert parsed["entrants"] == 500


def test_lobby_vision_players_left_optional():
    """Vision JSON sem players_left (campo omitted) → parser ainda devolve
    dict válido (field é opcional, não invalida)."""
    raw = (
        '{"site": "GGPoker", "tournament_name": "X",'
        ' "prizes": {"1": 100.0}, "entrants": 500}'
    )
    parsed = parse_and_validate_lobby_json(raw)
    assert parsed is not None
    assert parsed.get("players_left") is None
