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
                vpip_seats = parsed.get("vpip_seats")
                if not vpip_seats:
                    # Fallback: calculate from all_players_actions
                    vpip_seats = []
                    # all_players_actions in parsed is a dict where keys are player names and values are dicts with "actions" dict
                    actions = parsed.get("all_players_actions", {})
                    if isinstance(actions, list):
                        # Handle case where actions is a list of dicts
                        actions_dict = {}
                        for act in actions:
                            if isinstance(act, dict) and "player" in act:
                                p = act["player"]
                                if p not in actions_dict:
                                    actions_dict[p] = {"actions": {"preflop": [], "flop": [], "turn": [], "river": []}}
                                street = act.get("street", "preflop")
                                action_str = act.get("action", "")
                                if action_str:
                                    actions_dict[p]["actions"][street].append(action_str.capitalize())
                        actions = actions_dict
                        
                    if isinstance(actions, dict):
                        for p, p_data in actions.items():
                            if p == "_meta": continue
                            if not isinstance(p_data, dict): continue
                            # VPIP se fez call/raise preflop ou agiu posflop
                            has_vpip = False
                            acts = p_data.get("actions", {}) if isinstance(p_data, dict) else {}
                            if isinstance(acts, list):
                                # If acts is a list, convert it to dict format
                                new_acts = {"preflop": [], "flop": [], "turn": [], "river": []}
                                for a in acts:
                                    if isinstance(a, dict):
                                        street = a.get("street", "preflop")
                                        action_str = a.get("action", "")
                                        if action_str:
                                            new_acts[street].append(action_str.capitalize())
                                acts = new_acts
                            
                            if isinstance(acts, dict):
                                # Check preflop actions
                                preflop_acts = acts.get("preflop", [])
                                if isinstance(preflop_acts, list):
                                    for a in preflop_acts:
                                        if isinstance(a, str) and (a.startswith("Call") or a.startswith("Raise")):
                                            has_vpip = True
                                            break
                                        
                                # Check postflop actions
                                if not has_vpip:
                                    for street in ["flop", "turn", "river"]:
                                        if street in acts and isinstance(acts[street], list) and len(acts[street]) > 0:
                                            has_vpip = True
                                            break
                                        
                            if has_vpip:
                                # Need to find seat from player_names
                                # Try to find in players_list first
                                found_seat = False
                                for pl_data in player_names.get("players_list", []):
                                    if pl_data.get("name") == p:
                                        if pl_data.get("seat") not in vpip_seats:
                                            vpip_seats.append(pl_data.get("seat"))
                                        found_seat = True
                                        break
                                
                                # If not found in players_list, try to get from p_data
                                if not found_seat and "seat" in p_data:
                                    if p_data["seat"] not in vpip_seats:
                                        vpip_seats.append(p_data["seat"])
                    # Convert list to dict with empty string as action, since _create_villains_for_hand expects a dict
                    vpip_seats_dict = {seat: "" for seat in vpip_seats}
                    parsed["vpip_seats"] = vpip_seats_dict
                    
                if not parsed.get("vpip_seats"):
                    logger.info(f"Hand {hand_db_id} has no VPIP seats even after fallback. Skipping.")
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
        import traceback
        logger.error(f"Error: {e}")
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    run()
