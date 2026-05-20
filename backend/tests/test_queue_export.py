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


# ── pt24 bounty injection REMOVIDO em pt28-v3 (#HRC-GG-KOS-EXTRACTION reabre).
# Smoke 20 Maio: HRC parser rejeita HH com ", $X.XX bounty)" nas Seat lines.
# `_inject_bounties_into_seat_lines` foi apagada. Bounties continuam em
# payouts.json paralelo (HRC le por essa via). Tests pt24 abaixo removidos.


# ── pt25: #HRC-PRUNE-IN-GAP-DOWNSTREAM helpers ─────────────────────────────

import os as _os
from app.services.queue_export import (
    derive_real_aggressor_position,
)


# ── derive_real_aggressor_position ──────────────────────────────────────────

# Helper builder para HHs de teste. 8-max, button configurável.
# pt25d HRC docs convention (UTG=0 first-to-act preflop, BB=N-1) para 8-max
# com button=Seat #4:
#   UTG=Seat 7 (idx 0), EP=Seat 8 (idx 1), MP=Seat 1 (idx 2), HJ=Seat 2 (idx 3),
#   CO=Seat 3 (idx 4), BU=Seat 4 (idx 5), SB=Seat 5 (idx 6), BB=Seat 6 (idx 7).

def _hh_8max_btn4(preflop_actions: list[str]) -> str:
    """Constrói uma HH 8-max minimal com button Seat #4 e acções preflop
    customizáveis."""
    lines = [
        "Poker Hand #TM1: Tournament #100, Test - Level5 (200/400) - 2026/05/01 00:00:00",
        "Table 'A' 8-max Seat #4 is the button",
        "Seat 1: MPplayer (10000 in chips)",      # MP, HRC idx 2
        "Seat 2: HJplayer (10000 in chips)",      # HJ, HRC idx 3
        "Seat 3: COplayer (10000 in chips)",      # CO, HRC idx 4
        "Seat 4: Hero (10000 in chips)",          # BU, HRC idx 5
        "Seat 5: SBplayer (10000 in chips)",      # SB, HRC idx 6
        "Seat 6: BBplayer (10000 in chips)",      # BB, HRC idx 7
        "Seat 7: UTGplayer (10000 in chips)",     # UTG, HRC idx 0
        "Seat 8: EPplayer (10000 in chips)",      # EP, HRC idx 1
        "SBplayer: posts small blind 200",
        "BBplayer: posts big blind 400",
        "*** HOLE CARDS ***",
        "Dealt to Hero [As Kd]",
    ]
    lines.extend(preflop_actions)
    lines.append("*** SUMMARY ***")
    return "\n".join(lines) + "\n"


def test_aggressor_UTG_opens():
    """8-max, UTG raise first → HRC idx 0 (pt25d convention)."""
    hh = _hh_8max_btn4(["UTGplayer: raises 800 to 1200"])
    assert derive_real_aggressor_position(hh) == 0


def test_aggressor_EP_opens():
    """UTG folds, EP raises → HRC idx 1."""
    hh = _hh_8max_btn4([
        "UTGplayer: folds",
        "EPplayer: raises 800 to 1200",
    ])
    assert derive_real_aggressor_position(hh) == 1


def test_aggressor_MP_opens():
    """UTG/EP fold, MP raises → HRC idx 2."""
    hh = _hh_8max_btn4([
        "UTGplayer: folds",
        "EPplayer: folds",
        "MPplayer: raises 800 to 1200",
    ])
    assert derive_real_aggressor_position(hh) == 2


def test_aggressor_HJ_opens():
    """UTG/EP/MP fold, HJ raises → HRC idx 3."""
    hh = _hh_8max_btn4([
        "UTGplayer: folds",
        "EPplayer: folds",
        "MPplayer: folds",
        "HJplayer: raises 800 to 1200",
    ])
    assert derive_real_aggressor_position(hh) == 3


def test_aggressor_CO_opens():
    """UTG/EP/MP/HJ fold, CO raises → HRC idx 4."""
    hh = _hh_8max_btn4([
        "UTGplayer: folds",
        "EPplayer: folds",
        "MPplayer: folds",
        "HJplayer: folds",
        "COplayer: raises 800 to 1200",
    ])
    assert derive_real_aggressor_position(hh) == 4


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


def test_aggressor_SB_opens_returns_idx6():
    """pt25d: todos foldam até SB, SB raises → SB idx (N-2 = 6 em 8-handed).
    Não há mais early-return None desde pt25d (era heurística da convenção
    velha onde SB=0). `derive_prune_downstream` devolve [] naturalmente
    para esse caso (downstream vazio porque só BB sobra)."""
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
    assert derive_real_aggressor_position(hh) == 6


def test_aggressor_BU_opens_returns_idx5():
    """UTG..CO fold, BU (Hero, idx 5 em 8-handed = N-3) raises → 5.
    Test crítico para GG-5914506215 real (Hero=BU opens, smoke pt23)."""
    hh = _hh_8max_btn4([
        "UTGplayer: folds",
        "EPplayer: folds",
        "MPplayer: folds",
        "HJplayer: folds",
        "COplayer: folds",
        "Hero: raises 800 to 1200",
    ])
    assert derive_real_aggressor_position(hh) == 5


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
    """PS sample (PS-260299428000, 6-max BU=Seat 5, 5 sentados):
    Votsarrr@Seat5=BU opens → idx 2 (pt25d: BU em 5-handed = N-3 = 2)."""
    out = derive_real_aggressor_position(_HH_PS_REAL)
    assert out is not None
    # pt25d: button=Seat5; seat_list=[1,2,4,5,6]; btn_idx_in_list=3; n=5;
    # first_to_act_offset=3 → hrc0=seat_list[(3+3+0)%5=1]=Seat2(carlos8surf,UTG),
    # hrc1=Seat4(QuimDiamond,HJ), hrc2=Seat5(Votsarrr,BU),
    # hrc3=Seat6(UltraLoubard,SB), hrc4=Seat1(kokonakueka,BB).
    # Votsarrr opens → idx 2. ✓
    assert out == 2


def test_aggressor_GG_real_sample():
    """GG sample (GG real, 8-max BU=Seat 1, 5 sentados): 1º raise é
    221ebf0d@Seat8 após 8db88342@Seat7 fold. pt25d: HJ em 5-handed = idx 1."""
    out = derive_real_aggressor_position(_HH_GG_REAL)
    assert out is not None
    # pt25d: button=Seat1; seat_list=[1,5,6,7,8]; btn_idx_in_list=0; n=5;
    # first_to_act_offset=3 → hrc0=seat_list[3]=Seat7(8db88342,UTG),
    # hrc1=Seat8(221ebf0d,HJ), hrc2=Seat1(Hero,BU),
    # hrc3=Seat5(b839c780,SB), hrc4=Seat6(3343ebc6,BB).
    # 8db88342 folds (UTG=0), 221ebf0d raises (HJ=1). Aggressor=1.
    assert out == 1


def test_aggressor_WN_real_sample_INTERSTELLAR():
    """Winamax INTERSTELLAR (smoke target pt25b+pt25d): 6-max 5-sentados
    BU=Seat 2; blueballs67@Seat5=UTG raises first → idx 0 (pt25d)."""
    out = derive_real_aggressor_position(_HH_WN_REAL)
    assert out is not None
    # pt25d: seat_list=[1,2,3,4,5]; btn_idx_in_list=1; n=5;
    # first_to_act_offset=3 → hrc0=seat_list[(1+3+0)%5=4]=Seat5(blueballs67,UTG),
    # hrc1=Seat1(yousnouf75,HJ), hrc2=Seat2(imbagosu,BU),
    # hrc3=Seat3(Beu_Teu,SB), hrc4=Seat4(thinvalium,BB).
    # blueballs67 raises = idx 0 (UTG). ✓
    assert out == 0


def test_aggressor_WPN_real_sample():
    """WPN sample (8-max BU=Seat 1, 8 sentados full): DAVIDSBAGOFICE@Seat7
    raises após 3 folds. pt25d: HJ em 8-handed = idx 3."""
    out = derive_real_aggressor_position(_HH_WPN_REAL)
    assert out is not None
    # pt25d: 8 sentados, seat_list=[1..8], btn_idx_in_list=0, first_offset=3 →
    # hrc0=Seat4(TuuusTuuuuus,UTG), hrc1=Seat5(egegey1,EP),
    # hrc2=Seat6(pocahontas94,MP), hrc3=Seat7(DAVIDSBAGOFICE,HJ),
    # hrc4=Seat8(eagle47,CO), hrc5=Seat1(Jetsies,BU),
    # hrc6=Seat2(cringemeariver,SB), hrc7=Seat3(AbamaAbezyana,BB).
    # TuuusTuuuuus/egegey1/pocahontas94 fold (idx 0/1/2), DAVIDSBAGOFICE raises (idx 3).
    assert out == 3


# ── pt25b ETAPA 3: derive_seats_in_preflop_order + derive_table_format ──────

from app.services.queue_export import (
    derive_seats_in_preflop_order,
    derive_table_format,
)


