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

import logging
import re
from typing import Optional

logger = logging.getLogger("eliminated_bounty")

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


def _apply_seat_bounty(seat: dict, val, review, source) -> None:
    """CIRÚRGICO — só toca os 3 campos do bounty; nome/stack/posição/cartas intactos."""
    seat["bounty_value_usd"] = val                 # None (NULL) ou o verde (instantâneo)
    if review:
        seat[BOUNTY_REVIEW_KEY] = review
    else:
        seat.pop(BOUNTY_REVIEW_KEY, None)
    if source:
        seat[BOUNTY_SOURCE_KEY] = source
    else:
        seat.pop(BOUNTY_SOURCE_KEY, None)


def is_tagged(hand: Optional[dict]) -> bool:
    """SÓ-TAGADAS (APA §B.6): mão de estudo = hm3_tags OU discord_tags não-vazias.
    Espelho de name_propagation._is_tagged (fonte única do conceito)."""
    if not hand:
        return False
    return bool(hand.get("hm3_tags")) or bool(hand.get("discord_tags"))


def scrub_eliminated_bounties(apa: Optional[dict], pn: Optional[dict],
                             raw: Optional[str], vision_data: Optional[dict] = None,
                             *, tagged: bool = True) -> int:
    """FUNIL ÚNICO da cura verde-KO. Chamado 1× em cada caminho AUTOMÁTICO que escreve
    bounty por-seat (enrich gold/position_v3, orphan-enrich, table-ss, backfills gold-carry
    e capture, reread). Aplica a guarda aos seats HH-bustados em AMBOS apa e pn.players_list.
    Devolve nº de seats-nome tocados (audit). Muta apa/pn in-place.

    5 garantias:
    (0) SÓ-TAGADAS: `tagged=False` → NÃO scruba (return 0). O scope do core (APA §B.6) fica
        BAKED-IN no funil; o call-site passa `tagged=is_tagged(hand)`.
    (1) MUST independente do verde: sem `vision_data`/verde (backfills só-apa) → o bustado
        fica NULL + 'por rever' (a anulação vem SÓ do raw/HH).
    (2) raw obrigatório: sem `raw` NÃO se pode computar bust em segurança → NÃO scruba e
        LOGA warning (nunca deixa passar cru em silêncio; o call-site tem de garantir raw).
    (3) CIRÚRGICO: só bounty_value_usd/bounty_review/bounty_source.
    (4) apa↔pn consistente: busted/greens computados UMA vez, aplicados igual aos dois.
    """
    if not tagged:
        return 0
    if not isinstance(apa, dict):
        return 0
    if not raw:
        # Guarantee 2: um call-site sem raw é um buraco — sinaliza, não scruba às cegas.
        logger.warning("scrub_eliminated_bounties: raw ausente — bust não computável; "
                       "call-site tem de fornecer o raw (HH). Skip seguro (sem scrub).")
        return 0
    busted = busted_real_names(raw, apa)            # HH-autoritativo; {} se não há bust
    if not busted:
        return 0
    greens = parse_green_kos(vision_data)           # best-effort; [] se ausente/sem prompt
    touched = 0
    for key, entry in apa.items():                  # 1) apa (chave=hash/nick/Hero)
        if key == "_meta" or not isinstance(entry, dict):
            continue
        name = entry.get("real_name") or key
        if name not in busted:
            continue
        val, review, source = resolve_seat_bounty(
            name, entry.get("bounty_value_usd"), busted_names=busted, green_kos=greens)
        _apply_seat_bounty(entry, val, review, source)
        touched += 1
    for p in (pn or {}).get("players_list") or []:  # 2) pn.players_list (nome='name')
        if not isinstance(p, dict) or p.get("name") not in busted:
            continue
        val, review, source = resolve_seat_bounty(
            p.get("name"), p.get("bounty_value_usd"), busted_names=busted, green_kos=greens)
        _apply_seat_bounty(p, val, review, source)  # mesmo resultado → apa↔pn coerentes
    return touched


def scrub_and_persist(hand_db_id: int, vision_data: Optional[dict] = None,
                      incoming_folder_tag=None) -> int:
    """Wrapper DB-aware do funil, chamado nos PONTOS DE FINALIZAÇÃO (pós-persist de cada
    caminho automático). Lê apa/pn/raw/tags FRESCOS da mão, aplica o scrub (só-tagadas) e
    reescreve SE mudou. Idempotente → a ordem A/B não importa; correr 2× = mesmo resultado.

    - `tagged = is_tagged(mão) OU incoming_folder_tag` → cobre o 'tagada-depois' (a captura
      que traz a folder-tag torna a mão tagada NESTE momento → o scrub corre já).
    - `vision_data` (com green_kos) só é passado onde há Vision FRESCA (reread, enrich gold)
      → green-fill; senão MUST-only (bustado → NULL + 'por rever').
    - FAIL-SAFE do raw (garantia 2): sem raw NÃO scruba e NÃO escreve — nunca grava uma
      coroa que não consegue verificar (o scrub já devolve 0; aqui não há UPDATE).
    """
    import json as _json
    from app.db import query, get_conn
    rows = query("SELECT id, raw, all_players_actions AS apa, player_names AS pn, "
                 "hm3_tags, discord_tags FROM hands WHERE id = %s", (hand_db_id,))
    if not rows:
        return 0
    r = rows[0]
    tagged = is_tagged(r) or bool(incoming_folder_tag)
    if not tagged:
        return 0                                   # SÓ-TAGADAS: skip total (não escreve)
    if not r.get("raw"):
        return 0                                   # fail-safe: sem raw não se verifica bust
    apa = r["apa"] if isinstance(r["apa"], dict) else _json.loads(r["apa"] or "{}")
    pn = r["pn"] if isinstance(r["pn"], dict) else _json.loads(r["pn"] or "{}")
    n = scrub_eliminated_bounties(apa, pn, r["raw"], vision_data, tagged=True)
    if n:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE hands SET all_players_actions = %s, player_names = %s "
                            "WHERE id = %s",
                            (_json.dumps(apa), _json.dumps(pn), hand_db_id))
            conn.commit()
        finally:
            conn.close()
    return n
