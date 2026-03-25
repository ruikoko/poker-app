import os
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()

def get_conn():
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        r = urlparse(database_url)
        return psycopg2.connect(
            host=r.hostname,
            port=r.port or 5432,
            dbname=r.path.lstrip('/'),
            user=r.username,
            password=r.password,
            cursor_factory=RealDictCursor,
            sslmode='require'
        )
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 5432)),
        dbname=os.getenv("DB_NAME", "pokerdb"),
        user=os.getenv("DB_USER", "pokerapp"),
        password=os.getenv("DB_PASSWORD"),
        cursor_factory=RealDictCursor
    )

def query(sql: str, params=None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()

def execute(sql: str, params=None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            conn.commit()
            return cur.rowcount

def execute_returning(sql: str, params=None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            conn.commit()
            return cur.fetchone()
