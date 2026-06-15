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
      "players_left": int | null,           # pt25: mid-tournament players remaining
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
    '  "players_left": <int players still alive mid-tournament> | null,\n'
    '  "average_stack": <int average chip stack mid-tournament> | null,\n'
    '  "places_paid": <int total positions that get paid> | null,\n'
    '  "prize_pool": <float USD/EUR total prize pool> | null,\n'
    '  "buy_in": <float USD/EUR> | null,\n'
    '  "prizes": {"1": <float>, "2": <float>, ...},\n'
    '  "prize_ranges": [\n'
    '    {"rank_from": <int>, "rank_to": <int>, "amount": <float>},\n'
    "    ...\n"
    "  ],\n"
    '  "bounty_type_text": "<e.g. PKO 50%, Mystery KO>" | null\n'
    "}\n\n"
    "RULES:\n"
    "- prizes: ONLY the ranks that have a single individual payout shown\n"
    "  (typically ranks 1..10). Keys must be string digits (\"1\", not \"1st\").\n"
    "- prize_ranges: positions paid in GROUPED ranges (e.g. '11 ~ 12: $3,880.46',\n"
    "  '115 ~ 180: $554.65'). For each range, emit ONE entry with rank_from,\n"
    "  rank_to (inclusive) and amount. DO NOT expand into per-rank entries —\n"
    "  the backend does the expansion. If a payout is shown for a single rank,\n"
    "  put it in 'prizes', not 'prize_ranges'.\n"
    "- prize values must be plain numbers (no currency symbol, no commas).\n"
    "- average_stack: 'Average Stack' shown in the lobby header sidebar\n"
    "  (commonly with BB equivalent next to it, e.g. 'Average Stack: 179,530\n"
    "  (51.3 BB)'). Int chips, no commas.\n"
    "- places_paid: total number of positions paid; commonly labelled 'X\n"
    "  places paid', 'Places Paid: X', or visible as the cap of the prize\n"
    "  table (highest rank with a payout).\n"
    "- prize_pool: 'Total Prize Pool' from the lobby header (plain number).\n"
    "- entrants: TOTAL registered players (static after registration closes,\n"
    "  e.g. 500). Often labelled 'Entries', 'Players Entered', 'Total Entries'.\n"
    "- players_left: players STILL ALIVE in the event RIGHT NOW (decreases as\n"
    "  busts happen). Common formats in lobby header: 'Players Left: X',\n"
    "  'Remaining: X', 'X/Y' (where X is left, Y is entrants), or a 'Players'\n"
    "  count distinct from 'Entries'. If only one number is shown and it's\n"
    "  ambiguous, prefer null to guessing.\n"
    "- Use null (or empty list for prize_ranges) for fields you cannot read\n"
    "  with confidence.\n"
    "- Do NOT invent values not visible in the screenshot.\n"
    "- Output ONLY the JSON object."
)

_MODEL = "claude-sonnet-4-6"


def extract_lobby_payout_json(
    image_bytes: bytes, mime_type: str = "image/png",
    err_out: Optional[dict] = None,
) -> Optional[str]:
    """Chama Claude Sonnet 4.6 com a SS da lobby. Devolve raw JSON text ou
    None em caso de falha API. Pre-fill com '{' garante JSON puro (no preamble).

    pt73 — observabilidade: se `err_out` (dict) for dado, escreve nele
    `err_out['error']` com a causa REAL quando devolve None (espelho do
    table_ss_vision). Tipo de retorno inalterado — os mocks ignoram o arg extra.
    """
    try:
        from anthropic import Anthropic  # lazy: evita import-time se SDK ausente
    except ImportError:
        logger.error("anthropic SDK nao instalado")
        if err_out is not None:
            err_out["error"] = "anthropic SDK nao instalado"
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
        if m:
            return m.group(0)
        if err_out is not None:
            err_out["error"] = "Vision respondeu sem JSON parseable"
        return None
    except Exception as e:
        msg = f"{type(e).__name__}: {e}"
        logger.error(f"lobby_vision API error: {msg}")
        if err_out is not None:
            err_out["error"] = f"Vision API: {msg[:300]}"
        return None


# ── Parse + validation ───────────────────────────────────────────────────────

