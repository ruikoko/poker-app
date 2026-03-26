import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.db import get_conn
from app.routers import health, auth, import_, tournaments, hands, villains
from app.routers.entries import router as entries_router

load_dotenv()

app = FastAPI(title="Poker App API", version="0.1.0")

allowed_origin = os.getenv("ALLOWED_ORIGIN", "http://localhost:5173")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[allowed_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def apply_schema():
    """
    Aplica o schema.sql no arranque.
    Isto garante que novas tabelas/colunas (como entries) são criadas
    sem precisares de terminal na Railway.
    """
    schema_path = Path(__file__).resolve().parent.parent / "schema.sql"

    if not schema_path.exists():
        raise RuntimeError(f"schema.sql não encontrado em: {schema_path}")

    sql = schema_path.read_text(encoding="utf-8")

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@app.on_event("startup")
def startup_event():
    apply_schema()


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(import_.router)
app.include_router(tournaments.router)
app.include_router(hands.router)
app.include_router(villains.router)
app.include_router(entries_router)


@app.get("/")
def root():
    return {"app": "poker-app", "version": "0.1.0"}
