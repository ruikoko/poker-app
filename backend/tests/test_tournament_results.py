"""Tests para tournament_result_vision + endpoint /api/tournament-results/import.

Pattern de mocks alinhado com tests/test_lobby_sync.py: TestClient para o
endpoint, override de require_auth via dependency_overrides, mocks por
módulo (não por símbolo) para que reuso por outros tests não parta.
"""
import io
import json
import zipfile
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.services import tournament_result_vision as bv


# ── Fixtures ────────────────────────────────────────────────────────────────

_VANILLA_PRIZES_18 = [
    2133.63, 1582.71, 1174.11, 871.00, 646.14, 479.33,
    355.58, 268.27, 230.72, 230.72, 198.43, 198.43,
    198.43, 170.66, 170.66, 170.66, 170.66, 170.66,
]

_VANILLA_VJ = {
    "tournament_name": "Daily Hyper $80",
    "buy_in_text": "$80",
    "prize_pool": 9420.80,
    "total_players": 128,
    "hero_position": 36,
    "is_pko": False,
    "prizes": {
        str(i + 1): {"prize": v, "bounty_won": None}
        for i, v in enumerate(_VANILLA_PRIZES_18)
    },
}

# PKO: regular prizes ratio ~0.5 do pool ⇒ regular_pool ≈ 17000 num pool 34000.
# Distribuição construída para somar ≈ 17000.
_PKO_REGULAR_PRIZES = {
    "1": 2323.35, "2": 2323.17, "3": 1845.98, "4": 1453.59,
    "5": 1141.99, "6":  894.46, "7":  697.41, "8":  539.36,
    "9":  411.66, "10": 411.66, "11": 311.71, "12": 311.71,
    "13": 311.71, "14": 233.06, "15": 233.06, "16": 233.06,
    "17": 233.06, "18": 173.39, "19": 173.39, "20": 173.39,
    "21": 173.39, "22": 173.39, "23": 173.39, "24": 173.39,
}
_PKO_BOUNTIES = {
    "1": 4293.75, "2": 346.25, "3": 297.50, "4": 200.00,
    "33": None, "41": None, "46": None,
}
# Verifica matematicamente: sum_regular ≈ 13453.32. Para o test parser PKO
# usamos ratio derivado para fazer drift OK: ratio = 1 - regular/pool.
_PKO_SUM_REGULAR = sum(_PKO_REGULAR_PRIZES.values())  # ~15123.73
_PKO_POOL = round(_PKO_SUM_REGULAR * 2, 2)  # ratio 0.5 → regular = pool/2

_PKO_VJ = {
    "tournament_name": "Bounty Hunters Deepstack $88",
    "buy_in_text": "$73.60+$6.40+$8",
    "prize_pool": _PKO_POOL,
    "total_players": 386,
    "hero_position": 12,
    "is_pko": True,
    "prizes": {
        k: {"prize": v, "bounty_won": _PKO_BOUNTIES.get(k)}
        for k, v in _PKO_REGULAR_PRIZES.items()
    },
}


# ── 1-4. parse_and_validate_backoffice_json (unit) ──────────────────────────

def test_backoffice_parse_validates_sum_matches_pool():
    raw = json.dumps(_VANILLA_VJ)
    vj = bv.parse_and_validate_backoffice_json(raw)
    assert vj is not None
    assert vj["is_pko"] is False
    assert vj["tournament_name"] == "Daily Hyper $80"


def test_backoffice_parse_rejects_empty_prizes():
    bad = {**_VANILLA_VJ, "prizes": {}}
    assert bv.parse_and_validate_backoffice_json(json.dumps(bad)) is None


def test_backoffice_parse_rejects_sum_off_tolerance():
    # prize_pool muito off — diff > 0.05.
    bad = {**_VANILLA_VJ, "prize_pool": 5000.00}
    assert bv.parse_and_validate_backoffice_json(json.dumps(bad)) is None


def test_backoffice_parse_pko_missing_ratio_returns_sentinel():
    raw = json.dumps(_PKO_VJ)
    out = bv.parse_and_validate_backoffice_json(raw, ts_pko_ratio=None)
    assert isinstance(out, dict)
    assert out.get("_error") == "missing_pko_ratio"
    assert "_raw" in out


# ── 5-7. Prompt constant + PKO parse validation (sem SDK Anthropic) ─────────
# Padrão alinhado com test_lobby_vision.py — testar funções pure;
# extract_*_payout_json é integration externa, não unit-testado aqui.

def test_backoffice_prompt_constant_mentions_dual_format():
    """Prompt deve referir explicitamente o formato '$X + $Y' (dual PKO)."""
    p = bv._BACKOFFICE_PROMPT
    assert "$X + $Y" in p
    assert "is_pko" in p
    assert "bounty_won" in p


def test_backoffice_parse_pko_validates_with_explicit_ratio():
    """PKO + ratio explícito + sum_prize=regular_pool → vj válido."""
    raw = json.dumps(_PKO_VJ)
    vj = bv.parse_and_validate_backoffice_json(raw, ts_pko_ratio=0.5)
    assert vj is not None
    assert isinstance(vj, dict)
    assert vj.get("_error") is None
    assert vj["is_pko"] is True
    # PKO_VJ tem bounty incompleta → truncated warning expected.
    assert vj.get("_ss_likely_truncated") is True


