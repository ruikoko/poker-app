"""Backoffice GG results SS → JSON payouts (Vanilla + PKO).

Pipeline paralelo a lobby_vision: prompt distinto, schema com bounty_won
opcional por posição, validação branch por is_pko.

Mystery KO (tournament_format='KO' do TS) NÃO é suportado aqui em pt20 —
endpoint devolve "mystery_unsupported" se aparecer. Tech debt
#BACKOFFICE-MYSTERY tratará isso em commit futuro.
"""
from __future__ import annotations
import base64
import json
import logging
import re
from typing import Optional

logger = logging.getLogger("backoffice_vision")

_MODEL = "claude-sonnet-4-6"

_BACKOFFICE_PROMPT = (
    "This is the post-tournament results page from a GGPoker backoffice. "
    "It shows final rankings with prize per position and optional bounties.\n\n"
    "Reply with ONLY a JSON object matching this schema (no markdown, "
    "no preamble):\n"
    "{\n"
    '  "tournament_name": "<exact title>",\n'
    '  "buy_in_text": "<as shown>" | null,\n'
    '  "prize_pool": <total prize pool, plain number>,\n'
    '  "total_players": <total entrants, read from "of N" phrase>,\n'
    '  "hero_position": <int> | null,\n'
    '  "is_pko": <true if any paid row shows "$X + $Y" format, else false>,\n'
    '  "prizes": {\n'
    '    "1": {"prize": <float>, "bounty_won": <float> | null},\n'
    '    "2": {"prize": <float>, "bounty_won": <float> | null}\n'
    "  }\n"
    "}\n\n"
    "RULES:\n"
    "- Read the 'Result' column. Two possible formats per row:\n"
    "  (a) \"$X\" alone → {\"prize\": X, \"bounty_won\": null}\n"
    "  (b) \"$X + $Y\" → {\"prize\": X, \"bounty_won\": Y}\n"
    "- Include EVERY position with non-empty Result. Stop at last paid row.\n"
    "- Shared/tied prizes: list each position separately with same prize.\n"
    "- is_pko = true if at least one row shows \"+\" format.\n"
    "- prize_pool: plain number, no symbol/commas.\n"
    "- prizes keys are string digits (\"1\", \"2\", ...).\n"
    "- Use null only where unread with confidence. Do NOT invent.\n"
    "- Output ONLY the JSON object."
)


def extract_backoffice_payout_json(
    image_bytes: bytes, mime_type: str = "image/png"
) -> Optional[str]:
    """Chama Claude Sonnet 4.6 com a SS do backoffice. Devolve raw JSON
    text ou None em caso de falha API."""
    try:
        from anthropic import Anthropic
    except ImportError:
        logger.error("anthropic SDK nao instalado")
        return None

    try:
        client = Anthropic()
        b64 = base64.b64encode(image_bytes).decode("ascii")
        response = client.messages.create(
            model=_MODEL,
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64",
                                                  "media_type": mime_type,
                                                  "data": b64}},
                    {"type": "text", "text": _BACKOFFICE_PROMPT},
                ],
            }],
        )
        text = (response.content[0].text or "").strip()
        m = re.search(r"\{.*\}", text, re.DOTALL)
        return m.group(0) if m else None
    except Exception as e:
        logger.error(f"backoffice_vision API error: {type(e).__name__}: {e}")
        return None


def parse_and_validate_backoffice_json(
    raw: Optional[str],
    ts_pko_ratio: Optional[float] = None,
) -> Optional[dict]:
    """Parse + validation. Retorna dict ou None (invalid).

    Casos especiais:
    - PKO sem ts_pko_ratio → dict com "_error":"missing_pko_ratio" + "_raw".
    - Truncated SS → marca "_ss_likely_truncated" no dict válido.
    """
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (ValueError, TypeError) as e:
        logger.warning(f"backoffice JSON parse error: {e}")
        return None
    if not isinstance(data, dict):
        return None

    name = (data.get("tournament_name") or "").strip()
    if not name:
        return None
    pool = data.get("prize_pool")
    if not isinstance(pool, (int, float)) or pool <= 0:
        return None
    prizes = data.get("prizes")
    if not isinstance(prizes, dict) or not prizes:
        return None
    for k, v in prizes.items():
        if not isinstance(k, str) or not k.isdigit():
            return None
        if not isinstance(v, dict):
            return None
        p = v.get("prize")
        if not isinstance(p, (int, float)):
            return None

    is_pko = bool(data.get("is_pko"))
    data["is_pko"] = is_pko

    sum_prize = sum(v["prize"] for v in prizes.values())
    sum_bounty = sum((v.get("bounty_won") or 0) for v in prizes.values())

    if not is_pko:
        if abs(sum_prize - pool) > 0.05:
            logger.warning(
                f"backoffice vanilla sum off: {sum_prize:.2f} vs {pool:.2f}"
            )
            return None
        return data

    # PKO branch
    if ts_pko_ratio is None:
        return {"_error": "missing_pko_ratio", "_raw": data}
    try:
        ratio = float(ts_pko_ratio)
    except (TypeError, ValueError):
        return {"_error": "missing_pko_ratio", "_raw": data}

    regular_pool = pool * (1.0 - ratio)
    drift = abs(sum_prize - regular_pool)
    if drift > regular_pool * 0.02:
        logger.warning(
            f"backoffice PKO regular sum off: {sum_prize:.2f} vs "
            f"expected {regular_pool:.2f} (drift {drift:.2f})"
        )
        return None

    total_drift = abs((sum_prize + sum_bounty) - pool)
    if total_drift > pool * 0.005:
        data["_ss_likely_truncated"] = True
    return data


def build_backoffice_payouts_blob(
    vj: dict,
    ts_tournament_format: str,
    ts_pko_ratio: Optional[float],
) -> dict:
    """Achata schema rico para canónico HRC. bountyType vem do TS."""
    prizes_flat = {k: v["prize"] for k, v in vj["prizes"].items()}
    if not vj.get("is_pko"):
        bounty_type = "None"
        progressive_factor = 0.0
    else:
        bounty_type = ts_tournament_format or "PKO"
        progressive_factor = float(ts_pko_ratio) if ts_pko_ratio else 0.0
    return {
        "name": "/",
        "folders": [],
        "structures": [{
            "name": vj["tournament_name"],
            "chips": None,
            "prizes": prizes_flat,
            "bountyType": bounty_type,
            "progressiveFactor": progressive_factor,
        }],
    }