def test_seats_PS_real_sample():
    """PS-260299428000: 6-max BU=Seat 5, 5 sentados (Seat 3 missing).
    pt25d order: UTG, HJ, BU, SB, BB (UTG=idx 0)."""
    seats = derive_seats_in_preflop_order(_HH_PS_REAL)
    assert len(seats) == 5
    assert seats[0] == {"seat": 2, "position": "UTG", "hrc_idx": 0, "nick": "carlos8surf"}
    assert seats[1] == {"seat": 4, "position": "HJ",  "hrc_idx": 1, "nick": "QuimDiamond"}
    assert seats[2] == {"seat": 5, "position": "BU", "hrc_idx": 2, "nick": "Votsarrr"}
    assert seats[3] == {"seat": 6, "position": "SB",  "hrc_idx": 3, "nick": "UltraLoubard"}
    assert seats[4] == {"seat": 1, "position": "BB",  "hrc_idx": 4, "nick": "kokonakueka"}


def test_seats_GG_real_sample():
    """GG-5939385803: 8-max BU=Seat 1, 5 sentados (Seats 2,3,4 missing).
    pt25d order: UTG, HJ, BU, SB, BB."""
    seats = derive_seats_in_preflop_order(_HH_GG_REAL)
    assert len(seats) == 5
    nicks = [s["nick"] for s in seats]
    assert nicks == ["8db88342", "221ebf0d", "Hero", "b839c780", "3343ebc6"]
    positions = [s["position"] for s in seats]
    assert positions == ["UTG", "HJ", "BU", "SB", "BB"]


def test_seats_WN_real_sample_INTERSTELLAR():
    """WN-INTERSTELLAR (smoke target pt25b+pt25d): 6-max BU=Seat 2, 5 sentados.
    pt25d order: UTG, HJ, BU, SB, BB. blueballs67=UTG=idx 0 (era idx 2)."""
    seats = derive_seats_in_preflop_order(_HH_WN_REAL)
    assert len(seats) == 5
    nicks = [s["nick"] for s in seats]
    assert nicks == ["blueballs67", "yousnouf75", "imbagosu", "Beu_Teu", "thinvalium"]
    positions = [s["position"] for s in seats]
    assert positions == ["UTG", "HJ", "BU", "SB", "BB"]
    # blueballs67 = UTG = hrc_idx 0 (pt25d aggressor)
    assert next(s for s in seats if s["nick"] == "blueballs67")["hrc_idx"] == 0


def test_seats_WPN_real_sample():
    """WPN: 8-max BU=Seat 1, 8 sentados full.
    pt25d order: UTG, EP, MP, HJ, CO, BU, SB, BB."""
    seats = derive_seats_in_preflop_order(_HH_WPN_REAL)
    assert len(seats) == 8
    nicks = [s["nick"] for s in seats]
    assert nicks[0] == "TuuusTuuuuus"     # UTG
    assert nicks[1] == "egegey1"           # EP
    assert nicks[2] == "pocahontas94"      # MP
    assert nicks[3] == "DAVIDSBAGOFICE"    # HJ (aggressor)
    assert nicks[5] == "Jetsies"           # BU
    assert nicks[6] == "cringemeariver"    # SB
    assert nicks[7] == "AbamaAbezyana"     # BB
    positions = [s["position"] for s in seats]
    assert positions == ["UTG", "EP", "MP", "HJ", "CO", "BU", "SB", "BB"]


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


# ── hrc_script_gen: gerador novo per-hand (Maio 2026) ───────────────────────
# Substitui os antigos tests de derive_prune_downstream + generate_hrc_script
# (mecanismo de prune via JS removido — migra para Bloco 2 do watcher).

from app.services.hrc_script_gen import (
    apply_sizings_overrides,
    build_sizings_overrides,
    compute_effective_stack_bb,
    generate_hrc_script_for_hand,
    _CLASSIC_3BET_DEFAULTS,
    _OPEN_ALLIN_THRESHOLD_BB,
    _bucket_3bet,
    _bucket_4bet5bet,
    _bucket_open,
    _classic_3bet_band,
    _compute_classic_3bet_overrides,
    _format_sizing_array,
    _parse_preflop_actions,
    _parse_seat_stacks,
    _position_bucket_open,
    _postflop_rank,
)
from app.services.queue_export import derive_seats_in_preflop_order


# ── _parse_seat_stacks + compute_effective_stack_bb (cross-site) ────────────

def test_parse_seat_stacks_PS_real():
    """PS: chips com vírgula opcional + ' in chips'."""
    out = _parse_seat_stacks(_HH_PS_REAL)
    assert out["Votsarrr"] == 633451.0
    assert out["UltraLoubard"] == 391164.0


def test_parse_seat_stacks_GG_real():
    out = _parse_seat_stacks(_HH_GG_REAL)
    assert out["Hero"] == 40000.0
    assert out["221ebf0d"] == 42483.0


def test_parse_seat_stacks_WN_real():
    """WN: chips sem ' in chips', com bounty depois — regex pára em ')'."""
    out = _parse_seat_stacks(_HH_WN_REAL)
    assert out["blueballs67"] == 354758.0
    assert out["imbagosu"] == 615675.0


def test_parse_seat_stacks_WPN_real():
    """WPN: chips com 2 decimais."""
    out = _parse_seat_stacks(_HH_WPN_REAL)
    assert out["Jetsies"] == 448465.0
    assert out["eagle47"] == 34502.0


def test_compute_effective_stack_bb_PS():
    """PS sample: BB=25000; min stack = UltraLoubard 391164 → 391164/25000 = 15.65 BB."""
    eff = compute_effective_stack_bb(_HH_PS_REAL, level_bb=25000)
    assert eff == 15.65


def test_compute_effective_stack_bb_GG():
    """GG sample: BB=300; min stack = Hero 40000 → 40000/300 ≈ 133.33 BB."""
    eff = compute_effective_stack_bb(_HH_GG_REAL, level_bb=300)
    assert eff == 133.33


def test_compute_effective_stack_bb_no_seats_returns_None():
    assert compute_effective_stack_bb("nope nothing", level_bb=100) is None


def test_compute_effective_stack_bb_invalid_bb_returns_None():
    assert compute_effective_stack_bb(_HH_GG_REAL, level_bb=0) is None
    assert compute_effective_stack_bb(_HH_GG_REAL, level_bb=None) is None


# ── _position_bucket_open ─────────────────────────────────────────────────

def test_position_bucket_open_returns_BU_for_BU_BTN_HU():
    assert _position_bucket_open("BU") == "BU"
    assert _position_bucket_open("BTN") == "BU"
    assert _position_bucket_open("BU/SB") == "BU"


def test_position_bucket_open_returns_SB_BB():
    assert _position_bucket_open("SB") == "SB"
    assert _position_bucket_open("BB") == "BB"


def test_position_bucket_open_returns_OTHERS_for_everything_else():
    for pos in ("UTG", "EP", "MP", "EP1", "EP2", "HJ", "CO"):
        assert _position_bucket_open(pos) == "OTHERS"


def test_position_bucket_open_None_or_empty_returns_OTHERS():
    assert _position_bucket_open(None) == "OTHERS"
    assert _position_bucket_open("") == "OTHERS"


# ── _postflop_rank — IP/OOP lookup ─────────────────────────────────────────

def test_postflop_rank_5handed():
    """5-handed (UTG=0, HJ=1, BU=2, SB=3, BB=4): postflop order = SB=0, BB=1,
    UTG=2, HJ=3, BU=4 (BU most IP)."""
    assert _postflop_rank(0, 5) == 2   # UTG
    assert _postflop_rank(1, 5) == 3   # HJ
    assert _postflop_rank(2, 5) == 4   # BU
    assert _postflop_rank(3, 5) == 0   # SB
    assert _postflop_rank(4, 5) == 1   # BB


def test_postflop_rank_6handed():
    """6-handed: BU=3 → rank 5 (most IP)."""
    assert _postflop_rank(3, 6) == 5
    assert _postflop_rank(4, 6) == 0   # SB
    assert _postflop_rank(5, 6) == 1   # BB


# ── _parse_preflop_actions ─────────────────────────────────────────────────

def test_parse_preflop_actions_GG_HJ_open():
    """GG sample: 221ebf0d (HJ, idx 1) opens to 600. Stack 42483 / BB 300 → eff
    ~141 BB. Cobre bet_count=1 + position resolution."""
    seats = derive_seats_in_preflop_order(_HH_GG_REAL)
    actions = _parse_preflop_actions(_HH_GG_REAL, seats, level_sb=150, level_bb=300)
    assert len(actions) == 1
    a = actions[0]
    assert a["bet_count"] == 1
    assert a["nick"] == "221ebf0d"
    assert a["hrc_idx"] == 1
    assert a["position"] == "HJ"
    assert a["to_amount_bb"] == 2.0
    assert a["callers_before"] == 0