def test_backoffice_parse_pko_truncated_marks_ss_warning():
    """sum(prize) + sum(bounty) < pool * 0.995 → marca _ss_likely_truncated."""
    # toy: pool=1000, ratio=0.5, regular_pool=500.
    # prizes regular soma 500 ✓; bounties só 50 → total 550 vs pool 1000.
    # drift 450 > 1000*0.005 = 5 → truncated.
    toy = {
        "tournament_name": "Toy PKO $1",
        "prize_pool": 1000.0,
        "total_players": 100,
        "is_pko": True,
        "prizes": {
            "1": {"prize": 300.0, "bounty_won": 50.0},
            "2": {"prize": 200.0, "bounty_won": None},
        },
    }
    vj = bv.parse_and_validate_backoffice_json(json.dumps(toy), ts_pko_ratio=0.5)
    assert vj is not None
    assert vj.get("_ss_likely_truncated") is True


# ── 8-16. Endpoint ──────────────────────────────────────────────────────────

def _make_test_app(authed: bool = True):
    """FastAPI minimal com router tournament_results + opcional override
    de require_auth."""
    from app.routers.tournament_results import router
    from app.auth import require_auth
    app = FastAPI()
    app.include_router(router)
    if authed:
        app.dependency_overrides[require_auth] = lambda: {"id": 1, "email": "t@t"}
    return app


def _png_bytes() -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"x" * 100


