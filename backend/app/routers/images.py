"""
Router /api/images — galeria manual de imagens (Tech Debt #B9 fix).

Substitui Bucket 1 automático (attachments.py) que falhava sistematicamente
quando o utilizador joga múltiplos torneios em paralelo. Match temporal ±90s
sem cruzamento de tournament_name não tem fiabilidade suficiente — confirmado
em produção pt7 (1/3 attachments errado, 7-9 torneios distintos com hands
activas dentro de ±5min de cada imagem).

Esta API expõe:

    GET /api/images/gallery
        Lista entries `entry_type='image'` com paginação + filtros canal/data.
        Inclui flag `attached_to` (lista de hands a que cada imagem já está
        anexada) para a UI evitar duplicar.

    POST /api/hands/{hand_db_id}/images
        Body: {"entry_id": <int>}
        Cria row em hand_attachments com match_method='manual'.

    DELETE /api/hands/{hand_db_id}/images/{ha_id}
        Remove anexação manual.

A escolha de qual imagem anexar a qual mão é deferida ao utilizador (não
heurística automática). Tech Debt #B10 (futuro) adicionará Vision para
extrair tournament_name das imagens, permitindo filtragem na galeria.
"""
import base64
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from app.auth import require_auth
from app.db import query, get_conn

logger = logging.getLogger("images")
router = APIRouter(prefix="/api/images", tags=["images"])


# ── Models ──────────────────────────────────────────────────────────────────

class AttachImageRequest(BaseModel):
    entry_id: int = Field(..., description="ID da entry image em entries")


# ── GET /api/images/gallery ────────────────────────────────────────────────

