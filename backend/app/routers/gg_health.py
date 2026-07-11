"""Saúde das mãos GG — vista POR IMAGEM (Fase 1: só MOSTRAR, read-only).

Duas fontes de imagem GG, em sítios diferentes, unidas por UNION:
  - GOLD (replayer): `entries` (entry_type='screenshot', raw_json.img_b64),
    ligada à mão por `hands.entry_id`. Casa EXATO pelo nº do ficheiro.
  - IT table-SS: `table_ss_processing_log.img_b64`, ligada por
    `hands.context_table_ss_id`. Casa por tempo/nome → pode trocar.

Só GG, 2026. NADA escreve. O conflito de tags e a suspeita de troca calculam-se
LIVE. `nota`/`Timetell`/`For Review` são neutras no conflito.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel

from app.auth import require_auth, require_auth_or_api_key
from app.db import query, get_conn
from app.services.ft_boundary import (
    FT_CAP, count_hh_seats, compute_ft_boundary, propagate_ft,
    candidate_tns, via_b_diagnostics, review_status,
)
from app.services.tags_canonical import canonicalize_tag, normalize_tag_key
from app.services.eliminated_bounty import (
    busted_real_names, BOUNTY_REVIEW_KEY, BOUNTY_SOURCE_KEY, SOURCE_GREEN_KO,
)

router = APIRouter(prefix="/api/gg-health", tags=["gg-health"])

_GG = "h.site = 'GGPoker' AND h.played_at >= '2026-01-01'"
_FNUM_IT = re.compile(r"_(\d{9,10})-\d{14}-\d+\.(?:png|jpg|jpeg)$", re.I)
_FNUM_GOLD = re.compile(r"#(\d{9,10})")

# Regras de conflito (chaves normalizadas) — 2 regras seladas.
_PHASE_PAIRS = {  # base → ft (mesmo spot)
    "icm": "icm ft", "icm pko": "icm pko ft", "pos pko": "pos pko ft",
    "pos nko": "pos nko ft", "speed racer": "speed racer ft",
}
# Conjuntos de FORMATO (base + a própria ft), pela canónica.
_PKO_ALL = {"icm pko", "pos pko", "speed racer",
            "icm pko ft", "pos pko ft", "speed racer ft"}
_NONPKO_ALL = {"icm", "pos nko", "icm ft", "pos nko ft"}
_NEUTRAL = {"nota", "timetell", "for review"}


def _tag_conflicts(discord_tags, hm3_tags) -> list[str]:
    """Conflitos ('formato'/'fase') presentes na mão, pela canónica. Neutras
    (nota/Timetell/For Review) não contam."""
    nk = {normalize_tag_key(t) for t in list(discord_tags or []) + list(hm3_tags or []) if t}
    nk -= _NEUTRAL
    out = []
    if (nk & _PKO_ALL) and (nk & _NONPKO_ALL):        # PKO + não-PKO na mesma mão
        out.append("formato")
    if any(base in nk and ft in nk for base, ft in _PHASE_PAIRS.items()):  # base + a sua FT
        out.append("fase")
    return out


def _gold_rows() -> list[dict]:
    rows = query(
        f"""SELECT e.id AS ss_id, e.file_name AS fname, h.id AS hand_db_id,
                   h.hand_id, h.discord_tags, h.hm3_tags,
                   (h.player_names->>'match_method') AS mm
              FROM entries e JOIN hands h ON h.entry_id = e.id
             WHERE e.entry_type = 'screenshot'
               AND (e.raw_json->>'img_b64') IS NOT NULL AND {_GG}"""
    )
    out = []
    for r in rows:
        m = _FNUM_GOLD.search(r.get("fname") or "")
        out.append({
            "source": "gold",
            "image_url": f"/api/screenshots/image/{r['ss_id']}",
            "filename": r.get("fname"),
            "filename_num": m.group(1) if m else None,
            "hand_id": r.get("hand_id"),
            "hand_db_id": r.get("hand_db_id"),
            "matched": True,                # Gold liga sempre a uma mão
            "num_matches": True,            # Gold casa EXATO pelo nº
            "tags": list(r.get("discord_tags") or []) + list(r.get("hm3_tags") or []),
            "conflicts": _tag_conflicts(r.get("discord_tags"), r.get("hm3_tags")),
            "has_tag": bool(r.get("discord_tags") or r.get("hm3_tags")),
            "state": "casou",
        })
    return out


def _it_rows() -> list[dict]:
    # h = mão PRINCIPAL (a que aponta para esta captura via context_table_ss_id).
    # h2 = mão do matched_hand_id do log — para as capturas SECUNDÁRIAS (duplicados
    # legítimos: casaram uma mão, mas outra captura é a principal). #IT-MATCHER-COLISOES.
    rows = query(
        f"""SELECT l.id AS ss_id, l.original_filename AS fname, l.matched_hand_id,
                   l.swap_review,
                   h.id AS hand_db_id, h.hand_id, h.discord_tags, h.hm3_tags,
                   h2.id AS dup_db_id, h2.hand_id AS dup_hand_id,
                   h2.discord_tags AS dup_discord_tags, h2.hm3_tags AS dup_hm3_tags
              FROM table_ss_processing_log l
              LEFT JOIN hands h ON h.context_table_ss_id = l.id
              LEFT JOIN hands h2 ON h2.hand_id = l.matched_hand_id
             WHERE l.img_b64 IS NOT NULL AND l.site = 'GGPoker'"""
    )
    out = []
    for r in rows:
        m = _FNUM_IT.search(r.get("fname") or "")
        fnum = m.group(1) if m else None
        principal = r.get("hand_db_id") is not None
        # SECUNDÁRIA = não é a principal, mas casou uma mão existente (duplicado).
        secondary = (not principal) and r.get("dup_db_id") is not None
        matched = principal or secondary
        hand_db_id = r.get("hand_db_id") if principal else (r.get("dup_db_id") if secondary else None)
        matched_hid = (r.get("hand_id") if principal
                       else (r.get("dup_hand_id") if secondary else r.get("matched_hand_id")))
        disc = r.get("discord_tags") if principal else r.get("dup_discord_tags")
        hm3 = r.get("hm3_tags") if principal else r.get("dup_hm3_tags")
        # num_matches: None se não casou ou sem nº. Nº inteiro → igualdade; nº
        # TRUNCADO (título longo, ex. Speed Racer) → PREFIXO da mão (dois sinais
        # concordam; evita "suspeita" falsa em mãos que o matcher já acertou).
        if not matched or fnum is None:
            num_matches = None
        elif len(fnum) >= 10:
            num_matches = (matched_hid == f"GG-{fnum}")
        else:
            num_matches = bool(matched_hid) and matched_hid.startswith(f"GG-{fnum}")
        out.append({
            "source": "it",
            "ss_id": r["ss_id"],               # p/ as Ações 2/3 (link / swap-review)
            "image_url": f"/api/table-ss/image/{r['ss_id']}",
            "filename": r.get("fname"),
            "filename_num": fnum,
            "hand_id": matched_hid if matched else None,
            "hand_db_id": hand_db_id,
            "matched": matched,
            "secondary": secondary,
            "swap_reviewed": r.get("swap_review") is not None,
            "num_matches": num_matches,
            "tags": list(disc or []) + list(hm3 or []),
            "conflicts": _tag_conflicts(disc, hm3) if matched else [],
            "has_tag": bool(disc or hm3),
            "state": "duplicada" if secondary else ("casou" if principal else "órfã"),
        })
    # #SWAP-ACCEPT-GUARD — a mão do NÚMERO do ficheiro (GG-<fnum>) existe na base?
    # Se NÃO existir (caso dos "prints atrasados", cujo nº aponta a mão seguinte que
    # não temos importada), o ACEITAR não tem destino → o frontend desativa o botão.
    # Uma query única para todas as linhas.
    targets = {f"GG-{im['filename_num']}" for im in out if im.get("filename_num")}
    existing = set()
    if targets:
        existing = {row["hand_id"] for row in query(
            "SELECT hand_id FROM hands WHERE hand_id = ANY(%s)", (list(targets),))}
    for im in out:
        fn = im.get("filename_num")
        im["accept_target_exists"] = bool(fn) and (f"GG-{fn}" in existing)
    return out


def _all_images() -> list[dict]:
    return _gold_rows() + _it_rows()


# ── Predicados de grupo (por imagem) ─────────────────────────────────────────
def _group_pred(key):
    if key == "gold_matched":
        return lambda im: im["source"] == "gold" and im["matched"]
    if key == "it_matched":
        return lambda im: im["source"] == "it" and im["matched"]
    if key == "gold_no_tag":
        return lambda im: im["source"] == "gold" and im["matched"] and not im["has_tag"]
    if key == "orphans":
        return lambda im: not im["matched"]
    if key == "swap_suspects":
        # exclui as já revistas pelo Rui (Ação 3: 'moved'/'kept' → saem do painel).
        return lambda im: (im["source"] == "it" and im["matched"]
                           and im["num_matches"] is False and not im.get("swap_reviewed"))
    if key == "tag_conflicts":
        return lambda im: bool(im["conflicts"])
    if key == "all":
        return lambda im: True
    return None


@router.get("/summary")
def summary(current_user=Depends(require_auth)):
    """Panorama + contagens por grupo (read-only). Painéis = só números."""
    imgs = _all_images()
    hands_with_img = {im["hand_db_id"] for im in imgs if im["hand_db_id"]}

    def n(key):
        p = _group_pred(key)
        return sum(1 for im in imgs if p(im))

    # F4: "Precisam de ti" (ft_quarantine) conta SÓ os que exigem decisão do Rui
    # (secção 'needs' — none-com-sinal/mismatch/disagreement/n_unavailable/incoherent),
    # NÃO os match limpos (secção 'ready') nem os já promovidos. Gate apertado → poucos
    # candidatos → compute barato. Defensivo: pré-deploy/tabela ausente → 0.
    try:
        ft_quarantine = sum(1 for c in _ft_candidate_list() if c["section"] == "needs")
    except Exception:
        ft_quarantine = 0

    # Fase 3: quarentena de NOMES pendente (propagação por hash). Defensivo → 0.
    try:
        r = query("SELECT COUNT(*) c FROM name_quarantine_review WHERE decision='pending'")
        name_quarantine = int(r[0]["c"]) if r else 0
    except Exception:
        name_quarantine = 0

    return {
        "total_images": len(imgs),
        "total_hands_with_image": len(hands_with_img),
        "needs_you": {
            "gold_no_tag": n("gold_no_tag"),
            "orphans": n("orphans"),
            "swap_suspects": n("swap_suspects"),
            "tag_conflicts": n("tag_conflicts"),
            "ft_quarantine": ft_quarantine,
            "name_quarantine": name_quarantine,
        },
        "healthy": {
            "gold_matched": n("gold_matched"),
            "it_matched": n("it_matched"),
        },
    }


@router.get("/crowns")
def crowns_to_verify(current_user=Depends(require_auth)):
    """Painel COROAS da Saúde Import (consolidação 11 Jul) — mãos GG PKO/KO cuja
    coroa ($ bounty) gravada é < base÷2. `impossible` = valor >0 mas <½ (a Vision
    leu a chama VPIP em vez da coroa $); `unread` = coroa a $0 (por ler). Read-only:
    lista com IMAGEM + seats afetados para o Rui confirmar à vista (`tableSs.setBounties`
    com `confirm[]`) ou corrigir o valor. Fonte única `detect_bounty_below_half` (a
    mesma da guarda `bounty_below_half_base` do export)."""
    from app.services.queue_export import TS_GATED_FORMATS, detect_bounty_below_half
    rows = query(
        """SELECT h.id, h.hand_id, h.tournament_name, h.played_at::text AS played_at,
                  h.player_names AS pn, h.context_table_ss_id AS ss_id,
                  (h.player_names->>'match_method') AS mm,
                  ts.buy_in_bounty AS base
             FROM hands h
             JOIN tournament_summaries ts
               ON ts.site='GGPoker' AND ts.tournament_number = h.tournament_number
            WHERE h.site='GGPoker' AND h.played_at >= '2026-01-01'
              AND ts.buy_in_bounty IS NOT NULL
              AND lower(COALESCE(h.tournament_format,'')) = ANY(%s)
            ORDER BY h.played_at DESC""",
        (list(TS_GATED_FORMATS),),
    )
    impossible, unread = [], []
    by_source = {"table_ss": 0, "gold": 0, "other": 0}
    for r in rows:
        below = detect_bounty_below_half(r["pn"], r["base"])
        if not below:
            continue
        kind = "impossible" if any((b["value"] or 0) > 0 for b in below) else "unread"
        # ── ORIGEM do valor suspeito: compara-o com a coroa da captura table-SS
        #    (bate → escreveu-o o table-SS); senão veio do Gold/carry/reread. ──
        ss_vals = {}
        if r["ss_id"]:
            c = query("SELECT vision_json vj FROM table_ss_processing_log WHERE id=%s", (r["ss_id"],))
            if c:
                vj = c[0]["vj"]
                if isinstance(vj, str):
                    vj = json.loads(vj or "{}")
                ss_vals = {s.get("nick"): s.get("bounty_usd") for s in (vj.get("seats") or [])}
        match_ss = any(b["name"] in ss_vals and ss_vals[b["name"]] is not None
                       and abs(float(ss_vals[b["name"]]) - float(b["value"] or 0)) < 0.5
                       for b in below)
        gold = query("SELECT e.id FROM entries e JOIN hands h ON h.entry_id=e.id "
                     "WHERE h.id=%s AND e.entry_type='screenshot' "
                     "AND (e.raw_json->>'img_b64') IS NOT NULL LIMIT 1", (r["id"],))
        gold_id = gold[0]["id"] if gold else None
        if match_ss:
            source, src_img = "table_ss", (f"/api/table-ss/image/{r['ss_id']}" if r["ss_id"] else None)
        elif gold_id:
            source, src_img = "gold", f"/api/screenshots/image/{gold_id}"
        else:
            source, src_img = "other", (f"/api/table-ss/image/{r['ss_id']}" if r["ss_id"] else None)
        by_source[source] += 1
        item = {
            "id": r["id"], "hand_id": r["hand_id"],
            "tournament_name": r["tournament_name"], "played_at": r["played_at"],
            "kind": kind, "floor": below[0]["floor"],
            "match_method": r["mm"],
            "crown_source": source,           # table_ss | gold | other(carry/reread)
            "has_both": bool(r["ss_id"]) and bool(gold_id),
            "image_url": src_img,             # a imagem da FONTE do valor suspeito
            "image_is_source": True,          # (mostramos a fonte, não outra captura)
            "seats": [{"name": b["name"], "value": b["value"]} for b in below],
        }
        (impossible if kind == "impossible" else unread).append(item)
    return {"count": len(impossible) + len(unread),
            "by_source": by_source,
            "impossible": impossible, "unread": unread}


@router.get("/list")
def list_images(
    group: str = Query("all"),
    page: int = Query(1, ge=1),
    page_size: int = Query(60, ge=1, le=300),
    current_user=Depends(require_auth),
):
    """Lista POR IMAGEM de um grupo/cenário (read-only, paginada)."""
    pred = _group_pred(group)
    if pred is None:
        return {"error": f"grupo inválido: {group!r}", "total": 0, "images": []}
    rows = [im for im in _all_images() if pred(im)]
    total = len(rows)
    start = (page - 1) * page_size
    return {
        "group": group, "total": total, "page": page, "page_size": page_size,
        "images": rows[start:start + page_size],
    }


# ── Matéria-prima para a validação 4b da propagação FT (SÓ LEITURA) ──────────
# F2: a contagem canónica de sentados vive em `services/ft_boundary.count_hh_seats`
# (fonte única, endurecida lá). Alias mantém o nome local histórico.
_count_seats = count_hh_seats


@router.get("/ft/raw-material")
def ft_raw_material(current_user=Depends(require_auth_or_api_key)):
    """Matéria-prima (SÓ LEITURA) para a validação 4b da propagação FT: torneios GG
    2026 por DIA, com a pista de FT por torneio — o menor `players_left` visto
    (lobby + capturas IT) e os sentados na mão mais tardia. O Rui usa isto para ir
    buscar ao backoffice os prints de lobby dos torneios em que fez mesa final.

    `ft_candidate` = `min_players_left <= FT_CAP` (ou, sem esse sinal, sentados da
    última mão <= FT_CAP). Reutilizado pela Fase 3 (o preview/quarentena parte das
    mesmas leituras) e RE-CORRÍVEL após o wipe+reimport (recomputa de raiz, nada
    persistido). Ordenação: por dia (asc); dentro do dia, n_hands desc."""
    aggs = query(
        "SELECT h.tournament_number AS tn, MIN(h.played_at)::date AS day, "
        "       MAX(h.tournament_name) AS name, COUNT(*) AS n_hands, "
        "       MIN(l.players_left) AS min_pl_it "
        "  FROM hands h "
        "  LEFT JOIN table_ss_processing_log l "
        "         ON l.id = h.context_table_ss_id AND l.players_left IS NOT NULL "
        " WHERE " + _GG + " AND h.tournament_number IS NOT NULL "
        " GROUP BY h.tournament_number"
    )
    lobby = {r["tn"]: r["min_pl"] for r in query(
        "SELECT tournament_number AS tn, MIN(players_left) AS min_pl "
        "  FROM lobby_processing_log "
        " WHERE tournament_number IS NOT NULL AND site = 'GGPoker' "  # GG-scoped (o resto do circuito FT já o é)
        " GROUP BY tournament_number"
    )}
    latest = {r["tn"]: r["raw"] for r in query(
        "SELECT DISTINCT ON (h.tournament_number) h.tournament_number AS tn, h.raw AS raw "
        "  FROM hands h "
        " WHERE " + _GG + " AND h.tournament_number IS NOT NULL "
        " ORDER BY h.tournament_number, h.played_at DESC"
    )}

    rows = []
    for a in aggs:
        tn = a["tn"]
        pls = [v for v in (a["min_pl_it"], lobby.get(tn)) if isinstance(v, int)]
        min_pl = min(pls) if pls else None
        seats = _count_seats(latest.get(tn))
        ft_candidate = ((min_pl is not None and min_pl <= FT_CAP)
                        or (min_pl is None and seats is not None and seats <= FT_CAP))
        rows.append({
            "tournament_number": tn,
            "tournament_name": a["name"],
            "day": a["day"].isoformat() if a["day"] else None,
            "n_hands": a["n_hands"],
            "min_players_left": min_pl,
            "latest_hand_seats": seats,
            "has_lobby": tn in lobby,
            "ft_candidate": ft_candidate,
        })

    by_day: dict = {}
    for r in rows:
        by_day.setdefault(r["day"], []).append(r)
    days = []
    for day in sorted(by_day, key=lambda d: (d is None, d or "")):
        ts = sorted(by_day[day], key=lambda r: r["n_hands"], reverse=True)
        days.append({"day": day, "tournaments": ts,
                     "ft_candidates": sum(1 for r in ts if r["ft_candidate"])})
    return {
        "scope": "GGPoker 2026",
        "total_tournaments": len(rows),
        "total_ft_candidates": sum(1 for r in rows if r["ft_candidate"]),
        "days": days,
    }


# ── #GG-HEALTH-ACTIONS — Ação 1: tagar (multi-select, aviso de conflito) ──────
_TAG_BUTTONS = ["icm", "icm-pko", "pos-pko", "pos-nko", "speed-racer",
                "icm-ft", "icm-pko-ft", "pos-pko-ft", "pos-nko-ft",
                "speed-racer-ft", "nota"]
_PKO_TAGS = {"icm-pko", "pos-pko", "speed-racer",
             "icm-pko-ft", "pos-pko-ft", "speed-racer-ft"}
_VAN_TAGS = {"icm", "pos-nko", "icm-ft", "pos-nko-ft"}
_BOUNTY_FMT = {"PKO", "Super KO", "Mystery KO"}


def _tag_format_conflict(tag_canon, tournament_format):
    """A tag contradiz o formato REAL do torneio? (a app sabe o formato)."""
    fmt = (tournament_format or "").strip()
    if tag_canon in _PKO_TAGS and fmt == "Vanilla":
        return "pko_tag_on_vanilla"
    if tag_canon in _VAN_TAGS and fmt in _BOUNTY_FMT:
        return "vanilla_tag_on_bounty"
    return None


@router.get("/tag-buttons")
def tag_buttons(current_user=Depends(require_auth)):
    return {"tags": _TAG_BUTTONS}


@router.post("/tag")
def gg_health_tag(payload: dict = Body(...),
                  current_user=Depends(require_auth_or_api_key)):
    """Ação 1 — taga N mãos com UMA ou VÁRIAS tags canónicas de uma vez (`tags`:
    lista; `tag`: string única, back-compat). ACRESCENTA (union distinct em
    discord_tags — NUNCA substitui), normaliza na escrita, dispara
    apply_villain_rules. Se alguma tag contradizer o formato do torneio → devolve
    `needs_confirm` + warnings (não grava sem confirm). Idempotente (tag que a mão já
    tem → no-op)."""
    hand_ids = payload.get("hand_ids") or []
    # `tags` (lista) tem prioridade; senão `tag` (string única, back-compat).
    raw_tags = payload.get("tags")
    if not (isinstance(raw_tags, list) and raw_tags):
        raw_tags = [payload.get("tag")]
    # only_known=True: aceita SÓ tags reconhecidas (canónicas); string arbitrária
    # → None → 400 (o endpoint não deixa criar tags fora do vocabulário).
    canons = []
    for t in raw_tags:
        ct = canonicalize_tag(t, only_known=True)
        if not ct:
            raise HTTPException(400, f"tag inválida: {t!r} (usar as tags canónicas)")
        if ct not in canons:
            canons.append(ct)                  # dedup preservando ordem
    confirm = bool(payload.get("confirm"))
    if not canons:
        raise HTTPException(400, "tag(s) obrigatória(s) (usar as tags canónicas)")
    if not isinstance(hand_ids, list) or not hand_ids:
        raise HTTPException(400, "hand_ids (lista não-vazia) obrigatório")
    if len(hand_ids) > 500:
        raise HTTPException(400, "máx 500 mãos por chamada")
    rows = query("SELECT id, hand_id, discord_tags, tournament_format "
                 "FROM hands WHERE hand_id = ANY(%s)", (hand_ids,))
    warnings = []
    for r in rows:
        for ct in canons:
            c = _tag_format_conflict(ct, r["tournament_format"])
            if c:
                warnings.append({"hand_id": r["hand_id"], "conflict": c, "tag": ct,
                                 "tournament_format": r["tournament_format"]})
    if warnings and not confirm:
        return {"applied": 0, "needs_confirm": True, "warnings": warnings, "tags": canons}
    applied = hands_touched = 0
    conn = get_conn()
    try:
        for r in rows:
            existing = {canonicalize_tag(t) for t in (r["discord_tags"] or [])}
            to_add = [ct for ct in canons if ct not in existing]  # ACRESCENTA só o que falta
            if not to_add:
                continue                       # idempotente: já tem todas
            new_tags = list(r["discord_tags"] or []) + to_add
            with conn.cursor() as cur:
                cur.execute("UPDATE hands SET discord_tags=%s WHERE id=%s",
                            (new_tags, r["id"]))
            conn.commit()
            try:
                from app.services.villain_rules import apply_villain_rules
                apply_villain_rules(r["id"])
            except Exception:
                pass
            applied += len(to_add)
            hands_touched += 1
    finally:
        conn.close()
    return {"applied": applied, "hands": hands_touched, "tags": canons,
            "warnings": warnings, "needs_confirm": False}


# ── F3: preview + revisão/quarentena + promoção da fronteira FT ──────────────
_ft_map_status = review_status   # fonte única em services/ft_boundary (F5)


def _ft_warnings(d, diag) -> list:
    w = []
    st = d.get("status")
    cc = d.get("cross_check") or {}
    if st == "quarantine_disagreement":
        w.append("tag manual e lobby discordam (p/ la da janela do snap) -> quarentena")
    if st == "incoherent_signal":
        w.append("capturas incoerentes (cauda pos-pico com 2+ saltos) -> sem fronteira")
    if cc.get("match") is False and st != "quarantine_disagreement":
        w.append(f"cross-check falhou: N={cc.get('n')} != sentados 1a mao={cc.get('hh_seats')}")
    if cc.get("match") is None and d.get("boundary") is not None:
        w.append("sem N independente para cross-check (fonte sem lobby Info)")
    if diag:
        if diag.get("outlier_dropped"):
            w.append("via-b: outlier isolado descartado da sequencia de players_left")
        if diag.get("coherent") is False:
            w.append("via-b: sequencia pos-pico incoerente")
    return w


def _ft_hrc_stale(tn, boundary) -> list:
    """Maos >= fronteira com job HRC — ficam STALE se a tag mudar (re-solve = F6)."""
    rows = query(
        "SELECT h.hand_id, j.status FROM hands h JOIN hrc_jobs j ON j.hand_db_id = h.id "
        "WHERE h.site='GGPoker' AND h.tournament_number = %s AND h.played_at >= %s "
        "ORDER BY h.played_at ASC", (tn, boundary))
    return [{"hand_id": r["hand_id"], "hrc_status": r["status"]} for r in rows]


def _ft_get_review(tn):
    rows = query("SELECT * FROM ft_boundary_review WHERE tournament_number=%s", (tn,))
    return rows[0] if rows else None


def _ft_who(current_user) -> str:
    if isinstance(current_user, dict):
        return str(current_user.get("email") or current_user.get("id") or "api")
    return "api"


def _ft_upsert_review(tn, d, *, decision, decided_by, override_boundary=None, override_n=None):
    cc = d.get("cross_check") or {}
    status = _ft_map_status(d.get("status"), cc)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO ft_boundary_review (tournament_number, status, boundary, "
                "source, n_lobby, seats_first_hand, decision, override_boundary, "
                "override_n, decided_by, decided_at, updated_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW(),NOW()) "
                "ON CONFLICT (tournament_number) DO UPDATE SET status=EXCLUDED.status, "
                "boundary=EXCLUDED.boundary, source=EXCLUDED.source, "
                "n_lobby=EXCLUDED.n_lobby, seats_first_hand=EXCLUDED.seats_first_hand, "
                "decision=EXCLUDED.decision, override_boundary=EXCLUDED.override_boundary, "
                "override_n=EXCLUDED.override_n, decided_by=EXCLUDED.decided_by, "
                "decided_at=NOW(), updated_at=NOW()",
                (tn, status, d.get("boundary"), d.get("source"), d.get("n"),
                 cc.get("hh_seats"), decision, override_boundary, override_n, decided_by))
        conn.commit()
    finally:
        conn.close()


def _ft_mark_promoted(tn, decided_by):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE ft_boundary_review SET decision='promoted', "
                        "decided_by=%s, decided_at=NOW(), updated_at=NOW() "
                        "WHERE tournament_number=%s", (decided_by, tn))
        conn.commit()
    finally:
        conn.close()


_FT_BASE = ["icm", "icm-pko", "pos-pko", "pos-nko", "speed-racer"]


def _ft_change_count(tn, boundary) -> int:
    """Contagem LEVE (1 query) das mãos que mudariam: >= fronteira COM tag base-spot."""
    r = query(
        "SELECT count(*) AS n FROM hands WHERE site='GGPoker' AND tournament_number=%s "
        "AND played_at >= %s AND (discord_tags && %s OR hm3_tags && %s)",
        (tn, boundary, _FT_BASE, _FT_BASE))
    return r[0]["n"] if r else 0


def _ft_hrc_stale_count(tn, boundary) -> int:
    r = query(
        "SELECT count(*) AS n FROM hands h JOIN hrc_jobs j ON j.hand_db_id=h.id "
        "WHERE h.site='GGPoker' AND h.tournament_number=%s AND h.played_at >= %s",
        (tn, boundary))
    return r[0]["n"] if r else 0


def _ft_images(tn) -> dict:
    """TODAS as imagens que a app tem associadas ao torneio (regra 8 Jul), p/ o ensaio:
    (1) capturas de MESA (table_ss, img_b64) com captured_at + players_left lido — as
    que produziram a sequência que o Rui usa p/ decidir o Corrigir; (2) lobbys (sem
    imagem guardada → leitura + hora); (3) outras imagens ligadas às mãos (gold/replayer
    entries). Só URLs/metadados — read-only."""
    caps = query(
        "SELECT DISTINCT l.id AS ss_id, l.captured_at, l.players_left "
        "FROM table_ss_processing_log l JOIN hands h ON h.context_table_ss_id = l.id "
        "WHERE h.site='GGPoker' AND h.tournament_number=%s AND l.img_b64 IS NOT NULL "
        "ORDER BY l.captured_at", (tn,))
    table_ss = [{"ss_id": r["ss_id"], "image_url": f"/api/table-ss/image/{r['ss_id']}",
                 "captured_at": r["captured_at"].isoformat() if r["captured_at"] else None,
                 "players_left": r["players_left"]} for r in caps]
    lob = query(
        "SELECT posted_at, players_left, vision_json FROM lobby_processing_log "
        "WHERE tournament_number=%s ORDER BY posted_at", (tn,))
    lobby = [{"posted_at": r["posted_at"].isoformat() if r["posted_at"] else None,
              "players_left": r["players_left"],
              "open_tab": (r["vision_json"] or {}).get("open_tab"),
              "final_table_size": (r["vision_json"] or {}).get("final_table_size"),
              "note": "imagem não guardada"} for r in lob]
    other = query(
        "SELECT e.id AS ss_id, h.hand_id FROM entries e JOIN hands h ON h.entry_id = e.id "
        "WHERE h.site='GGPoker' AND h.tournament_number=%s "
        "AND (e.raw_json->>'img_b64') IS NOT NULL "
        "AND e.entry_type IN ('screenshot','replayer_link') ORDER BY h.played_at", (tn,))
    hand_imgs = [{"ss_id": r["ss_id"], "hand_id": r["hand_id"],
                  "image_url": f"/api/screenshots/image/{r['ss_id']}"} for r in other]
    return {"table_ss": table_ss, "lobby": lobby, "hand_images": hand_imgs}


def _ft_preview_for_tn(tn, full=False) -> dict:
    """LEVE por defeito (lista de todos os candidatos — só status/fronteira/contagens);
    `full=True` (um tn) traz o detalhe pesado: mãos que mudam (from→to), lista HRC
    stale, e a sequência da via-b. Evita o `propagate_ft` (double-compute) na lista."""
    d = compute_ft_boundary(tn)
    cc = d.get("cross_check") or {}
    boundary = d.get("boundary")
    rev = _ft_get_review(tn)
    out = {
        "tournament_number": tn,
        "status": _ft_map_status(d.get("status"), cc),
        "engine_status": d.get("status"), "source": d.get("source"),
        "boundary": boundary.isoformat() if boundary else None,
        "n_lobby": d.get("n"), "seats_first_hand": cc.get("hh_seats"),
        "cross_check": cc or None, "warnings": _ft_warnings(d, None),
        "decision": rev["decision"] if rev else "pending",
        "override_boundary": rev["override_boundary"].isoformat()
            if rev and rev.get("override_boundary") else None,
        "override_n": rev.get("override_n") if rev else None,
    }
    if boundary is None:
        out.update({"n_changes": 0, "hrc_stale_count": 0})
        if full:
            diag = via_b_diagnostics(tn)
            out.update({"changes": [], "hrc_stale": [], "via_b_diag": diag,
                        "warnings": _ft_warnings(d, diag), "images": _ft_images(tn)})
        return out
    if full:
        changes = propagate_ft(tn, dry_run=True).get("changed", [])
        hrc = _ft_hrc_stale(tn, boundary)
        diag = via_b_diagnostics(tn)
        out.update({"changes": changes, "n_changes": len(changes),
                    "hrc_stale": hrc, "hrc_stale_count": len(hrc),
                    "via_b_diag": diag, "warnings": _ft_warnings(d, diag),
                    "images": _ft_images(tn)})
    else:
        out["n_changes"] = _ft_change_count(tn, boundary)
        out["hrc_stale_count"] = _ft_hrc_stale_count(tn, boundary)
    return out


def _ft_partial_coverage(tn, boundary, n) -> bool:
    """COBERTURA PARCIAL da via-b: a fronteira ancorou num N pequeno (ex. 5) mas a FT
    arrancou MAIOR (houve mãos com > N sentados, <= FT_CAP, nos ~20 min antes) → o
    boundary perde as 1ªs mãos da FT. Visível na linha (não escondido)."""
    if not n or boundary is None:
        return False
    rows = query(
        "SELECT raw FROM hands WHERE site='GGPoker' AND tournament_number=%s "
        "AND played_at < %s AND played_at >= %s ORDER BY played_at",
        (tn, boundary, boundary - timedelta(minutes=20)))
    seats = [s for s in (count_hh_seats(r["raw"]) for r in rows) if isinstance(s, int)]
    return any(n < s <= FT_CAP for s in seats)


def _ft_candidate_list() -> list:
    """Lista dos candidatos (gate APERTADO: só sinal forte de FT → poucos), com o
    STATUS computado e a SECÇÃO: 'needs' (Precisam de ti — exige decisão), 'ready'
    (Prontas a aprovar — match limpo), 'done' (já promovido). Compute por tn é barato
    porque o gate é apertado. Ordena needs → ready → done, depois por dia."""
    tns = candidate_tns()
    if not tns:
        return []
    meta = {r["tn"]: r for r in query(
        "SELECT tournament_number AS tn, MAX(tournament_name) AS name, "
        "MIN(played_at)::date AS day, COUNT(*) AS n_hands "
        "FROM hands WHERE site='GGPoker' AND tournament_number = ANY(%s) "
        "GROUP BY tournament_number", (tns,))}
    dec = {r["tournament_number"]: r for r in query(
        "SELECT tournament_number, decision, decided_at FROM ft_boundary_review "
        "WHERE tournament_number = ANY(%s)", (tns,))}
    out = []
    for tn in tns:
        d = compute_ft_boundary(tn)
        cc = d.get("cross_check") or {}
        status = _ft_map_status(d.get("status"), cc)
        drow = dec.get(tn)
        decision = drow["decision"] if drow else "pending"
        # REVERSIBILIDADE do Dispensar: um 'dismissed' só volta a pending com sinal POSTERIOR
        # à dispensa (regra única `has_new_ft_signal`) — o Info PRÉ-EXISTENTE já não reacorda
        # (era o zombie). Não persiste no GET (só reflecte); o Rui volta a decidir.
        reactivated = False
        if decision == "dismissed" and _ft_dismiss_reactivated(
                tn, drow.get("decided_at") if drow else None):
            decision, reactivated = "pending", True
        boundary = d.get("boundary")
        if decision == "dismissed":
            section = "dismissed"  # Dispensados (sem FT — o Rui rebentou na bolha)
        elif decision == "promoted":
            section = "done"
        elif status == "match":
            section = "ready"      # match limpo → Prontas a aprovar
        else:
            section = "needs"      # none-com-sinal / mismatch / disagreement / ... → Precisam de ti
        m = meta.get(tn) or {}
        day = m.get("day")
        out.append({
            "tournament_number": tn, "tournament_name": m.get("name"),
            "day": day.isoformat() if day else None, "n_hands": m.get("n_hands"),
            "section": section, "status": status, "engine_status": d.get("status"),
            "source": d.get("source"),
            "boundary": boundary.isoformat() if boundary else None,
            "n": d.get("n"), "seats_first_hand": cc.get("hh_seats"), "match": cc.get("match"),
            "partial_coverage": _ft_partial_coverage(tn, boundary, d.get("n")) if (section == "ready") else False,
            "decision": decision, "reactivated": reactivated,
        })
    order = {"needs": 0, "ready": 1, "done": 2, "dismissed": 3}
    out.sort(key=lambda r: (order.get(r["section"], 4), r["day"] or ""))
    return out


def _ft_dismiss_reactivated(tn, decided_at=None) -> bool:
    """Um torneio dispensado ganhou sinal POSTERIOR à dispensa? Regra ÚNICA partilhada com o
    refresh (`has_new_ft_signal`): tag manual -ft (override) OU print Info com `posted_at >
    decided_at`. O Info PRÉ-EXISTENTE já NÃO reacorda (#FT-ZOMBIE-DISMISS-REACTIVATION, Rui
    10 Jul). Só se chama para os 'dismissed'."""
    from app.services.ft_boundary import has_new_ft_signal
    return has_new_ft_signal(tn, decided_at)


class FtTnBody(BaseModel):
    tournament_number: str


class FtCorrectBody(BaseModel):
    tournament_number: str
    override_boundary: Optional[datetime] = None
    override_n: Optional[int] = None


class FtPromoteBody(BaseModel):
    tournament_number: str
    confirm: bool = False


@router.get("/ft/preview")
def ft_preview(tn: Optional[str] = Query(None, description="Um torneio; omisso = todos os candidatos"),
               current_user=Depends(require_auth_or_api_key)):
    """Ensaio dry-run da fronteira FT (F3), SO LEITURA. Por torneio: fronteira+via
    (incl. fonte 0/manual), N + sentados da 1a mao, cross-check, maos que mudariam
    (from->to), avisos do fallback (outlier/sequencia) e maos HRC stale afetadas.
    Um `tn` -> detalhe FULL; sem `tn` -> lista LEVE de todos os candidatos (o detalhe
    pesado por torneio pede-se com `?tn=`)."""
    if tn:
        return {"tournaments": [_ft_preview_for_tn(tn, full=True)], "count": 1}
    lst = _ft_candidate_list()
    return {"candidates": lst, "count": len(lst)}


@router.post("/ft/confirm")
def ft_confirm(body: FtTnBody, current_user=Depends(require_auth_or_api_key)):
    """FIXA a fronteira COMPUTADA (decision='confirmed'). NAO promove — a escrita e o
    2o passo (POST /ft/promote). Devolve o ensaio actualizado."""
    d = compute_ft_boundary(body.tournament_number)
    _ft_upsert_review(body.tournament_number, d, decision="confirmed",
                      decided_by=_ft_who(current_user))
    return {"ok": True, "preview": _ft_preview_for_tn(body.tournament_number)}


@router.post("/ft/correct")
def ft_correct(body: FtCorrectBody, current_user=Depends(require_auth_or_api_key)):
    """CORRIGE a fronteira a mao (override_boundary/override_n; decision='corrected').
    NAO promove. Devolve o ensaio actualizado."""
    ob = body.override_boundary
    if ob is not None and ob.tzinfo is not None:   # convencao Lisboa-naive
        ob = ob.replace(tzinfo=None)
    d = compute_ft_boundary(body.tournament_number)
    _ft_upsert_review(body.tournament_number, d, decision="corrected",
                      override_boundary=ob, override_n=body.override_n,
                      decided_by=_ft_who(current_user))
    return {"ok": True, "preview": _ft_preview_for_tn(body.tournament_number)}


@router.post("/ft/promote")
def ft_promote(body: FtPromoteBody, current_user=Depends(require_auth_or_api_key)):
    """2o passo EXPLICITO — a escrita. Exige decisao previa (confirm/correct). dry_run
    por defeito (confirm=false -> plano); confirm=true escreve as tags (base->-ft) das
    maos >= fronteira e marca decision='promoted'. Usa a fronteira CORRIGIDA se
    decision='corrected'."""
    tn = body.tournament_number
    rev = _ft_get_review(tn)
    if not rev or rev["decision"] not in ("confirmed", "corrected"):
        raise HTTPException(422, "decide primeiro (POST /ft/confirm ou /ft/correct) antes de promover")
    override = rev["override_boundary"] if rev["decision"] == "corrected" else None
    plan = propagate_ft(tn, dry_run=not body.confirm, boundary_override=override)
    if not body.confirm:
        return {"dry_run": True, "plan": plan}
    _ft_mark_promoted(tn, _ft_who(current_user))
    return {"dry_run": False, "result": plan}


@router.post("/ft/dismiss")
def ft_dismiss(body: FtTnBody, current_user=Depends(require_auth_or_api_key)):
    """DISPENSAR ("sem FT") — o Rui rebentou na bolha, não fez mesa final. Escreve
    **APENAS** na `ft_boundary_review` (decision='dismissed' + decided_by/decided_at)
    via `_ft_upsert_review`. **NÃO toca nas mãos** do torneio, **NÃO** remove/altera
    tags (icm/nota/... = estudo de bolha válido, ficam intactas), **NÃO** mexe em
    study_state/vilões/nada fora da tabela de revisão. Sai de "Precisam de ti"; o
    /summary deixa de o contar. Reversível (ver `_ft_dismiss_reactivated`)."""
    d = compute_ft_boundary(body.tournament_number)
    _ft_upsert_review(body.tournament_number, d, decision="dismissed",
                      decided_by=_ft_who(current_user))
    return {"ok": True}


# ═══ APA §B.6 Fase 3 — propagacao de nomes por hash: preview + quarentena ═════

from app.services import name_propagation as _np


def _np_tagged_gg_tns() -> list:
    rows = query("""SELECT DISTINCT tournament_number FROM hands
        WHERE site='GGPoker' AND played_at >= '2026-01-01' AND tournament_number IS NOT NULL
          AND (COALESCE(array_length(hm3_tags,1),0)>0 OR COALESCE(array_length(discord_tags,1),0)>0)""")
    return [r["tournament_number"] for r in rows]


def _np_load_hands(tn) -> list:
    return [dict(r) for r in query("""SELECT id, hand_id, site, raw, player_names, hm3_tags, discord_tags,
        played_at FROM hands WHERE site='GGPoker' AND tournament_number=%s AND played_at >= '2026-01-01'""", (tn,))]


def _images_for_hands(db_ids: list) -> list:
    """TODAS as imagens que a app tem para um conjunto de mãos (por db_id), p/ o painel
    de conflitos de nomes: capturas de MESA (table_ss, img_b64) + outras imagens ligadas
    às mãos (gold/replayer). Só URLs/metadados — read-only. Espelha a regra 8 Jul da FT
    (é com as imagens que o Rui reconhece o jogador), mas filtrada às mãos do lado."""
    if not db_ids:
        return []
    out = []
    caps = query(
        "SELECT DISTINCT l.id AS ss_id, l.captured_at, h.hand_id "
        "FROM table_ss_processing_log l JOIN hands h ON h.context_table_ss_id = l.id "
        "WHERE h.id = ANY(%s) AND l.img_b64 IS NOT NULL ORDER BY l.captured_at", (db_ids,))
    for r in caps:
        out.append({"image_url": f"/api/table-ss/image/{r['ss_id']}", "kind": "table_ss",
                    "hand_id": r["hand_id"],
                    "captured_at": r["captured_at"].isoformat() if r["captured_at"] else None})
    other = query(
        "SELECT e.id AS ss_id, h.hand_id FROM entries e JOIN hands h ON h.entry_id = e.id "
        "WHERE h.id = ANY(%s) AND (e.raw_json->>'img_b64') IS NOT NULL "
        "AND e.entry_type IN ('screenshot','replayer_link') ORDER BY h.played_at", (db_ids,))
    for r in other:
        out.append({"image_url": f"/api/screenshots/image/{r['ss_id']}", "kind": "hand",
                    "hand_id": r["hand_id"]})
    return out


def _np_preview_for_tn(tn) -> dict:
    hands = _np_load_hands(tn)
    clean, quar = _np.build_name_map(hands)
    conn = get_conn()
    try:
        decisions = _np._load_decisions(conn, tn)
    finally:
        conn.close()
    clean, quar = _np._apply_decisions_to_map(clean, quar, decisions)
    plan = _np.propagation_plan(hands, clean)
    return {
        "tournament_number": tn,
        "map_size": len(clean),
        "quarantine": quar,
        "stats": plan["stats"],
        "changes": plan["changes"],
    }


@router.get("/names/preview")
def np_preview(tn: Optional[str] = Query(None), current_user=Depends(require_auth_or_api_key)):
    """Ensaio da propagacao de nomes (Fase 3), SO LEITURA. Com `tn` -> detalhe (mapa,
    quarentena, maos que mudam). Sem `tn` -> agregado sobre todos os GG tagados."""
    if tn:
        return _np_preview_for_tn(tn)
    agg = {"tournaments": 0, "with_map": 0, "fills": 0, "resolved": 0, "blanks": 0,
           "quarantine": 0, "tagged": 0}
    per = []
    for t in _np_tagged_gg_tns():
        p = _np_preview_for_tn(t)
        s = p["stats"]; nq = len(p["quarantine"])
        agg["tournaments"] += 1
        agg["with_map"] += 1 if p["map_size"] else 0
        agg["fills"] += s["fills_total"]; agg["resolved"] += s["hands_resolved_after"]
        agg["blanks"] += s["blank_hashes"]; agg["quarantine"] += nq; agg["tagged"] += s["tagged_hands"]
        if s["fills_total"] or nq:
            per.append({"tournament_number": t, "fills": s["fills_total"],
                        "quarantine": nq, "hands_with_fills": s["hands_with_fills"]})
    return {"aggregate": agg, "tournaments": per}


@router.get("/names/quarantine")
def np_quarantine(current_user=Depends(require_auth)):
    """Lista as entradas de quarentena de nomes PENDENTES (por torneio) para o painel.
    Cada item traz os DOIS lados do conflito (`sides`): por candidato, as mãos onde
    aparece (com fonte forte/fraca) + as imagens dessas mãos — é com os dois lados lado
    a lado (e as imagens) que o Rui reconhece qual dos lugares é o jogador verdadeiro."""
    rows = query("""SELECT tournament_number, kind, conflict_key, candidates, hands, decision,
                           chosen_name, chosen_hash, decided_by, decided_at
                    FROM name_quarantine_review WHERE decision='pending'
                    ORDER BY tournament_number, kind""")
    hcache: dict = {}

    def hands_of(tn):
        if tn not in hcache:
            hcache[tn] = _np_load_hands(tn)
        return hcache[tn]

    items = []
    for r in rows:
        it = dict(r)
        hs = hands_of(it["tournament_number"])
        sides = _np.conflict_sides(hs, it)
        for s in sides:
            s["images"] = _images_for_hands(s.pop("db_ids", []))
        it["sides"] = sides
        it["reentry"] = _np.reentry_hint(hs, it)   # pré-selecciona "Mesma pessoa (re-entrada)"
        items.append(it)
    return {"items": items, "count": len(items)}


class NpDecisionBody(BaseModel):
    tournament_number: str
    kind: str
    conflict_key: str
    chosen_name: Optional[str] = None
    chosen_hash: Optional[str] = None


def _np_decide(body, decision, who):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""UPDATE name_quarantine_review
                SET decision=%s, chosen_name=%s, chosen_hash=%s, decided_by=%s,
                    decided_at=(now() at time zone 'utc'), updated_at=(now() at time zone 'utc')
                WHERE tournament_number=%s AND kind=%s AND conflict_key=%s""",
                (decision, body.chosen_name, body.chosen_hash, who,
                 body.tournament_number, body.kind, body.conflict_key))
            if cur.rowcount == 0:
                raise HTTPException(404, "entrada de quarentena nao encontrada")
        conn.commit()
    finally:
        conn.close()
    res = _np.refresh_name_propagation(body.tournament_number, auto_write=True)
    return {"ok": True, "result": res}


