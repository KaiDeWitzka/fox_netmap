// W5 F-2: Tabellen-Neuaufbau nach PATCH stellt Fokus, Wert und Cursor der bearbeiteten Zelle wieder her
import { makeHarness, sleep, standalone } from "./harness.mjs";

const dev = (mac, ip, extra = {}) => ({
  mac, ip, ip6: "", hostname: ip, vendor: "", category: "Client", status: "online",
  subnet: "10.0.0.0/24", site: "", source: "ping+arp", room: "", ports_str: "", connected_to: "",
  note: "", last_seen: "2026-01-01T10:00:00+00:00", port_count: 0, x: null, y: null, connection: "",
  ...extra,
});

export async function run() {
  const h = makeHarness({
    devices: [dev("aa:bb:cc:dd:ee:ff", "10.0.0.5"), dev("bb:bb:bb:bb:bb:02", "10.0.0.6")],
    editMode: true,
  });
  await sleep(150);
  h.doc.querySelector('button[data-view="table"]').click(); // Tabellenansicht sichtbar machen (sonst ist focus() wirkungslos)
  await h.w.eval("loadDevices()");
  await sleep(50);
  const inp = h.doc.querySelector('#device-table tbody tr[data-mac="aa:bb:cc:dd:ee:ff"] input[data-key="note"]');
  h.check("tab_edit: Notiz-Eingabefeld mit data-mac/data-key vorhanden", !!inp);
  if (!inp) return h.failures;
  inp.focus();
  inp.value = "neu";
  inp.setSelectionRange(3, 3);
  inp.dispatchEvent(new h.w.Event("change", { bubbles: true }));
  await sleep(150);
  const after = h.doc.activeElement;
  h.check(
    "tab_through_edit_keeps_focus: Fokus bleibt auf derselben Zelle (gleiche MAC + Spalte)",
    !!after && after.dataset && after.dataset.key === "note" && after.closest("tr").dataset.mac === "aa:bb:cc:dd:ee:ff"
  );
  h.check("tab_through_edit_keeps_focus: Wert und Cursor erhalten", !!after && after.value === "neu" && after.selectionStart === 3);
  h.check(
    "tab_through_edit_keeps_focus: PATCH mit dem neuen Wert wurde gesendet",
    h.calls.some((c) => c.url.includes("/api/device/aa:bb:cc:dd:ee:ff") && c.method === "PATCH" && c.body.includes("neu"))
  );
  return h.failures;
}

standalone(run);
