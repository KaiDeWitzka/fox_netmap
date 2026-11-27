// W5 F-6: Refresh baut den Graphen neu, behaelt aber Zoom/Ausschnitt und schliesst Geisterdetails
import { makeHarness, sleep, standalone } from "./harness.mjs";

const dev = (mac, ip, extra = {}) => ({
  mac, ip, ip6: "", hostname: ip, vendor: "", category: "Client", status: "online",
  subnet: "10.0.0.0/24", site: "", source: "ping+arp", room: "", ports_str: "", connected_to: "",
  note: "", last_seen: "2026-01-01T10:00:00+00:00", port_count: 0, x: null, y: null, connection: "",
  ...extra,
});

export async function run() {
  const devs = [dev("aa:bb:cc:dd:ee:ff", "10.0.0.5")];
  const h = makeHarness({ devices: devs });
  await sleep(150);
  await h.w.eval("loadDevices()");
  await sleep(50);
  const cy = h.cy();
  const fitsAfterFirst = cy._fitCalls || 0;
  h.check("map_refresh: erstes Rendern fixt die Ansicht", fitsAfterFirst >= 1);
  await h.w.eval("showDetail('aa:bb:cc:dd:ee:ff')");
  await sleep(60);
  h.check("map_refresh: Detailfenster offen", !h.doc.getElementById("detail").hidden);
  devs.length = 0;
  devs.push(dev("bb:bb:bb:bb:bb:02", "10.0.0.6"));
  await h.w.eval("loadDevices()");
  await sleep(60);
  h.check("refresh_keeps_viewport: kein erneuter cy.fit beim Refresh", (cy._fitCalls || 0) === fitsAfterFirst);
  h.check("closes_stale_detail: Detailfenster schliesst sich, wenn das Geraet weg ist", h.doc.getElementById("detail").hidden);
  return h.failures;
}

standalone(run);
