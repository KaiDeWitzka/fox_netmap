"""W2 S-1/C-7/T-5: Embed-Token-Scope wird ueberall respektiert."""

from app import db


def _device(app, mac, ip, subnet, category="Client"):
    conn = db.connect(app.state.db_path)
    db.upsert_device(
        conn, {"mac": mac, "ip": ip, "subnet": subnet, "category": category, "status": "online"}, db.utcnow()
    )
    conn.commit()
    conn.close()


def _token(auth_client, subnets="", categories=""):
    r = auth_client.post("/api/tokens", json={"subnets": subnets, "categories": categories, "expires_hours": 24})
    assert r.status_code == 200
    return r.json()["token"]


def test_device_detail_out_of_scope_returns_404(auth_client, client, app):
    _device(app, "aa:bb:cc:dd:ee:01", "192.0.2.10", "192.0.2.0/24")
    _device(app, "aa:bb:cc:dd:ee:02", "198.51.100.10", "198.51.100.0/24")
    tok = _token(auth_client, subnets="192.0.2.0/24")
    r = client.get(f"/api/device/aa:bb:cc:dd:ee:02?token={tok}")
    assert r.status_code == 404  # nie 403: keine MAC-Existenz verraten
    r = client.get(f"/api/device/aa:bb:cc:dd:ee:01?token={tok}")
    assert r.status_code == 200


def test_multi_subnet_token_lists_all_allowed_subnets(auth_client, client, app):
    _device(app, "aa:bb:cc:dd:ee:01", "192.0.2.10", "192.0.2.0/24")
    _device(app, "aa:bb:cc:dd:ee:02", "198.51.100.10", "198.51.100.0/24")
    _device(app, "aa:bb:cc:dd:ee:03", "203.0.113.10", "203.0.113.0/24")
    tok = _token(auth_client, subnets="192.0.2.0/24,198.51.100.0/24")
    rows = client.get(f"/api/devices?token={tok}").json()
    macs = {r["mac"] for r in rows}
    assert macs == {"aa:bb:cc:dd:ee:01", "aa:bb:cc:dd:ee:02"}  # beide erlaubten Subnetze, nicht nur das erste


def test_requested_subnet_outside_token_never_widens_scope(auth_client, client, app):
    _device(app, "aa:bb:cc:dd:ee:01", "192.0.2.10", "192.0.2.0/24")
    _device(app, "aa:bb:cc:dd:ee:02", "198.51.100.10", "198.51.100.0/24")
    tok = _token(auth_client, subnets="192.0.2.0/24")
    rows = client.get(f"/api/devices?token={tok}&subnet=198.51.100.0/24").json()
    assert rows == []  # angefragtes fremdes Subnetz erweitert den Scope nicht


def test_category_scope(auth_client, client, app):
    _device(app, "aa:bb:cc:dd:ee:01", "192.0.2.10", "192.0.2.0/24", category="Drucker")
    _device(app, "aa:bb:cc:dd:ee:02", "192.0.2.11", "192.0.2.0/24", category="Client")
    tok = _token(auth_client, categories="Drucker")
    rows = client.get(f"/api/devices?token={tok}").json()
    assert [r["mac"] for r in rows] == ["aa:bb:cc:dd:ee:01"]
    r = client.get(f"/api/device/aa:bb:cc:dd:ee:02?token={tok}")
    assert r.status_code == 404


def test_token_expires_hours_validated(auth_client):
    assert auth_client.post("/api/tokens", json={"expires_hours": 0}).status_code == 422  # C-10
    assert auth_client.post("/api/tokens", json={"expires_hours": -5}).status_code == 422
    assert auth_client.post("/api/tokens", json={"expires_hours": 1}).status_code == 200