@router.post("/names/choose")
def np_choose(body: NpDecisionBody, current_user=Depends(require_auth_or_api_key)):
    """ESCOLHER o nome certo de um conflito -> entra no mapa e propaga. Para name_2_hash,
    passar `chosen_hash` (qual dos lugares recebe o nome; o outro fica branco)."""
    if not body.chosen_name:
        raise HTTPException(400, "chosen_name obrigatorio")
    if body.kind == "name_2_hash" and not body.chosen_hash:
        raise HTTPException(400, "name_2_hash exige chosen_hash")
    return _np_decide(body, "chosen", _ft_who(current_user))


@router.post("/names/merge")
def np_merge(body: NpDecisionBody, current_user=Depends(require_auth_or_api_key)):
    """MERGE de variantes OCR (same_hash) -> escolhe o canonico e propaga."""
    if body.kind != "same_hash" or not body.chosen_name:
        raise HTTPException(400, "merge so em same_hash + chosen_name")
    return _np_decide(body, "merged", _ft_who(current_user))


@router.post("/names/dismiss")
def np_dismiss(body: NpDecisionBody, current_user=Depends(require_auth_or_api_key)):
    """DISPENSAR -> o(s) hash(es) ficam BRANCOS (honesto). Escreve so na review."""
    return _np_decide(body, "dismissed", _ft_who(current_user))


