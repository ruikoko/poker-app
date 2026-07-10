"""HRC export queue endpoint — packages hands+payouts num zip para HRC watcher.

GET /api/queue/hrc — query params filtram hands; resposta e application/zip.

A selecção (Andar 1 SQL + defaults do basket) vive em
`app.services.hrc_queue` — fonte única partilhada com o painel HRC
(`GET /api/hrc/eligible`). Ver pt37.
"""
from __future__ import annotations
import io
import json
import logging
import zipfile
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse

from app.auth import require_auth_or_api_key
from app.db import query, execute
from app.services.hrc_jobs import (
    extract_meta_from_result_zip,
    upsert_hrc_job_result,
)
from app.services.queue_export import build_queue_zip
from app.services.hrc_queue import (
    resolve_filters,
    select_andar1_rows,
    lookup_payouts,
    lookup_bounties,
    lookup_icm_chips,
    enrich_hands_for_display,
    DEFAULT_TAGS,
    DEFAULT_STUDY_STATES,
    ALLOWED_SITES,
    normalize_tags_basket,
)

router = APIRouter(prefix="/api/queue", tags=["queue"])
logger = logging.getLogger("queue")

# Re-exports com os nomes privados legados — preservam o import path
# `from app.routers.queue import _DEFAULT_TAGS, _normalize_tags_basket` usado
# por backend/tests/test_queue_default_tags.py. Definições canónicas em
# app.services.hrc_queue (pt37 — single source, anti-drift).
_DEFAULT_TAGS = DEFAULT_TAGS
_DEFAULT_STUDY_STATES = DEFAULT_STUDY_STATES
_ALLOWED_SITES = ALLOWED_SITES
_normalize_tags_basket = normalize_tags_basket

# Cap de upload do zip de resultados (D-G2-4: 50 MB defensivo). Samples reais
# do HRC Complete Export ficam tipicamente em KB-MB; cap protege contra
# accident/abuse sem rejeitar uso legítimo.
#
# pt67 INTERINO (#HRC-RESULT-ZIP-413): subido 50 → 200 MB. Árvores Max=5
# (Complete Export = árvore inteira) chegam a ~112 MB e batiam no cap antigo
# (413 → adapter em retry-loop). O edge da Railway aceita ≥120 MB (provado:
# POST de 120 MB chega ao uvicorn e devolve a mensagem da app). 200 MB
# desbloqueia a 4ª volta SEM perder o bookkeeping de hrc_jobs.
# ⚠️ NÃO é a solução definitiva: 72 mãos × ~112 MB ≈ 8 GB em BYTEA é
# insustentável para a fila inteira — isso fica para a definitiva A/B/C
# (chunked / compressão / poda) em avaliação. Rede de salvação manual:
# upload via /hrc-sessions (POST /api/hrc/import, sem cap) → estudo OK,
# sem hrc_jobs.
_MAX_RESULT_ZIP_BYTES = 200 * 1024 * 1024  # 200 MB (pt67 interino; era 50 MB)


# ── Gate server-side da fila HRC com disparo manual (pt68, #QUEUE-NO-SERVER-SIDE-GATE) ──
# A fila nasce FECHADA: GET /hrc só serve mãos LIBERTADAS (em hrc_queue_release) e
# não-done. O Rui liberta lotes via POST /hrc/trigger ("Disparar"). Auto-fecha quando
# o lote é consumido (todas done → caem do filtro NOT EXISTS de hrc_jobs). O adapter
# não muda: fila fechada → zip vazio → fica idle. O download per-mão (/hrc/hand/{id})
# NÃO é gated. Ver REGISTO_CONCEITO / PENDENTES.

def ensure_hrc_queue_release_schema():
    execute(
        """
        CREATE TABLE IF NOT EXISTS hrc_queue_release (
            hand_db_id  INTEGER PRIMARY KEY REFERENCES hands(id) ON DELETE CASCADE,
            released_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            batch_id    TEXT
        )
        """
    )
    # pt83 (#HRC-SENT-LIST-AND-REQUEUE) — epoch de re-queue, incrementado por
    # POST /hrc/requeue. Servido por mão no manifest do pack → o adapter derrota
    # o dedup D10 (re-puxa quando served_epoch > o que tem em state).
    execute(
        "ALTER TABLE hrc_queue_release "
        "ADD COLUMN IF NOT EXISTS requeue_epoch INT NOT NULL DEFAULT 0"
    )
    # pt92 (#HRC-NODE-OFFSET-IMPLICIT-LINES) — marcador de re-processamento: mãos
    # já `done` cujo resultado ficou MAU (offset na posição errada) e foram
    # repostas para re-correr com o fix. NULL = normal; set → aparecem no
    # separador "Re-processar (offset corrigido)" do painel /hrc. Limpa-se quando
    # chega um novo `done` (POST /results). hand-level → vive em `hands`.
    execute(
        "ALTER TABLE hands ADD COLUMN IF NOT EXISTS reprocess_reason TEXT"
    )


