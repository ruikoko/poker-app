"""Detetor de bounties recuperáveis — endpoints (#CROWN-RECOVERY).

Varre TODAS as mãos GG KO/PKO com Gold e classifica coroas NULL (via
`services.crown_recovery.classify_hand`): grupo 1 (bustou+NULL = recuperável),
grupo 2 (não-bustou+não-Hero+NULL = falha real → balde das coroas), e over-read
(Seat lines != extraídos → revisão à parte, fora do grupo-1 automático).

Scan em daemon thread com CANCELAR (regra permanente: toda op em lote cancela;
mantém o parcial). Read-only — NÃO escreve. A escrita é o fluxo (A)+(B), gated
pelo carimbo do Rui, mostrando SEMPRE a imagem antes (LICAO 14 Jul)."""
from __future__ import annotations
import json
import logging
import threading
from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException

from app.auth import require_auth, require_auth_or_api_key
from app.db import query, get_conn
from app.services.crown_recovery import classify_hand, seated_hashes

router = APIRouter(prefix="/api/gg-health/crown-recovery", tags=["crown-recovery"])
logger = logging.getLogger("crown_recovery")

_STATE: dict = {
    "status": "idle",          # idle | running | done | cancelled | error
    "done": 0, "total": 0,
    "group1": [], "misread": [], "group2": [], "over_read": [],
    "cancel": False,
    "started_at": None, "finished_at": None, "error": None,
}
_LOCK = threading.Lock()

_POP_SQL = (
    "SELECT h.id, h.hand_id, h.tournament_name, h.tournament_number, h.played_at, "
    "       h.raw, h.player_names AS pn, e.id AS entry_id "
    "FROM hands h JOIN entries e ON e.id = h.entry_id AND e.entry_type='screenshot' "
    "     AND (e.raw_json->>'img_b64') IS NOT NULL "
    "WHERE h.site='GGPoker' AND h.played_at >= '2026-01-01' "
    "  AND lower(COALESCE(h.tournament_format,'')) ~ 'ko|pko|bounty' "
    "ORDER BY h.played_at DESC"
)


def _counter_proof(row, table, bust_hashes) -> dict:
    """Contraprova barata (cinto e suspensórios): o eliminado NÃO se senta na mão
    SEGUINTE da mesma mesa/torneio. Devolve {verdict, seated_next:[hashes vistos]}.
    - confirmed_gone: mão-seguinte existe e nenhum bust_hash lá está → bust firme.
    - seated_next: algum bust_hash sentado na mão-seguinte → NÃO bustou (despromove).
    - no_next_hand: sem mão-seguinte na mesma mesa → inconclusivo (mantém a régua).
    Defensivo: qualquer erro → no_next_hand (nunca parte o lote)."""
    if not bust_hashes or not table or not row.get("tournament_number"):
        return {"verdict": "no_next_hand", "seated_next": []}
    try:
        nxt = query(
            "SELECT raw FROM hands WHERE site='GGPoker' "
            "  AND tournament_number = %s AND raw LIKE %s "
            "  AND played_at > %s AND id <> %s "
            "ORDER BY played_at ASC, id ASC LIMIT 1",
            (row["tournament_number"], f"%Table '{table}'%",
             row["played_at"], row["id"]),
        )
    except Exception:  # pragma: no cover - defensivo
        logger.exception("[crown-recovery] contraprova falhou (hand %s)", row.get("hand_id"))
        return {"verdict": "no_next_hand", "seated_next": []}
    if not nxt:
        return {"verdict": "no_next_hand", "seated_next": []}
    seated = seated_hashes(nxt[0]["raw"])
    still = [h for h in bust_hashes if h in seated]
    return {"verdict": "seated_next" if still else "confirmed_gone", "seated_next": still}


