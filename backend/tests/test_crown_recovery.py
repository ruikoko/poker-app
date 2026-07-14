"""Detetor de bounties recuperáveis (#CROWN-RECOVERY) — classify_hand puro.
Cobre a armadilha-raiz: linhas do SUMMARY "Seat N: hash (small blind) ... and lost"
NÃO podem ser comidas pelo _SEAT_RE (senão o eliminado com posição rotulada nunca
entra em `lost`)."""
from app.services import crown_recovery as cr

# HH sintética 6-max: button=Seat1; bbbb (SB) all-in + lost = bustou.
_RAW = """Poker Hand #TM1: Tournament #999, Test KO Hold'em No Limit - Level1
Table '1' 6-max Seat #1 is the button
Seat 1: aaaa (1000 in chips)
Seat 2: bbbb (1000 in chips)
Seat 3: cccc (1000 in chips)
Seat 4: dddd (1000 in chips)
Seat 5: eeee (1000 in chips)
Seat 6: Hero (1000 in chips)
bbbb: raises 900 to 1000 and is all-in
Hero: calls 1000 and is all-in
*** SUMMARY ***
Seat 2: bbbb (small blind) showed [Ah Kh] and lost with Ace high
Seat 6: Hero showed [As Ks] and won (2000) with a pair of Aces
"""

# players_list: 6 posições (num_extracted==num_hh → sem over-read).
_PN = {"players_list": [
    {"name": "BustedGuy", "position": "SB", "bounty_value_usd": None},   # bustou + NULL → G1
    {"name": "LiveGuy", "position": "UTG", "bounty_value_usd": None},     # não bustou, não Hero → G2
    {"name": "Lauro Dermio", "position": "BB", "bounty_value_usd": None}, # Hero → excluído
    {"name": "HasCrown", "position": "CO", "bounty_value_usd": 50.0},     # tem coroa → skip
    {"name": "P5", "position": "MP", "bounty_value_usd": 25.0},
    {"name": "P6", "position": "BTN", "bounty_value_usd": 25.0},
]}


def test_classify_splits_group1_and_group2():
    res = cr.classify_hand(_RAW, _PN)
    assert res["over_read"] is False
    assert res["num_hh"] == 6 and res["num_extracted"] == 6
    assert [g["name"] for g in res["group1"]] == ["BustedGuy"]   # SB bustou + NULL
    assert [g["name"] for g in res["group2"]] == ["LiveGuy"]     # UTG NULL não-bustou
    # Hero (Lauro) NULL não entra em nenhum grupo
    names = {g["name"] for g in res["group1"] + res["group2"]}
    assert "Lauro Dermio" not in names
    assert "HasCrown" not in names


def test_summary_lost_line_not_eaten_by_seat_re():
    # a linha do SUMMARY com "(small blind)" tem de chegar ao _LOST_RE
    _, _, _, busted = cr._parse_busts(_RAW)
    assert "bbbb" in busted


def test_over_read_flagged_when_counts_differ():
    pn = {"players_list": _PN["players_list"][:4]}   # 4 extraídos vs 6 na HH
    res = cr.classify_hand(_RAW, pn)
    assert res["over_read"] is True


def test_hero_name_tolerant_to_truncation():
    assert cr._is_hero_name("Lauro Dermio") is True
    assert cr._is_hero_name("Lauro Der..") is True
    assert cr._is_hero_name("Random Villain") is False
