"""T-12 (W6): Lasttest - 500 Geraete in der DB, Listen-API und JSON-Export unter grosszuegigem Budget.
Die Zusage "Performance ab ungefaehr 200 Geraeten" (CHANGELOG) wird damit geprueft."""

import time

from app import db
from app.scanner import run

BUDGET_S = 10.0  # grosszuegig: CI-Maschinen sind langsam, Flapping ist hier nicht zulaessig


def _dev(i: int) -> dict:
    return {
        "mac": f"aa:bb:cc:00:{i // 256:02x}:{i % 256:02x}",
        "ip": f"10.0.{i // 256}.{i % 256}",
        "hostname": f"host-{i:04d}",
        "vendor": "Test",
        "category": "Client",
        "status": "online",
        "subnet": "10.0.0.0/8",
        "source": "ping+arp",
        "ports": [],
        "layout": {},
    }


def test_500_devices_list_under_budget(auth_client, app, settings):
    conn = db.connect(app.state.db_path)
    try:
        run.apply_scan(conn, settings, [_dev(i) for i in range(500)])
    finally:
        conn.close()

    t0 = time.perf_counter()
    r = auth_client.get("/api/devices")
    dt = time.perf_counter() - t0
    assert r.status_code == 200 and len(r.json()) == 500
    assert dt < BUDGET_S, f"GET /api/devices mit 500 Geraeten dauerte {dt:.2f}s (Budget {BUDGET_S}s)"

    t0 = time.perf_counter()
    r = auth_client.get("/api/export/json")
    dt = time.perf_counter() - t0
    assert r.status_code == 200 and "host-0499" in r.text
    assert dt < BUDGET_S, f"GET /api/export/json mit 500 Geraeten dauerte {dt:.2f}s (Budget {BUDGET_S}s)"

    t0 = time.perf_counter()
    r = auth_client.get("/api/device/aa:bb:cc:00:01:f3")
    dt = time.perf_counter() - t0
    assert r.status_code == 200 and r.json()["hostname"] == "host-0499"
    assert dt < BUDGET_S, f"GET /api/device/<mac> dauerte {dt:.2f}s (Budget {BUDGET_S}s)"
