"""HRC payouts extraction from Discord lobby screenshots via Claude Sonnet 4.6.

FASE A COMMIT 2 — funcoes puras + 1 chamada externa (Anthropic Messages API).
Bot Discord chama estas funcoes no path do canal #lobbys (FASE A COMMIT 3).

Schema esperado da resposta Vision (JSON puro, sem markdown):
    {
      "site": "GGPoker" | "PokerStars" | "Winamax" | null,
      "tournament_name": "...",
      "start_time_iso": "2026-05-05T18:30:00Z" | null,
      "starting_stack": int | null,
      "entrants": int | null,
      "buy_in": float | null,
      "prizes": {"1": float, ...} | {},
      "bounty_type_text": "PKO 50%" | "Mystery KO" | etc | null
    }

build_hrc_payouts_blob() converte para o schema canonico HRC Structure
Manager validado contra sample real (_local_only/sample_payouts/).
"""
from __future__ import annotations
import base64
import json
import logging
import re
from typing import Any, Optional

logger = logging.getLogger("lobby_vision")


# ── Lookup ratio bounty por nome do torneio ─────────────────────────────────
# Validado contra 97 torneios distintos em prod (auditoria FASE A pre-plan).
# Ordem importa — primeiro match ganha.

LOBBY_RATIO_LOOKUP: list = [
    (lambda n: "monster bounties" in n or "monster ko" in n,    ("PKO", 0.75)),
    (lambda n: "super ko" in n,                                  ("PKO", 0.40)),
    (lambda n: "mystery" in n and ("bounty" in n or "ko" in n), ("KO",  0.33)),
    (lambda n: "bounty hunters" in n,                            ("PKO", 0.50)),
    (lambda n: "bounty builder" in n,                            ("PKO", 0.50)),
    (lambda n: "knockout" in n,                                  ("PKO", 0.50)),
    (lambda n: "[bounty]" in n,                                  ("PKO", 0.50)),
    (lambda n: "bounty" in n,                                    ("PKO", 0.50)),
    (lambda n: True,                                             ("None", 0.0)),
]


def apply_ratio_lookup(tournament_name: str) -> tuple[str, float]:
    """Devolve (bountyType, progressiveFactor) consoante o nome do torneio.
    Sempre devolve tuple — ('None', 0.0) é o fallback final."""
    n = (tournament_name or "").lower()
    for predicate, result in LOBBY_RATIO_LOOKUP:
        if predicate(n):
            return result
    return ("None", 0.0)


# ── Vision call ──────────────────────────────────────────────────────────────

_LOBBY_PROMPT = (
    "This is a poker tournament lobby screenshot. Identify the site by "
    "client design, and extract tournament metadata + payout structure.\n\n"
    "Reply with ONLY a JSON object matching this exact schema (no markdown, "
    "no preamble, no comments):\n"
    "{\n"
    '  "site": "GGPoker" | "PokerStars" | "Winamax" | null,\n'
    '  "tournament_name": "<exact name as shown>",\n'
    '  "start_time_iso": "<ISO 8601 timestamp UTC>" | null,\n'
    '  "starting_stack": <int chips> | null,\n'
    '  "entrants": <int total registered> | null,\n'
    '  "prize_pool": <float USD/EUR total prize pool> | null,\n'
    '  "buy_in": <float USD/EUR> | null,\n'
    '  "prizes": {"1": <float>, "2": <float>, ...},\n'
    '  "bounty_type_text": "<e.g. PKO 50%, Mystery KO>" | null\n'
    "}\n\n"
    "RULES:\n"
    "- prizes keys must be string digits (\"1\", \"2\", not \"1st\").\n"
    "- prizes values must be plain numbers (no currency symbol, no commas).\n"
    "- prize_pool: read 'Total Prize Pool' from the lobby header (plain number, no symbol, no commas).\n"
    "- Use null for fields you cannot read with confidence.\n"
    "- Do NOT invent values not visible in the screenshot.\n"
    "- Output ONLY the JSON object."
)

_MODEL = "claude-sonnet-4-6"


def extract_lobby_payout_json(
    image_bytes: bytes, mime_type: str = "image/png"
) -> Optional[str]:
    """Chama Claude Sonnet 4.6 com a SS da lobby. Devolve raw JSON text ou
    None em caso de falha API. Pre-fill com '{' garante JSON puro (no preamble).
    """
    try:
        from anthropic import Anthropic  # lazy: evita import-time se SDK ausente
    except ImportError:
        logger.error("anthropic SDK nao instalado")
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
                        {"type": "text", "text": _LOBBY_PROMPT},
                    ],
                },
            ],
        )
        # Sonnet 4.6 nao aceita assistant prefill (400). Apanha primeiro
        # {...} no output via regex — resiliente a markdown wrap / prosa.
        text = (response.content[0].text or "").strip()
        m = re.search(r"\{.*\}", text, re.DOTALL)
        return m.group(0) if m else None
    except Exception as e:
        logger.error(f"lobby_vision API error: {type(e).__name__}: {e}")
        return None


# ── Parse + validation ───────────────────────────────────────────────────────

def parse_and_validate_lobby_json(raw: Optional[str]) -> Optional[dict]:
    """Parse + sanity check do JSON Vision. None em qualquer falha."""
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (ValueError, TypeError) as e:
        logger.warning(f"lobby_vision JSON parse error: {e}")
        return None
    if not isinstance(data, dict):
        logger.warning(f"lobby_vision JSON not dict: {type(data).__name__}")
        return None
    name = (data.get("tournament_name") or "").strip()
    if not name:
        logger.warning("lobby_vision JSON missing tournament_name")
        return None
    prizes = data.get("prizes")
    if not isinstance(prizes, dict) or not prizes:
        logger.warning("lobby_vision JSON missing/empty prizes")
        return None
    for k in prizes.keys():
        if not isinstance(k, str) or not k.isdigit():
            logger.warning(f"lobby_vision JSON prize key non-digit: {k!r}")
            return None
    return data


# ── HRC blob builder ─────────────────────────────────────────────────────────

def build_hrc_payouts_blob(vision_json: dict) -> dict:
    """Envolve vision_json no schema canonico HRC Structure Manager.

    chips = starting_stack * entrants (None se faltar algum).
    bountyType + progressiveFactor via apply_ratio_lookup pelo nome.
    """
    name = vision_json["tournament_name"]
    bounty_type, progressive_factor = apply_ratio_lookup(name)
    starting_stack = vision_json.get("starting_stack")
    entrants = vision_json.get("entrants")
    chips: Optional[float] = None
    if starting_stack and entrants:
        chips = float(starting_stack) * float(entrants)
    return {
        "name": "/",
        "folders": [],
        "structures": [{
            "name": name,
            "chips": chips,
            "prizes": vision_json["prizes"],
            "bountyType": bounty_type,
            "progressiveFactor": progressive_factor,
        }],
    }
