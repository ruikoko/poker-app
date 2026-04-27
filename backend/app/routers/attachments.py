"""
Router /api/attachments — Bucket 1.

Gere a tabela `hand_attachments`: cruza entries `image` Discord com mãos
existentes via janela temporal ±90s (regra de produto em CLAUDE.md secção
"Imagens de contexto Discord").

Match primário: outra entry Discord no mesmo canal ±90s que tenha hand
associada (via hands.entry_id). Match fallback: hands com origin IN
('hm3','hh_import') ±90s em qualquer canal (cobre o caso "mão veio via
HM3 sem entry Discord da mão").

Tiebreaker: mais próxima temporalmente; empate exacto → mão mais antiga.

Filtro permanente: só hands de 2026 (played_at >= '2026-01-01').

Endpoints:
- GET  /api/attachments/preview         — dry-run, sem efeitos
- POST /api/attachments/match           — sem confirm comporta-se como preview
- POST /api/attachments/match?confirm=true&limit=N — aplica matches

Helper `_fetch_entry_image_bytes` reintroduzido aqui (saiu de discord.py
no revert ab1953e). Cache img_b64 SÓ para URLs Gyazo (link rot real);
Discord CDN é estável → guarda só URL.

A função `run_match_worker(limit)` é o ponto de entrada usado pelos
triggers retroactivos (Fase IV) — chamada via asyncio.create_task em
sync_and_process / import_hm3.
"""
import base64
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from app.auth import require_auth
from app.db import query, get_conn

logger = logging.getLogger("attachments")
router = APIRouter(prefix="/api/attachments", tags=["attachments"])


# ── Helper: fetch image bytes ───────────────────────────────────────────────

def _fetch_entry_image_bytes(entry_type: str, raw_text: str | None) -> dict | None:
    """
    Obtém bytes de imagem de uma entry Discord.

    - 'replayer_link': URL HTML (gg.gl / pokercraft.com/embedded). Faz fetch
      HTML + extrai og:image PNG via _extract_gg_replayer_image.
    - 'image': URL directo (gyazo, cdn.discordapp.com, etc.). Download directo.

    Retorna {img_url, img_b64, mime_type} ou None em qualquer falha.

    Nota: este helper foi originalmente introduzido em bf0d9de (`discord.py`)
    e revertido em ab1953e. Reintroduzido aqui como parte da Fase III do
    Bucket 1 (anexos imagem ↔ mão), agora desacoplado do fluxo Vision.
    """
    url = (raw_text or "").strip()
    if not url.startswith("http"):
        return None

    if entry_type == "replayer_link":
        from app.discord_bot import _extract_gg_replayer_image
        data = _extract_gg_replayer_image(url)
        if not data:
            return None
        return {
            "img_url": data.get("img_url"),
            "img_b64": data.get("img_b64"),
            "mime_type": "image/png",
        }

    if entry_type == "image":
        try:
            import httpx
        except ImportError:
            logger.error("httpx não instalado — image fetch falhou")
            return None
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "image/*,*/*;q=0.8",
            }
            with httpx.Client(follow_redirects=True, timeout=15, headers=headers) as client:
                fetch_url = url
                # Gyazo: gyazo.com/<id> (HTML) → i.gyazo.com/<id>.<ext> (binário).
                # Imagens podem ser PNG, JPG ou GIF. Tenta .png primeiro (mais
                # comum em screenshots de poker), .jpg e .gif depois. Se nenhum
                # HEAD acertar, return None — não cai para o URL HTML (Tech Debt
                # #2: silent fallback era a causa de img_b64=NULL para JPEGs).
                if "gyazo.com/" in fetch_url and "i.gyazo.com" not in fetch_url and not any(
                    fetch_url.lower().endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp")
                ):
                    gid = fetch_url.rstrip("/").split("/")[-1]
                    resolved = None
                    for ext in (".png", ".jpg", ".gif"):
                        candidate = f"https://i.gyazo.com/{gid}{ext}"
                        try:
                            head = client.head(candidate)
                            if head.status_code == 200:
                                resolved = candidate
                                break
                        except Exception:
                            continue
                    if resolved:
                        fetch_url = resolved
                    else:
                        logger.warning(
                            f"gyazo: HEAD a .png/.jpg/.gif todas falharam "
                            f"para gid={gid} (URL original: {url})"
                        )
                        return None
                resp = client.get(fetch_url)
                if resp.status_code != 200:
                    logger.warning(
                        f"image fetch failed: {resp.status_code} for {fetch_url}"
                    )
                    return None
                ct = resp.headers.get("content-type", "image/png").split(";")[0].strip() or "image/png"
                if not ct.startswith("image/"):
                    logger.warning(f"image fetch: unexpected content-type {ct} for {fetch_url}")
                    return None
                img_b64 = base64.b64encode(resp.content).decode("ascii")
                return {
                    "img_url": fetch_url,
                    "img_b64": img_b64,
                    "mime_type": ct,
                }
        except Exception as e:
            logger.error(f"image fetch error for {url}: {e}")
            return None

    logger.warning(f"_fetch_entry_image_bytes: entry_type não suportado: {entry_type}")
    return None


