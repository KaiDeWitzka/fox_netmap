"""Tests für die Härtung v1.5.0: Passwort-Hash, Sessions, Cookie, Startpasswort, Privacy by Default, Healthcheck."""

import os
import socket
import stat
import subprocess
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app import auth, db, healthcheck
from app.config import Settings
from app.web import create_app

# --- Passwort-Hash ------------------------------------------------------------------------------


def test_production_iterations_meet_owasp(monkeypatch):
    monkeypatch.undo()  # Produktionswert, nicht den schnellen Testwert
    # T-8 (W6): billiger Wachposten - Konstanten-Check, kein Verhaltenstest
    assert auth.PBKDF2_ITERATIONS >= 600_000


def test_hash_format_and_verify():
    h = auth.hash_password("geheim")
    scheme, iterations, salt, _digest = h.split("$")
    assert scheme == "pbkdf2_sha256" and int(iterations) == auth.PBKDF2_ITERATIONS and len(salt) == 32
    assert auth.verify_password("geheim", h)
    assert not auth.verify_password("falsch", h)
    assert not auth.needs_rehash(h)


def test_legacy_hash_still_valid_and_flagged():
    legacy = "abcd$" + auth._pbkdf2("geheim", "abcd", auth.LEGACY_ITERATIONS)
    assert auth.verify_password("geheim", legacy)
    assert auth.needs_rehash(legacy)
    assert not auth.verify_password("geheim", "kaputt")


def test_login_upgrades_legacy_hash(client, app):
    conn = db.connect(app.state.db_path)
    db.ensure_user(conn, "admin", "abcd$" + auth._pbkdf2("secret", "abcd", auth.LEGACY_ITERATIONS), db.utcnow())
    conn.commit()
    assert client.post("/api/login", json={"username": "admin", "password": "secret"}).status_code == 200
    stored = db.get_user(conn, "admin")["pass_hash"]
    conn.close()
    assert stored.startswith(f"pbkdf2_sha256${auth.PBKDF2_ITERATIONS}$")
    assert auth.verify_password("secret", stored)


def test_unknown_user_rejected(client):
    assert client.post("/api/login", json={"username": "gibtsnicht", "password": "x"}).status_code == 401


# --- Sessions und Cookie ------------------------------------------------------------------------


def test_prune_removes_expired_and_caps(monkeypatch):
    monkeypatch.setattr(auth, "SESSIONS", {})
    monkeypatch.setattr(auth, "MAX_SESSIONS", 3)
    now = 1_000_000.0
    auth.SESSIONS["alt"] = ("admin", now - 1)
    for i in range(5):
        auth.SESSIONS[f"s{i}"] = ("admin", now + 100 + i)
    removed = auth.prune_sessions(now)
    assert removed == 3
    assert set(auth.SESSIONS) == {"s2", "s3", "s4"}


def test_logout_invalidates_session(auth_client):
    assert auth_client.get("/api/me").status_code == 200
    auth_client.post("/api/logout")
    assert auth_client.get("/api/me").status_code == 401


def test_cookie_secure_auto(client):
    r = client.post("/api/login", json={"username": "admin", "password": "secret"})
    assert "secure" not in r.headers["set-cookie"].lower()
    r = client.post(
        "/api/login", json={"username": "admin", "password": "secret"}, headers={"X-Forwarded-Proto": "https"}
    )
    assert "secure" in r.headers["set-cookie"].lower()


def test_cookie_secure_forced(tmp_path):
    s = Settings(data_dir=str(tmp_path), auth_pass="secret", cookie_secure="true")
    with TestClient(create_app(s)) as c:
        r = c.post("/api/login", json={"username": "admin", "password": "secret"})
        cookie = r.headers["set-cookie"].lower()
        assert "secure" in cookie and "httponly" in cookie and "samesite=lax" in cookie


# --- Startpasswort ------------------------------------------------------------------------------


