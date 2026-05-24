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
    '  "hero_nick": "<hero screen name>" | null\n'
    "}\n\n"
    "RULES:\n"
    "- HERO is the seat at the BOTTOM-CENTER of the table whose hole cards are "
    "face-up/visible. hero_nick is that seat's screen name.\n"
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
    image_bytes: bytes, mime_type: str = "image/png"
) -> Optional[str]:
    """Chama Claude Sonnet 4.6 com a SS da mesa. Devolve raw JSON text ou None
    em caso de falha API. Sonnet 4.6 não aceita prefill — apanha o 1º {...} via
    regex (resiliente a markdown wrap / prosa). Idêntico ao lobby_vision."""
    try:
        from anthropic import Anthropic  # lazy: evita import-time se SDK ausente
    except ImportError:
        logger.error("anthropic SDK não instalado")
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
        return m.group(0) if m else None
    except Exception as e:
        logger.error(f"table_ss_vision API error: {type(e).__name__}: {e}")
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
    return data


# ── captured_at do filename ──────────────────────────────────────────────────

def derive_captured_at(
    filename: Optional[str], tz_name: str = "Europe/Lisbon"
) -> Optional[datetime]:
    """`YYYYMMDDHHMMSS` no nome do ficheiro -> datetime tz-aware em UTC.

    O timestamp do filename é hora LOCAL da máquina de captura (default
    Europe/Lisbon, com DST WET/WEST). Converte-se para UTC para comparar com
    `hands.played_at` (TIMESTAMPTZ UTC). Ver #START-TIME-TIMEZONE-INCONSISTENCY.

    Devolve None se não houver grupo de 14 dígitos ou data inválida.
    """
    if not filename:
        return None
    m = re.search(r"(\d{14})", filename)
    if not m:
        return None
    try:
        naive = datetime.strptime(m.group(1), "%Y%m%d%H%M%S")
    except ValueError:
        return None
    try:
        from zoneinfo import ZoneInfo
        local = naive.replace(tzinfo=ZoneInfo(tz_name))
    except Exception:
        logger.warning(
            "zoneinfo %r indisponível (tzdata em falta?); a tratar captured_at "
            "como UTC — match temporal pode falhar por offset", tz_name,
        )
        local = naive.replace(tzinfo=timezone.utc)
    return local.astimezone(timezone.utc)
