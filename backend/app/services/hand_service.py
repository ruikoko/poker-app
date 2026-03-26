"""
Serviço de processamento de mãos.
Liga entries a hands: extrai mãos de uma entry e insere-as na tabela hands.
"""
import json
from app.db import get_conn, query, execute_returning
from app.parsers.gg_hands import parse_hands


def _insert_hand(conn, h: dict, entry_id: int | None) -> bool:
    """Insere uma mão na BD. Retorna True se inserida, False se duplicada."""
    with conn.cursor() as cur:
        if h["hand_id"]:
            cur.execute("SELECT id FROM hands WHERE hand_id = %s", (h["hand_id"],))
            if cur.fetchone():
                return False

        all_actions = h.get("all_players_actions")
        all_actions_json = json.dumps(all_actions) if all_actions else None

        cur.execute(
            """
            INSERT INTO hands
                (site, hand_id, played_at, stakes, position,
                 hero_cards, board, result, currency,
                 raw, entry_id, study_state, all_players_actions)
            VALUES
                (%(site)s, %(hand_id)s, %(played_at)s, %(stakes)s, %(position)s,
                 %(hero_cards)s, %(board)s, %(result)s, %(currency)s,
                 %(raw)s, %(entry_id)s, 'new', %(all_players_actions)s)
            """,
            {
                "site": h["site"],
                "hand_id": h["hand_id"],
                "played_at": h["played_at"],
                "stakes": h["stakes"],
                "position": h["position"],
                "hero_cards": h["hero_cards"] or [],
                "board": h["board"] or [],
                "result": h["result"],
                "currency": h["currency"],
                "raw": h.get("raw", ""),
                "entry_id": entry_id,
                "all_players_actions": all_actions_json,
            },
        )
        return True


def process_entry_to_hands(entry_id: int) -> dict:
    """
    Processa uma entry do tipo hand_history e cria as mãos correspondentes.
    Retorna um resumo: { inserted, skipped, errors }
    """
    rows = query("SELECT * FROM entries WHERE id = %s", (entry_id,))
    if not rows:
        return {"inserted": 0, "skipped": 0, "errors": ["Entry não encontrada"]}

    entry = rows[0]

    if entry["entry_type"] != "hand_history":
        return {"inserted": 0, "skipped": 0, "errors": ["Entry não é hand_history"]}

    raw_text = entry.get("raw_text") or ""
    file_name = entry.get("file_name") or "unknown"

    content = raw_text.encode("utf-8")
    parsed_hands, parse_errors = parse_hands(content, file_name)

    inserted = 0
    skipped = 0

    conn = get_conn()
    try:
        for h in parsed_hands:
            ok = _insert_hand(conn, h, entry_id)
            if ok:
                inserted += 1
            else:
                skipped += 1

        # Actualizar o estado da entry
        new_status = "processed" if not parse_errors else (
            "partial" if inserted > 0 else "failed"
        )
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE entries SET status = %s WHERE id = %s",
                (new_status, entry_id)
            )

        conn.commit()
    except Exception as e:
        conn.rollback()
        parse_errors.append(f"Erro de BD: {e}")
    finally:
        conn.close()

    return {
        "entry_id": entry_id,
        "inserted": inserted,
        "skipped": skipped,
        "errors": parse_errors,
    }
