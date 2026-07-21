"""PIPELINE DE ESTUDO — o que uma TAG desencadeia, num sítio só (21 Jul 2026).

CAUSA que fecha (#LEI-FIX-NA-CAUSA, família "regra num sítio, ausente noutro"):
o efeito de "esta mão passou a ter tag" estava ESPALHADO — inline no caminho da
folder-tag da captura, parcial no selo de tags (só vilões), ausente no editor da
página (PATCH). Uma mão re-tagada entrava no Estudo sem o funil das coroas nunca
ter corrido (caso real: GG-6090481360, bustado com coroa fantasma $421).

FONTE ÚNICA: `on_hand_tagged(hand_db_id)` corre, por ordem (decisão do Rui):
  1. `apply_villain_rules`        — vilões/notas (idempotente, re-avalia);
  2. `scrub_and_persist`          — funil das coroas (só-tagadas; lê a base do TS
                                    AO VIVO → cobre também o comboio pós-TS perdido);
  3. `trigger_name_propagation`   — nomes fortes do torneio (só se a mão ficou
                                    tagada; alvo de escrita = tagadas);
  4. `trigger_ft_refresh`         — review de mesa final (idem).

Os 3 caminhos de re-tag (PATCH do editor · selo de tags · folder-tag da captura)
são camadas finas sobre isto — como os 12 call-sites do bust. Cada passo é
DEFENSIVO: uma falha loga e segue (o pipeline nunca rebenta o caller).
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("study_pipeline")


def on_hand_tagged(hand_db_id: int, *, vision_data: Optional[dict] = None,
                   incoming_folder_tag=None, conn=None) -> dict:
    """Corre o pipeline de estudo sobre UMA mão que (re)ganhou tag — como se a
    tag tivesse chegado com ela à entrada.

    - `vision_data`: leitura Vision fresca (caminho da captura) → green-fill no funil.
    - `incoming_folder_tag`: a tag pode ainda não estar COMMITADA (reconcile em
      transacção do caller) → força `tagged` no funil ('tagada-depois').
    - `conn`: transacção do caller para os vilões (mesma semântica de sempre);
      os restantes passos usam ligações próprias.

    Devolve auditoria {villains, scrubbed, tagged, tn, propagation_fired, ft_fired}.
    Também é seguro chamar após REMOVER tags: os vilões re-avaliam (limpam), o
    funil vê a mão destagada e não escreve, propagação/FT não disparam."""
    audit = {"hand_db_id": hand_db_id, "villains": False, "scrubbed": 0,
             "tagged": False, "tn": None, "propagation_fired": False,
             "ft_fired": False}

    # 1) vilões/notas — a mesma porta de todos os writers de entrada.
    try:
        from app.services.villain_rules import apply_villain_rules
        apply_villain_rules(hand_db_id, conn=conn)
        audit["villains"] = True
    except Exception as e:  # pragma: no cover - defensivo
        logger.error("[study-pipeline] villain_rules hand %s: %s", hand_db_id, e)

    # 2) funil das coroas — lê apa/pn/raw/tags/TS frescos; só-tagadas (ou
    #    incoming_folder_tag); a base do TS entra AO VIVO (cobre o pós-TS perdido).
    try:
        from app.services.eliminated_bounty import scrub_and_persist
        audit["scrubbed"] = scrub_and_persist(
            hand_db_id, vision_data=vision_data,
            incoming_folder_tag=incoming_folder_tag)
    except Exception as e:  # pragma: no cover - defensivo
        logger.error("[study-pipeline] scrub hand %s: %s", hand_db_id, e)

    # Estado fresco p/ decidir os disparos por-torneio (3 e 4).
    site = tn = None
    try:
        from app.db import query
        rows = query("SELECT site, tournament_number, hm3_tags, discord_tags "
                     "FROM hands WHERE id = %s", (hand_db_id,))
        if rows:
            r = rows[0]
            site, tn = r.get("site"), r.get("tournament_number")
            from app.services.eliminated_bounty import is_tagged
            audit["tagged"] = is_tagged(r) or bool(incoming_folder_tag)
            audit["tn"] = tn
    except Exception as e:  # pragma: no cover - defensivo
        logger.error("[study-pipeline] estado hand %s: %s", hand_db_id, e)

    if not audit["tagged"]:
        return audit                       # destagada: vilões+funil já fizeram o certo

    # 3) propagação de nomes do torneio (GG-only; fire-and-forget, idempotente).
    if site == "GGPoker" and tn:
        try:
            from app.services.name_propagation import trigger_name_propagation
            trigger_name_propagation(tn)
            audit["propagation_fired"] = True
        except Exception as e:  # pragma: no cover - defensivo
            logger.error("[study-pipeline] name_propagation tn=%s: %s", tn, e)

    # 4) review de mesa final (fire-and-forget; relevante p/ tags '-ft').
    try:
        from app.services.ft_boundary import trigger_ft_refresh
        trigger_ft_refresh()
        audit["ft_fired"] = True
    except Exception as e:  # pragma: no cover - defensivo
        logger.error("[study-pipeline] ft_refresh hand %s: %s", hand_db_id, e)

    return audit
