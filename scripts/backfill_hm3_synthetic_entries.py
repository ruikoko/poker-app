"""Backfill retroactivo: criar entries 'hm3_synthetic' para hands HM3
ja existentes com entry_id IS NULL.

Parte 5 do plano #ORFA-HM3-SYNTHETIC-ENTRIES. Idempotente — re-run
nao duplica entries (Peca 1 garante UNIQUE em external_id WHERE
source='hm3_synthetic').

Uso:
    python scripts/backfill_hm3_synthetic_entries.py            # dry-run (default)
    python scripts/backfill_hm3_synthetic_entries.py --apply    # executa em prod
    python scripts/backfill_hm3_synthetic_entries.py --apply --batch 1000

Em Railway:
    railway run python scripts/backfill_hm3_synthetic_entries.py
    railway run python scripts/backfill_hm3_synthetic_entries.py --apply

Antes do --apply em prod: snapshot Railway recomendado.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

# Permite correr standalone fora do contexto FastAPI.
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
sys.path.insert(0, BACKEND)

from app.db import get_conn  # noqa: E402


def fetch_total(conn) -> int:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) AS n
            FROM hands
            WHERE origin = 'hm3'
              AND entry_id IS NULL
        """)
        row = cur.fetchone()
        return int(row["n"] if row else 0)


def fetch_breakdown(conn) -> list[dict]:
    """Quebra a contagem por site para visibilidade pre-apply."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT site, COUNT(*) AS n
            FROM hands
            WHERE origin = 'hm3'
              AND entry_id IS NULL
            GROUP BY site
            ORDER BY n DESC
        """)
        return [dict(r) for r in cur.fetchall()]


def fetch_batch(conn, limit: int, offset: int) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, hand_id, site
            FROM hands
            WHERE origin = 'hm3'
              AND entry_id IS NULL
            ORDER BY id
            LIMIT %s OFFSET %s
        """, (limit, offset))
        return [dict(r) for r in cur.fetchall()]


def upsert_synthetic_entry(conn, hand_id: str, site: str) -> int | None:
    """Cria (ou recupera) a entry sintetica para um hand_id.

    Idempotente via partial UNIQUE em (external_id) WHERE source='hm3_synthetic'.
    Devolve id da entry (novo ou existente).
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO entries
                (source, entry_type, site, file_name, external_id, status)
            VALUES
                ('hm3_synthetic', 'hand_history', %s, 'hm3_bat_backfill', %s, 'resolved')
            ON CONFLICT (external_id) WHERE source = 'hm3_synthetic' AND external_id IS NOT NULL DO NOTHING
            RETURNING id
            """,
            (site, hand_id),
        )
        row = cur.fetchone()
        if row:
            return row["id"]
        # Conflict → fetch existing.
        cur.execute(
            "SELECT id FROM entries WHERE source = 'hm3_synthetic' AND external_id = %s LIMIT 1",
            (hand_id,),
        )
        existing = cur.fetchone()
        return existing["id"] if existing else None


def link_hand_to_entry(conn, hand_db_id: int, entry_id: int) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE hands SET entry_id = %s WHERE id = %s AND entry_id IS NULL",
            (entry_id, hand_db_id),
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Executa em prod (default: dry-run sem alteracoes)",
    )
    parser.add_argument(
        "--batch",
        type=int,
        default=500,
        help="Tamanho do batch (default 500). Maximo razoavel: 1000.",
    )
    args = parser.parse_args()

    conn = get_conn()
    try:
        total = fetch_total(conn)
        breakdown = fetch_breakdown(conn)

        print(f"Hands HM3 com entry_id NULL: {total}")
        print("Breakdown por site:")
        for r in breakdown:
            print(f"  {r['site']!r:<15} {r['n']}")

        if total == 0:
            print("\nNada a fazer.")
            return 0

        if not args.apply:
            print("\n[DRY-RUN] Sem alteracoes. Re-run com --apply para executar.")
            print(f"          Tamanho de batch projectado: {args.batch}")
            print(f"          Batches projectados: {(total + args.batch - 1) // args.batch}")
            return 0

        print(f"\n[APPLY] A processar em batches de {args.batch}...")
        t0 = time.time()
        processed = 0
        linked = 0
        offset = 0
        while True:
            rows = fetch_batch(conn, args.batch, offset)
            if not rows:
                break
            for h in rows:
                eid = upsert_synthetic_entry(conn, h["hand_id"], h["site"])
                if eid is not None:
                    link_hand_to_entry(conn, h["id"], eid)
                    linked += 1
                processed += 1
            conn.commit()
            elapsed = time.time() - t0
            print(
                f"  batch offset={offset} processed={processed}/{total} "
                f"linked={linked} elapsed={elapsed:.1f}s"
            )
            # Iteramos sem offset porque a query WHERE entry_id IS NULL ja
            # exclui os ja processados — proximo fetch_batch comeca pelo
            # primeiro ainda NULL. Mantemos offset=0 para evitar skip.
            # (Se quisesses parallelismo, terias de usar offset++ + lock.)

        print(f"\nDone. Processed {processed}/{total}, linked {linked}.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
