from fastapi import APIRouter
from app.db import query

router = APIRouter(tags=["health"])

@router.get("/health")
def health():
    try:
        result = query("SELECT 1 AS ok")
        db_ok = result[0]["ok"] == 1
    except Exception as e:
        return {"status": "error", "db": str(e)}, 500
    return {"status": "ok", "db": "connected"}
