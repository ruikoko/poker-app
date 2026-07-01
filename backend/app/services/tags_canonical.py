"""Fonte ÚNICA de canonicalização de tags de estudo (GG + HM3/WN/PS/WPN).

Une, num só dicionário, as 4 redes que estavam dispersas:
  - `normalize_tag_key`  (routers/hands.py)  — case-insensitive + hífen→espaço
  - `IT_FOLDER_TAGS`     (tools/appimport)   — nome da subpasta do IT → tag
  - `hm3_tag_aliases`    (services/…)         — GTw→pos-nko, nota++→nota
  - `tag_family_key`     (routers/hands.py)   — nota ex→nota (SÓ agrupamento)

REGRA DURA: só ACRESCENTA reconhecimento, nunca remove. `canonicalize_tag`
devolve a forma canónica para QUALQUER forma reconhecida (mais formas que antes)
e **preserva inalterado** tudo o que não reconhece (as 51 tags HM3 adormecidas,
`nota ex`, tags custom, resíduos `Timetell`/`For Review`). Nunca deita fora.

As LISTAS DE DECISÃO (basket HRC, WPN gate, IRE `_has_ko_tag`, equity model)
**não** são tocadas: lêem sempre normalizado, e as canónicas normalizam para as
mesmas chaves de sempre → comportamento estritamente igual (ver
`backend/tests/test_tags_canonical.py`).

⚠️ `nota ex` NÃO é fundida em `nota` (é exemplar distinto p/ ML) — só o
`tag_family_key` (grouping visual, em hands.py) a agrupa com nota, e esse fica
como está.
"""
from __future__ import annotations

import re


def normalize_tag_key(tag: str | None) -> str:
    """Chave de unificação: minúsculas + hífen→espaço + espaços colapsados.
    (idêntica à de `routers/hands.py`; duplicada de propósito para este módulo
    ser um LEAF sem importar o router pesado — os dois têm de coincidir.)"""
    if not tag:
        return ""
    return re.sub(r"\s+", " ", str(tag).replace("-", " ").lower()).strip()


# ── Dicionário canónico: forma NORMALIZADA reconhecida → tag canónica ─────────
# Só é preciso listar diferenças SEMÂNTICAS (ordem de palavras, sinónimos de
# pasta, aliases); as variações de case/hífen já são cobertas por normalize.
CANONICAL_BY_NORM: dict[str, str] = {
    # ── spots base ──
    "icm": "icm",
    "icm pko": "icm-pko",
    "pos pko": "pos-pko",
    "pko pos": "pos-pko",          # pasta IT "PKO Pos" (ordem invertida)
    "pos nko": "pos-nko",
    "npko pos": "pos-nko",         # pasta IT antiga "NPKO Pos" (histórico)
    "nko pos": "pos-nko",          # 🆕 pasta IT nova "NKO Pos"
    "gtw": "pos-nko",              # alias HM3 (GTw descontinuada → pos-nko)
    "speed racer": "speed-racer",
    "speedracer": "speed-racer",   # pasta IT sem espaço
    # ── spots FT (fase = mesa final) ──
    "icm ft": "icm-ft",            # 🆕 pasta IT "ICM FT" (antes só via 1-clique)
    "icm pko ft": "icm-pko-ft",
    "pos pko ft": "pos-pko-ft",
    "pko pos ft": "pos-pko-ft",    # pasta IT "PKO Pos FT"
    "pos nko ft": "pos-nko-ft",    # 🆕 pasta IT nova "NKO Pos FT" (forma directa)
    "nko pos ft": "pos-nko-ft",    # 🆕 pasta IT nova "NKO Pos FT"
    "speed racer ft": "speed-racer-ft",  # 🆕 pasta IT "Speed Racer FT"
    "speedracer ft": "speed-racer-ft",
    # ── transversal ──
    "nota": "nota",
    "nota++": "nota",              # alias (nota++ → nota)
    # 'nota ex' (norm 'nota ex') NÃO entra: literal distinto (exemplar ML).
}


def canonicalize_tag(raw: str | None, *, only_known: bool = False) -> str | None:
    """Forma reconhecida → tag canónica. Preserva o que não reconhece.

    - `only_known=False` (default): forma não reconhecida → devolve o literal
      ORIGINAL inalterado (preserva 51 HM3 adormecidas, `nota ex`, custom,
      `Timetell`/`For Review`). É o modo dos pontos que já aceitam qualquer tag
      (import HM3, PATCH da mão, folder_tag).
    - `only_known=True`: forma não reconhecida → `None` (não inventa tag). É o
      modo do nome de PASTA do IT (pasta desconhecida = sem tag, como hoje).
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    canon = CANONICAL_BY_NORM.get(normalize_tag_key(s))
    if canon is not None:
        return canon
    return None if only_known else s


def canonicalize_tags(tags, *, only_known: bool = False) -> list[str]:
    """Canonicaliza uma lista, preservando ordem e removendo duplicados/None."""
    out: list[str] = []
    for t in (tags or []):
        c = canonicalize_tag(t, only_known=only_known)
        if c and c not in out:
            out.append(c)
    return out
