"""Gerät löschen (Recht auf Löschung, Art. 17 DSGVO)."""

from app import db
from tests.test_api import insert_device

MAC = "aa:bb:cc:dd:ee:ff"


def _count(app, table, col="mac", val=MAC):
    conn = db.connect(app.state.db_path)
    try:
        return conn.execute(f"SELECT COUNT(*) AS c FROM {table} WHERE {col} = ?", (val,)).fetchone()["c"]
    finally:
        conn.close()


def test_delete_entfernt_alle_daten(auth_client, app):
    insert_device(app)
    conn = db.connect(app.state.db_path)
    now = db.utcnow()
    db.add_history(conn, MAC, "online", now)
    db.add_event(conn, MAC, "new", "", now)
    db.upsert_device(conn, {"mac": "11:22:33:44:55:66", "ip": "192.168.1.11", "status": "online"}, now)
    db.set_layout(conn, "11:22:33:44:55:66", connected_to=MAC, connected_manual=1)
    conn.commit()
    conn.close()

    r = auth_client.delete(f"/api/device/{MAC}")
    assert r.status_code == 200
    for table in db.DEVICE_TABLES:
        assert _count(app, table) == 0, table
    assert _count(app, "device_layout", "connected_to") == 0
    assert auth_client.get(f"/api/device/{MAC}").status_code == 404


def test_delete_unbekannt_404(auth_client):
    assert auth_client.delete("/api/device/00:00:00:00:00:01").status_code == 404


def test_delete_ohne_login_verboten(client, app):
    insert_device(app)
    assert client.delete(f"/api/device/{MAC}").status_code == 401
    assert _count(app, "devices") == 1


def test_delete_mit_embed_token_verboten(auth_client, app):
    """Embed-Tokens sind nur lesend: auch mit gültigem Token kein Löschen ohne Session."""
    insert_device(app)
    tok = auth_client.post("/api/tokens", json={}).json()
    auth_client.cookies.clear()
    token = tok.get("token") or tok["embed_url"].split("token=")[1]
    assert auth_client.delete(f"/api/device/{MAC}?token={token}").status_code == 401
    assert _count(app, "devices") == 1
