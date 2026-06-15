"""Botão "Sincronizar histórico" — guarda do parâmetro `max_iters` em
process_replayer_links.

max_iters limita quantas PÁGINAS (LIMIT-blocks) a chamada processa antes de
devolver. O botão passa max_iters=1 para processar em VAGAS curtas (1 página por
chamada, o frontend repete até o preview dar 0) — sem isto, uma só chamada drena
todo o backlog de og:image sequenciais e recria o timeout de 300s.

Sem DB: o repo mocka `query`/`get_conn`. Com a página de SELECT sempre não-vazia,
o loop corre exactamente _PAGINATION_CAP = max(1, max_iters) vezes — por isso o
nº de chamadas a `query` (o SELECT da página) iguala max_iters.
"""
import asyncio
import base64
from unittest.mock import AsyncMock, MagicMock, patch

from app.routers import discord as disc


def _row():
    return {"id": 1, "raw_text": "https://gg.gl/x", "discord_posted_at": None, "raw_json": {}}


def _run_pages(max_iters):
    """Corre process_replayer_links com a página de SELECT sempre não-vazia e
    devolve quantas vezes o SELECT (query) foi chamado."""
    img = {"img_b64": base64.b64encode(b"x").decode(), "img_url": "http://img/x.png"}
    # pt73: a paginação só corre com a descoberta de imagem LIGADA (default é
    # desligada → early-return). Estes testes cobrem o path ligado.
    with patch.object(disc, "query", return_value=[_row()]) as mq, \
         patch("app.db.get_conn", return_value=MagicMock()), \
         patch("app.discord_bot.REPLAYER_IMAGE_DISCOVERY", True), \
         patch("app.discord_bot._extract_gg_replayer_image", return_value=img), \
         patch("app.routers.screenshot._run_vision_for_entry", new=AsyncMock()):
        asyncio.run(disc.process_replayer_links(
            confirm=True, limit=5, max_iters=max_iters, current_user={"id": 1},
        ))
        return mq.call_count


def test_max_iters_one_processes_single_page():
    # O botão "Sincronizar histórico" passa max_iters=1 → uma vaga = uma página.
    assert _run_pages(1) == 1


def test_max_iters_caps_page_count():
    # max_iters=N → no máximo N páginas (o cap legacy de drenagem é o default 50).
    assert _run_pages(3) == 3


def test_max_iters_clamped_to_at_least_one():
    # max_iters=0 nunca vira no-op: clamp para 1 (max(1, max_iters)).
    assert _run_pages(0) == 1


# ── pt73 — descoberta de imagem desligada por defeito (#REPLAYER-OGIMAGE-DEAD-SPA) ──

def test_discovery_disabled_skips_without_scanning():
    """Default (REPLAYER_IMAGE_DISCOVERY off): early-return, SEM varrer entries
    (não chama query) → não há fetch síncrono que prenda o event loop."""
    with patch.object(disc, "query") as mq, \
         patch("app.discord_bot.REPLAYER_IMAGE_DISCOVERY", False):
        out = asyncio.run(disc.process_replayer_links(
            confirm=True, limit=5, max_iters=50, current_user={"id": 1},
        ))
    assert out["status"] == "skipped"
    mq.assert_not_called()


def test_preview_reports_zero_pending_when_disabled():
    """Preview com descoberta desligada → pending_extract=0 (o botão não entra
    em loop) + backlog real visível em pending_extract_blocked."""
    rows = [
        {"id": 1, "raw_text": "u", "status": "new", "discord_channel": "c",
         "discord_author": "a", "discord_posted_at": None, "raw_json": {},
         "has_image": False, "vision_done": None},
    ]
    with patch.object(disc, "query", return_value=rows), \
         patch("app.discord_bot.REPLAYER_IMAGE_DISCOVERY", False):
        out = disc.process_replayer_links_preview(current_user={"id": 1})
    assert out["pending_extract"] == 0
    assert out["pending_extract_blocked"] == 1
    assert out["discovery_disabled"] is True
