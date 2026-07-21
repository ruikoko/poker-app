"""Detetor de bounties recuperáveis (#CROWN-RECOVERY) — classify_hand puro.
Cobre a armadilha-raiz: linhas do SUMMARY "Seat N: hash (small blind) ..." NÃO podem
ser comidas pelo _SEAT_RE (senão o eliminado com posição rotulada nunca é lido).
A régua de quem morreu vive em `eliminated_bounty.allin_outcomes` (fonte única,
#BUST-NO-COVERAGE-GUARD) — este módulo só lê a mesa e distribui pelos baldes."""
from app.services import crown_recovery as cr
from app.services import eliminated_bounty as eb

# HH sintética 6-max: button=Seat1; bbbb (SB) all-in e perdeu o pote = bustou.
# A linha "<vencedor> collected" é OBRIGATÓRIA (toda a HH real do GG a tem) — é ela
# que distingue quem ganhou o pote de quem o perdeu na fonte única.
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
Hero collected 2,000 from pot
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


def test_seat_line_with_position_label_still_parsed():
    # a linha do SUMMARY com "(small blind)" não pode ser comida pelo _SEAT_RE;
    # bbbb (all-in, não coletou, sem devolução) sai MORTO da fonte única.
    _, _, _, mortos, vivos = cr._parse_busts(_RAW)
    assert "bbbb" in mortos and vivos == set()


def test_over_read_flagged_when_counts_differ():
    pn = {"players_list": _PN["players_list"][:4]}   # 4 extraídos vs 6 na HH
    res = cr.classify_hand(_RAW, pn)
    assert res["over_read"] is True


def test_matador_hero_resolved_by_real_name():
    # o vencedor é o Hero (hash 'Hero'); a entrada dele em players_list vem sem
    # posição → tem de resolver pelo NOME REAL (não '—') e marcar is_hero.
    res = cr.classify_hand(_RAW, _PN)
    assert len(res["matadores"]) == 1
    m = res["matadores"][0]
    assert m["is_hero"] is True
    assert m["name"] == "Lauro Dermio"


def test_hero_name_tolerant_to_truncation():
    assert cr._is_hero_name("Lauro Dermio") is True
    assert cr._is_hero_name("Lauro Der..") is True
    assert cr._is_hero_name("Random Villain") is False


# ── Régua do resto-em-BB: all-in que PERDE mas SOBREVIVE (cobriu o adversário) ──
# bbbb (SB) faz all-in 50k, Hero cobre só 20k, 30k DEVOLVIDOS → bbbb fica com
# 30 BB (BB=1000) = VIVO. Coroa NULL = leitura falhada da placa própria, não verde-KO.
_RAW_SURVIVOR = """Poker Hand #TM2: Tournament #888, Test KO Hold'em No Limit - Level5(500/1,000(150))
Table '7' 6-max Seat #1 is the button
Seat 1: aaaa (5,000 in chips)
Seat 2: bbbb (50,000 in chips)
Seat 3: cccc (1,000 in chips)
Seat 4: dddd (1,000 in chips)
Seat 5: eeee (1,000 in chips)
Seat 6: Hero (20,000 in chips)
bbbb: raises 49,000 to 50,000 and is all-in
Hero: calls 20,000 and is all-in
Uncalled bet (30,000) returned to bbbb
Hero collected 40,000 from pot
*** SUMMARY ***
Seat 2: bbbb (small blind) showed [Ah Kh] and lost with Ace high
Seat 6: Hero showed [As Ks] and won (40,000) with a pair of Aces
"""

# Mesmo spot mas bbbb TOTALMENTE coberto (sem devolução) → resto 0 = bustou.
_RAW_COVERED = _RAW_SURVIVOR.replace(
    "Uncalled bet (30,000) returned to bbbb\n", "")


def test_survivor_goes_to_misread_not_group1():
    # bbbb (SB) perdeu o all-in mas ficou com 30 BB → misread (re-ler placa),
    # NUNCA group1 (verde × 2). LiveGuy (UTG, não all-in) fica em group2.
    res = cr.classify_hand(_RAW_SURVIVOR, _PN)
    assert [g["name"] for g in res["group1"]] == []
    assert [g["name"] for g in res["misread"]] == ["BustedGuy"]
    assert [g["name"] for g in res["group2"]] == ["LiveGuy"]
    assert "bbbb" not in res["bust_hashes"]      # não conta como bust


def test_covered_allin_loss_is_real_bust():
    # sem devolução → resto 0 → bust real → group1 + hash exposto p/ contraprova
    res = cr.classify_hand(_RAW_COVERED, _PN)
    assert [g["name"] for g in res["group1"]] == ["BustedGuy"]
    assert res["misread"] == []
    assert res["bust_hashes"] == ["bbbb"]


def test_bb_and_returned_and_table_helpers():
    # a cega grande e a devolução vivem na FONTE ÚNICA (eliminated_bounty); o
    # crown_recovery já não tem cópia própria — só a leitura da mesa fica cá.
    assert eb.bb_from_hh(_RAW_SURVIVOR) == 1000
    assert eb.returned_by_key(_RAW_SURVIVOR) == {"bbbb": 30000}
    assert cr._parse_table(_RAW_SURVIVOR) == "7"
    assert cr.seated_hashes(_RAW_SURVIVOR) == {"aaaa", "bbbb", "cccc", "dddd", "eeee", "Hero"}


def test_no_bb_defaults_to_bust():
    # _RAW não tem blinds no header ("Level1") → bb None → trata all-in+perdeu como
    # bust (comportamento seguro pré-régua; a contraprova do router é o backup).
    res = cr.classify_hand(_RAW, _PN)
    assert [g["name"] for g in res["group1"]] == ["BustedGuy"]
    assert res["misread"] == []
