// W5 F-7: Kartenberechnung darf nicht kubisch wachsen - 1000 Geraete unter 1 s (Kinderzahlen einmal je Render)
import { makeHarness, sleep, standalone } from "./harness.mjs";

export async function run() {
  const hex = (n) => n.toString(16).padStart(2, "0");
  const big = Array.from({ length: 1000 }, (_, i) => ({
    mac: `aa:bb:${hex((i >> 8) & 255)}:${hex(i & 255)}:${hex((i >> 4) & 255)}:${hex(i & 15)}`,
    ip: `10.0.${(i >> 8) & 255}.${i & 255}`,
    ip6: "", hostname: "host" + i, vendor: "", category: "Client", status: "online",
    subnet: "10.0.0.0/24", site: "", source: "ping+arp", room: "", ports_str: "", connected_to: "10.0.0.1",
    note: "", last_seen: "2026-01-01T10:00:00+00:00", port_count: 0, x: null, y: null, connection: "lan",
  }));
  const h = makeHarness({ devices: big });
  await sleep(250); // init laedt die 1000 Geraete ueber den Fetch-Mock
  const t0 = Date.now();
  await h.w.eval("renderMap()"); // reiner Karten-Neuaufbau (F-7: Kinderzahlen einmal je Render)
  const dt = Date.now() - t0;
  h.check(`render_1000_devices_under_budget: ${dt} ms < 1000 ms`, dt < 1000);
  h.check("render_1000: Graph wurde gebaut", h.cy()._els.length >= 1000);
  return h.failures;
}

standalone(run);
