"""Tests para `_derive_equity_model` em services/queue_export.py.

Refactor: substituiu os 2 sets `_EQUITY_FT_HM3` / `_EQUITY_FT_DISCORD`
(case-sensitive, exigiam manter ambas as formas) por `_EQUITY_FT_NORM_KEYS`
+ `normalize_tag_key` (#B17). Cobre agora qualquer case-variant.
"""
from __future__ import annotations

from app.services.queue_export import _derive_equity_model, _EQUITY_FT_NORM_KEYS


# ── Regressão: cases antigos continuam a bater ─────────────────────


def test_regression_hm3_capitalized_icm_ft_returns_malmuth():
    """O caso pt23 original — 'ICM FT' em hm3_tags → malmuth_harville_icm."""
    assert _derive_equity_model(["ICM FT"], None) == "malmuth_harville_icm"


def test_regression_hm3_icm_pko_ft_returns_malmuth():
    assert _derive_equity_model(["ICM PKO FT"], None) == "malmuth_harville_icm"


def test_regression_discord_lowercase_hyphen_returns_malmuth():
    """O outro caso pt23 — 'icm-ft' em discord_tags."""
    assert _derive_equity_model(None, ["icm-ft"]) == "malmuth_harville_icm"
    assert _derive_equity_model(None, ["icm-pko-ft"]) == "malmuth_harville_icm"


def test_regression_no_ft_tag_returns_multi_table_icm():
    """Default para mid-MTT: tags sem FT → multi_table_icm."""
    assert _derive_equity_model(["ICM"], ["icm-pko"]) == "multi_table_icm"
    assert _derive_equity_model(["nota++", "pos-pko"], []) == "multi_table_icm"
    assert _derive_equity_model([], []) == "multi_table_icm"


def test_regression_none_inputs_handled():
    assert _derive_equity_model(None, None) == "multi_table_icm"


# ── Casos novos: case-variants que antes escapavam ─────────────────


def test_hm3_lowercase_icm_ft_now_matches():
    """Antes: 'icm ft' em hm3_tags (lowercase) NÃO batia em _EQUITY_FT_HM3.
    Agora: bate via normalize_tag_key."""
    assert _derive_equity_model(["icm ft"], None) == "malmuth_harville_icm"


def test_discord_capitalized_now_matches():
    """Antes: 'ICM-FT' em discord_tags NÃO batia em _EQUITY_FT_DISCORD.
    Agora: bate."""
    assert _derive_equity_model(None, ["ICM-FT"]) == "malmuth_harville_icm"
    assert _derive_equity_model(None, ["ICM-PKO-FT"]) == "malmuth_harville_icm"


def test_mixed_case_with_hyphens_and_spaces_matches():
    """Combinatória de case + separator: tudo bate pela normalize."""
    assert _derive_equity_model(["Icm-Ft"], None) == "malmuth_harville_icm"
    assert _derive_equity_model([], ["ICM PKO FT"]) == "malmuth_harville_icm"
    assert _derive_equity_model(["icm-PKO-FT"], None) == "malmuth_harville_icm"


def test_hm3_form_in_discord_column_and_vice_versa():
    """Tagging cross-fonte: cada coluna pode usar qualquer convenção."""
    # HM3-style em discord_tags
    assert _derive_equity_model(None, ["ICM FT"]) == "malmuth_harville_icm"
    # Discord-style em hm3_tags
    assert _derive_equity_model(["icm-ft"], None) == "malmuth_harville_icm"


def test_ft_tag_among_other_tags_still_matches():
    """Mistura de tags FT + outras → ainda match (curto-circuita no primeiro)."""
    assert _derive_equity_model(
        ["For Review", "ICM FT", "nota++"],
        ["pos-pko"],
    ) == "malmuth_harville_icm"


def test_no_false_positives_from_substring_match():
    """'icm' (sem FT) NÃO deve disparar malmuth. Norm key 'icm' não está
    em _EQUITY_FT_NORM_KEYS ({'icm ft', 'icm pko ft'})."""
    assert _derive_equity_model(["ICM"], ["icm"]) == "multi_table_icm"
    # 'icm pko' (sem FT) também não.
    assert _derive_equity_model(["ICM PKO"], ["icm-pko"]) == "multi_table_icm"


# ── Invariante do set canónico ─────────────────────────────────────


def test_canonical_set_uses_normalized_form():
    """Defensiva: o set _EQUITY_FT_NORM_KEYS contém chaves já normalizadas
    (lowercase, espaço único, sem hyphens). Se alguém adicionar 'ICM FT'
    cru no set, o lookup nunca bate."""
    from app.routers.hands import normalize_tag_key
    for k in _EQUITY_FT_NORM_KEYS:
        assert k == normalize_tag_key(k), (
            f"_EQUITY_FT_NORM_KEYS contém '{k}' não normalizado"
        )
