"""Lógica core do pipeline lobby — extraída de discord_bot._handle_lobby_message
para reuso entre o handler real-time e o endpoint sync-recent.

Inclui:
- ensure_lobby_processing_log_schema() — chamada no main startup.
- process_lobby_message() — pipeline Vision → resolver → upsert + log.
- gather_candidates() — channel.history ∖ lobby_processing_log[success].
- run_sync() — orquestração do endpoint sync-recent.

Imports por módulo (não por símbolo) para que patches nos tests existentes
em app.services.lobby_vision.X / app.services.tournament_resolver.X /
app.services.payouts_service.X continuem a apanhar usos de dentro deste
módulo (o atributo é resolvido em runtime via módulo).
"""
from __future__ import annotations
import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from app.db import get_conn, query
from app.ingest_filters import is_pre_2026
from app.services import lobby_vision, tournament_resolver, payouts_service

logger = logging.getLogger("lobby_sync")

# Anthropic Tier 1 ~50 RPM ≈ 1.2s/req. Semáforo + sleep entre calls.
_anthropic_sem = asyncio.Semaphore(1)

_VALID_RESULTS = frozenset({
    "success", "vision_failed", "json_invalid", "site_undetected",
    "tm_not_found", "tm_ambiguous", "no_attachments", "pre_2026_skip",
    "upsert_error",
})


def ensure_lobby_processing_log_schema():
    """Idempotente. Chamada no lifespan."""
    sql = """
    CREATE TABLE IF NOT EXISTS lobby_processing_log (
        discord_message_id  TEXT PRIMARY KEY,
        channel_id          TEXT,
        attempted_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        attempt_count       INTEGER NOT NULL DEFAULT 1,
        result              TEXT NOT NULL,
        reason_detail       TEXT,
        site                TEXT,
        tournament_name     TEXT,
        tournament_number   TEXT,
        vision_json         JSONB,
        posted_at           TIMESTAMPTZ
    );
    """
    idx_attempted = (
        "CREATE INDEX IF NOT EXISTS idx_lobby_log_attempted_at "
        "ON lobby_processing_log (attempted_at DESC);"
    )
    idx_result = (
        "CREATE INDEX IF NOT EXISTS idx_lobby_log_result "
        "ON lobby_processing_log (result);"
    )
    # pt25: coluna players_left dedicada para o queue_export trigger do
    # prune-in-gap-downstream. Idempotente (IF NOT EXISTS). Permanece NULL
    # nos 18 rows historicos enquanto não houver backfill via Discord re-fetch.
    add_players_left = (
        "ALTER TABLE lobby_processing_log "
        "ADD COLUMN IF NOT EXISTS players_left INTEGER;"
    )
    # Index para o lookup BY tournament_number ORDER BY posted_at DESC
    idx_tn_posted = (
        "CREATE INDEX IF NOT EXISTS idx_lobby_log_tn_posted "
        "ON lobby_processing_log (tournament_number, posted_at DESC) "
        "WHERE tournament_number IS NOT NULL AND players_left IS NOT NULL;"
    )
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            cur.execute(idx_attempted)
            cur.execute(idx_result)
            cur.execute(add_players_left)
            cur.execute(idx_tn_posted)
        conn.commit()
    finally:
        conn.close()


