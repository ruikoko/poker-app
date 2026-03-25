import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from app.db import get_conn

sql = open(os.path.join(os.path.dirname(__file__), "schema.sql")).read()
conn = get_conn()
try:
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()
    print("Schema aplicado com sucesso.")
except Exception as e:
    conn.rollback()
    print(f"Erro: {e}")
    sys.exit(1)
finally:
    conn.close()
