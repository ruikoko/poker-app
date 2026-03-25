import os
import bcrypt
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from fastapi import Cookie, HTTPException, status
from app.db import query, execute_returning

def _serializer():
    secret = os.getenv("SESSION_SECRET")
    if not secret:
        raise RuntimeError("SESSION_SECRET não definido")
    return URLSafeTimedSerializer(secret, salt="poker-session")

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())

def create_session_token(user_id: int) -> str:
    return _serializer().dumps({"uid": user_id})

def decode_session_token(token: str, max_age: int = 86400 * 7) -> dict:
    try:
        return _serializer().loads(token, max_age=max_age)
    except SignatureExpired:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão expirada")
    except BadSignature:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão inválida")

def get_user_by_email(email: str):
    rows = query("SELECT * FROM users WHERE email = %s LIMIT 1", (email,))
    return rows[0] if rows else None

def create_user(email: str, password: str):
    return execute_returning(
        "INSERT INTO users (email, password_hash) VALUES (%s, %s) RETURNING id, email, created_at",
        (email, hash_password(password))
    )

def require_auth(session: str | None = Cookie(default=None)):
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autenticado")
    payload = decode_session_token(session)
    rows = query("SELECT id, email FROM users WHERE id = %s LIMIT 1", (payload["uid"],))
    if not rows:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Utilizador não encontrado")
    return rows[0]
