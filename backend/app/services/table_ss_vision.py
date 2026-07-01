"""Extracção de contexto a partir de SS de MESA de torneio via Claude Sonnet 4.6.

pt38 Fase A — espelha services/lobby_vision.py, mas a fonte é uma SS da MESA
(capturada via Intuitive Tables), não do lobby. Alvo:
`#HRC-MTT-STACKS-PAGE-SKIPPED-ON-NULL-PLAYERS-LEFT` — dar ao watcher um
`players_left` fidedigno e alinhado à mão.

Prompt validado em pt38 (Winamax 10/10; GGPoker campos críticos OK). Difere do
lobby: lê o painel de info da mesa + identifica o Hero (seat inferior-centro
com cartas visíveis) e a sua posição relativa ao botão.

Schema esperado da resposta Vision (JSON puro, sem markdown):
    {
      "site": "GGPoker" | "PokerStars" | "Winamax" | "WPN" | null,
      "tournament_name": "ODYSSEY #013" | null,
      "tournament_buy_in": "€50" | null,
      "blinds_level": {"small_blind": int|null, "big_blind": int|null, "ante": int|null},
      "players_left": int | null,        # jogadores AINDA VIVOS no torneio
      "total_entries": int | null,       # total de inscritos
      "itm_places": int | null,          # lugares pagos
      "average_stack_bb": float | null,
      "hero_stack_bb": float | null,
      "hero_position": "UTG".."BB" | null,
      "hero_nick": str | null
    }

`captured_at` NÃO vem da Vision (não vê o filename) — é derivado em
`derive_captured_at()` a partir do nome do ficheiro (YYYYMMDDHHMMSS, TZ local).
"""
from __future__ import annotations

import base64
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger("table_ss_vision")

_MODEL = "claude-sonnet-4-6"

