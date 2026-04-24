"""
Serviço de processamento de mãos.
Liga entries a hands: extrai mãos de uma entry e insere-as na tabela hands.
"""
import json
import logging
from app.db import get_conn, query, execute_returning
from app.parsers.gg_hands import parse_hands
from app.ingest_filters import is_pre_2026

logger = logging.getLogger("hand_service")


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


def _insert_hand(conn, h: dict, entry_id: int | None, tournament_pk: int | None = None, study_state: str = 'mtt_archive') -> bool:
    """Insere uma mão na BD. Retorna True se inserida, False se duplicada.

    Casos especiais:
    - Se já existe hand_id com raw vazio e hm3_tags=['GGDiscord'] (placeholder
      criado pelo fluxo Discord sem HH), apaga-a primeiro e insere a HH real.
      Sem isto, HHs importadas depois do placeholder ficavam presas como
      GGDiscord para sempre.
    """
    if is_pre_2026(h.get("played_at")):
        logger.warning(f"[hand_service legacy] Rejeitada hand_id={h.get('hand_id')} played_at={h.get('played_at')} (<2026)")
        return False
    with conn.cursor() as cur:
        if h["hand_id"]:
            cur.execute(
                """SELECT id, hm3_tags, raw
                   FROM hands WHERE hand_id = %s""",
                (h["hand_id"],)
            )
            existing = cur.fetchone()
            if existing:
                existing_raw = existing.get("raw") or ""
                existing_tags = existing.get("hm3_tags") or []
                is_placeholder = (
                    not existing_raw
                    and "GGDiscord" in existing_tags
                )
                if is_placeholder:
                    # Placeholder Discord sem HH — apagar para permitir insert da HH real
                    cur.execute("DELETE FROM hands WHERE id = %s", (existing["id"],))
                else:
                    # Duplicado real
                    return False

        all_actions = h.get("all_players_actions")
        all_actions_json = json.dumps(all_actions) if all_actions else None

        # Resolve tournament_pk from the hand's tournament_id string if not provided
        t_pk = tournament_pk
        if t_pk is None and h.get("tournament_id"):
            t_pk = _get_or_create_tournament_pk(conn, h["tournament_id"], h.get("site", ""))

        cur.execute(
            """
            INSERT INTO hands
                (site, hand_id, played_at, stakes, position,
                 hero_cards, board, result, currency,
                 raw, entry_id, study_state, all_players_actions, tournament_id)
            VALUES
                (%(site)s, %(hand_id)s, %(played_at)s, %(stakes)s, %(position)s,
                 %(hero_cards)s, %(board)s, %(result)s, %(currency)s,
                 %(raw)s, %(entry_id)s, %(study_state)s, %(all_players_actions)s, %(tournament_id)s)
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
