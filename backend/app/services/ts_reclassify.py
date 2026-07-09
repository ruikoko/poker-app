"""#TS-LATE-NO-FORMAT-RECALC — gatilho pós-import de TS GG (GG-only).

Fecha a fresta do cenário raro HH-primeiro → TS-depois: quando um TS GG entra
DEPOIS da HH, as mãos desse torneio já em BD foram classificadas pelo NOME no
import da HH (`parsers/gg_hands.py:369 detect_tournament_format(name)`, sem
consultar o TS) e as guardas de coroa (que dependem do `ts.buy_in_bounty`) não
dispararam no enrich (não havia TS). Este gatilho, fire-and-forget e idempotente:

  1. RECLASSIFICA o formato das mãos GG do `tournament_number` já em BD, agora com
     o sinal do TS (`has_player_bounty` = buy_in_bounty > 0) — o TS pode corrigir a
     classificação name-only. NÃO faz downgrade de KO específico (Mystery/Super KO
     → PKO) e NÃO toca não-GG.
  2. RE-CORRE o funil das coroas (`scrub_and_persist`, só-tagadas, DB-aware e
     idempotente) sobre essas mãos → as guardas vanilla/vivo-$0 disparam agora que
     o TS existe, exactamente como se o TS lá estivesse desde o início.
  3. JUSANTE: se a reclassificação mudou o formato de mãos com solve HRC já feito,
     LISTA-as (não re-solve — mesmo espírito da F6 dormente da FT).

Só-GG (única sala com TS). WN/PS/WPN deduzem o formato pelo nome e não são tocadas.
TS-primeiro (ritual normal): quando o TS entra, ainda não há mãos desse tn → no-op
(reclassified=0, rescrubbed=0) → o fluxo normal fica byte-idêntico.
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("ts_reclassify")

# KO específico não deve ser rebaixado a PKO genérico por uma reclassificação por bounty.
_KO_SPECIFIC = {"Mystery KO", "Super KO"}


def _reclassified_format(old_fmt, tournament_name, has_bounty: bool):
    """PURO. Novo formato para uma mão GG à luz do sinal do TS (`has_bounty`), ou None se
    NÃO deve mudar. Regras:
    - re-corre `detect_tournament_format(name, site='ggpoker', has_player_bounty=has_bounty)`
      (nome ganha; sem keyword, o bounty do TS decide) — o TS corrige a classificação
      name-only do import da HH;
    - None se o resultado é igual ao actual (idempotente, sem escrita);
    - None se rebaixaria KO específico (Mystery/Super KO → PKO) — não perder especificidade."""
    from app.utils.tournament_format import detect_tournament_format
    new_fmt = detect_tournament_format(
        tournament_name, site="ggpoker", has_player_bounty=has_bounty)
    if new_fmt == old_fmt:
        return None
    if old_fmt in _KO_SPECIFIC and new_fmt == "PKO":
        return None
    return new_fmt


def _downstream_hrc(hand_ids: list[str]) -> list[str]:
    """hand_ids (dos que mudaram de formato) com solve HRC 'done' → listar (não re-solver)."""
    if not hand_ids:
        return []
    from app.db import query
    rows = query(
        "SELECT h.hand_id FROM hrc_jobs j JOIN hands h ON h.id = j.hand_db_id "
        " WHERE h.hand_id = ANY(%s) AND j.status = 'done'",
        (hand_ids,),
    )
    return [r["hand_id"] for r in rows]


def reclassify_and_rescrub_for_tn(tournament_number: str) -> dict:
    """Aplica (1) reclassificação de formato + (2) re-scrub de coroas às mãos GG do tn.
    Devolve auditoria {tn, reclassified, rescrubbed, changes, hrc_stale}. Idempotente."""
    from app.db import query, get_conn
    from app.services.eliminated_bounty import scrub_and_persist

    ts = query(
        "SELECT buy_in_bounty FROM tournament_summaries "
        "WHERE site = 'GGPoker' AND tournament_number = %s",
        (str(tournament_number),),
    )
    if not ts:
        return {"tn": tournament_number, "reclassified": 0, "rescrubbed": 0,
                "changes": [], "hrc_stale": []}
    bib = ts[0]["buy_in_bounty"]
    has_bounty = bib is not None and float(bib) > 0

    hands = query(
        "SELECT id, hand_id, tournament_name, tournament_format "
        "  FROM hands WHERE site = 'GGPoker' AND tournament_number = %s",
        (str(tournament_number),),
    )
    if not hands:
        return {"tn": tournament_number, "reclassified": 0, "rescrubbed": 0,
                "changes": [], "hrc_stale": []}

    # (1) Reclassificação de formato (o TS corrige a classificação name-only da HH).
    changes = []
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for h in hands:
                new_fmt = _reclassified_format(h["tournament_format"], h["tournament_name"], has_bounty)
                if new_fmt is None:
                    continue
                cur.execute("UPDATE hands SET tournament_format = %s WHERE id = %s",
                            (new_fmt, h["id"]))
                changes.append({"hand_id": h["hand_id"], "from": h["tournament_format"], "to": new_fmt})
        conn.commit()
    finally:
        conn.close()

    # (2) Re-scrub das coroas (só-tagadas; scrub_and_persist lê o TS live e é idempotente).
    rescrubbed = 0
    for h in hands:
        try:
            if scrub_and_persist(h["id"]):
                rescrubbed += 1
        except Exception as exc:  # pragma: no cover - defensivo (nunca rebenta o import)
            logger.error("[ts-reclassify] scrub falhou hand %s: %s", h["hand_id"], exc)

    # (3) Jusante: solves HRC agora stale por mudança de formato (listar, não re-solver).
    hrc_stale = _downstream_hrc([c["hand_id"] for c in changes])

    logger.info("[ts-reclassify] tn=%s reclassified=%d rescrubbed=%d hrc_stale=%d",
                tournament_number, len(changes), rescrubbed, len(hrc_stale))
    return {"tn": tournament_number, "reclassified": len(changes),
            "rescrubbed": rescrubbed, "changes": changes, "hrc_stale": hrc_stale}


def reclassify_and_rescrub_for_tns(tns: Optional[list]) -> dict:
    """Aplica a todos os tns GG upsertados numa corrida de import de TS. Agrega auditoria."""
    tns = [t for t in (tns or []) if t]
    total_reclass = total_rescrub = 0
    per_tn, hrc_stale = [], []
    for tn in tns:
        r = reclassify_and_rescrub_for_tn(tn)
        total_reclass += r["reclassified"]
        total_rescrub += r["rescrubbed"]
        hrc_stale.extend(r["hrc_stale"])
        if r["reclassified"] or r["rescrubbed"]:
            per_tn.append(r)
    return {"tns": len(tns), "reclassified": total_reclass, "rescrubbed": total_rescrub,
            "hrc_stale": hrc_stale, "per_tn": per_tn}