@router.post("/names/reentry")
def np_reentry(body: NpDecisionBody, current_user=Depends(require_auth_or_api_key)):
    """MESMA PESSOA (RE-ENTRADA) -> o nome fica valido nos DOIS hashes (entradas
    distintas do mesmo humano). So `name_2_hash`. Sai da quarentena; ambos os hashes
    elegiveis p/ propagacao. NAO funde registos (stacks/maos/stats separados; so o
    nome e partilhado). O bounty e POR ENTRADA (re-entrada volta a base). Ver
    DESANON_ANATOMIA §3.3."""
    if body.kind != "name_2_hash":
        raise HTTPException(400, "re-entrada so em name_2_hash")
    if not body.chosen_name:
        body.chosen_name = body.conflict_key    # o nome do conflito
    return _np_decide(body, "reentry", _ft_who(current_user))


@router.get("/names/hand-status")
def np_hand_status(hand_id: str = Query(...), current_user=Depends(require_auth)):
    """OBRA 3 — selo "nome em revisao" na mao: esta mao esta envolvida nalgum conflito
    de nomes PENDENTE? Devolve {in_conflict, conflicts:[{tournament_number, kind,
    conflict_key}]}. O detalhe da mao mostra o selo + link p/ a Saude GG; some quando
    o conflito se resolve (a review deixa de estar 'pending')."""
    rows = query("""SELECT tournament_number, kind, conflict_key FROM name_quarantine_review
                    WHERE decision='pending' AND hands @> %s::jsonb""",
                 (json.dumps([hand_id]),))
    return {"in_conflict": bool(rows), "conflicts": [dict(r) for r in rows]}