def _run_scan():
    try:
        rows = query(_POP_SQL)
    except Exception as exc:  # pragma: no cover - defensivo
        logger.exception("[crown-recovery] query da população falhou")
        with _LOCK:
            _STATE.update(status="error", error=str(exc),
                          finished_at=datetime.now(timezone.utc).isoformat())
        return
    with _LOCK:
        _STATE.update(status="running", total=len(rows), done=0,
                      group1=[], misread=[], group2=[], over_read=[], error=None,
                      cancel=False,
                      started_at=datetime.now(timezone.utc).isoformat(), finished_at=None)
    cancelled = False
    for r in rows:
        with _LOCK:
            if _STATE.get("cancel"):
                cancelled = True
                break
        try:
            res = classify_hand(r["raw"], r["pn"])
            base = {"hand_db_id": r["id"], "hand_id": r["hand_id"],
                    "entry_id": r["entry_id"], "tournament": r["tournament_name"]}
            if res["over_read"]:
                # over-read fora do grupo-1 automático (revisão à parte)
                with _LOCK:
                    _STATE["over_read"].append({**base, "num_hh": res["num_hh"],
                                                "num_extracted": res["num_extracted"]})
            else:
                if res["group1"]:
                    # contraprova: o eliminado não se senta na mão-seguinte
                    cp = _counter_proof(r, res.get("table"), res.get("bust_hashes"))
                    if cp["verdict"] == "seated_next":
                        # sentou-se na mão-seguinte → NÃO bustou → despromove p/ re-ler
                        with _LOCK:
                            _STATE["misread"].append({
                                **base, "seats": res["group1"],
                                "reason": "seated_next_hand", "seated_next": cp["seated_next"]})
                    else:
                        with _LOCK:
                            _STATE["group1"].append({**base, "busted": res["group1"],
                                                     "matadores": res["matadores"],
                                                     "counter_proof": cp["verdict"]})
                if res.get("misread"):
                    with _LOCK:
                        _STATE["misread"].append({**base, "seats": res["misread"],
                                                  "reason": "alive_resto_bb"})
                if res["group2"]:
                    with _LOCK:
                        _STATE["group2"].append({**base, "seats": res["group2"]})
        except Exception:  # pragma: no cover - defensivo (nunca parte o lote)
            logger.exception("[crown-recovery] classify falhou (hand %s)", r.get("hand_id"))
        with _LOCK:
            _STATE["done"] += 1
    with _LOCK:
        _STATE.update(status="cancelled" if cancelled else "done",
                      finished_at=datetime.now(timezone.utc).isoformat())
    logger.info("[crown-recovery] %s: %d/%d | G1=%d misread=%d G2=%d over=%d",
                "cancelado" if cancelled else "terminado", _STATE["done"], _STATE["total"],
                len(_STATE["group1"]), len(_STATE["misread"]),
                len(_STATE["group2"]), len(_STATE["over_read"]))


_DROPS_SQL = (
    "SELECT h.id, h.hand_id, h.tournament_number AS tn, h.played_at, "
    "       h.player_names AS pn, h.all_players_actions AS apa, h.entry_id, "
    "       ts.buy_in_bounty AS bib "
    "FROM hands h JOIN tournament_summaries ts "
    "  ON ts.site='GGPoker' AND ts.tournament_number = h.tournament_number "
    "WHERE h.site='GGPoker' AND h.played_at >= '2026-01-01' "
    "  AND ts.buy_in_bounty IS NOT NULL AND ts.buy_in_bounty > 0"
)


def _on_halves_grid(crown: float, B: float) -> bool:
    """Grelha das METADES (solo KO): B, 1.5B, 1.75B, …=(2−2⁻ᵏ)B; >=2B livre; <B fora."""
    if B <= 0:
        return True
    q = crown / B
    if q >= 2 - 1e-9:
        return True
    if q < 1 - 1e-9:
        return False
    tol = max(1.0, 0.005 * crown)
    grid = [1.0] + [2 - 2 ** -k for k in range(1, 7)]
    return any(abs(crown - g * B) <= tol for g in grid)


def _norm_key(s):
    import re as _re
    return _re.sub(r"\s+", " ", (s or "").strip().lower())


