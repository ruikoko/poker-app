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

import re

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from app.auth import require_auth, require_auth_or_api_key
from app.db import query, get_conn
from app.services.ft_boundary import FT_CAP, count_hh_seats
from app.services.tags_canonical import canonicalize_tag, normalize_tag_key

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

    return {
        "total_images": len(imgs),
        "total_hands_with_image": len(hands_with_img),
        "needs_you": {
            "gold_no_tag": n("gold_no_tag"),
            "orphans": n("orphans"),
            "swap_suspects": n("swap_suspects"),
            "tag_conflicts": n("tag_conflicts"),
        },
        "healthy": {
            "gold_matched": n("gold_matched"),
            "it_matched": n("it_matched"),
        },
    }


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
        "  FROM lobby_processing_log WHERE tournament_number IS NOT NULL "
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
    """Ação 1 — taga N mãos com UMA tag canónica (multi-select). Normaliza na
    escrita, `union distinct` em discord_tags, dispara apply_villain_rules. Se a
    tag contradizer o formato do torneio → devolve `needs_confirm` + warnings (não
    grava sem confirm). Idempotente (mão que já tem a tag → no-op)."""
    hand_ids = payload.get("hand_ids") or []
    # only_known=True: aceita SÓ tags reconhecidas (canónicas); string arbitrária
    # → None → 400 (o endpoint não deixa criar tags fora do vocabulário).
    canon = canonicalize_tag(payload.get("tag"), only_known=True)
    confirm = bool(payload.get("confirm"))
    if not canon:
        raise HTTPException(400, "tag inválida (usar as tags canónicas)")
    if not isinstance(hand_ids, list) or not hand_ids:
        raise HTTPException(400, "hand_ids (lista não-vazia) obrigatório")
    if len(hand_ids) > 500:
        raise HTTPException(400, "máx 500 mãos por chamada")
    rows = query("SELECT id, hand_id, discord_tags, tournament_format "
                 "FROM hands WHERE hand_id = ANY(%s)", (hand_ids,))
    warnings = []
    for r in rows:
        c = _tag_format_conflict(canon, r["tournament_format"])
        if c:
            warnings.append({"hand_id": r["hand_id"], "conflict": c,
                             "tournament_format": r["tournament_format"]})
    if warnings and not confirm:
        return {"applied": 0, "needs_confirm": True, "warnings": warnings, "tag": canon}
    applied = 0
    conn = get_conn()
    try:
        for r in rows:
            existing = {canonicalize_tag(t) for t in (r["discord_tags"] or [])}
            if canon in existing:
                continue                       # idempotente: já tem a tag
            new_tags = list(r["discord_tags"] or []) + [canon]
            with conn.cursor() as cur:
                cur.execute("UPDATE hands SET discord_tags=%s WHERE id=%s",
                            (new_tags, r["id"]))
            conn.commit()
            try:
                from app.services.villain_rules import apply_villain_rules
                apply_villain_rules(r["id"])
            except Exception:
                pass
            applied += 1
    finally:
        conn.close()
    return {"applied": applied, "tag": canon, "warnings": warnings, "needs_confirm": False}
