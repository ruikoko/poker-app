"""Selecção partilhada das mãos elegíveis para a queue HRC.

FONTE ÚNICA do predicado de elegibilidade (Andar 1 SQL + defaults do basket),
consumida por:
  - `routers/queue.py:export_queue`  → gera o zip para o watcher.
  - `routers/hrc.py:list_eligible`   → lista JSON para o painel HRC (read-only).

Antes da pt37 o SQL e os defaults viviam inline em `export_queue`; o painel
teria de os duplicar, criando drift (exactamente a dor que motivou o painel).
Aqui há uma só definição.

ANDAR 1 = SQL de selecção (sites + basket de tags normalizado + study_state +
janela played_at). ANDAR 2 = filtros per-mão de `build_queue_zip` (tem payout,
raw convertível, seats parseáveis). `eligible_hands` aplica os dois + enriquece
com `aggressor_source` (via `classify_aggressor_source`, partilhado com
`build_queue_zip`), `position_hero` e `stack_hero_bb`.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.db import query
from app.routers.hands import normalize_tag_key
from app.services.queue_export import (
    convert_gg_hh_to_pokerstars_compatible,
    derive_seats_in_preflop_order,
    derive_aggressor_real_action,
    derive_first_vpip_position,
    classify_aggressor_source,
    _extract_blinds_from_header,
    BOUNTY_FORMATS,
    MYSTERY_FORMATS,
    TS_GATED_FORMATS,
)
from app.services.hrc_node_offset import strategy_table_positions
from app.services.hrc_script_gen import _parse_seat_stacks

logger = logging.getLogger("hrc_queue")

# Basket por defeito do export. Cada string passa por `normalize_tag_key` (#B17)
# antes de bater contra `hm3_tags`/`discord_tags`: case-insensitive + hyphen→space,
# daí "icm-pko" ≡ "ICM PKO" ≡ "ICM-pko". Adicionar case-variants é redundante.
DEFAULT_TAGS = [
    "icm-pko",
    "PKO SS",
    "sqz-pko",
    "ICM",
    "ICM FT",
    "ICM PKO FT",
    # Família Speed Racer (GG hyper PKO). O basket faz match EXACTO normalizado
    # (NORM(t)=ANY), ao contrário do IRE que usa substring (ire.py
    # SPEED_RACER_NEEDLE). Por isso as duas variantes reais das discord_tags do
    # Rui — `speed-racer` (→ "speed racer") e `speed-racer-ft` (→ "speed racer
    # ft") — têm de estar AMBAS aqui; não são case-variants redundantes (diferem
    # em nº de tokens). NÃO colapsar numa só.
    "speed-racer",
    "speed-racer-ft",
]
DEFAULT_STUDY_STATES = ["new"]
ALLOWED_SITES = ["GGPoker", "PokerStars", "Winamax", "WPN"]

# #WPN-ICM-TAG-GATE — a WPN é gateada pela TAG do Rui (a SUA classificação), NÃO
# por formato. A HH WPN não traz marcador de bounty (sem sinal estrutural), por
# isso um gate por formato (nome) tinha leak (#WPN-KO-NAME-ONLY-GATE, descartado).
# Em vez disso, a WPN só entra na fila se a mão tiver uma tag de estudo ICM — é o
# Rui que classifica. Normalizadas como o basket (normalize_tag_key).
WPN_ALLOWED_TAGS = ["ICM", "ICM FT"]

# SQL aplica a mesma normalização de `normalize_tag_key` a cada elemento de
# hm3_tags/discord_tags antes de comparar com o basket (idiom de /api/hands).
_NORM_SQL = "lower(regexp_replace(replace(t, '-', ' '), '\\s+', ' ', 'g'))"

_DEALT_RE = re.compile(r"Dealt to (.+?) \[")


def split_csv(value: Optional[str], default: list[str]) -> list[str]:
    if value is None:
        return default
    parts = [p.strip() for p in value.split(",") if p.strip()]
    return parts or default


def normalize_tags_basket(tags: list[str]) -> list[str]:
    """Aplica `normalize_tag_key` ao basket + dedup. Vazios caem fora."""
    seen: list[str] = []
    for t in tags:
        nk = normalize_tag_key(t)
        if nk and nk not in seen:
            seen.append(nk)
    return seen


def resolve_filters(
    tags: Optional[str] = None,
    study_state: Optional[str] = None,
    played_after: Optional[str] = None,
    played_before: Optional[str] = None,
) -> dict:
    """Resolve query params → valores efectivos (com os defaults do export).

    Levanta `ValueError` se played_after/played_before não forem ISO date —
    o caller (router) traduz em HTTP 400.
    """
    raw_tags = split_csv(tags, DEFAULT_TAGS)
    tags_norm = normalize_tags_basket(raw_tags)
    states_list = split_csv(study_state, DEFAULT_STUDY_STATES)
    now = datetime.now(timezone.utc)
    after_str = played_after or (now - timedelta(days=30)).date().isoformat()
    before_str = played_before or now.date().isoformat()
    after_dt = datetime.fromisoformat(after_str).replace(tzinfo=timezone.utc)
    before_dt = (
        datetime.fromisoformat(before_str).replace(tzinfo=timezone.utc)
        + timedelta(days=1)
    )
    return {
        "raw_tags": raw_tags,
        "tags_norm": tags_norm,
        "states_list": states_list,
        "after_str": after_str,
        "before_str": before_str,
        "after_dt": after_dt,
        "before_dt": before_dt,
    }


def select_andar1_rows(
    tags_norm: list[str],
    states_list: list[str],
    after_dt: datetime,
    before_dt: datetime,
    *,
    played_desc: bool = False,
) -> list[dict]:
    """ANDAR 1 — SQL canónica de selecção. Fonte única (anti-drift).

    `played_desc=False` (default) preserva a ordem ASC histórica de
    `export_queue`; o painel passa `True` para listar do mais recente.
    """
    order = "DESC" if played_desc else "ASC"
    # #WPN-ICM-TAG-GATE: tags ICM da WPN normalizadas como o basket.
    wpn_tags_norm = normalize_tags_basket(WPN_ALLOWED_TAGS)
    return query(
        f"""
        SELECT id, hand_id, site, tournament_number, tournament_name,
               tournament_format, raw, player_names, played_at,
               position, study_state, hm3_tags, discord_tags,
               context_table_ss_id, hero_cards
          FROM hands
         WHERE played_at >= '2026-01-01'
           AND site = ANY(%s)
           AND played_at >= %s
           AND played_at < %s
           AND study_state = ANY(%s)
           AND (
                 EXISTS (SELECT 1 FROM unnest(COALESCE(hm3_tags, '{{}}'::text[]))
                                AS t WHERE {_NORM_SQL} = ANY(%s))
              OR EXISTS (SELECT 1 FROM unnest(COALESCE(discord_tags, '{{}}'::text[]))
                                AS t WHERE {_NORM_SQL} = ANY(%s))
               )
           -- pt41 #HERO-BOUNTY-FROM-TS-DERIVATION: Mystery KO fora do /hrc
           -- (HRC não modela) + GG bounty-gated (PKO/SuperKO/KO) exige TS com
           -- buy_in_bounty. PS passa sempre (bounty na HH crua).
           -- pt42d #WN-BOUNTY-NULL-IN-HRC-PIPELINE v2: Winamax arquitectura
           -- final (revertida pt42c v1 — Seat lines conversion não era
           -- necessária):
           --   * HH WN passthrough (HRC lê formato `(<X>€ bounty)` nativo).
           --   * payouts.json no zip = layout HRC-aceite `{{name, folders,
           --     structures}}` com `_patch_winamax_payouts_bountytype` a
           --     aplicar bountyType="PKO" + progressiveFactor=0.5 + name
           --     "<Name>  #<tn>" (build_queue_zip).
           --   * Hints (equity_model, max_players, script_path,
           --     aggressor_real_action) em meta.json (não payouts.json —
           --     HRC rejeita campos extra → ICM puro).
           -- Sem gate adicional aqui — WN PKO passa pelo Andar 1 normalmente.
           AND lower(COALESCE(tournament_format, '')) <> ALL(%s::text[])
           AND (
                 site <> 'GGPoker'
              OR lower(COALESCE(tournament_format, '')) <> ALL(%s::text[])
              OR EXISTS (SELECT 1 FROM tournament_summaries ts
                          WHERE ts.site = hands.site
                            AND ts.tournament_number = hands.tournament_number
                            AND ts.buy_in_bounty IS NOT NULL)
               )
           -- #WPN-ICM-TAG-GATE: a WPN é gateada pela TAG do Rui (a SUA
           -- classificação), NÃO por formato — sem sinal estrutural na HH WPN, o
           -- gate por formato (nome) tinha leak (#WPN-KO-NAME-ONLY-GATE,
           -- descartado). A WPN só entra se a mão tiver uma tag de estudo ICM
           -- (WPN_ALLOWED_TAGS, normalizada como o basket). Qualquer outra (incl.
           -- PKO) fica de fora. Mystery continua excluído acima (todas as salas);
           -- o gate GG continua GG-only. GG/PS/WN imunes (a cláusula só morde
           -- quando site='WPN').
           AND (
                 site <> 'WPN'
              OR EXISTS (SELECT 1 FROM unnest(COALESCE(hm3_tags, '{{}}'::text[]))
                                AS t WHERE {_NORM_SQL} = ANY(%s))
              OR EXISTS (SELECT 1 FROM unnest(COALESCE(discord_tags, '{{}}'::text[]))
                                AS t WHERE {_NORM_SQL} = ANY(%s))
               )
           -- #SERVER-FILTER-HRC-STATUS (pt43): excluir mãos já calculadas
           -- (hrc_jobs.status='done'). Reduz bandwidth do GET /api/queue/hrc
           -- (adapter) e tira-as do painel /hrc — ambos partilham esta fonte.
           AND NOT EXISTS (
                 SELECT 1 FROM hrc_jobs j
                  WHERE j.hand_db_id = hands.id
                    AND j.status = 'done'
               )
           -- Manual-only (pt92): mãos postas DE LADO (set-aside — tipicamente as
           -- grandes/veneno) saem da elegibilidade e da lista, para não serem
           -- selecionadas/servidas por engano. Marcador durável: hrc_jobs com
           -- meta_json.set_aside=true (escrito por POST /hrc/set-aside).
           AND NOT EXISTS (
                 SELECT 1 FROM hrc_jobs j
                  WHERE j.hand_db_id = hands.id
                    AND (j.meta_json ->> 'set_aside') = 'true'
               )
         ORDER BY played_at {order}
        """,
        (ALLOWED_SITES, after_dt, before_dt, states_list, tags_norm, tags_norm,
         list(MYSTERY_FORMATS),      # exclusão Mystery (todas as salas)
         list(TS_GATED_FORMATS),     # gate KO GG (exige TS com buy_in_bounty)
         wpn_tags_norm, wpn_tags_norm),  # #WPN-ICM-TAG-GATE: WPN só com tag ICM (hm3+discord)
    )


def lookup_payouts(rows: list[dict]) -> dict:
    """Lookup {(site, tournament_number): payouts_json} para o set de mãos."""
    sites = list({r["site"] for r in rows if r.get("site")})
    tnums = list({r["tournament_number"] for r in rows if r.get("tournament_number")})
    if not (sites and tnums):
        return {}
    prows = query(
        """SELECT site, tournament_number, payouts_json
             FROM tournament_payouts
            WHERE site = ANY(%s) AND tournament_number = ANY(%s)""",
        (sites, tnums),
    )
    return {(r["site"], r["tournament_number"]): r["payouts_json"] for r in prows}


def lookup_bounties(rows: list[dict]) -> dict:
    """pt41 — lookup {(site, tn): {starting_bounty, ts_format}} para o set de mãos.
    Espelho de `lookup_payouts` (anti-drift). `starting_bounty` =
    `tournament_summaries.buy_in_bounty` (base por torneio, GG-only). None quando
    o TS não tem bounty (vanilla) ou não existe."""
    sites = list({r["site"] for r in rows if r.get("site")})
    tnums = list({r["tournament_number"] for r in rows if r.get("tournament_number")})
    if not (sites and tnums):
        return {}
    brows = query(
        """SELECT site, tournament_number, buy_in_bounty, tournament_format
             FROM tournament_summaries
            WHERE site = ANY(%s) AND tournament_number = ANY(%s)""",
        (sites, tnums),
    )
    return {
        (r["site"], r["tournament_number"]): {
            "starting_bounty": (
                float(r["buy_in_bounty"]) if r["buy_in_bounty"] is not None else None
            ),
            "ts_format": r["tournament_format"],
        }
        for r in brows
    }


def lookup_ts_meta(rows: list[dict]) -> dict:
    """Lookup {(site, tn): {total_players, tournament_speed}} para os filtros da
    UI (total de jogadores + velocidade). Query ÚNICA em lote ao
    `tournament_summaries` (espelho de `lookup_bounties`; separada para não
    tocar no contrato testado dessa). Defensivo: `{}` em falha/sem-chaves."""
    sites = list({r["site"] for r in rows if r.get("site")})
    tnums = list({r["tournament_number"] for r in rows if r.get("tournament_number")})
    if not (sites and tnums):
        return {}
    try:
        prows = query(
            """SELECT site, tournament_number, total_players, tournament_speed
                 FROM tournament_summaries
                WHERE site = ANY(%s) AND tournament_number = ANY(%s)""",
            (sites, tnums),
        )
    except Exception:
        logger.exception("lookup_ts_meta falhou")
        return {}
    return {
        (r["site"], r["tournament_number"]): {
            "total_players": r.get("total_players"),
            "tournament_speed": (
                (r.get("tournament_speed") or "").strip().lower() or None
            ),
        }
        for r in prows
    }


def _fresh_starting_stack(apa) -> Optional[float]:
    """#ICM-CHIPS-USE-TS-FINAL-FIELD-GG — salvaguarda da "mão fresca".

    Dado o `all_players_actions` (JSONB) da mão MAIS ANTIGA de um torneio,
    devolve o stack inicial (em fichas) SE a mão é mesmo a entrada do torneio:
      - `_meta.level == 1` (Nível 1); E
      - todos os jogadores têm o MESMO stack (1 só valor distinto — ninguém
        ainda ganhou/perdeu fichas); E
      - esse stack é REDONDO (sem parte fraccionária, ex. 10000); E
      - se o Hero está identificado, o seu stack bate com o comum.

    Qualquer falha → None (o caller não faz override; fica a estimativa do
    lobby). Nunca lança.
    """
    if isinstance(apa, str):
        try:
            apa = json.loads(apa)
        except (ValueError, TypeError):
            return None
    if not isinstance(apa, dict):
        return None
    meta = apa.get("_meta")
    if not isinstance(meta, dict) or meta.get("level") != 1:
        return None
    stacks: list[float] = []
    hero_stack: Optional[float] = None
    for k, v in apa.items():
        if k == "_meta" or not isinstance(v, dict):
            continue
        s = v.get("stack")
        if not isinstance(s, (int, float)) or isinstance(s, bool) or s <= 0:
            return None
        stacks.append(float(s))
        if v.get("is_hero"):
            hero_stack = float(s)
    if not stacks:
        return None
    if len({round(s, 6) for s in stacks}) != 1:
        return None
    common = stacks[0]
    if common != int(common):
        return None
    if hero_stack is not None and round(hero_stack, 6) != round(common, 6):
        return None
    return common


def lookup_icm_chips(rows: list[dict]) -> dict:
    """#ICM-CHIPS-USE-TS-FINAL-FIELD-GG — total de fichas do torneio para o ICM,
    derivado do campo FINAL do TS (não da foto parcial do lobby).

    O `chips` que o HRC usa para o ICM vem hoje da estimativa do lobby
    (`average_stack × players_left` lida no momento da SS); em registo tardio
    subconta. Aqui calcula-se o total verdadeiro:

        total_chips = TS.total_players × starting_stack

    com `starting_stack` lido da mão MAIS ANTIGA do torneio (`_fresh_starting_stack`,
    validada como Nível 1 / stacks iguais e redondos).

    Devolve `{(site, tn): {total_chips, total_players, starting_stack}}` APENAS
    para torneios em que: site == 'GGPoker', existe TS com `total_players > 0`,
    e a 1ª mão é fresca. Caso contrário a chave fica de fora → o override não se
    aplica (mantém-se a estimativa do lobby).

    GG-only por desenho: WN/PS/WPN nunca entram (o parser de TS é GG-only desde
    pt38; e os outros sites gravam a estimativa do lobby na mesma). Query em
    LOTE (espelho de `lookup_ts_meta`). Defensivo: `{}` em falha/sem-chaves.
    """
    tnums = list({
        r["tournament_number"] for r in rows
        if r.get("site") == "GGPoker" and r.get("tournament_number")
    })
    if not tnums:
        return {}
    try:
        ts_rows = query(
            """SELECT tournament_number, total_players
                 FROM tournament_summaries
                WHERE site = 'GGPoker' AND tournament_number = ANY(%s)
                  AND total_players IS NOT NULL AND total_players > 0""",
            (tnums,),
        )
    except Exception:
        logger.exception("lookup_icm_chips: TS query falhou")
        return {}
    players_by_tn = {r["tournament_number"]: int(r["total_players"]) for r in ts_rows}
    if not players_by_tn:
        return {}

    try:
        # Mão mais antiga (entrada) por torneio, em lote.
        hand_rows = query(
            """SELECT DISTINCT ON (tournament_number)
                      tournament_number, all_players_actions
                 FROM hands
                WHERE site = 'GGPoker' AND tournament_number = ANY(%s)
                  AND played_at >= '2026-01-01'
                ORDER BY tournament_number, played_at ASC""",
            (list(players_by_tn.keys()),),
        )
    except Exception:
        logger.exception("lookup_icm_chips: query da 1ª mão falhou")
        return {}

    out: dict = {}
    for r in hand_rows:
        tn = r["tournament_number"]
        total_players = players_by_tn.get(tn)
        if not total_players:
            continue
        starting_stack = _fresh_starting_stack(r.get("all_players_actions"))
        if not starting_stack:
            continue
        out[("GGPoker", tn)] = {
            "total_chips": float(total_players) * float(starting_stack),
            "total_players": total_players,
            "starting_stack": float(starting_stack),
        }
    return out


def lookup_players_left(rows: list[dict]) -> dict:
    """Resolve `players_left` por mão (id → (valor, fonte)) em LOTE — sem query
    por mão. Precedência espelha `queue_export._resolve_players_left`:
    `table_ss_processing_log` (per-mão, via `context_table_ss_id`) >
    `lobby_processing_log` (por torneio). Defensivo: tudo (None, None) em falha."""
    ctx_ids = list({
        r["context_table_ss_id"] for r in rows
        if isinstance(r.get("context_table_ss_id"), int)
    })
    tnums = list({r["tournament_number"] for r in rows if r.get("tournament_number")})
    ts_map: dict = {}
    lobby_map: dict = {}
    try:
        if ctx_ids:
            for pr in query(
                "SELECT id, players_left FROM table_ss_processing_log "
                "WHERE id = ANY(%s) AND players_left IS NOT NULL",
                (ctx_ids,),
            ):
                ts_map[pr["id"]] = pr["players_left"]
        if tnums:
            for pr in query(
                """SELECT DISTINCT ON (tournament_number)
                          tournament_number, players_left
                     FROM lobby_processing_log
                    WHERE tournament_number = ANY(%s)
                      AND result = 'success' AND players_left IS NOT NULL
                    ORDER BY tournament_number, posted_at DESC NULLS LAST""",
                (tnums,),
            ):
                lobby_map[pr["tournament_number"]] = pr["players_left"]
    except Exception:
        logger.exception("lookup_players_left falhou")
    out: dict = {}
    for r in rows:
        ctx = r.get("context_table_ss_id")
        tn = r.get("tournament_number")
        if isinstance(ctx, int) and ctx in ts_map:
            out[r["id"]] = (ts_map[ctx], "table_ss")
        elif tn and tn in lobby_map:
            out[r["id"]] = (lobby_map[tn], "lobby")
        else:
            out[r["id"]] = (None, None)
    return out


def pending_ts_hands(
    *,
    tags: Optional[str] = None,
    study_state: Optional[str] = None,
    played_after: Optional[str] = None,
    played_before: Optional[str] = None,
) -> list[dict]:
    """pt41 — mãos GG bounty-format ESCONDIDAS do /hrc por falta de TS-com-bounty.

    Espelha a janela/tags/study_state do Andar 1 mas devolve o complemento do
    gate: GG bounty-format SEM `tournament_summaries.buy_in_bounty`, agrupado por
    torneio. `reason`:
      - `needs_ts_import`     — PKO/SuperKO/KO → importar o TS resolve.
      - `mystery_unsupported` — Mystery KO → #MYSTERY-KO-DUAL-SUPPORT (sessão futura).
    Alimenta o banner D1 no painel /hrc. Read-only.
    """
    f = resolve_filters(tags, study_state, played_after, played_before)
    rows = query(
        f"""
        SELECT tournament_number AS tn,
               max(tournament_name) AS tournament_name,
               lower(COALESCE(tournament_format, '')) AS fmt,
               count(*) AS n_hands
          FROM hands
         WHERE played_at >= '2026-01-01'
           AND site = 'GGPoker'
           AND played_at >= %s
           AND played_at < %s
           AND study_state = ANY(%s)
           AND lower(COALESCE(tournament_format, '')) = ANY(%s::text[])
           AND (
                 EXISTS (SELECT 1 FROM unnest(COALESCE(hm3_tags, '{{}}'::text[]))
                                AS t WHERE {_NORM_SQL} = ANY(%s))
              OR EXISTS (SELECT 1 FROM unnest(COALESCE(discord_tags, '{{}}'::text[]))
                                AS t WHERE {_NORM_SQL} = ANY(%s))
               )
           AND NOT EXISTS (SELECT 1 FROM tournament_summaries ts
                            WHERE ts.site = hands.site
                              AND ts.tournament_number = hands.tournament_number
                              AND ts.buy_in_bounty IS NOT NULL)
         GROUP BY tournament_number, lower(COALESCE(tournament_format, ''))
         ORDER BY n_hands DESC
        """,
        (f["after_dt"], f["before_dt"], f["states_list"],
         list(BOUNTY_FORMATS), f["tags_norm"], f["tags_norm"]),
    )
    out: list[dict] = []
    for r in rows:
        fmt = r["fmt"]
        out.append({
            "tournament_number": r["tn"],
            "tournament_name": r["tournament_name"],
            "tournament_format": fmt,
            "n_hands": r["n_hands"],
            "reason": "mystery_unsupported" if fmt in MYSTERY_FORMATS else "needs_ts_import",
        })
    return out


def _hero_stack_bb(hh_text: str, bb: Optional[int]) -> Optional[float]:
    """Stack do Hero em BB: nick da linha `Dealt to <nick> [` + seat stacks / BB."""
    if not hh_text or not bb:
        return None
    m = _DEALT_RE.search(hh_text)
    if not m:
        return None
    chips = _parse_seat_stacks(hh_text).get(m.group(1).strip())
    if chips is None:
        return None
    try:
        return round(float(chips) / float(bb), 1)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def eligible_hands(
    *,
    tags: Optional[str] = None,
    study_state: Optional[str] = None,
    played_after: Optional[str] = None,
    played_before: Optional[str] = None,
    include_no_payout: bool = False,
) -> dict:
    """Mãos elegíveis para a queue HRC, espelhando os gates de /api/queue/hrc.

    ANDAR 1 (SQL partilhada) + ANDAR 2 (payout/raw/seats de `build_queue_zip`)
    + enriquecimento (aggressor_source / position_hero / stack_hero_bb).
    Devolve dict serializável: count, filters, scenario_counts, format_counts,
    hands[]. Read-only — não escreve nada.
    """
    f = resolve_filters(tags, study_state, played_after, played_before)
    rows = [dict(r) for r in select_andar1_rows(
        f["tags_norm"], f["states_list"], f["after_dt"], f["before_dt"],
        played_desc=True,
    )]
    payouts = lookup_payouts(rows)
    bounties = lookup_bounties(rows)
    ts_meta = lookup_ts_meta(rows)            # total_players + speed (lote)
    players_left_map = lookup_players_left(rows)  # id → (valor, fonte) (lote)

    hands: list[dict] = []
    scen = {"real": 0, "fallback_root": 0, "fallback_unusable_position": 0}
    fmt: dict[str, int] = {}
    for h in rows:
        # ANDAR 2 — gate 1: raw convertível
        hh = convert_gg_hh_to_pokerstars_compatible(h)
        if not hh:
            continue
        # ANDAR 2 — gate 2: payout (a não ser include_no_payout)
        blob = payouts.get((h["site"], h["tournament_number"]))
        if blob is None and not include_no_payout:
            continue
        # ANDAR 2 — gate 3: seats parseáveis
        seats_list = derive_seats_in_preflop_order(hh)
        seats = len(seats_list)
        positions = strategy_table_positions(seats)
        if not positions:
            continue
        # Enriquecimento (mesmo cálculo do build_queue_zip)
        blinds = _extract_blinds_from_header(hh)
        sb, bb = blinds if blinds else (None, None)
        real = derive_aggressor_real_action(hh, sb, bb) if bb is not None else None
        src = classify_aggressor_source(real, positions)
        scen[src] = scen.get(src, 0) + 1
        fkey = h.get("tournament_format") or "?"
        fmt[fkey] = fmt.get(fkey, 0) + 1
        meta = ts_meta.get((h["site"], h["tournament_number"])) or {}
        pl_val, pl_src = players_left_map.get(h["id"], (None, None))
        hands.append({
            "id": h["id"],
            "hand_id": h["hand_id"],
            "site": h["site"],
            "tournament_number": h["tournament_number"],
            "tournament_name": h["tournament_name"],
            "tournament_format": h["tournament_format"],
            "played_at": h["played_at"].isoformat() if h["played_at"] else None,
            "hm3_tags": h.get("hm3_tags") or [],
            "discord_tags": h.get("discord_tags") or [],
            "position_hero": h.get("position"),
            "first_vpip_position": derive_first_vpip_position(hh, seats_list),
            "seats_occupied": seats,
            "stack_hero_bb": _hero_stack_bb(hh, bb),
            "aggressor_source": src,
            "has_payout": blob is not None,
            "starting_bounty": (
                bounties.get((h["site"], h["tournament_number"])) or {}
            ).get("starting_bounty"),
            # Filtros de torneio (UI). None = "sem dado" (nunca esconder a mão).
            "total_players": meta.get("total_players"),
            "tournament_speed": meta.get("tournament_speed"),
            "players_left": pl_val,
            "players_left_source": pl_src,
        })

    return {
        "count": len(hands),
        "filters": {
            "tags": f["raw_tags"],
            "study_state": f["states_list"],
            "played_after": f["after_str"],
            "played_before": f["before_str"],
            "include_no_payout": include_no_payout,
        },
        "scenario_counts": scen,
        "format_counts": fmt,
        "hands": hands,
    }