def test_parse_preflop_actions_PS_BU_jam():
    """PS sample: Votsarrr (BU, idx 2 em 5-handed) raises 605201 to 630201
    (jam). BB 25000 → 630201/25000 ≈ 25.21 BB."""
    seats = derive_seats_in_preflop_order(_HH_PS_REAL)
    actions = _parse_preflop_actions(_HH_PS_REAL, seats, level_sb=12500, level_bb=25000)
    assert len(actions) == 1
    a = actions[0]
    assert a["bet_count"] == 1
    assert a["nick"] == "Votsarrr"
    assert a["position"] == "BU"
    assert a["to_amount_bb"] == 25.21


def test_parse_preflop_actions_WN_squeeze():
    """WN INTERSTELLAR: blueballs67 (UTG) raises to 16000, yousnouf75 calls,
    imbagosu folds, Beu_Teu (SB) 3-bets to 64000. SB 3-bet com 1 caller
    inbetween → callers_before=1 (squeeze)."""
    seats = derive_seats_in_preflop_order(_HH_WN_REAL)
    actions = _parse_preflop_actions(_HH_WN_REAL, seats, level_sb=4000, level_bb=8000)
    assert len(actions) == 2
    open_action = actions[0]
    sqz_action = actions[1]
    assert open_action["bet_count"] == 1
    assert open_action["nick"] == "blueballs67"
    assert open_action["position"] == "UTG"
    assert open_action["to_amount_bb"] == 2.0
    assert sqz_action["bet_count"] == 2
    assert sqz_action["nick"] == "Beu_Teu"
    assert sqz_action["position"] == "SB"
    assert sqz_action["to_amount_bb"] == 8.0
    assert sqz_action["callers_before"] == 1


def test_parse_preflop_actions_walk_to_BB_returns_empty():
    """HH sem nenhum raise → list vazio."""
    hh = (
        "Hand #X: Test - Level1 (50/100) - 2026/01/01\n"
        "Table 'T' 6-max Seat #1 is the button\n"
        "Seat 1: A (10000 in chips)\n"
        "Seat 2: B (10000 in chips)\n"
        "B: posts small blind 50\n"
        "A: posts big blind 100\n"
        "*** HOLE CARDS ***\n"
        "B: folds\n"
        "*** SUMMARY ***\n"
    )
    seats = derive_seats_in_preflop_order(hh)
    actions = _parse_preflop_actions(hh, seats, level_sb=50, level_bb=100)
    assert actions == []


# ── _bucket_open / _bucket_3bet / _bucket_4bet5bet ─────────────────────────

def test_bucket_open_mapping():
    assert _bucket_open({"bet_count": 1, "position": "UTG"}) == "SIZES_OPEN_OTHERS"
    assert _bucket_open({"bet_count": 1, "position": "BU"}) == "SIZES_OPEN_BU"
    assert _bucket_open({"bet_count": 1, "position": "SB"}) == "SIZES_OPEN_SB"
    assert _bucket_open({"bet_count": 1, "position": "BB"}) == "SIZES_OPEN_BB"


def test_bucket_open_returns_None_for_non_open():
    assert _bucket_open({"bet_count": 2, "position": "BU"}) is None


def test_bucket_3bet_squeeze_buckets():
    # Squeeze IP (HJ 3-bets after open + 1 caller)
    a = {"bet_count": 2, "position": "HJ", "callers_before": 1}
    assert _bucket_3bet(a, opener_position="UTG") == "SIZES_3BET_SQUEEZE_IP"
    # Squeeze SB
    a = {"bet_count": 2, "position": "SB", "callers_before": 1}
    assert _bucket_3bet(a, opener_position="UTG") == "SIZES_3BET_SQUEEZE_SB"
    # Squeeze BB
    a = {"bet_count": 2, "position": "BB", "callers_before": 1}
    assert _bucket_3bet(a, opener_position="UTG") == "SIZES_3BET_SQUEEZE_BB"


def test_bucket_3bet_non_squeeze_buckets():
    # SB 3-bets BB
    a = {"bet_count": 2, "position": "SB", "callers_before": 0}
    assert _bucket_3bet(a, opener_position="BB") == "SIZES_3BET_SB_VS_BB"
    # SB 3-bets other
    a = {"bet_count": 2, "position": "SB", "callers_before": 0}
    assert _bucket_3bet(a, opener_position="UTG") == "SIZES_3BET_SB_VS_OTHER"
    # BB 3-bets SB
    a = {"bet_count": 2, "position": "BB", "callers_before": 0}
    assert _bucket_3bet(a, opener_position="SB") == "SIZES_3BET_BB_VS_SB"
    # BB 3-bets other
    a = {"bet_count": 2, "position": "BB", "callers_before": 0}
    assert _bucket_3bet(a, opener_position="UTG") == "SIZES_3BET_BB_VS_OTHER"
    # Other 3-bets (IP)
    a = {"bet_count": 2, "position": "HJ", "callers_before": 0}
    assert _bucket_3bet(a, opener_position="UTG") == "SIZES_3BET_IP"


def test_bucket_4bet5bet_IP_OOP():
    # 4-bet by BU (idx 5) vs 3-better SB (idx 6) em 8-handed → BU postflop
    # rank 7 > SB rank 0 → IP.
    a = {"bet_count": 3, "hrc_idx": 5, "previous_raiser_idx": 6}
    assert _bucket_4bet5bet(a, n_seated=8) == "SIZES_POT_4BET_IP"
    # 5-bet by SB (idx 6) vs 4-better BU (idx 5) → SB rank 0 < BU rank 7 → OOP.
    a = {"bet_count": 4, "hrc_idx": 6, "previous_raiser_idx": 5}
    assert _bucket_4bet5bet(a, n_seated=8) == "SIZES_POT_5BET_OOP"


def test_bucket_4bet5bet_returns_None_for_non_4bet5bet():
    assert _bucket_4bet5bet({"bet_count": 1, "hrc_idx": 0, "previous_raiser_idx": None}, n_seated=6) is None
    assert _bucket_4bet5bet({"bet_count": 2, "hrc_idx": 0, "previous_raiser_idx": 0}, n_seated=6) is None


# ── _format_sizing_array — JS literal ───────────────────────────────────────

def test_format_sizing_array_ints_and_ALLIN():
    assert _format_sizing_array([2, "ALLIN"]) == "[2, ALLIN]"


def test_format_sizing_array_floats():
    assert _format_sizing_array([2.5, "ALLIN"]) == "[2.5, ALLIN]"
    # 2.0 → "2" (drop trailing zero)
    assert _format_sizing_array([2.0, "ALLIN"]) == "[2, ALLIN]"


def test_format_sizing_array_single_value():
    assert _format_sizing_array([3.5]) == "[3.5]"


# ── apply_sizings_overrides — substituição no template ─────────────────────

_CANONICAL_TEMPLATE_PATH = _os.path.join(
    _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
    "app", "services", "hrc_scripts", "mtt_advanced_canonical_2026.js",
)


def _read_template():
    with open(_CANONICAL_TEMPLATE_PATH, "r", encoding="utf-8") as f:
        return f.read()


def test_apply_overrides_substitutes_SIZES_OPEN_OTHERS():
    tpl = _read_template()
    out = apply_sizings_overrides(tpl, {"SIZES_OPEN_OTHERS": [2.5, "ALLIN"]})
    assert "let SIZES_OPEN_OTHERS = [2.5, ALLIN];" in out
    # Default original do template foi substituído
    assert "let SIZES_OPEN_OTHERS = [2, ALLIN];" not in out
    # 1 ocorrência apenas
    assert out.count("let SIZES_OPEN_OTHERS") == 1


def test_apply_overrides_leaves_untouched_vars_alone():
    tpl = _read_template()
    out = apply_sizings_overrides(tpl, {"SIZES_OPEN_OTHERS": [2.5, "ALLIN"]})
    # SIZES_OPEN_BU não foi tocado → fica no default do template
    assert "let SIZES_OPEN_BU = [2, ALLIN];" in out


def test_apply_overrides_handles_multiple():
    tpl = _read_template()
    out = apply_sizings_overrides(tpl, {
        "SIZES_OPEN_OTHERS": [2.5, "ALLIN"],
        "SIZES_3BET_BB_VS_OTHER": [9, "ALLIN"],
        "SIZES_POT_4BET_OOP": [0.45, "ALLIN"],
    })
    assert "let SIZES_OPEN_OTHERS = [2.5, ALLIN];" in out
    assert "let SIZES_3BET_BB_VS_OTHER = [9, ALLIN];" in out
    assert "let SIZES_POT_4BET_OOP = [0.45, ALLIN];" in out


def test_apply_overrides_unknown_var_logs_and_skips():
    tpl = _read_template()
    # Var inexistente → log warning, output igual ao input
    out = apply_sizings_overrides(tpl, {"SIZES_NONEXISTENT": [1, "ALLIN"]})
    assert out == tpl


# ── build_sizings_overrides — end-to-end ──────────────────────────────────

