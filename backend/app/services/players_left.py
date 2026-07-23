"""#PLAYERS-LEFT — RÉGUA ÚNICA «quantos jogadores restam no torneio À HORA DESTA MÃO?»

Fonte única (#LEI-FIX-NA-CAUSA, 23 Jul). Antes viviam DUAS cópias divergentes:
`queue_export._resolve_players_left` (por mão) usava o print de lobby MAIS RECENTE
do torneio (`ORDER BY posted_at DESC`) — sem olhar à hora da mão — e
`hrc_queue.lookup_players_left` (lote) espelhava-a por torneio (o painel mostrava
o MESMO valor a todas as mãos do torneio). Caso real do defeito: GG-6139792066
(2 Jul 23:02) exportada para o HRC com «Remaining Players = 22» (print das 23:15,
13 min DEPOIS da mão) quando o print mais próximo (23:06) dizia 34.

Régua (ditada pelo Rui, 23 Jul):
  1. CAPTURA DA PRÓPRIA MÃO (`hands.context_table_ss_id` →
     `table_ss_processing_log.players_left`) — o número lido da foto do momento
     («My Rank: X / Y», o Y). fonte='table_ss'.
  2. Senão, print de lobby do torneio MAIS PRÓXIMO NO TEMPO do `played_at` da mão
     (nunca «o mais recente»). fonte='lobby'.
  3. Senão → (None, None) — VAZIO HONESTO (sem hora da mão também: sem hora não
     há «mais próximo», e adivinhar era o defeito antigo).

ZERO-LIDO = DESCONHECIDO: `players_left <= 0` nunca sai daqui como valor válido
(as queries filtram `> 0`; a Vision às vezes não lê e o 0 não é um torneio com
zero jogadores).

Consumidores (todos por camada fina, LEI 3): a exportação HRC (o `players_left`
do `meta.json` do pack → «Remaining Players» no solver) e os painéis HRC
(fila/enviadas/resolvidas, coluna «restantes»).
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("players_left")

SOURCE_CAPTURE = "table_ss"   # captura da própria mão
SOURCE_LOBBY = "lobby"        # print de lobby mais próximo NO TEMPO


def _naive(dt):
    """Wall-clock Lisboa: descarta tzinfo (o posted_at do lobby traz a marca +00
    enganadora — #LOBBY-LOG-POSTED-AT-TZ-MISLABEL — mas o relógio é o de Lisboa,
    como o played_at naive das mãos)."""
    try:
        return dt.replace(tzinfo=None) if getattr(dt, "tzinfo", None) else dt
    except Exception:
        return dt


def _valid(pl) -> Optional[int]:
    """Zero/negativo lido = DESCONHECIDO, nunca valor válido."""
    if isinstance(pl, int) and not isinstance(pl, bool) and pl > 0:
        return pl
    return None


def resolve_players_left_batch(rows: list) -> dict:
    """{hand_db_id: (players_left, fonte)} em LOTE — a RÉGUA ÚNICA (ver docstring
    do módulo). `rows` precisam de `id`, `context_table_ss_id`,
    `tournament_number`, `played_at`. Defensivo: falha de BD → (None, None)."""
    rows = [r for r in (rows or []) if isinstance(r, dict)]
    ctx_ids = list({
        r["context_table_ss_id"] for r in rows
        if isinstance(r.get("context_table_ss_id"), int)
    })
    tnums = list({str(r["tournament_number"]) for r in rows
                  if r.get("tournament_number")})
    cap_map: dict = {}
    prints_by_tn: dict = {}
    try:
        from app.db import query               # lazy: test-friendly (mock app.db.query)
        if ctx_ids:
            for pr in query(
                "SELECT id, players_left FROM table_ss_processing_log "
                "WHERE id = ANY(%s) AND players_left > 0",
                (ctx_ids,),
            ):
                cap_map[pr["id"]] = pr["players_left"]
        if tnums:
            for pr in query(
                """SELECT tournament_number, posted_at, players_left
                     FROM lobby_processing_log
                    WHERE tournament_number = ANY(%s)
                      AND result = 'success'
                      AND players_left > 0
                      AND posted_at IS NOT NULL""",
                (tnums,),
            ):
                prints_by_tn.setdefault(str(pr["tournament_number"]), []).append(
                    (_naive(pr["posted_at"]), pr["players_left"]))
    except Exception:
        logger.exception("resolve_players_left_batch falhou (devolve Nones)")

    out: dict = {}
    for r in rows:
        key = r.get("id")
        ctx = r.get("context_table_ss_id")
        val = _valid(cap_map.get(ctx)) if isinstance(ctx, int) else None
        if val is not None:
            out[key] = (val, SOURCE_CAPTURE)
            continue
        ps = prints_by_tn.get(str(r.get("tournament_number") or "")) or []
        pa = _naive(r.get("played_at"))
        if ps and pa is not None:
            try:
                closest = min(ps, key=lambda p: abs((p[0] - pa).total_seconds()))
                out[key] = (closest[1], SOURCE_LOBBY)   # a query só traz > 0
                continue
            except Exception:
                logger.exception("closest-print falhou (tn=%s)", r.get("tournament_number"))
        out[key] = (None, None)
    return out


def resolve_players_left_for_hand(hand) -> tuple:
    """Camada fina por mão sobre a régua única. Devolve (valor, fonte)."""
    if not isinstance(hand, dict):
        return (None, None)
    row = {
        "id": 0,
        "context_table_ss_id": hand.get("context_table_ss_id"),
        "tournament_number": hand.get("tournament_number"),
        "played_at": hand.get("played_at"),
    }
    return resolve_players_left_batch([row]).get(0, (None, None))
