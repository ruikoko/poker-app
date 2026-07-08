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
from collections import Counter, defaultdict
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
    quarantine: [{"kind": "same_hash"|"name_2_hash"|"strong_weak_mismatch", "hash"/"name",
                  "candidates":[...], "hands": [hand_id,...]}]
    """
    # 1) recolher nomes FORTES por hash (semeiam) + FRACOS por hash (p/ o mismatch)
    hash_names: dict[str, list[str]] = defaultdict(list)
    hash_verified: dict[str, bool] = defaultdict(bool)
    hash_hands: dict[str, set] = defaultdict(set)
    weak_names: dict[str, list[tuple]] = defaultdict(list)   # hash -> [(name, hand_id)]
    for h in hands:
        pn = _pn(h)
        if _is_strong(h):
            ver = _verified_by_user(pn)
            for hsh, name in _anon_map(pn).items():
                hash_names[hsh].append(name)
                hash_verified[hsh] = hash_verified[hsh] or ver
                hash_hands[hsh].add(h.get("hand_id"))
        else:
            for hsh, name in _anon_map(pn).items():
                weak_names[hsh].append((name, h.get("hand_id")))

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

    # 4) NOVO — strong_weak_mismatch: hash com nome FORTE X + leitura(s) FRACA(s)
    # divergente(s) (Y != X e não OCR-variante de X). Hoje passavam em silêncio (só os
    # fortes semeiam) → misread fraco ficava agarrado (caso 93d63976 "Vadzim" forte + 4
    # "Diego Emperador" fracas). O hash MANTÉM o nome forte no mapa (não-bloqueante); o
    # cartão é p/ confirmar o forte → scrub das fracas. Só p/ hashes que ficaram em `clean`.
    for hsh, info in clean.items():
        strongset = set(hash_names.get(hsh, []))
        snorm = {_norm(s) for s in strongset}
        mism = [(nm, hid) for (nm, hid) in weak_names.get(hsh, [])
                if _norm(nm) not in snorm and not any(_ocr_variant(nm, s) for s in strongset)]
        if mism:
            quarantine.append({
                "kind": "strong_weak_mismatch", "hash": hsh, "name": info["name"],
                "candidates": sorted({info["name"]} | {m[0] for m in mism}),
                "hands": sorted({m[1] for m in mism if m[1]}),
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
    elif kind in ("same_hash", "strong_weak_mismatch"):
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

# bala fresca ≈ starting stack (BANDA, não `>=`): um re-buy dá ~o stack de arranque, NUNCA
# muito mais — um stack grande herdado (jogador acumulado, não re-buy) fica FORA em cima.
# A banda é generosa em baixo porque o `start_stack` é MEDIDO (max na 1ª mão conhecida) e
# pode vir sobrestimado (líder), enquanto o re-buy real = arranque verdadeiro.
_FRESH_STACK_LO = 0.80          # tolerância em baixo (antes/blinds + erro de medição do start)
_FRESH_STACK_HI = 1.15          # em cima: exclui "stack herdado grande" (>start)
_REBUY_GAP_MAX_S = 60 * 60      # gap curto = <= 1h (minutos-a-1h; "minutos, não horas")


def _iso(dt):
    try:
        return dt.isoformat()
    except Exception:
        return None


def _stack_in(raw, h):
    for s in seat_block(raw):
        if s["hash"] == h:
            return s["stack"]
    return None


def _tournament_start_stack(hands: list):
    """Stack de arranque do torneio = MAIOR stack na 1ª mão cronológica (na mão 1 todos
    têm a bala full). Coverage gap (1ª mão conhecida é já mid-torneio) → sobrestima o
    arranque → a bala fresca falha o teste → NÃO promove a confirmed (fica likely) —
    conservador por desenho (a nota de honestidade: só promover por presença de dados)."""
    dated = [h for h in hands if h.get("played_at") is not None and h.get("raw")]
    if not dated:
        return None
    first = min(dated, key=lambda h: h.get("played_at"))
    return max((s["stack"] for s in seat_block(first.get("raw"))), default=None)


def _line_about(t: str, h: str) -> bool:
    """A linha do raw é SOBRE o hash `h`? (acção `<h>: …` / `<h> collected …` / SUMMARY
    `Seat N: <h> …`). Evita colisão por prefixo exigindo `:`/espaço/`(` a seguir."""
    return (t.startswith(h + ":") or t.startswith(h + " ")
            or bool(re.search(r'Seat \d+:\s*' + re.escape(h) + r'\b', t)))


def _all_in_and_result(raw, h) -> tuple:
    """Na mão (raw), o hash `h` foi ALL-IN e COLECTOU o pote? Devolve (all_in, collected).
    Bust = all_in ∧ ¬collected (foi com tudo e o pote foi para outro)."""
    all_in = collected = False
    for line in (raw or "").splitlines():
        t = line.strip()
        if not _line_about(t, h):
            continue
        low = t.lower()
        if "all-in" in low:
            all_in = True
        if "collected" in low or "and won" in low or " won (" in low or "wins" in low:
            collected = True
    return all_in, collected


def reentry_hint(hands: list, item: dict) -> dict:
    """Para um conflito `name_2_hash`, avalia se os 2 hashes são a MESMA pessoa por
    RE-ENTRADA. Base: o hash GG é fixo por ENTRADA — um re-buy gera hash NOVO p/ o
    mesmo humano (o invariante 1-hash=1-pessoa continua; o inverso 1-pessoa=1-hash NÃO
    vale em torneios re-entry).

    SINAIS FRACOS (sempre): `same_nick` (nick exacto), `both_strong` (fonte forte dos 2
    lados), `disjoint_windows` (janelas sem sobreposição), `co_present` (2 hashes na mesma
    mão → VENENO duro). `likely_reentry` = same_nick ∧ both_strong ∧ disjoint ∧ ¬co_present.

    EVIDÊNCIA DURA na HH (promove a `level='confirmed'`):
      1. **BUST da 1ª entrada** — na ÚLTIMA mão do hash EARLY (última aparição), ele foi
         all-in e o pote foi para outro (`_all_in_and_result`).
      2. **BALA FRESCA da 2ª** — o stack inicial do hash LATE na 1ª mão dele ≈ starting
         stack do torneio (`>= _FRESH_STACK_FRAC × start`).
      3. **GAP curto** entre o bust e a 1ª mão do late (<= 1h).
    `level` ∈ {`confirmed`, `likely`, None}. **Nota de honestidade:** a ausência de bust
    legível (não-GG, HH em falta) NUNCA despromove um `likely` — só a PRESENÇA de evidência
    promove a `confirmed`. A decisão é SEMPRE clique do Rui.
    Ver `DESANON_ANATOMIA §3.3`, `REGISTO_CONCEITO 2026-07-08` (Olisadebee/AmigoCrypto)."""
    if item.get("kind") != "name_2_hash":
        return {"applies": False}
    cands = item.get("candidates") or []
    if len(cands) != 2:
        return {"applies": False}
    ha, hb = cands
    co_present = False
    # SEATED = mãos onde o hash está nos SEATS do raw (jogou, tenha nome ou não) → janelas
    # + bust/rebuy. NAMED = mãos onde tem nome no apa → nick/força. (Distinção crítica: o
    # bust está na última mão JOGADA, que pode NÃO estar desanonimizada.)
    seated = {ha: [], hb: []}
    strong_names = {ha: [], hb: []}   # leituras de FONTE FORTE (o nick fiável)
    for h in hands:
        hs = hand_hashes(h)
        has_a, has_b = ha in hs, hb in hs
        if has_a and has_b:
            co_present = True
        am = _anon_map(_pn(h))
        st = _is_strong(h)
        for hx, seated_here in ((ha, has_a), (hb, has_b)):
            if seated_here and h.get("played_at") is not None:
                seated[hx].append(h)
            if hx in am and st:
                strong_names[hx].append(_norm(am[hx]))
    for hx in (ha, hb):
        seated[hx].sort(key=lambda h: h.get("played_at"))
    appear = seated
    ta = [h.get("played_at") for h in seated[ha]]
    tb = [h.get("played_at") for h in seated[hb]]
    disjoint = None
    if ta and tb:
        disjoint = (max(ta) < min(tb)) or (max(tb) < min(ta))
    # `same_nick` compara a leitura de FONTE FORTE (dominante) de cada lado, TOLERANTE a
    # OCR — ignora misreads FRACOS (ex.: "Vadzim Khazanau" fraco sobre um "OHmyBUDDHA"
    # forte, que mascarava um re-entry real). Caso OHmyBUDDHA (293643156).
    na = Counter(strong_names[ha]).most_common(1)[0][0] if strong_names[ha] else None
    nb = Counter(strong_names[hb]).most_common(1)[0][0] if strong_names[hb] else None
    same_nick = bool(na and nb and (na == nb or _ocr_variant(na, nb)))
    both_strong = bool(strong_names[ha] and strong_names[hb])
    weak_ok = bool(same_nick and both_strong and disjoint is True and not co_present)

    out = {"applies": True, "co_present": co_present, "disjoint_windows": disjoint,
           "same_nick": same_nick, "both_strong": both_strong,
           "likely_reentry": weak_ok, "level": ("likely" if weak_ok else None)}
    if not weak_ok or not ta or not tb:
        return out

    # early = quem tem a 1ª janela; a sua ÚLTIMA mão deve ser o bust
    if max(ta) < min(tb):
        early, elist, late, llist = ha, appear[ha], hb, appear[hb]
    else:
        early, elist, late, llist = hb, appear[hb], ha, appear[ha]
    last, first = elist[-1], llist[0]
    all_in, collected = _all_in_and_result(last.get("raw"), early)
    bust_lost = all_in and not collected
    start_stack = _tournament_start_stack(hands)
    fresh_stack = _stack_in(first.get("raw"), late)
    fresh = bool(start_stack and fresh_stack and
                 start_stack * _FRESH_STACK_LO <= fresh_stack <= start_stack * _FRESH_STACK_HI)
    try:
        gap_s = int((first.get("played_at") - last.get("played_at")).total_seconds())
    except Exception:
        gap_s = None
    gap_short = gap_s is not None and 0 <= gap_s <= _REBUY_GAP_MAX_S
    confirmed = bool(bust_lost and fresh and gap_short)
    out["level"] = "confirmed" if confirmed else "likely"
    out["bust"] = {"hash": early, "hand_id": last.get("hand_id"), "db_id": last.get("id"),
                   "played_at": _iso(last.get("played_at")), "all_in": all_in, "lost": bust_lost}
    out["rebuy"] = {"hash": late, "hand_id": first.get("hand_id"), "db_id": first.get("id"),
                    "played_at": _iso(first.get("played_at")), "stack": fresh_stack,
                    "start_stack": start_stack, "fresh": fresh}
    out["gap_seconds"] = gap_s
    return out


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
    corrections_total = 0
    for h in tagged:
        vill = hand_hashes(h)
        if not vill:
            continue
        own = _anon_map(_pn(h))          # hashes já com nome nesta mão
        hand_weak = not _is_strong(h)    # só corrige misreads em mãos FRACAS
        fills, ver_fills, corrected = {}, {}, {}
        for v in vill:
            cur = own.get(v)
            mapped = clean_map.get(v)
            if mapped is None:
                if cur is None:
                    blanks.add(v)
                continue
            if cur is None:
                fills[v] = mapped["name"]     # preenche branco
                if mapped["verified"]:
                    ver_fills[v] = True
            elif mapped["verified"] and hand_weak and _norm(cur) != _norm(mapped["name"]):
                # CORRECÇÃO: um nome VERIFICADO (decisão do Rui: re-entrada/escolher/fundir)
                # vence um misread FRACO existente diferente — a leitura errada NÃO fica
                # agarrada à mão a contaminar. (Mão FORTE ou mapa não-verificado → intocado:
                # o upgrade fraco→position_v3 continua deferido.)
                fills[v] = mapped["name"]
                ver_fills[v] = True
                corrected[v] = cur
                corrections_total += 1
            # else: já tem o nome certo / mapa forte-não-verificado / mão forte → não toca
        # "resolvida" = todos os vilões com nome (próprio OU preenchido)
        if all((v in own) or (v in fills) for v in vill):
            resolved += 1
        if fills:
            changes.append({
                "hand_id": h.get("hand_id"), "db_id": h.get("id"),
                "fills": fills, "verified_fills": ver_fills, "corrected": corrected,
            })
    return {
        "changes": changes,
        "blank_hashes": blanks,
        "stats": {
            "tagged_hands": len(tagged),
            "hands_with_fills": len(changes),
            "hands_resolved_after": resolved,
            "fills_total": sum(len(c["fills"]) for c in changes),
            "corrections_total": corrections_total,
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


def _clean_stale_villains(conn, db_id: int) -> int:
    """Apaga viloes STALE de uma mao: linhas em `hand_villains` cujo `player_name` JA NAO
    e um `real_name` do apa (ex.: o misread 'Vadzim Khazanau' depois de corrigido para
    'OHmyBUDDHA') — a leitura errada nao fica agarrada a mao a contaminar os Viloes. So
    remove nomes ausentes do apa (os viloes validos ficam intactos → sem duplo-incremento
    de `villain_notes`)."""
    with conn.cursor() as cur:
        cur.execute("SELECT all_players_actions apa FROM hands WHERE id=%s", (db_id,))
        row = cur.fetchone()
        apa = _as_dict(row["apa"]) if row else {}
        valid = [n for n in {(v.get("real_name") or "") for k, v in apa.items()
                             if k != "_meta" and isinstance(v, dict)} if n]
        cur.execute("DELETE FROM hand_villains WHERE hand_db_id=%s AND NOT (player_name = ANY(%s))",
                    (db_id, valid or [""]))
        return cur.rowcount


def apply_propagation(hands: list, clean_map: dict, *, conn=None, dry_run: bool = True) -> dict:
    """Aplica o plano as maos tagadas. dry_run=True devolve so o plano. Escreve
    idempotentemente, re-avalia viloes nas maos alteradas e LIMPA viloes stale (misreads
    corrigidos)."""
    plan = propagation_plan(hands, clean_map)
    if dry_run:
        return {"dry_run": True, **plan["stats"], "changes": plan["changes"]}
    own = conn is None
    if own:
        from app.db import get_conn
        conn = get_conn()
    written_hands = []
    stale_removed = 0
    try:
        for ch in plan["changes"]:
            if _write_fills(conn, ch["db_id"], ch["fills"], ch["verified_fills"]):
                written_hands.append(ch["db_id"])
        conn.commit()
        from app.services.villain_rules import apply_villain_rules
        for db_id in written_hands:
            try:
                apply_villain_rules(db_id, conn=conn)
                stale_removed += _clean_stale_villains(conn, db_id)
            except Exception:
                logger.exception("apply_villain_rules falhou hand %s", db_id)
        conn.commit()
    finally:
        if own:
            conn.close()
    return {"dry_run": False, "hands_written": len(written_hands),
            "stale_villains_removed": stale_removed, **plan["stats"]}


# ── review da quarentena (decisoes persistidas, respeitadas por re-runs) ──────

def _load_tournament_hands(conn, tn: str) -> list:
    with conn.cursor() as cur:
        cur.execute("""SELECT id, hand_id, site, raw, player_names, hm3_tags, discord_tags,
                              played_at
                       FROM hands WHERE site='GGPoker' AND tournament_number=%s
                       AND played_at >= '2026-01-01'""", (tn,))
        return [dict(r) for r in cur.fetchall()]


def _quar_key(q: dict) -> str:
    return q["hash"] if q["kind"] in ("same_hash", "strong_weak_mismatch") else q["name"]


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
            if q["kind"] in ("same_hash", "strong_weak_mismatch"):
                # confirma o nome no hash (VERIFICADO) → propaga + scruba as fracas divergentes
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
