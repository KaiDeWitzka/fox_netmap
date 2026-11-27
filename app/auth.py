"""Authentisierung: Passwort-Hashing, Sessions, Login/Logout.

Sicherheitsrelevante Festlegungen sind in docs/03-sicherheit.md beschrieben.
"""

import hashlib
import hmac
import logging
import os
import secrets
import sqlite3
import threading
import time
from contextlib import suppress
from typing import Any

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import db
from .config import Settings

log = logging.getLogger("fox_netmap")

router = APIRouter()

# --- Passwort-Hashing ---------------------------------------------------------------------------
# Format: "pbkdf2_sha256$<iterationen>$<salt>$<hex-digest>".
# Altformat bis v1.4.x: "<salt>$<hex-digest>" mit 100.000 Iterationen. Es wird weiter akzeptiert und
# beim nächsten erfolgreichen Login transparent auf das aktuelle Format umgestellt.

PBKDF2_ITERATIONS = 600_000  # OWASP Password Storage Cheat Sheet (2023) für PBKDF2-HMAC-SHA256
LEGACY_ITERATIONS = 100_000
_SCHEME = "pbkdf2_sha256"


def _pbkdf2(password: str, salt: str, iterations: int) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations).hex()


def hash_password(password: str, salt: str | None = None, iterations: int | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    iterations = iterations or PBKDF2_ITERATIONS
    return f"{_SCHEME}${iterations}${salt}${_pbkdf2(password, salt, iterations)}"


def _parse(stored: str) -> tuple[int, str, str] | None:
    parts = stored.split("$")
    if len(parts) == 4 and parts[0] == _SCHEME and parts[1].isdigit():
        return int(parts[1]), parts[2], parts[3]
    if len(parts) == 2:
        return LEGACY_ITERATIONS, parts[0], parts[1]
    return None


def verify_password(password: str, stored: str) -> bool:
    parsed = _parse(stored or "")
    if parsed is None:
        return False
    iterations, salt, digest = parsed
    return hmac.compare_digest(_pbkdf2(password, salt, iterations), digest)


def needs_rehash(stored: str) -> bool:
    parsed = _parse(stored or "")
    return parsed is None or not stored.startswith(_SCHEME + "$") or parsed[0] < PBKDF2_ITERATIONS


# Für unbekannte Benutzer wird gegen diesen Hash geprüft, damit die Antwortzeit nicht verrät,
# ob ein Benutzername existiert (Schutz vor User-Enumeration).
_DUMMY_HASH: str | None = None


def _dummy_hash() -> str:
    global _DUMMY_HASH
    if _DUMMY_HASH is None or not _DUMMY_HASH.startswith(f"{_SCHEME}${PBKDF2_ITERATIONS}$"):
        _DUMMY_HASH = hash_password(secrets.token_urlsafe(16))
    return _DUMMY_HASH


# --- Sessions -----------------------------------------------------------------------------------
# Bewusst nur im Speicher: Ein Neustart meldet alle Benutzer ab. Abgelaufene Sessions werden bei jedem
# Login und regelmäßig bei der Prüfung entfernt; die Anzahl ist begrenzt (älteste fliegen zuerst raus).

SESSION_TTL = 12 * 3600
MAX_SESSIONS = 200
_PRUNE_EVERY = 60

SESSIONS: dict[str, tuple[str, float]] = {}
_sessions_lock = threading.Lock()
_last_prune = 0.0


def prune_sessions(now: float | None = None) -> int:
    """Entfernt abgelaufene Sessions und kappt auf MAX_SESSIONS. Liefert die Anzahl entfernter Einträge."""
    global _last_prune
    now = now or time.time()
    with _sessions_lock:
        before = len(SESSIONS)
        for token in [t for t, (_, exp) in SESSIONS.items() if exp <= now]:
            del SESSIONS[token]
        if len(SESSIONS) > MAX_SESSIONS:
            for token, _ in sorted(SESSIONS.items(), key=lambda kv: kv[1][1])[: len(SESSIONS) - MAX_SESSIONS]:
                del SESSIONS[token]
        _last_prune = now
        return before - len(SESSIONS)


def create_session(username: str, now: float | None = None) -> str:
    now = now or time.time()
    token = secrets.token_urlsafe(32)
    with _sessions_lock:
        SESSIONS[token] = (username, now + SESSION_TTL)
    prune_sessions(now)
    return token


def is_valid_session(token: str | None) -> bool:
    now = time.time()
    if now - _last_prune > _PRUNE_EVERY:
        prune_sessions(now)
    if not token:
        return False
    entry = SESSIONS.get(token)
    if entry is None:
        return False
    return entry[1] > now


def _cookie_secure(request: Request) -> bool:
    mode = str(getattr(request.app.state.settings, "cookie_secure", "auto")).strip().lower()
    if mode in ("true", "1", "yes", "on"):
        return True
    if mode in ("false", "0", "no", "off"):
        return False
    # auto: Secure, sobald die Verbindung (direkt oder laut Reverse Proxy) per HTTPS läuft.
    proto = request.headers.get("x-forwarded-proto", "").split(",")[0].strip().lower()
    return request.url.scheme == "https" or proto == "https"


# --- Initialer Benutzer -------------------------------------------------------------------------

INITIAL_PASSWORD_FILE = "initial-admin-password.txt"  # noqa: S105 - Dateiname, kein Passwort


def ensure_default_user(conn: sqlite3.Connection, settings: Settings) -> None:
    """Legt den Admin an bzw. setzt sein Passwort aus NETZ_AUTH_PASS.

    Ohne NETZ_AUTH_PASS wird nur beim allerersten Start ein Zufallspasswort erzeugt und in
    <data_dir>/initial-admin-password.txt (Rechte 0600) abgelegt, nicht ins Log geschrieben.
    Bei späteren Starts bleibt das bestehende Passwort erhalten.
    """
    password = settings.auth_pass
    existing = db.get_user(conn, settings.auth_user)
    if password:
        if (
            existing is None
            or not verify_password(password, existing["pass_hash"])
            or needs_rehash(existing["pass_hash"])
        ):
            db.ensure_user(conn, settings.auth_user, hash_password(password), db.utcnow())
        _remove_initial_password_file(settings.data_dir)
    elif existing is None:
        password = secrets.token_urlsafe(16)
        db.ensure_user(conn, settings.auth_user, hash_password(password), db.utcnow())
        path = _write_initial_password_file(settings.data_dir, settings.auth_user, password)
        log.warning(
            "NETZ_AUTH_PASS nicht gesetzt: Startpasswort fuer '%s' liegt in %s (nur fuer den Besitzer lesbar). "
            "Bitte NETZ_AUTH_PASS setzen und die Datei loeschen.",
            settings.auth_user,
            path,
        )
    conn.commit()


def _write_initial_password_file(data_dir: str, username: str, password: str) -> str:
    path = os.path.join(data_dir, INITIAL_PASSWORD_FILE)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(f"Benutzer: {username}\nPasswort: {password}\n")
    os.chmod(path, 0o600)
    return path


def _remove_initial_password_file(data_dir: str) -> None:
    with suppress(FileNotFoundError):
        os.remove(os.path.join(data_dir, INITIAL_PASSWORD_FILE))


# --- Endpunkte ----------------------------------------------------------------------------------


class LoginRequest(BaseModel):
    username: str = Field(max_length=128)
    password: str = Field(max_length=1024)


@router.post("/api/login")
def login(
    body: LoginRequest, request: Request, response: Response
) -> Any:  # Any: FastAPI baut aus Union[Response, dict] kein response_model
    throttle = request.app.state.login_throttle
    client_ip = request.client.host if request.client else "unknown"
    wait = throttle.retry_after(client_ip, body.username)
    if wait:
        # S-5: bei aktiver Sperre wird das Passwort trotzdem geprueft - ein richtiges kommt durch
        # (sonst sperrt ein Angreifer hinter einem gemeinsamen Proxy alle aus). Die Kosten begrenzen
        # die Drossel: ohne Reservierung laeuft kein Hash.
        if not throttle.try_acquire_unlocked(client_ip, body.username):
            log.warning("Login gesperrt (zu viele Fehlversuche) fuer IP %s, Benutzer '%s'", client_ip, body.username)
            return JSONResponse(
                {"detail": "too many failed attempts"}, status_code=429, headers={"Retry-After": str(wait)}
            )
    elif not throttle.try_acquire(client_ip, body.username):
        # S-4: Limit (inkl. laufender Versuche) erreicht - ohne Hash ablehnen
        log.warning("Login gedrosselt (zu viele Versuche) fuer IP %s, Benutzer '%s'", client_ip, body.username)
        return JSONResponse({"detail": "too many failed attempts"}, status_code=429)
    conn = db.connect(request.app.state.db_path)
    try:
        user = db.get_user(conn, body.username)
        stored = user["pass_hash"] if user else _dummy_hash()
        ok = verify_password(body.password, stored) and user is not None
        if ok and needs_rehash(stored):
            db.ensure_user(conn, body.username, hash_password(body.password), db.utcnow())
            conn.commit()
            log.info("Passwort-Hash fuer '%s' auf %s Iterationen aktualisiert", body.username, PBKDF2_ITERATIONS)
    finally:
        conn.close()
    if not ok:
        throttle.release(client_ip, body.username, success=False)
        log.warning("Login fehlgeschlagen fuer Benutzer '%s' von IP %s", body.username, client_ip)
        if wait:
            return JSONResponse(
                {"detail": "too many failed attempts"}, status_code=429, headers={"Retry-After": str(wait)}
            )
        return JSONResponse({"detail": "invalid credentials"}, status_code=401)
    # S-5: richtiges Passwort ist auch waehrend einer Sperre gueltig (sonst sperrt ein Angreifer
    # hinter einem gemeinsamen Proxy alle aus); register_success hebt die Sperre auf
    throttle.release(client_ip, body.username, success=True)
    log.info("Login ok: %s", body.username)
    token = create_session(body.username)
    response.set_cookie(
        "fox_session",
        token,
        httponly=True,
        samesite="lax",
        max_age=SESSION_TTL,
        secure=_cookie_secure(request),
        path="/",
    )
    return {"ok": True, "username": body.username}


@router.post("/api/logout")
def logout(request: Request, response: Response) -> dict[str, Any]:
    with _sessions_lock:
        SESSIONS.pop(request.cookies.get("fox_session", ""), None)
    response.delete_cookie("fox_session", path="/", httponly=True, samesite="lax", secure=_cookie_secure(request))
    return {"ok": True}


@router.get("/api/me")
def me(request: Request) -> Any:  # Any: 401 als JSONResponse, sonst dict - kein response_model
    token = request.cookies.get("fox_session")
    entry = SESSIONS.get(token or "")
    if not is_valid_session(token) or entry is None:
        return JSONResponse({"detail": "unauthorized"}, status_code=401)
    return {"username": entry[0]}
