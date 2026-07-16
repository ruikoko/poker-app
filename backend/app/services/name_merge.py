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