def _released_ids() -> set:
    return {r["hand_db_id"] for r in query("SELECT hand_db_id FROM hrc_queue_release")}


@router.get("/hrc")
def export_queue(
    tags: Optional[str] = Query(None, description="CSV de tags (hm3+discord)"),
    study_state: Optional[str] = Query(None, description="CSV de study_states"),
    played_after: Optional[str] = Query(None, description="ISO date YYYY-MM-DD"),
    played_before: Optional[str] = Query(None, description="ISO date YYYY-MM-DD"),
    include_no_payout: bool = Query(False),
    current_user=Depends(require_auth_or_api_key),
):
    try:
        f = resolve_filters(tags, study_state, played_after, played_before)
    except ValueError:
        raise HTTPException(400, "played_after/played_before devem ser ISO date")

    hands = [dict(r) for r in select_andar1_rows(
        f["tags_norm"], f["states_list"], f["after_dt"], f["before_dt"],
    )]
    # Gate (pt68): só servir mãos LIBERTADAS. Fila fechada (nada libertado) → vazio.
    released = _released_ids()
    hands = [h for h in hands if h["id"] in released]
    # pt83 — epoch de re-queue por mão (servido no manifest → dedup epoch-aware do adapter).
    epoch_by_id = {r["hand_db_id"]: r["requeue_epoch"]
                   for r in query("SELECT hand_db_id, requeue_epoch FROM hrc_queue_release")}
    for h in hands:
        h["requeue_epoch"] = epoch_by_id.get(h["id"], 0)
    payouts_by_key = lookup_payouts(hands)
    bounty_by_key = lookup_bounties(hands)
    chips_by_key = lookup_icm_chips(hands)  # #ICM-CHIPS-USE-TS-FINAL-FIELD-GG

    filters_meta = {
        "tags": f["raw_tags"],
        "tags_normalized": f["tags_norm"],
        "study_state": f["states_list"],
        "played_after": f["after_str"],
        "played_before": f["before_str"],
        "include_no_payout": include_no_payout,
    }

    zip_bytes = build_queue_zip(
        hands, payouts_by_key,
        include_no_payout=include_no_payout,
        filters_meta=filters_meta,
        bounty_by_key=bounty_by_key,
        chips_by_key=chips_by_key,
    )
    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y%m%dT%H%M%SZ")
    fname = f"queue_{ts}.zip"
    logger.info(
        "queue/hrc exported: queried=%d filename=%s", len(hands), fname,
    )
    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


def _eligible_rows():
    f = resolve_filters(None, None, None, None)
    return [dict(r) for r in select_andar1_rows(
        f["tags_norm"], f["states_list"], f["after_dt"], f["before_dt"],
    )]


def _hand_exportable_quick(site, raw):
    """Guarda leve (point 4) para a UI: site suportado + raw presente. O guard
    PROFUNDO (seats/payout/bounty) corre no /release via build_queue_zip."""
    if site not in ALLOWED_SITES:
        return False, "site não suportado (%s)" % (site or "?")
    if not (raw or "").strip():
        return False, "sem HH (raw vazio)"
    return True, None


