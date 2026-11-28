// W5 F-15/S-8/SF-5: Einstellungsfenster wird beim Tabwechsel nicht geleert, Theme wird angewandt,
// Secrets als configured mit Loeschen-Button, Zustellstatus wird angezeigt
import { makeHarness, sleep, standalone } from "./harness.mjs";

const dev = (mac, ip, extra = {}) => ({
  mac, ip, ip6: "", hostname: ip, vendor: "", category: "Client", status: "online",
  subnet: "10.0.0.0/24", site: "", source: "ping+arp", room: "", ports_str: "", connected_to: "",
  note: "", last_seen: "2026-01-01T10:00:00+00:00", port_count: 0, x: null, y: null, connection: "",
  ...extra,
});

export async function run() {
  const h = makeHarness({
    devices: [dev("aa:bb:cc:dd:ee:ff", "10.0.0.5")],
    scanStatus: { scanning: 0, last_scan: "2026-11-26T10:00:00+00:00", last_notify_status: "fehlgeschlagen", last_notify_at: "2026-11-26T10:00:00+00:00" },
  });
  await sleep(200);
  h.doc.getElementById("btn-settings").click();
  await sleep(100);
  h.check("settings_form: subnets wird einmal geladen", h.doc.getElementById("st-subnets").value === "10.0.0.0/24");
  h.doc.getElementById("st-subnets").value = "10.9.9.0/24";
  h.doc.getElementById("settings-msg").textContent = "alte Meldung";
  h.doc.getElementById("tab-detail").click();
  await sleep(30);
  h.doc.getElementById("tab-settings").click();
  await sleep(30);
  h.check("form_not_reset_on_tab_change: Feldwert bleibt nach Tabwechsel", h.doc.getElementById("st-subnets").value === "10.9.9.0/24");
  h.check("form_not_reset_on_tab_change: settings-msg wird beim Tabwechsel geleert", h.doc.getElementById("settings-msg").textContent === "");

  h.doc.getElementById("st-theme").value = "light";
  h.doc.getElementById("settings-form").dispatchEvent(new h.w.Event("submit", { cancelable: true }));
  await sleep(100);
  h.check("settings_form: gespeichertes Theme wird sofort angewandt", h.doc.documentElement.dataset.theme === "light");

  h.check("S-8: nicht konfiguriertes Secret (fritz_pass) -> Feld leer, Loeschen-Button versteckt",
    h.doc.getElementById("st-fritzpass").value === "" && h.doc.getElementById("st-fritzpass-clear").hidden);
  h.check("S-8: konfiguriertes Secret (snmp_community) -> Loeschen-Button sichtbar, Feld leer",
    h.doc.getElementById("st-snmpcommunity").value === "" && !h.doc.getElementById("st-snmpcommunity-clear").hidden);
  h.check("E-9: PVE-Abschnitt vorhanden, Token-Secret nicht konfiguriert -> Loeschen-Button versteckt",
    !!h.doc.getElementById("st-pve") && !!h.doc.getElementById("st-pvetokensecret") && h.doc.getElementById("st-pvetokensecret-clear").hidden);
  h.doc.getElementById("st-snmpcommunity-clear").click();
  await sleep(100);
  const patch = [...h.calls].reverse().find((c) => c.url.includes("/api/settings") && c.method === "PATCH");
  h.check("S-8: Loeschen sendet explizites null (Backend entfernt die Zeile)", !!patch && patch.body.includes('"snmp_community":null'));

  h.check("SF-5: Zustellstatus in den Einstellungen sichtbar",
    h.doc.getElementById("st-notify-status").textContent.includes("fehlgeschlagen"));
  return h.failures;
}

standalone(run);
