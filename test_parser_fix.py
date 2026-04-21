"""
Testa em memória o fix do regex de seats + merge de actions/cards para
PS e WPN. Não escreve nada na BD.

Corre com: railway run python test_parser_fix.py
"""
import os
import sys
import json
import psycopg2
from psycopg2.extras import RealDictCursor

# Para importar app.routers.hm3 (funções puras, sem side-effects em import)
BACKEND = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
sys.path.insert(0, BACKEND)

from app.routers.hm3 import _parse_hand, _parse_actions_from_raw  # noqa: E402


DB_URL = os.environ.get("DATABASE_PUBLIC_URL") or os.environ.get("DATABASE_URL")
if not DB_URL:
    raise SystemExit("DATABASE_PUBLIC_URL / DATABASE_URL não definido no ambiente.")

conn = psycopg2.connect(DB_URL)
conn.autocommit = True
cur = conn.cursor(cursor_factory=RealDictCursor)

CORRUPTED_MARKERS = ("showed", " shows ", " won", "and won")


def has_corrupted_key(apa: dict) -> list[str]:
    bad = []
    for k in apa or {}:
        if k == "_meta":
            continue
        low = k.lower()
        if any(m in low for m in CORRUPTED_MARKERS):
            bad.append(k)
    return bad


def fetch_targets():
    targets = []

    # 1) Pinado pelo utilizador
    cur.execute(
        "SELECT id, hand_id, site, raw, all_players_actions FROM hands WHERE id = %s",
        (182063,),
    )
    row = cur.fetchone()
    if row:
        targets.append(row)

    # 2) +2 mãos PS com chave corrompida no JSON actual
    cur.execute("""
        SELECT id, hand_id, site, raw, all_players_actions
        FROM hands
        WHERE site = 'PokerStars'
          AND has_showdown = TRUE
          AND id <> 182063
          AND raw IS NOT NULL AND raw <> ''
        ORDER BY played_at DESC NULLS LAST
        LIMIT 40
    """)
    rows = cur.fetchall()
    added = 0
    for row in rows:
        apa = row["all_players_actions"]
        if isinstance(apa, str):
            try:
                apa = json.loads(apa)
            except Exception:
                continue
        if not isinstance(apa, dict):
            continue
        if has_corrupted_key(apa):
            targets.append(row)
            added += 1
            if added >= 2:
                break

    # 3) 1 WPN se existir (has_showdown pode estar a FALSE nestas mãos)
    cur.execute("""
        SELECT id, hand_id, site, raw, all_players_actions
        FROM hands
        WHERE site = 'WPN'
          AND raw ILIKE '%shows [%'
          AND raw IS NOT NULL AND raw <> ''
        ORDER BY played_at DESC NULLS LAST
        LIMIT 40
    """)
    for row in cur.fetchall():
        apa = row["all_players_actions"]
        if isinstance(apa, str):
            try:
                apa = json.loads(apa)
            except Exception:
                continue
        if isinstance(apa, dict) and has_corrupted_key(apa):
            targets.append(row)
            break

    return targets


def simulate_import(raw: str, site: str):
    """
    Replica em memória o que import_hm3 faz: _parse_hand + _parse_actions_from_raw +
    merge de actions/cards. Devolve (all_players, merge_stats).
    """
    parsed = _parse_hand(raw, site)
    if not parsed:
        return None, {"parsed": False}

    all_players = dict(parsed.get("all_players") or {})
    all_players["_meta"] = {
        "level": parsed.get("level"),
        "sb": parsed.get("sb_size", 0),
        "bb": parsed.get("bb_size", 0),
        "ante": parsed.get("ante_size", 0),
        "num_players": parsed.get("num_players", 0),
    }

    actions_by_player, cards_by_player = _parse_actions_from_raw(raw, site)

    merge_stats = {
        "parsed": True,
        "players_from_seat": sum(1 for k in all_players if k != "_meta"),
        "actions_players": len(actions_by_player),
        "cards_players": len(cards_by_player),
        "actions_new_entries": 0,
        "cards_new_entries": 0,
        "actions_new_keys": [],
        "cards_new_keys": [],
    }

    for player_name, actions in actions_by_player.items():
        if player_name in all_players and isinstance(all_players[player_name], dict):
            all_players[player_name]["actions"] = actions
        elif player_name != "_meta":
            all_players[player_name] = {"actions": actions}
            merge_stats["actions_new_entries"] += 1
            merge_stats["actions_new_keys"].append(player_name)
    for player_name, cards in cards_by_player.items():
        if player_name in all_players and isinstance(all_players[player_name], dict):
            all_players[player_name]["cards"] = cards
        elif player_name != "_meta":
            all_players[player_name] = {"cards": cards}
            merge_stats["cards_new_entries"] += 1
            merge_stats["cards_new_keys"].append(player_name)

    return all_players, merge_stats