def test_initial_password_written_to_file_not_log(tmp_path, capsys, caplog):
    s = Settings(data_dir=str(tmp_path), auth_pass="")
    create_app(s)
    path = tmp_path / auth.INITIAL_PASSWORD_FILE
    assert path.exists()
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    password = path.read_text().split("Passwort: ")[1].strip()
    out = capsys.readouterr()
    assert password not in out.out + out.err + caplog.text
    with TestClient(create_app(s)) as c:  # zweiter Start: Passwort bleibt gleich
        assert c.post("/api/login", json={"username": "admin", "password": password}).status_code == 200


def test_env_password_removes_initial_file(tmp_path):
    create_app(Settings(data_dir=str(tmp_path), auth_pass=""))
    assert (tmp_path / auth.INITIAL_PASSWORD_FILE).exists()
    s = Settings(data_dir=str(tmp_path), auth_pass="neu")
    with TestClient(create_app(s)) as c:
        assert c.post("/api/login", json={"username": "admin", "password": "neu"}).status_code == 200
    assert not (tmp_path / auth.INITIAL_PASSWORD_FILE).exists()


# --- Privacy by Default -------------------------------------------------------------------------


def test_oui_online_lookup_off_by_default(monkeypatch):
    monkeypatch.delenv("NETZ_OUI_ONLINE_ENABLED", raising=False)
    assert Settings(_env_file=None).oui_online_enabled is False


# --- Healthcheck --------------------------------------------------------------------------------


def _state(tmp_path, **fields):
    conn = db.connect(db.db_path(str(tmp_path)))
    db.init_db(conn)
    db.set_scan_state(conn, **fields)
    conn.commit()
    conn.close()


def test_health_scanner_states(tmp_path):
    now = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)
    assert healthcheck.check_scanner(str(tmp_path), now=now)[0]  # noch keine DB
    _state(tmp_path, scanning=0, next_scan=(now + timedelta(minutes=10)).isoformat())
    assert healthcheck.check_scanner(str(tmp_path), now=now)[0]
    _state(tmp_path, scanning=0, next_scan=(now - timedelta(minutes=30)).isoformat())
    ok, msg = healthcheck.check_scanner(str(tmp_path), now=now)
    assert not ok and "ueberfaellig" in msg
    _state(tmp_path, scanning=1)
    assert healthcheck.check_scanner(str(tmp_path), now=now)[0]


def test_health_role_from_env(monkeypatch):
    monkeypatch.setenv("NETZ_ROLE", "scanner")
    assert healthcheck.detect_role() == "scanner"


def test_health_web_unreachable():
    # T-14 (W6): frei gewaehlter, gerade geschlossener Port statt fest verdrahtetem Port 1
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        closed_port = s.getsockname()[1]
    ok, msg = healthcheck.check_web(closed_port)
    assert not ok and "erreichbar" in msg


def test_entrypoint_shell_syntax():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    assert subprocess.run(["sh", "-n", os.path.join(root, "docker", "entrypoint.sh")]).returncode == 0


def test_entrypoint_reports_chown_probe_failure(tmp_path):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    entrypoint = os.path.join(root, "docker", "entrypoint.sh")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fakes = {
        "id": "#!/bin/sh\necho 0\n",
        "find": "#!/bin/sh\necho 'find: simulated I/O error' >&2\nexit 1\n",
        "setpriv": "#!/bin/sh\nexit 0\n",
    }
    for name, body in fakes.items():
        p = bin_dir / name
        p.write_text(body)
        os.chmod(p, 0o700)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "APP_UID": "10001",
        "APP_GID": "10001",
        "NETZ_DATA_DIR": str(data_dir),
    }
    r = subprocess.run(["sh", entrypoint, "scanner"], env=env, capture_output=True, text=True, timeout=15)
    assert r.returncode == 0
    assert "WARN" in r.stderr
    assert "simulated I/O error" in r.stderr