def test_build_sizings_overrides_GG_HJ_open_deep():
    """GG sample: HJ opens 2bb, eff stack ~141bb (>25) → SIZES_OPEN_OTHERS=[2]
    (sem ALLIN porque deep)."""
    seats = derive_seats_in_preflop_order(_HH_GG_REAL)
    eff = compute_effective_stack_bb(_HH_GG_REAL, level_bb=300)
    out = build_sizings_overrides(
        _HH_GG_REAL, level_sb=150, level_bb=300, seats=seats,
        effective_stack_bb=eff,
    )
    assert "SIZES_OPEN_OTHERS" in out
    assert out["SIZES_OPEN_OTHERS"] == [2.0]  # sem ALLIN — eff > 25
    # Nenhum 3-bet/4-bet na mão
    assert "SIZES_3BET_IP" not in out


def test_build_sizings_overrides_PS_BU_jam_shallow():
    """PS sample: BU jam (~25.21 BB to). Eff stack = UltraLoubard 391164/25000
    ≈ 15.65 BB (≤25) → SIZES_OPEN_BU = [25.21, ALLIN]."""
    seats = derive_seats_in_preflop_order(_HH_PS_REAL)
    eff = compute_effective_stack_bb(_HH_PS_REAL, level_bb=25000)
    out = build_sizings_overrides(
        _HH_PS_REAL, level_sb=12500, level_bb=25000, seats=seats,
        effective_stack_bb=eff,
    )
    assert out["SIZES_OPEN_BU"] == [25.21, "ALLIN"]


def test_build_sizings_overrides_WN_squeeze_3bet():
    """WN: UTG opens 2bb + SB squeeze 3-bet 8bb. eff stack = min(stacks)/BB.
    yousnouf75 163754 / 8000 ≈ 20.47 BB → ≤25 → ALLIN nos opens fica.
    Espera: SIZES_OPEN_OTHERS=[2, ALLIN], SIZES_3BET_SQUEEZE_SB=[8, ALLIN]."""
    seats = derive_seats_in_preflop_order(_HH_WN_REAL)
    eff = compute_effective_stack_bb(_HH_WN_REAL, level_bb=8000)
    out = build_sizings_overrides(
        _HH_WN_REAL, level_sb=4000, level_bb=8000, seats=seats,
        effective_stack_bb=eff,
    )
    assert out["SIZES_OPEN_OTHERS"] == [2.0, "ALLIN"]
    assert out["SIZES_3BET_SQUEEZE_SB"] == [8.0, "ALLIN"]


def test_build_sizings_overrides_WPN_HJ_open_deep():
    """WPN sample: DAVIDSBAGOFICE@Seat7=HJ opens 1600→3200. BB=1600 → 2 BB.
    Min stack eagle47 34502 / 1600 ≈ 21.56 BB → ≤25 → ALLIN fica."""
    seats = derive_seats_in_preflop_order(_HH_WPN_REAL)
    eff = compute_effective_stack_bb(_HH_WPN_REAL, level_bb=1600)
    out = build_sizings_overrides(
        _HH_WPN_REAL, level_sb=800, level_bb=1600, seats=seats,
        effective_stack_bb=eff,
    )
    assert out["SIZES_OPEN_OTHERS"] == [2.0, "ALLIN"]


def test_build_sizings_overrides_no_raises_returns_empty():
    """Walk-to-BB → dict vazio (template inalterado)."""
    hh = (
        "Hand #X: Test - Level1 (50/100) - 2026/01/01\n"
        "Table 'T' 6-max Seat #1 is the button\n"
        "Seat 1: A (10000 in chips)\n"
        "Seat 2: B (10000 in chips)\n"
        "B: posts small blind 50\n"
        "A: posts big blind 100\n"
        "*** HOLE CARDS ***\n"
        "B: folds\n"
        "*** SUMMARY ***\n"
    )
    seats = derive_seats_in_preflop_order(hh)
    out = build_sizings_overrides(hh, level_sb=50, level_bb=100, seats=seats,
                                  effective_stack_bb=100.0)
    assert out == {}


def test_build_sizings_overrides_drops_ALLIN_when_effective_above_threshold():
    """Eff stack 26 BB > 25 → ALLIN sai dos opens. Mesma HH GG, mas força
    effective via param."""
    seats = derive_seats_in_preflop_order(_HH_GG_REAL)
    out_below = build_sizings_overrides(
        _HH_GG_REAL, level_sb=150, level_bb=300, seats=seats,
        effective_stack_bb=25.0,
    )
    out_above = build_sizings_overrides(
        _HH_GG_REAL, level_sb=150, level_bb=300, seats=seats,
        effective_stack_bb=25.5,
    )
    # No threshold (==25), ALLIN inclui-se.
    assert out_below["SIZES_OPEN_OTHERS"] == [2.0, "ALLIN"]
    # > threshold (25.5), ALLIN sai.
    assert out_above["SIZES_OPEN_OTHERS"] == [2.0]


def test_build_sizings_overrides_classic_3bet_ignores_real_sizing_when_deep():
    """Pós-extensão Maio 2026: classic 3-bet ignora sizing real da HH.
    Para eff >= 35 BB, NÃO há override de classic 3-bet — defaults do
    template ficam (já incluem ALLIN como 2ª entrada).

    Build HH sintética: BU opens, SB 3-bets, eff 100 BB.
    """
    hh = (
        "Hand #X: Test - Level1 (50/100) - 2026/01/01\n"
        "Table 'T' 6-max Seat #5 is the button\n"
        "Seat 1: A (10000 in chips)\n"
        "Seat 2: B (10000 in chips)\n"
        "Seat 3: C (10000 in chips)\n"
        "Seat 4: D (10000 in chips)\n"
        "Seat 5: E (10000 in chips)\n"
        "A: posts small blind 50\n"
        "B: posts big blind 100\n"
        "*** HOLE CARDS ***\n"
        "C: folds\n"
        "D: folds\n"
        "E: raises 200 to 300\n"
        "A: raises 700 to 1000\n"
        "B: folds\n"
        "*** SUMMARY ***\n"
    )
    seats = derive_seats_in_preflop_order(hh)
    out = build_sizings_overrides(hh, level_sb=50, level_bb=100, seats=seats,
                                  effective_stack_bb=100.0)
    # E=BU opens 3 BB, A=SB 3-bets 10 BB vs BU. eff > 25 → SIZES_OPEN_BU sem ALLIN
    assert out["SIZES_OPEN_BU"] == [3.0]
    # Classic 3-bet bucket (SB vs BU = SIZES_3BET_SB_VS_OTHER) NÃO é tocado
    # com eff=100 (>=35). O sizing real (10 BB) é ignorado, defaults intactos.
    assert "SIZES_3BET_SB_VS_OTHER" not in out
    # Nem qualquer outro classic 3-bet bucket.
    for var in ("SIZES_3BET_IP", "SIZES_3BET_BB_VS_SB",
                "SIZES_3BET_BB_VS_OTHER", "SIZES_3BET_SB_VS_BB"):
        assert var not in out


def test_build_sizings_overrides_4bet_with_ratio():
    """4-bet OOP. HH sintética: SB opens, BB 3-bets, SB 4-bets. SB OOP.

    Pot tracking esperado:
      Start: SB=50, BB=100 (pot 150, call=100)
      SB raises to 250 → SB=250, pot=300, call=250
      BB raises to 700 → pot before BB action = 300, pot after BB hipotético
        call = 300+(250-100)=450; BB raise inc = 700-250 = 450; fraction =
        450/450 = 1.0 — mas SB's contribution already at 250 fica.
      Actually let me think more carefully:
        Pot before BB 3-bet action: 50+250 = 300.
        BB needs to call: 250 - 100 = 150 to match. After call: pot=450.
        BB raise inc: 700 - 250 = 450. Fraction: 450/450 = 1.0.
      SB 4-bets to ALLIN-shove? Let's do SB raises to 1300:
        Pot before SB action: 250+700 = 950.
        SB needs to call: 700-250 = 450 to match. After call: pot=1400.
        SB raise inc: 1300-700 = 600. Fraction: 600/1400 = 0.43.
    """
    hh = (
        "Hand #X: Test - Level1 (50/100) - 2026/01/01\n"
        "Table 'T' 6-max Seat #5 is the button\n"
        "Seat 1: A (10000 in chips)\n"
        "Seat 2: B (10000 in chips)\n"
        "Seat 3: C (10000 in chips)\n"
        "Seat 4: D (10000 in chips)\n"
        "Seat 5: E (10000 in chips)\n"
        "A: posts small blind 50\n"
        "B: posts big blind 100\n"
        "*** HOLE CARDS ***\n"
        "C: folds\n"
        "D: folds\n"
        "E: folds\n"
        "A: raises 200 to 250\n"
        "B: raises 450 to 700\n"
        "A: raises 600 to 1300\n"
        "*** SUMMARY ***\n"
    )
    seats = derive_seats_in_preflop_order(hh)
    out = build_sizings_overrides(hh, level_sb=50, level_bb=100, seats=seats,
                                  effective_stack_bb=100.0)
    # SB opens BU=? No — em 5-handed, btn=Seat5, seat_list=[1,2,3,4,5],
    # btn_idx=4, first_to_act_offset=3 → hrc0=Seat[(4+3+0)%5=2]=Seat3(C, UTG),
    # hrc1=Seat4(D, HJ), hrc2=Seat5(E, BU), hrc3=Seat1(A, SB), hrc4=Seat2(B, BB)
    # Open by SB (A) → SIZES_OPEN_SB.
    assert out["SIZES_OPEN_SB"] == [2.5]  # 250/100 = 2.5
    # eff=100 >= 35 → classic 3-bet bucket SIZES_3BET_BB_VS_SB NÃO é tocado
    # (default do template `[10, ALLIN]` fica). O sizing real do 3-bet é
    # ignorado pela regra do multiplicador.
    assert "SIZES_3BET_BB_VS_SB" not in out
    # 4-bet by SB (A) vs BB 3-better. Postflop rank: SB=0, BB=1 → 4-better OOP.
    assert out["SIZES_POT_4BET_OOP"] == [0.43, "ALLIN"]