@router.post("/hrc/release")
def queue_release(payload: dict = Body(...),
                  current_user=Depends(require_auth_or_api_key)):
    """Release FORÇADO (multi-select da Estudo, pt68): liberta as mãos `hand_ids`
    escolhidas para a fila, **independente do cabaz/janela** (o gesto é "eu quero
    ESTAS"). Salta as não-exportáveis com motivo (build_queue_zip per-mão).
    Idempotente (ON CONFLICT). Body: {hand_ids: [...]}."""
    hand_ids = payload.get("hand_ids") or []
    if not isinstance(hand_ids, list) or not hand_ids:
        raise HTTPException(400, "hand_ids (lista não-vazia) obrigatório")
    if len(hand_ids) > 500:
        raise HTTPException(400, "máximo 500 mãos por envio")
    batch_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    released, skipped = [], []
    for hid in hand_ids:
        rows = query(f"SELECT {_HAND_COLS} FROM hands WHERE hand_id = %s LIMIT 1",
                     (hid,))
        if not rows:
            skipped.append({"hand_id": hid, "reason": "mão não encontrada"})
            continue
        h = dict(rows[0])
        ok, reason = _hand_exportable_quick(h.get("site"), h.get("raw"))
        if not ok:
            skipped.append({"hand_id": hid, "reason": reason})
            continue
        try:  # guard profundo: o pack é gerável?
            pk = lookup_payouts([h])
            bk = lookup_bounties([h])
            # (#include_no_payout-mismatch): include_no_payout=False alinha o release
            # com o que o GET /hrc serve. Sem isto, uma mão sem payout passava o guard
            # (True) e era LIBERTADA, mas o adapter (GET, False) nunca a servia →
            # released-fantasma presa em hrc_queue_release.
            zb = build_queue_zip([h], pk, include_no_payout=False,
                                 filters_meta={"single_hand": hid}, bounty_by_key=bk)
            with zipfile.ZipFile(io.BytesIO(zb)) as zf:
                man = json.loads(zf.read("manifest.json"))
            if man.get("total_in_zip", 0) == 0:
                # sem payout → vai para `missing_payouts` (não `skipped`): motivo claro.
                if man.get("missing_payouts"):
                    reason = ("sem payout — não pode ir ao HRC "
                              "(torneio sem estrutura de prémios)")
                else:
                    sk = man.get("skipped") or []
                    reason = sk[0].get("reason") if sk else "não exportável"
                skipped.append({"hand_id": hid, "reason": reason})
                continue
        except Exception as e:
            skipped.append({"hand_id": hid,
                            "reason": "erro ao gerar pack: %s" % type(e).__name__})
            continue
        # #HRC-ADAPTER-STATE-DESYNC-SILENT: re-envio tem de incrementar o
        # requeue_epoch (servir epoch > o do state local do adapter), senão o
        # adapter salta a mão em silêncio (dedup hrc_adapter.py:262). Release
        # fresco → INSERT epoch=0 (adapter puxa na mesma, não está em state);
        # re-envio (já libertada) → +1 → adapter re-puxa sozinho e loga re-queue.
        execute("INSERT INTO hrc_queue_release (hand_db_id, batch_id) VALUES (%s,%s) "
                "ON CONFLICT (hand_db_id) DO UPDATE SET "
                "  requeue_epoch = hrc_queue_release.requeue_epoch + 1, "
                "  released_at = NOW(), "
                "  batch_id = EXCLUDED.batch_id", (h["id"], batch_id))
        released.append(hid)
    logger.info("queue/hrc release forçado: released=%d skipped=%d batch=%s",
                len(released), len(skipped), batch_id)
    return {"released": released, "skipped": skipped, "batch_id": batch_id}


@router.post("/hrc/states")
def queue_hand_states(payload: dict = Body(...),
                      current_user=Depends(require_auth_or_api_key)):
    """Estado HRC por mão (badges da Estudo): nada / na fila / concluída / falhou
    + exportável? (guarda leve). Body: {hand_ids: [...]}."""
    hand_ids = payload.get("hand_ids") or []
    if not isinstance(hand_ids, list):
        raise HTTPException(400, "hand_ids (lista) obrigatório")
    if not hand_ids:
        return {"states": {}}
    rows = query(
        "SELECT h.hand_id, h.site, (h.raw IS NULL OR h.raw='') AS no_raw, "
        "(r.hand_db_id IS NOT NULL) AS released, j.status AS job_status "
        "FROM hands h "
        "LEFT JOIN hrc_queue_release r ON r.hand_db_id = h.id "
        "LEFT JOIN hrc_jobs j ON j.hand_db_id = h.id "
        "WHERE h.hand_id = ANY(%s)", (list(hand_ids),))
    out = {}
    for r in rows:
        if r["job_status"] == "done":
            state = "concluída"
        elif r["job_status"] == "failed":
            state = "falhou"
        elif r["released"]:
            state = "na fila"
        else:
            state = "nada"
        exportable = (r["site"] in ALLOWED_SITES) and not r["no_raw"]
        reason = (None if exportable else
                  ("site não suportado" if r["site"] not in ALLOWED_SITES else "sem HH"))
        out[r["hand_id"]] = {"state": state, "exportable": exportable, "reason": reason}
    return {"states": out}


# ── pt83 (#HRC-SENT-LIST-AND-REQUEUE) — lista das ENVIADAS + estado + re-queue ──
def _derive_sent_state(job_status) -> str:
    """Estado derivado de uma mão LIBERTADA (released). O backend NÃO distingue
    'a resolver agora' de 'presa' nem 'ainda não puxada' — tudo 'por_resolver'
    (o adapter não reporta pull, o watcher não reporta progresso)."""
    if job_status == "done":
        return "resolvida"
    if job_status == "failed":
        return "cancelada"
    return "por_resolver"


