// T-16 (W6): Scan-Anzeige im jsdom mit echtem scanning: 1 (f631a25) und Wechsel auf 0
// mit neuem last_scan muss loadDevices() ausloesen (b454ca8: Auto-Update nach erstem Scan).
import { makeHarness, sleep, standalone } from "./harness.mjs";

const dev = (mac, ip) => ({
  mac, ip, ip6: "", hostname: ip, vendor: "", category: "Client", status: "online",
  subnet: "10.0.0.0/24", site: "", source: "ping+arp", room: "", ports_str: "", connected_to: "",
  note: "", last_seen: "2026-01-01T10:00:00+00:00", port_count: 0, x: null, y: null, connection: "",
});

const scanStatusResp = (state) => ({
  ok: true,
  status: 200,
  json: async () => ({ scanning: state.scanning, last_scan: state.last_scan, next_scan: state.next_scan }),
  cookies: {},
  blob: async () => new Blob(["x"]),
});

const devicesCalls = (h) => h.calls.filter((c) => c.url.includes("/api/devices") && !c.url.includes("/api/device/")).length;

export async function run() {
  const state = { scanning: 1, last_scan: "2026-01-01T10:00:00+00:00", next_scan: "2026-01-01T10:15:00+00:00" };
  const h = makeHarness({
    devices: [dev("aa:bb:cc:dd:ee:ff", "10.0.0.5")],
    // async: api() erwartet ein Promise (fetch(...).then(...))
    fetchImpl: async (u, opts, def) => (String(u).includes("/api/scan/status") ? scanStatusResp(state) : def(u, opts)),
  });
  const deadline = Date.now() + 5000;
  while (Date.now() < deadline && !h.calls.some((c) => c.url.includes("/api/scan/status"))) await sleep(10);
  await h.w.eval("pollScanStatus()");
  await sleep(30);
  const el = h.doc.getElementById("scan-status");
  const runningText = h.w.eval("t('scan.running')");
  h.check("scan_indicator: scanning=1 -> Klasse 'running' gesetzt (f631a25)", el.classList.contains("running"));
  h.check("scan_indicator: scanning=1 -> Text enthaelt t('scan.running')", el.textContent.includes(runningText));

  const before = devicesCalls(h);
  state.scanning = 0;
  state.last_scan = "2026-01-01T10:05:00+00:00";
  await h.w.eval("pollScanStatus()");
  await sleep(50);
  h.check("scan_indicator: scanning 1->0 mit neuem last_scan ruft loadDevices() erneut auf (b454ca8)", devicesCalls(h) > before);
  h.check("scan_indicator: scanning=0 -> Klasse 'running' entfernt", !el.classList.contains("running"));
  h.check("scan_indicator: scanning=0 -> Text enthaelt scan.running nicht mehr", !el.textContent.includes(runningText));

  const h2 = makeHarness({ devices: [], scanStatus: { scanning: 0, last_scan: null, next_scan: null } });
  const deadline2 = Date.now() + 5000;
  while (Date.now() < deadline2 && !h2.calls.some((c) => c.url.includes("/api/devices"))) await sleep(10);
  const base2 = devicesCalls(h2); // init() hat loadDevices() einmal gerufen
  await h2.w.eval("pollScanStatus()");
  await sleep(30);
  const el2 = h2.doc.getElementById("scan-status");
  h2.check("scan_indicator: scanning=0 von Beginn an -> keine 'running'-Klasse", !el2.classList.contains("running"));
  h2.check("scan_indicator: scanning=0 ohne last_scan -> kein zusaetzlicher loadDevices()-Aufruf", devicesCalls(h2) === base2);

  return h.failures + h2.failures;
}

standalone(run);
