"""
Serviço de processamento de mãos.
Liga entries a hands: extrai mãos de uma entry e insere-as na tabela hands.
"""
from app.db import get_conn, query, execute_returning
from app.parsers.gg_hands import parse_hands


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
    site = entry.get("site") or "GGPoker"

    content = raw_text.encode("utf-8")

    # Parsear as mãos
    if "ggpoker" in site.lower() or "gg" in site.lower():
        parsed_hands, parse_errors = parse_hands(content, file_name)
    else:
        # Fallback: tentar GG parser
        parsed_hands, parse_errors = parse_hands(content, file_name)

    inserted = 0
    skipped = 0

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for h in parsed_hands:
                # Verificar duplicado por hand_id
                if h["hand_id"]:
                    cur.execute(
                        "SELECT id FROM hands WHERE hand_id = %s",
                        (h["hand_id"],)
                    )
                    if cur.fetchone():
                        skipped += 1
                        continue

                cur.execute(
                    """
                    INSERT INTO hands
                        (site, hand_id, played_at, stakes, position,
                         hero_cards, board, result, currency,
                         raw, entry_id, study_state)
                    VALUES
                        (%(site)s, %(hand_id)s, %(played_at)s, %(stakes)s, %(position)s,
                         %(hero_cards)s, %(board)s, %(result)s, %(currency)s,
                         %(raw)s, %(entry_id)s, 'new')
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
                        "raw": h["raw"],
                        "entry_id": entry_id,
                    },
                )
                inserted += 1

            # Actualizar o estado da entry
            new_status = "processed" if not parse_errors else (
                "partial" if inserted > 0 else "failed"
            )
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
