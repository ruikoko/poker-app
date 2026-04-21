"""
Classificação de formato de torneio a partir do nome.

Valores canónicos: 'PKO' | 'KO' | 'mystery' | 'vanilla'

Usado por:
  - parsers.gg_hands (popular hands.tournament_format no parse)
  - routers.mtt (pipeline MTT SS↔HH e import ZIP)
  - services.hand_service._insert_hand (validação indirecta via INSERT)
"""


def detect_tournament_format(tournament_name: str | None) -> str:
    """Devolve 'PKO' | 'KO' | 'mystery' | 'vanilla'. Nunca None."""
    if not tournament_name:
        return "vanilla"
    name_lower = tournament_name.lower()
    if "mystery" in name_lower:
        return "mystery"
    if "bounty" in name_lower or "pko" in name_lower or "knockout" in name_lower:
        return "PKO"
    if " ko " in name_lower or name_lower.endswith(" ko"):
        return "KO"
    return "vanilla"