@router.get("/hrc/sent")
def queue_sent(current_user=Depends(require_auth_or_api_key)):
    """Lista TODAS as mãos libertadas (enviadas ao HRC) + estado derivado, para a
    secção 'Enviadas' do painel HRC. Reusa o JOIN de /hrc/states.

    Estados: resolvida (job done) / cancelada (job failed, +error) / por_resolver
    (released sem job). `released_at` p/ a pista 'enviada há Xh'. Read-only."""
    rows = query(
        "SELECT h.id, h.hand_id, h.site, h.tournament_name, h.hero_cards, h.played_at, "
        "       h.tournament_number, h.tournament_format, h.position, h.raw, "
        "       r.released_at, r.batch_id, r.requeue_epoch, "
        "       j.status AS job_status, j.error, j.result_zip_size, j.completed_at "
        "FROM hrc_queue_release r "
        "JOIN hands h ON h.id = r.hand_db_id "
        "LEFT JOIN hrc_jobs j ON j.hand_db_id = r.hand_db_id "
        "ORDER BY r.released_at DESC"
    )
    rows = [dict(r) for r in rows]
    # Enriquecimento com os campos ricos (iguais à secção Elegíveis) para a barra
    # de filtros da secção 'HRC Solved'. Defensivo — nunca esconde uma mão enviada.
    rich_by_id = enrich_hands_for_display(rows)
    out = []
    for d in rows:
        d["state"] = _derive_sent_state(d.get("job_status"))
        rich = rich_by_id.get(d.get("id"), {})
        out.append({
            "id": d.get("id"), "hand_id": d["hand_id"], "site": d["site"],
            "tournament_name": d.get("tournament_name"),
            "hero_cards": d.get("hero_cards"),
            "played_at": d.get("played_at"),
            "released_at": d.get("released_at"),
            "requeue_epoch": d.get("requeue_epoch") or 0,
            "state": d["state"],
            "error": d.get("error") if d["state"] == "cancelada" else None,
            "result_zip_size": d.get("result_zip_size") if d["state"] == "resolvida" else None,
            "completed_at": d.get("completed_at"),
            # Campos ricos p/ os filtros da secção HRC Solved (None = "sem dado").
            "tournament_format": rich.get("tournament_format"),
            "position_hero": rich.get("position_hero"),
            "first_vpip_position": rich.get("first_vpip_position"),
            "stack_hero_bb": rich.get("stack_hero_bb"),
            "total_players": rich.get("total_players"),
            "tournament_speed": rich.get("tournament_speed"),
            "players_left": rich.get("players_left"),
            "players_left_source": rich.get("players_left_source"),
        })
    return {"sent": out, "total": len(out)}


@router.post("/hrc/requeue")
def queue_requeue(payload: dict = Body(...),
                  current_user=Depends(require_auth_or_api_key)):
    """Re-põe mãos FALHADAS na fila: apaga o hrc_job failed (→ volta a
    'por_resolver') + incrementa `requeue_epoch` (servido no manifest → o adapter
    re-puxa, derrotando o dedup D10). Só actua sobre released + job failed.
    Body: {hand_ids: [...]}. Devolve {requeued, skipped}."""
    hand_ids = payload.get("hand_ids") or []
    if not isinstance(hand_ids, list) or not hand_ids:
        raise HTTPException(400, "hand_ids (lista não-vazia) obrigatório")
    requeued, skipped = [], []
    for hid in hand_ids:
        rows = query(
            "SELECT h.id, (r.hand_db_id IS NOT NULL) AS released, j.status AS job_status "
            "FROM hands h "
            "LEFT JOIN hrc_queue_release r ON r.hand_db_id = h.id "
            "LEFT JOIN hrc_jobs j ON j.hand_db_id = h.id "
            "WHERE h.hand_id = %s", (hid,))
        if not rows:
            skipped.append({"hand_id": hid, "reason": "mão não encontrada"})
            continue
        row = rows[0]
        if not row["released"]:
            skipped.append({"hand_id": hid, "reason": "não está na fila (não libertada)"})
            continue
        if row["job_status"] != "failed":
            skipped.append({"hand_id": hid,
                            "reason": f"não é falhada (estado={row['job_status'] or 'por_resolver'})"})
            continue
        # apaga o job failed → volta a 'por_resolver'; bump do epoch → adapter re-puxa.
        execute("DELETE FROM hrc_jobs WHERE hand_db_id = %s AND status = 'failed'", (row["id"],))
        execute("UPDATE hrc_queue_release SET requeue_epoch = requeue_epoch + 1 "
                "WHERE hand_db_id = %s", (row["id"],))
        requeued.append(hid)
    logger.info("queue/hrc requeue: requeued=%d skipped=%d", len(requeued), len(skipped))
    return {"requeued": requeued, "skipped": skipped}


