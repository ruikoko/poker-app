"""RAIZ 2 (11 Jul) — desambiguação de EDIÇÕES do mesmo torneio GG no mesmo dia.

Testa `_disambiguate_editions` (provas duras H1-H4 + quarentena) com os casos
REAIS nomeados, e a integração via `resolve_tournament_number(disambiguate_editions=True)`
(tier='edition_quarantine'). As janelas de mãos são mockadas por tn.
"""
from datetime import datetime
from unittest.mock import patch

from app.services import tournament_resolver as TR
from app.services.tournament_resolver import (
    _disambiguate_editions, resolve_tournament_number,
)


def _cand(tn, name, start, total):
    return {"tournament_number": tn, "tournament_name": name,
            "start_time": start, "total_players": total}


def _windows(mapping):
    """side_effect p/ _edition_hand_window: {tn: (first, last)}."""
    def _fn(site, tn):
        return mapping.get(tn, (None, None))
    return _fn


# ── H3: não-arrancada + eliminações → exclui (o zombie Daily Hyper $60) ────────
def test_daily_hyper_60_zombie_glues_to_started_edition():
    A = _cand("295219051", "Daily Hyper $60", datetime(2026, 7, 2, 17, 45), 172)
    B = _cand("295258986", "Daily Hyper $60", datetime(2026, 7, 2, 20, 45), 169)
    wins = _windows({
        "295219051": (datetime(2026, 7, 2, 18, 10), datetime(2026, 7, 2, 19, 28)),
        "295258986": (datetime(2026, 7, 2, 20, 47), datetime(2026, 7, 2, 21, 30)),
    })
    with patch.object(TR, "_edition_hand_window", side_effect=wins):
        tn, decision, _ = _disambiguate_editions(
            "GGPoker", [A, B], datetime(2026, 7, 2, 20, 19),
            entrants=172, players_left=7, lobby_name="Daily Hyper $60")
    # 295258986 arranca às 20:45 (> 20:19) mas o print mostra 165 eliminados
    # (172-7) → impossível → exclui. Sobra 295219051.
    assert tn == "295219051"


# ── H2: impossibilidade (entrants > campo final) → exclui (BH $88) ────────────
def test_bh88_entrants_exceed_field_excludes_wrong_edition():
    X = _cand("294738291", "Bounty Hunters Deepstack Turbo $88",
              datetime(2026, 6, 30, 20, 15), 219)
    Y = _cand("294711510", "Bounty Hunters Deepstack Turbo $88",
              datetime(2026, 6, 30, 18, 15), 305)
    wins = _windows({
        "294738291": (datetime(2026, 6, 30, 20, 16), datetime(2026, 6, 30, 21, 20)),
        "294711510": (datetime(2026, 6, 30, 18, 15), datetime(2026, 6, 30, 21, 30)),
    })
    with patch.object(TR, "_edition_hand_window", side_effect=wins):
        tn, _, _ = _disambiguate_editions(
            "GGPoker", [X, Y], datetime(2026, 6, 30, 21, 5),
            entrants=287, players_left=128,
            lobby_name="Bounty Hunters Deepstack Turbo $88")
    # entrants=287 > 219 (campo final de 294738291) → impossível → sobra 294711510.
    assert tn == "294711510"


def test_entrants_below_field_is_never_proof():
    """Ressalva do Rui: entrants < campo final é NORMAL (print antes de fechar
    inscrições) e NUNCA prova. Se só isso separasse → quarentena."""
    P = _cand("297027787", "Daily Hyper $80", datetime(2026, 7, 9, 18, 45), 125)
    Q = _cand("297003773", "Daily Hyper $80", datetime(2026, 7, 9, 16, 45), 121)
    wins = _windows({
        "297027787": (datetime(2026, 7, 9, 19, 3), datetime(2026, 7, 9, 19, 13)),
        "297003773": (datetime(2026, 7, 9, 17, 7), datetime(2026, 7, 9, 17, 26)),
    })
    with patch.object(TR, "_edition_hand_window", side_effect=wins):
        tn, decision, _ = _disambiguate_editions(
            "GGPoker", [P, Q], datetime(2026, 7, 9, 19, 25),
            entrants=121, players_left=5, lobby_name="Daily Hyper $80")
    # Ambas arrancadas; entrants=121 casa MELHOR com 297003773 (121) mas isso é
    # só desempate soft → NÃO cola → quarentena.
    assert tn is None
    assert decision == "ambiguous_editions"


# ── H1: nome exacto elimina o superset "Europe" ───────────────────────────────
def test_exact_name_filter_drops_europe_superset():
    exact = _cand("297032960", "Speed Racer Bounty $108 [10 BB]",
                  datetime(2026, 7, 9, 19, 10), 130)
    europe1 = _cand("297045229", "Speed Racer Bounty Europe $108 [10 BB]",
                    datetime(2026, 7, 9, 20, 10), 148)
    europe2 = _cand("297008917", "Speed Racer Bounty Europe $108 [10 BB]",
                    datetime(2026, 7, 9, 17, 10), 176)
    wins = _windows({
        "297032960": (datetime(2026, 7, 9, 19, 10), datetime(2026, 7, 9, 19, 44)),
    })
    with patch.object(TR, "_edition_hand_window", side_effect=wins):
        tn, _, _ = _disambiguate_editions(
            "GGPoker", [exact, europe1, europe2], datetime(2026, 7, 9, 19, 30),
            entrants=122, players_left=49,
            lobby_name="Speed Racer Bounty $108 [10 BB]")
    # "Speed Racer $108" != "Speed Racer Europe $108" → só o exacto sobra.
    assert tn == "297032960"


