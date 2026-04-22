"""
Classificação de formato de torneio.

Valores canónicos: 'PKO' | 'KO' | 'mystery' | 'vanilla'

Hierarquia:
  1. NOME ganha sempre (keywords: mystery, bounty/pko/knockout, ' ko ' / ' ko$').
  2. Se nome → vanilla, tenta sinais estruturais por sala (kwargs opcionais):
     - Winamax: raw_hh contém linha Seat com '<N>€ bounty)' → PKO
     - PokerStars: raw_hh header com '[$€]X+[$€]Y+[$€]Z' (3 componentes) → PKO
     - GGPoker: has_player_bounty=True → PKO (caller pré-computa de
                hand_villains/player_names)
     - WPN: sem sinal estrutural, fica vanilla
  3. Sem sinais → vanilla.

Chamada minimal `detect_tournament_format(name)` continua a funcionar (retro-compat).
"""
import re

# ── Name-based detection ─────────────────────────────────────────────────────
_MYSTERY_RE = re.compile(r"mystery", re.I)
_PKO_RE     = re.compile(r"bounty|pko|knockout", re.I)
_KO_RE      = re.compile(r"\s+ko(\s|$)", re.I)

# ── Structural signals per site ──────────────────────────────────────────────
# Winamax: "Seat 1: name (12379, 20€ bounty)"
_WN_BOUNTY_RE = re.compile(r"\d+(?:\.\d+)?\s*€\s*bounty\)", re.I)
# PokerStars: header "Tournament #..., $5.00+$0.50+$0.50 USD..."
_PS_3COMP_RE  = re.compile(
    r"[$€]\d+(?:\.\d+)?\+[$€]\d+(?:\.\d+)?\+[$€]\d+(?:\.\d+)?"
)


def _classify_by_name(tournament_name: str | None) -> str | None:
    """Devolve 'mystery'/'PKO'/'KO' se nome tiver keyword; None caso contrário."""
    if not tournament_name:
        return None
    if _MYSTERY_RE.search(tournament_name):
        return "mystery"
    if _PKO_RE.search(tournament_name):
        return "PKO"
    if _KO_RE.search(tournament_name):
        return "KO"
    return None


def detect_tournament_format(
    tournament_name: str | None,
    *,
    site: str | None = None,
    raw_hh: str | None = None,
    has_player_bounty: bool | None = None,
) -> str:
    """Devolve 'PKO' | 'KO' | 'mystery' | 'vanilla'. Nunca None."""
    # 1. NOME ganha sempre
    by_name = _classify_by_name(tournament_name)
    if by_name is not None:
        return by_name

    # 2. Sinal estrutural por sala (só quando nome → vanilla)
    if site:
        s = site.lower()
        if s == "winamax" and raw_hh and _WN_BOUNTY_RE.search(raw_hh):
            return "PKO"
        if s == "pokerstars" and raw_hh:
            # Limita o scan às primeiras 5 linhas (header) — evita matches no summary
            header = "\n".join(raw_hh.splitlines()[:5])
            if _PS_3COMP_RE.search(header):
                return "PKO"
        if s == "ggpoker" and has_player_bounty:
            return "PKO"
        # WPN: sem sinal estrutural

    return "vanilla"
