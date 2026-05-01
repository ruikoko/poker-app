"""
Backfill script Phase 2:
Apaga villains antigos e recria baseados em showdown (jogadores que mostraram cartas).
Phase 1 (has_showdown) já foi feita via SQL direto.
"""
import os
import sys
import json
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.db import get_conn, query
from app.parsers.gg_hands import parse_hands as gg_parse_hands
from app.services.villain_rules import apply_villain_rules

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backfill_showdown")


def run():
    logger.info("=== Recreating villains based on showdown ===")

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # Get showdown hands with player_names (matched hands)
            cur.execute("""
                SELECT id, raw, player_names
                FROM hands
                WHERE has_showdown = TRUE
                  AND player_names IS NOT NULL
                  AND raw IS NOT NULL AND raw != ''
            """)
            showdown_hands = cur.fetchall()
            logger.info(f"Found {len(showdown_hands)} showdown hands with player_names.")

            # Delete ALL existing villains first
            cur.execute("DELETE FROM hand_villains")
            deleted = cur.rowcount
            logger.info(f"Deleted {deleted} old villains.")

            created_total = 0
            skipped = 0

            for i, r in enumerate(showdown_hands):
                hand_db_id = r["id"]
                raw_hh = r["raw"]
                player_names = r["player_names"] or {}

                if isinstance(player_names, str):
                    try:
                        player_names = json.loads(player_names)
                    except:
                        player_names = {}

                # Parse HH
                parsed_list, _errs = gg_parse_hands(raw_hh.encode("utf-8"), f"hand_{hand_db_id}.txt")
                if not parsed_list:
                    skipped += 1
                    continue

                parsed = parsed_list[0]

                # Check if there are showdown cards in parsed data
                apa = parsed.get("all_players_actions", {})
                has_showdown_cards = False
                if isinstance(apa, dict):
                    for p, pdata in apa.items():
                        if p == "_meta":
                            continue
                        if isinstance(pdata, dict) and not pdata.get("is_hero") and pdata.get("cards"):
                            has_showdown_cards = True
                            break

                if not has_showdown_cards:
                    skipped += 1
                    continue

                # Reconstruct screenshot_data from player_names
                screenshot_data = {
                    "hero": player_names.get("hero"),
                    "vision_sb": player_names.get("vision_sb"),
                    "vision_bb": player_names.get("vision_bb"),
                    "players_list": player_names.get("players_list") or [],
                    "players_by_position": player_names.get("players_by_position") or {},
                    "file_meta": player_names.get("file_meta") or {},
                }

                # ONDA 5 #B23 refactor: substitui _create_villains_for_hand pela
                # função canónica apply_villain_rules. Flag showdown_only=True
                # deprecada — apply_villain_rules trata showdown naturalmente
                # via has_cards no candidate building (per comment legacy
                # mtt.py:646-648: regra A∨C∨D já lida com ambos os modos).
                try:
                    result = apply_villain_rules(hand_db_id, conn=conn)
                    n = result["n_villains_created"]
                    created_total += n
                    if n > 0 and (i < 5 or i % 50 == 0):
                        logger.info(f"[{i+1}/{len(showdown_hands)}] Hand {hand_db_id}: created {n} showdown villains.")
                except Exception as e:
                    logger.warning(f"Hand {hand_db_id} failed: {e}")
                    skipped += 1
                    continue

            conn.commit()
            logger.info(f"Done! Created {created_total} showdown villains total. Skipped {skipped} hands.")

    except Exception as e:
        conn.rollback()
        import traceback
        logger.error(f"Error: {e}")
        traceback.print_exc()
    finally:
        conn.close()


if __name__ == "__main__":
    run()
