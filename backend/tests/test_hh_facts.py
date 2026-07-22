# -*- coding: utf-8 -*-
"""Helpers ÚNICOS de factos da HH (hh_facts) — a régua do painel de reconciliação.
Casos calcados nos reais desta semana (GG-6180819531 all-in pré · folds pré ·
GG-6177134170 bets no flop · marcador SHOWDOWN espúrio)."""
from app.services.hh_facts import hero_postflop_betting, real_showdown

_ALLIN_PRE_BOARD_RUNS = (
    "Poker Hand #TM1: Tournament #1, Hold'em - Level4(500/1,000)\n"
    "Seat 1: Hero (10,000 in chips)\n"
    "a1: raises 4,050 to 5,050 and is all-in\n"
    "Hero: raises 3,050 to 8,100 and is all-in\n"
    "*** FLOP *** [Js 9d 7s]\n"
    "*** TURN *** [Js 9d 7s] [3h]\n"
    "*** RIVER *** [Js 9d 7s 3h] [Jd]\n"
    "*** SHOWDOWN ***\n"
    "a1 collected 17,550 from pot\n"
    "*** SUMMARY ***\n"
)

_FOLD_PRE = (
    "Poker Hand #TM2: ...\n"
    "Hero: folds\n"
    "a1 collected 1,500 from pot\n"
    "*** SUMMARY ***\n"
)

_HERO_BETS_FLOP = (
    "Poker Hand #TM3: ...\n"
    "Hero: raises 5,000 to 10,000\n"
    "*** FLOP *** [Ah 7s 3d]\n"
    "Hero: bets 41,000\n"
    "a1: folds\n"
    "*** SUMMARY ***\n"
)

_HERO_CHECKS_FLOP = _HERO_BETS_FLOP.replace("Hero: bets 41,000", "Hero: checks")

_SPURIOUS_SHOWDOWN = (
    "Poker Hand #TM4: ...\n"
    "Hero: raises 2,000 to 4,000\n"
    "a1: folds\n"
    "*** SHOWDOWN ***\n"          # marcador espúrio do GG (fold-to) — SEM 'shows'
    "Hero collected 5,000 from pot\n"
    "*** SUMMARY ***\n"
)

_REAL_SHOWS = (
    "Poker Hand #TM5: ...\n"
    "*** FLOP *** [Ks 3h 6h]\n"
    "Hero: checks\n"
    "*** SHOWDOWN ***\n"
    "a1: shows [4d 3h] (two pair)\n"
    "Hero: shows [Th Kh] (a pair of Tens)\n"
    "a1 collected 192,826 from pot\n"
    "*** SUMMARY ***\n"
)


def test_allin_pre_com_board_a_correr_NAO_e_posflop():
    # a régua é AÇÃO, não distribuição de cartas (caso GG-6180819531)
    assert hero_postflop_betting(_ALLIN_PRE_BOARD_RUNS) is False


def test_fold_preflop_nao_e_posflop():
    assert hero_postflop_betting(_FOLD_PRE) is False


def test_bets_e_checks_no_flop_sao_posflop():
    assert hero_postflop_betting(_HERO_BETS_FLOP) is True
    assert hero_postflop_betting(_HERO_CHECKS_FLOP) is True


def test_acao_de_vilao_posflop_nao_conta_como_hero():
    raw = _HERO_BETS_FLOP.replace("Hero: bets 41,000", "a2: bets 41,000")
    assert hero_postflop_betting(raw) is False


def test_showdown_marcador_espurio_nao_conta():
    assert real_showdown(_SPURIOUS_SHOWDOWN) is False


def test_showdown_real_com_shows_conta():
    assert real_showdown(_REAL_SHOWS) is True


def test_inputs_vazios():
    assert hero_postflop_betting("") is False and hero_postflop_betting(None) is False
    assert real_showdown("") is False and real_showdown(None) is False