def _zip_bytes(files: list[tuple[str, bytes]]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in files:
            zf.writestr(name, data)
    return buf.getvalue()


def test_backoffice_import_single_image_success():
    """1 PNG vanilla, TS existe → success."""
    with patch(
        "app.services.tournament_result_vision.extract_backoffice_payout_json",
        return_value=json.dumps(_VANILLA_VJ),
    ), patch(
        "app.services.tournament_resolver.resolve_tournament_number",
        return_value=("283542054", []),
    ), patch(
        "app.routers.tournament_results.query",
        side_effect=[
            # _lookup_ts_meta
            [{"tournament_format": "None", "tournament_pko_ratio": None}],
        ],
    ), patch(
        "app.services.payouts_service.upsert_payout",
        return_value={"action": "inserted"},
    ):
        client = TestClient(_make_test_app())
        r = client.post(
            "/api/tournament-results/import",
            files={"file": ("daily80.png", _png_bytes(), "image/png")},
            data={"vision_throttle_seconds": "0"},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 1
    assert body["results"][0]["result"] == "success"
    assert body["results"][0]["tournament_number"] == "283542054"
    assert body["results"][0]["n_prizes"] == 18
    assert body["summary"]["success"] == 1


def test_backoffice_import_zip_batch_mixed_results():
    """ZIP com 2 imagens: 1 success vanilla, 1 missing_ts."""
    bad_vj = {**_VANILLA_VJ, "tournament_name": "Inexistent $1"}
    extract_outs = [json.dumps(_VANILLA_VJ), json.dumps(bad_vj)]
    resolve_outs = [("283542054", []), (None, [])]
    query_outs = [
        # 1st: _lookup_ts_meta para tn resolvido
        [{"tournament_format": "None", "tournament_pko_ratio": None}],
        # 2nd: nem chega a _lookup_ts_meta (resolver devolveu None)
    ]
    zb = _zip_bytes([("a.png", _png_bytes()), ("b.png", _png_bytes())])
    with patch(
        "app.services.tournament_result_vision.extract_backoffice_payout_json",
        side_effect=extract_outs,
    ), patch(
        "app.services.tournament_resolver.resolve_tournament_number",
        side_effect=resolve_outs,
    ), patch(
        "app.routers.tournament_results.query",
        side_effect=query_outs,
    ), patch(
        "app.services.payouts_service.upsert_payout",
        return_value={"action": "inserted"},
    ):
        client = TestClient(_make_test_app())
        r = client.post(
            "/api/tournament-results/import",
            files={"file": ("batch.zip", zb, "application/zip")},
            data={"vision_throttle_seconds": "0"},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 2
    results_by = {x["result"] for x in body["results"]}
    assert results_by == {"success", "missing_ts"}


def test_backoffice_import_missing_ts_continues_batch():
    """Resolver devolve (None, []) → result=missing_ts; batch não aborta."""
    with patch(
        "app.services.tournament_result_vision.extract_backoffice_payout_json",
        return_value=json.dumps(_VANILLA_VJ),
    ), patch(
        "app.services.tournament_resolver.resolve_tournament_number",
        return_value=(None, []),
    ):
        client = TestClient(_make_test_app())
        r = client.post(
            "/api/tournament-results/import",
            files={"file": ("x.png", _png_bytes(), "image/png")},
            data={"vision_throttle_seconds": "0"},
        )
    body = r.json()
    assert body["results"][0]["result"] == "missing_ts"
    assert "Importa o .txt primeiro" in body["results"][0]["error"]


def test_backoffice_import_ambiguous_ts_returns_candidates():
    """Resolver devolve (None, [c1, c2]) → result=ambiguous_ts."""
    cands = [
        {"tournament_number": "111", "tournament_name": "Daily Hyper $80"},
        {"tournament_number": "222", "tournament_name": "Daily Hyper $80"},
    ]
    with patch(
        "app.services.tournament_result_vision.extract_backoffice_payout_json",
        return_value=json.dumps(_VANILLA_VJ),
    ), patch(
        "app.services.tournament_resolver.resolve_tournament_number",
        return_value=(None, cands),
    ):
        client = TestClient(_make_test_app())
        r = client.post(
            "/api/tournament-results/import",
            files={"file": ("x.png", _png_bytes(), "image/png")},
            data={"vision_throttle_seconds": "0"},
        )
    body = r.json()
    assert body["results"][0]["result"] == "ambiguous_ts"
    assert len(body["results"][0]["candidates"]) == 2


def test_backoffice_import_dry_run_no_writes():
    """dry_run=True → upsert NÃO chamado; result=success."""
    upsert_calls = {"n": 0}
    def fake_upsert(**kw):
        upsert_calls["n"] += 1
        return {"action": "inserted"}
    with patch(
        "app.services.tournament_result_vision.extract_backoffice_payout_json",
        return_value=json.dumps(_VANILLA_VJ),
    ), patch(
        "app.services.tournament_resolver.resolve_tournament_number",
        return_value=("283542054", []),
    ), patch(
        "app.routers.tournament_results.query",
        side_effect=[
            [{"tournament_format": "None", "tournament_pko_ratio": None}],
        ],
    ), patch(
        "app.services.payouts_service.upsert_payout",
        side_effect=fake_upsert,
    ):
        client = TestClient(_make_test_app())
        r = client.post(
            "/api/tournament-results/import",
            files={"file": ("x.png", _png_bytes(), "image/png")},
            data={"dry_run": "true", "vision_throttle_seconds": "0"},
        )
    assert r.json()["results"][0]["result"] == "success"
    assert upsert_calls["n"] == 0
    assert r.json()["results"][0]["source"].endswith("(dry_run)")


def test_backoffice_import_skip_existing_idempotency():
    """skip_existing=true + row prévia backoffice_vision: → skipped_existing."""
    with patch(
        "app.services.tournament_result_vision.extract_backoffice_payout_json",
        return_value=json.dumps(_VANILLA_VJ),
    ), patch(
        "app.services.tournament_resolver.resolve_tournament_number",
        return_value=("283542054", []),
    ), patch(
        "app.routers.tournament_results.query",
        side_effect=[
            # 1: _lookup_ts_meta
            [{"tournament_format": "None", "tournament_pko_ratio": None}],
            # 2: skip_existing lookup → encontra row backoffice_vision:
            [{"source": "backoffice_vision:old.png"}],
        ],
    ), patch(
        "app.services.payouts_service.upsert_payout",
        return_value={"action": "updated"},
    ) as m_upsert:
        client = TestClient(_make_test_app())
        r = client.post(
            "/api/tournament-results/import",
            files={"file": ("new.png", _png_bytes(), "image/png")},
            data={"skip_existing": "true", "vision_throttle_seconds": "0"},
        )
    assert r.json()["results"][0]["result"] == "skipped_existing"
    m_upsert.assert_not_called()


def test_backoffice_import_unauthorized_401():
    """Sem override de require_auth → 401."""
    client = TestClient(_make_test_app(authed=False))
    r = client.post(
        "/api/tournament-results/import",
        files={"file": ("x.png", _png_bytes(), "image/png")},
    )
    assert r.status_code == 401


def test_backoffice_import_invalid_file_type_400():
    """File .pdf não suportado → 400."""
    client = TestClient(_make_test_app())
    r = client.post(
        "/api/tournament-results/import",
        files={"file": ("doc.pdf", b"%PDF-1.4 ...", "application/pdf")},
    )
    assert r.status_code == 400
    assert "nao suportado" in r.json()["detail"].lower()


def test_backoffice_import_mystery_unsupported():
    """TS com tournament_format='KO' (Mystery) → result='mystery_unsupported'."""
    with patch(
        "app.services.tournament_result_vision.extract_backoffice_payout_json",
        return_value=json.dumps(_VANILLA_VJ),
    ), patch(
        "app.services.tournament_resolver.resolve_tournament_number",
        return_value=("999888777", []),
    ), patch(
        "app.routers.tournament_results.query",
        side_effect=[
            # _lookup_ts_meta: Mystery
            [{"tournament_format": "KO", "tournament_pko_ratio": 0.33}],
        ],
    ), patch(
        "app.services.payouts_service.upsert_payout",
        return_value={"action": "inserted"},
    ) as m_upsert:
        client = TestClient(_make_test_app())
        r = client.post(
            "/api/tournament-results/import",
            files={"file": ("mys.png", _png_bytes(), "image/png")},
            data={"vision_throttle_seconds": "0"},
        )
    assert r.json()["results"][0]["result"] == "mystery_unsupported"
    m_upsert.assert_not_called()
