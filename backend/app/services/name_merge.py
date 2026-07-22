"""LEI DO CRUZAMENTO — nome mais completo (ordem do Rui, 15-16 Jul).

Quando Gold e SS de mesa casam o mesmo jogador, o **nome completo** ganha sempre;
se AMBOS truncados, fica o **mais longo**. Selos (`verified_by_user`) intocáveis.
Puro (sem BD) — reusado pelo dry-run/aplicação do histórico E pelo merge do reimport.
"""
from __future__ import annotations

import re

_TRUNC = re.compile(r"(\.\.+|…)\s*$")      # truncado = 2+ pontos ou reticências no fim
_ANYDOT = re.compile(r"[.…]\s*$")          # completo = SEM qualquer ponto/reticência no fim


def is_truncated(n) -> bool:
    return bool(n) and bool(_TRUNC.search(n))


def is_complete(n) -> bool:
    return bool(n) and not _ANYDOT.search(n)


def _prefix(n) -> str:
    return _TRUNC.sub("", n or "").strip()


def _norm(s) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def best_completion(stored, pool):
    """O melhor nome para o MESMO jogador dado `stored` (truncado) e a `pool` de nomes
    lidos na mão. Completo ganha sempre; se todos truncados, o mais longo. Devolve o
    nome novo, ou None se não há melhoria OU é ambíguo (2 completos distintos)."""
    if not is_truncated(stored):
        return None
    sp = _norm(_prefix(stored))
    exts = [n for n in pool if n and _norm(_prefix(n)).startswith(sp)
            and len(_prefix(n)) >= len(_prefix(stored))]
    if not exts:
        return None
    completes = [n for n in exts if is_complete(n)]
    if completes:
        if len({_norm(n) for n in completes}) > 1:
            return None                     # ambíguo → não mexe
        best = max(completes, key=len)
    else:
        maxlen = max(len(_prefix(n)) for n in exts)
        top = [n for n in exts if len(_prefix(n)) == maxlen]
        if len({_norm(_prefix(n)) for n in top}) > 1:
            return None                     # ambíguo → não mexe
        best = max(top, key=len)
    if _norm(best) == _norm(stored):
        return None
    if is_complete(best) and is_truncated(stored):
        return best
    if len(_prefix(best)) > len(_prefix(stored)):
        return best
    return None


# ── Régua da ELIMINAÇÃO (irmã da best_completion — lei do Rui, 22 Jul) ────────
# Numa mesa, se TODOS os nomes casam entre a HH e a captura menos UM de cada
# lado, esse par é a mesma pessoa (não há outro para ser) — mesmo com o coto
# mal soletrado pelo OCR (onde o prefixo falha). Fica o nome MAIS COMPLETO.

# Lixo de UI que a Vision às vezes devolve como "nick" — NÃO conta como nome (G2).
GARBAGE_NICKS = {"post blind(s)", "post", "fold", "call", "check", "raise",
                 "all-in", "allin", "sitting out", "sit out", "sitout", ""}


def clean_capture_nicks(vision_json):
    """Nicks LEGÍVEIS de uma captura (lixo de UI fora)."""
    out = []
    for s in (vision_json or {}).get("seats") or []:
        n = (s.get("nick") or "").strip()
        if n and n.lower() not in GARBAGE_NICKS:
            out.append(n)
    return out


def _same_player_name(a, b) -> bool:
    """O MESMO nome nas duas fontes: igual (norm) ou truncatura-prefixo de um lado."""
    if _norm(a) == _norm(b):
        return True
    if is_truncated(a) and _prefix(a) and _norm(b).startswith(_norm(_prefix(a))):
        return True
    if is_truncated(b) and _prefix(b) and _norm(a).startswith(_norm(_prefix(b))):
        return True
    return False


def elimination_completion(named, hh_seats, vision_json):
    """Aplica a régua da eliminação a UMA captura. `named` = {chave_apa: real_name}
    (inclui "Hero"); `hh_seats` = sentados na HH. Devolve {"hash","from","to"} — o
    único par sobrante, com o nome completo da captura — ou None (recusa honesta).

    AS 3 GUARDAS (não negociáveis, ditadas pelo Rui):
      G1 — HERO FORA PRIMEIRO, dos dois lados. Se o Hero não se encontra na
           captura (a Vision falha muitas vezes UM jogador, e muitas vezes é o
           Hero) → NÃO elimina nada nesta captura.
      G2 — CONTAGENS RECONCILIADAS: nicks legíveis == sentados na HH.
      G3 — UM-E-UM: só casa quando sobra exatamente 1 de cada lado.
    Só completa truncados (o sobrante da HH truncado + o da captura completo e
    mais longo); vilões sem nome na HH nunca casam por aqui (o sobrante da
    captura passa a 2 → G3 recusa sozinha)."""
    nicks = clean_capture_nicks(vision_json)
    if not hh_seats or not nicks or len(nicks) != hh_seats:      # G2
        return None
    hero = named.get("Hero")
    if not hero:
        return None
    seats = (vision_json or {}).get("seats") or []
    hero_nick = next(((s.get("nick") or "").strip() for s in seats
                      if s.get("is_hero") and (s.get("nick") or "").strip()
                      and (s.get("nick") or "").strip().lower() not in GARBAGE_NICKS),
                     None)
    if hero_nick is None or hero_nick not in nicks:
        hero_nick = next((n for n in nicks if _same_player_name(hero, n)), None)
    if hero_nick is None:                                        # G1 — recusa total
        return None
    pool = list(nicks)
    pool.remove(hero_nick)
    rest = {k: n for k, n in named.items() if k != "Hero" and n}
    for k, nm in list(rest.items()):
        m = next((c for c in pool if _same_player_name(nm, c)), None)
        if m is not None:
            pool.remove(m)
            rest.pop(k)
    if len(rest) != 1 or len(pool) != 1:                         # G3
        return None
    (hsh, nm), cand = next(iter(rest.items())), pool[0]
    if not is_truncated(nm) or not is_complete(cand):
        return None
    if len(cand) <= len(_prefix(nm)):
        return None                     # não é mais completo → nada a ganhar
    return {"hash": hsh, "from": nm, "to": cand}


def names_pool(apa, players_list, gold_raw_json, ss_vision_jsons):
    """Todos os nomes lidos numa mão: apa + players_list + Gold (players_list + raw_vision)
    + TODAS as SS. `ss_vision_jsons` = lista de vision_json (uma por captura)."""
    pool = set()
    for k, v in (apa or {}).items():
        if k != "_meta" and isinstance(v, dict) and v.get("real_name"):
            pool.add(v["real_name"])
    for p in (players_list or []):
        if p.get("name"):
            pool.add(p["name"])
    if gold_raw_json:
        for p in (gold_raw_json.get("players_list") or []):
            if p.get("name"):
                pool.add(p["name"])
        rv = gold_raw_json.get("raw_vision")
        if isinstance(rv, str):
            for ln in rv.splitlines():
                if ln.startswith("PLAYER:"):
                    nm = ln.split("PLAYER:", 1)[1].split("|")[0].strip()
                    if nm and nm != "NONE":
                        pool.add(nm)
    for vj in (ss_vision_jsons or []):
        for s in (vj.get("seats") or []):
            if s.get("nick"):
                pool.add(s["nick"])
    return pool