@router.get("/drops")
def crown_drops(current_user=Depends(require_auth_or_api_key)):
    """Worklist SÓ-LEITURA de coroas SUSPEITAS, para o Rui trabalhar NA app (regra da casa):
    - **QUEDAS**: a coroa do MESMO hash desce entre mãos (impossível no PKO → misread). Cada
      caso traz o valor BAIXO (a mão a rever) + a referência ALTA anterior, com imagens.
      Cosméticos (queda < $1) excluídos.
    - **FORA-DE-GRELHA**: coroa que não cai na grelha das metades (sinalizador leve).
    A escrita é o carimbo (`/set-bounties`, `manual`) — aqui NÃO se escreve nada."""
    from app.services.eliminated_bounty import is_bounty_sealed
    rows = query(_DROPS_SQL)
    from collections import defaultdict
    tl = defaultdict(list)              # (tn, hash) -> [(played_at, crown, hand_db, hand_id, name, entry_id, sealed)]
    off_grid = []
    for r in rows:
        pn = r["pn"] if isinstance(r["pn"], dict) else json.loads(r["pn"] or "{}")
        apa = r["apa"] if isinstance(r["apa"], dict) else json.loads(r["apa"] or "{}")
        B = float(r["bib"]) / 2.0
        for k, v in (apa or {}).items():
            if k == "_meta" or not isinstance(v, dict):
                continue
            bv = v.get("bounty_value_usd")
            try:
                bv = float(bv) if bv is not None else None
            except (TypeError, ValueError):
                bv = None
            if bv is None or bv <= 0:
                continue
            nm = v.get("real_name") or k
            _sealed = is_bounty_sealed(v)
            tl[(r["tn"], k)].append((r["played_at"], round(bv, 2), r["id"], r["hand_id"], nm,
                                     r["entry_id"], _sealed))
            # SELO: um valor validado pelo Rui NUNCA entra num detetor (nem na grelha).
            if not _sealed and not _on_halves_grid(bv, B):
                off_grid.append({"hand_db_id": r["id"], "hand_id": r["hand_id"], "player": nm,
                                 "value": round(bv, 2), "ratio": round(bv / B, 4) if B else None,
                                 "entry_id": r["entry_id"]})
    drops = []
    for key, seq in tl.items():
        seq = sorted(seq, key=lambda x: (x[0] or ""))
        for i in range(len(seq) - 1):
            a, b = seq[i], seq[i + 1]
            # SELO: se o valor BAIXO (o que seria acusado) está SELADO = carimbo do Rui →
            # NUNCA entra no detetor (validado; não se acusa a si próprio).
            if b[6]:
                continue
            if b[1] < a[1] and (a[1] - b[1]) >= 1.0:      # queda >= $1 (exclui cosmético)
                drops.append({
                    "hand_db_id": b[2], "hand_id": b[3], "player": b[4],
                    "low": b[1], "ref": a[1], "ref_hand_db_id": a[2], "ref_hand_id": a[3],
                    "entry_id": b[5], "ref_entry_id": a[5], "kind": "misread"})
    # dedup off-grid por (player, valor) — mostra 1 por caso
    seen = set(); og = []
    for o in sorted(off_grid, key=lambda x: (str(x["player"]).lower(), x["value"])):
        kk = (_norm_key(o["player"]), o["value"])
        if kk in seen:
            continue
        seen.add(kk); og.append(o)
    # Dispensados (legítimos: re-entrada/crescimento) — não reaparecem.
    dismissed = _drops_dismissed_set()
    drops = [d for d in drops if (d["hand_id"], _norm_key(d["player"])) not in dismissed]
    og = [o for o in og if (o["hand_id"], _norm_key(o["player"])) not in dismissed]
    return {"drops": drops, "off_grid": og,
            "counts": {"drops": len(drops), "misread": len(drops), "off_grid": len(og)}}


def _ensure_drops_dismissed():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("CREATE TABLE IF NOT EXISTS crown_drop_dismissed ("
                        "hand_id TEXT, player TEXT, created_at TIMESTAMPTZ DEFAULT now(), "
                        "PRIMARY KEY (hand_id, player))")
        conn.commit()
    finally:
        conn.close()


def _drops_dismissed_set() -> set:
    try:
        _ensure_drops_dismissed()
        rows = query("SELECT hand_id, player FROM crown_drop_dismissed")
        return {(r["hand_id"], _norm_key(r["player"])) for r in rows}
    except Exception:  # pragma: no cover - defensivo
        return set()


@router.post("/drops/dismiss")
def crown_drops_dismiss(payload: dict = Body(...), current_user=Depends(require_auth_or_api_key)):
    """Dispensar um caso da revisão de quedas (legítimo — re-entrada/crescimento): NÃO
    escreve coroa, só marca para não reaparecer. Body: {hand_id, player}."""
    hand_id = (payload or {}).get("hand_id")
    player = (payload or {}).get("player")
    if not hand_id or not player:
        raise HTTPException(400, "hand_id + player obrigatórios")
    _ensure_drops_dismissed()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO crown_drop_dismissed (hand_id, player) VALUES (%s,%s) "
                        "ON CONFLICT DO NOTHING", (hand_id, _norm_key(player)))
        conn.commit()
    finally:
        conn.close()
    return {"status": "dismissed", "hand_id": hand_id, "player": player}