# Prompt validado em pt38 (ver _local_only/test_table_ss/test_vision_table_ss.py).
# Pede SÓ campos visuais; captured_at é derivado do filename em Python.
_TABLE_PROMPT = (
    "This is a screenshot of a LIVE poker TOURNAMENT TABLE (not a lobby). "
    "Identify the poker site by client design, then read the tournament info "
    "panel and the table.\n\n"
    "Reply with ONLY a JSON object matching this EXACT schema (no markdown, no "
    "preamble, no comments, no trailing text):\n"
    "{\n"
    '  "site": "GGPoker" | "PokerStars" | "Winamax" | "WPN" | null,\n'
    '  "tournament_name": "<exact name incl. number if shown, e.g. ODYSSEY #013>" | null,\n'
    '  "tournament_buy_in": "<as shown incl. currency, e.g. €50>" | null,\n'
    '  "blinds_level": {"small_blind": <int> | null, "big_blind": <int> | null, "ante": <int> | null},\n'
    '  "hero_rank": <int hero current rank/standing among players alive> | null,\n'
    '  "players_left": <int players STILL ALIVE in the tournament right now> | null,\n'
    '  "total_entries": <int total players that ENTERED, only if shown separately> | null,\n'
    '  "itm_places": <int number of paid places / places paid> | null,\n'
    '  "average_stack_bb": <float average stack in BIG BLINDS> | null,\n'
    '  "hero_stack_bb": <float hero stack in BIG BLINDS> | null,\n'
    '  "hero_position": "UTG" | "UTG1" | "MP" | "HJ" | "CO" | "BTN" | "SB" | "BB" | null,\n'
    '  "hero_nick": "<hero screen name>" | null,\n'
    '  "seats": [ {"nick": "<exact screen name under the avatar>", '
    '"stack_bb": <float stack in BIG BLINDS> | "ALLIN" | null, '
    '"bounty_usd": <float DOLLAR $ in the GOLD CROWN badge above the avatar> | null, '
    '"is_hero": <true for the bottom-center hero seat, else false>, '
    '"is_button": <true for the seat with the dealer BUTTON (D chip), else false>} ]\n'
    "}\n\n"
    "RULES:\n"
    "- HERO is the seat at the BOTTOM-CENTER of the table (the auto-centered hero "
    "position). Identify it by POSITION ONLY — the hero is ALWAYS at bottom-center. DO "
    "NOT rely on hole cards: if the hero FOLDED the cards are gone but the seat is STILL "
    "the bottom-center one. hero_nick is that seat's screen name.\n"
    "- is_button = the seat that has the dealer BUTTON (the 'D' dealer chip); exactly one.\n"
    "- The seats array MUST be in CLOCKWISE order STARTING FROM THE HERO (hero is the "
    "first element, then clockwise around the table) — used to align seats to the HH.\n"
    "- seats: return EVERY seated player at the table (one object per occupied "
    "seat, including the hero). nick = the exact screen name shown under that "
    "seat's avatar (preserve case and punctuation). stack_bb = that seat's stack "
    "in BIG BLINDS (convert from chips by dividing by big_blind if shown in "
    "chips; use the literal 'ALLIN' string if the seat shows All-In; null if "
    "unreadable).\n"
    "  * bounty_usd = the DOLLAR amount ($) in the GOLD/YELLOW CROWN badge above the "
    "avatar (the KO/PKO bounty). A MONEY value: $50, $75, $215. In a PKO it is NEVER "
    "tiny — at least about $50 (half the bounty buy-in), often much more. null if no "
    "crown.\n"
    "  * There is ALSO an ORANGE/RED FLAME badge near the avatar showing a PERCENT (%) "
    "— the player's VPIP statistic (e.g. 16%, 27%, 43%). IGNORE the flame — it is NOT "
    "the bounty. NEVER put the flame percent into bounty_usd. A small number like 16, "
    "20, 27, 43 is the FLAME percent, NOT the crown bounty; only the gold crown DOLLAR "
    "($) goes in bounty_usd.\n"
    "  is_hero = true only for the bottom-center "
    "hero seat. Do NOT include empty seats. Read each nick carefully — they feed "
    "an exact name match.\n"
    "- hero_position is the HERO seat relative to the dealer BUTTON (the 'D' "
    "chip). The seat with the button = BTN; the next clockwise = SB, then BB, "
    "then UTG, etc. Read carefully which seat the button is on.\n"
    "- TOURNAMENT INFO PANEL — read the rank/players line VERY CAREFULLY. The "
    "format differs by site and the slash numbers are NOT 'left/entrants':\n"
    "  * Winamax (top-right panel): 'Rank: <hero_rank> / <players_left> "
    "(<itm_places>)'. The number BEFORE the '/' is the HERO's current rank; the "
    "number AFTER the '/' is PLAYERS LEFT (still alive); the number in "
    "PARENTHESES is itm_places (paid spots).\n"
    "  * GGPoker: 'My Rank: <hero_rank> / <players_left>' (NO itm number in "
    "this panel). Before the '/' = hero rank; after the '/' = players left.\n"
    "- players_left = ALWAYS the count of players STILL ALIVE = the number "
    "AFTER the '/'. It is NEVER the hero rank (before the '/') and NEVER the "
    "parentheses number.\n"
    "- hero_rank = the number BEFORE the '/' (hero's current standing). It is "
    "always <= players_left.\n"
    "- total_entries = the TOTAL number that entered, ONLY if a separate "
    "explicit entrants counter is visible (e.g. '124 entrants', "
    "'Entries: 1059'). The rank/players slash line is NOT total_entries. If no "
    "explicit entrants counter is shown, set total_entries = null. Do NOT "
    "derive it from the slash numbers.\n"
    "- itm_places = number of paid positions. On Winamax it is the parentheses "
    "number on the rank line; elsewhere 'X paid' / 'ITM: X'. Null if absent.\n"
    "- average_stack_bb / hero_stack_bb: report in BIG BLINDS. If the client "
    "shows stacks in CHIPS, convert to BB by dividing by big_blind. If shown in "
    "BB already, use as-is. Keep one decimal.\n"
    "- blinds_level: read the current level blinds + ante as integer chips "
    "(e.g. 100/200 (25) -> small_blind 100, big_blind 200, ante 25).\n"
    "- Use null for any field you cannot read with confidence. DO NOT invent "
    "values not visible in the screenshot.\n"
    "- Output ONLY the JSON object."
)


# ── Vision call ──────────────────────────────────────────────────────────────

