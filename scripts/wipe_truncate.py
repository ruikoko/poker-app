"""
Script 2 de 2: TRUNCATE das tabelas alvo apos backup (script 1) validado.
- Conecta via DATABASE_PUBLIC_URL.
- Pede confirmacao 'YES' literal em stdin.
- TRUNCATE ... RESTART IDENTITY CASCADE numa transacao unica.
- Verifica contagens pos-TRUNCATE = 0; ROLLBACK se divergir.

Correr so depois de:
  1. scripts/wipe_dump_snapshot.py ter terminado com sucesso.
  2. Conferencia visual do manifest + CSVs no Desktop.
"""
import os
import sys
import psycopg2
from datetime import datetime

# Lista deve coincidir exactamente com TABLES_TO_DUMP no script 1
TABLES_TO_TRUNCATE = [
    "hands",
    "mtt_hands",
    "entries",
    "hand_villains",
    "hand_attachments",   # cascadeado por FK mas explicito vale defesa em profundidade
    "villain_notes",
    "tournaments",
    "tournaments_meta",   # nao tem FK para hands, nao era cascadeado (regressao pt14 Fase 3)
    "import_logs",
    "study_sessions",
    "monthly_stats",
    "discord_sync_state",
]


def main():
    db_url = os.environ.get("DATABASE_PUBLIC_URL")
    if not db_url:
        raise SystemExit("ERRO: DATABASE_PUBLIC_URL nao esta setado.")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    host = db_url.split("@")[1].split("/")[0]

    print("=" * 70)
    print("SCRIPT 2 DE 2 -- TRUNCATE DESTRUTIVO")
    print("=" * 70)
    print(f"Timestamp: {ts}")
    print(f"Database:  {host}")
    print(f"Tabelas alvo ({len(TABLES_TO_TRUNCATE)}):")
    for t in TABLES_TO_TRUNCATE:
        print(f"  - {t}")
    print()

    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    try:
        with conn.cursor() as c:
            # Pre-counts para o log (cross-check com manifest do script 1)
            print("Contagens PRE-TRUNCATE:")
            pre_totals = {}
            pre_grand_total = 0
            for t in TABLES_TO_TRUNCATE:
                c.execute(f"SELECT COUNT(*) FROM {t}")
                n = c.fetchone()[0]
                pre_totals[t] = n
                pre_grand_total += n
                print(f"  {t:<25} {n:>8}")
            print(f"  {'TOTAL':<25} {pre_grand_total:>8}")
            print()

            # Confirmacao stdin (excepto se --yes na CLI: modo automatizado).
            print("Esta accao e IRREVERSIVEL. Sem backup (script 1) nao ha volta.")
            print(f"Vao ser apagadas {pre_grand_total} rows em {len(TABLES_TO_TRUNCATE)} tabelas.")
            print()
            if "--yes" in sys.argv:
                print("Flag --yes detectada. A confirmar automaticamente.")
            else:
                answer = input("Escreve 'YES' (maiusculas, sem aspas) para confirmar: ").strip()
                if answer != "YES":
                    print(f"Confirmacao invalida ('{answer}'). A abortar sem tocar na BD.")
                    conn.rollback()
                    sys.exit(1)

            print()
            print("A executar TRUNCATE em transacao unica...")
            stmt = (
                "TRUNCATE TABLE "
                + ", ".join(TABLES_TO_TRUNCATE)
                + " RESTART IDENTITY CASCADE"
            )
            print(f"  SQL: {stmt}")
            c.execute(stmt)

            # Verificacao pos-TRUNCATE
            print()
            print("Contagens POS-TRUNCATE (antes de commit):")
            divergent = []
            for t in TABLES_TO_TRUNCATE:
                c.execute(f"SELECT COUNT(*) FROM {t}")
                n = c.fetchone()[0]
                marker = "OK" if n == 0 else "FAIL"
                print(f"  [{marker}] {t:<25} {n:>8}")
                if n != 0:
                    divergent.append((t, n))

            if divergent:
                print()
                print(f"FAIL: {len(divergent)} tabelas nao ficaram a 0. A fazer ROLLBACK.")
                for t, n in divergent:
                    print(f"  {t}: {n} rows remanescentes")
                conn.rollback()
                sys.exit(2)

            conn.commit()
            print()
            print("=" * 70)
            print("COMMIT OK -- todas as tabelas a 0.")
            print("=" * 70)
            print()
            print("Proximo passo: re-importar HHs HM3 + sincronizar Discord retroactivo.")

    except Exception as exc:
        conn.rollback()
        print(f"\nErro inesperado: {exc}")
        print("ROLLBACK automatico feito.")
        sys.exit(3)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
