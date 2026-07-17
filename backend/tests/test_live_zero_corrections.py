"""CORREÇÃO 3 (bust cross-hand — última mão nunca condena vivos) + CORREÇÃO 1
(releitura mostra TODOS os lugares por preencher, vivos OU bustados-nesta-mão;
selados fora; contador X de Y). Funções puras + um caso end-to-end com query mockada."""
from unittest.mock import patch

from app.routers import gg_health


# ── CORREÇÃO 3 — _is_cross_hand_eliminated ───────────────────────────────────
def test_cross_hand_last_recorded_hand_never_condemns():
    # Esta É a última mão gravada do torneio (tlast == played_at): ninguém reaparece
    # porque não há mais mãos, não por bust → NUNCA condena vivos.
    assert gg_health._is_cross_hand_eliminated(
        "abc", "2026-07-11 20:00:00", "2026-07-11 20:00:00", "2026-07-11 20:00:00") is False


def test_cross_hand_real_bust_when_tournament_continues():
    # O hash não reaparece (ls == played_at) MAS o torneio continua (tlast > played_at)
    # → eliminado de verdade.
    assert gg_health._is_cross_hand_eliminated(
        "abc", "2026-07-11 20:00:00", "2026-07-11 20:00:00", "2026-07-11 21:30:00") is True


def test_cross_hand_alive_reappears_later():
    # Reaparece numa mão posterior (ls > played_at) → vivo.
    assert gg_health._is_cross_hand_eliminated(
        "abc", "2026-07-11 20:00:00", "2026-07-11 21:00:00", "2026-07-11 21:30:00") is False


def test_cross_hand_no_hash_or_missing_ts():
    assert gg_health._is_cross_hand_eliminated(None, "x", "x", "x") is False
    assert gg_health._is_cross_hand_eliminated("abc", "x", None, "y") is False
    assert gg_health._is_cross_hand_eliminated("abc", "x", "y", None) is False


# ── CORREÇÃO 1 — _whole_table_zero_select (puro) ─────────────────────────────
def test_select_includes_unfilled_excludes_sealed_and_counts():
    pl = ([{"name": f"p{i}", "bounty_value_usd": 0} for i in range(6)]
          + [{"name": "s1", "bounty_value_usd": 50, "bounty_source": "manual"},
             {"name": "s2", "bounty_value_usd": 30, "bounty_source": "green_ko"}])
    q, zero, n = gg_health._whole_table_zero_select(pl)
    assert n == 8                              # Y = lugares da captura
    assert len(zero) == 6                      # X = por preencher
    assert "s1" not in zero and "s2" not in zero   # selados fora
    assert q is True                           # 6/8 >= 0.7 → mesa-toda


def test_select_not_qualify_below_threshold():
    pl = [{"name": "a", "bounty_value_usd": 0},
          {"name": "b", "bounty_value_usd": 50, "bounty_source": "manual"},
          {"name": "c", "bounty_value_usd": 50, "bounty_source": "manual"}]
    q, zero, n = gg_health._whole_table_zero_select(pl)
    assert n == 3 and len(zero) == 1 and q is False   # 1/3 < 0.7


# ── CORREÇÃO 1 — end-to-end (query mockada): bustado-nesta-mão entra + X de Y ──
def test_whole_table_hands_includes_busted_and_reports_n_total():
    pl = [{"name": "Loser", "bounty_value_usd": None},    # bustou NESTA mão, sem coroa
          {"name": "A", "bounty_value_usd": 0},
          {"name": "B", "bounty_value_usd": 0},
          {"name": "C", "bounty_value_usd": 0},
          {"name": "Sealed", "bounty_value_usd": 50, "bounty_source": "manual"}]
    base_rows = [{"tournament_number": "T1", "buy_in_bounty": 100}]
    hand_rows = [{"id": 1, "hand_id": "GG-1", "tn": "T1", "tname": "Daily KO",
                  "pa": "2026-07-11 10:00:00", "pn": {"players_list": pl}, "ssid": 9}]
    with patch.object(gg_health, "query", side_effect=[base_rows, hand_rows]):
        out = gg_health._whole_table_zero_hands()
    assert len(out) == 1
    h = out[0]
    assert "Loser" in h["zero_seats"]          # bustado-nesta-mão SEM coroa → entra (Correção 1)
    assert "Sealed" not in h["zero_seats"]     # coroa selada → fora
    assert h["n_total"] == 5                    # Y
    assert len(h["zero_seats"]) == 4            # X (Loser, A, B, C)
