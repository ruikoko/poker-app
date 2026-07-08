"""APA §B.6 Fase 3 — propagação de nomes por HASH (sistema misto, só-tagadas).

Motor da última fase do core (aprovado 8 Jul). Constrói o mapa hash→nome de um
torneio GG lendo de TODAS as mãos com desanon, mas **só nomes de FONTE FORTE**
(`position_v3` / `verified_by_user`) semeiam o mapa (guarda a). Escreve só nas
mãos **TAGADAS** (`hm3_tags` OU `discord_tags` não-vazias): preenche cada hash
**sem** real_name com o nome do mapa, **sem mudar chaves** (Fase 2), com
`match_method='hash_propagation_v1'` e "por verificar" a menos que a fonte seja
`verified_by_user`.

Guardas na construção do mapa:
- (b) nome-já-usado: o MESMO nome em 2 hashes → NENHUM entra no mapa; ambos à
  quarentena (pelo invariante do hash, 2 hashes = 2 pessoas → um nome está errado).
- (c) conflito no mesmo hash: forte vence fraca (só fortes semeiam, logo forte-vs-forte)
  → variantes OCR (via `_ocr_variant`, critério ENDURECIDO — truncagem-prefixo OU distância
  de edição ≤1-2, mais seguro que o `_same_player` das coroas Gold) **auto-merge** quando
  inequívoco; senão quarentena.
- (d) sem semente forte / mapa vazio → branco honesto, zero escrita.

As funções de construção/plano são PURAS (operam sobre linhas de mão já lidas) →
testáveis e corríveis sobre o laboratório. Ver `DESANON_ANATOMIA §3.4`,
`APA_INDEXACAO_E_COLAPSO §B.6`, `FT_BOUNDARY_ANATOMIA.md` (a quarentena é irmã da FT).
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Any, Optional

from app.services.deanon_status import deanon_status

_SEAT_RE = re.compile(r'^Seat \d+: ([0-9a-f]{4,8}) \(', re.M)   # hashes anón (Hero/nomes reais excluídos)
PROPAGATION_MATCH_METHOD = "hash_propagation_v1"


# ── coerção ──────────────────────────────────────────────────────────────────

def _as_dict(v) -> dict:
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except (ValueError, TypeError):
            return {}
    return v if isinstance(v, dict) else {}


def _pn(hand) -> dict:
    return _as_dict(hand.get("player_names"))


def _anon_map(pn: dict) -> dict:
    m = pn.get("anon_map")
    if not isinstance(m, dict):
        return {}
    return {k: v for k, v in m.items()
            if k != "Hero" and isinstance(v, str) and v.strip()}


def _match_method(pn: dict) -> Optional[str]:
    return pn.get("match_method")


def _verified_by_user(pn: dict) -> bool:
    return bool(pn.get("verified_by_user"))


def _is_strong(hand) -> bool:
    """Fonte FORTE = deanon_status 'verified' (position_v3 OU verified_by_user)."""
    pn = _pn(hand)
    return deanon_status(hand.get("site"), _match_method(pn), _verified_by_user(pn)) == "verified"


def _is_tagged(hand) -> bool:
    return bool(hand.get("hm3_tags")) or bool(hand.get("discord_tags"))


def hand_hashes(hand) -> set:
    """Hashes anón (seats) da HH — independente do formato do apa (lê do raw)."""
    return set(_SEAT_RE.findall(hand.get("raw") or ""))


_SEAT_FULL_RE = re.compile(r'^Seat (\d+): (.+?) \(([\d,]+)', re.M)   # seat/nome-ou-hash/stack


def seat_block(raw) -> list:
    """Bloco de Seats do raw (seat/hash/stack) — a matéria do cruzamento posição+stack
    que o Rui usa p/ decidir. Lê a 1ª número da linha como stack (GG `(20000 in chips)`,
    WN `(19245, 50€ bounty)`). Só o ROSTER do topo (antes do 1º `***`) — evita apanhar
    as linhas `Seat N: X won (...)` do SUMMARY. Hero/nicks reais aparecem tal-e-qual."""
    raw = raw or ""
    cut = raw.find("*** ")
    header = raw[:cut] if cut != -1 else raw
    out = []
    for m in _SEAT_FULL_RE.finditer(header):
        out.append({"seat": int(m.group(1)), "hash": m.group(2).strip(),
                    "stack": int(m.group(3).replace(",", ""))})
    return out


# ── construção do mapa hash→nome (guardas a/b/c + OCR-merge) ──────────────────

def _lev(a: str, b: str) -> int:
    """Distância de edição (Levenshtein), iterativa."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _ocr_variant(a: str, b: str) -> bool:
    """True se `a` e `b` são o MESMO jogador módulo truncagem/OCR — critério ENDURECIDO
    (mais seguro que o `_same_player` das coroas Gold, que fundia por prefixo de 6 e
    juntaria por erro 'Daniel Filipe'/'Daniel Ferreira'). Só funde quando é inequívoco:
    truncagem pura (o curto é prefixo do longo) OU distância de edição ≤1 (≤2 p/ nomes
    longos). Rejeita nomes que divergem em tokens (colisão de 1º nome). Aplica-se a
    nomes no MESMO hash (= mesma pessoa pelo invariante), logo o risco é só desanon a
    pôr 2 nomes GENUINAMENTE diferentes no mesmo hash — esses (distância grande) vão à
    quarentena, não se fundem."""
    ca, cb = _norm(a), _norm(b)
    if ca == cb:
        return True
    lo, hi = sorted((ca, cb), key=len)
    if len(lo) >= 4 and hi.startswith(lo):    # truncagem pura
        return True
    if abs(len(ca) - len(cb)) <= 2:            # OCR: distância pequena
        return _lev(ca, cb) <= (1 if min(len(ca), len(cb)) < 12 else 2)
    return False


