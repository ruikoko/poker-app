"""
backend/app/services/villain_rules.py

Função canónica única para aplicar A∨C∨D a uma hand. Substitui:
  - mtt._create_villains_for_hand
  - mtt._create_ggpoker_villain_notes_for_hand
  - hm3._create_hand_villains_hm3
  - screenshot._maybe_create_rule_c_villain_for_hand

Regras de elegibilidade (REGRAS_NEGOCIO.md §3.3):
  A — hm3_tags contém tag a começar por 'nota'           → category='nota'
  C — 'nota' em discord_tags + match_method real          → category='nota'
  D — villain_nick em FRIEND_HEROES (Karluz/flightrisk)   → category='friend'

Pré-condição (linha 74-75 de _classify_villain_categories): has_cards
OR has_vpip. Excepção #B19: hands com hm3_tags ~ 'nota%' aceitam non-hero
postflop-only (BB-check-preflop a agir postflop sem VPIP).

Side-effects:
  - INSERT em hand_villains (1 row por (player, category) aplicável).
  - UPSERT em villain_notes (incrementa hands_seen, agnóstico de category;
    1ª chamada por (hand_db_id, nick) apenas — guard Q6 evita duplo-
    incremento em repeat-calls).

Idempotente: ON CONFLICT no partial UNIQUE
(hand_db_id, player_name, category) WHERE hand_db_id IS NOT NULL.
Chamadas repetidas são no-op para hand_villains; villain_notes guard
detecta repeat via SELECT prévio por (hand_db_id, nick).
"""
from __future__ import annotations
import json
import logging

from psycopg2.extras import RealDictCursor

from app.db import get_conn
from app.hero_names import HERO_NAMES
from app.services.hand_service import _classify_villain_categories, _is_anon_hash

logger = logging.getLogger(__name__)


# ── API pública ──────────────────────────────────────────────────────────────

def apply_villain_rules(hand_db_id: int, *, conn=None) -> dict:
    """
    Aplica A∨C∨D a uma hand. Idempotente.

    Args:
      hand_db_id: id em `hands`.
      conn: psycopg2 connection opcional. Se None, abre própria e committa.
            Se fornecida, NÃO committa nem fecha — caller é dono da transacção.

    Returns:
      {
        "n_villains_created": int,         # rows efectivamente inseridas
        "n_villain_notes_upserts": int,    # candidates classificados (1ª vez)
        "skipped_reason": str | None,      # se early-return
      }
    """
    own_conn = conn is None
    if own_conn:
        conn = get_conn()

    try:
        hand = _read_hand(conn, hand_db_id)
        if not hand:
            return _result(0, 0, skipped_reason="hand_not_found")

        # Invariante: GG anonimizada (sem match_method real) NÃO cria villains.
        # Sites não-GG têm nicks reais directamente do parser, sem precisar
        # de match_method. Per REGRAS_NEGOCIO §6 + §3.3 invariante.
        if hand["site"] == "GGPoker":
            mm = hand.get("match_method") or ""
            if not mm or mm.startswith("discord_placeholder_"):
                return _result(0, 0, skipped_reason="gg_anon_no_match")

        candidates = _build_candidates(hand)
        if not candidates:
            return _result(0, 0, skipped_reason="no_candidates")

        # Filtro "vilão principal" (spec pt12+): manter apenas candidates
        # que chegaram à street máxima da hand. Sem tie-break — se múltiplos
        # chegaram à mesma street, todos passam. Edge case (apa placeholder
        # sem actions): max_street=0, todos passam.
        candidates = _filter_to_furthest_street(
            candidates, hand.get("all_players_actions") or {}
        )

        n_villains, n_notes = _persist(conn, hand_db_id, hand, candidates)

        if own_conn:
            conn.commit()

        logger.info(
            "apply_villain_rules: hand=%d site=%s candidates=%d "
            "n_villains=%d n_notes=%d",
            hand_db_id, hand["site"], len(candidates), n_villains, n_notes,
        )
        return _result(n_villains, n_notes)

    except Exception as exc:
        if own_conn:
            conn.rollback()
        logger.error("apply_villain_rules failed hand=%d: %s", hand_db_id, exc)
        raise
    finally:
        if own_conn:
            conn.close()


# ── Helpers internos ─────────────────────────────────────────────────────────

def _result(n_villains: int, n_notes: int, *, skipped_reason: str | None = None) -> dict:
    return {
        "n_villains_created": n_villains,
        "n_villain_notes_upserts": n_notes,
        "skipped_reason": skipped_reason,
    }


