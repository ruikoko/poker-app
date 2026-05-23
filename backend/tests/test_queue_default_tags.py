"""Tests para a normalização do basket de tags em /api/queue/hrc.

Substitui o antigo `_expand_icm_case` (ad-hoc, só ICM) por
`_normalize_tags_basket` (#B17, cobre qualquer case-variant via
`normalize_tag_key`). Regressão zero nos casos ICM antigos + apanha
agora variantes que escapavam.
"""
from __future__ import annotations

from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import require_auth_or_api_key
from app.routers.hands import normalize_tag_key
from app.routers.queue import (
    _DEFAULT_TAGS,
    _normalize_tags_basket,
    router as queue_router,
)


def _make_app():
    app = FastAPI()
    app.include_router(queue_router)
    app.dependency_overrides[require_auth_or_api_key] = (
        lambda: {"id": None, "email": None, "auth_type": "api_key"}
    )
    return app


# ── _normalize_tags_basket unit ──────────────────────────────────────


def test_basket_normalize_case_variants_collapse():
    """ICM, icm, Icm → 1 key."""
    out = _normalize_tags_basket(["ICM", "icm", "Icm"])
    assert out == ["icm"]


def test_basket_normalize_hyphen_vs_space_collapse():
    """'icm-pko', 'ICM PKO', 'icm pko' → 1 key 'icm pko'."""
    out = _normalize_tags_basket(["icm-pko", "ICM PKO", "icm pko"])
    assert out == ["icm pko"]


def test_basket_normalize_preserves_distinct_concepts():
    """'pos-pko' vs 'pko-pos' são tags semanticamente distintas; word order
    importa em normalize_tag_key (não é uma anagrama mas case+hyphen)."""
    out = _normalize_tags_basket(["pos-pko", "pko-pos"])
    assert sorted(out) == ["pko pos", "pos pko"]


def test_basket_normalize_drops_empty_and_dedupes_preserving_order():
    out = _normalize_tags_basket(["ICM", "", "  ", "icm-pko", "ICM"])
    assert out == ["icm", "icm pko"]


def test_default_basket_normalizes_to_six_distinct_keys():
    """Os 6 conceitos do _DEFAULT_TAGS produzem 6 norm_keys distintos.

    Cobre o objectivo da limpeza Fix 1: a lista perdeu os 2 duplicados
    case-variant ('icm-ft', 'icm-pko-ft') sem perder cobertura — antes
    precisava de escrever ambas as forms.
    """
    norm = _normalize_tags_basket(_DEFAULT_TAGS)
    assert sorted(norm) == sorted({
        normalize_tag_key("icm-pko"),       # 'icm pko'
        normalize_tag_key("PKO SS"),        # 'pko ss'
        normalize_tag_key("sqz-pko"),       # 'sqz pko'
        normalize_tag_key("ICM"),           # 'icm'
        normalize_tag_key("ICM FT"),        # 'icm ft'
        normalize_tag_key("ICM PKO FT"),    # 'icm pko ft'
    })
    assert len(norm) == 6


# ── Regressão: casos ICM antigos continuam a funcionar ──────────────


def test_regression_icm_uppercase_matches_icm_lowercase_in_basket():
    """O hack antigo `_expand_icm_case` garantia que pedir 'ICM' incluía
    'icm' e vice-versa. Confirmar que o novo mecanismo faz o mesmo via
    normalização (ambos viram norm_key 'icm')."""
    assert _normalize_tags_basket(["ICM"]) == ["icm"]
    assert _normalize_tags_basket(["icm"]) == ["icm"]
    # Pedir ambos: 1 chave deduped.
    assert _normalize_tags_basket(["ICM", "icm"]) == ["icm"]


def test_regression_icm_ft_variants_collapse():
    """'ICM FT' (HM3) e 'icm-ft' (Discord channel) eram entradas separadas
    no _DEFAULT_TAGS antigo. Agora colapsam para uma só."""
    assert _normalize_tags_basket(["ICM FT"]) == ["icm ft"]
    assert _normalize_tags_basket(["icm-ft"]) == ["icm ft"]
    assert _normalize_tags_basket(["ICM FT", "icm-ft"]) == ["icm ft"]


# ── Endpoint passa o basket normalizado ao SQL ──────────────────────


def test_endpoint_passes_normalized_basket_to_sql():
    """Mocka `query` e confirma que o `tags_norm` chega aos params como
    lista deduped+normalized, independentemente do que o caller mandou."""
    app = _make_app()
    client = TestClient(app)
    captured = {}

    def fake_query(sql, params=None):
        # Só capturamos a 1ª query (hands fetch) — segunda é payouts.
        if "FROM hands" in sql and "discord_tags" in sql:
            captured["params"] = params
        return []

    with patch("app.services.hrc_queue.query", side_effect=fake_query):
        r = client.get(
            "/api/queue/hrc?tags=ICM,icm,ICM-PKO,icm-pko,ICM"
        )
    assert r.status_code == 200
    # Params: (sites, after, before, states, tags_norm, tags_norm)
    assert "params" in captured
    tags_arg = captured["params"][4]
    assert tags_arg == captured["params"][5]
    # 5 inputs colapsam a 2 norm_keys: 'icm' e 'icm pko'
    assert sorted(tags_arg) == ["icm", "icm pko"]


def test_endpoint_default_basket_passes_six_keys_to_sql():
    app = _make_app()
    client = TestClient(app)
    captured = {}

    def fake_query(sql, params=None):
        if "FROM hands" in sql and "discord_tags" in sql:
            captured["params"] = params
        return []

    with patch("app.services.hrc_queue.query", side_effect=fake_query):
        r = client.get("/api/queue/hrc")
    assert r.status_code == 200
    tags_arg = captured["params"][4]
    assert len(tags_arg) == 6


def test_endpoint_filters_meta_echoes_both_raw_and_normalized():
    """O zip resultante tem manifest com filters_meta — confirmar que
    inclui ambos `tags` (raw user input) e `tags_normalized` (post-norm)."""
    import io, json, zipfile

    app = _make_app()
    client = TestClient(app)

    with patch("app.services.hrc_queue.query", return_value=[]):
        r = client.get("/api/queue/hrc?tags=ICM,icm-pko")
    assert r.status_code == 200
    # Zip body com manifest dentro
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    manifest = json.loads(zf.read("manifest.json"))
    filters = manifest.get("filters", {})
    assert filters.get("tags") == ["ICM", "icm-pko"]
    assert filters.get("tags_normalized") == ["icm", "icm pko"]