def _merge_ocr(names: list[str]) -> Optional[str]:
    """Se todos os nomes são o MESMO jogador módulo truncagem/OCR (via `_ocr_variant`),
    devolve o canónico (o mais comprido = leitura mais completa); senão None (conflito
    genuíno → quarentena)."""
    uniq = list(dict.fromkeys(n for n in names if n and n.strip()))
    if not uniq:
        return None
    if len(uniq) == 1:
        return uniq[0]
    canonical = max(uniq, key=len)
    if all(_ocr_variant(canonical, n) for n in uniq):
        return canonical
    return None


def build_name_map(hands: list[dict]) -> tuple[dict, list[dict]]:
    """Constrói o mapa hash→{name, verified} de UM torneio a partir das mãos.
    Só FORTES semeiam. Devolve (clean_map, quarantine).

    clean_map: {hash: {"name": str, "verified": bool}}
    quarantine: [{"kind": "same_hash"|"name_2_hash", "hash"/"name", "candidates":[...],
                  "hands": [hand_id,...]}]
    """
    # 1) recolher nomes fortes por hash (com proveniência)
    hash_names: dict[str, list[str]] = defaultdict(list)
    hash_verified: dict[str, bool] = defaultdict(bool)
    hash_hands: dict[str, set] = defaultdict(set)
    for h in hands:
        if not _is_strong(h):
            continue
        pn = _pn(h)
        ver = _verified_by_user(pn)
        for hsh, name in _anon_map(pn).items():
            hash_names[hsh].append(name)
            hash_verified[hsh] = hash_verified[hsh] or ver
            hash_hands[hsh].add(h.get("hand_id"))

    quarantine: list[dict] = []
    tentative: dict[str, dict] = {}   # hash -> {name, verified}
    # 2) guarda (c) — resolver conflito no mesmo hash (OCR-merge ou quarentena)
    for hsh, names in hash_names.items():
        merged = _merge_ocr(names)
        if merged is None:
            quarantine.append({
                "kind": "same_hash", "hash": hsh,
                "candidates": sorted(set(names)),
                "hands": sorted(x for x in hash_hands[hsh] if x),
            })
            continue
        tentative[hsh] = {"name": merged, "verified": hash_verified[hsh]}

    # 3) guarda (b) — nome-já-usado (mesmo nome em 2+ hashes) → ambos à quarentena
    name_to_hashes: dict[str, list[str]] = defaultdict(list)
    for hsh, info in tentative.items():
        name_to_hashes[_norm(info["name"])].append(hsh)
    clean: dict[str, dict] = {}
    for hsh, info in tentative.items():
        dupes = name_to_hashes[_norm(info["name"])]
        if len(dupes) > 1:
            continue   # veneno — não entra no mapa (a quarentena regista-se abaixo, 1x por nome)
        clean[hsh] = info
    for nnm, hs in name_to_hashes.items():
        if len(hs) > 1:
            quarantine.append({
                "kind": "name_2_hash", "name": tentative[hs[0]]["name"],
                "candidates": sorted(hs),
                "hands": sorted({x for h in hs for x in hash_hands[h] if x}),
            })
    return clean, quarantine