def _read_hand(conn, hand_db_id: int) -> dict | None:
    """SELECT atómico do estado completo da hand."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """SELECT id, site, raw, all_players_actions, has_showdown,
                      hm3_tags, discord_tags,
                      player_names->>'match_method' AS match_method,
                      player_names AS pn
               FROM hands WHERE id = %s""",
            (hand_db_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def _build_candidates(hand: dict) -> list[dict]:
    """
    Constrói lista de non-hero candidates a partir de all_players_actions.

    apa é a fonte canónica — populada pelos parsers (HM3 / GG / etc.) e
    enriched para GG após match SS↔HH. Para cada non-hero:
      - has_cards: showdown cards presentes
      - has_vpip: acção preflop voluntária (call/raise/bet/all-in)
      - has_postflop: actuou em flop/turn/river

    Eligibility default: has_cards OR has_vpip.
    Excepção #B19 (REGRAS_NEGOCIO §3.3): se hand tem hm3_tags ~ 'nota%',
    aceita postflop-only (cobre BB que checked preflop e agiu postflop).

    Vision metadata (stack/bounty_pct/country) puxada de player_names JSON
    quando disponível. Fallback a apa[name].stack para non-Vision paths.
    """
    apa = hand.get("all_players_actions") or {}
    if not isinstance(apa, dict):
        return []

    pn = hand.get("pn") or {}
    if isinstance(pn, str):
        try:
            pn = json.loads(pn)
        except (ValueError, TypeError):
            pn = {}
    vision_by_name = {
        (vp.get("name") or "").lower(): vp
        for vp in (pn.get("players_list") or [])
        if isinstance(vp, dict)
    }

    # #B19 (REGRAS_NEGOCIO.md §3.3): tag 'nota' (HM3 ou canal Discord)
    # sinaliza intenção explícita do Rui de criar villain. Alargar
    # candidates a postflop-only nesses casos.
    has_nota_intent = (
        any((t or "").lower().startswith("nota") for t in (hand.get("hm3_tags") or []))
        or 'nota' in (hand.get("discord_tags") or [])
    )

    candidates: list[dict] = []
    for name, pdata in apa.items():
        if name == "_meta" or not isinstance(pdata, dict):
            continue
        if pdata.get("is_hero"):
            continue
        if not name or name in ("Hero", "Unknown"):
            continue
        if name.lower() in HERO_NAMES:
            continue
        if _is_anon_hash(name):
            continue

        actions = pdata.get("actions") or {}
        if not isinstance(actions, dict):
            actions = {}
        cards = pdata.get("cards") or []

        has_cards = bool(cards)
        has_vpip = _has_vpip_preflop(actions.get("preflop"))
        has_postflop = any(actions.get(s) for s in ("flop", "turn", "river"))

        eligible = has_cards or has_vpip
        if not eligible and has_nota_intent and has_postflop:
            eligible = True
        if not eligible:
            continue

        vinfo = vision_by_name.get(name.lower(), {})
        candidates.append({
            "nick": name,
            "position": pdata.get("position"),
            "stack": vinfo.get("stack") or pdata.get("stack"),
            "bounty_pct": vinfo.get("bounty_pct"),
            "country": vinfo.get("country"),
            "has_cards": has_cards,
            "has_vpip": has_vpip,
            "vpip_action": (
                ", ".join(cards) if cards
                else _vpip_label(actions.get("preflop"))
            ),
        })

    return candidates


def _has_vpip_preflop(preflop_actions) -> bool:
    """
    VPIP estrito = pelo menos uma acção voluntária preflop
    (call/raise/bet/all-in). Aceita string única ou lista de strings
    (parser GG bulk produz lista; parser MTT produz string).
    """
    if preflop_actions is None:
        return False
    text = (
        " ".join(str(x) for x in preflop_actions)
        if isinstance(preflop_actions, list)
        else str(preflop_actions)
    ).lower().strip()
    if not text:
        return False
    return any(kw in text for kw in ("calls", "raises", "bets", "all-in"))


def _vpip_label(preflop_actions) -> str | None:
    """Etiqueta sucinta da acção preflop para gravar em hand_villains.vpip_action."""
    if preflop_actions is None:
        return None
    text = (
        " ".join(str(x) for x in preflop_actions)
        if isinstance(preflop_actions, list)
        else str(preflop_actions)
    ).lower()
    for kw in ("all-in", "raises", "calls", "bets"):
        if kw in text:
            return kw.rstrip("s")  # raise/call/bet/all-in
    return None


def _street_reached(actions, cards) -> int:
    """
    Hierarquia: 0=sem_dados, 1=preflop, 2=flop, 3=turn, 4=river, 5=showdown.

    Showdown = chegou ao river COM acção real E cards reveladas.
    Cards isoladas (mucked GG side-info) não promovem a showdown.
    """
    actions = actions if isinstance(actions, dict) else {}
    has_cards = bool(cards)
    has_river = bool(actions.get("river"))
    has_turn  = bool(actions.get("turn"))
    has_flop  = bool(actions.get("flop"))
    has_pf    = bool(actions.get("preflop"))

    if has_river and has_cards:
        return 5
    if has_river: return 4
    if has_turn:  return 3
    if has_flop:  return 2
    if has_pf:    return 1
    return 0


def _filter_to_furthest_street(candidates: list[dict], apa: dict) -> list[dict]:
    """
    Filtra candidates a quem chegou à street máxima da hand.

    Spec (pt12+):
      - Hierarquia: showdown > river > turn > flop > preflop > sem_dados.
      - Sem tie-break: empate na street máxima → todos retornados.
      - Edge case (max_street=0, ninguém tem dados): todos retornados.
    """
    if not candidates:
        return []

    annotated = []
    for c in candidates:
        pdata = apa.get(c["nick"]) if isinstance(apa, dict) else None
        if not isinstance(pdata, dict):
            pdata = {}
        s = _street_reached(pdata.get("actions"), pdata.get("cards"))
        annotated.append((s, c))

    max_street = max(s for s, _ in annotated)
    if max_street == 0:
        # Edge case: apa placeholder / sem dados de actions — todos passam.
        return [c for _, c in annotated]
    return [c for s, c in annotated if s == max_street]


def _persist(conn, hand_db_id: int, hand: dict, candidates: list[dict]) -> tuple[int, int]:
    """
    Para cada candidate: classifica via A∨C∨D + INSERT hand_villains
    (idempotente via ON CONFLICT) + UPSERT villain_notes (1ª chamada apenas).

    Guard de idempotência villain_notes (Q6): antes do UPSERT, verifica se
    já existe row em hand_villains para (hand_db_id, nick) com qualquer
    category. Se sim, é repeat-call — skip villain_notes para evitar
    duplo-incremento de hands_seen. Se não, UPSERT normal.

    Retorna (n_hand_villains_inserted, n_villain_notes_upserts).
    """
    hand_meta = {
        "hm3_tags": hand.get("hm3_tags") or [],
        "discord_tags": hand.get("discord_tags") or [],
        "has_showdown": hand.get("has_showdown"),
        "match_method": hand.get("match_method"),
    }
    site = hand.get("site") or "GGPoker"

    n_villains = 0
    n_notes = 0
    with conn.cursor() as cur:
        for c in candidates:
            cats = _classify_villain_categories(
                hand_meta, c["nick"], c["has_cards"], c["has_vpip"]
            )
            if not cats:
                continue

            # Q6 guard: 1ª vez para (hand_db_id, nick)? Se já existe
            # row com qualquer category, é repeat call — skip villain_notes
            # UPSERT (evita duplo-incremento de hands_seen).
            cur.execute(
                "SELECT 1 FROM hand_villains "
                "WHERE hand_db_id = %s AND player_name = %s LIMIT 1",
                (hand_db_id, c["nick"]),
            )
            is_first_time = cur.fetchone() is None

            for cat in cats:
                cur.execute(
                    """INSERT INTO hand_villains
                           (mtt_hand_id, hand_db_id, player_name, position, stack,
                            bounty_pct, country, vpip_action, category)
                       VALUES (NULL, %s, %s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (hand_db_id, player_name, category)
                       WHERE hand_db_id IS NOT NULL DO NOTHING""",
                    (hand_db_id, c["nick"], c["position"], c["stack"],
                     c["bounty_pct"], c["country"], c["vpip_action"], cat),
                )
                if cur.rowcount > 0:
                    n_villains += 1

            if is_first_time:
                cur.execute(
                    """INSERT INTO villain_notes (site, nick, hands_seen, updated_at)
                       VALUES (%s, %s, 1, NOW())
                       ON CONFLICT (site, nick) DO UPDATE SET
                           hands_seen = villain_notes.hands_seen + 1,
                           updated_at = NOW()""",
                    (site, c["nick"]),
                )
                n_notes += 1

    return n_villains, n_notes