def _is_gyazo(url: str | None) -> bool:
    return bool(url) and "gyazo.com" in url.lower()


# ── Match logic ─────────────────────────────────────────────────────────────

def _pending_image_entries(limit: int) -> list[dict]:
    """
    Universo de entries `image` Discord ainda por anexar:
    - source='discord' AND entry_type='image'
    - sem row em hand_attachments com aquele entry_id (NOT IN)

    Ordem: discord_posted_at ASC (processa mais antigas primeiro).

    NOTA: não filtramos por entries.status. O CHECK constraint
    entries_status_check não inclui 'attached' (descoberto a 2026-04-26
    durante backfill Fase VI), pelo que entries.status nunca toma esse
    valor. O NOT IN em hand_attachments já filtra entries processadas.
    """
    return query(
        """
        SELECT
            id,
            raw_text,
            discord_channel,
            discord_posted_at,
            entry_type
        FROM entries
        WHERE source = 'discord'
          AND entry_type = 'image'
          AND id NOT IN (
              SELECT entry_id FROM hand_attachments WHERE entry_id IS NOT NULL
          )
          AND discord_posted_at IS NOT NULL
        ORDER BY discord_posted_at ASC
        LIMIT %s
        """,
        (limit,),
    )


def _find_primary_match(img_entry: dict) -> dict | None:
    """
    Match primário: outra entry Discord no mesmo canal cuja hand associada
    fica dentro de ±90s (entre img.discord_posted_at e e2.discord_posted_at,
    sibling delta — define a janela de match conforme SPEC §4).

    O delta_seconds REPORTADO é image-to-played_at (|h.played_at -
    img.discord_posted_at|), conforme SPEC §3 — uniforme com fallback path.

    Tiebreaker: delta_s ASC (image-to-played_at), played_at ASC, hand id ASC.

    Filtro: hands.played_at >= '2026-01-01'.
    """
    rows = query(
        """
        SELECT
            h.id AS hand_db_id,
            h.hand_id AS hand_id_text,
            h.played_at,
            e2.id AS sibling_entry_id,
            e2.discord_posted_at AS sibling_posted_at,
            ABS(EXTRACT(EPOCH FROM (h.played_at - %s::timestamptz)))::int AS delta_s
        FROM entries e2
        JOIN hands h ON h.entry_id = e2.id
        WHERE e2.id <> %s
          AND e2.source = 'discord'
          AND e2.discord_channel = %s
          AND e2.discord_posted_at IS NOT NULL
          AND ABS(EXTRACT(EPOCH FROM (e2.discord_posted_at - %s::timestamptz))) <= 90
          AND h.played_at >= '2026-01-01'
        ORDER BY delta_s ASC, h.played_at ASC, h.id ASC
        LIMIT 1
        """,
        (
            img_entry["discord_posted_at"],
            img_entry["id"],
            img_entry["discord_channel"],
            img_entry["discord_posted_at"],
        ),
    )
    return rows[0] if rows else None