@router.post("/hrc/set-aside")
def queue_set_aside(payload: dict = Body(...),
                    current_user=Depends(require_auth_or_api_key)):
    """Põe mãos-veneno DE LADO (inverso do /hrc/release): des-libertar (sai da fila
    servida → o adapter deixa de as puxar) + nota de auditoria (hrc_jobs failed).
    NÃO re-enfileirável (un-released → fora do /sent → sem botão Re-pôr na fila).
    Re-libertar no fluxo normal ("Disparar") quando se quiser re-tentar.
    Body: {hand_ids: [...], note?: "..."}. Devolve {set_aside, skipped}."""
    hand_ids = payload.get("hand_ids") or []
    note = (payload.get("note") or "set-aside manual").strip()
    if not isinstance(hand_ids, list) or not hand_ids:
        raise HTTPException(400, "hand_ids (lista não-vazia) obrigatório")
    set_aside, skipped = [], []
    for hid in hand_ids:
        rows = query("SELECT id FROM hands WHERE hand_id = %s", (hid,))
        if not rows:
            skipped.append({"hand_id": hid, "reason": "mão não encontrada"})
            continue
        hdb = rows[0]["id"]
        # 1. des-libertar → fora da fila servida (adapter deixa de puxar)
        execute("DELETE FROM hrc_queue_release WHERE hand_db_id = %s", (hdb,))
        # 2. nota de auditoria (hrc_jobs failed; UNIQUE(hand_db_id) → upsert)
        execute(
            "INSERT INTO hrc_jobs (hand_db_id, status, error, submitted_at, "
            "completed_at, meta_json) VALUES (%s, 'failed', %s, NOW(), NOW(), %s) "
            "ON CONFLICT (hand_db_id) DO UPDATE SET status='failed', "
            "error=EXCLUDED.error, completed_at=NOW(), meta_json=EXCLUDED.meta_json",
            (hdb, note, json.dumps({"set_aside": True, "reason": "manual", "note": note})),
        )
        set_aside.append(hid)
    logger.info("queue/hrc set-aside: %d de lado, %d skipped", len(set_aside), len(skipped))
    return {"set_aside": set_aside, "skipped": skipped}


@router.get("/hrc/verify/{hand_id}")
def queue_verify_hand(hand_id: str, current_user=Depends(require_auth_or_api_key)):
    """pt85 (#HRC-VERIFY) — verificação de correção HH-vs-HRC de UMA mão resolvida
    (C1-C5; C6 = v2). Read-only: abre o result_zip + a HH e cruza."""
    from app.services.hrc_verify import verify_hand
    rows = query(
        "SELECT h.hand_id, h.site, h.tournament_format, h.raw, h.all_players_actions, "
        "       h.context_table_ss_id, j.result_zip "
        "FROM hands h JOIN hrc_jobs j ON j.hand_db_id = h.id "
        "WHERE h.hand_id = %s AND j.status = 'done' AND j.result_zip IS NOT NULL",
        (hand_id,))
    if not rows:
        raise HTTPException(404, "mão não resolvida ou sem result_zip")
    h = dict(rows[0])
    zb = bytes(h["result_zip"])
    res = verify_hand(h, zb)
    res["site"] = h["site"]
    res.update(_verify_origin(h))
    # pt86 (#HRC-VERIFY) — vista legível "HH vs HRC": nó central (sequence-match,
    # não offset de linha) + ramos imediatos com frequências fold/call/raise.
    from app.services.hrc_verify_tree import build_verify_tree
    res["tree"] = build_verify_tree(h, zb)
    return res


def _verify_origin(h: dict) -> dict:
    """Origem da mão para o verify view: SS (table-SS) para GG com imagem guardada;
    HH texto caso contrário (WN/import). A imagem table-SS vive em
    table_ss_processing_log.img_b64, servível em /api/table-ss/image/{id}."""
    tsid = h.get("context_table_ss_id")
    if tsid:
        return {"origin_kind": "ss", "capture_url": f"/api/table-ss/image/{tsid}"}
    return {"origin_kind": "hh_text", "capture_url": None}


def _compute_verify_entry(h: dict, zip_bytes: bytes) -> dict:
    """pt92 ② — corre verify_hand + monta a entry (verdict/scale/checks/origin)
    que o painel consome. Determinístico por (mão, zip) → cacheável."""
    from app.services.hrc_verify import verify_hand
    res = verify_hand(h, zip_bytes)
    return {"hand_id": res["hand_id"], "site": h.get("site"),
            "verdict": res["verdict"], "scale": res["scale"],
            "checks": res["checks"], **_verify_origin(h)}