def parse_and_validate_lobby_json(raw: Optional[str]) -> Optional[dict]:
    """Parse + sanity check do JSON Vision. None em qualquer falha.

    pt29 Fase A extension: aceita `prize_ranges` (list of {rank_from,
    rank_to, amount}) como alternativa OU complemento de `prizes`. Pelo
    menos uma das duas fontes tem de ter conteudo (sem `prizes` E sem
    `prize_ranges` -> rejeita). Campos opcionais novos `average_stack` e
    `places_paid` sao aceites mas nao obrigatorios — graceful degrade.
    """
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

    prizes = data.get("prizes") or {}
    prize_ranges = data.get("prize_ranges") or []
    if not isinstance(prizes, dict):
        logger.warning(f"lobby_vision JSON prizes not dict: {type(prizes).__name__}")
        return None
    if not isinstance(prize_ranges, list):
        logger.warning(
            f"lobby_vision JSON prize_ranges not list: {type(prize_ranges).__name__}"
        )
        return None
    if not prizes and not prize_ranges:
        logger.warning("lobby_vision JSON missing/empty prizes AND prize_ranges")
        return None
    for k in prizes.keys():
        if not isinstance(k, str) or not k.isdigit():
            logger.warning(f"lobby_vision JSON prize key non-digit: {k!r}")
            return None

    return data


# ── HRC blob builder ─────────────────────────────────────────────────────────

def _expand_prize_ranges(prizes: dict, prize_ranges: list) -> dict:
    """pt29 Fase A extension: expande `prize_ranges` em entries individuais
    + mescla com `prizes` singles.

    Cada range {rank_from, rank_to, amount} gera entries
    {str(rank_from): amount, ..., str(rank_to): amount}. Entries em `prizes`
    tem precedencia sobre ranges para a mesma rank (rare; defensivo).

    Entries com tipos/valores invalidos sao silenciosamente skippadas (graceful
    degrade — Vision pode ter um range com amount=null por exemplo).
    """
    out: dict = {}
    # 1. Expandir ranges primeiro (singles podem override).
    for r in (prize_ranges or []):
        if not isinstance(r, dict):
            continue
        rank_from = r.get("rank_from")
        rank_to = r.get("rank_to")
        amount = r.get("amount")
        if not isinstance(rank_from, int) or not isinstance(rank_to, int):
            continue
        if rank_to < rank_from or rank_from < 1:
            continue
        if amount is None or isinstance(amount, bool):
            continue
        try:
            amt = float(amount)
        except (ValueError, TypeError):
            continue
        for r_idx in range(rank_from, rank_to + 1):
            out[str(r_idx)] = amt
    # 2. Singles sobrepoem ranges (entries explicitas ganham).
    for k, v in (prizes or {}).items():
        if isinstance(k, str) and k.isdigit() and v is not None:
            try:
                out[k] = float(v)
            except (ValueError, TypeError):
                continue
    return out


def build_hrc_payouts_blob(vision_json: dict) -> dict:
    """Envolve vision_json no schema canonico HRC Structure Manager.

    chips (pt29 Fase A extension): prefere `average_stack * players_left`
    (total real de chips em jogo mid-tournament). Fallback `starting_stack *
    entrants` (legacy pt18; chips iniciais antes de bust-outs). None se
    nenhuma combinacao disponivel.

    prizes (pt29 Fase A extension): expandido via `_expand_prize_ranges`
    para mesclar singles + ranges agrupados. Lobbys GG mostram tipicamente
    ranks 1..10 individuais + ranks 11..places_paid em ranges.

    bountyType + progressiveFactor via apply_ratio_lookup pelo nome.

    WARN log (nao fatal) se `places_paid` capturado nao bate com o numero
    total de entries pos-expansao — pode indicar Vision miss em algum range.
    """
    name = vision_json["tournament_name"]
    bounty_type, progressive_factor = apply_ratio_lookup(name)

    # pt29: chips real mid-tournament > chips iniciais.
    chips: Optional[float] = None
    avg_stack = vision_json.get("average_stack")
    players_left = vision_json.get("players_left")
    if isinstance(avg_stack, (int, float)) and avg_stack > 0 \
       and isinstance(players_left, int) and players_left > 0:
        chips = float(avg_stack) * float(players_left)
    else:
        starting_stack = vision_json.get("starting_stack")
        entrants = vision_json.get("entrants")
        if starting_stack and entrants:
            chips = float(starting_stack) * float(entrants)

    # pt29: expandir prize_ranges + mesclar com prizes singles.
    prizes_final = _expand_prize_ranges(
        vision_json.get("prizes") or {},
        vision_json.get("prize_ranges") or [],
    )

    # pt29: WARN se places_paid declarado nao bate com numero de entries.
    places_paid = vision_json.get("places_paid")
    if isinstance(places_paid, int) and places_paid > 0:
        actual_count = len(prizes_final)
        if actual_count != places_paid:
            logger.warning(
                "lobby_vision places_paid mismatch: declared=%d, expanded=%d "
                "(tournament=%r). Vision may have missed a range or single.",
                places_paid, actual_count, name,
            )

    return {
        "name": "/",
        "folders": [],
        "structures": [{
            "name": name,
            "chips": chips,
            "prizes": prizes_final,
            "bountyType": bounty_type,
            "progressiveFactor": progressive_factor,
        }],
    }
