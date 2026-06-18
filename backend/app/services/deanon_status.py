"""Estado de verificação da desanonimização GG, DERIVADO do `match_method`.

Regra (pt76): a desanon por POSIÇÃO (`position_v3`) é verificada; a desanon por
STACK/feltro (`table_ss`, `anchors_stack_elimination_v2*`, `mtt_*`) é "por
verificar / potencialmente errada" (pode trocar vilões de stacks próximos —
ver `DESANON_ANATOMIA §3.2`). Não-GG (nomes reais da HH) e GG sem match real
(null / placeholder) → sem aviso.

É PURO/DERIVADO — nunca guardado numa coluna (não fica stale; se uma mão for
re-desanonimizada para `position_v3`, o estado vira 'verified' sozinho).
"""

VERIFIED_MATCH_METHODS = frozenset({"position_v3"})


def deanon_status(site, match_method):
    """→ 'verified' | 'unverified' | None.

    - 'verified'   : GG desanonimizada por posição (`position_v3`).
    - 'unverified' : GG desanonimizada por stack/feltro (`table_ss`,
                     `anchors_stack_elimination*`, `mtt_*`) → aviso ⚠.
    - None         : não-GG (nomes reais da HH) ou GG sem match real
                     (null / `discord_placeholder_*` / desconhecido) → sem aviso.
    """
    if site != "GGPoker":
        return None
    mm = (match_method or "").strip()
    if not mm:
        return None
    if mm in VERIFIED_MATCH_METHODS:
        return "verified"
    if (mm == "table_ss"
            or mm.startswith("anchors_stack_elimination")
            or mm.startswith("mtt_")):
        return "unverified"
    return None  # placeholders / desconhecido → sem aviso


def _match_method_of(player_names):
    """Extrai `match_method` de um `player_names` (dict ou JSON-str ou None)."""
    if not player_names:
        return None
    if isinstance(player_names, str):
        import json
        try:
            player_names = json.loads(player_names)
        except (ValueError, TypeError):
            return None
    if isinstance(player_names, dict):
        return player_names.get("match_method")
    return None


def deanon_status_from_row(row):
    """Conveniência: calcula a partir de um row com `site` + `player_names`."""
    return deanon_status(row.get("site"),
                         _match_method_of(row.get("player_names")))