class NpApplyBody(BaseModel):
    tournament_number: Optional[str] = None
    dry_run: bool = False


@router.post("/names/apply")
def np_apply(body: NpApplyBody, current_user=Depends(require_auth_or_api_key)):
    """Aplica a propagacao LIMPA (auto-write dos casos sem ambiguidade). Um `tn` ou
    todos os GG tagados. dry_run=true -> so o plano agregado, nao escreve."""
    tns = [body.tournament_number] if body.tournament_number else _np_tagged_gg_tns()
    total = {"tournaments": 0, "hands_written": 0, "fills": 0, "quarantine_pending": 0}
    for t in tns:
        res = _np.refresh_name_propagation(t, auto_write=not body.dry_run)
        total["tournaments"] += 1
        total["hands_written"] += res.get("hands_written", 0)
        total["fills"] += res.get("fills_total", 0)
        total["quarantine_pending"] += res.get("quarantine_pending", 0)
    return {"dry_run": body.dry_run, **total}


# ── CURA verde-KO — scan read-only de CONTAMINAÇÃO (rede de verificação) ──────
@router.get("/eliminated-crown-scan")
def eliminated_crown_scan(current_user=Depends(require_auth_or_api_key)):
    """READ-ONLY. Verifica a cura verde-KO: seats ELIMINADOS (sinal HH: all-in e perdeu).

    ★ CRIVO VERDADEIRO (`vision_origin_contamination`): bustado com coroa >0 cuja
    proveniência NÃO é 'green_ko' (derivada do verde pelo chokepoint) = coroa de
    origem-Vision = contaminação. **Alvo pós-cura+reimporte: 0.** Apanha TODOS os
    casos, incluindo os de valor ÚNICO que a heurística 'forte' não vê. É a garantia
    estrutural da cura (todo bustado passa pelo chokepoint → verde-derivado OU NULL).

    Proxies visíveis (subconjunto do crivo): `strong` = coroa >base÷2 igual à de outro
    seat vivo (quase-certo veneno); `soft` = restante coroa origem-Vision (única/≤base÷2).
    `review` = já marcado 'por rever' (guarda ativa — OK); `green_ko` = derivado do verde
    (curado — OK, NÃO conta no crivo). NADA escreve."""
    base = {r["tournament_number"]: float(r["buy_in_bounty"]) for r in query(
        "SELECT tournament_number, buy_in_bounty FROM tournament_summaries "
        "WHERE site='GGPoker' AND buy_in_bounty IS NOT NULL")}
    rows = query(
        "SELECT hand_id, tournament_number, tournament_name, raw, "
        "       all_players_actions AS apa, player_names AS pn "
        "  FROM hands "
        " WHERE site='GGPoker' AND played_at >= '2026-01-01' "
        "   AND player_names->>'match_method' IS NOT NULL "
        "   AND player_names->'players_list' IS NOT NULL "
        # SÓ-TAGADAS (mãos que o Rui marcou in-game p/ rever): o crivo, como a cura,
        # só vale nas tagadas (APA §B.6). Não-tagadas serão apagadas no reimporte.
        "   AND (COALESCE(array_length(hm3_tags,1),0)>0 "
        "        OR COALESCE(array_length(discord_tags,1),0)>0)")
    vision_origin, strong, soft, review, green_ko = [], [], [], [], []
    for r in rows:
        apa = r["apa"] if isinstance(r["apa"], dict) else json.loads(r["apa"] or "{}")
        pn = r["pn"] if isinstance(r["pn"], dict) else json.loads(r["pn"] or "{}")
        busted = busted_real_names(r["raw"], apa)
        if not busted:
            continue
        pl = pn.get("players_list") or []
        crowns = {}
        for p in pl:
            try:
                bv = float(p.get("bounty_value_usd") or 0)
            except (TypeError, ValueError):
                bv = 0.0
            if bv > 0:
                crowns.setdefault(round(bv, 2), []).append(p.get("name"))
        b = base.get(r["tournament_number"])
        floor = b / 2 if b else None
        for p in pl:
            nm = p.get("name")
            if nm not in busted:
                continue
            try:
                bv = float(p.get("bounty_value_usd") or 0)
            except (TypeError, ValueError):
                bv = 0.0
            source = p.get(BOUNTY_SOURCE_KEY)
            item = {"hand_id": r["hand_id"], "tournament_name": r["tournament_name"],
                    "name": nm, "crown": bv, "floor": floor,
                    "review": p.get(BOUNTY_REVIEW_KEY), "source": source}
            if bv <= 0:
                if p.get(BOUNTY_REVIEW_KEY):
                    review.append(item)      # NULL + 'por rever' (guarda ativa — OK)
                continue                     # senão: eliminado sem coroa (limpo)
            if source == SOURCE_GREEN_KO:
                green_ko.append(item)        # verde-derivado (curado) — NÃO conta no crivo
                continue
            # coroa >0 num bustado SEM 'green_ko' = origem-Vision = CONTAMINAÇÃO (crivo).
            vision_origin.append(item)
            others = [n for n in crowns.get(round(bv, 2), []) if n != nm]
            if others and floor is not None and bv > floor + 0.001:
                item["equal_to"] = others
                strong.append(item)
            else:
                soft.append(item)
    return {"scanned_hands": len(rows),
            # ★ crivo verdadeiro da cura: tem de ser 0 pós-cura+reimporte.
            "vision_origin_contamination": len(vision_origin),
            # GATE DURO (decisão Web 9 Jul): >0 após reimporte OU após qualquer ingest GG
            # = PARAR + investigar + corrigir. NUNCA "dado por curado" com o scan >0.
            "gate": "hard: vision_origin_contamination>0 => PARAR+investigar (nunca curado)",
            "counts": {"strong": len(strong), "soft": len(soft),
                       "review": len(review), "green_ko": len(green_ko)},
            "vision_origin": vision_origin,
            "strong": strong, "soft": soft, "review": review, "green_ko": green_ko}


