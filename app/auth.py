import hashlib
import hmac
import secrets
import time

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from . import db

SESSIONS: dict[str, tuple[str, float]] = {}
SESSION_TTL = 12 * 3600

router = APIRouter()


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()
    return f"{salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, digest = stored.split("$", 1)
    except ValueError:
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()
    return hmac.compare_digest(candidate, digest)


def is_valid_session(token: str | None) -> bool:
    if not token:
        return False
    entry = SESSIONS.get(token)
    return bool(entry) and entry[1] > time.time()


def ensure_default_user(conn, settings) -> None:
    password = settings.auth_pass
    if not password:
        password = secrets.token_urlsafe(16)
        print(f"[fox_netmap] NETZ_AUTH_PASS nicht gesetzt - generiertes Passwort fuer '{settings.auth_user}': {password}")
    db.ensure_user(conn, settings.auth_user, hash_password(password), db.utcnow())
    conn.commit()


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/api/login")
def login(body: LoginRequest, request: Request, response: Response):
    conn = db.connect(request.app.state.db_path)
    try:
        user = db.get_user(conn, body.username)
    finally:
        conn.close()
    if not user or not verify_password(body.password, user["pass_hash"]):
        return JSONResponse({"detail": "invalid credentials"}, status_code=401)
    token = secrets.token_urlsafe(32)
    SESSIONS[token] = (body.username, time.time() + SESSION_TTL)
    response.set_cookie("fox_session", token, httponly=True, samesite="lax", max_age=SESSION_TTL)
    return {"ok": True, "username": body.username}


@router.post("/api/logout")
def logout(request: Request, response: Response):
    SESSIONS.pop(request.cookies.get("fox_session", ""), None)
    response.delete_cookie("fox_session")
    return {"ok": True}


@router.get("/api/me")
def me(request: Request):
    token = request.cookies.get("fox_session")
    if not is_valid_session(token):
        return JSONResponse({"detail": "unauthorized"}, status_code=401)
    return {"username": SESSIONS[token][0]}
