import os
from datetime import datetime, timezone
from passlib.context import CryptContext
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from fastapi import Cookie, HTTPException, status
from app.db import query, execute_returning

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

def _serializer():
    secret = os.getenv("SESSION_SECRET")
    if not secret:
        raise RuntimeError("SESSION_SECRET não definido no .env")
    return URLSafeTimedSerializer(secret, salt="poker-session")

# ── Passwords ────────────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return pwd_ctx.hash(plain)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)

# ── Session token ────────────────────────────────────────────────────────────

def create_session_token(user_id: int) -> str:
    return _serializer().dumps({"uid": user_id})

def decode_session_token(token: str, max_age: int = 86400 * 7) -> dict:
    """Lança HTTPException se token inválido ou expirado."""
    try:
        return _serializer().loads(token, max_age=max_age)
    except SignatureExpired:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão expirada")
    except BadSignature:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão inválida")

# ── User helpers ─────────────────────────────────────────────────────────────

def get_user_by_email(email: str):
    rows = query("SELECT * FROM users WHERE email = %s LIMIT 1", (email,))
    return rows[0] if rows else None

def create_user(email: str, password: str):
    return execute_returning(
        "INSERT INTO users (email, password_hash) VALUES (%s, %s) RETURNING id, email, created_at",
        (email, hash_password(password))
    )

# ── Dependency ───────────────────────────────────────────────────────────────

def require_auth(session: str | None = Cookie(default=None)):
    """FastAPI dependency — injeta em qualquer router que precise de auth."""
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autenticado")
    payload = decode_session_token(session)
    rows = query("SELECT id, email FROM users WHERE id = %s LIMIT 1", (payload["uid"],))
    if not rows:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Utilizador não encontrado")
    return rows[0]
