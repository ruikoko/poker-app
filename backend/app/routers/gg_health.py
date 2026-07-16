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
                   h.tournament_name, h.tournament_format, h.played_at,
                   (h.player_names->>'match_method') AS mm
              FROM entries e JOIN hands h ON h.entry_id = e.id
             WHERE e.entry_type = 'screenshot'
               AND (e.raw_json->>'img_b64') IS NOT NULL AND {_GG}"""
    )
    out = []
    for r in rows:
        m = _FNUM_GOLD.search(r.get("fname") or "")
        mm = r.get("mm")
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
            # Metadados p/ triar em lote (nome/data/formato) sem depender só da imagem.
            "tournament_name": r.get("tournament_name"),
            "tournament_format": r.get("tournament_format"),
            "played_at": r["played_at"].isoformat() if r.get("played_at") else None,
            # anónima = ainda sem nomes (a tag entra na mesma; os nomes vêm depois).
            "anon": mm in (None, "", "discord_placeholder_no_hh"),
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

    # "Golds por ler": mãos GG com Gold ligada mas vision_done=false (a leitura nunca
    # correu / falhou em background sem recuperação — a fresta do funil). Defensivo → 0.
    try:
        golds_unread = _golds_unread_count()
    except Exception:
        golds_unread = 0

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
            "golds_unread": golds_unread,
        },
        "healthy": {
            "gold_matched": n("gold_matched"),
            "it_matched": n("it_matched"),
        },
    }


# ── "Golds por ler" — mãos com Gold ligada mas vision_done=false ──────────────
_GOLDS_UNREAD_WHERE = (
    "h.site='GGPoker' AND h.played_at >= '2026-01-01' "
    "AND e.entry_type='screenshot' AND (e.raw_json->>'img_b64') IS NOT NULL "
    "AND (e.raw_json->>'vision_done')::boolean = false"
)


def _golds_unread_count() -> int:
    r = query("SELECT COUNT(*) c FROM hands h JOIN entries e ON e.id = h.entry_id "
              "WHERE " + _GOLDS_UNREAD_WHERE)
    return int(r[0]["c"]) if r else 0


def _golds_unread_list() -> list[dict]:
    rows = query(
        "SELECT h.id, h.hand_id, h.played_at, h.tournament_name, h.tournament_number, "
        "       h.tournament_format, e.file_name, "
        "       (h.context_table_ss_id IS NOT NULL) AS has_ss, "
        "       (h.player_names->>'match_method') AS mm "
        "  FROM hands h JOIN entries e ON e.id = h.entry_id "
        " WHERE " + _GOLDS_UNREAD_WHERE +
        " ORDER BY h.played_at DESC NULLS LAST")
    out = []
    for r in rows:
        mm = r.get("mm")
        out.append({
            "id": r["id"],
            "hand_id": r["hand_id"],
            "played_at": r["played_at"].isoformat() if r.get("played_at") else None,
            "tournament_name": r.get("tournament_name"),
            "tournament_number": r.get("tournament_number"),
            "tournament_format": r.get("tournament_format"),
            "has_ss": bool(r.get("has_ss")),
            # anónima = ainda sem nomes (placeholder/sem match real) — a leitura da Gold
            # dá-lhe nomes; nas outras a Gold só melhora/confirma.
            "anon": mm in (None, "", "discord_placeholder_no_hh"),
            "file_name": r.get("file_name"),
        })
    return out


@router.get("/golds-unread")
def golds_unread(current_user=Depends(require_auth_or_api_key)):
    """Painel "Golds por ler" — mãos GG com Gold ligada cuja Vision NUNCA correu
    (`vision_done=false` + img presente). É a fresta do funil (a Vision de background
    falhou/nunca disparou e nada as re-apanha). A UI lê cada uma (`gold-vision-run`).
    Read-only aqui."""
    lst = _golds_unread_list()
    return {"count": len(lst), "hands": lst}


@router.get("/crowns")
def crowns_to_verify(current_user=Depends(require_auth)):
    """Painel COROAS da Saúde Import (consolidação 11 Jul) — mãos GG PKO/KO cuja
    coroa ($ bounty) gravada é < base÷2. `impossible` = valor >0 mas <½ (a Vision
    leu a chama VPIP em vez da coroa $); `unread` = coroa a $0 (por ler). Read-only:
    lista com IMAGEM + seats afetados para o Rui confirmar à vista (`tableSs.setBounties`
    com `confirm[]`) ou corrigir o valor. Fonte única `detect_bounty_below_half` (a
    mesma da guarda `bounty_below_half_base` do export)."""
    # #CROWN-HIGH-IS-ACCUMULATION (Rui, 15 Jul): o gate >3×base EXTINGUIU-SE (coroa alta =
    # acumulação legítima, exporta sem confirmar). O grupo "Valor alto — confirmar" era o
    # FANTASMA desse gate morto — pedia uma confirmação sem objeto → removido também daqui.
    from app.services.queue_export import (
        TS_GATED_FORMATS, detect_bounty_below_half)
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
        flagged = below                     # p/ deteção de origem
        # ── ORIGEM do valor: compara-o com a coroa da captura table-SS
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
                       for b in flagged)
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
        base_item = {
            "id": r["id"], "hand_id": r["hand_id"],
            "tournament_name": r["tournament_name"], "played_at": r["played_at"],
            "match_method": r["mm"],
            "crown_source": source,           # table_ss | gold | other(carry/reread)
            "has_both": bool(r["ss_id"]) and bool(gold_id),
            "image_url": src_img,             # a imagem da FONTE do valor
            "image_is_source": True,
        }
        by_source[source] += 1
        kind = "impossible" if any((b["value"] or 0) > 0 for b in below) else "unread"
        (impossible if kind == "impossible" else unread).append({
            **base_item, "kind": kind, "floor": below[0]["floor"],
            "seats": [{"name": b["name"], "value": b["value"]} for b in below]})
    return {"count": len(impossible) + len(unread),
            "by_source": by_source,
            "impossible": impossible, "unread": unread}


@router.get("/list")
def list_images(
    group: str = Query("all"),
    page: int = Query(1, ge=1),
    page_size: int = Query(60, ge=1, le=3000),
    current_user=Depends(require_auth),
):
    """Lista POR IMAGEM de um grupo/cenário (read-only, paginada). O teto alto (3000)
    serve o "Gold sem tag", que carrega TUDO para os filtros + seleção-em-lote operarem
    sobre o grupo inteiro (a lista devolve URLs, não base64 — é leve)."""
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


@router.post("/untag")
def gg_health_untag(payload: dict = Body(...),
                    current_user=Depends(require_auth_or_api_key)):
    """Ferramenta de edição — REMOVE UMA ou VÁRIAS tags canónicas de N mãos (o oposto
    de `/tag`). Usa-se para limpar tags espúrias (ex.: um SS mal casado deixou `pos-pko`
    numa mão vizinha; ao recasar, a tag fica na errada). Só toca `discord_tags` (as tags
    de estudo vivem lá — ver banner do CLAUDE.md); NÃO toca `hm3_tags`. Normaliza para
    comparar (remove a forma canónica mesmo que a gravada seja uma variante). Dispara
    `apply_villain_rules` (remover `nota` pode desfazer um villain). Idempotente: tag que
    a mão não tem → no-op. Body: {hand_ids:[...], tags:[...] | tag:'...'}."""
    hand_ids = payload.get("hand_ids") or []
    raw_tags = payload.get("tags")
    if not (isinstance(raw_tags, list) and raw_tags):
        raw_tags = [payload.get("tag")]
    canons = []
    for t in raw_tags:
        ct = canonicalize_tag(t, only_known=True)
        if not ct:
            raise HTTPException(400, f"tag inválida: {t!r} (usar as tags canónicas)")
        if ct not in canons:
            canons.append(ct)
    if not canons:
        raise HTTPException(400, "tag(s) obrigatória(s) (usar as tags canónicas)")
    if not isinstance(hand_ids, list) or not hand_ids:
        raise HTTPException(400, "hand_ids (lista não-vazia) obrigatório")
    if len(hand_ids) > 500:
        raise HTTPException(400, "máx 500 mãos por chamada")
    rows = query("SELECT id, hand_id, discord_tags FROM hands WHERE hand_id = ANY(%s)",
                 (hand_ids,))
    remove_set = set(canons)
    removed = hands_touched = 0
    conn = get_conn()
    try:
        for r in rows:
            cur_tags = list(r["discord_tags"] or [])
            # mantém a etiqueta se a sua forma canónica NÃO está no conjunto a remover.
            keep = [t for t in cur_tags if canonicalize_tag(t) not in remove_set]
            if len(keep) == len(cur_tags):
                continue                       # nada a remover nesta mão
            with conn.cursor() as cur:
                cur.execute("UPDATE hands SET discord_tags=%s WHERE id=%s",
                            (keep, r["id"]))
            conn.commit()
            try:
                from app.services.villain_rules import apply_villain_rules
                apply_villain_rules(r["id"])
            except Exception:
                pass
            removed += len(cur_tags) - len(keep)
            hands_touched += 1
    finally:
        conn.close()
    return {"removed": removed, "hands": hands_touched, "tags": canons}


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


def _same_name_trunc(a, b) -> bool:
    """Dois nomes são o MESMO tolerando a TRUNCAÇÃO da Vision ('Tobias Schw..' ==
    'Tobias Schwecht'). Uma rotação exige nomes DIFERENTES entre si (a,b → b,a); um nome
    encurtado de si próprio NÃO é troca de vizinho. Prefixo em qualquer sentido, mín 4
    chars (evita casar por acaso). Mesmo espírito da guarda da âncora (_vision_hero_nick_is_rui)."""
    x = (a or "").strip().lower().rstrip(".").strip()
    y = (b or "").strip().lower().rstrip(".").strip()
    if not x or not y:
        return False
    if x == y:
        return True
    return min(len(x), len(y)) >= 4 and (x.startswith(y) or y.startswith(x))


@router.get("/names/rotation-scan")
def names_rotation_scan(current_user=Depends(require_auth_or_api_key)):
    """Detetor de ROTAÇÃO (família da captura 782). N conflitos de nomes num torneio podem
    vir de UMA captura podre: a âncora rodou a roda → cada seat recebeu o nick do vizinho.
    Para cada tn com conflitos pending, constrói o mapa FORTE (position_v3) e acha as mãos
    cuja de-anon (não-position_v3) discorda do forte em ≥3 hashes = captura rotacionada. A
    cura é UMA ação — reverter essa captura — não N × 'confirmar o forte'. Read-only."""
    tns = [r["tournament_number"] for r in query(
        "SELECT DISTINCT tournament_number FROM name_quarantine_review WHERE decision='pending'")]
    rotten = []
    for tn in tns:
        strong = {}
        for r in query(
            "SELECT all_players_actions apa FROM hands WHERE tournament_number=%s "
            "AND site='GGPoker' AND (player_names->>'match_method')='position_v3'", (tn,)):
            apa = r["apa"] if isinstance(r["apa"], dict) else json.loads(r["apa"] or "{}")
            for k, v in apa.items():
                if k not in ("_meta", "Hero") and isinstance(v, dict) and v.get("real_name"):
                    strong.setdefault(k, v["real_name"])
        if not strong:
            continue
        for r in query(
            "SELECT hand_id, (player_names->>'match_method') mm, all_players_actions apa "
            "FROM hands WHERE tournament_number=%s AND site='GGPoker' "
            "AND (player_names->>'match_method') IS NOT NULL "
            "AND (player_names->>'match_method') <> 'position_v3'", (tn,)):
            apa = r["apa"] if isinstance(r["apa"], dict) else json.loads(r["apa"] or "{}")
            confl = []
            for k, v in apa.items():
                if k in ("_meta", "Hero") or not isinstance(v, dict):
                    continue
                nm, st = v.get("real_name"), strong.get(k)
                # tolerante a truncação: 'Tobias Schw..' == 'Tobias Schwecht' NÃO é troca.
                if nm and st and not _same_name_trunc(nm, st):
                    confl.append({"hash": k, "read": nm, "strong": st})
            if len(confl) >= 3:            # cadeia de rotação (≥3 hashes DIFERENTES)
                rotten.append({"tournament_number": tn, "hand_id": r["hand_id"],
                               "match_method": r["mm"], "n_conflicts": len(confl),
                               "conflicts": confl})
    return {"count": len(rotten), "rotten": rotten}


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


# ── GATE + WORKLIST da guarda VIVO-$0 (irmão do eliminated-crown-scan) ─────────
def _live_zero_seats() -> tuple[int, list, list]:
    """Núcleo partilhado (gate + worklist). Varre as mãos GG KO tagadas e devolve
    (scanned, silent, review) — silent = coroa $0 SEM review (contaminação, escrita
    calada); review = $0 com review honesto. Cada seat traz `db_id`+`played_at` para
    a imagem/link do painel de resolução. NADA escreve."""
    base = {r["tournament_number"]: float(r["buy_in_bounty"]) for r in query(
        "SELECT tournament_number, buy_in_bounty FROM tournament_summaries "
        "WHERE site='GGPoker' AND buy_in_bounty IS NOT NULL AND buy_in_bounty > 0")}
    rows = query(
        "SELECT id AS db_id, hand_id, tournament_number, tournament_name, "
        "       played_at::text AS played_at, raw, "
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
            item = {"id": r["db_id"], "hand_id": r["hand_id"],
                    "tournament_name": r["tournament_name"],
                    "played_at": r["played_at"], "name": nm,
                    "floor": round(b / 2.0, 2), "review": p.get(BOUNTY_REVIEW_KEY)}
            if p.get(BOUNTY_REVIEW_KEY):
                review.append(item)     # honesto (guarda activa)
            else:
                silent.append(item)     # coroa $0 gravada em silêncio = contaminação
    return scanned, silent, review


@router.get("/live-crown-zero-scan")
def live_crown_zero_scan(current_user=Depends(require_auth_or_api_key)):
    """GATE da guarda vivo-$0 (só-tagadas, GG KO). Reporta jogadores VIVOS (não bustados
    pela HH) com coroa $0 em torneios KO (buy_in_bounty do TS > 0). Dois baldes:
    - `silent_zero` = coroa $0/null SEM bounty_review → CONTAMINAÇÃO (grava $0 em silêncio).
      GATE DURO: >0 após reimporte OU qualquer ingest GG = PARAR + investigar + corrigir.
    - `review` = $0 com review='live_crown_read_zero' → honesto (guarda activa — OK).
    Torneios não-KO ou sem TS ficam FORA (a guarda não se aplica). NADA escreve."""
    scanned, silent, review = _live_zero_seats()
    return {"scanned_ko_tagged_hands": scanned,
            # ★ crivo da guarda vivo-$0: tem de ser 0 pós-reimporte.
            "silent_zero_contamination": len(silent),
            "gate": "hard: silent_zero_contamination>0 => PARAR+investigar (nunca curado)",
            "counts": {"silent": len(silent), "review": len(review)},
            "silent_zero": silent, "review": review}


# ── WORKLIST de resolução do vivo-$0 (a escrita passa por /set-bounties, que ALINHA
#    apa+players_list pelo nome normalizado — o fix do desalinhamento é o que a torna real) ──
def _ensure_live_zero_dismissed():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("CREATE TABLE IF NOT EXISTS live_zero_dismissed ("
                        "hand_id TEXT, name TEXT, created_at TIMESTAMPTZ DEFAULT now(), "
                        "PRIMARY KEY (hand_id, name))")
        conn.commit()
    finally:
        conn.close()


def _live_zero_dismissed_set() -> set:
    try:
        _ensure_live_zero_dismissed()
        return {(r["hand_id"], r["name"])
                for r in query("SELECT hand_id, name FROM live_zero_dismissed")}
    except Exception:  # pragma: no cover - defensivo
        return set()


@router.get("/live-zero/list")
def live_zero_list(current_user=Depends(require_auth_or_api_key)):
    """WORKLIST de resolução (LEI 1/3). TODOS os lugares vivos-$0 tagados KO — os DOIS
    baldes, porque AMBOS precisam do carimbo da coroa real:
    - `review` = a guarda leu a placa e não conseguiu a coroa → gravou $0 honesto (é ISTO
      que o Rui vem ler à imagem e selar — o grosso do trabalho);
    - `silent` = $0 gravado sem review (contaminação) → também se carimba, e além disso é
      alarme do crivo (`/live-crown-zero-scan` conta-o à parte para o gate do reimporte).
    Cada card: imagem + nº+link + coroa a carimbar (≥ base÷2 = `floor`) + `bucket`.
    Carimbar via /set-bounties (sela + ALINHA as 2 gavetas) tira-o daqui (coroa > 0);
    Dispensar também. Exclui os já dispensados. READ-ONLY."""
    dismissed = _live_zero_dismissed_set()
    _, silent, review = _live_zero_seats()
    items = ([{**s, "bucket": "silent"} for s in silent]
             + [{**s, "bucket": "review"} for s in review])
    hands = [s for s in items if (s["hand_id"], s["name"]) not in dismissed]
    hands.sort(key=lambda s: (s["bucket"] != "silent", s["played_at"] or ""), reverse=False)
    return {"count": len(hands),
            "counts": {"silent": len([h for h in hands if h["bucket"] == "silent"]),
                       "review": len([h for h in hands if h["bucket"] == "review"])},
            "hands": hands}


@router.post("/live-zero/dismiss")
def live_zero_dismiss(payload: dict = Body(...),
                      current_user=Depends(require_auth_or_api_key)):
    """Dispensar um seat vivo-$0 (revisto, sem imagem para corrigir / legítimo): sai da
    worklist, não escreve coroa. Body: {hand_id, name}."""
    hand_id = (payload or {}).get("hand_id")
    name = (payload or {}).get("name")
    if not hand_id or not name:
        raise HTTPException(400, "hand_id + name obrigatórios")
    _ensure_live_zero_dismissed()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO live_zero_dismissed (hand_id, name) VALUES (%s,%s) "
                        "ON CONFLICT DO NOTHING", (hand_id, name))
        conn.commit()
    finally:
        conn.close()
    return {"status": "dismissed", "hand_id": hand_id, "name": name}


# ── LEI DO CRUZAMENTO — amostra do balde PREENCHER (validação do critério) ─────
_CROSS_TRUNC = re.compile(r"(\.\.+|…)\s*$")


def _cross_norm(s):
    return re.sub(r"\s+", " ", _CROSS_TRUNC.sub("", (s or "").strip().lower()))


# TOLERÂNCIA DE CÊNTIMOS (Rui): duas leituras a diferir < $1 = a mesma coroa (tremura de
# leitura), não conflito. Diferenças de DÓLARES (>= $1) = conflito real.
_JITTER = 1.0


def _cross_num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _cross_trajectory():
    """(tn, nome_norm) → [(played_at, coroa)] de TODAS as mãos GG 2026 — a trajetória
    do jogador no torneio (a coroa só SOBE). Usada pelo crivo do não-desce."""
    traj: dict = {}
    for r in query(
            "SELECT tournament_number AS tn, played_at::text AS pa, player_names AS pn "
            "  FROM hands WHERE site='GGPoker' AND played_at >= '2026-01-01' "
            "   AND player_names->'players_list' IS NOT NULL"):
        pn = r["pn"] if isinstance(r["pn"], dict) else json.loads(r["pn"] or "{}")
        for p in (pn.get("players_list") or []):
            v = _cross_num(p.get("bounty_value_usd"))
            if v is not None and v > 0 and p.get("name"):
                traj.setdefault((r["tn"], _cross_norm(p["name"])), []).append((r["pa"], v))
    return traj


def _cross_sieve(prop, base, tn, key, played_at, traj):
    """CRIVO DA FÍSICA (ordem do Rui — 'outra captura leu' NÃO é prova). Devolve
    (ok, reason). O valor da fonte irmã só se PROPÕE se passar:
    - FLOOR: coroa nunca < base÷2 (fresh) → `$36` num torneio de base $250 chumba;
    - NÃO-DESCE: a coroa do mesmo jogador só sobe no torneio → não pode ser < uma
      leitura ANTERIOR nem > uma POSTERIOR (contra a trajetória = misread)."""
    if base and prop < base / 2 - 0.01:
        return False, "below_floor"
    seq = traj.get((tn, key)) or []
    before = [v for (t, v) in seq if t < played_at]
    after = [v for (t, v) in seq if t > played_at]
    if before and prop < max(before) - 0.5:
        return False, "descends_vs_earlier"
    if after and prop > min(after) + 0.5:
        return False, "exceeds_later"
    return True, None


def _gold_photo_time(grj, fallback):
    """Hora da FOTO do Gold (replayer) = `file_meta.date + time` — NÃO o `entry.created_at`
    (que é a hora do PROCESSAMENTO/reimport, ex. 07-10). Sem file_meta → fallback. Corrige o
    'mais recente' dos conflitos (comparar relógios errados dava falsos 'recent_below_max')."""
    fm = (grj or {}).get("file_meta") if isinstance(grj, dict) else None
    if isinstance(fm, dict) and fm.get("date"):
        return f"{fm['date']} {fm.get('time') or '00:00'}"
    return fallback


def _cross_gold_crowns(grj):
    """{nome_norm: coroa} da Gold (players_list + raw_vision). None se não é Gold real."""
    rv = grj.get("raw_vision") if isinstance(grj, dict) else None
    if not (isinstance(rv, str) and rv.strip().startswith("TM")):
        return None
    gc: dict = {}
    for p in (grj.get("players_list") or []):
        v = _cross_num(p.get("bounty_value_usd"))
        if p.get("name") and v is not None:
            gc[_cross_norm(p["name"])] = v
    for ln in rv.splitlines():
        if ln.startswith("PLAYER:"):
            parts = [x.strip() for x in ln.split("PLAYER:", 1)[1].split("|")]
            if len(parts) >= 4:
                v = _cross_num(parts[3])
                if parts[0] and parts[0] != "NONE" and v is not None:
                    gc.setdefault(_cross_norm(parts[0]), v)
    return gc


def _crossing_all_fills():
    """Núcleo da LEI DO CRUZAMENTO (coroas). Devolve (survivors, suspects). survivor =
    seat com coroa VAZIA no gravado + valor da fonte irmã (Gold principal, senão a MAIOR
    das SS) que PASSA o crivo da física (`_cross_sieve`). suspect = chumba o crivo. Cada
    item traz refs das 2 capturas (leu/falhou) p/ a amostra montar imagens. NADA escreve."""
    from app.services.eliminated_bounty import is_bounty_sealed
    ko = {r["tournament_number"]: float(r["buy_in_bounty"]) for r in query(
        "SELECT tournament_number, buy_in_bounty FROM tournament_summaries "
        "WHERE site='GGPoker' AND buy_in_bounty > 0")}
    traj = _cross_trajectory()
    ss_by_hand: dict = {}
    for r in query(
            "SELECT matched_hand_id AS mh, id, vision_json AS vj, captured_at::text AS cap "
            "  FROM table_ss_processing_log "
            " WHERE matched_hand_id IS NOT NULL AND result='success' AND img_b64 IS NOT NULL"):
        vj = r["vj"] if isinstance(r["vj"], dict) else json.loads(r["vj"] or "{}")
        ss_by_hand.setdefault(r["mh"], []).append(
            {"kind": "ss", "id": r["id"], "cap": r["cap"],
             "url": f"/api/table-ss/image/{r['id']}",
             "crowns": {_cross_norm(s.get("nick")): _cross_num(s.get("bounty_usd"))
                        for s in (vj.get("seats") or []) if s.get("nick")}})
    rows = query(
        "SELECT h.id, h.hand_id, h.tournament_number AS tn, h.tournament_name AS tname, "
        "       h.context_table_ss_id AS ssid, "
        "       h.played_at::text AS pa, h.player_names AS pn, "
        "       e.id AS entry_id, e.raw_json AS grj, e.created_at::text AS gold_at "
        "  FROM hands h LEFT JOIN entries e ON e.id = h.entry_id "
        " WHERE h.site='GGPoker' AND h.played_at >= '2026-01-01' "
        "   AND h.player_names->'players_list' IS NOT NULL")
    cases, suspects = [], []
    for r in rows:
        base = ko.get(r["tn"])
        if not base:
            continue
        pn = r["pn"] if isinstance(r["pn"], dict) else json.loads(r["pn"] or "{}")
        grj = r["grj"] if isinstance(r["grj"], dict) else json.loads(r["grj"] or "{}") if r["grj"] else {}
        gc = _cross_gold_crowns(grj)
        gold = ({"kind": "gold", "id": r["entry_id"], "cap": _gold_photo_time(grj, r.get("gold_at")),
                 "url": f"/api/screenshots/image/{r['entry_id']}", "crowns": gc}
                if gc is not None else None)
        caps = ([gold] if gold else []) + ss_by_hand.get(r["hand_id"], [])
        for p in (pn.get("players_list") or []):
            if is_bounty_sealed(p):
                continue
            cur_v = _cross_num(p.get("bounty_value_usd"))
            if cur_v is not None and cur_v > 0:
                continue
            key = _cross_norm(p.get("name"))
            # Gold principal; senão a captura SS com o MAIOR valor (a fresta é sempre a coroa
            # mais completa — o crivo protege contra o inflar).
            read = next((c for c in caps if (c["crowns"].get(key) or 0) > 0 and c["kind"] == "gold"), None)
            if not read:
                ssv = [c for c in caps if (c["crowns"].get(key) or 0) > 0]
                read = max(ssv, key=lambda c: c["crowns"][key]) if ssv else None
            if not read:
                continue
            failed = next((c for c in caps if c["id"] != read["id"]
                           and c["crowns"].get(key) in (None, 0)), None)
            if not failed and r["ssid"]:
                failed = next((c for c in caps if c["kind"] == "ss" and c["id"] == r["ssid"]), None)
            prop = read["crowns"][key]
            ok, reason = _cross_sieve(prop, base, r["tn"], key, r["pa"], traj)
            case = {
                "hand_id": r["hand_id"], "hand_db_id": r["id"], "seat": p.get("name"),
                "tournament": r.get("tname"), "base_source": "ts",
                "stored": p.get("bounty_value_usd"),
                "value": prop, "base": base, "floor": round(base / 2.0, 2),
                "sieve_ok": ok, "sieve_reason": reason,
                "read": {"source": read["kind"], "capture_id": read["id"],
                         "image_url": read["url"], "captured_at": read["cap"]},
                "failed": ({"source": failed["kind"], "capture_id": failed["id"],
                            "image_url": failed["url"], "captured_at": failed["cap"]}
                           if failed else None),
            }
            (cases if ok else suspects).append(case)
    return cases, suspects


@router.get("/crossing/fill-sample")
def crossing_fill_sample(n: int = Query(4, ge=1, le=12),
                         seed: Optional[int] = None,
                         current_user=Depends(require_auth)):
    """AMOSTRA read-only do balde PREENCHER, JÁ CRIVADA pela física. `sample` = sobreviventes
    (proposta); `suspects` = crivados ('irmã suspeita'), com a razão. Cada caso traz as DUAS
    imagens (leu ✓ / falhou ✗) + horas. Sorteio por `seed` (fixo) ou aleatório (omitir)."""
    cases, suspects = _crossing_all_fills()
    import random
    rng = random.Random(seed) if seed is not None else random.Random()
    rng.shuffle(cases); rng.shuffle(suspects)
    return {
        "counts": {"passed": len(cases), "suspect": len(suspects),
                   "total": len(cases) + len(suspects)},
        "total_fill_seats": len(cases) + len(suspects),
        "sample": cases[:n], "suspects": suspects[:n]}


def _crossing_name_fixes():
    """Núcleo da LEI DO CRUZAMENTO (nomes). Lista de {hand_id, hand_db_id, hash, from, to}
    — nomes truncados no apa que ganham a forma mais completa de qualquer fonte irmã
    (regra `name_merge.best_completion`; selo `verified_by_user` intocável). NADA escreve."""
    from app.services.name_merge import best_completion, names_pool, is_truncated
    ss_by_hand: dict = {}
    for r in query(
            "SELECT matched_hand_id AS mh, vision_json AS vj FROM table_ss_processing_log "
            " WHERE matched_hand_id IS NOT NULL AND result='success'"):
        vj = r["vj"] if isinstance(r["vj"], dict) else json.loads(r["vj"] or "{}")
        ss_by_hand.setdefault(r["mh"], []).append(vj)
    rows = query(
        "SELECT h.id, h.hand_id, h.player_names AS pn, h.all_players_actions AS apa, "
        "       e.raw_json AS grj "
        "  FROM hands h LEFT JOIN entries e ON e.id = h.entry_id "
        " WHERE h.site='GGPoker' AND h.played_at >= '2026-01-01' "
        "   AND h.player_names IS NOT NULL")
    fixes = []
    for r in rows:
        apa = r["apa"] if isinstance(r["apa"], dict) else json.loads(r["apa"] or "{}")
        pn = r["pn"] if isinstance(r["pn"], dict) else json.loads(r["pn"] or "{}")
        grj = r["grj"] if isinstance(r["grj"], dict) else json.loads(r["grj"] or "{}") if r["grj"] else {}
        pool = names_pool(apa, pn.get("players_list"), grj, ss_by_hand.get(r["hand_id"], []))
        for k, v in (apa or {}).items():
            if k == "_meta" or not isinstance(v, dict) or v.get("verified_by_user"):
                continue
            nm = v.get("real_name")
            if not is_truncated(nm):
                continue
            best = best_completion(nm, pool)
            if best:
                fixes.append({"hand_id": r["hand_id"], "hand_db_id": r["id"],
                              "hash": k, "from": nm, "to": best})
    return fixes


@router.get("/crossing/plan")
def crossing_plan(current_user=Depends(require_auth)):
    """DRY-RUN da LEI DO CRUZAMENTO (o Rui deu aval à 2ª amostra). Números finais para o
    carimbo ÚNICO em lote: coroas a PREENCHER (as 88 crivadas) + nomes completos>truncados.
    READ-ONLY — só escreve no /crossing/apply."""
    fills, suspects = _crossing_all_fills()
    names = _crossing_name_fixes()
    return {
        "crowns": {"seats": len(fills),
                   "hands": len({f["hand_id"] for f in fills}),
                   "suspects_frozen": len(suspects),
                   "examples": [{"hand_id": f["hand_id"], "seat": f["seat"],
                                 "value": f["value"], "source": f["read"]["source"]}
                                for f in fills[:8]]},
        "names": {"seats": len(names),
                  "hands": len({f["hand_id"] for f in names}),
                  "examples": [{"hand_id": f["hand_id"], "from": f["from"], "to": f["to"]}
                               for f in names[:8]]},
    }


def _do_crossing_apply():
    """NÚCLEO da aplicação do cruzamento (coroas crivadas SELADAS cross_capture + nomes
    completos). Sem confirm/HTTP — partilhado pelo carimbo do Rui E pelo reconcile de
    import (o reimport nasce cruzado). Idempotente/transacional; selos intocáveis."""
    from app.services.eliminated_bounty import (
        BOUNTY_SOURCE_KEY, SOURCE_CROSS_CAPTURE, is_bounty_sealed)
    fills, _ = _crossing_all_fills()
    names = _crossing_name_fixes()
    # agrupa por mão
    by_hand: dict = {}
    for f in fills:
        by_hand.setdefault(f["hand_db_id"], {"crowns": [], "names": []})["crowns"].append(f)
    for f in names:
        by_hand.setdefault(f["hand_db_id"], {"crowns": [], "names": []})["names"].append(f)
    crowns_written = names_written = hands_touched = 0
    conn = get_conn()
    try:
        for hid, work in by_hand.items():
            rows = query("SELECT player_names AS pn, all_players_actions AS apa "
                         "FROM hands WHERE id=%s", (hid,))
            if not rows:
                continue
            pn = rows[0]["pn"] if isinstance(rows[0]["pn"], dict) else json.loads(rows[0]["pn"] or "{}")
            apa = rows[0]["apa"] if isinstance(rows[0]["apa"], dict) else json.loads(rows[0]["apa"] or "{}")
            pl = pn.get("players_list") or []
            changed = False
            # coroas: preenche o seat por nome, SELA com cross_capture (não pisa selados)
            cw = {c["seat"]: c["value"] for c in work["crowns"]}
            for p in pl:
                if p.get("name") in cw and not is_bounty_sealed(p):
                    cur_v = p.get("bounty_value_usd")
                    if cur_v is None or cur_v == 0:
                        p["bounty_value_usd"] = cw[p["name"]]
                        p[BOUNTY_SOURCE_KEY] = SOURCE_CROSS_CAPTURE
                        crowns_written += 1
                        changed = True
            # nomes: completa apa.real_name + players_list.name (selo intocável)
            nmap = {f["hash"]: f["to"] for f in work["names"]}
            for k, to in nmap.items():
                v = apa.get(k)
                if isinstance(v, dict) and not v.get("verified_by_user"):
                    old = v.get("real_name")
                    if old and old != to:
                        v["real_name"] = to
                        names_written += 1
                        changed = True
                        for p in pl:
                            if p.get("name") == old and not p.get("verified_by_user"):
                                p["name"] = to
            if changed:
                hands_touched += 1
                with conn.cursor() as cur:
                    cur.execute("UPDATE hands SET player_names=%s, all_players_actions=%s WHERE id=%s",
                                (json.dumps(pn), json.dumps(apa), hid))
        conn.commit()
    finally:
        conn.close()
    return {"status": "applied", "crowns_written": crowns_written,
            "names_written": names_written, "hands_touched": hands_touched}


@router.post("/crossing/apply")
def crossing_apply(payload: dict = Body(default=None),
                   current_user=Depends(require_auth)):
    """CARIMBO ÚNICO EM LOTE do Rui (LEI DO CRUZAMENTO). Escreve as coroas crivadas
    (SELADAS, `bounty_source='cross_capture'`) + os nomes completos. Só corre com
    `{"confirm": true}` (o carimbo). NADA nos suspeitos."""
    if not (payload or {}).get("confirm"):
        raise HTTPException(400, "carimbo exige {confirm: true}")
    return _do_crossing_apply()


# ── LEI DO CRUZAMENTO — CONFLITOS (decisão (B) do Rui) ─────────────────────────
def _crossing_conflicts():
    """Seats NÃO-selados com coroa >0 onde as fontes DISCORDAM. Três baldes (decisão do Rui):
    - **auto** (B): crescimento óbvio — o MAIOR é o MAIS RECENTE e passa a física (≥ coroa
      fresca base÷2 + não-desce) → fica o mais recente (`cross_conflict`).
    - **exclusion**: TODAS as leituras < KO inicial (base÷2) = impossíveis → morrem; o `stored`
      é são (≥ base÷2 + na grelha das metades) → fica o stored (`cross_exclusion`). Física certa,
      sem comparar leituras suspeitas → resolve-se sozinha (painel informativo, sem trava).
    - **eye**: incompatíveis (o recente é menor = misread, ou stored não-são) → olho do Rui.
    Devolve (auto, exclusion, eye). NADA escreve."""
    from app.services.eliminated_bounty import is_bounty_sealed
    from app.routers.crown_recovery import _on_halves_grid, _on_split_grid
    ko = {r["tournament_number"]: float(r["buy_in_bounty"]) for r in query(
        "SELECT tournament_number, buy_in_bounty FROM tournament_summaries "
        "WHERE site='GGPoker' AND buy_in_bounty > 0")}
    traj = _cross_trajectory()
    ssb: dict = {}
    for r in query(
            "SELECT matched_hand_id AS mh, id, vision_json AS vj, captured_at::text AS cap "
            "  FROM table_ss_processing_log "
            " WHERE matched_hand_id IS NOT NULL AND result='success' AND img_b64 IS NOT NULL"):
        vj = r["vj"] if isinstance(r["vj"], dict) else json.loads(r["vj"] or "{}")
        ssb.setdefault(r["mh"], []).append(
            {"source": "ss", "id": r["id"], "cap": r["cap"] or "",
             "url": f"/api/table-ss/image/{r['id']}",
             "crowns": {_cross_norm(s.get("nick")): _cross_num(s.get("bounty_usd"))
                        for s in (vj.get("seats") or []) if s.get("nick")}})
    rows = query(
        "SELECT h.id, h.hand_id, h.tournament_number AS tn, h.tournament_name AS tname, "
        "       h.played_at::text AS pa, "
        "       h.player_names AS pn, e.id AS entry_id, e.raw_json AS grj, "
        "       e.created_at::text AS gold_at "
        "  FROM hands h LEFT JOIN entries e ON e.id = h.entry_id "
        " WHERE h.site='GGPoker' AND h.played_at >= '2026-01-01' "
        "   AND h.player_names->'players_list' IS NOT NULL")
    auto, exclusion, eye = [], [], []
    for r in rows:
        base = ko.get(r["tn"])
        if not base:
            continue
        pn = r["pn"] if isinstance(r["pn"], dict) else json.loads(r["pn"] or "{}")
        grj = r["grj"] if isinstance(r["grj"], dict) else json.loads(r["grj"] or "{}") if r["grj"] else {}
        gc = _cross_gold_crowns(grj)
        caps = ([{"source": "gold", "id": r["entry_id"], "cap": _gold_photo_time(grj, r.get("gold_at")) or "",
                  "url": f"/api/screenshots/image/{r['entry_id']}", "crowns": gc}] if gc is not None else [])
        caps += ssb.get(r["hand_id"], [])
        for p in (pn.get("players_list") or []):
            if is_bounty_sealed(p):
                continue
            sv = _cross_num(p.get("bounty_value_usd"))
            if sv is None or sv <= 0:
                continue
            key = _cross_norm(p.get("name"))
            reads = [c for c in caps if (c["crowns"].get(key) or 0) > 0]
            vals = {round(c["crowns"][key], 2) for c in reads}
            if not vals:
                continue
            recent = max(reads, key=lambda c: c["cap"])
            mx = max(c["crowns"][key] for c in reads)
            floor = round(base / 2.0, 2)
            readings = sorted(({"value": c["crowns"][key], "source": c["source"],
                                "captured_at": c["cap"] or None, "image_url": c["url"]}
                               for c in reads), key=lambda x: x["captured_at"] or "")
            item = {"hand_id": r["hand_id"], "hand_db_id": r["id"], "seat": p.get("name"),
                    "tournament": r.get("tname"), "base_source": "ts",
                    "stored": sv, "winner": mx, "base": base, "floor": floor,
                    "readings": readings}
            # TOLERÂNCIA DE CÊNTIMOS (Rui): leituras dentro de <$1 = a MESMA coroa (tremura de
            # leitura), NÃO conflito. Se TODO o espectro (leituras + stored) cai em <$1:
            #  - idênticas (≤1¢) → não há nada (concordam) → skip;
            #  - tremura → fica a mais recente, sela, vai à vitrine informativa (sem gastar o olho).
            allvals = list(vals) + [round(sv, 2)]
            if max(allvals) - min(allvals) < _JITTER:
                if len(vals) == 1 and abs(next(iter(vals)) - sv) < 0.01:
                    continue                   # verdadeiramente iguais → nada a resolver
                item["kept"] = recent["crowns"][key]
                item["jitter"] = True
                exclusion.append(item)
                continue
            # EXCLUSÃO DE PARTES (generalizada — decisão do Rui): a régua é a PERTENÇA À GRELHA,
            # não a comparação de leituras. Candidatas = stored + todas as leituras. Uma é
            # "possível" sse >= KO inicial (base÷2) E na grelha das metades. Se houver EXATAMENTE
            # UMA possível (as outras < KO ou fora-de-grelha = a grelha não as fabrica), essa
            # ganha SOZINHA (física certa). ≥2 possíveis = conflito real → (B) crescimento/olho.
            # 0 possíveis = todas impossíveis → olho.
            candidates = {round(c["crowns"][key], 2) for c in reads}
            candidates.add(round(sv, 2))
            grid_valid = sorted(v for v in candidates
                                if v >= floor - 0.01 and _on_halves_grid(v, floor))
            # SPLIT° presente (nota #1): um valor que SÓ bate num split° não é chama nem degrau
            # simples → NÃO se auto-descarta; o olho do Rui arbitra.
            has_split = any(v not in grid_valid and _on_split_grid(v, floor) for v in candidates)
            if has_split:
                item["reason"] = "split_arbitra"       # split° em jogo → olho
                eye.append(item)
            elif len(grid_valid) == 1:
                item["kept"] = grid_valid[0]           # a possível ganha; as impossíveis (chama) morrem
                exclusion.append(item)
            elif len(grid_valid) == 0:
                item["reason"] = "ambas_impossiveis"   # nenhuma na grelha → olho
                eye.append(item)
            else:
                # ≥2 valores POSSÍVEIS (na grelha) na MESMA mão. A coroa é FIXA nesse momento
                # (todas as capturas são da mesma mão) → NÃO há crescimento nem "mais recente":
                # um dos on-grid é um misread coincidente (ex. $25 = chama VPIP 25 = 2.5B). Não se
                # auto-decide → OLHO do Rui, com AMBAS as leituras + imagens à vista.
                item["reason"] = "ambos_possiveis"
                eye.append(item)
    return auto, exclusion, eye


@router.get("/crossing/conflicts/plan")
def crossing_conflicts_plan(current_user=Depends(require_auth)):
    """DRY-RUN dos conflitos (B). auto = crescimento óbvio (resolve pela física); eye =
    incompatível (card). READ-ONLY."""
    auto, exclusion, eye = _crossing_conflicts()
    return {"auto": {"seats": len(auto), "hands": len({a["hand_id"] for a in auto}),
                     "examples": [{"hand_id": a["hand_id"], "seat": a["seat"],
                                   "stored": a["stored"], "winner": a["winner"]} for a in auto[:8]]},
            "exclusion": {"seats": len(exclusion), "hands": len({e["hand_id"] for e in exclusion})},
            "eye": {"seats": len(eye), "hands": len({e["hand_id"] for e in eye})}}


def _do_crossing_conflicts_apply():
    """NÚCLEO da resolução AUTO (B) dos conflitos (crescimento óbvio → o mais recente=max,
    SELADO cross_conflict). Sem confirm/HTTP — partilhado pelo carimbo E pelo reconcile."""
    from app.services.eliminated_bounty import BOUNTY_SOURCE_KEY, is_bounty_sealed
    auto, _exc, _ = _crossing_conflicts()
    by_hand: dict = {}
    for a in auto:
        by_hand.setdefault(a["hand_db_id"], []).append(a)
    written = hands_touched = 0
    conn = get_conn()
    try:
        for hid, items in by_hand.items():
            rows = query("SELECT player_names AS pn FROM hands WHERE id=%s", (hid,))
            if not rows:
                continue
            pn = rows[0]["pn"] if isinstance(rows[0]["pn"], dict) else json.loads(rows[0]["pn"] or "{}")
            pl = pn.get("players_list") or []
            wmap = {a["seat"]: a["winner"] for a in items}
            changed = False
            for p in pl:
                if p.get("name") in wmap and not is_bounty_sealed(p):
                    p["bounty_value_usd"] = wmap[p["name"]]
                    p[BOUNTY_SOURCE_KEY] = "cross_conflict"
                    written += 1
                    changed = True
            if changed:
                hands_touched += 1
                with conn.cursor() as cur:
                    cur.execute("UPDATE hands SET player_names=%s WHERE id=%s",
                                (json.dumps(pn), hid))
        conn.commit()
    finally:
        conn.close()
    return {"status": "applied", "crowns_written": written, "hands_touched": hands_touched}


@router.post("/crossing/conflicts/apply-selected")
def crossing_conflicts_apply_selected(payload: dict = Body(...),
                                      current_user=Depends(require_auth)):
    """SELEÇÃO EM LOTE (o lote cego morreu — ordem do Rui). O Rui varre os 33 AUTO como
    cards pré-marcados, desmarca os podres (ex. WhereIsMyBeer $40=chama), edita valores se
    quiser, e carimba os SELECIONADOS num clique. Body: {items:[{hand_id, seat, value}]}.
    Sela cada um (`bounty_source='manual'` — arbítrio do Rui na placa), alinhando as 2
    gavetas (apa + players_list) pelo nome. Idempotente/transacional."""
    from app.services.eliminated_bounty import BOUNTY_SOURCE_KEY, SOURCE_MANUAL, is_bounty_sealed
    items = (payload or {}).get("items") or []
    by_hand: dict = {}
    for it in items:
        hid, seat, val = it.get("hand_id"), it.get("seat"), it.get("value")
        if hid and seat and val is not None:
            by_hand.setdefault(hid, {})[seat] = val
    _nm = lambda s: re.sub(r"(.)\1+", r"\1", re.sub(r"\s+", "", (s or "").lower()))
    written = hands_touched = 0
    conn = get_conn()
    try:
        for hid, seatmap in by_hand.items():
            rows = query("SELECT id, player_names AS pn, all_players_actions AS apa "
                         "FROM hands WHERE hand_id=%s", (hid,))
            if not rows:
                continue
            pn = rows[0]["pn"] if isinstance(rows[0]["pn"], dict) else json.loads(rows[0]["pn"] or "{}")
            apa = rows[0]["apa"] if isinstance(rows[0]["apa"], dict) else json.loads(rows[0]["apa"] or "{}")
            by_norm = {_nm(k): v for k, v in seatmap.items()}
            changed = False
            for p in (pn.get("players_list") or []):
                want = seatmap.get(p.get("name")) or by_norm.get(_nm(p.get("name")))
                if want is not None and not is_bounty_sealed(p):
                    p["bounty_value_usd"] = float(want)
                    p[BOUNTY_SOURCE_KEY] = SOURCE_MANUAL
                    written += 1
                    changed = True
            for k, v in (apa or {}).items():   # alinha o apa por nome
                if k == "_meta" or not isinstance(v, dict) or is_bounty_sealed(v):
                    continue
                want = seatmap.get(v.get("real_name")) or by_norm.get(_nm(v.get("real_name")))
                if want is not None:
                    v["bounty_value_usd"] = float(want)
                    v[BOUNTY_SOURCE_KEY] = SOURCE_MANUAL
                    changed = True
            if changed:
                hands_touched += 1
                with conn.cursor() as cur:
                    cur.execute("UPDATE hands SET player_names=%s, all_players_actions=%s WHERE hand_id=%s",
                                (json.dumps(pn), json.dumps(apa), hid))
        conn.commit()
    finally:
        conn.close()
    return {"status": "applied", "sealed": written, "hands_touched": hands_touched}


def _do_crossing_exclusion_apply():
    """EXCLUSÃO DE PARTES (decisão do Rui — resolve-se sozinha). Sela o `stored` são
    (`cross_exclusion`) nos conflitos onde a leitura era uma chama < KO inicial. O valor
    NÃO muda (o stored já é o são); só se sela p/ proteger + sair do detetor. Física certa,
    sem trava. Sem confirm/HTTP — partilhado pelo reconcile."""
    from app.services.eliminated_bounty import BOUNTY_SOURCE_KEY, SOURCE_CROSS_EXCLUSION, is_bounty_sealed
    _a, exclusion, _e = _crossing_conflicts()
    by_hand: dict = {}
    for x in exclusion:
        by_hand.setdefault(x["hand_db_id"], []).append(x)
    written = hands_touched = 0
    conn = get_conn()
    try:
        for hid, items in by_hand.items():
            rows = query("SELECT player_names AS pn FROM hands WHERE id=%s", (hid,))
            if not rows:
                continue
            pn = rows[0]["pn"] if isinstance(rows[0]["pn"], dict) else json.loads(rows[0]["pn"] or "{}")
            kept_map = {x["seat"]: x["kept"] for x in items}
            changed = False
            for p in (pn.get("players_list") or []):
                if p.get("name") in kept_map and not is_bounty_sealed(p):
                    p["bounty_value_usd"] = kept_map[p["name"]]     # a única possível (pode ≠ stored)
                    p[BOUNTY_SOURCE_KEY] = SOURCE_CROSS_EXCLUSION
                    written += 1
                    changed = True
            if changed:
                hands_touched += 1
                with conn.cursor() as cur:
                    cur.execute("UPDATE hands SET player_names=%s WHERE id=%s",
                                (json.dumps(pn), hid))
        conn.commit()
    finally:
        conn.close()
    return {"status": "applied", "sealed": written, "hands_touched": hands_touched}


def run_crossing_auto(reason: str = "import") -> dict:
    """LEI DO CRUZAMENTO no merge (ordem do Rui: 'o reimport nasce cruzado'). Corre a
    aplicação automática — nomes completos + coroas crivadas (SELADAS cross_capture) +
    conflitos de crescimento óbvio (B, `cross_conflict`) + exclusão de partes (chama < KO
    morre, fica o stored são, `cross_exclusion`). Só toca não-selados; o olho do Rui fica
    com os conflitos incompatíveis. Idempotente/defensivo (nunca lança)."""
    # ⚠️ O AUTO (crescimento óbvio, 2 possíveis) SAIU do auto-aplicar (o lote cego morreu):
    # o $40=2×B pode ser chama on-grid que nenhuma régua apanha → passa a SELEÇÃO EM LOTE
    # (olho do Rui). Só ficam automáticos: fills/nomes (crivados) + exclusão (grid-certa).
    out = {}
    for label, fn in (("fills_names", _do_crossing_apply),
                      ("conflicts_exclusion", _do_crossing_exclusion_apply)):
        try:
            out[label] = fn()
        except Exception:
            logger.exception("[crossing/%s] %s falhou", reason, label)
    logger.info("[crossing/%s] %s", reason, out)
    return out


@router.get("/crossing/conflicts/eye")
def crossing_conflicts_eye(n: int = Query(20, ge=1, le=200),
                           current_user=Depends(require_auth)):
    """Os conflitos INCOMPATÍVEIS para o olho do Rui — seat + os valores lidos (com fonte,
    hora e IMAGEM de cada) → ele escolhe. A escrita é o /set-bounties (manual, selado)."""
    _a, _x, eye = _crossing_conflicts()
    return {"count": len(eye), "conflicts": eye[:n]}


@router.get("/crossing/conflicts/exclusion")
def crossing_conflicts_exclusion(n: int = Query(200, ge=1, le=500),
                                 current_user=Depends(require_auth)):
    """PAINEL INFORMATIVO (não-worklist): conflitos resolvidos por EXCLUSÃO DE PARTES — a
    chama < KO inicial morreu, ficou o `stored` são. Cada linha: mão (nº+link) + as leituras
    (com imagem) + o valor que ficou (`kept`). Não prende nada, não conta como pendência.
    A resolução (selo `cross_exclusion`) corre sozinha no reconcile de import."""
    _a, exclusion, _e = _crossing_conflicts()
    return {"count": len(exclusion), "items": exclusion[:n]}


@router.get("/crossing/conflicts/auto-list")
def crossing_conflicts_auto_list(current_user=Depends(require_auth)):
    """LISTA COMPLETA dos conflitos AUTO para a SELEÇÃO EM LOTE (o lote cego morreu). Cada
    item: o `winner` que se escreveria + as leituras (valor+fonte+hora+IMAGEM) + torneio + B
    (coroa fresca) → o Rui varre, desmarca os podres (chama on-grid como o $40=2×B do
    WhereIsMyBeer) e carimba os selecionados. READ-ONLY."""
    auto, _x, _e = _crossing_conflicts()
    return {"count": len(auto), "items": auto}


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


def _crowns_from_witness(img_b64, gold: bool) -> dict:
    """name(lower) → coroa lida, via Vision (prompt NOVO) sobre UMA testemunha
    (gold=entry replayer / table-SS). {} em falha."""
    if not img_b64:
        return {}
    import base64
    from app.services.image_utils import detect_image_mime
    try:
        img = base64.b64decode(img_b64)
    except Exception:
        return {}
    mime = detect_image_mime(img) or "image/png"
    out = {}
    if gold:
        from app.routers.screenshot import (
            _extract_hand_data_from_image_claude, _parse_vision_response)
        raw = _extract_hand_data_from_image_claude(img, mime)
        data = _parse_vision_response(raw) if raw else {}
        for s in data.get("players_list", []):
            if s.get("name"):
                out[str(s["name"]).strip().lower()] = s.get("bounty_value_usd")
    else:
        from app.services.table_ss_vision import (
            extract_table_ss_json, parse_and_validate_table_ss_json)
        raw = extract_table_ss_json(img, mime)
        data = parse_and_validate_table_ss_json(raw) if raw else None
        for s in (data or {}).get("seats", []):
            if s.get("nick"):
                out[str(s["nick"]).strip().lower()] = s.get("bounty_usd")
    return out


def _hand_witnesses(entry_id, ctx) -> tuple:
    """(gold_map, ss_map) — coroas das 2 testemunhas da MESMA mão via Vision novo."""
    gold_map, ss_map = {}, {}
    if ctx:
        c = query("SELECT img_b64 FROM table_ss_processing_log WHERE id=%s", (ctx,))
        if c and c[0]["img_b64"]:
            ss_map = _crowns_from_witness(c[0]["img_b64"], gold=False)
    if entry_id:
        c = query("SELECT raw_json->>'img_b64' b FROM entries WHERE id=%s", (entry_id,))
        if c and c[0]["b"]:
            gold_map = _crowns_from_witness(c[0]["b"], gold=True)
    return gold_map, ss_map


def _to_float(v):
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


@router.post("/crowns/high-reread-confirm")
def crowns_high_reread_confirm(payload: dict = Body(...),
                               current_user=Depends(require_auth_or_api_key)):
    """Grupo 'Valor alto' — re-lê cada mão (coroa > 3×base não confirmada) e
    AUTO-CARIMBA (`bounty_confirmed`) os seats cuja re-leitura BATE o valor gravado
    (tolerância de cêntimos: max($1, 0.5%)). Consistência entre leituras independentes
    = prova (lição 11 Jul). Divergentes ficam no grupo, devolvidos com os 2 valores
    lado a lado. body: {"hand_ids":[...], "dry_run":bool}. NÃO altera valores — só o
    flag; divergentes ficam intactos p/ o olho do Rui."""
    from app.services.queue_export import detect_bounty_above_3x
    hand_ids = payload.get("hand_ids") or []
    dry_run = bool(payload.get("dry_run", False))
    results = []
    for hid in hand_ids:
        rows = query(
            "SELECT h.id, h.entry_id, h.context_table_ss_id ctx, h.player_names pn, "
            "  ts.buy_in_bounty base "
            "FROM hands h LEFT JOIN tournament_summaries ts "
            "  ON ts.site='GGPoker' AND ts.tournament_number=h.tournament_number "
            "WHERE h.hand_id=%s", (hid,))
        if not rows:
            results.append({"hand_id": hid, "error": "not found"}); continue
        r = rows[0]
        pn = r["pn"]
        if isinstance(pn, str): pn = json.loads(pn or "{}")
        highs = detect_bounty_above_3x(pn, r["base"])
        if not highs:
            results.append({"hand_id": hid, "skip": "sem coroa alta por confirmar"}); continue
        high_names = {h["name"] for h in highs}
        # 1 testemunha basta (a que gravou o valor); preferir table-SS, senão gold
        gold_map, ss_map = _hand_witnesses(r["entry_id"], r["ctx"])
        vmap = ss_map or gold_map
        if not vmap:
            results.append({"hand_id": hid, "error": "Vision sem leitura"}); continue
        pl = pn.get("players_list") or []
        confirmed, diverge = [], []
        for e in pl:
            if e.get("name") not in high_names:
                continue
            stored = _to_float(e.get("bounty_value_usd"))
            reread = _to_float(vmap.get(str(e.get("name") or "").strip().lower()))
            tol = max(1.0, (stored or 0) * 0.005)
            if reread is not None and stored is not None and abs(stored - reread) <= tol:
                if not dry_run:
                    e["bounty_confirmed"] = True
                    e.pop("crown_reread", None)          # limpa divergência antiga
                confirmed.append({"name": e.get("name"), "value": stored})
            else:
                if not dry_run:
                    e["crown_reread"] = reread            # persiste p/ o painel (lado a lado)
                diverge.append({"name": e.get("name"), "stored": stored, "reread": reread})
        if (confirmed or diverge) and not dry_run:
            conn = get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute("UPDATE hands SET player_names=%s WHERE id=%s",
                                (json.dumps(pn), r["id"]))
                conn.commit()
            finally:
                conn.close()
        results.append({"hand_id": hid, "auto_confirmed": confirmed, "diverge": diverge})
    return {"results": results, "dry_run": dry_run}


@router.post("/crowns/fallback-fill")
def crowns_fallback_fill(payload: dict = Body(...),
                         current_user=Depends(require_auth_or_api_key)):
    """Fallback SS por seat (desenho do Rui): para seats com coroa NULL/$0, procura o
    valor NOUTRA testemunha da MESMA mão (Gold + table-SS). **Gold preferida**; se NULL
    na Gold usa a table-SS; grava `bounty_source` por seat. Guarda base÷2 aplica-se.
    'por rever' (`crown_review='no_witness_has_plate'`) só quando NENHUMA testemunha tem
    a placa. NÃO toca seats que já têm coroa >0. body: {"hand_ids":[...], "dry_run":bool}."""
    from app.services.table_ss_deanon import _guard_suspect_crowns
    hand_ids = payload.get("hand_ids") or []
    dry_run = bool(payload.get("dry_run", False))
    results = []
    for hid in hand_ids:
        rows = query(
            "SELECT h.id, h.tournament_number tn, h.entry_id, h.context_table_ss_id ctx, "
            "  h.player_names pn, h.all_players_actions apa "
            "FROM hands h WHERE h.hand_id=%s", (hid,))
        if not rows:
            results.append({"hand_id": hid, "error": "not found"}); continue
        r = rows[0]
        pn = r["pn"]; apa = r["apa"]
        if isinstance(pn, str): pn = json.loads(pn or "{}")
        if isinstance(apa, str): apa = json.loads(apa or "{}")
        gold_map, ss_map = _hand_witnesses(r["entry_id"], r["ctx"])
        pl = pn.get("players_list") or []
        filled, still = [], []
        final_by_name = {}
        for e in pl:
            nm = str(e.get("name") or "").strip().lower()
            cur = _to_float(e.get("bounty_value_usd"))
            if cur is not None and cur > 0:
                final_by_name[nm] = cur
                continue                                   # já tem coroa — não tocar
            g = _to_float(gold_map.get(nm)); s = _to_float(ss_map.get(nm))
            chosen, src = (None, None)
            if g is not None and g > 0: chosen, src = g, "gold"
            elif s is not None and s > 0: chosen, src = s, "table_ss"
            if chosen is not None:
                if not dry_run:
                    e["bounty_value_usd"] = chosen
                    e["bounty_source"] = src
                    e.pop("crown_review", None)
                final_by_name[nm] = chosen
                filled.append({"name": e.get("name"), "value": chosen, "source": src})
            else:
                if not dry_run:
                    e["crown_review"] = "no_witness_has_plate"
                still.append({"name": e.get("name")})
        guard = _guard_suspect_crowns(pl, r["tn"])          # base÷2 nos preenchidos
        for e in pl:                                        # refrescar após guarda
            final_by_name[str(e.get("name") or "").strip().lower()] = _to_float(e.get("bounty_value_usd"))
        if isinstance(apa, dict):                           # espelhar no apa
            for k, v in apa.items():
                if k == "_meta" or not isinstance(v, dict): continue
                rn = str(v.get("real_name") or "").strip().lower()
                if rn in final_by_name:
                    v["bounty_value_usd"] = final_by_name[rn]
        if not dry_run and (filled or guard.get("below_half")):
            conn = get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute("UPDATE hands SET player_names=%s, all_players_actions=%s WHERE id=%s",
                                (json.dumps(pn), json.dumps(apa), r["id"]))
                conn.commit()
            finally:
                conn.close()
        results.append({"hand_id": hid, "filled": filled, "still_review": still,
                        "guard": guard,
                        "witnesses": {"gold": bool(gold_map), "table_ss": bool(ss_map)}})
    return {"results": results, "dry_run": dry_run}


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
    from app.services.image_utils import detect_image_mime
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
        mime = detect_image_mime(img_bytes) or "image/png"
        seats = []; err_out = {}; raw = None
        if src == "table_ss":
            raw = extract_table_ss_json(img_bytes, mime, err_out=err_out)
            data = parse_and_validate_table_ss_json(raw) if raw else None
            for s in (data or {}).get("seats", []):
                seats.append({"name": s.get("nick"), "bounty": s.get("bounty_usd"), "vpip": None})
        else:
            raw = _extract_hand_data_from_image_claude(img_bytes, mime)
            data = _parse_vision_response(raw) if raw else {}
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
                    "mime": mime, "raw_len": len(raw or ""),
                    "vision_error": err_out.get("error"),
                    "n_seats": len(seats), "seats": seats, "guard": guard})
    return {"results": out}


@router.post("/crowns/reread")
def crowns_reread(payload: dict = Body(...),
                  current_user=Depends(require_auth_or_api_key)):
    """Botão de RE-LEITURA do painel Coroas (11 Jul) — re-lê a Vision com o prompt
    NOVO (placa de $) sobre a imagem guardada de cada mão suspeita e ESCREVE as
    coroas corrigidas em player_names + all_players_actions. Guarda base÷2 aplicada
    (coroa <½ → NULL + 'por rever'). body: {"hand_ids": [...], "dry_run": bool}.
    Só toca bounty_value_usd + crown_review dos seats que a Vision voltou a ler —
    NÃO mexe nomes, posições, match_method nem anon_map. Seats bounty_confirmed
    (exceção manual) ficam intactos (a guarda salta-os)."""
    import base64
    from app.services.table_ss_vision import (
        extract_table_ss_json, parse_and_validate_table_ss_json)
    from app.routers.screenshot import (
        _extract_hand_data_from_image_claude, _parse_vision_response)
    from app.services.table_ss_deanon import _guard_suspect_crowns
    from app.services.image_utils import detect_image_mime
    hand_ids = payload.get("hand_ids") or []
    dry_run = bool(payload.get("dry_run", False))
    results = []
    for hid in hand_ids:
        rows = query(
            "SELECT h.id, h.hand_id, h.tournament_number tn, h.entry_id, "
            "  h.context_table_ss_id ctx, h.player_names pn, h.all_players_actions apa, "
            "  ts.buy_in_bounty base "
            "FROM hands h LEFT JOIN tournament_summaries ts "
            "  ON ts.site='GGPoker' AND ts.tournament_number=h.tournament_number "
            "WHERE h.hand_id=%s", (hid,))
        if not rows:
            results.append({"hand_id": hid, "error": "not found"}); continue
        r = rows[0]
        floor = (float(r["base"]) / 2.0) if r["base"] is not None else None
        pn = r["pn"]
        if isinstance(pn, str): pn = json.loads(pn or "{}")
        apa = r["apa"]
        if isinstance(apa, str): apa = json.loads(apa or "{}")
        img_b64 = None; src = None
        if r["ctx"]:
            ir = query("SELECT img_b64 FROM table_ss_processing_log WHERE id=%s", (r["ctx"],))
            img_b64 = ir[0]["img_b64"] if ir and ir[0]["img_b64"] else None; src = "table_ss"
        if not img_b64 and r["entry_id"]:
            ir = query("SELECT raw_json->>'img_b64' b FROM entries WHERE id=%s", (r["entry_id"],))
            img_b64 = ir[0]["b"] if ir and ir[0]["b"] else None; src = "gold"
        if not img_b64:
            results.append({"hand_id": hid, "error": "sem imagem guardada"}); continue
        try:
            img_bytes = base64.b64decode(img_b64)
        except Exception as e:
            results.append({"hand_id": hid, "error": f"decode: {e}"}); continue
        mime = detect_image_mime(img_bytes) or "image/png"
        vmap = {}; verr = {}
        if src == "table_ss":
            raw = extract_table_ss_json(img_bytes, mime, err_out=verr)
            data = parse_and_validate_table_ss_json(raw) if raw else None
            for s in (data or {}).get("seats", []):
                if s.get("nick"): vmap[str(s["nick"]).strip().lower()] = s.get("bounty_usd")
        else:
            raw = _extract_hand_data_from_image_claude(img_bytes, mime)
            data = _parse_vision_response(raw) if raw else {}
            for s in data.get("players_list", []):
                if s.get("name"): vmap[str(s["name"]).strip().lower()] = s.get("bounty_value_usd")
        if not vmap:
            results.append({"hand_id": hid, "error": "Vision sem seats",
                            "vision_error": verr.get("error")}); continue
        from app.services.eliminated_bounty import is_bounty_sealed
        pl = pn.get("players_list") or []
        orig = {str(p.get("name") or "").strip().lower(): p.get("bounty_value_usd") for p in pl}
        for p in pl:                                   # aplicar a leitura nova
            if is_bounty_sealed(p):                    # SELO — re-leitura não pisa o carimbo
                continue
            nm = str(p.get("name") or "").strip().lower()
            if nm and nm in vmap:
                p["bounty_value_usd"] = vmap[nm]
        guard = _guard_suspect_crowns(pl, r["tn"])      # base÷2 → NULL + por rever
        changes = []
        final_by_name = {}
        seat_detail = []
        for p in pl:
            nm = str(p.get("name") or "").strip().lower()
            fv = p.get("bounty_value_usd")
            final_by_name[nm] = fv
            before = orig.get(nm)
            vhit = nm in vmap
            if before is None and not vhit:
                continue                                # seat vazio / sem coroa — ignorar
            if fv is not None:
                status = "corrected" if (before or None) != (fv or None) else "unchanged"
                reason = None
            else:
                status = "por_rever"
                if not vhit:
                    reason = "nome não casou (truncado/renomeado) → guarda NULL"
                elif vmap.get(nm) is None:
                    reason = "NULL da Vision (placa ilegível)"
                else:
                    reason = "Vision <½ base (guarda)"
            seat_detail.append({"name": p.get("name"), "before": before, "after": fv,
                                "status": status, "reason": reason})
            if vhit and (orig.get(nm) or None) != (fv or None):
                changes.append({"name": p.get("name"), "old": orig.get(nm), "new": fv})
        if isinstance(apa, dict):                       # espelhar no apa (por real_name)
            for k, v in apa.items():
                if k == "_meta" or not isinstance(v, dict): continue
                rn = str(v.get("real_name") or "").strip().lower()
                if rn and rn in final_by_name:
                    v["bounty_value_usd"] = final_by_name[rn]
        if not dry_run and (changes or guard.get("below_half")):
            conn = get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE hands SET player_names=%s, all_players_actions=%s WHERE id=%s",
                        (json.dumps(pn), json.dumps(apa), r["id"]))
                conn.commit()
            finally:
                conn.close()
        results.append({"hand_id": hid, "src": src, "dry_run": dry_run, "base": r["base"],
                        "guard": guard, "n_changes": len(changes), "changes": changes,
                        "seat_detail": seat_detail, "vision_error": verr.get("error")})
    return {"results": results, "dry_run": dry_run}


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