def _find_fallback_match(img_entry: dict) -> dict | None:
    """
    Match fallback: hands com origin IN ('hm3','hh_import') e played_at
    dentro de ±90s do discord_posted_at da imagem. Em qualquer canal — cobre
    mãos que chegaram via HM3 sem entry Discord da mão.

    Filtro: hands.played_at >= '2026-01-01'.
    """
    rows = query(
        """
        SELECT
            h.id AS hand_db_id,
            h.hand_id AS hand_id_text,
            h.played_at,
            ABS(EXTRACT(EPOCH FROM (h.played_at - %s::timestamptz)))::int AS delta_s
        FROM hands h
        WHERE h.origin IN ('hm3', 'hh_import')
          AND h.played_at IS NOT NULL
          AND h.played_at >= '2026-01-01'
          AND ABS(EXTRACT(EPOCH FROM (h.played_at - %s::timestamptz))) <= 90
        ORDER BY delta_s ASC, h.played_at ASC, h.id ASC
        LIMIT 1
        """,
        (img_entry["discord_posted_at"], img_entry["discord_posted_at"]),
    )
    return rows[0] if rows else None


def _compute_match_candidates(limit: int) -> list[dict]:
    """
    Sem efeitos. Para cada entry image pendente, tenta match primário; se
    falhar, fallback. Devolve lista de candidates a ser inseridos.

    Cada item:
        {
          "entry_id": int,
          "url": str,
          "channel": str,
          "posted_at": isoformat,
          "match": {
              "hand_db_id": int,
              "hand_id_text": str,
              "played_at": isoformat,
              "delta_seconds": int,
              "match_method": 'discord_channel_temporal' | 'hm3_temporal_fallback'
          } | None,
          "reason": str (só se match=None)
        }
    """
    out = []
    for e in _pending_image_entries(limit):
        item = {
            "entry_id": e["id"],
            "url": e["raw_text"],
            "channel": e["discord_channel"],
            "posted_at": e["discord_posted_at"].isoformat() if e["discord_posted_at"] else None,
            "match": None,
        }

        primary = _find_primary_match(e)
        if primary:
            item["match"] = {
                "hand_db_id": primary["hand_db_id"],
                "hand_id_text": primary["hand_id_text"],
                "played_at": primary["played_at"].isoformat() if primary["played_at"] else None,
                "delta_seconds": int(primary["delta_s"]),
                "match_method": "discord_channel_temporal",
            }
            out.append(item)
            continue

        fallback = _find_fallback_match(e)
        if fallback:
            item["match"] = {
                "hand_db_id": fallback["hand_db_id"],
                "hand_id_text": fallback["hand_id_text"],
                "played_at": fallback["played_at"].isoformat() if fallback["played_at"] else None,
                "delta_seconds": int(fallback["delta_s"]),
                "match_method": "hm3_temporal_fallback",
            }
            out.append(item)
            continue

        item["reason"] = "no candidate ±90s in same channel or HM3/hh_import"
        out.append(item)

    return out


