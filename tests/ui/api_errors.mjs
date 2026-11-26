// W5 F-3/SF-6/F-4/F-1: Fehlerschicht api.js - 422 sichtbar, Netzwerkfehler beherrschbar, veraltete Antworten verworfen
import { makeHarness, sleep, standalone } from "./harness.mjs";

const dev = (mac, ip, extra = {}) => ({
  mac, ip, ip6: "", hostname: ip, vendor: "", category: "Client", status: "online",
  subnet: "10.0.0.0/24", site: "", source: "ping+arp", room: "", ports_str: "", connected_to: "",
  note: "", last_seen: "2026-01-01T10:00:00+00:00", port_count: 0, x: null, y: null, connection: "",
  ...extra,
});

const resp422 = (detail) => ({
  ok: false,
  status: 422,
  json: async () => ({ detail }),
  cookies: {},
  blob: async () => new Blob(["x"]),
});

export async function run() {
  let failures = 0;
  const check = (name, cond) => {
    if (!cond) {
      failures++;
      console.error("FAIL:", name);
    }
  };

  // F-3/SF-6: PATCH mit 422 -> role="alert" mit Detail, Eingabe bleibt, kein Reload
  {
    const h = makeHarness({
      devices: [dev("aa:bb:cc:dd:ee:ff", "10.0.0.5")],
      fetchImpl: async (u, opts, fb) => {
        if (String(u).includes("/api/device/") && opts.method === "PATCH") return resp422("assignment would create a cycle");
        return fb(u, opts);
      },
    });
    await sleep(150);
    await h.w.eval("showDetail('aa:bb:cc:dd:ee:ff')");
    await sleep(60);
    h.doc.getElementById("ed-note").value = "wichtige Notiz";
    const reloadsBefore = h.calls.filter((c) => c.url.includes("/api/devices?")).length;
    h.doc.getElementById("ed-save").click();
    await sleep(100);
    const alert = h.doc.getElementById("app-alert");
    check("patch_422: role=alert sichtbar mit Server-Detail", !alert.hidden && alert.getAttribute("role") === "alert" && alert.textContent.includes("cycle"));
    check("patch_422: Eingabe bleibt erhalten", h.doc.getElementById("ed-note").value === "wichtige Notiz");
    check("patch_422: kein Reload nach Fehler", h.calls.filter((c) => c.url.includes("/api/devices?")).length === reloadsBefore);
  }

  // F-4: /api/meta faellt aus -> init stirbt nicht, Tabelle + Scan-Knopf funktionieren
  {
    const h = makeHarness({
      devices: [dev("aa:bb:cc:dd:ee:ff", "10.0.0.5")],
      fetchImpl: async (u, opts, fb) => {
        if (String(u).includes("/api/meta")) throw new TypeError("fetch failed");
        return fb(u, opts);
      },
    });
    await sleep(200);
    check("init_survives_meta_failure: Tabelle trotzdem geladen", h.doc.querySelectorAll("#device-table tbody tr").length === 1);
    h.doc.getElementById("btn-scan").click();
    await sleep(60);
    check("init_survives_meta_failure: Scan-Knopf hat Handler (POST /api/scan)", h.calls.some((c) => c.url.includes("/api/scan") && c.method === "POST"));
  }

  // F-4: Server komplett weg -> Offline-Banner, keine unbehandelte Ablehnung
  {
    const offlineCalls = [];
    const h = makeHarness({
      devices: [],
      fetchImpl: async (u, opts) => {
        offlineCalls.push({ url: String(u), method: (opts && opts.method) || "GET" });
        throw new TypeError("fetch failed");
      },
    });
    await sleep(200);
    check("init_offline: Offline-Banner sichtbar", !h.doc.getElementById("offline-banner").hidden);
    h.doc.getElementById("btn-scan").click();
    await sleep(60);
    check("init_offline: Scan-Knopf trotzdem bedienbar", offlineCalls.some((c) => c.url.includes("/api/scan") && c.method === "POST"));
  }

  // F-1: ueberlappende loadDevices - die zuletzt gestellte (schnelle) Antwort gewinnt
  {
    const devs = [dev("aa:bb:cc:dd:ee:ff", "10.0.0.5", { hostname: "nas" }), dev("bb:bb:bb:bb:bb:02", "10.0.0.6", { hostname: "other" })];
    const h = makeHarness({
      devices: devs,
      fetchImpl: async (u, opts, fb) => {
        const s = String(u);
        if (s.includes("/api/devices")) {
          if (!s.includes("q=")) return new Promise((res) => setTimeout(() => res(h.okJson(devs)), 100));
          return h.okJson(devs.filter((d) => (d.hostname || "").includes("nas")));
        }
        return fb(u, opts);
      },
    });
    await sleep(150);
    const p1 = h.w.eval("loadDevices()");
    h.doc.getElementById("search").value = "nas";
    const p2 = h.w.eval("loadDevices()");
    await p2;
    await p1;
    await sleep(150);
    const rows = h.doc.querySelectorAll("#device-table tbody tr");
    check("stale_response_ignored: nur die zuletzt gestellte Antwort gewinnt", rows.length === 1 && rows[0].textContent.includes("nas"));
  }

  return failures;
}

standalone(run);
