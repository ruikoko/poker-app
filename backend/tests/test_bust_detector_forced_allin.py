"""CORREÇÃO — all-in por POST FORÇADO deixa de depender da frase 'all-in'.

Raiz: `busted_keys_from_hh` (eliminated_bounty) e `_parse_busts` (crown_recovery)
ancoravam na frase de acção 'all-in', que o GG NÃO escreve quando o stack inteiro
se esgota a postar ante+cega. Regra nova (conta, não texto): soma dos posts
forçados (ante+cegas) >= stack de entrada = all-in; some-se ao all-in por frase;
cruza-se com 'perdeu' como hoje. Guarda: perder um pote ≠ bustar (só é bust quem
ficou sem fichas — a conta do stack).
"""
from app.services.eliminated_bounty import busted_keys_from_hh, forced_allin_keys
from app.services.crown_recovery import _parse_busts


# HH REAL da GG-6117282604 (verbatim da BD). Contém DOIS casos no mesmo texto:
#  - c94c6e7b (vGVSv): ante 1.200 + SB 2.370 = 3.570 = stack → all-in por post + perdeu.
#  - 1c062e4f: mostrou 'and lost' no showdown MAS entrou com 134.027 e sobrou-lhe
#    stack (não all-in) → o FALSO-POSITIVO que a guarda tem de rejeitar.
_HH_REAL = """Poker Hand #TM6117282604: Tournament #293610929, Speed Racer Bounty Europe $108 [10 BB] Hold'em No Limit - Level9(4,000/8,000(1,200)) - 2026/06/26 17:46:24
Table '2' 6-max Seat #5 is the button
Seat 1: f4948de8 (49,975 in chips)
Seat 2: 1c062e4f (134,027 in chips)
Seat 4: 31f175f5 (122,848 in chips)
Seat 5: Hero (81,980 in chips)
Seat 6: c94c6e7b (3,570 in chips)
f4948de8: posts the ante 1,200
1c062e4f: posts the ante 1,200
31f175f5: posts the ante 1,200
c94c6e7b: posts the ante 1,200
Hero: posts the ante 1,200
c94c6e7b: posts small blind 2,370
f4948de8: posts big blind 8,000
*** HOLE CARDS ***
Dealt to f4948de8
Dealt to 1c062e4f
Dealt to 31f175f5
Dealt to Hero [Ad 3d]
Dealt to c94c6e7b
1c062e4f: raises 8,000 to 16,000
31f175f5: folds
Hero: raises 64,780 to 80,780 and is all-in
f4948de8: folds
1c062e4f: calls 64,780
Hero: shows [Ad 3d]
c94c6e7b: shows [2h Ks]
1c062e4f: shows [6c 7s]
*** FLOP *** [Qh Ac 5d]
*** TURN *** [Qh Ac 5d] [Jd]
*** RIVER *** [Qh Ac 5d Jd] [Jc]
*** SHOWDOWN ***
Hero collected 15,480 from pot
Hero collected 162,450 from pot
*** SUMMARY ***
Total pot 177,930 | Rake 0 | Jackpot 0 | Bingo 0 | Fortune 0 | Tax 0
Board [Qh Ac 5d Jd Jc]
Seat 1: f4948de8 (big blind) folded before Flop
Seat 2: 1c062e4f showed [6c 7s] and lost with a pair of Jacks
Seat 4: 31f175f5 folded before Flop
Seat 5: Hero (button) showed [Ad 3d] and won (177,930) with two pair, Aces and Jacks
Seat 6: c94c6e7b (small blind) showed [2h Ks] and lost with a pair of Jacks
"""


# ── Teste 1 — o caso real: vGVSv detetado pelos DOIS detetores ────────────────
def test_real_vgvsv_forced_allin_detected_both():
    assert "c94c6e7b" in busted_keys_from_hh(_HH_REAL)          # Detetor 1 (vivo-$0)
    _s, _b, _n, busted = _parse_busts(_HH_REAL)
    assert "c94c6e7b" in busted                                 # Detetor 2 (recuperáveis)
    assert "c94c6e7b" in forced_allin_keys(_HH_REAL)            # o sinal aritmético


# ── Teste 2 (o mais importante) — perdeu o pote MAS ficou com fichas → NÃO bust ─
def test_lost_pot_but_kept_chips_is_not_bust():
    # 1c062e4f: 'and lost' no showdown, entrou com 134.027, só postou ante 1.200
    # (posts << stack) e chamou 64.780 (sobrou-lhe stack) → NÃO é bust.
    assert "1c062e4f" not in forced_allin_keys(_HH_REAL)        # a conta não o marca
    assert "1c062e4f" not in busted_keys_from_hh(_HH_REAL)      # Detetor 1
    _s, _b, _n, busted = _parse_busts(_HH_REAL)
    assert "1c062e4f" not in busted                             # Detetor 2 (apesar do 'lost')


# ── Teste 3 — postou a cega mas sobrou-lhe stack → NÃO é all-in ────────────────
def test_posted_blind_with_stack_left_is_not_allin():
    # f4948de8: postou BB 8.000 com stack 49.975 → 8.000 < 49.975 → não all-in.
    assert "f4948de8" not in forced_allin_keys(_HH_REAL)


# ── Teste 4 — o all-in por FRASE continua a funcionar ─────────────────────────
_HH_PHRASE = """Poker Hand #TM1: Tournament #999, Test - Level1(500/1,000) - 2026/01/01 00:00:00
Table '1' 6-max Seat #1 is the button
Seat 1: winner (100,000 in chips)
Seat 2: cccc (20,000 in chips)
winner: posts small blind 500
cccc: posts big blind 1,000
*** HOLE CARDS ***
cccc: raises 19,000 to 20,000 and is all-in
winner: calls 19,000
*** SHOWDOWN ***
winner collected 40,000 from pot
*** SUMMARY ***
Seat 1: winner showed [Ah Ad] and won (40,000) with a pair of Aces
Seat 2: cccc showed [2h 3d] and lost with high card
"""


def test_phrase_allin_still_detected():
    # cccc: all-in por FRASE ('and is all-in') + perdeu; postou BB 1.000 de 20.000
    # (posts << stack) → NÃO é forçado, mas a frase apanha-o. Regra nova não estraga a antiga.
    assert "cccc" not in forced_allin_keys(_HH_PHRASE)          # não é forçado
    assert "cccc" in busted_keys_from_hh(_HH_PHRASE)            # Detetor 1 (frase)
    _s, _b, _n, busted = _parse_busts(_HH_PHRASE)
    assert "cccc" in busted                                     # Detetor 2 (frase & lost)
    assert "winner" not in busted                              # o vencedor nunca busta