# ── H4: janela de mãos exclui a edição que já acabou há muito ──────────────────
def test_hand_window_excludes_long_finished_edition():
    early = _cand("297008916", "Speed Racer Bounty $32 [10 BB]",
                  datetime(2026, 7, 9, 17, 10), 464)
    late = _cand("297032961", "Speed Racer Bounty $32 [10 BB]",
                 datetime(2026, 7, 9, 19, 10), 465)
    wins = _windows({
        "297008916": (datetime(2026, 7, 9, 17, 10), datetime(2026, 7, 9, 17, 10)),
        "297032961": (datetime(2026, 7, 9, 19, 10), datetime(2026, 7, 9, 19, 17)),
    })
    with patch.object(TR, "_edition_hand_window", side_effect=wins):
        tn, _, _ = _disambiguate_editions(
            "GGPoker", [early, late], datetime(2026, 7, 9, 19, 16),
            entrants=347, players_left=193,
            lobby_name="Speed Racer Bounty $32 [10 BB]")
    # 297008916 acabou 17:10 (+120min slack = 19:10) < anchor 19:16 → fora da
    # janela; sobra a edição das 19:10.
    assert tn == "297032961"


def test_genuinely_ambiguous_two_started_no_containment_quarantines():
    A = _cand("111", "Foo Bounty $50", datetime(2026, 7, 1, 18, 0), 200)
    B = _cand("222", "Foo Bounty $50", datetime(2026, 7, 1, 20, 0), 200)
    wins = _windows({
        "111": (datetime(2026, 7, 1, 18, 2), datetime(2026, 7, 1, 20, 30)),
        "222": (datetime(2026, 7, 1, 20, 2), datetime(2026, 7, 1, 21, 0)),
    })
    # anchor 21:15 cai na cauda (slack +120min) de AMBAS, sem containment estrito
    # (>última mão das duas), ambas arrancadas, sem eliminações que separem
    # (pl None) → só o desempato soft sobraria → quarentena.
    with patch.object(TR, "_edition_hand_window", side_effect=wins):
        tn, decision, _ = _disambiguate_editions(
            "GGPoker", [A, B], datetime(2026, 7, 1, 21, 15),
            entrants=180, players_left=None, lobby_name="Foo Bounty $50")
    assert tn is None


# ── Integração: tier='edition_quarantine' via resolve_tournament_number ────────
def test_resolve_returns_edition_quarantine_tier():
    editions = [
        {"tournament_number": "297027787", "tournament_name": "Daily Hyper $80",
         "start_time": datetime(2026, 7, 9, 18, 45), "total_players": 125},
        {"tournament_number": "297003773", "tournament_name": "Daily Hyper $80",
         "start_time": datetime(2026, 7, 9, 16, 45), "total_players": 121},
    ]
    wins = _windows({
        "297027787": (datetime(2026, 7, 9, 19, 3), datetime(2026, 7, 9, 19, 13)),
        "297003773": (datetime(2026, 7, 9, 17, 7), datetime(2026, 7, 9, 17, 26)),
    })
    anchor = datetime(2026, 7, 9, 19, 25)
    with patch.object(TR, "query", return_value=editions), \
         patch.object(TR, "_edition_hand_window", side_effect=wins):
        tn, cands, tier = resolve_tournament_number(
            "GGPoker", "Daily Hyper $80", None,
            posted_at_hint=datetime(2026, 7, 9, 18, 25),  # UTC-naive (janela)
            buy_in=80.0, anchor_mode="prestart", return_tier=True,
            disambiguate_editions=True, disambig_anchor_lisbon=anchor,
            disambig_entrants=121, disambig_players_left=5,
        )
    assert tn is None
    assert tier == "edition_quarantine"
    assert len(cands) == 2


def test_resolve_single_edition_glues_without_disambiguation():
    editions = [{"tournament_number": "295428550",
                 "tournament_name": "Bounty Hunters Daily Main",
                 "start_time": datetime(2026, 7, 9, 19, 0), "total_players": 2690}]
    with patch.object(TR, "query", return_value=editions):
        tn, cands, tier = resolve_tournament_number(
            "GGPoker", "Bounty Hunters Daily Main", None,
            posted_at_hint=datetime(2026, 7, 9, 19, 0),
            buy_in=54.0, anchor_mode="prestart", return_tier=True,
            disambiguate_editions=True,
            disambig_anchor_lisbon=datetime(2026, 7, 9, 20, 0),
            disambig_entrants=1877, disambig_players_left=1877,
        )
    assert tn == "295428550"
    assert tier == "summaries"
