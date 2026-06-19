"""pt82 (#HRC-TREES-PERSIST-BEELINK) — nome legível do tree de output.

O backend pré-computa `tree_filename` (a partir do hand record) e mete-o no
meta.json do pack → o adapter copia o zip de output para C:\\hrc\\trees\\<nome>
sem parsear a HH. Formato:
`<torneio>_<mãoHerói>_<AAAA-MM-DD>_<HHhMM>_<hand_id>.zip` (played_at = Lisboa naive).
"""
from __future__ import annotations

from datetime import datetime

from app.services.queue_export import compute_tree_filename, _build_hand_meta


def test_normal_name():
    h = {
        "tournament_name": "Speed Racer Bounty Europe $108",
        "hero_cards": "AhKs",
        "played_at": datetime(2026, 6, 16, 17, 10, 2),
        "hand_id": "GG-6083184245",
    }
    assert compute_tree_filename(h) == (
        "SpeedRacerBountyEurope$108_AhKs_2026-06-16_17h10_GG-6083184245.zip"
    )


def test_invalid_chars_stripped():
    h = {"tournament_name": 'A/B:C*?"<>|D', "hero_cards": "Qs Qd",
         "played_at": datetime(2026, 1, 2, 9, 5), "hand_id": "GG-1"}
    out = compute_tree_filename(h)
    # sem nenhum char inválido de filename Windows
    assert not any(c in out for c in '<>:"/\\|?*')
    assert out == "ABCD_QsQd_2026-01-02_09h05_GG-1.zip"


def test_tournament_truncated_to_40():
    h = {"tournament_name": "X" * 100, "hero_cards": "AhAd",
         "played_at": datetime(2026, 3, 1, 0, 0), "hand_id": "GG-9"}
    tn_part = compute_tree_filename(h).split("_")[0]
    assert len(tn_part) == 40


def test_missing_hero_cards_xx():
    h = {"tournament_name": "Daily", "hero_cards": None,
         "played_at": datetime(2026, 5, 5, 12, 0), "hand_id": "GG-2"}
    assert "_XX_" in compute_tree_filename(h)


def test_missing_tournament_fallback():
    h = {"tournament_name": None, "hero_cards": "AhKs",
         "played_at": datetime(2026, 5, 5, 12, 0), "hand_id": "GG-3"}
    assert compute_tree_filename(h).startswith("torneio_AhKs_")


def test_missing_played_at_fallback():
    h = {"tournament_name": "Daily", "hero_cards": "AhKs",
         "played_at": None, "hand_id": "GG-4"}
    assert "_sem-data_" in compute_tree_filename(h)


def test_played_at_as_iso_string():
    h = {"tournament_name": "Daily", "hero_cards": "AhKs",
         "played_at": "2026-06-16T17:10:02", "hand_id": "GG-5"}
    assert "_2026-06-16_17h10_" in compute_tree_filename(h)


def test_winamax_hand_id_with_hyphens_preserved():
    h = {"tournament_name": "GRAVITY", "hero_cards": "JhJd",
         "played_at": datetime(2026, 6, 15, 18, 8),
         "hand_id": "WN-4850168930850832391-177-1781554111"}
    out = compute_tree_filename(h)
    assert out.endswith("_WN-4850168930850832391-177-1781554111.zip")


def test_hero_cards_as_list_pt82b():
    """Regressão pt82b (#HERO-CARDS-LIST-IN-TREE-NAME): em prod hero_cards vem
    como LISTA → coerce p/ string, sem TypeError (era o 500 do pull)."""
    h = {"tournament_name": "Daily", "hero_cards": ["Ah", "Ks"],
         "played_at": datetime(2026, 6, 1, 20, 30), "hand_id": "GG-7"}
    assert compute_tree_filename(h) == "Daily_AhKs_2026-06-01_20h30_GG-7.zip"


def test_never_raises_on_weird_types_pt82b():
    """À prova de bala: tipos inesperados → fallback <hand_id>.zip, NUNCA levanta."""
    h = {"tournament_name": {"x": 1}, "hero_cards": 12345,
         "played_at": object(), "hand_id": "GG-8"}
    out = compute_tree_filename(h)
    assert out and out.endswith(".zip")
    assert not any(c in out for c in '<>:"/\\|?*')


def test_build_hand_meta_includes_tree_filename():
    """_build_hand_meta mete `tree_filename` (sem tournament_number → sem DB)."""
    h = {"tournament_name": "Daily", "hero_cards": "AhKs",
         "played_at": datetime(2026, 6, 1, 20, 30), "hand_id": "GG-7",
         "tournament_number": None}
    meta = _build_hand_meta(h, "hh", equity_model="multi_table_icm",
                            payout_blob=None, target_node_offset=0)
    assert meta["tree_filename"] == compute_tree_filename(h)
    assert meta["tree_filename"].startswith("Daily_AhKs_2026-06-01_20h30_GG-7")
