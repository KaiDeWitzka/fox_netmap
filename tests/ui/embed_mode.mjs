// W5 F-12: Embed-Anicht - wirkungslose Bedienelemente ausgeblendet, Exportlinks tragen den Token
import { makeHarness, sleep, standalone } from "./harness.mjs";

const dev = (mac, ip, extra = {}) => ({
  mac, ip, ip6: "", hostname: ip, vendor: "", category: "Client", status: "online",
  subnet: "10.0.0.0/24", site: "", source: "ping+arp", room: "", ports_str: "", connected_to: "",
  note: "", last_seen: "2026-01-01T10:00:00+00:00", port_count: 0, x: null, y: null, connection: "",
  ...extra,
});

export async function run() {
  const h = makeHarness({ devices: [dev("aa:bb:cc:dd:ee:ff", "10.0.0.5")], url: "http://localhost/embed?token=abc123" });
  await sleep(200);
  h.check("embed: body traegt Klasse embed", h.doc.body.classList.contains("embed"));
  const cs = (el) => h.w.getComputedStyle(el).display;
  h.check(
    "embed_hides_edit_and_tokens_exports: exp-json/exp-csv/btn-pdf/table-tools per CSS ausgeblendet",
    cs(h.doc.getElementById("exp-json")) === "none" &&
      cs(h.doc.getElementById("exp-csv")) === "none" &&
      cs(h.doc.getElementById("btn-pdf")) === "none" &&
      cs(h.doc.querySelector(".table-tools")) === "none"
  );
  h.check(
    "embed_hides_tokens_exports: Exportlinks tragen den Token",
    h.doc.getElementById("exp-json").href.includes("token=abc123") && h.doc.getElementById("exp-csv").href.includes("token=abc123")
  );
  h.check(
    "embed: API-Calls tragen den Token (sonst 401)",
    h.calls.some((c) => c.url.includes("/api/devices") && c.url.includes("token=abc123"))
  );
  return h.failures;
}

standalone(run);
