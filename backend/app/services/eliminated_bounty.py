"""Cura do core — coroa de jogadores ELIMINADOS (verde-KO). GG only, PKO/KO.

DEFEITO (armadilha verde-KO, ver CLAUDE.md; caso arieloo/mirroring GG-6114944767 pt95;
caso GG-6140169166 Hero $170.63←KamikazzE97): quando um jogador é eliminado, a coroa
PRÓPRIA dele some e METADE do bounty aparece a VERDE na coroa de quem o elimina. A leitura
por-seat da Vision atribui ao seat eliminado a coroa do seat VIZINHO → bounty errado (veneno).

INVARIANTE (não pode quebrar): um seat ELIMINADO (sinal da HH — all-in e perdeu) NUNCA
recebe a coroa por-seat da Vision. A anulação depende SÓ da HH — nunca do prompt ler o verde.

CHOKEPOINT: `resolve_seat_bounty()` — TODOS os caminhos AUTOMÁTICOS que escrevem bounty
por-seat no ingest/backfill passam por aqui (enrich gold/position_v3, table-ss, gold-carry).
Endpoints MANUAIS (/set-bounties, /set-anon-map) ficam de fora (aí é o Rui a mandar).

MUST     — eliminado sem verde derivável → bounty NULL + review='eliminated_no_green'.
SHOULD   — 1 eliminado + 1 verde → bounty = verde (instantâneo; convenção #KO-CROWN-INSTANT-FIX,
           o resto do código faz ÷instant_fraction=×2 → total). Guarda o INSTANTÂNEO (o verde).
FALLBACK — multiway (vários eliminados ou vários verdes, sem ligar 1:1) → NULL + 'eliminated_ambiguous'.
"""
from __future__ import annotations

import re
from typing import Optional

# Marca de review no seat (apa/pn) quando o bounty do eliminado fica por preencher.
BOUNTY_REVIEW_KEY = "bounty_review"
REVIEW_NO_GREEN = "eliminated_no_green"       # bustou, sem verde legível → por rever
REVIEW_AMBIGUOUS = "eliminated_ambiguous"     # multiway → não se liga verde↔eliminado

# Proveniência do bounty no seat (apa/pn). O CRIVO VERDADEIRO da cura: um seat
# HH-bustado com coroa >0 SÓ é aceitável se a proveniência for 'green_ko' (derivado
# do verde pelo chokepoint). Coroa >0 num bustado SEM esta marca = origem-Vision =
# contaminação (o "forte" da heurística é só um proxy visível deste crivo).
BOUNTY_SOURCE_KEY = "bounty_source"
SOURCE_GREEN_KO = "green_ko"                  # derivado do verde-KO na coroa do eliminador

# ── Sinal de ELIMINADO (autoritativo — HH) ───────────────────────────────────
# Linha de acção: "<key>: bets 47,944 and is all-in" (key = hash GG ou "Hero").
# Restrito a UMA linha ([^:\n], [^\n]*) senão [^:]+ engole newlines (bug apanhado 9 Jul).
_ALLIN_RE = re.compile(r"^([^:\n]+):[^\n]*\band is all-in\b", re.M)
# Colecta do pote: "<key> collected 180,816 from pot" (sem ':').
_COLLECT_RE = re.compile(r"^([^\n:]+?) collected [\d,]+", re.M)


def busted_keys_from_hh(raw: Optional[str]) -> set:
    """Chaves-da-HH (hash GG / 'Hero') ELIMINADAS nesta mão: foram all-in E NÃO
    coletaram nenhum pote (perderam o all-in). Autoritativo (HH), independente da Vision."""
    if not raw:
        return set()
    allin = {m.group(1).strip() for m in _ALLIN_RE.finditer(raw)}
    collected = {m.group(1).strip() for m in _COLLECT_RE.finditer(raw)}
    return {k for k in allin if k not in collected}


def busted_real_names(raw: Optional[str], apa: Optional[dict]) -> set:
    """Nomes REAIS dos seats eliminados (mapeia as chaves-HH via apa: real_name || chave)."""
    keys = busted_keys_from_hh(raw)
    if not keys:
        return set()
    key2name = {k: (v.get("real_name") or k)
                for k, v in (apa or {}).items()
                if k != "_meta" and isinstance(v, dict)}
    return {key2name.get(k, k) for k in keys}


# ── Verde-KO (Vision — SHOULD; nunca gate do invariante) ──────────────────────
# Linha do prompt novo: "GREEN_KO: <winner_name> | <value>" (o valor verde = instantâneo
# do bounty do eliminado, na coroa de quem o eliminou).
def parse_green_kos(vision_data: Optional[dict]) -> list:
    """Lista de {winner, value} dos verdes-KO que a Vision emitiu. [] se ausente."""
    out = []
    for g in (vision_data or {}).get("green_kos") or []:
        try:
            val = float(g.get("value"))
        except (TypeError, ValueError):
            continue
        if val > 0:
            out.append({"winner": (g.get("winner") or "").strip(), "value": val})
    return out


def resolve_seat_bounty(
    name: str,
    vision_crown,
    *,
    busted_names: set,
    green_kos: Optional[list] = None,
) -> tuple:
    """CHOKEPOINT do bounty por-seat. Devolve (value, review_reason, source).

    - Seat NÃO eliminado → coroa da Vision tal-e-qual (value, None, None). O caminho
      normal fica INALTERADO (convenção #KO-CROWN-INSTANT-FIX: value = instantâneo).
    - Seat ELIMINADO (HH) → NUNCA a coroa por-seat da Vision. Se houver exatamente 1
      eliminado E 1 verde → (verde, None, 'green_ko') [proveniência marcada = crivo].
      Senão (0 verdes, >1 verde, >1 eliminado) → (None, review, None).

    `source` é a marca de proveniência (SOURCE_GREEN_KO só quando derivado do verde);
    o caller grava-a em `bounty_source` do seat. Um bustado com coroa >0 sem esta marca
    é contaminação de origem-Vision (crivo verdadeiro = 0 pós-cura).
    """
    if name not in busted_names:
        return vision_crown, None, None
    greens = green_kos or []
    # Caso limpo (SHOULD): 1 eliminado nesta mão + 1 verde → liga-se sem ambiguidade.
    if len(busted_names) == 1 and len(greens) == 1:
        return greens[0]["value"], None, SOURCE_GREEN_KO
    if not greens:
        return None, REVIEW_NO_GREEN, None
    return None, REVIEW_AMBIGUOUS, None