@router.post("/drops/undismiss")
def crown_drops_undismiss(payload: dict = Body(...),
                          current_user=Depends(require_auth_or_api_key)):
    """Reabrir casos de queda dispensados — remove a(s) linha(s) de `crown_drop_dismissed`
    → voltam à worklist. Body: {hand_id, player} (surgical) OU {all: true} (reabre todos).
    Usado para desfazer as dispensas feitas sob a premissa FALSA "migração de unidade" (os
    valores altos antigos eram COROAS CERTAS; a fórmula do verde passou a ×2). Devolve nº reaberto."""
    all_flag = bool((payload or {}).get("all"))
    hand_id = (payload or {}).get("hand_id")
    player = (payload or {}).get("player")
    if not all_flag and not (hand_id and player):
        raise HTTPException(400, "hand_id+player OU all:true obrigatórios")
    _ensure_drops_dismissed()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if all_flag:
                cur.execute("DELETE FROM crown_drop_dismissed")
            else:
                cur.execute("DELETE FROM crown_drop_dismissed WHERE hand_id=%s AND player=%s",
                            (hand_id, _norm_key(player)))
            n = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    logger.info("[crown-recovery] undismiss all=%s hand=%s player=%s -> %d reaberto(s)",
                all_flag, hand_id, player, n)
    return {"status": "undismissed", "reopened": n}