def extract_table_ss_json(
    image_bytes: bytes, mime_type: str = "image/png",
    err_out: Optional[dict] = None,
) -> Optional[str]:
    """Chama Claude Sonnet 4.6 com a SS da mesa. Devolve raw JSON text ou None
    em caso de falha API. Sonnet 4.6 não aceita prefill — apanha o 1º {...} via
    regex (resiliente a markdown wrap / prosa). Idêntico ao lobby_vision.

    pt73 — observabilidade: se `err_out` (dict) for dado, escreve nele
    `err_out['error']` com a causa REAL quando devolve None (ex.: erro da
    Anthropic 'credit balance too low', SDK ausente, ou resposta sem JSON). O
    caller propaga isso para `reason_detail` em vez do genérico 'devolveu None'.
    Mantém o tipo de retorno (Optional[str]) — os mocks dos testes ignoram o
    arg extra."""
    try:
        from anthropic import Anthropic  # lazy: evita import-time se SDK ausente
    except ImportError:
        logger.error("anthropic SDK não instalado")
        if err_out is not None:
            err_out["error"] = "anthropic SDK não instalado"
        return None

    try:
        client = Anthropic()
        b64 = base64.b64encode(image_bytes).decode("ascii")
        response = client.messages.create(
            model=_MODEL,
            max_tokens=2048,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": mime_type,
                                "data": b64,
                            },
                        },
                        {"type": "text", "text": _TABLE_PROMPT},
                    ],
                },
            ],
        )
        text = (response.content[0].text or "").strip()
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            return m.group(0)
        if err_out is not None:
            err_out["error"] = "Vision respondeu sem JSON parseable"
        return None
    except Exception as e:
        msg = f"{type(e).__name__}: {e}"
        logger.error(f"table_ss_vision API error: {msg}")
        if err_out is not None:
            err_out["error"] = f"Vision API: {msg[:300]}"
        return None


# ── Parse + validation ───────────────────────────────────────────────────────

