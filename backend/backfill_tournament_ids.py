#!/usr/bin/env python3
"""
Script de backfill: liga as mãos existentes aos torneios via tournament_id.

As mãos importadas pelo parser GGPoker têm o campo tournament_id (string) no raw,
mas a coluna hands.tournament_id (FK para tournaments.id) pode estar NULL.

Este script:
1. Lê todos os torneios da tabela tournaments (com o campo tid)
2. Para cada mão com tournament_id NULL, tenta extrair o tournament_id do raw
3. Faz match com tournaments.tid e actualiza hands.tournament_id

Execução: python3 backfill_tournament_ids.py
"""
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from app.db import get_conn

def main():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # 1. Verificar se a coluna existe
            cur.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'hands' AND column_name = 'tournament_id'
            """)
            if not cur.fetchone():
                print("Coluna tournament_id não existe ainda. A executar migration...")
                cur.execute("ALTER TABLE hands ADD COLUMN IF NOT EXISTS tournament_id BIGINT")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_hands_tournament_id ON hands(tournament_id)")
                conn.commit()
                print("Migration executada.")

            # 2. Carregar mapa tid -> pk de todos os torneios
            cur.execute("SELECT id, tid FROM tournaments WHERE tid IS NOT NULL")
            tid_to_pk = {row['tid']: row['id'] for row in cur.fetchall()}
            print(f"Torneios encontrados: {len(tid_to_pk)}")

            # 3. Buscar mãos sem tournament_id mas com raw que contém Tournament #
            cur.execute("""
                SELECT id, raw FROM hands
                WHERE tournament_id IS NULL
                AND raw IS NOT NULL
                AND raw LIKE '%Tournament #%'
            """)
            hands = cur.fetchall()
            print(f"Mãos a processar: {len(hands)}")

            updated = 0
            not_found = 0

            for hand in hands:
                raw = hand['raw'] or ''
                m = re.search(r'Tournament\s*#(\d+)', raw)
                if not m:
                    continue
                tid_str = m.group(1)
                pk = tid_to_pk.get(tid_str)
                if pk:
                    cur.execute(
                        "UPDATE hands SET tournament_id = %s WHERE id = %s",
                        (pk, hand['id'])
                    )
                    updated += 1
                else:
                    not_found += 1

            conn.commit()
            print(f"Mãos actualizadas: {updated}")
            print(f"Torneio não encontrado para: {not_found} mãos")

    except Exception as e:
        conn.rollback()
        print(f"Erro: {e}")
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    main()