@router.post("/suggest")
def crown_recovery_suggest(payload: dict = Body(...), current_user=Depends(require_auth)):
    """Etapa 2 — "sugerir" LÊ AMBOS numa só chamada (pedido do Rui): corre a Vision UMA vez
    na Gold e devolve (a) `busted` = coroa do ELIMINADO = VERDE × 2 (fórmula do Rui, 20 Jul;
    GREEN_TO_CROWN_FACTOR); (b) `crowns` = a coroa DOURADA de cada jogador lida no
    `players_list` (para o matador). `greens`/`green_total` trazem o verde CRU (informativo).
    Read-only — NÃO escreve. O Rui confere/edita antes de carimbar. Body: {hand_id}."""
    import base64
    from app.services.eliminated_bounty import (
        busted_real_names, resolve_seat_bounty, parse_green_kos, SOURCE_GREEN_KO)
    from app.routers.screenshot import (
        _extract_hand_data_from_image_claude, _parse_vision_response)
    from app.services.image_utils import detect_image_mime
    from app.services.eliminated_bounty import busted_keys_from_hh
    hand_id = (payload or {}).get("hand_id")
    if not hand_id:
        return {"error": "hand_id obrigatório", "busted": {}, "crowns": {}, "image": "none"}
    rows = query(
        "SELECT h.id, h.raw, h.all_players_actions AS apa, h.tournament_number AS tn, "
        "       h.played_at, e.raw_json->>'img_b64' AS gold_img, ts.buy_in_bounty AS bib "
        "  FROM hands h LEFT JOIN entries e ON e.id = h.entry_id "
        "  LEFT JOIN tournament_summaries ts "
        "    ON ts.site='GGPoker' AND ts.tournament_number = h.tournament_number "
        " WHERE h.hand_id = %s", (hand_id,))
    if not rows:
        return {"error": "mão não encontrada", "busted": {}, "crowns": {}, "image": "none"}
    r = rows[0]
    import json as _json
    apa = r["apa"] if isinstance(r["apa"], dict) else _json.loads(r["apa"] or "{}")
    busted = busted_real_names(r["raw"], apa)
    base = (float(r["bib"]) / 2.0) if r["bib"] else None
    # ÚLTIMA COROA CONHECIDA de cada eliminado (valor ESPERADO em multi-KO): o seu hash na
    # última mão ANTERIOR do torneio com coroa lida. Sem leitura anterior → provável fresco=B.
    last_crowns = {}
    try:
        b_keys = busted_keys_from_hh(r["raw"])
        key2name = {k: (v.get("real_name") or k) for k, v in apa.items()
                    if k != "_meta" and isinstance(v, dict)}
        if b_keys and r["tn"]:
            prior = query("SELECT all_players_actions AS apa FROM hands "
                          " WHERE site='GGPoker' AND tournament_number=%s AND played_at < %s "
                          " ORDER BY played_at DESC", (r["tn"], r["played_at"]))
            for k in b_keys:
                nm = key2name.get(k, k)
                for pr in prior:
                    pa = pr["apa"] if isinstance(pr["apa"], dict) else _json.loads(pr["apa"] or "{}")
                    v = (pa or {}).get(k)
                    if isinstance(v, dict) and v.get("bounty_value_usd"):
                        try:
                            last_crowns[nm] = round(float(v["bounty_value_usd"]), 2)
                        except (TypeError, ValueError):
                            pass
                        break
    except Exception:  # pragma: no cover - defensivo
        pass
    b64 = r["gold_img"]
    if not b64:
        # sem Gold → o verde/coroas não estão guardados; lê à mão da imagem na página.
        return {"hand_id": hand_id, "busted": {}, "crowns": {}, "image": "none",
                "note": "sem Gold — lê à mão da imagem"}
    if "," in b64[:40]:
        b64 = b64.split(",", 1)[1]
    try:
        img = base64.b64decode(b64)
    except Exception:
        return {"hand_id": hand_id, "busted": {}, "crowns": {}, "image": "none",
                "error": "imagem ilegível"}
    text = _extract_hand_data_from_image_claude(img, detect_image_mime(img) or "image/png")
    data = _parse_vision_response(text) if text else {}
    greens = parse_green_kos(data)
    # (a) eliminado → coroa = VERDE × 2 (física do Rui; resolve_seat_bounty já ×2).
    # `busted` = coroa (o que se grava); `busted_greens` = o verde CRU lido (= coroa÷2),
    # para o painel mostrar "verde $X → coroa $Y" à vista.
    busted_out = {}
    busted_greens = {}
    for name in sorted(busted):
        val, _review, source = resolve_seat_bounty(name, None, busted_names=busted, green_kos=greens)
        if source == SOURCE_GREEN_KO and val is not None:
            busted_out[name] = val
            busted_greens[name] = round(val / 2.0, 2)   # verde cru = coroa ÷ 2
    # (b) coroa dourada de cada jogador (players_list.bounty_value_usd da Vision)
    crowns = {}
    for p in (data.get("players_list") or []):
        nm = p.get("name"); bv = p.get("bounty_value_usd")
        if nm and bv is not None:
            try:
                crowns[nm] = float(bv)
            except (TypeError, ValueError):
                pass
    result = {"hand_id": hand_id, "busted": busted_out, "busted_greens": busted_greens,
              "crowns": crowns, "greens": greens, "image": "gold",
              "last_crowns": last_crowns, "base": base,
              "green_total": round(sum(g["value"] for g in greens), 2) if greens else None}
    _cache_suggestion(hand_id, result)     # a sugestão PAGA persiste (não evapora no refresh)
    return result


