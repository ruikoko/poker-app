import os
import hmac
import logging
import bcrypt
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from fastapi import Cookie, Header, HTTPException, status
from app.db import query, execute_returning

logger = logging.getLogger("auth")

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


def require_auth_or_api_key(
    session: str | None = Cookie(default=None),
    authorization: str | None = Header(default=None),
):
    """Aceita autenticação por cookie de sessão OU por API key Bearer.

    Caminhos (na ordem de tentativa):

    1. Header `Authorization: Bearer <token>`: se presente, compara o token
       com a env var `HRC_WATCHER_API_KEY` em constant-time. Match → devolve
       `{"id": None, "email": None, "auth_type": "api_key"}`. Sem match ou
       env var indefinida → 401 (não faz fallback para cookie — assume que
       quem manda Bearer está explicitamente a usar esse caminho).

    2. Cookie `session` (caminho legado): delega para `require_auth`,
       devolvendo `{"id": uid, "email": ...}` do user em BD.

    3. Sem cookie e sem header → 401.

    Usado por endpoints HRC que precisam de chamada machine-to-machine
    long-lived (watcher do Beelink). Outros endpoints continuam em
    `require_auth` (cookie-only).

    Env var: `HRC_WATCHER_API_KEY` — token de 48 bytes URL-safe gerado
    via `secrets.token_urlsafe(48)`. Rotação = mudar env var + redeploy.
    """
    if authorization and authorization.startswith("Bearer "):
        provided = authorization[len("Bearer "):].strip()
        expected = os.getenv("HRC_WATCHER_API_KEY")
        if expected and provided and hmac.compare_digest(provided, expected):
            logger.info("auth: api_key authenticated")
            return {"id": None, "email": None, "auth_type": "api_key"}
        logger.warning("auth: invalid api_key attempt")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key inválida",
        )

    if session:
        return require_auth(session)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não autenticado",
    )
