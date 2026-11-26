"""W2 S-4 (parallele Logins zaehlen mit) und S-5 (richtiges Passwort hebt Sperre auf)."""

import threading

from app.security import LoginThrottle


def test_parallel_wrong_logins_capped_at_limit():
    # S-4: Fehlversuche + laufende Versuche duerfen das Limit nicht ueberschreiten
    t = LoginThrottle(max_per_user=5, max_per_ip=20, window=900, lockout=900)
    ok = [t.try_acquire("10.0.0.1", "admin") for _ in range(10)]
    assert sum(ok) == 5  # fuenf Reservierungen, danach dicht (pending zaehlt mit)
    assert t.retry_after("10.0.0.1", "admin") > 0


def test_correct_password_passes_during_ip_lock(client, app):
    # S-5: nach 20 Fehlversuchen (IP-Lock) kommt das richtige Passwort trotzdem durch
    for _ in range(20):
        r = client.post("/api/login", json={"username": "admin", "password": "falsch"})
        assert r.status_code in (401, 429)
    r = client.post("/api/login", json={"username": "admin", "password": "secret"})
    assert r.status_code == 200


def test_login_throttle_parallel_threads():
    t = LoginThrottle(max_per_user=5, max_per_ip=100, window=900, lockout=900)
    results = []

    def worker():
        results.append(t.try_acquire("10.9.9.9", "admin"))

    threads = [threading.Thread(target=worker) for _ in range(15)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert sum(results) == 5  # genau das Limit, nie mehr