# ── CURA verde-KO — apply controlado do funil às TAGADAS (demonstração do crivo→0) ──
@router.post("/eliminated-scrub-apply")
def eliminated_scrub_apply(
    confirm: bool = Query(False),
    hand_ids: Optional[str] = Query(None),
    limit: int = Query(300, ge=1, le=1000),
    current_user=Depends(require_auth_or_api_key),
):
    """Aplica o funil (`scrub_and_persist`) às mãos GG TAGADAS: verde-KO (seat HH-bustado) E
    guarda vivo-$0 (KO + vivo + coroa $0 → NULL+'por rever'; `kind` distingue no plano).
    `confirm=false` (default) = ENSAIO: mostra o que mudaria (por mão: seat + coroa-atual →
    NULL/'por rever'), NÃO escreve. `confirm=true` = escreve, MUST-only (sem verde — o verde
    vive no ingest com Vision fresca; aqui é demonstração do crivo→0 na BD atual, que o
    reimporte apaga). Só-tagadas (o wrapper valida). Idempotente. `hand_ids` limita ao teste."""
    import copy as _copy
    from app.services.eliminated_bounty import (
        busted_real_names, scrub_eliminated_bounties, scrub_and_persist, BOUNTY_REVIEW_KEY,
    )
    ids = [h.strip() for h in hand_ids.split(",") if h.strip()] if hand_ids else None
    where = "AND h.hand_id = ANY(%s)" if ids else ""
    params = (ids,) if ids else tuple()
    rows = query(
        "SELECT h.id, h.hand_id, h.raw, h.all_players_actions AS apa, h.player_names AS pn, "
        "       ts.buy_in_bounty AS bounty_base, (ts.tournament_number IS NOT NULL) AS has_ts "
        "  FROM hands h "
        "  LEFT JOIN tournament_summaries ts "
        "    ON ts.site='GGPoker' AND ts.tournament_number = h.tournament_number "
        " WHERE h.site='GGPoker' AND h.played_at >= '2026-01-01' "
        "   AND h.player_names->>'match_method' IS NOT NULL "
        "   AND (COALESCE(array_length(h.hm3_tags,1),0)>0 "
        "        OR COALESCE(array_length(h.discord_tags,1),0)>0) " + where, params)
    changed_hands = changed_seats = written = 0
    plan = []
    for r in rows[:limit]:
        apa = r["apa"] if isinstance(r["apa"], dict) else json.loads(r["apa"] or "{}")
        pn = r["pn"] if isinstance(r["pn"], dict) else json.loads(r["pn"] or "{}")
        busted = busted_real_names(r["raw"], apa)
        base = r.get("bounty_base")
        is_ko = bool(base and float(base) > 0)
        has_ts_no_bounty = bool(r.get("has_ts")) and not is_ko      # vanilla (TS sem bounty)
        if not busted and not is_ko and not has_ts_no_bounty:
            continue
        # snapshot — CÓPIA scrubada (verde-KO + guarda vivo-$0 + guarda vanilla).
        apa_c, pn_c = _copy.deepcopy(apa), _copy.deepcopy(pn)
        n = scrub_eliminated_bounties(apa_c, pn_c, r["raw"], None, tagged=True,
                                      bounty_base=base, has_ts_no_bounty=has_ts_no_bounty)
        if not n:
            continue
        seats = []
        for k, v in apa.items():
            if k == "_meta" or not isinstance(v, dict):
                continue
            nm = v.get("real_name") or k
            old = v.get("bounty_value_usd")
            vc = apa_c.get(k, {})
            new = vc.get("bounty_value_usd")
            if old != new:
                rev = vc.get(BOUNTY_REVIEW_KEY)
                kind = ("eliminated" if nm in busted
                        else "live_zero" if rev else "vanilla_null")
                seats.append({"name": nm, "from": old, "to": new, "kind": kind, "review": rev})
        if not seats:
            continue
        changed_hands += 1
        changed_seats += len(seats)
        if len(plan) < 60:
            plan.append({"hand_id": r["hand_id"], "seats": seats})
        if confirm:
            written += scrub_and_persist(r["id"])   # escreve (MUST-only)
    return {"dry_run": not confirm, "tagged_scanned": min(len(rows), limit),
            "changed_hands": changed_hands, "changed_seats": changed_seats,
            "seats_written": written if confirm else 0, "plan": plan}