# ── Classic 3-bet multiplier rule (Maio 2026, extensão pós-9b6e839) ─────
# Os 5 buckets de 3-bet clássico ignoram o sizing real da HH. Em vez disso,
# aplica-se um multiplicador ao default do template em função da stack
# efectiva. Squeezes mantêm sizing real. Convenção dos limiares:
# lower-inclusive, upper-exclusive (`eff >= threshold`).

def test_classic_3bet_band_above_35_returns_none_mult():
    """eff >= 35 → defaults intactos, sem override."""
    assert _classic_3bet_band(35) == (None, False)
    assert _classic_3bet_band(40) == (None, False)
    assert _classic_3bet_band(100.0) == (None, False)


def test_classic_3bet_band_30_band_x0_90():
    """[30, 35) → ×0.90."""
    assert _classic_3bet_band(30) == (0.90, False)
    assert _classic_3bet_band(32.5) == (0.90, False)
    assert _classic_3bet_band(34.99) == (0.90, False)


def test_classic_3bet_band_25_band_x0_80():
    """[25, 30) → ×0.80. 25 cai aqui (boundary inferior inclusivo)."""
    assert _classic_3bet_band(25) == (0.80, False)
    assert _classic_3bet_band(27) == (0.80, False)
    assert _classic_3bet_band(29.99) == (0.80, False)


def test_classic_3bet_band_18_band_x0_70():
    """[18, 25) → ×0.70. 18 cai aqui (boundary inferior inclusivo)."""
    assert _classic_3bet_band(18) == (0.70, False)
    assert _classic_3bet_band(22.5) == (0.70, False)
    assert _classic_3bet_band(24.99) == (0.70, False)


def test_classic_3bet_band_below_18_shove_only():
    """eff < 18 → ['ALLIN'] só (jam-or-fold)."""
    assert _classic_3bet_band(17.99) == (None, True)
    assert _classic_3bet_band(15) == (None, True)
    assert _classic_3bet_band(5) == (None, True)


def test_classic_3bet_band_none_returns_none_mult():
    """eff=None → defensivo, sem override."""
    assert _classic_3bet_band(None) == (None, False)


def test_compute_classic_3bet_overrides_x0_90_all_5_buckets():
    """eff=30 → ×0.90 a todos os 5 buckets. 10×0.9=9.0, 6×0.9=5.4, 8×0.9=7.2, 11×0.9=9.9."""
    out = _compute_classic_3bet_overrides(30)
    assert out == {
        "SIZES_3BET_IP": [5.4, "ALLIN"],
        "SIZES_3BET_BB_VS_SB": [9.0, "ALLIN"],
        "SIZES_3BET_BB_VS_OTHER": [7.2, "ALLIN"],
        "SIZES_3BET_SB_VS_BB": [9.9, "ALLIN"],
        "SIZES_3BET_SB_VS_OTHER": [7.2, "ALLIN"],
    }


def test_compute_classic_3bet_overrides_x0_80_boundary_25():
    """eff=25 → ×0.80 (boundary inferior inclusivo)."""
    out = _compute_classic_3bet_overrides(25)
    assert out == {
        "SIZES_3BET_IP": [4.8, "ALLIN"],
        "SIZES_3BET_BB_VS_SB": [8.0, "ALLIN"],
        "SIZES_3BET_BB_VS_OTHER": [6.4, "ALLIN"],
        "SIZES_3BET_SB_VS_BB": [8.8, "ALLIN"],
        "SIZES_3BET_SB_VS_OTHER": [6.4, "ALLIN"],
    }


def test_compute_classic_3bet_overrides_x0_70_boundary_18():
    """eff=18 → ×0.70 (boundary inferior inclusivo)."""
    out = _compute_classic_3bet_overrides(18)
    assert out == {
        "SIZES_3BET_IP": [4.2, "ALLIN"],
        "SIZES_3BET_BB_VS_SB": [7.0, "ALLIN"],
        "SIZES_3BET_BB_VS_OTHER": [5.6, "ALLIN"],
        "SIZES_3BET_SB_VS_BB": [7.7, "ALLIN"],
        "SIZES_3BET_SB_VS_OTHER": [5.6, "ALLIN"],
    }


def test_compute_classic_3bet_overrides_shove_only_below_18():
    """eff=15 (<18) → array ['ALLIN'] só nos 5 buckets."""
    out = _compute_classic_3bet_overrides(15)
    expected_keys = set(_CLASSIC_3BET_DEFAULTS)
    assert set(out.keys()) == expected_keys
    for var in expected_keys:
        assert out[var] == ["ALLIN"]


def test_compute_classic_3bet_overrides_above_35_empty():
    """eff >= 35 → {} (defaults intactos)."""
    assert _compute_classic_3bet_overrides(35) == {}
    assert _compute_classic_3bet_overrides(40) == {}
    assert _compute_classic_3bet_overrides(None) == {}


# ── build_sizings_overrides com classic 3-bet multiplier ────────────────

def _synthetic_hh(eff_bb_target: float, with_3bet: bool = True,
                  with_squeeze: bool = False) -> tuple:
    """Constrói HH sintética com stacks tunados para a efectiva desejada.
    BB=100, SB=50. Player A=SB, B=BB, C/D=UTG/HJ, E=BU em 5-handed.
    """
    chips_per_player = int(eff_bb_target * 100)
    raises_block = "C: folds\n"
    if with_squeeze:
        # UTG opens 2.5bb, HJ flats, BU 3-bet squeeze (8bb).
        raises_block += (
            "D: raises 200 to 250\n"
            "E: calls 250\n"
            "A: folds\n"
            "B: raises 550 to 800\n"
        )
    elif with_3bet:
        # BU opens 3bb, SB 3-bets 10bb (classic, no callers).
        raises_block += (
            "D: folds\n"
            "E: raises 200 to 300\n"
            "A: raises 700 to 1000\n"
            "B: folds\n"
        )
    else:
        raises_block += "D: folds\nE: folds\nA: folds\n"
    hh = (
        "Hand #X: Test - Level1 (50/100) - 2026/01/01\n"
        "Table 'T' 6-max Seat #5 is the button\n"
        f"Seat 1: A ({chips_per_player} in chips)\n"
        f"Seat 2: B ({chips_per_player} in chips)\n"
        f"Seat 3: C ({chips_per_player} in chips)\n"
        f"Seat 4: D ({chips_per_player} in chips)\n"
        f"Seat 5: E ({chips_per_player} in chips)\n"
        "A: posts small blind 50\n"
        "B: posts big blind 100\n"
        "*** HOLE CARDS ***\n"
        + raises_block +
        "*** SUMMARY ***\n"
    )
    seats = derive_seats_in_preflop_order(hh)
    return hh, seats


def test_build_overrides_applies_multiplier_for_classic_3bet_at_27bb():
    """eff=27 BB → ×0.80 nos 5 buckets, mesmo com 3-bet real na HH (10bb)."""
    hh, seats = _synthetic_hh(27.0, with_3bet=True)
    out = build_sizings_overrides(hh, level_sb=50, level_bb=100, seats=seats,
                                  effective_stack_bb=27.0)
    # Sizing real do 3-bet (10 BB) é IGNORADO. Multiplier ×0.80 nos defaults:
    assert out["SIZES_3BET_IP"] == [4.8, "ALLIN"]
    assert out["SIZES_3BET_BB_VS_SB"] == [8.0, "ALLIN"]
    assert out["SIZES_3BET_BB_VS_OTHER"] == [6.4, "ALLIN"]
    assert out["SIZES_3BET_SB_VS_BB"] == [8.8, "ALLIN"]
    assert out["SIZES_3BET_SB_VS_OTHER"] == [6.4, "ALLIN"]


def test_build_overrides_applies_multiplier_without_3bet_in_hh():
    """eff=22 BB + HH só com fold/open → multiplier ainda se aplica aos 5 buckets."""
    hh, seats = _synthetic_hh(22.0, with_3bet=False)
    out = build_sizings_overrides(hh, level_sb=50, level_bb=100, seats=seats,
                                  effective_stack_bb=22.0)
    # ×0.70 nos defaults independentemente da HH ter 3-bet ou não.
    assert out["SIZES_3BET_IP"] == [4.2, "ALLIN"]
    assert out["SIZES_3BET_BB_VS_SB"] == [7.0, "ALLIN"]
    assert out["SIZES_3BET_BB_VS_OTHER"] == [5.6, "ALLIN"]
    assert out["SIZES_3BET_SB_VS_BB"] == [7.7, "ALLIN"]
    assert out["SIZES_3BET_SB_VS_OTHER"] == [5.6, "ALLIN"]


