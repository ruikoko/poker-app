import os
import sys
import json
import logging

# Add backend dir to path so we can import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.db import get_conn, query
from app.parsers.gg_hands import parse_hands as gg_parse_hands
from app.routers.mtt import _create_villains_for_hand

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("refix_villains")

def run():
    logger.info("Starting retroactive villains creation for refixed hands...")
    
    rows = query(
        """
        SELECT id, hand_id, raw, player_names
        FROM hands
        WHERE player_names->>'match_method' = 'anchors_stack_elimination_v2_refix'
        """
    )
    
    logger.info(f"Found {len(rows)} hands to process.")
    
    conn = get_conn()
    created_total = 0
    skipped = 0
    
    try:
        with conn.cursor() as cur:
            for r in rows:
                hand_db_id = r["id"]
                raw_hh = r["raw"]
                player_names = r["player_names"] or {}
                
                if not raw_hh:
                    logger.warning(f"Hand {hand_db_id} has no raw HH. Skipping.")
                    skipped += 1
                    continue
                    
                # Parse HH
                parsed_list, _errs = gg_parse_hands(raw_hh.encode("utf-8"), f"hand_{hand_db_id}.txt")
                if not parsed_list:
                    logger.warning(f"Hand {hand_db_id} failed to parse. Skipping.")
                    skipped += 1
                    continue
                    
                parsed = parsed_list[0]
                if not parsed.get("vpip_seats"):
                    logger.info(f"Hand {hand_db_id} has no VPIP seats. Skipping.")
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
                
                # Idempotency: delete existing villains for this hand_db_id
                cur.execute("DELETE FROM hand_villains WHERE hand_db_id = %s", (hand_db_id,))
                
                # Create villains
                n = _create_villains_for_hand(conn, parsed, screenshot_data, hand_db_id=hand_db_id)
                created_total += n
                logger.info(f"Hand {hand_db_id}: created {n} villains.")
                
        conn.commit()
        logger.info(f"Done! Created {created_total} villains total. Skipped {skipped} hands.")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    run()