def cache_verify_for_hand(hand_db_id: int) -> Optional[dict]:
    """pt92 ② — calcula e GRAVA o verdict de verificação de uma mão resolvida em
    `hrc_jobs.verify_json`. Best-effort (devolve None em falha; não levanta).
    Usado no POST /results (eager) e no 1º /verify de cada mão (lazy backfill)."""
    try:
        rows = query(
            "SELECT h.hand_id, h.site, h.tournament_format, h.raw, "
            "       h.all_players_actions, h.context_table_ss_id, j.result_zip "
            "FROM hands h JOIN hrc_jobs j ON j.hand_db_id = h.id "
            "WHERE h.id = %s AND j.status = 'done' AND j.result_zip IS NOT NULL",
            (hand_db_id,),
        )
        if not rows:
            return None
        h = dict(rows[0])
        entry = _compute_verify_entry(h, bytes(h["result_zip"]))
        execute("UPDATE hrc_jobs SET verify_json = %s WHERE hand_db_id = %s",
                (json.dumps(entry), hand_db_id))
        return entry
    except Exception:
        logger.exception("cache_verify_for_hand falhou hand_db_id=%s", hand_db_id)
        return None


@router.get("/hrc/verify")
def queue_verify_batch(current_user=Depends(require_auth_or_api_key)):
    """pt85 — verify C1-C5 em lote sobre todas as resolvidas. Read-only.

    pt92 ②: lê o cache `hrc_jobs.verify_json` (SEM puxar o result_zip). Mãos sem
    cache (legadas) são calculadas + cacheadas UMA vez (lazy backfill) — só essas
    puxam o zip. Após a 1ª passagem, o endpoint não toca em nenhum zip → instantâneo.
    """
    from collections import Counter
    # 1. Cacheadas — só o JSON pequeno, zero zips.
    cached = query(
        "SELECT j.verify_json AS v FROM hrc_jobs j "
        "WHERE j.status = 'done' AND j.result_zip IS NOT NULL "
        "  AND j.verify_json IS NOT NULL")
    out = [r["v"] for r in cached if r["v"]]
    # 2. Sem cache (legadas) — puxa o zip UMA vez, calcula, cacheia.
    uncached = query(
        "SELECT h.id, h.hand_id, h.site, h.tournament_format, h.raw, "
        "       h.all_players_actions, h.context_table_ss_id, j.result_zip "
        "FROM hands h JOIN hrc_jobs j ON j.hand_db_id = h.id "
        "WHERE j.status = 'done' AND j.result_zip IS NOT NULL "
        "  AND j.verify_json IS NULL")
    for r in uncached:
        h = dict(r)
        entry = _compute_verify_entry(h, bytes(h["result_zip"]))
        execute("UPDATE hrc_jobs SET verify_json = %s WHERE hand_db_id = %s",
                (json.dumps(entry), h["id"]))
        out.append(entry)
    vc = Counter(e.get("verdict") for e in out)
    return {"total": len(out), "summary": dict(vc), "hands": out}


@router.get("/hrc/gate")
def queue_gate(current_user=Depends(require_auth_or_api_key)):
    """Contadores da fila HRC. pt92: a fila é 100% MANUAL — não há 'abrir/fechar'
    nem disparo em lote; só 'Enviar ao HRC' (POST /hrc/release) liberta mãos.
    Devolve contagens para o painel (sem campo 'gate' open/closed)."""
    eligible = _eligible_rows()
    elig_ids = {h["id"] for h in eligible}
    released = _released_ids()
    pending = elig_ids & released            # libertadas E ainda elegíveis (não-done)
    return {
        "eligible_total": len(elig_ids),      # elegíveis não-done, não-set-aside (todas)
        "released_pending": len(pending),     # libertadas, ainda por consumir (em curso)
        "not_released": len(elig_ids - released),  # disponíveis (por enviar manualmente)
        "released_total": len(released),
        "done_of_released": len(released - elig_ids),  # libertadas já consumidas (done)
    }


@router.post("/hrc/clear-released")
def queue_clear_released(current_user=Depends(require_auth_or_api_key)):
    """pt92 — Limpa/pausa a fila: remove TODAS as mãos de `hrc_queue_release` →
    o adapter deixa de puxar até nova seleção manual ('Enviar ao HRC'). NÃO toca
    em `hands` nem escreve `hrc_jobs` (não marca nada failed/set-aside) — só
    des-liberta. Devolve {cleared}."""
    n = query("SELECT count(*) AS n FROM hrc_queue_release")[0]["n"]
    execute("DELETE FROM hrc_queue_release")
    logger.info("queue/hrc clear-released: cleared=%d", n)
    return {"cleared": n}