def _ensure_suggestion_cache():
    """Tabela lazy de cache das sugestões da Vision (uma leitura PAGA por mão). Persiste
    entre refreshes/reinícios → o Rui nunca perde o lote a meio da colheita."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("CREATE TABLE IF NOT EXISTS crown_suggestion_cache ("
                        "hand_id TEXT PRIMARY KEY, payload JSONB NOT NULL, "
                        "created_at TIMESTAMPTZ DEFAULT now())")
        conn.commit()
    finally:
        conn.close()


def _cache_suggestion(hand_id: str, payload: dict) -> None:
    try:
        _ensure_suggestion_cache()
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO crown_suggestion_cache (hand_id, payload) VALUES (%s,%s) "
                            "ON CONFLICT (hand_id) DO UPDATE SET payload=EXCLUDED.payload, "
                            "created_at=now()", (hand_id, json.dumps(payload)))
            conn.commit()
        finally:
            conn.close()
    except Exception:  # pragma: no cover - defensivo (cache nunca parte a leitura)
        logger.exception("[crown-recovery] cache da sugestão falhou (hand %s)", hand_id)


@router.get("/suggestions-cache")
def crown_suggestions_cache(current_user=Depends(require_auth_or_api_key)):
    """Devolve TODAS as sugestões da Vision já pagas ({hand_id: payload}). O painel
    recarrega-as no load → o lote sobrevive ao refresh. Read-only."""
    try:
        _ensure_suggestion_cache()
        rows = query("SELECT hand_id, payload FROM crown_suggestion_cache")
        return {"cache": {r["hand_id"]: r["payload"] for r in rows}}
    except Exception:  # pragma: no cover - defensivo
        logger.exception("[crown-recovery] leitura do cache falhou")
        return {"cache": {}}


@router.post("/scan")
def crown_recovery_scan(current_user=Depends(require_auth)):
    """Arranca (ou re-arranca) o scan em daemon thread. Idempotente. Read-only."""
    with _LOCK:
        if _STATE["status"] == "running":
            return {"status": "running", "done": _STATE["done"], "total": _STATE["total"],
                    "note": "já a correr"}
        _STATE["status"] = "running"
    threading.Thread(target=_run_scan, daemon=True).start()
    return {"status": "running", "note": "scan arrancado (todas as KO/PKO c/ Gold)"}


@router.post("/cancel")
def crown_recovery_cancel(current_user=Depends(require_auth)):
    """Cancela o scan em curso — interrompe na próxima mão, mantém o parcial."""
    with _LOCK:
        if _STATE["status"] != "running":
            return {"status": _STATE["status"], "note": "nada a cancelar"}
        _STATE["cancel"] = True
    return {"status": "cancelling", "note": "interrompe na próxima mão; mantém o parcial"}


def _drop_resolved(cards: list) -> list:
    """Filtra os cards cujo(s) seat(s) JÁ têm coroa preenchida na BD (recuperados) —
    INDEPENDENTE do scan em memória (que pode estar velho após carimbos/reload/deploy).
    Fecha o "carimbo que volta": o painel reconhece os resolvidos SEMPRE, venha o estado
    de onde vier. Um card FICA se ainda houver ≥1 seat sem coroa. Fail-open (erro → mostra
    tudo, nunca esconde por engano)."""
    if not cards:
        return cards
    ids = [c.get("hand_db_id") for c in cards if c.get("hand_db_id") is not None]
    if not ids:
        return cards
    try:
        rows = query("SELECT id, player_names FROM hands WHERE id = ANY(%s)", (ids,))
    except Exception:  # pragma: no cover - defensivo
        logger.exception("[crown-recovery] filtro de resolvidos falhou — mostra tudo (seguro)")
        return cards
    crown_by_id = {}
    for r in rows:
        pn = r["player_names"] if isinstance(r["player_names"], dict) else json.loads(r["player_names"] or "{}")
        crown_by_id[r["id"]] = {p.get("name"): p.get("bounty_value_usd")
                                for p in (pn or {}).get("players_list") or [] if isinstance(p, dict)}
    out = []
    for c in cards:
        crowns = crown_by_id.get(c.get("hand_db_id"), {})
        names = [s.get("name") for s in (c.get("busted") or c.get("seats") or []) if isinstance(s, dict)]
        still_null = [n for n in names if crowns.get(n) is None]
        if still_null or not names:          # ainda por recuperar (ou sem info → mantém)
            out.append(c)
    return out


@router.get("")
def crown_recovery_state(current_user=Depends(require_auth_or_api_key)):
    """Progresso + worklists (grupo 1 recuperável, grupo 2 falha real, over-read).
    NÃO escreve nada. Os grupos com carimbo (grupo 1 + misread) são filtrados AO VIVO
    contra a BD → um seat já recuperado NUNCA reaparece (independente do scan em memória)."""
    with _LOCK:
        group1 = list(_STATE["group1"])
        misread = list(_STATE["misread"])
        group2 = list(_STATE["group2"])
        over_read = list(_STATE["over_read"])
        status = _STATE["status"]; done = _STATE["done"]; total = _STATE["total"]
        started_at = _STATE["started_at"]; finished_at = _STATE["finished_at"]; error = _STATE["error"]
    # filtro AO VIVO fora do lock (faz I/O à BD) — fecha o "carimbo que volta"
    group1 = _drop_resolved(group1)
    misread = _drop_resolved(misread)
    return {
        "status": status, "done": done, "total": total,
        "group1_count": len(group1), "misread_count": len(misread),
        "group2_count": len(group2), "over_read_count": len(over_read),
        "group1": group1, "misread": misread, "group2": group2, "over_read": over_read,
        "started_at": started_at, "finished_at": finished_at, "error": error,
    }
