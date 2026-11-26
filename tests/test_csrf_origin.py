"""W2 S-16: unsichere Methoden mit Sitzungscookie brauchen passenden Origin/Referer."""


def test_foreign_origin_post_rejected(auth_client):
    r = auth_client.post("/api/layout/reset", headers={"Origin": "http://evil.example"})
    assert r.status_code == 403


def test_matching_origin_post_allowed(auth_client):
    r = auth_client.post("/api/layout/reset", headers={"Origin": "http://testserver"})
    assert r.status_code == 200


def test_no_origin_still_allowed(auth_client):
    # Skripte/Clients ohne Origin-Header bleiben erlaubt (SameSite=Lax schuetzt cross-site)
    r = auth_client.post("/api/layout/reset")
    assert r.status_code == 200
