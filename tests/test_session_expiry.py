"""T-4/T-15 (W6): Sitzungsablauf wird auch ohne Prune abgelehnt; globaler Zustand zwischen Tests isoliert."""

import time

from app import auth


def test_expired_session_rejected_without_prune(auth_client):
    """M10-Killer: Eine abgelaufene Sitzung muss auch dann 401 liefern, wenn prune_sessions
    gerade nicht anlaeuft - is_valid_session prueft entry[1] > now selbst (auth.py)."""
    token = next(iter(auth.SESSIONS))
    auth._last_prune = time.time()  # Prune laeuft die naechsten _PRUNE_EVERY Sekunden nicht
    auth.SESSIONS[token] = ("admin", time.time() - 1)  # abgelaufen
    assert auth_client.get("/api/me").status_code == 401
    assert token in auth.SESSIONS  # ohne Prune bleibt der Eintrag stehen, wird aber abgelehnt


def test_login_creates_session(auth_client):
    assert len(auth.SESSIONS) >= 1


def test_sessions_isolated_between_tests(client):
    # autouse-Fixture clean_auth_state hat SESSIONS vor diesem Test geleert
    assert auth.SESSIONS == {}
    assert client.get("/api/me").status_code == 401