@router.get("/gallery")
def gallery(
    channel: Optional[str] = Query(None, description="Filtrar por channel_name (ex: 'icm')"),
    date: Optional[str] = Query(None, description="Filtrar por data YYYY-MM-DD (UTC)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(40, ge=1, le=200),
    current_user=Depends(require_auth),
):
    """
    Lista entries `entry_type='image'` para a galeria manual.

    Cada item devolve:
        {
            "entry_id": int,
            "image_url": str,         # raw_text (ex: gyazo URL)
            "channel_id": str,
            "channel_name": str,
            "posted_at": ISO8601 datetime,
            "author": str,
            "discord_message_url": str,
            "attached_to": [          # hands a que esta imagem já está anexada
                {"hand_db_id": int, "hand_id": str, "ha_id": int}
            ]
        }

    Paginação simples: page * page_size.
    """
    where = ["e.source = 'discord'", "e.entry_type = 'image'"]
    params: list = []

    if channel:
        where.append("d.channel_name = %s")
        params.append(channel)
    if date:
        where.append("DATE(e.discord_posted_at AT TIME ZONE 'UTC') = %s::date")
        params.append(date)

    offset = (page - 1) * page_size

    where_clause = " AND ".join(where)
    sql = f"""
        SELECT
            e.id AS entry_id,
            e.raw_text AS image_url,
            e.discord_channel AS channel_id,
            d.channel_name,
            e.discord_posted_at AS posted_at,
            e.discord_author AS author,
            e.discord_message_url
        FROM entries e
        LEFT JOIN discord_sync_state d ON d.channel_id = e.discord_channel
        WHERE {where_clause}
        ORDER BY e.discord_posted_at DESC NULLS LAST, e.id DESC
        LIMIT %s OFFSET %s
    """
    params_with_paging = params + [page_size, offset]
    rows = query(sql, tuple(params_with_paging))

    count_sql = f"""
        SELECT COUNT(*) AS n
        FROM entries e
        LEFT JOIN discord_sync_state d ON d.channel_id = e.discord_channel
        WHERE {where_clause}
    """
    total_rows = query(count_sql, tuple(params))
    total = total_rows[0]["n"] if total_rows else 0

    items = []
    for r in rows:
        att_rows = query(
            """
            SELECT ha.id AS ha_id, ha.hand_db_id, h.hand_id
            FROM hand_attachments ha
            LEFT JOIN hands h ON h.id = ha.hand_db_id
            WHERE ha.entry_id = %s
            """,
            (r["entry_id"],),
        )
        items.append({
            "entry_id": r["entry_id"],
            "image_url": r["image_url"],
            "channel_id": r["channel_id"],
            "channel_name": r["channel_name"],
            "posted_at": r["posted_at"].isoformat() if r["posted_at"] else None,
            "author": r["author"],
            "discord_message_url": r["discord_message_url"],
            "attached_to": [
                {
                    "ha_id": a["ha_id"],
                    "hand_db_id": a["hand_db_id"],
                    "hand_id": a["hand_id"],
                }
                for a in att_rows
            ],
        })

    return {
        "ok": True,
        "page": page,
        "page_size": page_size,
        "total": total,
        "filters": {"channel": channel, "date": date},
        "items": items,
    }


# ── GET /api/images/{entry_id}/raw ─────────────────────────────────────────

@router.get("/{entry_id}/raw")
def serve_image_raw(entry_id: int):
    """
    Serve bytes da imagem de uma entry image (Tech Debt #B9 thumbnails fix).

    Endpoint público sem auth — justificação: entries entry_type='image'
    contêm URLs Gyazo já públicos partilhadas em Discord; servir os mesmos
    bytes via proxy não acrescenta exposição. Se no futuro houver uploads
    privados, mudar para auth-required.

    Lógica:
    1. Valida entry_type='image' (404 se não)
    2. Cache hit: serve raw_json.img_b64 directamente
    3. Cache miss: _fetch_entry_image_bytes (resolve gyazo.com/{id} →
       i.gyazo.com/{id}.png/.jpg/.gif via HEAD probe em attachments.py)
    4. Response com bytes + mime_type + Cache-Control 1h (browser cache
       evita re-fetch a cada render do thumbnail).
    """
    rows = query(
        "SELECT raw_text, entry_type, raw_json FROM entries WHERE id = %s",
        (entry_id,),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="entry not found")
    e = rows[0]
    if e["entry_type"] != "image":
        raise HTTPException(status_code=400, detail="entry_type != 'image'")

    raw_json = e.get("raw_json") or {}
    if isinstance(raw_json, dict) and raw_json.get("img_b64"):
        try:
            img_bytes = base64.b64decode(raw_json["img_b64"])
            mime = raw_json.get("mime_type", "image/png")
            return Response(
                content=img_bytes,
                media_type=mime,
                headers={"Cache-Control": "private, max-age=3600"},
            )
        except Exception as exc:
            logger.warning(f"img_b64 decode falhou para entry {entry_id}: {exc}")
            # Fall through para fetch live

    from app.routers.attachments import _fetch_entry_image_bytes
    data = _fetch_entry_image_bytes("image", e["raw_text"])
    if not data or not data.get("img_b64"):
        raise HTTPException(status_code=502, detail="failed to fetch image")
    img_bytes = base64.b64decode(data["img_b64"])
    return Response(
        content=img_bytes,
        media_type=data.get("mime_type", "image/png"),
        headers={"Cache-Control": "private, max-age=3600"},
    )


# ── GET /api/images/channels ────────────────────────────────────────────────

@router.get("/channels")
def channels(current_user=Depends(require_auth)):
    """
    Lista canais Discord com pelo menos 1 entry image (para popular dropdown
    do filtro de canal na UI da galeria).
    """
    rows = query(
        """
        SELECT
            d.channel_name,
            d.channel_id,
            COUNT(*) AS n_images
        FROM entries e
        JOIN discord_sync_state d ON d.channel_id = e.discord_channel
        WHERE e.source = 'discord' AND e.entry_type = 'image'
        GROUP BY d.channel_name, d.channel_id
        ORDER BY n_images DESC, d.channel_name ASC
        """,
    )
    return {
        "ok": True,
        "channels": [
            {
                "channel_id": r["channel_id"],
                "channel_name": r["channel_name"],
                "n_images": r["n_images"],
            }
            for r in rows
        ],
    }
