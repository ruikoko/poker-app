import psycopg2, os, sys

conn = psycopg2.connect(os.environ['DATABASE_PUBLIC_URL'])
c = conn.cursor()

GUARD = """
  origin IS NULL
  AND played_at >= '2026-01-01'
  AND entry_id IS NOT NULL
  AND EXISTS (
      SELECT 1 FROM entries e
      WHERE e.id = hands.entry_id
        AND e.source = 'hh_text'
        AND e.entry_type = 'hand_history'
  )
"""

print("DRY-RUN: SELECT COUNT antes do UPDATE")
c.execute(f"SELECT COUNT(*) FROM hands WHERE {GUARD}")
expected = c.fetchone()[0]
print(f"  candidatas a backfill: {expected}")

if expected != 1146:
    print(f"ABORT: esperado 1146, obtido {expected}. Nao aplico UPDATE.")
    sys.exit(1)

print("\nOK (1146). A executar UPDATE ...")
c.execute(f"UPDATE hands SET origin='hh_import' WHERE {GUARD}")
updated = c.rowcount
print(f"  UPDATE rowcount: {updated}")

if updated != 1146:
    print(f"ABORT: UPDATE tocou {updated} linhas (esperado 1146). ROLLBACK.")
    conn.rollback()
    sys.exit(2)

conn.commit()
print("COMMIT OK")

print("\nPOS-BACKFILL breakdown (2026+):")
c.execute("""
    SELECT COALESCE(origin, 'NULL') AS origin, COUNT(*)
    FROM hands
    WHERE played_at >= '2026-01-01'
    GROUP BY origin
    ORDER BY COUNT(*) DESC
""")
for r in c.fetchall():
    print(f"  {r[0]:<15} {r[1]}")

c.close()
conn.close()