def test_build_overrides_squeeze_keeps_real_sizing_when_classic_3bet_rule_applies():
    """eff=22 + squeeze na HH → SIZES_3BET_SQUEEZE_* mantém sizing real;
    classic 3-bet buckets recebem ×0.70."""
    hh, seats = _synthetic_hh(22.0, with_3bet=False, with_squeeze=True)
    out = build_sizings_overrides(hh, level_sb=50, level_bb=100, seats=seats,
                                  effective_stack_bb=22.0)
    # Squeeze sizing real (8 BB) — sem multiplicador. O squeezer no _synthetic_hh
    # é B (BB, hrc_idx 4 em 5-handed: SB=3, BB=4, UTG=0, HJ=1, BU=2).
    # Squeeze por BB → SIZES_3BET_SQUEEZE_BB.
    assert out["SIZES_3BET_SQUEEZE_BB"] == [8.0, "ALLIN"]
    # Classic 3-bet buckets ainda recebem ×0.70.
    assert out["SIZES_3BET_IP"] == [4.2, "ALLIN"]
    assert out["SIZES_3BET_BB_VS_SB"] == [7.0, "ALLIN"]


def test_build_overrides_shove_only_below_18bb_in_classic_3bet():
    """eff=12 BB (<18) → classic 3-bet buckets = ['ALLIN'] só."""
    hh, seats = _synthetic_hh(12.0, with_3bet=True)
    out = build_sizings_overrides(hh, level_sb=50, level_bb=100, seats=seats,
                                  effective_stack_bb=12.0)
    for var in _CLASSIC_3BET_DEFAULTS:
        assert out[var] == ["ALLIN"]


def test_build_overrides_no_classic_3bet_override_above_35bb():
    """eff=40 BB → nenhum classic 3-bet bucket nos overrides (defaults intactos)."""
    hh, seats = _synthetic_hh(40.0, with_3bet=True)
    out = build_sizings_overrides(hh, level_sb=50, level_bb=100, seats=seats,
                                  effective_stack_bb=40.0)
    for var in _CLASSIC_3BET_DEFAULTS:
        assert var not in out


# ── generate_hrc_script_for_hand — pipeline completo ──────────────────────

def test_generate_hrc_script_for_hand_GG_HJ_open():
    """Pipeline completo GG sample. Eff ~133 BB → opens sem ALLIN."""
    seats = derive_seats_in_preflop_order(_HH_GG_REAL)
    js, overrides, eff, err = generate_hrc_script_for_hand(
        _HH_GG_REAL, level_sb=150, level_bb=300, seats=seats,
    )
    assert err is None
    assert eff == 133.33
    assert overrides["SIZES_OPEN_OTHERS"] == [2.0]
    assert "let SIZES_OPEN_OTHERS = [2];" in js
    # Outras vars não tocadas
    assert "let SIZES_OPEN_BU = [2, ALLIN];" in js


def test_generate_hrc_script_for_hand_walk_to_BB_returns_template_intact():
    """Sem raises → template devolvido cru, overrides={}."""
    hh = (
        "Hand #X: Test - Level1 (50/100) - 2026/01/01\n"
        "Table 'T' 6-max Seat #1 is the button\n"
        "Seat 1: A (10000 in chips)\n"
        "Seat 2: B (10000 in chips)\n"
        "B: posts small blind 50\n"
        "A: posts big blind 100\n"
        "*** HOLE CARDS ***\n"
        "B: folds\n"
        "*** SUMMARY ***\n"
    )
    seats = derive_seats_in_preflop_order(hh)
    js, overrides, eff, err = generate_hrc_script_for_hand(
        hh, level_sb=50, level_bb=100, seats=seats,
    )
    assert err is None
    assert overrides == {}
    # Template tem o default original em SIZES_OPEN_OTHERS
    assert "let SIZES_OPEN_OTHERS = [2, ALLIN];" in js


def test_generate_hrc_script_for_hand_template_io_failure_returns_error():
    """Path inexistente → js=None, error populated."""
    seats = derive_seats_in_preflop_order(_HH_GG_REAL)
    js, overrides, eff, err = generate_hrc_script_for_hand(
        _HH_GG_REAL, level_sb=150, level_bb=300, seats=seats,
        template_path="/nonexistent/template.js",
    )
    assert js is None
    assert err is not None
    assert "FileNotFoundError" in err


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
    # script_path apontará para script.js (gerado sempre em Maio 2026+)
    assert payouts["script_path"] == "script.js"
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
    # script.js gerado sempre (Maio 2026+) — script_path relativo "script.js"
    assert payouts["script_path"] == "script.js"


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


# ── Integration: script.js per-hand no zip (gerador novo Maio 2026) ────────

# HH UTG-open com 8 seats, 6 voluntários (UTG raise + 5 calls), hero=BB.
# Eff ~25 BB (stacks 10000 / BB 400). Cobre opens com ALLIN.
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


def test_build_queue_zip_writes_script_js_for_hand_with_open():
    """Mão com pelo menos 1 raise preflop → script.js escrito + payouts.json
    script_path='script.js'. Manifest tem `has_script=True` e
    `script_overrides` populated."""
    hand = {
        "id": 1, "hand_id": "GG-OPEN", "site": "GGPoker",
        "tournament_number": "111",
        "raw": _HH_UTG_OPEN_8MAX,
        "player_names": {},
    }
    blob = build_queue_zip([hand], {("GGPoker", "111"): _fake_payout_blob()})
    zf = _zipfile.ZipFile(_io.BytesIO(blob))
    names = set(zf.namelist())
    assert "GG-OPEN/script.js" in names

    payouts = _json.loads(zf.read("GG-OPEN/payouts.json"))
    assert payouts["script_path"] == "script.js"

    js = zf.read("GG-OPEN/script.js").decode("utf-8")
    # UTGopener é UTG (idx 0 em 8-handed) → SIZES_OPEN_OTHERS substituído.
    # Open size = 1200/400 = 3 BB. Eff stack = 10000/400 = 25 → ALLIN fica.
    assert "let SIZES_OPEN_OTHERS = [3, ALLIN];" in js
    # Outras vars intactas
    assert "let SIZES_OPEN_BU = [2, ALLIN];" in js

    manifest = _json.loads(zf.read("manifest.json"))
    entry = manifest["hands_included"][0]
    assert entry["has_script"] is True
    assert entry["script_overrides"]["SIZES_OPEN_OTHERS"] == [3.0, "ALLIN"]
    assert entry["effective_stack_bb"] == 25.0
    assert entry["aggressor_position"] == 0  # UTG=0 em 8-handed (HRC docs conv)
    assert entry["script_generation_error"] is None


def test_build_queue_zip_writes_script_js_for_walk_to_BB():
    """Mão sem raises (walk-to-BB) → script.js ainda é escrito com template
    intacto. Decisão: consistência > optimização. Overrides vazio."""
    hh = (
        "Hand #X: Test - Level1 (50/100) - 2026/01/01\n"
        "Table 'T' 6-max Seat #1 is the button\n"
        "Seat 1: A (10000 in chips)\n"
        "Seat 2: B (10000 in chips)\n"
        "B: posts small blind 50\n"
        "A: posts big blind 100\n"
        "*** HOLE CARDS ***\n"
        "B: folds\n"
        "*** SUMMARY ***\n"
    )
    hand = {
        "id": 1, "hand_id": "GG-WALK", "site": "GGPoker",
        "tournament_number": "111",
        "raw": hh,
        "player_names": {},
    }
    blob = build_queue_zip([hand], {("GGPoker", "111"): _fake_payout_blob()})
    zf = _zipfile.ZipFile(_io.BytesIO(blob))
    names = set(zf.namelist())
    assert "GG-WALK/script.js" in names

    js = zf.read("GG-WALK/script.js").decode("utf-8")
    # Template intacto — defaults canónicos.
    assert "let SIZES_OPEN_OTHERS = [2, ALLIN];" in js

    manifest = _json.loads(zf.read("manifest.json"))
    entry = manifest["hands_included"][0]
    assert entry["has_script"] is True
    assert entry["script_overrides"] == {}
    assert entry["aggressor_position"] is None


def test_build_queue_zip_script_generation_error_on_template_io_failure(monkeypatch):
    """Força OSError no read do template → manifest captura `script_generation_error`
    e `has_script=False`."""
    from app.services import hrc_script_gen as gen
    monkeypatch.setattr(
        gen, "_HRC_TEMPLATE_PATH", "/nonexistent/path/to/template.js",
    )

    hand = {
        "id": 1, "hand_id": "GG-FAIL", "site": "GGPoker",
        "tournament_number": "111",
        "raw": _HH_UTG_OPEN_8MAX,
        "player_names": {},
    }
    blob = build_queue_zip([hand], {("GGPoker", "111"): _fake_payout_blob()})
    zf = _zipfile.ZipFile(_io.BytesIO(blob))
    names = set(zf.namelist())
    assert "GG-FAIL/script.js" not in names

    manifest = _json.loads(zf.read("manifest.json"))
    entry = manifest["hands_included"][0]
    assert entry["has_script"] is False
    assert entry["script_generation_error"] is not None
    assert "FileNotFoundError" in entry["script_generation_error"]


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