@router.post("/hrc/reset-done")
def queue_reset_done(payload: dict = Body(...),
                     current_user=Depends(require_auth_or_api_key)):
    """pt92 (#HRC-NODE-OFFSET-IMPLICIT-LINES) — repõe mãos `done` ESPECÍFICAS para
    re-processar (resultado antigo ficou na posição errada do offset). SEGURO:
    actua **só** sobre os `hand_ids` passados — NUNCA um reset geral.

    Por cada mão com job `done`: apaga o `hrc_job` (→ volta a elegível) + marca
    `hands.reprocess_reason = reason` (default 'offset_fix_pt92') → aparece no
    separador "Re-processar (offset corrigido)". A mão NÃO é libertada aqui — o
    Rui selecciona-a e envia manualmente. Body: {hand_ids:[...], reason?}.
    """
    hand_ids = payload.get("hand_ids") or []
    reason = (payload.get("reason") or "offset_fix_pt92").strip()
    if not isinstance(hand_ids, list) or not hand_ids:
        raise HTTPException(400, "hand_ids (lista não-vazia) obrigatório")
    if len(hand_ids) > 500:
        raise HTTPException(400, "máximo 500 mãos por chamada")
    reset, skipped = [], []
    for hid in hand_ids:
        rows = query(
            "SELECT h.id, j.status AS job_status FROM hands h "
            "LEFT JOIN hrc_jobs j ON j.hand_db_id = h.id WHERE h.hand_id = %s",
            (hid,),
        )
        if not rows:
            skipped.append({"hand_id": hid, "reason": "mão não encontrada"})
            continue
        row = rows[0]
        if row["job_status"] != "done":
            skipped.append({"hand_id": hid,
                            "reason": f"não está 'done' (estado={row['job_status'] or 'sem job'})"})
            continue
        # apaga o job done → re-elegível; marca para o separador de re-processo.
        execute("DELETE FROM hrc_jobs WHERE hand_db_id = %s AND status = 'done'",
                (row["id"],))
        execute("DELETE FROM hrc_queue_release WHERE hand_db_id = %s", (row["id"],))
        execute("UPDATE hands SET reprocess_reason = %s WHERE id = %s",
                (reason, row["id"]))
        reset.append(hid)
    logger.info("queue/hrc reset-done: reset=%d skipped=%d reason=%s",
                len(reset), len(skipped), reason)
    return {"reset": reset, "skipped": skipped}


# Colunas que `build_queue_zip` consome — espelham `select_andar1_rows`
# (anti-drift: mesma forma de row para a maquinaria per-mão e batch).
_HAND_COLS = (
    "id, hand_id, site, tournament_number, tournament_name, "
    "tournament_format, raw, player_names, played_at, position, "
    "study_state, hm3_tags, discord_tags, context_table_ss_id, hero_cards"
)


@router.get("/hrc/hand/{hand_id}")
def export_queue_single_hand(
    hand_id: str,
    current_user=Depends(require_auth_or_api_key),
):
    """Download do pack HRC de UMA mão (workflow manual do Rui no painel /hrc).

    Reusa a maquinaria batch: `lookup_payouts` + `build_queue_zip([hand])`.
    Zip: `<hand_id>/hh.txt` + `payouts.json` (+ meta/script/manifest).

    - 404 se `hand_id` não existe.
    - 409 se o torneio da mão não tem `tournament_payouts` (pack ficaria sem
      `payouts.json` — exactamente a estrutura que o Rui quer evitar criar à mão).
    - 422 se a mão tem payout mas não é exportável (raw não convertível / sem
      seats parseáveis) — devolve o `reason` do `manifest.skipped`.
    """
    rows = query(
        f"SELECT {_HAND_COLS} FROM hands WHERE hand_id = %s LIMIT 1", (hand_id,)
    )
    if not rows:
        raise HTTPException(404, f"hand_id '{hand_id}' não encontrado")
    h = dict(rows[0])

    payouts_by_key = lookup_payouts([h])
    if payouts_by_key.get((h["site"], h["tournament_number"])) is None:
        raise HTTPException(
            409,
            f"sem tournament_payouts para o torneio {h['site']}/"
            f"{h['tournament_number']} desta mão",
        )

    # pt41: bounty base do TS (per-mão); se for PKO GG sem TS, build_queue_zip
    # skipa com reason='pko_without_ts_bounty' → 422 no gate final abaixo.
    bounty_by_key = lookup_bounties([h])
    chips_by_key = lookup_icm_chips([h])  # #ICM-CHIPS-USE-TS-FINAL-FIELD-GG

    zip_bytes = build_queue_zip(
        [h], payouts_by_key,
        include_no_payout=False,
        filters_meta={"single_hand": hand_id},
        bounty_by_key=bounty_by_key,
        chips_by_key=chips_by_key,
    )

    # Gate final: se a mão foi saltada (raw/seats), não devolver zip só-manifest.
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        manifest = json.loads(zf.read("manifest.json"))
    if manifest.get("total_in_zip", 0) == 0:
        skipped = manifest.get("skipped") or []
        reason = skipped[0].get("reason") if skipped else "unknown"
        raise HTTPException(422, f"mão '{hand_id}' não exportável: {reason}")

    fname = f"hrc_{hand_id}.zip"
    logger.info("queue/hrc single-hand exported: hand_id=%s filename=%s", hand_id, fname)
    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@router.post("/hrc/results")