# ── GATE da guarda VIVO-$0 (irmão do eliminated-crown-scan) ───────────────────
@router.get("/live-crown-zero-scan")
def live_crown_zero_scan(current_user=Depends(require_auth_or_api_key)):
    """GATE da guarda vivo-$0 (só-tagadas, GG KO). Reporta jogadores VIVOS (não bustados
    pela HH) com coroa $0 em torneios KO (buy_in_bounty do TS > 0). Dois baldes:
    - `silent_zero` = coroa $0/null SEM bounty_review → CONTAMINAÇÃO (grava $0 em silêncio).
      GATE DURO: >0 após reimporte OU qualquer ingest GG = PARAR + investigar + corrigir.
    - `review` = $0 com review='live_crown_read_zero' → honesto (guarda activa — OK).
    Torneios não-KO ou sem TS ficam FORA (a guarda não se aplica). NADA escreve."""
    base = {r["tournament_number"]: float(r["buy_in_bounty"]) for r in query(
        "SELECT tournament_number, buy_in_bounty FROM tournament_summaries "
        "WHERE site='GGPoker' AND buy_in_bounty IS NOT NULL AND buy_in_bounty > 0")}
    rows = query(
        "SELECT hand_id, tournament_number, tournament_name, raw, "
        "       all_players_actions AS apa, player_names AS pn "
        "  FROM hands "
        " WHERE site='GGPoker' AND played_at >= '2026-01-01' "
        "   AND player_names->>'match_method' IS NOT NULL "
        "   AND player_names->'players_list' IS NOT NULL "
        "   AND (COALESCE(array_length(hm3_tags,1),0)>0 "
        "        OR COALESCE(array_length(discord_tags,1),0)>0)")
    scanned = 0
    silent, review = [], []
    for r in rows:
        b = base.get(r["tournament_number"])
        if not b:                       # não-KO ou sem TS → guarda não se aplica
            continue
        scanned += 1
        apa = r["apa"] if isinstance(r["apa"], dict) else json.loads(r["apa"] or "{}")
        pn = r["pn"] if isinstance(r["pn"], dict) else json.loads(r["pn"] or "{}")
        busted = busted_real_names(r["raw"], apa)
        for p in pn.get("players_list") or []:
            nm = p.get("name")
            if not nm or nm in busted:
                continue                # eliminado = verde-KO (outro crivo)
            try:
                bv = float(p.get("bounty_value_usd") or 0)
            except (TypeError, ValueError):
                bv = 0.0
            if bv > 0:
                continue
            item = {"hand_id": r["hand_id"], "tournament_name": r["tournament_name"],
                    "name": nm, "review": p.get(BOUNTY_REVIEW_KEY)}
            if p.get(BOUNTY_REVIEW_KEY):
                review.append(item)     # honesto (guarda activa)
            else:
                silent.append(item)     # coroa $0 gravada em silêncio = contaminação
    return {"scanned_ko_tagged_hands": scanned,
            # ★ crivo da guarda vivo-$0: tem de ser 0 pós-reimporte.
            "silent_zero_contamination": len(silent),
            "gate": "hard: silent_zero_contamination>0 => PARAR+investigar (nunca curado)",
            "counts": {"silent": len(silent), "review": len(review)},
            "silent_zero": silent, "review": review}