# ── pt25e #META-AGGRESSOR-REAL-ACTION ───────────────────────────────────────

from app.services.queue_export import (
    derive_aggressor_real_action,
    _extract_blinds_from_header,
)


# Cross-site real samples — reaproveita _HH_*_REAL definidos acima.

def test_aggressor_real_action_PS_sample():
    """PS-260299428000: Level XXVI (12500/25000), Votsarrr raises 605201 to
    630201 and is all-in → size_bb = 630201/25000 ≈ 25.21.

    pt25e #META-AGGRESSOR-POSITION: 6-max BU=Seat 5, 5 sentados; Votsarrr
    (Seat 5) = BU no preflop order de 5-handed (hrc_idx=2)."""
    blinds = _extract_blinds_from_header(_HH_PS_REAL)
    assert blinds == (12500, 25000)
    out = derive_aggressor_real_action(_HH_PS_REAL, 12500, 25000)
    assert out is not None
    assert out["type"] == "raise"
    assert out["size_bb"] == round(630201 / 25000, 2)
    assert out["position"] == "BU"


def test_aggressor_real_action_GG_sample():
    """GG-5939385803: Level3(150/300(45)), 221ebf0d raises 300 to 600 →
    size_bb = 600/300 = 2.0 (canónico UTG open 2bb).

    pt25e #META-AGGRESSOR-POSITION: 8-max BU=Seat 1, 5 sentados (Seats
    2/3/4 missing); 221ebf0d (Seat 8) = HJ em 5-handed (hrc_idx=1)."""
    blinds = _extract_blinds_from_header(_HH_GG_REAL)
    assert blinds == (150, 300)
    out = derive_aggressor_real_action(_HH_GG_REAL, 150, 300)
    assert out == {"type": "raise", "size_bb": 2.0, "position": "HJ"}


def test_aggressor_real_action_WN_sample_INTERSTELLAR():
    """Winamax INTERSTELLAR: Holdem no limit (1000/4000/8000) — ante/sb/bb;
    blueballs67 raises 8000 to 16000 → size_bb = 16000/8000 = 2.0.

    pt25e #META-AGGRESSOR-POSITION: 6-max BU=Seat 2, 5 sentados; blueballs67
    (Seat 5) = UTG em 5-handed (hrc_idx=0)."""
    blinds = _extract_blinds_from_header(_HH_WN_REAL)
    assert blinds == (4000, 8000)
    out = derive_aggressor_real_action(_HH_WN_REAL, 4000, 8000)
    assert out == {"type": "raise", "size_bb": 2.0, "position": "UTG"}


def test_aggressor_real_action_WPN_sample():
    """WPN: Level 4 (800.00/1600.00); DAVIDSBAGOFICE raises 1600.00 to 3200.00
    → size_bb = 3200/1600 = 2.0 (decimais WPN tolerados).

    pt25e #META-AGGRESSOR-POSITION: 8-max BU=Seat 1, 8 sentados full;
    DAVIDSBAGOFICE (Seat 7) = HJ em 8-handed (hrc_idx=3)."""
    blinds = _extract_blinds_from_header(_HH_WPN_REAL)
    assert blinds == (800, 1600)
    out = derive_aggressor_real_action(_HH_WPN_REAL, 800, 1600)
    assert out == {"type": "raise", "size_bb": 2.0, "position": "HJ"}


# Sintéticos cobrindo cenários canónicos do plano.

def test_aggressor_real_action_UTG_raise_2bb():
    """8-max UTG raise to 800 com BB=400 → 2.0bb (open canónico) + UTG."""
    hh = _hh_8max_btn4(["UTGplayer: raises 400 to 800"])
    out = derive_aggressor_real_action(hh, 200, 400)
    assert out == {"type": "raise", "size_bb": 2.0, "position": "UTG"}


def test_aggressor_real_action_raise_2_5bb():
    """UTG raise to 1000 com BB=400 → 2.5bb open."""
    hh = _hh_8max_btn4(["UTGplayer: raises 600 to 1000"])
    out = derive_aggressor_real_action(hh, 200, 400)
    assert out == {"type": "raise", "size_bb": 2.5, "position": "UTG"}


def test_aggressor_real_action_raise_3bb():
    """UTG raise to 1200 com BB=400 → 3.0bb open."""
    hh = _hh_8max_btn4(["UTGplayer: raises 800 to 1200"])
    out = derive_aggressor_real_action(hh, 200, 400)
    assert out == {"type": "raise", "size_bb": 3.0, "position": "UTG"}


def test_aggressor_real_action_all_in_shove():
    """UTG raise to 10000 and is all-in com BB=400 → 25bb shove."""
    hh = _hh_8max_btn4(["UTGplayer: raises 9600 to 10000 and is all-in"])
    out = derive_aggressor_real_action(hh, 200, 400)
    assert out == {"type": "raise", "size_bb": 25.0, "position": "UTG"}


def test_aggressor_real_action_limp_completion_returns_None():
    """Limp pot: todos foldam até SB, SB completa, BB checks — sem raise/bet
    → None (consistente com derive_real_aggressor_position)."""
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
    out = derive_aggressor_real_action(hh, 200, 400)
    assert out is None


# pt25e #META-AGGRESSOR-POSITION: sintéticos por N de jogadores sentados,
# cobrindo as labels de `_POSITION_LABELS_BY_N` em casos canónicos. N=8 já
# coberto pelo bloco _hh_8max_btn4 acima (UTG, HJ, ..., BU/SB labels).

def _hh_5max_btn1(preflop_actions: list[str]) -> str:
    """5-handed minimal HH: BU=Seat 1; pt25d preflop order:
    UTG=Seat 4, HJ=Seat 5, BU=Seat 1, SB=Seat 2, BB=Seat 3."""
    lines = [
        "Poker Hand #TM5: Tournament #100, Test - Level5 (200/400) - 2026/05/01 00:00:00",
        "Table '5max' 6-max Seat #1 is the button",
        "Seat 1: BUplayer (10000 in chips)",
        "Seat 2: SBplayer (10000 in chips)",
        "Seat 3: BBplayer (10000 in chips)",
        "Seat 4: UTGplayer (10000 in chips)",
        "Seat 5: HJplayer (10000 in chips)",
        "SBplayer: posts small blind 200",
        "BBplayer: posts big blind 400",
        "*** HOLE CARDS ***",
        "Dealt to Hero [As Kd]",
    ]
    lines.extend(preflop_actions)
    lines.append("*** SUMMARY ***")
    return "\n".join(lines) + "\n"


def _hh_4max_btn1(preflop_actions: list[str]) -> str:
    """4-handed minimal HH: BU=Seat 1; pt25d preflop order:
    UTG=Seat 3, BU=Seat 1, SB=Seat 2; wait — n=4, first_offset=3,
    btn_idx=0, n=4 → hrc0=seat_list[3]=Seat 4, hrc1=Seat 1, hrc2=Seat 2, hrc3=Seat 3.
    Labels: UTG, BU, SB, BB → UTGplayer@Seat 4, BU@Seat 1, SB@Seat 2, BB@Seat 3."""
    lines = [
        "Poker Hand #TM4: Tournament #100, Test - Level5 (200/400) - 2026/05/01 00:00:00",
        "Table '4max' 6-max Seat #1 is the button",
        "Seat 1: BUplayer (10000 in chips)",
        "Seat 2: SBplayer (10000 in chips)",
        "Seat 3: BBplayer (10000 in chips)",
        "Seat 4: UTGplayer (10000 in chips)",
        "SBplayer: posts small blind 200",
        "BBplayer: posts big blind 400",
        "*** HOLE CARDS ***",
        "Dealt to Hero [As Kd]",
    ]
    lines.extend(preflop_actions)
    lines.append("*** SUMMARY ***")
    return "\n".join(lines) + "\n"


def _hh_hu(preflop_actions: list[str]) -> str:
    """HU 2-handed minimal: BU=Seat 1 (BU/SB age primeiro preflop)."""
    lines = [
        "Poker Hand #TMHU: Tournament #100, Test - Level5 (200/400) - 2026/05/01 00:00:00",
        "Table 'HU' 2-max Seat #1 is the button",
        "Seat 1: SBplayer (10000 in chips)",
        "Seat 2: BBplayer (10000 in chips)",
        "SBplayer: posts small blind 200",
        "BBplayer: posts big blind 400",
        "*** HOLE CARDS ***",
        "Dealt to Hero [As Kd]",
    ]
    lines.extend(preflop_actions)
    lines.append("*** SUMMARY ***")
    return "\n".join(lines) + "\n"


def test_aggressor_real_action_5handed_UTG_open():
    """5-handed UTG open → position UTG (hrc_idx 0; labels UTG/HJ/BU/SB/BB)."""
    hh = _hh_5max_btn1(["UTGplayer: raises 400 to 800"])
    out = derive_aggressor_real_action(hh, 200, 400)
    assert out == {"type": "raise", "size_bb": 2.0, "position": "UTG"}