def _norm(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").lower().rstrip(". ").strip())


# ── lados de um conflito de quarentena (contexto p/ o Rui decidir) ────────────

def conflict_sides(hands: list, item: dict) -> list:
    """Para UM item de quarentena, devolve os LADOS (candidatos) com o contexto que o
    Rui precisa p/ decidir: as aparições (mão + fonte forte/fraca) de cada lado. PURA —
    NÃO lê imagens (o router junta-as por `db_ids`, que aqui só se coleccionam).

    - `name_2_hash` (nome em 2 lugares): um lado por HASH candidato → as mãos onde esse
      hash carrega o nome (é entre estes 2 lugares que o Rui escolhe qual é o jogador).
    - `same_hash` (hash lido com nomes diferentes): um lado por VARIANTE de nome → as
      mãos/aparições onde o hash foi lido como essa variante.
    """
    kind = item.get("kind")
    key = item.get("conflict_key")
    cands = item.get("candidates") or []
    sides = []

    def _appear_for(match, disputed_hash) -> list:
        """match(hand) -> (matches: bool, display_name: str|None). `disputed_hash` = a
        chave em disputa neste lado (p/ destacar o seat no bloco de Seats do raw)."""
        out = []
        for h in hands:
            ok, nm = match(h)
            if ok:
                seats = seat_block(h.get("raw"))
                for s in seats:
                    s["disputed"] = (s["hash"] == disputed_hash)
                out.append({"hand_id": h.get("hand_id"), "db_id": h.get("id"),
                            "name": nm, "source": "strong" if _is_strong(h) else "weak",
                            "seats": seats})
        out.sort(key=lambda a: (a["source"] != "strong", a["hand_id"] or ""))
        return out

    if kind == "name_2_hash":
        for hc in cands:
            def _m(h, hc=hc):
                am = _anon_map(_pn(h))
                return (hc in am, am.get(hc))
            appear = _appear_for(_m, hc)
            name = next((a["name"] for a in appear if a["source"] == "strong"),
                        appear[0]["name"] if appear else key)
            sides.append({"kind": "hash", "hash": hc, "name": name,
                          "db_ids": [a["db_id"] for a in appear if a.get("db_id")],
                          "appearances": appear})
    elif kind == "same_hash":
        for nv in cands:
            nnorm = _norm(nv)
            def _m(h, nnorm=nnorm):
                nm = _anon_map(_pn(h)).get(key)
                return (bool(nm) and _norm(nm) == nnorm, nm)
            appear = _appear_for(_m, key)
            sides.append({"kind": "name", "name": nv,
                          "db_ids": [a["db_id"] for a in appear if a.get("db_id")],
                          "appearances": appear})
    return sides


# ── classificador de RE-ENTRADA (o hash é fixo por ENTRADA, não por pessoa) ───

def reentry_hint(hands: list, item: dict) -> dict:
    """Para um conflito `name_2_hash`, avalia se os 2 hashes são a MESMA pessoa por
    RE-ENTRADA. Base: o hash GG é fixo por ENTRADA — um re-buy gera hash NOVO p/ o
    mesmo humano (o invariante 1-hash=1-pessoa continua; o inverso 1-pessoa=1-hash NÃO
    vale em torneios re-entry). Sinais:
      - `same_nick`  : mesmo nick EXATO nos 2 lados (nicks GG são únicos por conta);
      - `both_strong`: fonte FORTE dos dois lados (position_v3 / verificado);
      - `disjoint_windows`: janelas de aparição SEM sobreposição (um lado todo antes
        do outro) — coerente com sair e voltar a entrar;
      - `co_present` : os 2 hashes na MESMA mão → IMPOSSÍVEL ser 1 pessoa → VENENO duro.
    `likely_reentry` = same_nick ∧ both_strong ∧ disjoint ∧ ¬co_present. A decisão é
    SEMPRE clique do Rui (isto só PRÉ-SELECCIONA o verbo; nunca auto-resolve).
    Ver `DESANON_ANATOMIA §3.3`, `REGISTO_CONCEITO 2026-07-08` (Olisadebee)."""
    if item.get("kind") != "name_2_hash":
        return {"applies": False}
    cands = item.get("candidates") or []
    if len(cands) != 2:
        return {"applies": False}
    ha, hb = cands
    co_present = False
    times = {ha: [], hb: []}
    strong = {ha: False, hb: False}
    names = {ha: set(), hb: set()}
    for h in hands:
        hs = hand_hashes(h)
        has_a, has_b = ha in hs, hb in hs
        if has_a and has_b:
            co_present = True
        am = _anon_map(_pn(h))
        st = _is_strong(h)
        pat = h.get("played_at")
        for hx in (ha, hb):
            if hx in am:
                names[hx].add(_norm(am[hx]))
                strong[hx] = strong[hx] or st
                if pat is not None:
                    times[hx].append(pat)
    disjoint = None
    if times[ha] and times[hb]:
        disjoint = (max(times[ha]) < min(times[hb])) or (max(times[hb]) < min(times[ha]))
    same_nick = bool(names[ha] and names[ha] == names[hb])
    both_strong = strong[ha] and strong[hb]
    likely = bool(same_nick and both_strong and disjoint is True and not co_present)
    return {
        "applies": True, "co_present": co_present, "disjoint_windows": disjoint,
        "same_nick": same_nick, "both_strong": both_strong, "likely_reentry": likely,
    }


# ── plano de propagação (só-tagadas; preenche brancos) ───────────────────────

def propagation_plan(hands: list[dict], clean_map: dict) -> dict:
    """Para cada mão TAGADA, calcula os hashes SEM nome que o mapa preenche.
    Devolve {changes: [{hand_id, fills:{hash:name}, verified_fills, ...}],
             blanks: set(hash), stats}. Não escreve."""
    changes = []
    blanks: set = set()
    resolved = 0
    tagged = [h for h in hands if _is_tagged(h)]
    quarantine_hashes = set()   # preenchido pelo caller p/ não contar como branco
    for h in tagged:
        vill = hand_hashes(h)
        if not vill:
            continue
        own = _anon_map(_pn(h))          # hashes já com nome nesta mão
        fills, ver_fills = {}, {}
        for v in vill:
            if v in own:
                continue                 # já tem nome (não sobrescreve)
            if v in clean_map:
                fills[v] = clean_map[v]["name"]
                if clean_map[v]["verified"]:
                    ver_fills[v] = True
            else:
                blanks.add(v)
        # "resolvida" = todos os vilões com nome (próprio OU preenchido)
        if all((v in own) or (v in fills) for v in vill):
            resolved += 1
        if fills:
            changes.append({
                "hand_id": h.get("hand_id"), "db_id": h.get("id"),
                "fills": fills, "verified_fills": ver_fills,
            })
    return {
        "changes": changes,
        "blank_hashes": blanks,
        "stats": {
            "tagged_hands": len(tagged),
            "hands_with_fills": len(changes),
            "hands_resolved_after": resolved,
            "fills_total": sum(len(c["fills"]) for c in changes),
            "blank_hashes": len(blanks),
        },
    }


# ── logging ──────────────────────────────────────────────────────────────────
import logging
logger = logging.getLogger("name_propagation")


# ── schema da quarentena de nomes (irmã da ft_boundary_review) ────────────────

def ensure_name_quarantine_schema(conn=None) -> None:
    own = conn is None
    if own:
        from app.db import get_conn
        conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS name_quarantine_review (
                    id                BIGSERIAL PRIMARY KEY,
                    tournament_number TEXT NOT NULL,
                    kind              TEXT NOT NULL,
                    conflict_key      TEXT NOT NULL,
                    candidates        JSONB,
                    hands             JSONB,
                    decision          TEXT NOT NULL DEFAULT 'pending',
                    chosen_name       TEXT,
                    chosen_hash       TEXT,
                    decided_by        TEXT,
                    decided_at        TIMESTAMP,
                    updated_at        TIMESTAMP DEFAULT (now() at time zone 'utc'),
                    UNIQUE (tournament_number, kind, conflict_key)
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_nqr_tn ON name_quarantine_review(tournament_number)")
        conn.commit()
    finally:
        if own:
            conn.close()


# ── escrita dos preenchimentos (formato Fase 2: apa hash-keyed) ───────────────

def _write_fills(conn, db_id: int, fills: dict, verified_fills: dict) -> int:
    """Escreve os preenchimentos numa mao. Idempotente: salta hashes que ja tem o nome.
    Preenche SO hashes que sao chave do apa (nao inventa). Devolve n escrito."""
    with conn.cursor() as cur:
        cur.execute("SELECT all_players_actions apa, player_names pn FROM hands WHERE id=%s", (db_id,))
        row = cur.fetchone()
        if not row:
            return 0
        apa = _as_dict(row["apa"])
        pn = _as_dict(row["pn"])
        anon = pn.get("anon_map") if isinstance(pn.get("anon_map"), dict) else {}
        written = 0
        for hsh, name in fills.items():
            entry = apa.get(hsh)
            if not isinstance(entry, dict):
                continue
            if (entry.get("real_name") or "") == name and anon.get(hsh) == name:
                continue
            entry["real_name"] = name
            entry["name_source"] = PROPAGATION_MATCH_METHOD
            entry["name_verified"] = bool(verified_fills.get(hsh))
            anon[hsh] = name
            written += 1
        if not written:
            return 0
        pn["anon_map"] = anon
        mm = pn.get("match_method")
        if not mm or str(mm).startswith("discord_placeholder"):
            pn["match_method"] = PROPAGATION_MATCH_METHOD
        cur.execute("UPDATE hands SET all_players_actions=%s, player_names=%s WHERE id=%s",
                    (json.dumps(apa), json.dumps(pn), db_id))
    return written


def apply_propagation(hands: list, clean_map: dict, *, conn=None, dry_run: bool = True) -> dict:
    """Aplica o plano as maos tagadas. dry_run=True devolve so o plano. Escreve
    idempotentemente e re-avalia viloes nas maos alteradas."""
    plan = propagation_plan(hands, clean_map)
    if dry_run:
        return {"dry_run": True, **plan["stats"], "changes": plan["changes"]}
    own = conn is None
    if own:
        from app.db import get_conn
        conn = get_conn()
    written_hands = []
    try:
        for ch in plan["changes"]:
            if _write_fills(conn, ch["db_id"], ch["fills"], ch["verified_fills"]):
                written_hands.append(ch["db_id"])
        conn.commit()
        from app.services.villain_rules import apply_villain_rules
        for db_id in written_hands:
            try:
                apply_villain_rules(db_id, conn=conn)
            except Exception:
                logger.exception("apply_villain_rules falhou hand %s", db_id)
        conn.commit()
    finally:
        if own:
            conn.close()
    return {"dry_run": False, "hands_written": len(written_hands), **plan["stats"]}


# ── review da quarentena (decisoes persistidas, respeitadas por re-runs) ──────

def _load_tournament_hands(conn, tn: str) -> list:
    with conn.cursor() as cur:
        cur.execute("""SELECT id, hand_id, site, raw, player_names, hm3_tags, discord_tags,
                              played_at
                       FROM hands WHERE site='GGPoker' AND tournament_number=%s
                       AND played_at >= '2026-01-01'""", (tn,))
        return [dict(r) for r in cur.fetchall()]


def _quar_key(q: dict) -> str:
    return q["hash"] if q["kind"] == "same_hash" else q["name"]


def _load_decisions(conn, tn: str) -> dict:
    with conn.cursor() as cur:
        cur.execute("""SELECT kind, conflict_key, decision, chosen_name, chosen_hash
                       FROM name_quarantine_review WHERE tournament_number=%s""", (tn,))
        return {(r["kind"], r["conflict_key"]): dict(r) for r in cur.fetchall()}


def _apply_decisions_to_map(clean: dict, quarantine: list, decisions: dict):
    """Decisoes RESOLVIDAS entram no mapa (decisao manual = verified); DISPENSADAS ficam
    brancas; PENDENTES continuam na quarentena. Respeitado por todos os re-runs."""
    still = []
    for q in quarantine:
        dec = decisions.get((q["kind"], _quar_key(q)))
        if not dec or dec["decision"] == "pending":
            still.append(q)
            continue
        if dec["decision"] == "dismissed":
            continue
        if dec["decision"] == "reentry" and q["kind"] == "name_2_hash":
            # RE-ENTRADA: os 2 hashes são a mesma pessoa (entradas distintas) → o nome
            # fica válido nos DOIS. Sai da quarentena; ambos elegíveis p/ propagação.
            # NÃO funde registos (stacks/mãos/stats separados) — só o NOME é partilhado.
            nm = dec.get("chosen_name") or q.get("name")
            if nm:
                for hsh in q.get("candidates", []):
                    clean[hsh] = {"name": nm, "verified": True}
            continue
        if dec["decision"] in ("chosen", "merged") and dec.get("chosen_name"):
            if q["kind"] == "same_hash":
                clean[q["hash"]] = {"name": dec["chosen_name"], "verified": True}
            elif dec.get("chosen_hash"):
                clean[dec["chosen_hash"]] = {"name": dec["chosen_name"], "verified": True}
        else:
            still.append(q)
    return clean, still


def _upsert_quarantine(conn, tn: str, quarantine: list) -> None:
    """Regista/atualiza as PENDENTES; NAO toca em linhas ja decididas."""
    with conn.cursor() as cur:
        for q in quarantine:
            cur.execute("""
                INSERT INTO name_quarantine_review
                    (tournament_number, kind, conflict_key, candidates, hands)
                VALUES (%s,%s,%s,%s,%s)
                ON CONFLICT (tournament_number, kind, conflict_key) DO UPDATE
                    SET candidates=EXCLUDED.candidates, hands=EXCLUDED.hands,
                        updated_at=(now() at time zone 'utc')
                    WHERE name_quarantine_review.decision='pending'
            """, (tn, q["kind"], _quar_key(q),
                  json.dumps(q["candidates"]), json.dumps(q.get("hands", []))))
    conn.commit()


def refresh_name_propagation(tn: str, *, conn=None, auto_write: bool = True) -> dict:
    """Recomputa o mapa, aplica decisoes da quarentena, regista pendentes e (auto_write)
    escreve a propagacao LIMPA nas tagadas. Idempotente. E o que os gatilhos correm."""
    own = conn is None
    if own:
        from app.db import get_conn
        conn = get_conn()
    try:
        ensure_name_quarantine_schema(conn)
        hands = _load_tournament_hands(conn, tn)
        if not hands:
            return {"tn": tn, "skipped": "no_hands"}
        clean, quarantine = build_name_map(hands)
        decisions = _load_decisions(conn, tn)
        clean, quarantine = _apply_decisions_to_map(clean, quarantine, decisions)
        _upsert_quarantine(conn, tn, quarantine)
        result = apply_propagation(hands, clean, conn=conn, dry_run=not auto_write)
        return {"tn": tn, "quarantine_pending": len(quarantine), "map_size": len(clean), **result}
    finally:
        if own:
            conn.close()


def _all_tagged_gg_tns() -> list:
    """Todos os torneios GG 2026 com >=1 mao tagada (universo da propagacao)."""
    from app.db import query
    rows = query("""SELECT DISTINCT tournament_number FROM hands
        WHERE site='GGPoker' AND played_at >= '2026-01-01' AND tournament_number IS NOT NULL
          AND (COALESCE(array_length(hm3_tags,1),0)>0 OR COALESCE(array_length(discord_tags,1),0)>0)""")
    return [r["tournament_number"] for r in rows]


def trigger_name_propagation(tns=None) -> None:
    """Fire-and-forget: refresh da propagacao. `tns` = str/lista de torneios, OU None
    (varre TODOS os GG tagados — modo dos gatilhos de import, à imagem do FT). Idempotente
    (só escreve o que falta). Nunca lanca (defensivo — não parte o import que o dispara)."""
    import threading
    if isinstance(tns, str):
        tns = [tns]
    specific = [t for t in {str(x) for x in (tns or []) if x}]

    def _run():
        targets = specific or _all_tagged_gg_tns()
        for tn in targets:
            try:
                refresh_name_propagation(tn, auto_write=True)
            except Exception:
                logger.exception("[name_propagation] refresh falhou tn=%s", tn)

    threading.Thread(target=_run, daemon=True).start()
