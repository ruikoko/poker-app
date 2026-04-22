"""
Serviço de processamento de mãos.
Liga entries a hands: extrai mãos de uma entry e insere-as na tabela hands.
"""
import json
from app.db import get_conn, query, execute_returning
from app.parsers.gg_hands import parse_hands


def _get_or_create_tournament_pk(conn, tournament_id_str: str, site: str) -> int | None:
    """
    Dado o tournament_id string do parser (ex: "1234567"),
    devolve o PK da tabela tournaments (ou None se não existir).
    """
    if not tournament_id_str:
        return None
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM tournaments WHERE tid = %s AND site ILIKE %s",
            (tournament_id_str, f"%{site}%")
        )
        row = cur.fetchone()
        if row:
            return row["id"]
    return None


import logging
logger = logging.getLogger("hand_service")

def _insert_hand(conn, h: dict, entry_id: int | None, tournament_pk: int | None = None, study_state: str = 'mtt_archive') -> bool:
    """Insere uma mão na BD. Retorna True se inserida, False se duplicada."""
    with conn.cursor() as cur:
        if h["hand_id"]:
            logger.info(f"[_insert_hand] Processando hand_id: {h['hand_id']}")
            cur.execute("SELECT id, raw, hm3_tags FROM hands WHERE hand_id = %s", (h["hand_id"],))
            existing = cur.fetchone()
            if existing:
                logger.info(f"[_insert_hand] hand_id {h['hand_id']} já existe. ID: {existing['id']}, raw_len: {len(existing['raw']) if existing['raw'] else 0}, tags: {existing['hm3_tags']}")
                # Se for placeholder GGDiscord (raw vazio + tag GGDiscord), apaga-o para dar lugar à HH real
                is_placeholder = (
                    (not existing["raw"] or existing["raw"].strip() == "") and
                    existing["hm3_tags"] and "GGDiscord" in existing["hm3_tags"]
                )
                if is_placeholder:
                    logger.info(f"[_insert_hand] hand_id {h['hand_id']} é placeholder GGDiscord. A apagar para substituir.")
                    cur.execute("DELETE FROM hands WHERE id = %s", (existing["id"],))
                else:
                    logger.info(f"[_insert_hand] hand_id {h['hand_id']} NÃO é placeholder. Ignorando (duplicado).")
                    return False
            else:
                logger.info(f"[_insert_hand] hand_id {h['hand_id']} é novo. A inserir.")

        all_actions = h.get("all_players_actions")
        all_actions_json = json.dumps(all_actions) if all_actions else None

        # Detect showdown: any non-hero player with cards shown
        has_showdown = False
        if isinstance(all_actions, dict):
            for p, pdata in all_actions.items():
                if p == "_meta":
                    continue
                if isinstance(pdata, dict) and not pdata.get("is_hero") and pdata.get("cards"):
                    has_showdown = True
                    break

        # Resolve tournament_pk from the hand's tournament_id string if not provided
        t_pk = tournament_pk
        if t_pk is None and h.get("tournament_id"):
            t_pk = _get_or_create_tournament_pk(conn, h["tournament_id"], h.get("site", ""))

        cur.execute(
            """
            INSERT INTO hands
                (site, hand_id, played_at, stakes, position,
                 hero_cards, board, result, currency,
                 raw, entry_id, study_state, all_players_actions, tournament_id,
                 has_showdown, buy_in, tournament_format, tournament_name, tournament_number)
            VALUES
                (%(site)s, %(hand_id)s, %(played_at)s, %(stakes)s, %(position)s,
                 %(hero_cards)s, %(board)s, %(result)s, %(currency)s,
                 %(raw)s, %(entry_id)s, %(study_state)s, %(all_players_actions)s, %(tournament_id)s,
                 %(has_showdown)s, %(buy_in)s, %(tournament_format)s, %(tournament_name)s, %(tournament_number)s)
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
                "study_state": study_state,
                "all_players_actions": all_actions_json,
                "tournament_id": t_pk,
                "has_showdown": has_showdown,
                "buy_in": h.get("buy_in"),
                "tournament_format": h.get("tournament_format"),
                # tournament_name: nome real limpo devolvido pelo parser GG.
                # tournament_number: string crua do raw; o parser GG chama-lhe
                # "tournament_id" por historia, mas o valor string vai para
                # a coluna nova hands.tournament_number TEXT. A coluna FK
                # hands.tournament_id BIGINT continua a receber o t_pk resolvido.
                "tournament_name": h.get("tournament_name"),
                "tournament_number": h.get("tournament_id"),
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
