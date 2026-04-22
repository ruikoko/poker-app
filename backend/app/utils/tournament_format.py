"""
Classificacao de formato de torneio.

Valores canonicos (novos, case-exact):
    'Super KO' | 'PKO' | 'Mystery KO' | 'Vanilla'

Hierarquia:
  1. NOME: keywords no nome
       - 'mystery'                         -> 'Mystery KO'
       - 'bounty' / 'pko' / 'knockout'     -> 'PKO'
       - ' ko ' / ' ko$' (standalone)      -> 'PKO' (safe default conservador:
                                              nome ambiguo sem sinal claro
                                              assume-se bounty)
  2. SINAIS ESTRUTURAIS por sala (so quando nome nao decide):
       - PokerStars: 3-componentes no header (raw_hh)
           * B > A                         -> 'Super KO'
           * B == A + 'bounty' no raw      -> 'PKO'
           * B == A sem 'bounty' no raw    -> 'Mystery KO'
       - Winamax: raw_hh contem '<N>€ bounty)' em linha Seat
           * -> 'PKO'
       - GGPoker: has_player_bounty=True
           * -> 'PKO'
       - WPN: sem sinal estrutural fiavel -> 'Vanilla'
  3. Sem sinais                           -> 'Vanilla'.

Legacy (pre-rename) em BD: 'PKO' | 'KO' | 'mystery' | 'vanilla'. Mantem-se
sem backfill. Callers que comparam valores devem usar dual-accept (D3).

O detector nunca devolve 'KO' puro na saida: esse valor existe apenas para
maos legacy ja em BD. Nomes tipo 'KO Daily' sao classificados como 'PKO'
pelo ramo conservador (keyword ` ko `).

Chamada minimal `detect_tournament_format(name)` continua a funcionar (retro-compat).
"""
import re

# ── Name-based detection ─────────────────────────────────────────────────────
_MYSTERY_RE = re.compile(r"mystery", re.I)
_PKO_RE     = re.compile(r"bounty|pko|knockout", re.I)
# Standalone ` ko ` / ` ko$` — nome ambiguo, assume PKO conservador.
# Ordem de avaliacao: _MYSTERY_RE vence (ex: "Mystery KO"), senao _PKO_RE,
# senao _KO_RE. Ver _classify_by_name.
_KO_RE      = re.compile(r"\s+ko(\s|$)", re.I)

# ── Structural signals per site ──────────────────────────────────────────────
# Winamax: "Seat 1: name (12379, 20€ bounty)"
_WN_BOUNTY_RE = re.compile(r"\d+(?:\.\d+)?\s*€\s*bounty\)", re.I)

# PokerStars: 3-componentes "$A+$B+$C" no header; captura os valores
# para comparar A vs B (Super KO vs PKO/Mystery KO).
_PS_3COMP_AMOUNTS_RE = re.compile(
    r"[$€](\d+(?:\.\d+)?)\+[$€](\d+(?:\.\d+)?)\+[$€](\d+(?:\.\d+)?)"
)

# PokerStars: bounty inline nas linhas Seat (ex: "Seat 1: x (24500 in chips, $25 bounty)").
_PS_BOUNTY_RE = re.compile(r"\$\d+(?:\.\d+)?\s*bounty\b", re.I)


def _classify_by_name(tournament_name: str | None) -> str | None:
    """Devolve canonico novo se nome tiver keyword; None caso contrario.

    Ordem de prioridade:
      1. 'mystery' -> 'Mystery KO'  (Mystery vence sempre: torneios Mystery
         sao KO-based mas precisam de ser classificados como Mystery KO,
         nao PKO.)
      2. 'bounty' / 'pko' / 'knockout' -> 'PKO'
      3. ' ko ' / ' ko$' -> 'PKO'   (safe default conservador: nomes
         ambiguos como 'KO Daily' assumem bounty; ver docstring do modulo.)
    """
    if not tournament_name:
        return None
    if _MYSTERY_RE.search(tournament_name):
        return "Mystery KO"
    if _PKO_RE.search(tournament_name):
        return "PKO"
    if _KO_RE.search(tournament_name):
        return "PKO"
    return None


def detect_tournament_format(
    tournament_name: str | None,
    *,
    site: str | None = None,
    raw_hh: str | None = None,
    has_player_bounty: bool | None = None,
) -> str:
    """Devolve 'Super KO' | 'PKO' | 'Mystery KO' | 'Vanilla'. Nunca None."""
    # 1. NOME ganha sempre
    by_name = _classify_by_name(tournament_name)
    if by_name is not None:
        return by_name

    # 2. Sinal estrutural por sala
    if site:
        s = site.lower()
        if s == "pokerstars" and raw_hh:
            # Limita o scan ao header (~2000 chars) para evitar matches no summary.
            header = raw_hh[:2000]
            m = _PS_3COMP_AMOUNTS_RE.search(header)
            if m:
                try:
                    a = float(m.group(1))
                    b = float(m.group(2))
                    if b > a:
                        return "Super KO"
                    if b == a:
                        if _PS_BOUNTY_RE.search(raw_hh):
                            return "PKO"
                        return "Mystery KO"
                except (ValueError, IndexError):
                    pass

        if s == "winamax" and raw_hh and _WN_BOUNTY_RE.search(raw_hh):
            return "PKO"

        if s == "ggpoker" and has_player_bounty:
            return "PKO"

        # WPN: sem sinal estrutural fiavel -> Vanilla
        # Outros sites: fallback no final

    return "Vanilla"
