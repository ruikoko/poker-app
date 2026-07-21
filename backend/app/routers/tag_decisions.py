"""SELO DA TAG — endpoints (read-only preview + escrita SELADA).

O Rui corrige tags: tira uma tag de uma mão (botão na página da mão) ou de VÁRIAS de uma vez
(selecção em lote no painel). A decisão fica SELADA em `tag_decisions` (append-only) e
sobrevive a todo o reprocessamento — ver `services/tag_decisions.py`.

Regras da casa cumpridas:
- O lote mostra o CUSTO antes de correr (`/preview`: quantas mãos, que tags saem) → o botão
  Cancelar vive no frontend; nada se escreve sem o Rui carimbar.
- Cada operação do lote vai ao RASTO, uma linha por mão, como se fosse feita à mão.
- FALHA HONESTA (Peça 1): o lote reporta por-item (ok/erro+porquê); nunca sucesso em bloco
  quando parte falhou.
- `hm3_tags` NÃO é tocada. Só `discord_tags`.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Body, Depends, HTTPException

from app.auth import require_auth
from app.db import get_conn, query
from app.services.tag_decisions import (ORIGIN_BATCH, ORIGIN_HAND_PAGE, VALID_ACTIONS,
                                        actor_of, seal_and_recompute)

router = APIRouter(prefix="/api/tag-decisions", tags=["tag-decisions"])
logger = logging.getLogger("tag_decisions")


def _apply_one(cur, hand_id, tag, action, *, actor, origin):
    """Aplica UMA decisão + re-avalia vilões das mãos afectadas. Devolve dict-resultado.
    Levanta ValueError em erro de validação/mão inexistente; o call site do lote apanha e
    transforma em item-erro (falha honesta).

    HONESTO (add): se a mão de destino JÁ tem a tag, NÃO escreve em duplicado nem finge —
    devolve `already_present=True, changed=False`. (O remove sela sempre: mesmo que a tag
    esteja ausente agora, o selo impede que um writer a volte a pôr no reprocessamento.)"""
    hand_id = (hand_id or "").strip()
    tag = (tag or "").strip()
    if not hand_id:
        raise ValueError("hand_id em falta")
    if not tag:
        raise ValueError("tag em falta")
    if action not in VALID_ACTIONS:
        raise ValueError(f"acção inválida: {action!r}")
    cur.execute("SELECT id, discord_tags FROM hands WHERE hand_id = %s", (hand_id,))
    hrows = cur.fetchall()
    if not hrows:
        raise ValueError(f"mão {hand_id} não encontrada")
    present = any(tag in (r.get("discord_tags") or []) for r in hrows)
    if action == "add" and present:
        return {"hand_id": hand_id, "tag": tag, "action": action,
                "already_present": True, "changed": False,
                "hand_db_ids": [r["id"] for r in hrows]}
    affected = seal_and_recompute(cur, hand_id, tag, action, actor=actor, origin=origin)
    return {"hand_id": hand_id, "tag": tag, "action": action,
            "already_present": False, "changed": True, "hand_db_ids": affected}


def _refresh_villains(hand_db_ids):
    """Pós-commit: corre o PIPELINE DE ESTUDO único (`on_hand_tagged`) em cada mão
    afectada — vilões (tirar 'nota' desfaz; pôr cria) + funil das coroas + propagação
    + FT. 21 Jul: antes só re-avaliava vilões; uma mão re-tagada por aqui entrava no
    Estudo sem o funil nunca ter corrido. Defensivo."""
    try:
        from app.services.study_pipeline import on_hand_tagged
        for hid in dict.fromkeys(hand_db_ids):        # dedupe, preserva ordem
            try:
                on_hand_tagged(hid)
            except Exception as e:  # pragma: no cover - defensivo
                logger.error("[tag-seal] pipeline hand %s: %s", hid, e)
    except Exception:  # pragma: no cover - defensivo
        pass


@router.post("/remove")
def remove_tag(payload: dict = Body(...), current_user=Depends(require_auth)):
    """Botão da página da mão: TIRA uma tag de uma mão. Sela (remove) + recomputa. A mão sem
    tag segue o caminho normal (vai para Torneios). Body: {hand_id, tag}."""
    actor = actor_of(current_user)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            res = _apply_one(cur, payload.get("hand_id"), payload.get("tag"), "remove",
                             actor=actor, origin=ORIGIN_HAND_PAGE)
        conn.commit()
    except ValueError as e:
        conn.rollback()
        raise HTTPException(400, str(e))
    finally:
        conn.close()
    _refresh_villains(res["hand_db_ids"])
    logger.info("[tag-seal] REMOVE %s de %s por %s", res["tag"], res["hand_id"], actor)
    return {"status": "removed", "hand_id": res["hand_id"], "tag": res["tag"]}


@router.post("/add")
def add_tag(payload: dict = Body(...), current_user=Depends(require_auth)):
    """Simétrico do remove: PÕE uma tag numa mão (para mover A→B, ou repor). Sela (add) +
    recomputa. Body: {hand_id, tag}."""
    actor = actor_of(current_user)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            res = _apply_one(cur, payload.get("hand_id"), payload.get("tag"), "add",
                             actor=actor, origin=ORIGIN_HAND_PAGE)
        conn.commit()
    except ValueError as e:
        conn.rollback()
        raise HTTPException(400, str(e))
    finally:
        conn.close()
    if res.get("already_present"):              # honesto: não finge que fez
        return {"status": "already_present", "hand_id": res["hand_id"], "tag": res["tag"],
                "already_present": True}
    _refresh_villains(res["hand_db_ids"])
    logger.info("[tag-seal] ADD %s a %s por %s", res["tag"], res["hand_id"], actor)
    return {"status": "added", "hand_id": res["hand_id"], "tag": res["tag"],
            "already_present": False}


@router.post("/preview")
def preview_batch(payload: dict = Body(...), current_user=Depends(require_auth)):
    """CUSTO do lote antes de correr (read-only, re-confere a BD ao vivo). Para cada item
    {hand_id, tag, action}, diz se a mão existe e que tags ficam depois. Body: {items:[...]}."""
    items = payload.get("items") or []
    if not isinstance(items, list) or not items:
        raise HTTPException(400, "items (lista não-vazia) obrigatório")
    hand_ids = sorted({(it.get("hand_id") or "").strip() for it in items if it.get("hand_id")})
    rows = query("SELECT hand_id, discord_tags FROM hands WHERE hand_id = ANY(%s)", (hand_ids,))
    tags_now = {r["hand_id"]: list(r["discord_tags"] or []) for r in rows}
    out = []
    n_hands, n_ops = set(), 0
    for it in items:
        hid = (it.get("hand_id") or "").strip()
        tag = (it.get("tag") or "").strip()
        action = it.get("action") or "remove"
        present = hid in tags_now
        has_tag = present and tag in tags_now[hid]
        # "sai" se for remove de uma tag que a mão tem; "entra" se add de uma que não tem.
        will_change = (action == "remove" and has_tag) or (action == "add" and present and not has_tag)
        out.append({"hand_id": hid, "tag": tag, "action": action, "exists": present,
                    "tags_now": tags_now.get(hid, []), "will_change": will_change,
                    "reason": None if present else "mão não encontrada"})
        if present:
            n_hands.add(hid)
        if will_change:
            n_ops += 1
    return {"n_hands": len(n_hands), "n_ops": n_ops, "n_items": len(items), "items": out}


@router.post("/batch")
def batch(payload: dict = Body(...), current_user=Depends(require_auth)):
    """Lote SELADO. Cada item {hand_id, tag, action='remove'|'add'} é aplicado numa
    transacção PRÓPRIA (um falho não arrasta os outros) e vai ao rasto — uma linha por mão.
    FALHA HONESTA: devolve n_ok/n_failed + por-item ok/erro. Body: {items:[...]}."""
    items = payload.get("items") or []
    if not isinstance(items, list) or not items:
        raise HTTPException(400, "items (lista não-vazia) obrigatório")
    if len(items) > 500:
        raise HTTPException(400, "máx 500 itens por chamada")
    actor = actor_of(current_user)
    results, refresh = [], []
    for it in items:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                res = _apply_one(cur, it.get("hand_id"), it.get("tag"),
                                 it.get("action") or "remove", actor=actor, origin=ORIGIN_BATCH)
            conn.commit()
            if res.get("changed"):                 # só re-avalia vilões do que mudou
                refresh.extend(res["hand_db_ids"])
            results.append({"hand_id": res["hand_id"], "tag": res["tag"],
                            "action": res["action"], "ok": True,
                            "already_present": bool(res.get("already_present")),
                            "changed": bool(res.get("changed"))})
        except ValueError as e:
            conn.rollback()
            results.append({"hand_id": (it.get("hand_id") or "").strip(),
                            "tag": (it.get("tag") or "").strip(),
                            "action": it.get("action") or "remove", "ok": False, "error": str(e)})
        except Exception as e:  # pragma: no cover - defensivo
            conn.rollback()
            logger.exception("[tag-seal] item %s falhou", it)
            results.append({"hand_id": (it.get("hand_id") or "").strip(),
                            "tag": (it.get("tag") or "").strip(),
                            "action": it.get("action") or "remove", "ok": False, "error": repr(e)})
        finally:
            conn.close()
    _refresh_villains(refresh)
    n_ok = sum(1 for r in results if r["ok"])
    n_failed = len(results) - n_ok
    logger.info("[tag-seal] LOTE por %s: %d ok, %d falhou", actor, n_ok, n_failed)
    return {"n_ok": n_ok, "n_failed": n_failed, "results": results}