def validate(all_players: dict, merge_stats: dict) -> list[tuple[str, bool, object]]:
    non_meta = {k: v for k, v in all_players.items() if k != "_meta"}
    checks = []

    bad_keys = has_corrupted_key(all_players)
    checks.append(("Sem chaves corrompidas (showed/shows/won)", not bad_keys, bad_keys))

    missing = []
    for k, v in non_meta.items():
        if not isinstance(v, dict):
            missing.append((k, "não é dict"))
            continue
        for field in ("seat", "position", "is_hero", "actions"):
            if field not in v:
                missing.append((k, f"falta {field}"))
    checks.append(("Todos os players têm seat+position+is_hero+actions",
                   not missing, missing))

    no_ghost_entries = (merge_stats["actions_new_entries"] == 0
                        and merge_stats["cards_new_entries"] == 0)
    ghost_detail = (
        f"actions_new={merge_stats['actions_new_entries']} "
        f"({merge_stats['actions_new_keys']}) "
        f"cards_new={merge_stats['cards_new_entries']} "
        f"({merge_stats['cards_new_keys']})"
    )
    checks.append(("Merge não criou entries fantasma", no_ghost_entries, ghost_detail))

    heroes = [k for k, v in non_meta.items()
              if isinstance(v, dict) and v.get("is_hero") is True]
    checks.append(("Exactamente 1 is_hero=True", len(heroes) == 1, heroes))

    return checks


def main():
    targets = fetch_targets()
    if not targets:
        print("Nenhum target encontrado.")
        return

    for t in targets:
        print()
        print("#" * 78)
        print(f"#  id={t['id']}  hand_id={t['hand_id']}  site={t['site']}")
        print("#" * 78)

        apa_before = t["all_players_actions"]
        if isinstance(apa_before, str):
            try:
                apa_before = json.loads(apa_before)
            except Exception:
                apa_before = {}

        print("\nANTES — chaves em all_players_actions (em BD):")
        keys_before = [k for k in (apa_before or {}) if k != "_meta"]
        for k in keys_before:
            print(f"  - {k!r}")
        print(f"  (corrupted: {has_corrupted_key(apa_before or {})})")

        all_players_after, merge_stats = simulate_import(t["raw"], t["site"])
        if all_players_after is None:
            print("\n_parse_hand devolveu None — parser falhou.")
            continue

        print(f"\nDEPOIS — merge_stats: {merge_stats}")

        print("\nValidações:")
        for label, ok, detail in validate(all_players_after, merge_stats):
            mark = "[OK]  " if ok else "[FAIL]"
            extra = "" if ok else f"  ->  {detail}"
            print(f"  {mark} {label}{extra}")

        has_showdown = any(
            isinstance(pdata, dict) and not pdata.get("is_hero") and pdata.get("cards")
            for name, pdata in all_players_after.items()
            if name != "_meta"
        )
        print(f"\nhas_showdown recalculado: {has_showdown}")

        print("\nall_players_actions (DEPOIS, em memória — NÃO gravado em BD):")
        print(json.dumps(all_players_after, indent=2, ensure_ascii=False, default=str))

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
