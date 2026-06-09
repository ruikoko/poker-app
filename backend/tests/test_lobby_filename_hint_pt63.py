"""pt63 — precedência do FILENAME (Intuitive Tables) sobre a Vision no pipeline
de lobby. O appimport, ao rotear a pasta única `it`, deriva o site do nome do
ficheiro (e, no GG, o nome do torneio) e manda-os como `site_hint`/`name_hint` ao
`POST /api/lobbys/upload`. Rede de segurança p/ capturas cortadas (Vision inventa
site/nome). Sem os campos (Discord, LOBBY_DIR) → comportamento de sempre."""
import asyncio
from datetime import datetime
from unittest.mock import patch, AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

PNG = b"\x89PNG\r\n\x1a\nx"
POSTED = datetime(2026, 6, 8, 23, 14, 49)   # Lisboa naive, 2026 (não pre_2026_skip)


def _run(**kwargs):
    """Corre process_lobby_message com a Vision/resolver/hero-anchor mockados.
    Devolve (res, resolver_mock, log_mock)."""
    from app.services import lobby_sync
    with patch.object(lobby_sync, "_upsert_lobby_log") as mlog, \
         patch.object(lobby_sync, "_resolve_via_hero_anchor", return_value=None), \
         patch.object(lobby_sync.lobby_vision, "extract_lobby_payout_json",
                      return_value="{}"), \
         patch.object(lobby_sync.lobby_vision, "parse_and_validate_lobby_json",
                      return_value=kwargs.pop("vj")), \
         patch.object(lobby_sync.tournament_resolver, "resolve_tournament_number",
                      return_value=(None, [], "no_match")) as mres:
        res = asyncio.run(lobby_sync.process_lobby_message(
            PNG, "image/png", message_id="h", channel_id=None,
            posted_at=POSTED, **kwargs))
    return res, mres, mlog


# ── site_hint: precedência sobre a Vision ─────────────────────────────────────

def test_winamax_filename_beats_vision_ggpoker():
    # Lobby Winamax cortado → Vision diz GGPoker 'TRICKNELLEN'. O filename (Winamax)
    # tem precedência: o resolver e o log ficam Winamax.
    vj = {"site": "GGPoker", "tournament_name": "TRICKNELLEN", "players_left": 34}
    res, mres, mlog = _run(vj=vj, site_hint="Winamax", name_hint=None)
    assert res["site"] == "Winamax"
    assert res["result"] == "tm_not_found"
    assert mres.call_args.args[0] == "Winamax"          # resolver recebeu Winamax
    assert mlog.call_args.kwargs["site"] == "Winamax"   # log gravou Winamax


def test_site_hint_rescues_vision_undetected():
    # Vision não detecta site (None) → sem hint daria site_undetected. Com o hint do
    # filename, passa o gate e segue para o resolver.
    vj = {"site": None, "tournament_name": None, "players_left": 12}
    res, mres, _ = _run(vj=vj, site_hint="GGPoker", name_hint=None)
    assert res["site"] == "GGPoker"
    assert res["result"] == "tm_not_found"              # não site_undetected
    assert mres.called


# ── name_hint: nome do filename entra no resolver (GG) ────────────────────────

def test_name_hint_drives_resolver():
    vj = {"site": "GGPoker", "tournament_name": "nome lido errado", "players_left": 22}
    res, mres, _ = _run(vj=vj, site_hint="GGPoker",
                        name_hint="Bounty Hunters Hyper Special $108")
    assert mres.call_args.args[1] == "Bounty Hunters Hyper Special $108"
    assert res["tournament_name"] == "Bounty Hunters Hyper Special $108"


# ── sem hints: comportamento inalterado ───────────────────────────────────────

def test_no_hints_uses_vision_values():
    vj = {"site": "GGPoker", "tournament_name": "Daily Hyper $50", "players_left": 68}
    res, mres, _ = _run(vj=vj)   # sem site_hint/name_hint
    assert res["site"] == "GGPoker"
    assert res["tournament_name"] == "Daily Hyper $50"
    assert mres.call_args.args[0] == "GGPoker"
    assert mres.call_args.args[1] == "Daily Hyper $50"


# ── endpoint: plumbing dos hints + compatibilidade ────────────────────────────

def _app():
    from app.routers.lobbys import router
    from app.auth import require_auth
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[require_auth] = lambda: {"id": 1, "email": "t@t"}
    return app


@patch("app.routers.lobbys.process_lobby_message", new_callable=AsyncMock)
@patch("app.routers.lobbys.query", return_value=[])
def test_endpoint_forwards_hints(mq, mproc):
    mproc.return_value = {"result": "tm_not_found", "site": "Winamax",
                          "tournament_name": "HIGHROLLER", "tournament_number": None,
                          "action": None, "reason_detail": "x"}
    r = TestClient(_app()).post(
        "/api/lobbys/upload",
        files={"file": ("Winamax.exe-Winamax-20260608223716-50.png", PNG, "image/png")},
        data={"captured_at": "2026-06-08T22:37:16",
              "site_hint": "Winamax", "name_hint": ""})
    assert r.status_code == 200, r.text
    kw = mproc.call_args.kwargs
    assert kw["site_hint"] == "Winamax"
    assert kw["name_hint"] is None      # "" → None (não dispara precedência)


@patch("app.routers.lobbys.process_lobby_message", new_callable=AsyncMock)
@patch("app.routers.lobbys.query", return_value=[])
def test_endpoint_without_hints_passes_none(mq, mproc):
    mproc.return_value = {"result": "success", "site": "GGPoker",
                          "tournament_name": "Daily Hyper $50",
                          "tournament_number": "287210981", "action": "inserted",
                          "reason_detail": None}
    r = TestClient(_app()).post(
        "/api/lobbys/upload",
        files={"file": ("x.png", PNG, "image/png")},
        data={"captured_at": "2026-06-04T15:30:12"})
    assert r.status_code == 200, r.text
    kw = mproc.call_args.kwargs
    assert kw["site_hint"] is None and kw["name_hint"] is None