# ── GATE da guarda VANILLA (#SPURIOUS-CROWN-NON-KO) ───────────────────────────
@router.get("/spurious-crown-non-ko-scan")
def spurious_crown_non_ko_scan(current_user=Depends(require_auth_or_api_key)):
    """GATE da guarda vanilla (só-tagadas, GG). Reporta mãos de torneios com TS a dizer SEM
    bounty (buy_in_bounty nulo/0) mas com ≥1 lugar com coroa >0 — coroa INVENTADA pela Vision
    num vanilla (raiz: `table_ss_deanon._seats_to_vision_data` copia `bounty_usd` sem gate; o
    funil anula). GATE DURO: >0 pós-reimporte OU pós-ingest GG = PARAR + investigar. NADA escreve."""
    vanilla_tns = {r["tournament_number"] for r in query(
        "SELECT tournament_number FROM tournament_summaries "
        "WHERE site='GGPoker' AND (buy_in_bounty IS NULL OR buy_in_bounty = 0)")}
    rows = query(
        "SELECT hand_id, tournament_number, tournament_name, player_names AS pn "
        "  FROM hands "
        " WHERE site='GGPoker' AND played_at >= '2026-01-01' "
        "   AND player_names->>'match_method' IS NOT NULL "
        "   AND player_names->'players_list' IS NOT NULL "
        "   AND (COALESCE(array_length(hm3_tags,1),0)>0 "
        "        OR COALESCE(array_length(discord_tags,1),0)>0)")
    hits, scanned = [], 0
    for r in rows:
        if r["tournament_number"] not in vanilla_tns:
            continue                    # não-vanilla ou sem TS → fora do âmbito da guarda
        scanned += 1
        pn = r["pn"] if isinstance(r["pn"], dict) else json.loads(r["pn"] or "{}")
        seats = []
        for p in pn.get("players_list") or []:
            try:
                bv = float(p.get("bounty_value_usd") or 0)
            except (TypeError, ValueError):
                bv = 0.0
            if bv > 0:
                seats.append({"name": p.get("name"), "crown": bv})
        if seats:
            hits.append({"hand_id": r["hand_id"], "tournament_name": r["tournament_name"],
                         "seats": seats})
    return {"scanned_vanilla_tagged_hands": scanned,
            # ★ crivo da guarda vanilla: tem de ser 0 pós-reimporte.
            "spurious_crown_contamination": len(hits),
            "gate": "hard: spurious_crown_contamination>0 => PARAR+investigar (nunca curado)",
            "hits": hits}


@router.post("/crowns/test-reread")
def crowns_test_reread(payload: dict = Body(...),
                       current_user=Depends(require_auth_or_api_key)):
    """ENSAIO read-only (#FLAME-AS-CROWN prompt novo 11 Jul) — teste de aceitação
    do Rui. Re-lê a Vision com o prompt ATUAL (novo, placa de $) sobre a imagem
    JÁ GUARDADA de cada mão e devolve os bounties por seat + o efeito da guarda
    (base÷2 + grelha). **NÃO escreve NADA** na BD. body: {"hand_ids": [...]}."""
    import base64
    from app.services.table_ss_vision import (
        extract_table_ss_json, parse_and_validate_table_ss_json)
    from app.routers.screenshot import (
        _extract_hand_data_from_image_claude, _parse_vision_response)
    from app.services.table_ss_deanon import _guard_suspect_crowns
    hand_ids = payload.get("hand_ids") or []
    out = []
    for hid in hand_ids:
        rows = query(
            "SELECT h.id, h.hand_id, h.tournament_number tn, h.entry_id, "
            "  h.context_table_ss_id ctx, (h.player_names->>'match_method') mm, "
            "  ts.buy_in_bounty base "
            "FROM hands h LEFT JOIN tournament_summaries ts "
            "  ON ts.site='GGPoker' AND ts.tournament_number=h.tournament_number "
            "WHERE h.hand_id=%s", (hid,))
        if not rows:
            out.append({"hand_id": hid, "error": "not found"}); continue
        r = rows[0]
        base = float(r["base"]) if r["base"] is not None else None
        img_b64 = None; src = None
        if r["ctx"]:
            ir = query("SELECT img_b64 FROM table_ss_processing_log WHERE id=%s", (r["ctx"],))
            img_b64 = ir[0]["img_b64"] if ir and ir[0]["img_b64"] else None
            src = "table_ss"
        if not img_b64 and r["entry_id"]:
            ir = query("SELECT raw_json->>'img_b64' b FROM entries WHERE id=%s", (r["entry_id"],))
            img_b64 = ir[0]["b"] if ir and ir[0]["b"] else None
            src = "gold"
        if not img_b64:
            out.append({"hand_id": hid, "error": "sem imagem guardada"}); continue
        try:
            img_bytes = base64.b64decode(img_b64)
        except Exception as e:
            out.append({"hand_id": hid, "error": f"decode: {e}"}); continue
        seats = []
        if src == "table_ss":
            raw = extract_table_ss_json(img_bytes, "image/png")
            data = parse_and_validate_table_ss_json(raw) if raw else None
            for s in (data or {}).get("seats", []):
                seats.append({"name": s.get("nick"), "bounty": s.get("bounty_usd"), "vpip": None})
        else:
            text = _extract_hand_data_from_image_claude(img_bytes, "image/png")
            data = _parse_vision_response(text) if text else {}
            for s in data.get("players_list", []):
                seats.append({"name": s.get("name"), "bounty": s.get("bounty_value_usd"),
                              "vpip": s.get("bounty_pct")})
        # guarda em ENSAIO (cópia; não toca BD)
        preview = [{"name": x["name"], "bounty_value_usd": x["bounty"]} for x in seats]
        guard = _guard_suspect_crowns(preview, r["tn"]) if base else {"below_half": 0, "off_grid": 0}
        gmap = {p["name"]: p for p in preview}
        for x in seats:
            gp = gmap.get(x["name"], {})
            x["after_guard"] = gp.get("bounty_value_usd", x["bounty"])
            x["crown_review"] = gp.get("crown_review")
        out.append({"hand_id": hid, "mm": r["mm"], "src": src, "base": base,
                    "n_seats": len(seats), "seats": seats, "guard": guard})
    return {"results": out}


@router.get("/flame-as-crown-scan")
def flame_as_crown_scan(current_user=Depends(require_auth_or_api_key)):
    """4º GATE das coroas (11 Jul) — chama-lida-como-coroa. Reusa a fonte única
    `detect_bounty_below_half`: mãos GG PKO/KO cuja coroa gravada é < base÷2 (a
    Vision leu a chama VPIP % em vez da coroa $). Bounty-quality passa a critério
    de aceitação, ao lado dos 3 gates (vision_origin/silent_zero/spurious). GATE
    DURO: `flame_as_crown_contamination` tem de ser 0 pós-reimporte/pós-cura.
    Seats com `bounty_confirmed` (exceção manual do Rui) NÃO contam. NADA escreve."""
    from app.services.queue_export import TS_GATED_FORMATS, detect_bounty_below_half
    rows = query(
        "SELECT h.hand_id, h.tournament_name, h.player_names AS pn, ts.buy_in_bounty AS base "
        "  FROM hands h JOIN tournament_summaries ts "
        "    ON ts.site='GGPoker' AND ts.tournament_number = h.tournament_number "
        " WHERE h.site='GGPoker' AND h.played_at >= '2026-01-01' "
        "   AND ts.buy_in_bounty IS NOT NULL "
        "   AND lower(COALESCE(h.tournament_format,'')) = ANY(%s)",
        (list(TS_GATED_FORMATS),),
    )
    hits, scanned = [], 0
    for r in rows:
        pn = r["pn"] if isinstance(r["pn"], dict) else json.loads(r["pn"] or "{}")
        if not (pn.get("players_list")):
            continue
        scanned += 1
        below = detect_bounty_below_half(pn, r["base"])
        if below:
            hits.append({"hand_id": r["hand_id"], "tournament_name": r["tournament_name"],
                         "floor": below[0]["floor"],
                         "seats": [{"name": b["name"], "value": b["value"]} for b in below]})
    return {"scanned_gg_pko_hands": scanned,
            # ★ 4º gate: tem de ser 0 pós-reimporte/pós-cura.
            "flame_as_crown_contamination": len(hits),
            "gate": "hard: flame_as_crown_contamination>0 => PARAR+investigar (chama lida como coroa)",
            "hits": hits[:200]}


# ══════════════════════════════════════════════════════════════════════════════
# RAIZ 2 (11 Jul) — resolver de EDIÇÕES: crivo + quarentena + decisão manual.
# GG-only (a Winamax identifica o torneio na própria HH; sem edições repetidas
# no mesmo dia — decisão do Rui). NADA no funil das coroas nem no watcher.
# ══════════════════════════════════════════════════════════════════════════════

_LOBBY_SOURCE_PREFIXES = (
    "discord_lobby_vision:", "reconcile_lobby_vision:", "file_lobby_vision:",
)


def _reresolve_lobby_row(row: dict):
    """Re-corre o resolver (com desambiguação de edições) sobre uma row de
    lobby_processing_log usando o vision_json guardado. Devolve ((tn, cands,
    tier), vj). Read-only."""
    from app.services import tournament_resolver as TR
    from app.utils.timezones import utc_to_lisbon_naive
    vj = row.get("vision_json") or {}
    if isinstance(vj, str):
        vj = json.loads(vj or "{}")
    site = row.get("site") or vj.get("site")
    name = row.get("tournament_name") or vj.get("tournament_name")
    posted = row.get("posted_at")
    pl_raw = vj.get("players_left")
    pl = int(pl_raw) if isinstance(pl_raw, int) and pl_raw > 0 else None
    res = TR.resolve_tournament_number(
        site, name, vj.get("start_time_iso"),
        posted_at_hint=posted, buy_in=vj.get("buy_in"),
        anchor_mode="prestart", return_tier=True,
        disambiguate_editions=True,
        disambig_anchor_lisbon=(utc_to_lisbon_naive(posted) if posted else None),
        disambig_entrants=vj.get("entrants"), disambig_players_left=pl,
    )
    return res, vj


@router.get("/lobby-edition-scan")
def lobby_edition_scan(current_user=Depends(require_auth_or_api_key)):
    """CRIVO READ-ONLY da Raiz 2 (irmao do eliminated-crown-scan).

    Varre cada tournament_payouts GG ESCRITO por um lobby e re-corre o resolver
    (com prova de edicao) sobre o lobby QUE O ESCREVEU. Se esse lobby, com a prova
    de hoje, casa noutra edicao (ou fica ambiguo), o payout consumido pelo ICM
    pode ser da edicao errada = CONTAMINACAO.

    - contamination: o escritor casa agora numa edicao DIFERENTE do tn do payout
      (veneno duro — o ICM usou premios de outra edicao). GATE: >0 => PARAR.
    - suspect: o escritor ficou em quarentena (2+ edicoes, sem prova) — rever no
      painel. NAO conta no gate duro (o payout pode estar certo; falta prova).
    NADA escreve."""
    rows = query(
        "SELECT tp.tournament_number AS payout_tn, tp.source, "
        "       l.discord_message_id, l.site, l.tournament_name, l.posted_at, "
        "       l.players_left, l.vision_json "
        "  FROM tournament_payouts tp "
        "  LEFT JOIN lobby_processing_log l "
        "    ON l.discord_message_id = split_part(tp.source, ':', 2) "
        " WHERE tp.site = 'GGPoker'"
    )
    clean, contamination, suspect, no_writer = [], [], [], []
    for r in rows:
        src = r.get("source") or ""
        if not any(src.startswith(p) for p in _LOBBY_SOURCE_PREFIXES):
            continue  # manual/backoffice: nao e do resolver de lobbys
        if not r.get("discord_message_id"):
            no_writer.append({"payout_tn": r["payout_tn"], "source": src})
            continue
        (new_tn, _cands, tier), _vj = _reresolve_lobby_row(r)
        item = {"payout_tn": r["payout_tn"], "writer_msg": r["discord_message_id"][:12],
                "tournament_name": r.get("tournament_name"), "new_tn": new_tn, "tier": tier}
        if tier == "edition_quarantine" or new_tn is None:
            item["editions"] = [c.get("tournament_number") for c in _cands]
            suspect.append(item)
        elif str(new_tn) != str(r["payout_tn"]):
            contamination.append(item)
        else:
            clean.append(item)
    return {
        "scanned_lobby_payouts": len(clean) + len(contamination) + len(suspect),
        "edition_contamination": len(contamination),
        "gate": "hard: edition_contamination>0 => PARAR+investigar (payout de edicao errada no ICM)",
        "counts": {"clean": len(clean), "suspect": len(suspect),
                   "no_writer_row": len(no_writer)},
        "contamination": contamination, "suspect": suspect, "no_writer": no_writer,
    }


