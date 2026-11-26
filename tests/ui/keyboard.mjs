// W5 F-8: Enter auf Link in der Tabellenzeile wird nicht verschluckt; Kopfzellen per Tastatur sortierbar
import { makeHarness, sleep, standalone } from "./harness.mjs";

const dev = (mac, ip, extra = {}) => ({
  mac, ip, ip6: "", hostname: ip, vendor: "", category: "Client", status: "online",
  subnet: "10.0.0.0/24", site: "", source: "ping+arp", room: "", ports_str: "", connected_to: "",
  note: "", last_seen: "2026-01-01T10:00:00+00:00", port_count: 0, x: null, y: null, connection: "",
  ...extra,
});

export async function run() {
  const h = makeHarness({ devices: [dev("aa:bb:cc:dd:ee:ff", "10.0.0.5", { hostname: "nas", ports_str: "80" })] });
  await sleep(150);
  await h.w.eval("loadDevices()");
  await sleep(50);

  const row = h.doc.querySelector("#device-table tbody tr");
  const link = row.querySelector("a.ext-link");
  h.check("keyboard: ext-link in Tabellenzeile vorhanden", !!link);
  const detailCalls = () => h.calls.filter((c) => c.url.includes("/api/device/")).length;
  if (link) {
    link.focus();
    const before = detailCalls();
    link.dispatchEvent(new h.w.KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true }));
    await sleep(50);
    h.check("enter_on_link_not_swallowed: Enter auf Link oeffnet kein Detail", detailCalls() === before);
  }
  row.focus();
  const beforeRow = detailCalls();
  row.dispatchEvent(new h.w.KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true }));
  await sleep(60);
  h.check("keyboard: Enter auf der Zeile oeffnet das Detail", detailCalls() === beforeRow + 1);

  const th = h.doc.querySelector('#device-table thead th[data-key="hostname"]');
  h.check("headers_sortable_by_keyboard: th hat tabindex=0 und aria-sort", !!th && th.tabIndex === 0 && !!th.getAttribute("aria-sort"));
  th.dispatchEvent(new h.w.KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true }));
  await sleep(40);
  const th2 = h.doc.querySelector('#device-table thead th[data-key="hostname"]');
  h.check("headers_sortable_by_keyboard: Enter auf th sortiert um (aria-sort descending)", !!th2 && th2.getAttribute("aria-sort") === "descending");
  return h.failures;
}

standalone(run);
