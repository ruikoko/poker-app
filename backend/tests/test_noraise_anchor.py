"""Unit tests — pt86c #HRC-ANCHOR-FALLS-TO-ROOT-NOT-HERO (Passo 1).

`derive_noraise_anchor`: âncora da 1ª DECISÃO do Hero quando NÃO há raise
voluntário preflop. Cobre os 4 ramos da regra do Rui:
  - pote por abrir no turno do Hero → open do próprio Hero
  - limp da SB antes do Hero (Hero=BB) → complete da SB
  - walk (Hero nunca decide) → None
  - limp de não-blind antes do Hero → None (Passo 2)

Geometria 6-max com button=Seat 4 (label order [MP,HJ,CO,BTN,SB,BB] em ordem
preflop a partir do Seat 1): seat1=MP seat2=HJ seat3=CO seat4=BTN seat5=SB
seat6=BB. As asserts de posição usam `_resolve_position_for_nick` (não
hardcode) para ficarem robustas a mudanças de convenção.
"""
from app.services.queue_export import (
    derive_noraise_anchor,
    derive_aggressor_real_action,
    _resolve_position_for_nick,
    _hero_nick_from_hh,
)

_HDR = (
    "Poker Hand #TM1: Tournament #1, Test Hold'em No Limit - "
    "Level7(350/700(100)) - 2026/06/23 12:00:00\n"
    "Table '1' 6-max Seat #4 is the button\n"
)
_SEATS_HERO_BTN = (
    "Seat 1: P1 (40,000 in chips)\n"
    "Seat 2: P2 (40,000 in chips)\n"
    "Seat 3: P3 (40,000 in chips)\n"
    "Seat 4: Hero (40,000 in chips)\n"
    "Seat 5: P5 (40,000 in chips)\n"
    "Seat 6: P6 (40,000 in chips)\n"
)
_SEATS_HERO_BB = (
    "Seat 1: P1 (40,000 in chips)\n"
    "Seat 2: P2 (40,000 in chips)\n"
    "Seat 3: P3 (40,000 in chips)\n"
    "Seat 4: P4 (40,000 in chips)\n"
    "Seat 5: P5 (40,000 in chips)\n"
    "Seat 6: Hero (40,000 in chips)\n"
)


def _hh(seats, *action_lines):
    return (
        _HDR + seats + "*** HOLE CARDS ***\n"
        "Dealt to Hero [Ah Kh]\n"
        + "".join(l + "\n" for l in action_lines)
        + "*** SUMMARY ***\n"
    )


def test_hero_open_button_first_in_unopened():
    """BTN folda num pote por abrir → âncora no open do próprio Hero (BTN)."""
    hh = _hh(_SEATS_HERO_BTN, "P1: folds", "P2: folds", "P3: folds",
             "Hero: folds", "P5: folds")
    assert derive_aggressor_real_action(hh, 350, 700) is None  # sem raise
    a = derive_noraise_anchor(hh, 350, 700)
    assert a == {
        "type": "open", "size_bb": None,
        "position": _resolve_position_for_nick(hh, "Hero"),
        "source": "noraise_hero_open",
    }
    assert a["position"] == "BTN"


def test_hero_open_ignores_sb_limp_downstream():
    """SB limpa DEPOIS do Hero foldar → âncora continua no open do Hero (BTN);
    o limp da SB é jusante e indiferente."""
    hh = _hh(_SEATS_HERO_BTN, "P1: folds", "P2: folds", "P3: folds",
             "Hero: folds", "P5: calls 350", "P6: checks")
    a = derive_noraise_anchor(hh, 350, 700)
    assert a["source"] == "noraise_hero_open"
    assert a["position"] == "BTN"


def test_walk_hero_bb_returns_none():
    """Hero=BB, todos foldam até à SB que folda → walk; Hero nunca age → None."""
    hh = _hh(_SEATS_HERO_BB, "P1: folds", "P2: folds", "P3: folds",
             "P4: folds", "P5: folds")
    assert derive_noraise_anchor(hh, 350, 700) is None


def test_sb_complete_hero_bb_anchors_sb():
    """Hero=BB, SB completa (limp) antes do Hero → âncora no complete da SB."""
    hh = _hh(_SEATS_HERO_BB, "P1: folds", "P2: folds", "P3: folds",
             "P4: folds", "P5: calls 350", "Hero: checks")
    a = derive_noraise_anchor(hh, 350, 700)
    assert a == {
        "type": "complete", "size_bb": None, "position": "SB",
        "source": "noraise_sb_complete",
    }
    assert _resolve_position_for_nick(hh, "P5") == "SB"


def test_nonblind_limp_before_hero_returns_none():
    """Limp de NÃO-blind (MP) antes do Hero → Passo 2 (nó não modelado) → None."""
    hh = _hh(_SEATS_HERO_BTN, "P1: calls 700", "P2: folds", "P3: folds",
             "Hero: folds", "P5: folds")
    assert _resolve_position_for_nick(hh, "P1") == "MP"
    assert derive_noraise_anchor(hh, 350, 700) is None


_SEATS_HERO_SB = (
    "Seat 1: P1 (40,000 in chips)\n"
    "Seat 2: P2 (40,000 in chips)\n"
    "Seat 3: P3 (40,000 in chips)\n"
    "Seat 4: P4 (40,000 in chips)\n"
    "Seat 5: Hero (40,000 in chips)\n"
    "Seat 6: P6 (40,000 in chips)\n"
)


def test_hero_open_sb_first_in():
    """Hero=SB num pote por abrir (todos os de antes foldam) → open do Hero (SB)."""
    hh = _hh(_SEATS_HERO_SB, "P1: folds", "P2: folds", "P3: folds",
             "P4: folds", "Hero: folds")
    a = derive_noraise_anchor(hh, 350, 700)
    assert a["source"] == "noraise_hero_open"
    assert a["position"] == _resolve_position_for_nick(hh, "Hero") == "SB"


def test_missing_hero_returns_none():
    """Sem `Dealt to` (sem Hero identificável) → None defensivo."""
    hh = (_HDR + _SEATS_HERO_BTN + "*** HOLE CARDS ***\n"
          "P1: folds\nP2: folds\n*** SUMMARY ***\n")
    assert _hero_nick_from_hh(hh) is None
    assert derive_noraise_anchor(hh, 350, 700) is None


def test_invalid_blinds_returns_none():
    hh = _hh(_SEATS_HERO_BTN, "P1: folds", "Hero: folds")
    assert derive_noraise_anchor(hh, 0, 0) is None