def _coerce_pos_int(value: Any) -> Optional[int]:
    """int > 0 ou None. Aceita int e str de dígitos; bool não é int aqui."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str) and value.strip().isdigit():
        n = int(value.strip())
        return n if n > 0 else None
    return None


def _coerce_stack_bb(value: Any) -> Any:
    """Stack do banco: float > 0, a sentinela 'ALLIN' (string), ou None."""
    if isinstance(value, str) and value.strip().upper() in ("ALLIN", "ALL-IN", "ALL IN"):
        return "ALLIN"
    f = _coerce_float(value)
    return f if (f is not None and f > 0) else None


def _coerce_seats(value: Any) -> list[dict]:
    """Valida a lista `seats` da Vision. Cada banco vira
    {nick:str, stack_bb:float|'ALLIN'|None, bounty_usd:float|None, is_hero:bool}.
    Descarta entradas sem nick. Lista vazia se ausente/inválida."""
    if not isinstance(value, list):
        return []
    out: list[dict] = []
    for s in value:
        if not isinstance(s, dict):
            continue
        nick = (s.get("nick") or "").strip()
        if not nick:
            continue
        out.append({
            "nick": nick,
            "stack_bb": _coerce_stack_bb(s.get("stack_bb")),
            "bounty_usd": _coerce_float(s.get("bounty_usd")),
            "is_hero": bool(s.get("is_hero")),
            "is_button": bool(s.get("is_button")),   # pt96: 2ª âncora (fixa a direcção)
        })
    return out


def _coerce_float(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except (ValueError, TypeError):
            return None
    return None


# ── #TABLE-SS-VISION-SITE-MISCLASS — corrigir a site lida quando o nome a contradiz ──

# `#NNN` no FIM do nome = nº de mesa Winamax (`Table: 'NAME(num)#seat'`); nenhuma
# outra sala o usa. O `#NNN` de prefixo/meio (ex.: série "W SERIES #220 - …") é
# legítimo — a regex só apanha o FIM, por isso não o toca.
_TRAILING_TABLE_NUM_RE = re.compile(r"#\s*\d+\s*$")


def _sites_for_tournament_name(name: str) -> set:
    """Salas (de `hands` 2026) cujo `tournament_name` bate `name` por token-subset
    (com `clean_tournament_name`). Read-only. Usado pela Regra B de `_correct_site`."""
    from app.db import query
    from app.services.tournament_resolver import name_tokens_subset, clean_tournament_name
    nc = clean_tournament_name(name)
    rows = query(
        "SELECT DISTINCT site, tournament_name FROM hands "
        "WHERE tournament_name IS NOT NULL AND tournament_name <> '' "
        "AND played_at >= '2026-01-01'"
    )
    out: set = set()
    for r in rows:
        tc = clean_tournament_name(r["tournament_name"])
        if name_tokens_subset(nc, tc) or name_tokens_subset(tc, nc):
            out.add(r["site"])
    return out


def _correct_site(name: Optional[str], read_site: Optional[str]) -> Optional[str]:
    """Corrige a site lida pela Vision quando o NOME a contradiz (determinístico,
    sem listas hardcoded). #TABLE-SS-VISION-SITE-MISCLASS.

    - **Regra A** (zero-risco): nome com `#NNN` trailing (nº de mesa Winamax) +
      site lida != Winamax → Winamax.
    - **Regra B** (cross-check BD, conservadora): se a sala lida NÃO tem torneio
      com este nome e existe EXACTAMENTE uma outra que tem → essa.
    - Senão mantém `read_site`. Loga INFO em cada correcção (rasto de auditoria).
    """
    if not name:
        return read_site
    # Regra A — string pura, 0 falsos positivos (nenhuma sala não-WN usa #NNN trailing).
    if read_site != "Winamax" and _TRAILING_TABLE_NUM_RE.search(name):
        logger.info("[table_ss_site_fix] %s -> Winamax | name=%r | rule=A (#NNN trailing)",
                    read_site, name)
        return "Winamax"
    # Regra B — cross-check BD. Fail-safe: erro de BD não corrige (mantém leitura).
    try:
        sites = _sites_for_tournament_name(name)
    except Exception as e:  # pragma: no cover - defensivo
        logger.warning("[table_ss_site_fix] cross-check BD falhou name=%r: %s", name, e)
        return read_site
    if sites and read_site not in sites and len(sites) == 1:
        new_site = next(iter(sites))
        logger.info("[table_ss_site_fix] %s -> %s | name=%r | rule=B (cross-check BD)",
                    read_site, new_site, name)
        return new_site
    return read_site


def parse_and_validate_table_ss_json(raw: Optional[str]) -> Optional[dict]:
    """Parse + sanity check do JSON Vision. None em qualquer falha.

    Mais leve que o lobby (não há prizes): exige dict + pelo menos um campo
    útil (`tournament_name`, `players_left` ou `site`). Coerce numérico dos
    campos críticos para o pipeline a jusante poder confiar nos tipos.
    """
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (ValueError, TypeError) as e:
        logger.warning(f"table_ss_vision JSON parse error: {e}")
        return None
    if not isinstance(data, dict):
        logger.warning(f"table_ss_vision JSON not dict: {type(data).__name__}")
        return None

    name = (data.get("tournament_name") or "").strip() or None
    players_left = _coerce_pos_int(data.get("players_left"))
    site = (data.get("site") or "").strip() or None

    if not (name or players_left or site):
        logger.warning("table_ss_vision JSON sem campos úteis")
        return None

    # Normaliza os campos no dict devolvido.
    data["tournament_name"] = name
    data["site"] = site
    data["hero_rank"] = _coerce_pos_int(data.get("hero_rank"))
    data["players_left"] = players_left
    data["total_entries"] = _coerce_pos_int(data.get("total_entries"))
    data["itm_places"] = _coerce_pos_int(data.get("itm_places"))
    data["average_stack_bb"] = _coerce_float(data.get("average_stack_bb"))
    data["hero_stack_bb"] = _coerce_float(data.get("hero_stack_bb"))
    data["seats"] = _coerce_seats(data.get("seats"))
    return data


# ── captured_at do filename ──────────────────────────────────────────────────

def derive_captured_at(
    filename: Optional[str], tz_name: str = "Europe/Lisbon"
) -> Optional[datetime]:
    """`YYYYMMDDHHMMSS` no nome do ficheiro -> datetime NAIVE em hora de LISBOA.

    Convenção pt51: o timestamp do filename é a hora local da máquina de captura
    (Lisboa) → guarda-se VERBATIM (naive), na MESMA referência que
    `hands.played_at` (também Lisboa naive). Sem conversão = match temporal
    directo, sem offset. (`tz_name` mantido por compatibilidade de assinatura;
    não é usado — a convenção é sempre Lisboa.)

    Devolve None se não houver grupo de 14 dígitos ou data inválida.
    """
    if not filename:
        return None
    m = re.search(r"(\d{14})", filename)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y%m%d%H%M%S")  # naive = Lisboa
    except ValueError:
        return None
