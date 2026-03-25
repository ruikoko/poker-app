from fastapi import APIRouter, Response, HTTPException, status, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from app.auth import (
    get_user_by_email, verify_password, create_session_token,
    require_auth, create_user
)
import os

router = APIRouter(prefix="/api/auth", tags=["auth"])

COOKIE_NAME = "session"
COOKIE_MAX_AGE = 86400 * 7  # 7 dias

class LoginBody(BaseModel):
    email: str
    password: str

class RegisterBody(BaseModel):
    email: str
    password: str

@router.post("/login")
def login(body: LoginBody, response: Response):
    user = get_user_by_email(body.email)
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas")

    token = create_session_token(user["id"])
    is_prod = os.getenv("ENV", "production") == "production"

    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=is_prod,          # HTTPS em produção
        samesite="none",
        max_age=COOKIE_MAX_AGE,
        path="/"
    )
    return {"ok": True, "email": user["email"]}

@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(key=COOKIE_NAME, path="/")
    return {"ok": True}

@router.get("/me")
def me(current_user=Depends(require_auth)):
    return {"id": current_user["id"], "email": current_user["email"]}

@router.post("/register")
def register(body: RegisterBody, response: Response):
    """Apenas para criar o primeiro utilizador. Desactivar depois se necessário."""
    if get_user_by_email(body.email):
        raise HTTPException(status_code=400, detail="Email já registado")
    user = create_user(body.email, body.password)
    token = create_session_token(user["id"])
    is_prod = os.getenv("ENV", "production") == "production"
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=is_prod,
        samesite="none",
        max_age=COOKIE_MAX_AGE,
        path="/"
    )
    return {"ok": True, "email": user["email"]}