def _edition_evidence(site, candidates, anchor_lisbon):
    """Para o painel: por edicao candidata, start, janela de maos, total, e se o
    anchor cai na janela — a prova que o Rui ve para decidir."""
    from app.services import tournament_resolver as TR
    out = []
    for c in candidates:
        tn = c.get("tournament_number")
        fh, lh = TR._edition_hand_window(site, tn)
        started = (anchor_lisbon is not None and c.get("start_time") is not None
                   and anchor_lisbon >= c["start_time"])
        out.append({
            "tournament_number": tn,
            "tournament_name": c.get("tournament_name"),
            "start_time": c["start_time"].isoformat() if c.get("start_time") else None,
            "total_players": c.get("total_players"),
            "first_hand": fh.isoformat() if fh else None,
            "last_hand": lh.isoformat() if lh else None,
            "started_at_capture": started,
        })
    return out


@router.get("/lobby-edition-quarantine")
def lobby_edition_quarantine(current_user=Depends(require_auth_or_api_key)):
    """READ-ONLY. Lobbys GG em quarentena de edicao (2+ edicoes plausiveis sem
    prova dura). Para cada um, recalcula os candidatos + evidencia (start, janela
    de maos, entrants, anchor) para o Rui decidir no painel."""
    from app.utils.timezones import utc_to_lisbon_naive
    rows = query(
        "SELECT discord_message_id, site, tournament_name, posted_at, "
        "       players_left, vision_json "
        "  FROM lobby_processing_log "
        " WHERE result = 'edition_quarantine' AND vision_json IS NOT NULL "
        " ORDER BY posted_at DESC"
    )
    items = []
    for r in rows:
        (tn, cands, tier), vj = _reresolve_lobby_row(r)
        if tier != "edition_quarantine":
            items.append({
                "message_id": r["discord_message_id"], "now_resolvable_tn": tn,
                "tournament_name": r.get("tournament_name"),
                "note": "reconcile vai resolver", "candidates": [],
            })
            continue
        posted = r.get("posted_at")
        anchor_l = utc_to_lisbon_naive(posted) if posted else None
        items.append({
            "message_id": r["discord_message_id"],
            "tournament_name": r.get("tournament_name"),
            "posted_at": posted.isoformat() if posted else None,
            "anchor_lisbon": anchor_l.isoformat() if anchor_l else None,
            "entrants": vj.get("entrants"), "players_left": r.get("players_left"),
            "candidates": _edition_evidence(r.get("site") or vj.get("site"), cands, anchor_l),
        })
    return {"quarantined": len(rows), "items": items}


class _EditionResolveBody(BaseModel):
    message_id: str
    chosen_tn: str
    dry_run: bool = True


@router.post("/lobby-edition-resolve")
def lobby_edition_resolve(body: _EditionResolveBody = Body(...),
                          current_user=Depends(require_auth_or_api_key)):
    """Decisao MANUAL do Rui: cola um lobby em quarentena a edicao que ele escolhe.
    Escreve o payout (source manual_edition: — precedencia D11, nao e esmagado por
    lobbys futuros) e marca o log success. dry_run=true (default) so mostra.

    Respeita D11 (nao sobrescreve manual:/backoffice_vision: ja presente) e a
    guarda de coerencia de payout. So GG."""
    from app.services import lobby_vision, payouts_service
    from app.services.payout_coherence import check_vj_payout_coherent
    from app.services.lobby_sync import _upsert_lobby_log, _is_info_tab
    rows = query(
        "SELECT discord_message_id, site, tournament_name, posted_at, players_left, "
        "       vision_json, result FROM lobby_processing_log "
        " WHERE discord_message_id = %s", (body.message_id,))
    if not rows:
        raise HTTPException(404, "lobby message nao encontrada")
    r = rows[0]
    vj = r.get("vision_json") or {}
    if isinstance(vj, str):
        vj = json.loads(vj or "{}")
    site = r.get("site") or vj.get("site")
    if site != "GGPoker":
        raise HTTPException(422, "Raiz 2 e GG-only")
    tn = body.chosen_tn.strip()
    ts = query("SELECT tournament_number, tournament_name FROM tournament_summaries "
               "WHERE site='GGPoker' AND tournament_number=%s", (tn,))
    if not ts:
        raise HTTPException(422, f"tn {tn} nao existe em tournament_summaries")
    if _is_info_tab(vj):
        raise HTTPException(422, "print da aba Info nao escreve payout (so marca FT)")
    existing = query("SELECT source FROM tournament_payouts WHERE site='GGPoker' "
                     "AND tournament_number=%s", (tn,))
    cur_src = (existing[0].get("source") or "") if existing else ""
    if cur_src.startswith("manual:") or cur_src.startswith("backoffice_vision:"):
        raise HTTPException(409, f"payout de {tn} tem fonte de maior precedencia: {cur_src}")
    ok_coh, coh_reason = check_vj_payout_coherent(site, tn, vj)
    if not ok_coh:
        raise HTTPException(422, f"payout incoerente: {coh_reason}")
    plan = {"message_id": body.message_id, "chosen_tn": tn,
            "chosen_name": ts[0].get("tournament_name"),
            "prev_source": cur_src or None, "dry_run": body.dry_run}
    if body.dry_run:
        plan["would"] = "escrever payout (source manual_edition:) + log success"
        return plan
    blob = lobby_vision.build_hrc_payouts_blob(vj)
    up = payouts_service.upsert_payout(site="GGPoker", tournament_number=tn,
                                       payouts_json=blob,
                                       source=f"manual_edition:{body.message_id}")
    _upsert_lobby_log(
        message_id=body.message_id, channel_id=None, result="success",
        reason_detail=f"manual_edition_resolve -> {tn}",
        site="GGPoker", tournament_name=r.get("tournament_name"),
        tournament_number=tn, vision_json=vj, posted_at=r.get("posted_at"),
        players_left=r.get("players_left"))
    plan["payout_action"] = (up or {}).get("action")
    plan["written"] = True
    return plan


class _EditionRepointBody(BaseModel):
    payout_tn: str
    correct_tn: str
    dry_run: bool = True


@router.post("/lobby-edition-repoint")
def lobby_edition_repoint(body: _EditionRepointBody = Body(...),
                          current_user=Depends(require_auth_or_api_key)):
    """Fecha uma contaminacao de edicao JA ESCRITA (o que a quarentena NAO trata,
    pois so age em prints novos). O payout de `payout_tn` foi escrito por um lobby
    que, com a prova de hoje, pertence a `correct_tn`. APAGA o payout de payout_tn
    + reaponta o log do escritor para correct_tn; se correct_tn nao tiver payout,
    escreve-o do vj do escritor (D11 + coerencia). dry_run=true (default) so mostra.

    GUARDA DURA: o crivo TEM de confirmar que o escritor resolve para correct_tn
    (senao 422) — nunca apaga por palpite. So GG. Gate: correr /lobby-edition-scan
    a seguir; deve ficar sem esta contaminacao."""
    from app.services import lobby_vision, payouts_service
    from app.services.payout_coherence import check_vj_payout_coherent
    rows = query(
        "SELECT tp.tournament_number AS payout_tn, tp.source, "
        "       l.discord_message_id, l.site, l.tournament_name, l.posted_at, "
        "       l.players_left, l.vision_json "
        "  FROM tournament_payouts tp "
        "  LEFT JOIN lobby_processing_log l "
        "    ON l.discord_message_id = split_part(tp.source, ':', 2) "
        " WHERE tp.site='GGPoker' AND tp.tournament_number=%s", (body.payout_tn,))
    if not rows:
        raise HTTPException(404, f"payout GG {body.payout_tn} nao encontrado")
    r = rows[0]
    src = r.get("source") or ""
    if not any(src.startswith(p) for p in _LOBBY_SOURCE_PREFIXES):
        raise HTTPException(422, f"payout {body.payout_tn} nao e de lobby (source={src})")
    if not r.get("discord_message_id"):
        raise HTTPException(422, "escritor do payout nao encontrado no log")
    # GUARDA — o crivo confirma que o escritor pertence a correct_tn?
    (new_tn, _cands, tier), vj = _reresolve_lobby_row(r)
    if str(new_tn) != str(body.correct_tn):
        raise HTTPException(422, f"crivo NAO confirma: escritor resolve para {new_tn} "
                                 f"(tier={tier}), nao {body.correct_tn}")
    exist_correct = query("SELECT source FROM tournament_payouts WHERE site='GGPoker' "
                          "AND tournament_number=%s", (body.correct_tn,))
    correct_has = bool(exist_correct)
    plan = {
        "payout_tn": body.payout_tn, "correct_tn": body.correct_tn,
        "writer_msg": r["discord_message_id"][:12], "crivo_tier": tier,
        "would_delete_payout_of": body.payout_tn,
        "correct_tn_already_has_payout": correct_has,
        "would_write_correct_from_writer": (not correct_has),
        "dry_run": body.dry_run,
    }
    if body.dry_run:
        return plan
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM tournament_payouts WHERE site='GGPoker' "
                        "AND tournament_number=%s", (body.payout_tn,))
            plan["deleted_payout_rows"] = cur.rowcount
            cur.execute("UPDATE lobby_processing_log SET tournament_number=%s "
                        "WHERE discord_message_id=%s",
                        (body.correct_tn, r["discord_message_id"]))
            plan["repointed_writer_log"] = cur.rowcount
            conn.commit()
    if not correct_has:
        ok_coh, coh = check_vj_payout_coherent(r.get("site") or "GGPoker",
                                               body.correct_tn, vj)
        if ok_coh:
            blob = lobby_vision.build_hrc_payouts_blob(vj)
            payouts_service.upsert_payout(
                site="GGPoker", tournament_number=body.correct_tn,
                payouts_json=blob, source=f"manual_edition:{r['discord_message_id']}")
            plan["wrote_correct"] = True
        else:
            plan["wrote_correct"] = False
            plan["coherence_skip"] = coh
    plan["written"] = True
    return plan