def test_aggressor_real_action_5handed_HJ_open():
    """5-handed UTG folds, HJ raises → position HJ (hrc_idx 1)."""
    hh = _hh_5max_btn1([
        "UTGplayer: folds",
        "HJplayer: raises 400 to 800",
    ])
    out = derive_aggressor_real_action(hh, 200, 400)
    assert out == {"type": "raise", "size_bb": 2.0, "position": "HJ"}


def test_aggressor_real_action_5handed_BU_open():
    """5-handed UTG+HJ fold, BU raises → position BU (hrc_idx 2)."""
    hh = _hh_5max_btn1([
        "UTGplayer: folds",
        "HJplayer: folds",
        "BUplayer: raises 600 to 1000",
    ])
    out = derive_aggressor_real_action(hh, 200, 400)
    assert out == {"type": "raise", "size_bb": 2.5, "position": "BU"}


def test_aggressor_real_action_5handed_SB_open():
    """5-handed todos foldam até SB, SB raises → position SB (hrc_idx N-2=3)."""
    hh = _hh_5max_btn1([
        "UTGplayer: folds",
        "HJplayer: folds",
        "BUplayer: folds",
        "SBplayer: raises 600 to 1000",
    ])
    out = derive_aggressor_real_action(hh, 200, 400)
    assert out == {"type": "raise", "size_bb": 2.5, "position": "SB"}


def test_aggressor_real_action_4handed_UTG_open():
    """4-handed UTG raises → position UTG (hrc_idx 0; labels UTG/BU/SB/BB).
    Pt25d convention: first_offset=3, btn_idx=0, n=4 → UTG=seat_list[3]=Seat 4."""
    hh = _hh_4max_btn1(["UTGplayer: raises 400 to 800"])
    out = derive_aggressor_real_action(hh, 200, 400)
    assert out == {"type": "raise", "size_bb": 2.0, "position": "UTG"}


def test_aggressor_real_action_4handed_BU_open():
    """4-handed UTG folds, BU raises → position BU (hrc_idx 1)."""
    hh = _hh_4max_btn1([
        "UTGplayer: folds",
        "BUplayer: raises 400 to 800",
    ])
    out = derive_aggressor_real_action(hh, 200, 400)
    assert out == {"type": "raise", "size_bb": 2.0, "position": "BU"}


def test_aggressor_real_action_4handed_SB_open():
    """4-handed UTG/BU fold, SB raises → position SB (hrc_idx N-2=2)."""
    hh = _hh_4max_btn1([
        "UTGplayer: folds",
        "BUplayer: folds",
        "SBplayer: raises 600 to 1000",
    ])
    out = derive_aggressor_real_action(hh, 200, 400)
    assert out == {"type": "raise", "size_bb": 2.5, "position": "SB"}


def test_aggressor_real_action_HU_BB_3bet_after_SB_call():
    """HU SB completa (call), BB raises → position BB (hrc_idx N-1=1).
    Confirma que para HU o aggressor pode ser BB quando SB começa por
    completar."""
    hh = _hh_hu([
        "SBplayer: calls 200",
        "BBplayer: raises 800 to 1200",
    ])
    out = derive_aggressor_real_action(hh, 200, 400)
    assert out == {"type": "raise", "size_bb": 3.0, "position": "BB"}


def test_aggressor_real_action_HU_SB_raise_synthetic():
    """HU SB raise (BU/SB age primeiro). Cobre o caso degenerate onde o
    label canónico é 'BU/SB' (não 'SB' nem 'BU')."""
    hh = _hh_hu(["SBplayer: raises 600 to 800"])
    out = derive_aggressor_real_action(hh, 200, 400)
    assert out == {"type": "raise", "size_bb": 2.0, "position": "BU/SB"}


def test_aggressor_real_action_HU_SB_raise():
    """HU 2-handed: SB age primeiro preflop. SB raise to 800 com BB=400
    → 2.0bb open. Position = "BU/SB" (label canónico HU em
    `_POSITION_LABELS_BY_N[2]`)."""
    hu_hh = (
        "Poker Hand #TM2: Tournament #100, Test - Level5 (200/400) - 2026/05/01 00:00:00\n"
        "Table 'HU' 2-max Seat #1 is the button\n"
        "Seat 1: SBplayer (10000 in chips)\n"
        "Seat 2: BBplayer (10000 in chips)\n"
        "SBplayer: posts small blind 200\n"
        "BBplayer: posts big blind 400\n"
        "*** HOLE CARDS ***\n"
        "Dealt to Hero [As Kd]\n"
        "SBplayer: raises 600 to 800\n"
        "*** SUMMARY ***\n"
    )
    out = derive_aggressor_real_action(hu_hh, 200, 400)
    assert out == {"type": "raise", "size_bb": 2.0, "position": "BU/SB"}


def test_aggressor_real_action_no_preflop_marker_returns_None():
    """HH sem marker preflop (`*** HOLE CARDS ***` ou `*** PRE-FLOP ***`) →
    None (graceful, mão truncada / cancelled)."""
    truncated = "Some header\nSeat 1: X (100 in chips)\n(no hole cards section)\n"
    out = derive_aggressor_real_action(truncated, 200, 400)
    assert out is None


def test_aggressor_real_action_invalid_bb_returns_None():
    """level_bb 0 ou None → None (defensivo, evita ZeroDivisionError)."""
    hh = _hh_8max_btn4(["UTGplayer: raises 400 to 800"])
    assert derive_aggressor_real_action(hh, 200, 0) is None
    assert derive_aggressor_real_action(hh, 200, None) is None  # type: ignore[arg-type]


def test_aggressor_real_action_empty_hh_returns_None():
    """Defensivo: hh_text vazio/None → None."""
    assert derive_aggressor_real_action("", 200, 400) is None
    assert derive_aggressor_real_action(None, 200, 400) is None  # type: ignore[arg-type]


def test_extract_blinds_unknown_header_returns_None():
    """Header sem padrão reconhecível → None (caller cai em aggressor=None)."""
    assert _extract_blinds_from_header("just a plain text line") is None
    assert _extract_blinds_from_header("") is None
    assert _extract_blinds_from_header(None) is None  # type: ignore[arg-type]


# Integração build_queue_zip: aggressor_real_action no manifest + payouts.json.

def test_build_queue_zip_injects_aggressor_real_action_in_manifest_and_payouts():
    """pt25e: hand com raise preflop → manifest entry + payouts.json têm
    `aggressor_real_action={type, size_bb, position}`. _HH_UTG_OPEN_8MAX usa
    Level5 (200/400) e UTGopener (Seat 7, BU=Seat 4 → UTG em 8-handed)
    raises 800 to 1200 → 3.0bb + position UTG."""
    hand = {
        "id": 1, "hand_id": "GG-AGG", "site": "GGPoker",
        "tournament_number": "111",
        "raw": _HH_UTG_OPEN_8MAX,
        "player_names": {},
        "players_left": 200,
    }
    blob = build_queue_zip([hand], {("GGPoker", "111"): _fake_payout_blob()})
    zf = _zipfile.ZipFile(_io.BytesIO(blob))
    manifest = _json.loads(zf.read("manifest.json"))
    entry = manifest["hands_included"][0]
    expected = {"type": "raise", "size_bb": 3.0, "position": "UTG"}
    assert entry["aggressor_real_action"] == expected
    payouts = _json.loads(zf.read("GG-AGG/payouts.json"))
    assert payouts["aggressor_real_action"] == expected


def test_build_queue_zip_aggressor_real_action_None_for_limp_pot():
    """pt25e: hand sem raise/bet preflop (limp pot) → entry e payouts.json
    com `aggressor_real_action=None` (campo presente, valor null)."""
    limp_hh = """Poker Hand #TM3: Tournament #100, Test - Level5 (200/400) - 2026/05/01 00:00:00
Table 'X' 8-max Seat #4 is the button
Seat 1: P1 (10000 in chips)
Seat 4: Hero (10000 in chips)
Seat 5: SBplayer (10000 in chips)
Seat 6: BBplayer (10000 in chips)
SBplayer: posts small blind 200
BBplayer: posts big blind 400
*** HOLE CARDS ***
Dealt to Hero [As Kd]
P1: folds
Hero: folds
SBplayer: calls 200
BBplayer: checks
*** SUMMARY ***
"""
    hand = {
        "id": 1, "hand_id": "GG-LIMP", "site": "GGPoker",
        "tournament_number": "111",
        "raw": limp_hh,
        "player_names": {},
        "players_left": 200,
    }
    blob = build_queue_zip([hand], {("GGPoker", "111"): _fake_payout_blob()})
    zf = _zipfile.ZipFile(_io.BytesIO(blob))
    manifest = _json.loads(zf.read("manifest.json"))
    entry = manifest["hands_included"][0]
    assert entry["aggressor_real_action"] is None
    payouts = _json.loads(zf.read("GG-LIMP/payouts.json"))
    assert payouts["aggressor_real_action"] is None