def _upsert_lobby_log(
    *,
    message_id: str,
    channel_id: Optional[str],
    result: str,
    reason_detail: Optional[str] = None,
    site: Optional[str] = None,
    tournament_name: Optional[str] = None,
    tournament_number: Optional[str] = None,
    vision_json: Optional[dict] = None,
    posted_at: Optional[datetime] = None,
    players_left: Optional[int] = None,
) -> None:
    """UPSERT por message_id. Incrementa attempt_count em conflito.

    Falhas BD são engolidas com logger.error — não devem partir o handler
    real-time ou o batch sync se a tabela estiver indisponível. ValueError
    em `result` inválido continua a propagar (caller bug).

    pt25: `players_left` (int|None) — extraído pelo Vision da SS lobby
    mid-tournament; usado como trigger do prune-in-gap-downstream em
    queue_export. Coluna dedicada (não apenas dentro de vision_json) para
    query simples por `tournament_number`.
    """
    if result not in _VALID_RESULTS:
        raise ValueError(f"invalid result {result!r}")
    try:
        conn = get_conn()
    except Exception as e:
        logger.error(f"[lobby_log] get_conn failed: {type(e).__name__}: {e}")
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO lobby_processing_log (
                    discord_message_id, channel_id, attempted_at, attempt_count,
                    result, reason_detail, site, tournament_name,
                    tournament_number, vision_json, posted_at, players_left
                ) VALUES (
                    %s, %s, NOW(), 1, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (discord_message_id) DO UPDATE SET
                    attempted_at      = NOW(),
                    attempt_count     = lobby_processing_log.attempt_count + 1,
                    result            = EXCLUDED.result,
                    reason_detail     = EXCLUDED.reason_detail,
                    site              = COALESCE(EXCLUDED.site, lobby_processing_log.site),
                    tournament_name   = COALESCE(EXCLUDED.tournament_name, lobby_processing_log.tournament_name),
                    tournament_number = COALESCE(EXCLUDED.tournament_number, lobby_processing_log.tournament_number),
                    vision_json       = COALESCE(EXCLUDED.vision_json, lobby_processing_log.vision_json),
                    posted_at         = COALESCE(EXCLUDED.posted_at, lobby_processing_log.posted_at),
                    players_left      = COALESCE(EXCLUDED.players_left, lobby_processing_log.players_left)
                """,
                (
                    message_id, channel_id, result, reason_detail,
                    site, tournament_name, tournament_number,
                    json.dumps(vision_json) if vision_json else None,
                    posted_at, players_left,
                ),
            )
        conn.commit()
    except Exception as e:
        logger.error(f"[lobby_log] insert failed msg_id={message_id}: {type(e).__name__}: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _is_info_tab(vision_json) -> bool:
    """#LOBBY-INFO-NO-PAYOUT (regra 7 Jul) — o print com a aba **Info** aberta marca
    só o ARRANQUE da FT (fronteira + final_table_size) e NÃO é fonte de prémios (na
    aba Info os prémios saem a zeros/fichas). Onde isto for True, o pipeline resolve
    o tn e grava vision_json/players_left mas NUNCA escreve tournament_payouts."""
    return (isinstance(vision_json, dict)
            and (vision_json.get("open_tab") or "").strip() == "Info")


def _refresh_lobby_vision_json(
    message_id: str, vision_json: Optional[dict], players_left: Optional[int]
) -> int:
    """#LOBBY-FORCE-REVISION — refresh CIRÚRGICO: reescreve SÓ `vision_json`
    (+`players_left`) da row existente. NÃO toca result/tournament_number/posted_at/
    source nem `tournament_payouts` — o refresh de leitura (FT: open_tab/
    final_table_size) nunca degrada prémios já lidos. Devolve nº de rows afectadas
    (0 = não existia). Defensivo: falhas de BD engolidas (não partem o upload)."""
    try:
        conn = get_conn()
    except Exception as e:
        logger.error(f"[lobby_log] refresh get_conn failed: {type(e).__name__}: {e}")
        return 0
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE lobby_processing_log "
                "   SET vision_json = %s, "
                "       players_left = COALESCE(%s, players_left), "
                "       attempted_at = NOW(), "
                "       attempt_count = attempt_count + 1 "
                " WHERE discord_message_id = %s",
                (json.dumps(vision_json) if vision_json else None,
                 players_left, message_id),
            )
            n = cur.rowcount
        conn.commit()
        return n
    except Exception as e:
        logger.error(f"[lobby_log] refresh failed msg_id={message_id}: {type(e).__name__}: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


# ── Fallback ancorado no Hero (corrige sala mal lida pela Vision) ────────────
# pt — #LOBBY-SITE-MISCLASS-HERO-ANCHOR. Quando o resolver primário (site + nome +
# tempo) dá tm_not_found, este fallback usa as mãos do HERO à volta do captured_at
# para encontrar o torneio REAL — mesmo noutra sala (corrige WN lido como GG).

_HERO_ANCHOR_WINDOW_MIN = 45     # ±min à volta do captured_at p/ apanhar mãos do Hero
_HA_BUY_IN_TOL = 0.01            # buy_in TEM de bater (igualdade pelo total)
_HA_PRIZE_POOL_TOL = 0.02        # tolerância do sinal secundário prize_pool (±2%)


def _ha_float(v):
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _ha_prize_pool_match(cand_site, cand_tn, lobby_pp) -> bool:
    """Sinal SECUNDÁRIO (fraco): prize_pool do candidato (de tournament_summaries,
    GG-only) dentro de ±_HA_PRIZE_POOL_TOL do prize_pool do lobby. False quando não
    há TS (ex.: Winamax) ou inputs inválidos. Tolerância apertada porque o pool
    live (lobby) ≠ pool final (TS) na maioria dos casos."""
    if lobby_pp is None or lobby_pp <= 0 or not cand_tn:
        return False
    rows = query(
        "SELECT prize_pool FROM tournament_summaries WHERE site=%s AND tournament_number=%s",
        (cand_site, cand_tn),
    )
    pp = _ha_float(rows[0]["prize_pool"]) if rows else None
    if not pp or pp <= 0:
        return False
    return abs(pp - lobby_pp) / lobby_pp <= _HA_PRIZE_POOL_TOL


def _resolve_via_hero_anchor(vision_json: dict, anchor, primary_site,
                             window_min: int = _HERO_ANCHOR_WINDOW_MIN):
    """Fallback SITE-AGNÓSTICO para tm_not_found do resolver primário. Identifica o
    torneio real pelas mãos do HERO à volta do captured_at do lobby, podendo
    corrigir a SALA (ex.: Vision leu GG mas é Winamax).

    GUARD RAILS — sinal forte OBRIGATÓRIO (sem isto devolve None, NUNCA adivinha):
      (1) buy_in do lobby == buy_in do candidato, pelo TOTAL (±_HA_BUY_IN_TOL).
          O `hands.buy_in` é o total (ex.: WN 'HIGHROLLER (232€+18€)' → 250).
      (2) E confirmação: nome do lobby ⊆ nome do candidato (name_tokens_subset,
          o mesmo do resolver) OU prize_pool em tolerância (_ha_prize_pool_match).
      (3) E EXACTAMENTE 1 torneio (tn, site) distinto a passar (1)+(2) — unicidade.
          0 candidatos, empate (≥2), ou lobby sem buy_in → None (fica tm_not_found).

    Só lê a tabela `hands` (cobre todas as salas; as mãos são do Hero). Devolve
    (tournament_number, real_site) ou None. `real_site` pode diferir de
    `primary_site` (= correcção de sala)."""
    lobby_bi = _ha_float(vision_json.get("buy_in"))
    if not lobby_bi or lobby_bi <= 0 or anchor is None:
        return None
    a = anchor.replace(tzinfo=None) if getattr(anchor, "tzinfo", None) is not None else anchor
    lo, hi = a - timedelta(minutes=window_min), a + timedelta(minutes=window_min)
    rows = query(
        "SELECT DISTINCT site, tournament_number, stakes, buy_in FROM hands "
        "WHERE played_at >= %s AND played_at <= %s "
        "  AND tournament_number IS NOT NULL AND buy_in IS NOT NULL",
        (lo, hi),
    )
    lobby_name = vision_json.get("tournament_name") or ""
    lobby_pp = _ha_float(vision_json.get("prize_pool"))
    hits = set()
    for r in rows:
        cand_bi = _ha_float(r.get("buy_in"))
        if cand_bi is None or abs(cand_bi - lobby_bi) > _HA_BUY_IN_TOL:
            continue   # (1) buy_in TEM de bater pelo total — sinal forte
        name_ok = tournament_resolver.name_tokens_subset(lobby_name, r.get("stakes"))
        pp_ok = _ha_prize_pool_match(r.get("site"), r.get("tournament_number"), lobby_pp)
        if not (name_ok or pp_ok):
            continue   # (2) confirmação por nome OU prize_pool
        hits.add((r["tournament_number"], r["site"]))
    if len(hits) == 1:    # (3) unicidade — senão NÃO adivinha
        return next(iter(hits))
    return None


async def process_lobby_message(
    image_bytes: bytes,
    mime_type: str,
    message_id: str,
    channel_id: Optional[str],
    posted_at: datetime,
    caption_text: str = "",
    tn_override: Optional[str] = None,
    *,
    throttle_seconds: float = 0.0,
    source_prefix: str = "discord_lobby_vision",
    log_on_failure: bool = True,
    site_hint: Optional[str] = None,
    name_hint: Optional[str] = None,
    refresh_vision_only: bool = False,
) -> dict:
    """Vision → parse → resolver → upsert payouts → log.

    Devolve dict com todas as keys necessárias ao caller construir reply:
    result, reason_detail, site, tournament_name, tournament_number,
    vision_json, prizes_count, candidates (list), bounty_type,
    progressive_factor, action ("inserted"/"updated"/None).
    """
    base = {
        "result": "", "reason_detail": None,
        "site": None, "tournament_name": None, "tournament_number": None,
        "vision_json": None, "prizes_count": 0, "players_left": None,
        "candidates": [], "bounty_type": None, "progressive_factor": None,
        "action": None,
        # detalhe de import (página Lobbys): como resolveu + precedência + o que
        # ficou escrito em tournament_payouts.
        "resolver_tier": None, "existing_source": None, "payouts_blob": None,
    }

    if is_pre_2026(posted_at):
        base["result"] = "pre_2026_skip"
        return base

    vmeta: dict = {}   # pt73: apanha a causa REAL da falha da Vision
    async with _anthropic_sem:
        raw = await asyncio.to_thread(
            lobby_vision.extract_lobby_payout_json, image_bytes, mime_type, vmeta
        )
        if throttle_seconds > 0:
            await asyncio.sleep(throttle_seconds)

    if raw is None:
        real_err = vmeta.get("error") or "vision_returned_none"
        if log_on_failure:
            _upsert_lobby_log(
                message_id=message_id, channel_id=channel_id,
                result="vision_failed",
                reason_detail=real_err,
                posted_at=posted_at,
            )
        base["result"] = "vision_failed"
        base["reason_detail"] = real_err
        return base

    vj = lobby_vision.parse_and_validate_lobby_json(raw)
    if vj is None:
        if log_on_failure:
            _upsert_lobby_log(
                message_id=message_id, channel_id=channel_id,
                result="json_invalid",
                reason_detail=f"raw_head={raw[:200]!r}",
                posted_at=posted_at,
            )
        base["result"] = "json_invalid"
        base["reason_detail"] = f"raw_head={raw[:80]!r}"
        return base

    site = vj.get("site")
    name = vj.get("tournament_name")
    # pt63 — precedência do FILENAME (Intuitive Tables) sobre a Vision. Capturas
    # cortadas/desenquadradas fazem a Vision inventar site/nome (ex.: um lobby
    # Winamax lido como GGPoker 'TRICKNELLEN'); o nome do ficheiro do IT traz o
    # site fiável (e, no GG, o nome do torneio). Espelha o table-ss, que decide o
    # site pelo filename desde pt56/pt60. Discord e a 2ª via LOBBY_DIR não mandam
    # hints → comportamento inalterado. Log INFO quando discordam (auditoria).
    if site_hint:
        if site and site_hint != site:
            logger.info("[lobby] site do filename %r tem precedência sobre Vision %r (msg=%s)",
                        site_hint, site, message_id)
        site = site_hint
    if name_hint:
        if name and name_hint != name:
            logger.info("[lobby] nome do filename %r tem precedência sobre Vision %r (msg=%s)",
                        name_hint, name, message_id)
        name = name_hint
    # pt25: players_left lido do prompt extension; pode ser None se Vision
    # não encontrou o número (e.g. campo invisível em alguns layouts).
    # Coerce defensiva: aceita só int positivo, descarta None/0/strings.
    _pl_raw = vj.get("players_left")
    players_left: Optional[int] = (
        int(_pl_raw) if isinstance(_pl_raw, int) and _pl_raw > 0 else None
    )
    base["site"] = site
    base["tournament_name"] = name
    base["vision_json"] = vj
    base["prizes_count"] = len(vj.get("prizes") or {})
    base["players_left"] = players_left

    # #LOBBY-FORCE-REVISION (F2/4b.1) — force=true no upload fura o dedup e re-corre
    # a Vision; aqui só reescrevemos o vision_json (+players_left) da row existente
    # — captura open_tab/final_table_size do prompt novo — SEM resolver torneio nem
    # tocar tournament_payouts (D11/reconcile continuam donos dos payouts). Repõe a
    # leitura do FT num print já processado sem risco de degradar prémios já lidos.
    if refresh_vision_only:
        n = _refresh_lobby_vision_json(message_id, vj, players_left)
        base["result"] = "vision_refreshed" if n else "vision_refresh_no_row"
        return base

    # WPN é sala de 1ª classe desde pt60 (ALLOWED_SITES do table_ss, resolver,
    # fila HRC); o gate do lobby ficou sem ela. Incluída para a skin WPN do Rui
    # (YaPoker, site_hint=WPN do filename) deixar de cair em site_undetected.
    if site not in ("GGPoker", "PokerStars", "Winamax", "WPN"):
        if log_on_failure:
            _upsert_lobby_log(
                message_id=message_id, channel_id=channel_id,
                result="site_undetected",
                reason_detail=f"vision_site={site!r}",
                site=site, tournament_name=name,
                vision_json=vj, posted_at=posted_at,
                players_left=players_left,
            )
        base["result"] = "site_undetected"
        base["reason_detail"] = f"vision_site={site!r}"
        return base

    if tn_override:
        tn = tn_override
        candidates: list = []
        resolver_tier = "caption_override"  # bypass do resolver via caption #TM<n>
    else:
        tn, candidates, resolver_tier = await asyncio.to_thread(
            tournament_resolver.resolve_tournament_number,
            site, name, vj.get("start_time_iso"),
            posted_at_hint=posted_at,
            buy_in=vj.get("buy_in"),
            anchor_mode="prestart",  # pt41 Track A — lobby SS é pré-start
            return_tier=True,
        )
    base["resolver_tier"] = resolver_tier

    # Fallback ancorado no Hero — SÓ quando o primário dá tm_not_found (sem
    # candidatos; NUNCA em tm_ambiguous). Pode corrigir a sala. Ver
    # _resolve_via_hero_anchor (guard rails). Se resolver, tn fica não-None e cai
    # no caminho normal de precedência + upsert abaixo, com a sala corrigida.
    if tn is None and not candidates:
        fb = await asyncio.to_thread(_resolve_via_hero_anchor, vj, posted_at, site)
        if fb is not None:
            tn, real_site = fb
            resolver_tier = "hero_anchor_fallback"
            base["resolver_tier"] = resolver_tier
            if real_site != site:
                logger.info("[lobby] site corrigido %s->%s via hero-anchor "
                            "(tn=%s msg=%s)", site, real_site, tn, message_id)
                site = real_site
                base["site"] = site

    if tn is None:
        result = "tm_ambiguous" if candidates else "tm_not_found"
        reason = (f"n_candidates={len(candidates)}"
                  if candidates else f"start={vj.get('start_time_iso')!r}")
        _upsert_lobby_log(
            message_id=message_id, channel_id=channel_id,
            result=result, reason_detail=reason,
            site=site, tournament_name=name,
            vision_json=vj, posted_at=posted_at,
            players_left=players_left,
        )
        base["result"] = result
        base["reason_detail"] = reason
        base["candidates"] = candidates
        return base

    # #LOBBY-INFO-NO-PAYOUT (regra 7 Jul) — o print da aba Info marca só o ARRANQUE
    # da FT; NÃO é fonte de prémios. Resolve o tn e grava vision_json/players_left
    # (o motor FT lê daí), mas NUNCA escreve tournament_payouts: sendo sempre o
    # ÚLTIMO print do torneio, esmagaria por last-write-wins os payouts bons das
    # abas de prémios (a D11 só protege manual/backoffice). Mesma família do
    # refresh_vision_only, que também retorna antes do upsert_payout.
    if _is_info_tab(vj):
        _upsert_lobby_log(
            message_id=message_id, channel_id=channel_id,
            result="success",
            reason_detail="info_tab_no_payout",
            site=site, tournament_name=name, tournament_number=tn,
            vision_json=vj, posted_at=posted_at, players_left=players_left,
        )
        base["result"] = "success"
        base["reason_detail"] = "info_tab_no_payout"
        base["tournament_number"] = tn
        base["action"] = None            # não escreveu payout (só marca a FT)
        return base

    # #SYNC-RECENT-RESPECT-MANUAL (pt43) — guarda de precedência D11
    # (manual > backoffice_vision > discord_lobby_vision). O lobby é a fonte de
    # menor prioridade: NÃO sobrescreve manual/backoffice já presentes (dados
    # parciais do lobby = regressão de qualidade). Discord-sobre-Discord passa
    # (last-write-wins na mesma fonte). Espelha o skip_existing do backoffice
    # (routers/tournament_results.py:170-182). Ref: REGRAS_NEGOCIO.md §12.2.
    existing = await asyncio.to_thread(
        query,
        "SELECT source FROM tournament_payouts "
        "WHERE site = %s AND tournament_number = %s",
        (site, tn),
    )
    if existing:
        cur_src = existing[0].get("source") or ""
        if cur_src.startswith("manual:") or cur_src.startswith("backoffice_vision:"):
            _upsert_lobby_log(
                message_id=message_id, channel_id=channel_id,
                result="skipped_precedence",
                reason_detail=f"existing source={cur_src!r} >= discord_lobby_vision",
                site=site, tournament_name=name, tournament_number=tn,
                vision_json=vj, posted_at=posted_at,
                players_left=players_left,
            )
            base["result"] = "skipped_precedence"
            base["reason_detail"] = f"existing source={cur_src!r}"
            base["tournament_number"] = tn
            base["existing_source"] = cur_src
            return base

    blob = lobby_vision.build_hrc_payouts_blob(vj)
    try:
        upsert_res = await asyncio.to_thread(
            payouts_service.upsert_payout,
            site=site, tournament_number=tn,
            payouts_json=blob,
            source=f"{source_prefix}:{message_id}",
        )
        action = (upsert_res or {}).get("action")
    except Exception as e:
        _upsert_lobby_log(
            message_id=message_id, channel_id=channel_id,
            result="upsert_error",
            reason_detail=f"{type(e).__name__}: {e}",
            site=site, tournament_name=name, tournament_number=tn,
            vision_json=vj, posted_at=posted_at,
            players_left=players_left,
        )
        base["result"] = "upsert_error"
        base["reason_detail"] = str(e)
        base["tournament_number"] = tn
        return base

    # Extrai bounty_type + progressive_factor da structure[0] do blob.
    s0 = (blob.get("structures") or [{}])[0]
    bounty_type = s0.get("bountyType")
    progressive_factor = s0.get("progressiveFactor")

    _upsert_lobby_log(
        message_id=message_id, channel_id=channel_id,
        result="success",
        site=site, tournament_name=name, tournament_number=tn,
        vision_json=vj, posted_at=posted_at,
        players_left=players_left,
    )
    base["result"] = "success"
    base["tournament_number"] = tn
    base["bounty_type"] = bounty_type
    base["progressive_factor"] = progressive_factor
    base["action"] = action
    base["payouts_blob"] = blob   # o que ficou escrito em tournament_payouts
    # se o torneio já existia, regista a source anterior (overwrite same-source)
    base["existing_source"] = (existing[0].get("source") if existing else None)
    return base


async def gather_candidates(
    channel,
    since: datetime,
    until: datetime,
    max_messages: int,
    *,
    failure_types: Optional[list[str]] = None,
    retry_success: bool = False,
) -> list:
    """Visita channel.history(since..until) e devolve mensagens cuja
    discord_message_id (a) não está em lobby_processing_log, OU
    (b) está com result ∈ failure_types e retry_success=False, OU
    (c) está com result='success' mas retry_success=True.

    Limita a max_messages. Ignora mensagens do próprio bot e sem attachments.
    """
    existing_log = {
        row["discord_message_id"]: row["result"]
        for row in query(
            "SELECT discord_message_id, result FROM lobby_processing_log",
            (),
        )
    }
    filt = set(failure_types) if failure_types else None

    out = []
    bot_user = getattr(channel.guild, "me", None)
    bot_user_id = getattr(bot_user, "id", None) if bot_user else None

    # limit=None: o discord.py pagina internamente (lazy) toda a janela
    # after/before; o cap real é max_messages (break abaixo). Sem isto o default
    # 100 do discord.py cortava janelas largas em silêncio
    # (#LOBBY-SYNC-PAGINATION-LIMIT). NÃO toca os canais de estudo
    # (_sync_guild_history em discord_bot.py, que já passa limit=500).
    async for msg in channel.history(after=since, before=until, oldest_first=True, limit=None):
        if bot_user_id is not None and getattr(msg.author, "id", None) == bot_user_id:
            continue
        if not msg.attachments:
            continue
        mid = str(msg.id)
        prior = existing_log.get(mid)
        if prior == "success" and not retry_success:
            continue
        if prior and prior != "success":
            if filt is not None and prior not in filt:
                continue
        out.append(msg)
        if len(out) >= max_messages:
            break
    return out


async def run_sync(
    since: datetime,
    until: datetime,
    sites: Optional[list[str]] = None,
    max_messages: int = 200,
    dry_run: bool = False,
    throttle_seconds: float = 1.2,
    failure_types: Optional[list[str]] = None,
    retry_success: bool = False,
) -> dict:
    """Orquestra sync-recent. Retorna dict serializável."""
    from app.discord_bot import get_bot, LOBBY_CHANNEL_NAME

    bot = get_bot()
    if bot is None or not bot.is_ready():
        raise RuntimeError("bot_offline")

    channel = None
    for g in bot.guilds:
        for ch in g.text_channels:
            if ch.name.lower() == LOBBY_CHANNEL_NAME:
                channel = ch
                break
        if channel:
            break
    if channel is None:
        raise RuntimeError("lobby_channel_not_found")

    started = datetime.now(timezone.utc)
    candidates = await gather_candidates(
        channel, since, until, max_messages,
        failure_types=failure_types, retry_success=retry_success,
    )

    already_q = query(
        """SELECT COUNT(*) AS n
             FROM lobby_processing_log
            WHERE result = 'success'
              AND posted_at >= %s AND posted_at < %s""",
        (since, until),
    )
    already_success = already_q[0]["n"] if already_q else 0

    results = {"success_new": 0, "still_failed": 0, "errors": 0}
    successes: list[dict] = []
    failures: list[dict] = []
    rate_limit_pauses = 0

    for msg in candidates:
        if dry_run:
            failures.append({
                "message_id": str(msg.id), "reason": "dry_run",
                "site": None, "name": None,
                "posted_at": msg.created_at.isoformat(),
            })
            continue

        # Extrai bytes da 1ª attachment imagem.
        att = next(
            (a for a in msg.attachments
             if (getattr(a, "content_type", "") or "").startswith("image/")
                or (getattr(a, "filename", "") or "").lower().endswith(
                    (".png", ".jpg", ".jpeg", ".webp"))),
            None,
        )
        if att is None:
            _upsert_lobby_log(
                message_id=str(msg.id), channel_id=str(channel.id),
                result="no_attachments", posted_at=msg.created_at,
            )
            failures.append({
                "message_id": str(msg.id), "reason": "no_attachments",
                "site": None, "name": None,
                "posted_at": msg.created_at.isoformat(),
            })
            continue

        try:
            content_bytes = await att.read()
        except Exception as e:
            results["errors"] += 1
            failures.append({
                "message_id": str(msg.id),
                "reason": f"download_error:{type(e).__name__}",
                "site": None, "name": None,
                "posted_at": msg.created_at.isoformat(),
            })
            continue

        from app.services.image_utils import detect_image_mime
        from app.discord_bot import _extract_tn_from_caption
        mime = detect_image_mime(content_bytes)
        tn_override = _extract_tn_from_caption(msg.content or "")

        try:
            r = await process_lobby_message(
                content_bytes, mime, str(msg.id), str(channel.id),
                msg.created_at, msg.content or "", tn_override,
                throttle_seconds=throttle_seconds,
            )
        except Exception as e:
            results["errors"] += 1
            failures.append({
                "message_id": str(msg.id),
                "reason": f"process_error:{type(e).__name__}",
                "site": None, "name": None,
                "posted_at": msg.created_at.isoformat(),
            })
            continue

        if throttle_seconds > 0:
            rate_limit_pauses += 1

        if sites and r["site"] and r["site"] not in sites:
            continue

        if r["result"] == "success":
            results["success_new"] += 1
            successes.append({
                "message_id": str(msg.id),
                "site": r["site"],
                "tournament_number": r["tournament_number"],
                "tournament_name": r["tournament_name"],
            })
        else:
            results["still_failed"] += 1
            meta = query(
                """SELECT attempt_count, attempted_at
                     FROM lobby_processing_log
                    WHERE discord_message_id = %s""",
                (str(msg.id),),
            )
            m = dict(meta[0]) if meta else {}
            last_at = m.get("attempted_at")
            failures.append({
                "message_id": str(msg.id),
                "reason": r["result"],
                "reason_detail": r["reason_detail"],
                "site": r["site"],
                "name": r["tournament_name"],
                "posted_at": msg.created_at.isoformat(),
                "attempt_count": m.get("attempt_count"),
                "last_attempt_at": last_at.isoformat() if last_at else None,
            })

    finished = datetime.now(timezone.utc)
    return {
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "duration_seconds": (finished - started).total_seconds(),
        "dry_run": dry_run,
        "discord_history_count": len(candidates),
        "already_success_skipped_in_window": already_success,
        "candidates": len(candidates),
        "processed": len(candidates) if not dry_run else 0,
        "results": results,
        "successes": successes,
        "failures": failures,
        "rate_limit_pauses": rate_limit_pauses,
    }


# ── Reconcile: re-resolver lobbys pendentes contra o estado ACTUAL da BD ──────

def _coerce_players_left(vj: dict) -> Optional[int]:
    """Mesma coerção defensiva de process_lobby_message: só int positivo."""
    v = (vj or {}).get("players_left")
    return v if isinstance(v, int) and v > 0 else None


def reconcile_lobby_logs(message_ids: Optional[list] = None, dry_run: bool = False) -> dict:
    """Re-corre o resolver sobre lobbys que ficaram `tm_not_found`/`tm_ambiguous`,
    usando o `vision_json` JÁ GUARDADO no log — SEM chamar a Vision. Quando o
    torneio se tornou resolvível (chegaram mãos/TS), escreve o payout (respeitando
    a precedência D11 manual/backoffice) e actualiza o log para `success`
    (ou `skipped_precedence`).

    Idempotente: ao resolver, a row deixa de estar em ('tm_not_found','tm_ambiguous')
    e sai da selecção; `upsert_payout` é upsert; re-correr sem dados novos é no-op.
    Determinístico: só toca a BD quando o resolver passa a casar.

    Disparado fire-and-forget após os imports de HH/TS e on-demand via
    `POST /api/lobbys/reconcile`. `dry_run=True` → calcula e devolve o preview
    por torneio, sem escrever. `message_ids=[]` → curto-circuita.

    Devolve {scanned, resolved, written, skipped_precedence, still_unresolved,
    dry_run, items:[...]}.
    """
    if message_ids is not None and len(message_ids) == 0:
        return {"scanned": 0, "resolved": 0, "written": 0, "skipped_precedence": 0,
                "still_unresolved": 0, "dry_run": dry_run, "items": []}

    sql = (
        "SELECT discord_message_id, site, tournament_name, posted_at, "
        "       vision_json, result "
        "FROM lobby_processing_log "
        "WHERE result IN ('tm_not_found', 'tm_ambiguous') "
        "  AND vision_json IS NOT NULL"
    )
    if message_ids is not None:
        rows = query(sql + " AND discord_message_id = ANY(%s)", (list(message_ids),))
    else:
        rows = query(sql)

    scanned = resolved = written = skipped_prec = still = 0
    items: list[dict] = []

    for r in rows:
        scanned += 1
        vj = r.get("vision_json") or {}
        site = r.get("site") or vj.get("site")
        name = r.get("tournament_name") or vj.get("tournament_name")
        posted_at = r.get("posted_at")
        # anchor prestart, convenção pt51 (Lisboa naive) — descarta tz se vier
        anchor = posted_at
        if anchor is not None and getattr(anchor, "tzinfo", None) is not None:
            anchor = anchor.replace(tzinfo=None)

        tn, candidates, tier = tournament_resolver.resolve_tournament_number(
            site, name, vj.get("start_time_iso"),
            posted_at_hint=anchor, buy_in=vj.get("buy_in"),
            anchor_mode="prestart", return_tier=True,
        )

        item = {
            "message_id": r["discord_message_id"], "site": site,
            "tournament_name": name, "prev_result": r.get("result"),
            "resolved_tn": tn, "resolver_tier": tier, "n_candidates": len(candidates),
            # data da captura/post (Lisboa wall-clock) — deixa claro que um pendente
            # está à espera dos dados do PRÓPRIO dia, não avariado.
            "lobby_date": posted_at.date().isoformat() if posted_at else None,
        }

        # Fallback ancorado no Hero (mesmo guard rails do live path) — corrige a
        # sala mal lida sem re-Vision, usando o vision_json + as mãos do Hero já
        # em BD. Só quando tm_not_found (sem candidatos).
        if tn is None and not candidates:
            fb = _resolve_via_hero_anchor(vj, anchor, site)
            if fb is not None:
                tn, real_site = fb
                tier = "hero_anchor_fallback"
                item["resolved_tn"] = tn
                item["resolver_tier"] = tier
                if real_site != site:
                    item["site_corrected"] = f"{site}->{real_site}"
                    site = real_site   # sala corrigida na precedência + write + log

        if tn is None:
            still += 1
            item["action"] = "still_ambiguous" if candidates else "still_unresolved"
            items.append(item)
            continue

        resolved += 1
        # #LOBBY-INFO-NO-PAYOUT (regra 7 Jul) — print da aba Info nunca escreve
        # payout (só marca a FT). Resolve o tn e passa a success, sem tocar
        # tournament_payouts. Espelha o gate de process_lobby_message.
        if _is_info_tab(vj):
            item["action"] = "info_ft_marker"
            if not dry_run:
                _upsert_lobby_log(
                    message_id=r["discord_message_id"], channel_id=None,
                    result="success",
                    reason_detail="reconcile: info_tab_no_payout",
                    site=site, tournament_name=name, tournament_number=tn,
                    vision_json=vj, posted_at=posted_at,
                    players_left=_coerce_players_left(vj),
                )
            items.append(item)
            continue

        # Precedência D11: lobby é a fonte de menor prioridade — NÃO sobrescreve
        # manual:/backoffice_vision: já presentes. Espelha process_lobby_message.
        existing = query(
            "SELECT source FROM tournament_payouts WHERE site = %s AND tournament_number = %s",
            (site, tn),
        )
        cur_src = (existing[0].get("source") or "") if existing else ""

        if cur_src.startswith("manual:") or cur_src.startswith("backoffice_vision:"):
            skipped_prec += 1
            item["action"] = "skipped_precedence"
            item["existing_source"] = cur_src
            if not dry_run:
                _upsert_lobby_log(
                    message_id=r["discord_message_id"], channel_id=None,
                    result="skipped_precedence",
                    reason_detail=f"reconcile: existing source={cur_src!r} >= lobby",
                    site=site, tournament_name=name, tournament_number=tn,
                    vision_json=vj, posted_at=posted_at,
                    players_left=_coerce_players_left(vj),
                )
            items.append(item)
            continue

        item["action"] = "written"
        item["existing_source"] = cur_src or None
        if not dry_run:
            blob = lobby_vision.build_hrc_payouts_blob(vj)
            upsert_res = payouts_service.upsert_payout(
                site=site, tournament_number=tn, payouts_json=blob,
                source=f"reconcile_lobby_vision:{r['discord_message_id']}",
            )
            item["payout_action"] = (upsert_res or {}).get("action")
            _upsert_lobby_log(
                message_id=r["discord_message_id"], channel_id=None,
                result="success",
                site=site, tournament_name=name, tournament_number=tn,
                vision_json=vj, posted_at=posted_at,
                players_left=_coerce_players_left(vj),
            )
        written += 1
        items.append(item)

    logger.info(
        "[lobby_reconcile] scanned=%d resolved=%d written=%d skipped_precedence=%d "
        "still_unresolved=%d dry_run=%s",
        scanned, resolved, written, skipped_prec, still, dry_run,
    )
    return {
        "scanned": scanned, "resolved": resolved, "written": written,
        "skipped_precedence": skipped_prec, "still_unresolved": still,
        "dry_run": dry_run, "items": items,
    }