async def upload_hrc_result(
    hand_id: str = Query(..., description="hand_id TEXT (ex: 'GG-281416137')"),
    status: str = Query("done", description="'done' ou 'failed'"),
    error: Optional[str] = Query(None, description="motivo (obrigatório se status='failed')"),
    file: Optional[UploadFile] = File(None),
    current_user=Depends(require_auth_or_api_key),
):
    """Recebe resultado HRC para uma mão (do watcher Beelink).

    - `status='done'`: `file` obrigatório (zip Complete Export do HRC).
      O zip deve conter `meta.json` no root com pelo menos
      `{rank, players_left, stage, ci}`.
    - `status='failed'`: `error` obrigatório, `file` ignorado se vier.

    UPSERT em `hrc_jobs` por `hand_db_id`. Re-upload sobrescreve
    (preserva `submitted_at` original).

    Auth: cookie (UI) OU `Authorization: Bearer <HRC_WATCHER_API_KEY>` (G4).

    Returns: `{hand_db_id, status, action, meta}`.
    """
    if status not in ("done", "failed"):
        raise HTTPException(400, f"status inválido: '{status}' (use 'done' ou 'failed')")
    if status == "failed" and not error:
        raise HTTPException(400, "error obrigatório quando status='failed'")
    if error and len(error) > 500:
        raise HTTPException(400, "error excede 500 chars")

    rows = query(
        "SELECT id FROM hands WHERE hand_id = %s LIMIT 1", (hand_id,)
    )
    if not rows:
        raise HTTPException(404, f"hand_id '{hand_id}' não encontrado")
    hand_db_id = rows[0]["id"]

    now_iso = datetime.now(timezone.utc).isoformat()
    base_meta = {
        "hand_id": hand_id,
        "received_at": now_iso,
        "received_from": "watcher",
    }

    if status == "failed":
        if file is not None:
            logger.warning(
                "hrc_jobs: file ignored on failed upload hand_id=%s", hand_id
            )
        meta_aug = {**base_meta, "failure_reported_by": "watcher"}
        row = upsert_hrc_job_result(
            hand_db_id=hand_db_id,
            status="failed",
            result_zip=None,
            meta_json=meta_aug,
            error=error,
        )
        size = 0
    else:  # done
        if file is None:
            raise HTTPException(400, "file obrigatório quando status='done'")
        content = await file.read()
        size = len(content)
        if size == 0:
            raise HTTPException(400, "file vazio")
        if size > _MAX_RESULT_ZIP_BYTES:
            raise HTTPException(
                413, f"file excede {_MAX_RESULT_ZIP_BYTES // 1024 // 1024} MB"
            )
        try:
            meta = extract_meta_from_result_zip(content)
        except ValueError as e:
            raise HTTPException(400, str(e))
        # base_meta DEPOIS de meta para que server-side sobrescreva
        # eventuais campos homónimos no meta.json do zip (D-G2-EXTRA-3).
        meta_aug = {**meta, **base_meta}
        row = upsert_hrc_job_result(
            hand_db_id=hand_db_id,
            status="done",
            result_zip=content,
            meta_json=meta_aug,
            error=None,
        )
        # pt92 ② — cacheia o verdict de verificação já aqui (eager), para o
        # GET /hrc/verify não precisar de re-puxar+re-analisar o zip. Best-effort.
        cache_verify_for_hand(hand_db_id)
        # pt92 (#HRC-NODE-OFFSET-IMPLICIT-LINES) — mão re-processada → sai do
        # separador "Re-processar" (limpa o marcador).
        execute("UPDATE hands SET reprocess_reason = NULL "
                "WHERE id = %s AND reprocess_reason IS NOT NULL", (hand_db_id,))

    action = "inserted" if row.get("inserted") else "updated"
    logger.info(
        "hrc_jobs: upsert hand_id=%s db_id=%d status=%s size=%d action=%s",
        hand_id, hand_db_id, status, size, action,
    )
    return {
        "hand_db_id": hand_db_id,
        "status": status,
        "action": action,
        "meta": meta_aug,
    }