def _apply_match(candidate: dict) -> dict:
    """
    Aplica um single candidate: fetch bytes (só se Gyazo, decisão Q2),
    INSERT em hand_attachments, UPDATE entry status='attached'.

    Tudo na mesma conexão; commit no fim. ON CONFLICT DO NOTHING via UNIQUE
    parcial não é necessário porque o filtro `_pending_image_entries` já
    exclui entries com row prévia — ainda assim, INSERT faz ON CONFLICT
    DO NOTHING defensivo (race conditions entre workers concorrentes).
    """
    entry_id = candidate["entry_id"]
    match = candidate["match"]
    if not match:
        return {"entry_id": entry_id, "status": "skip", "reason": candidate.get("reason")}

    url = candidate["url"]
    img_b64 = None
    mime_type = None

    # Q2 SPEC: cache bytes só para Gyazo (link rot). Discord CDN é estável.
    if _is_gyazo(url):
        try:
            data = _fetch_entry_image_bytes("image", url)
            if data:
                img_b64 = data.get("img_b64")
                mime_type = data.get("mime_type")
        except Exception as e:
            logger.warning(f"gyazo fetch falhou para entry {entry_id}: {e}")
            # não bloqueia o match — guarda só URL

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO hand_attachments (
                    hand_db_id, entry_id,
                    image_url, cached_url, img_b64, mime_type,
                    posted_at, channel_name,
                    match_method, delta_seconds
                )
                VALUES (
                    %s, %s,
                    %s, NULL, %s, %s,
                    %s::timestamptz, %s,
                    %s, %s
                )
                ON CONFLICT (hand_db_id, entry_id) WHERE entry_id IS NOT NULL DO NOTHING
                RETURNING id
                """,
                (
                    match["hand_db_id"], entry_id,
                    url, img_b64, mime_type,
                    candidate["posted_at"], candidate["channel"],
                    match["match_method"], match["delta_seconds"],
                ),
            )
            inserted = cur.fetchone()
            if inserted is None:
                conn.commit()
                return {"entry_id": entry_id, "status": "skip", "reason": "row já existia (race)"}

            # NOTA: não escrevemos entries.status = 'attached'. O CHECK constraint
            # entries_status_check (new/processed/partial/failed/archived/resolved)
            # não inclui 'attached' — descoberto durante backfill Fase VI a 2026-04-26.
            # O estado "anexada" é representado apenas pela existência de row
            # em hand_attachments. O filtro de _pending_image_entries usa NOT IN
            # nessa tabela, suficiente para excluir entries já processadas.
        conn.commit()
        return {
            "entry_id": entry_id,
            "status": "ok",
            "attachment_id": inserted["id"],
            "hand_db_id": match["hand_db_id"],
            "hand_id_text": match["hand_id_text"],
            "match_method": match["match_method"],
            "delta_seconds": match["delta_seconds"],
            "img_b64_cached": img_b64 is not None,
        }
    except Exception as e:
        conn.rollback()
        logger.error(f"_apply_match falhou para entry {entry_id}: {e}")
        return {"entry_id": entry_id, "status": "error", "reason": str(e)}
    finally:
        conn.close()


def run_match_worker(limit: int = 100) -> dict:
    """
    Ponto de entrada usado pelos triggers retroactivos (Fase IV) e pelo
    endpoint POST /match. Calcula candidates + aplica os com match.
    """
    candidates = _compute_match_candidates(limit)
    results = [_apply_match(c) for c in candidates]
    return {
        "total_seen": len(candidates),
        "applied": sum(1 for r in results if r["status"] == "ok"),
        "skipped": sum(1 for r in results if r["status"] == "skip"),
        "errors": sum(1 for r in results if r["status"] == "error"),
        "results": results,
    }


# ── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/preview")
def preview(
    limit: int = Query(100, ge=1, le=500),
    current_user=Depends(require_auth),
):
    """
    DRY-RUN. Calcula matches que SERIAM inseridos. Não escreve nada.
    """
    candidates = _compute_match_candidates(limit)
    with_match = [c for c in candidates if c["match"]]
    without_match = [c for c in candidates if not c["match"]]
    by_method = {}
    for c in with_match:
        m = c["match"]["match_method"]
        by_method[m] = by_method.get(m, 0) + 1
    return {
        "ok": True,
        "total_pending": len(candidates),
        "with_match": len(with_match),
        "without_match": len(without_match),
        "by_method": by_method,
        "candidates": candidates,
    }


@router.post("/match")
def match_endpoint(
    confirm: bool = False,
    limit: int = Query(100, ge=1, le=500),
    current_user=Depends(require_auth),
):
    """
    Sem ?confirm=true comporta-se como /preview (não escreve).
    Com ?confirm=true aplica os matches: INSERT em hand_attachments + UPDATE
    entries.status='attached'.
    """
    if not confirm:
        return preview(limit=limit, current_user=current_user)
    return run_match_worker(limit=limit)
