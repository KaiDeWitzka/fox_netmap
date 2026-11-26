// W5 F-9: Seitenleiste - Fokus beim Oeffnen ins Panel, Escape schliesst, Fokus zurueck zum Opener; aria-Labels
import { makeHarness, sleep, standalone } from "./harness.mjs";

const dev = (mac, ip, extra = {}) => ({
  mac, ip, ip6: "", hostname: ip, vendor: "", category: "Client", status: "online",
  subnet: "10.0.0.0/24", site: "", source: "ping+arp", room: "", ports_str: "", connected_to: "",
  note: "", last_seen: "2026-01-01T10:00:00+00:00", port_count: 0, x: null, y: null, connection: "",
  ...extra,
});

export async function run() {
  const h = makeHarness({ devices: [dev("aa:bb:cc:dd:ee:ff", "10.0.0.5")] });
  await sleep(150);
  await h.w.eval("loadDevices()");
  await sleep(40);
  h.doc.getElementById("btn-scan").focus();
  await h.w.eval("showDetail('aa:bb:cc:dd:ee:ff')");
  await sleep(80);
  const aside = h.doc.getElementById("detail");
  h.check("sidebar_focus: Panel offen", !aside.hidden);
  h.check("sidebar_focus: Fokus liegt im Panel", aside.contains(h.doc.activeElement));
  h.check(
    "sidebar_focus: ed-cat/ed-note/ed-parent haben aria-label",
    !!h.doc.getElementById("ed-cat")?.getAttribute("aria-label") &&
      !!h.doc.getElementById("ed-note")?.getAttribute("aria-label") &&
      !!h.doc.getElementById("ed-parent")?.getAttribute("aria-label")
  );
  h.doc.dispatchEvent(new h.w.KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true }));
  await sleep(30);
  h.check("sidebar_escape: Escape schliesst die Seitenleiste", aside.hidden);
  h.check("sidebar_escape: Fokus geht zurueck zum Opener (#btn-scan)", h.doc.activeElement === h.doc.getElementById("btn-scan"));
  return h.failures;
}

standalone(run);
