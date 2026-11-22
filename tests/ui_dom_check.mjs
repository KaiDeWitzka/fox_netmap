import fs from "node:fs";
import path from "node:path";
import { JSDOM } from "jsdom";

const repo = path.resolve(new URL("..", import.meta.url).pathname);
const html = fs
  .readFileSync(path.join(repo, "app/static/index.html"), "utf8")
  .replace('<script src="/static/vendor/cytoscape.min.js"></script>', "")
  .replace('<script src="/static/i18n.js"></script>', "")
  .replace('<script src="/static/app.js"></script>', "");
const css = fs.readFileSync(path.join(repo, "app/static/styles.css"), "utf8");

const dom = new JSDOM(html, { url: "http://localhost/", runScripts: "dangerously", pretendToBeVisual: true });
const w = dom.window;
const doc = w.document;
const style = doc.createElement("style");
style.textContent = css;
doc.head.appendChild(style);

const calls = [];
const DEVS = [
      {
        mac: "aa:bb:cc:dd:ee:ff", ip: "10.0.0.5", ip6: "fdf1:3afe:ed39::10", hostname: "nas", vendor: "Synology",
        category: "Server/NAS", status: "online", subnet: "10.0.0.0/24", site: "Zuhause", source: "ping+arp,tr064",
        ports_str: "80;443", connected_to: "10.0.0.1", note: "", last_seen: "2026-01-01T10:00:00+00:00",
        port_count: 2, x: null, y: null, connection: "lan",
      },
      {
        mac: "ip:192.168.179.20", ip: "192.168.179.20", hostname: "remote-plug", vendor: "",
        category: "Smart-Home/IoT", status: "offline", subnet: "192.168.179.0/24", site: "Remote", source: "tcp",
        ports_str: "", connected_to: "d8:47:32:8e:ee:06", note: "", last_seen: "2026-01-01T10:00:00+00:00",
        port_count: 0, x: null, y: null, connection: "",
      },
      {
        mac: "d8:47:32:8e:ee:06", ip: "192.168.178.10", hostname: "TL-SG108E-GZ", vendor: "TP-Link",
        category: "Switch", status: "online", subnet: "192.168.178.0/24", site: "Zuhause", source: "ping+arp",
        ports_str: "80", connected_to: "192.168.178.1", note: "", last_seen: "2026-01-01T10:00:00+00:00",
        port_count: 1, x: null, y: null, connection: "lan",
      },
      {
        mac: "aa:bb:cc:00:11:22", ip: "192.168.178.77", hostname: "wlan-tv", vendor: "",
        category: "Smart-Home/IoT", status: "online", subnet: "192.168.178.0/24", site: "Zuhause", source: "tr064",
        ports_str: "", connected_to: "wlan:192.168.178.1", note: "", last_seen: "2026-01-01T10:00:00+00:00",
        port_count: 0, x: null, y: null, connection: "wlan", vpn: 1,
      },
      {
        mac: "76:84:18:83:f1:3c", ip: "", hostname: "PC-76-84-18-83-F1-3C", vendor: "",
        category: "Client", status: "online", subnet: "", site: "", source: "tr064",
        ports_str: "", connected_to: "192.168.178.1", note: "", last_seen: "2026-01-01T10:00:00+00:00",
        port_count: 0, x: null, y: null, connection: "",
      },
];
w.fetch = async (url, opts = {}) => {
  calls.push({ url: String(url), method: opts.method || "GET", body: opts.body || null });
  const json = async () => {
    if (String(url).includes("/api/devices/connect")) return { ok: true, count: JSON.parse(opts.body).macs.length };
    if (String(url).includes("/api/devices")) {
      const m = String(url).match(/status=([^&]+)/);
      return m && m[1] === "online" ? DEVS.filter((d) => d.status === "online") : DEVS;
    }

    if (String(url).includes("/api/categories")) return ["Router", "Switch", "Client"];
    if (String(url).includes("/api/meta")) return { version: "1.6.5", gateway: "192.168.178.1", wan_ip: "79.227.229.246", wan_status: "Connected" };
    if (String(url).includes("/api/sites"))
      return { names: ["Remote", "Zuhause"], map: { "10.0.0.0/24": "Zuhause", "192.168.178.0/24": "Zuhause", "192.168.179.0/24": "Remote" } };
    if (String(url).includes("/api/device/")) {
      const mac = String(url).split("/api/device/")[1];
      if (mac === "66:66:66:66:66:66")
        return {
          mac, ip: "192.168.178.66", hostname: '<img src=x onerror="window.__xss=1">', vendor: "<script>window.__xss=2</script>",
          category: "Client", status: "online", subnet: "192.168.178.0/24", source: "mdns", note: '" autofocus onfocus="window.__xss=3',
          first_seen: "2026-01-01T09:00:00+00:00", last_seen: "2026-01-01T10:00:00+00:00",
          ports: [{ port: 80, proto: "tcp", service: "<b onmouseover=window.__xss=4>http</b>" }],
          connection: "lan", layout: { connected_to: "", connected_manual: 0 }, history: [],
          events: [{ ts: "2026-01-01", type: "new", detail: "<svg onload=window.__xss=5>" }],
        };
      if (mac === "d8:47:32:8e:ee:06")
        return {
          mac, ip: "192.168.178.10", hostname: "TL-SG108E-GZ", vendor: "TP-Link",
          category: "Switch", status: "online", subnet: "192.168.178.0/24", source: "ping+arp", note: "",
          first_seen: "2026-01-01T09:00:00+00:00", last_seen: "2026-01-01T10:00:00+00:00",
          ports: [{ port: 80, proto: "tcp", service: "http" }],
          connection: "lan", layout: { connected_to: "192.168.178.1", connected_manual: 0 }, history: [], events: [],
        };
      if (mac === "aa:bb:cc:00:11:22")
        return {
          mac, ip: "192.168.178.77", hostname: "wlan-tv", vendor: "",
          category: "Smart-Home/IoT", status: "online", subnet: "192.168.178.0/24", source: "tr064", note: "",
          first_seen: "2026-01-01T09:00:00+00:00", last_seen: "2026-01-01T10:00:00+00:00",
          ports: [], vpn: 1, connection: "wlan", layout: { connected_to: "wlan:192.168.178.1", connected_manual: 0 }, history: [], events: [],
        };
      return {
        mac: "aa:bb:cc:dd:ee:ff", ip: "10.0.0.5", ip6: "fdf1:3afe:ed39::10", hostname: "nas", vendor: "Synology",
        category: "Server/NAS", status: "online", subnet: "10.0.0.0/24", site: "Zuhause", source: "ping+arp,tr064", note: "",
        first_seen: "2026-01-01T09:00:00+00:00", last_seen: "2026-01-01T10:00:00+00:00",
        ports: [{ port: 80, proto: "tcp", service: "http" }, { port: 443, proto: "tcp", service: "https" }],
        connection: "lan", layout: { connected_to: "192.168.178.1", connected_manual: 0 }, history: [], events: [],
      };
    }
    if (String(url).includes("/api/settings"))
      return {
        theme: "dark",
        scan_interval: 900,
        subnets: "",
        port_top: 1000,
        history_hours: 720,
        device_retention_days: 30,
        snmp_enabled: true,
        snmp_switches: "",
        auth_enabled: true,
        auto_export: false,
        auto_export_interval_hours: 24,
        mdns_enabled: true,
        oui_online_enabled: true,
        oui_online_max: 10,
        oui_online_url: "",
        alarm_whitelist: "",
        sites: "",
        vpn_pool: "off",
        lang: "de",
        scan_timeout: 1.0,
        ports: "",
        fritz_url: "",
        fritz_urls: "",
        fritz_user: "",
        snmp_community: "public",
        notify_webhook: "",
        notify_gotify: "",
        notify_ntfy: "",
        auto_export_dir: "exports",
      };
    if (String(url).includes("/api/tokens")) return [];
    if (String(url).includes("/api/logs"))
      return {
        file: "/data/netmap.log",
        total: 2,
        returned: 2,
        lines: ["2026-01-01 10:00:00 INFO fox_netmap: Scan fertig: 3 Geraete, 0 neu", "2026-01-01 10:00:01 ERROR fox_netmap scanner: Scan-Fehler: <b>boom</b>"],
      };
    if (String(url).includes("/api/scan")) return { last_scan: null, next_scan: null, scanning: 0 };
    return {};
  };
  return { ok: true, status: 200, json, cookies: {}, blob: async () => new w.Blob(["%PDF-1.4 mock"], { type: "application/pdf" }) };
};
let cyInstance = null;
w.cytoscape = (opts) => {
  cyInstance = {
    _els: [],
    _style: (opts && opts.style) || [],
    _zoom: 1,
    zoom() { return this._zoom; },
    style() {
      const self = this;
      return { selector() { return { style(k, v) { if (k === "label") self._labelStyle = v; return { update() {} }; } }; } };
    },
    _handlers: {},
    on(ev, sel, fn) {
      if (typeof sel === "function") this._handlers[ev] = sel;
      else this._handlers[ev + ":" + sel] = fn;
    },
    elements() {
      const self = this;
      return {
        remove() {},
        removeClass(c) { self._removedClass = c; },
        addClass() {},
        not(nhood) { return { addClass(c) { self._dimmedClass = c; } }; },
      };
    },
    add(els) { this._els = els; },
    layout(opts) { this._lastLayout = opts.name; this._lastLayoutOpts = opts; return { run() {} }; },
    fit() { this._fitCalls = (this._fitCalls || 0) + 1; },
    resize() {},
    nodes() { return { removeClass() {} }; },
    edges() { return { removeClass() {}, filter: () => ({ addClass() {} }) }; },
    getElementById: () => ({ addClass() {}, removeClass() {} }),
    png: () => "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
  };
  return cyInstance;
};
w.print = () => calls.push({ url: "window.print", method: "CALL" });
w.URL.createObjectURL = () => "blob:mock-pdf";
w.URL.revokeObjectURL = () => {};

w.eval(
  fs.readFileSync(path.join(repo, "app/static/i18n.js"), "utf8") +
    "\n;\n" +
    fs.readFileSync(path.join(repo, "app/static/icons.js"), "utf8") +
    "\n;\n" +
    fs.readFileSync(path.join(repo, "app/static/app.js"), "utf8")
);
await new Promise((r) => setTimeout(r, 200));

let failures = 0;
function check(name, cond) {
  console.log((cond ? "PASS" : "FAIL") + "  " + name);
  if (!cond) failures++;
}
const vis = (el) => el && w.getComputedStyle(el).display !== "none";
const $ = (s) => doc.querySelector(s);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

check("init: Karte sichtbar", vis($("#view-map")));
check("init: Tabelle versteckt", !vis($("#view-table")));
check("init: Sidebar zu", !vis($("#detail")));

// Header zweizeilig nach Themenschwerpunkten gruppiert (vNext)
check("Header: zwei Zeilen (.hdr-row)", doc.querySelectorAll("header .hdr-row").length === 2);
check(
  "Header: 4 Themengruppen mit sichtbarem Label",
  doc.querySelectorAll("header .hdr-group").length === 4 &&
    [...doc.querySelectorAll("header .hdr-label")].every((l) => l.textContent.trim().length > 0)
);
check(
  "Header: Gruppen in den Zeilen (Ansicht | Karte, Aktionen, App)",
  doc.querySelectorAll("header .hdr-row")[0].querySelectorAll(".hdr-group").length === 1 &&
    doc.querySelectorAll("header .hdr-row")[1].querySelectorAll(".hdr-group").length === 3
);
check(
  "Header: Einstellungen-Button mit Gear-Icon + Label deutlich sichtbar",
  !!$("#btn-settings .gear") && !!$("#btn-settings [data-i18n='tab.settings']") && $("#btn-settings").classList.contains("hdr-settings")
);
check(
  "Header: alle IDs stabil geblieben",
  ["nav", "search", "filter-category", "filter-status", "filter-site", "btn-online", "scan-status", "chk-groups", "layout-select", "btn-layout-reset", "btn-scan", "btn-pdf", "pdf-orientation", "btn-print", "btn-theme", "lang-select", "btn-settings", "btn-logout"].every((id) => !!$("#" + id))
);
check("Icon: Favicon-Link in index.html + Logo im Header", html.includes('rel="icon"') && html.includes("/static/favicon.svg") && !!$("header h1 .hdr-logo"));
check(
  "Icon: favicon.svg existiert und enthaelt Fuchs-Kopf + Netzwerk",
  (() => {
    const svg = fs.readFileSync(path.join(repo, "app/static/favicon.svg"), "utf8");
    return svg.includes("<svg") && svg.includes("#f97316") && svg.includes("circle") && svg.includes("M12 6");
  })()
);

$("#nav [data-view='table']").click();
check("Tabelle: Tabellenansicht sichtbar", vis($("#view-table")));
check("Tabelle: Karte versteckt", !vis($("#view-map")));

$("#btn-settings").click();
await sleep(50);
check("Tabelle + ⚙: Sidebar sichtbar", vis($("#detail")));
check("Tabelle + ⚙: Settings-Tab aktiv", $("#settings-content").hidden === false && $("#detail-content").hidden === true);
check(
  "Settings: Formular in 7 Themenschwerpunkten gruppiert (fieldset+legend)",
  doc.querySelectorAll("#settings-form fieldset.st-group").length === 7 &&
    [...doc.querySelectorAll("#settings-form fieldset.st-group legend")].every((l) => l.textContent.trim().length > 0)
);
check(
  "Settings: alle Eingabe-IDs stabil geblieben",
  ["st-theme", "st-lang", "st-auth", "st-interval", "st-subnets", "st-scantimeout", "st-porttop", "st-ports", "st-history", "st-retention", "st-eventretention", "st-mdns", "st-fritzurl", "st-fritzurls", "st-fritzuser", "st-fritzpass", "st-snmp", "st-switches", "st-snmpcommunity", "st-notifywebhook", "st-notifygotify", "st-notifyntfy", "st-whitelist", "st-autoexport", "st-autoexport-interval", "st-autoexportdir", "st-sites", "st-vpnpool", "st-ouionline", "st-ouimax", "st-ouiurl"].every((id) => !!$("#" + id))
);

$("#settings-form").dispatchEvent(new w.Event("submit", { cancelable: true }));
await sleep(50);
check("Tabelle: Settings speichern -> PATCH /api/settings", calls.some((c) => c.url.includes("/api/settings") && c.method === "PATCH"));

$("#tab-detail").click();
check("Tab Details: Detail-Content sichtbar", $("#detail-content").hidden === false && $("#settings-content").hidden === true);

$("#btn-close-detail").click();
check("✕: Sidebar wieder zu", !vis($("#detail")));

$("#nav [data-view='map']").click();
check("Karte: Kartenansicht sichtbar", vis($("#view-map")) && !vis($("#view-table")));

$("#btn-settings").click();
await sleep(50);
check("Karte + ⚙: Sidebar sichtbar", vis($("#detail")));
$("#btn-close-detail").click();
check("Karte + ✕: Sidebar zu", !vis($("#detail")));

const scanPostsBefore = calls.filter((c) => c.url.includes("/api/scan") && c.method === "POST").length;
$("#btn-scan").click();
await sleep(50);
check("Beide Sichten: Jetzt scannen -> POST /api/scan", calls.filter((c) => c.url.includes("/api/scan") && c.method === "POST").length === scanPostsBefore + 1);

$("#btn-theme").click();
check("Theme-Toggle: dark -> light", doc.documentElement.dataset.theme === "light");
$("#btn-theme").click();
check("Theme-Toggle: light -> dark", doc.documentElement.dataset.theme === "dark");

$("#btn-print").click();
await sleep(250);
check("Drucken: wechselt auf Tabelle + window.print", vis($("#view-table")) && calls.some((c) => c.url === "window.print"));

check("Header: Export-Link JSON", doc.querySelector("a[href='/api/export/json']") !== null);
check("Header: Export-Link CSV", doc.querySelector("a[href*='/api/export/csv']") !== null);
check("Header: PDF-Button vorhanden", !!$("#btn-pdf"));
const origAnchorClick = w.HTMLAnchorElement.prototype.click;
w.HTMLAnchorElement.prototype.click = function () {};
$("#btn-pdf").click();
await sleep(60);
w.HTMLAnchorElement.prototype.click = origAnchorClick;
const pdfCall = [...calls].reverse().find((c) => c.url.includes("/api/export/pdf"));
check(
  "Header: PDF-Button -> POST /api/export/pdf mit Karten-Snapshot (data:image/png)",
  !!pdfCall && pdfCall.method === "POST" && !!pdfCall.body && pdfCall.body.includes('"image":"data:image/png;base64,')
);

check(
  "Header: PDF-Orientierung-Select vorhanden (2 Optionen, default hoch)",
  (() => { const el = $("#pdf-orientation"); return !!el && el.options.length === 2 && el.value === "portrait"; })()
);
$("#pdf-orientation").value = "landscape";
$("#pdf-orientation").dispatchEvent(new w.Event("change"));
check("Header: Orientierung wird persistiert (localStorage fox_pdf_orientation)", w.localStorage.getItem("fox_pdf_orientation") === "landscape");
const origAnchorClick2 = w.HTMLAnchorElement.prototype.click;
w.HTMLAnchorElement.prototype.click = function () {};
$("#btn-pdf").click();
await sleep(60);
w.HTMLAnchorElement.prototype.click = origAnchorClick2;
const pdfCall2 = [...calls].reverse().find((c) => c.url.includes("/api/export/pdf"));
check("Header: PDF-POST enthaelt orientation=landscape", !!pdfCall2 && !!pdfCall2.body && pdfCall2.body.includes('"orientation":"landscape"'));
check("Header: Suche + 2 Filter vorhanden", $("#search") && $("#filter-category") && $("#filter-status"));

$("#search").value = "nas";
$("#search").dispatchEvent(new w.Event("input"));
await sleep(400);
check("Suche: GET /api/devices?q=nas", calls.some((c) => c.url.includes("/api/devices") && c.url.includes("q=nas")));

check("Standorte: /api/sites geladen + Filter befuellt", calls.some((c) => c.url.includes("/api/sites")) && $("#filter-site") && $("#filter-site").options.length === 3);
check("Standorte: Spalte 'Standort' in Tabelle", !!doc.querySelector('#device-table th[data-key="site"]'));
$("#filter-site").value = "Remote";
$("#filter-site").dispatchEvent(new w.Event("change"));
await sleep(80);
check("Standorte: Filter -> GET /api/devices mit site=Remote", [...calls].reverse().some((c) => c.url.includes("/api/devices") && c.url.includes("site=Remote")));
$("#filter-site").value = "";
$("#filter-site").dispatchEvent(new w.Event("change"));
await sleep(80);

check("i18n: Sprachwahl mit 6 Sprachen befuellt", !!$("#lang-select") && $("#lang-select").options.length === 6);
$("#lang-select").value = "en";
$("#lang-select").dispatchEvent(new w.Event("change"));
await sleep(60);
check(
  "i18n: Wechsel auf en -> Nav 'Map', Scan 'Scan now', Spalte 'Vendor'",
  $("#nav [data-view='map']").textContent === "Map" &&
    $("#btn-scan").textContent === "Scan now" &&
    [...doc.querySelectorAll("#device-table thead th")].some((th) => th.dataset.key === "vendor" && th.textContent.includes("Vendor"))
);
check(
  "i18n: Wechsel auf en -> PATCH /api/settings lang=en + localStorage fox_lang",
  [...calls].reverse().some((c) => c.url.includes("/api/settings") && c.method === "PATCH" && c.body.includes('"lang":"en"')) &&
    w.localStorage.getItem("fox_lang") === "en"
);
$("#lang-select").value = "de";
$("#lang-select").dispatchEvent(new w.Event("change"));
await sleep(60);
check("i18n: Zurueck auf de -> Nav 'Karte' wiederhergestellt", $("#nav [data-view='map']").textContent === "Karte" && w.localStorage.getItem("fox_lang") === "de");

const thKeys = () => [...doc.querySelectorAll("#device-table thead th[data-key]")].map((t) => t.dataset.key);
const beforeCols = thKeys();
check("Spalten: draggable-Header", doc.querySelectorAll("#device-table thead th[draggable='true']").length === beforeCols.length);
const dt = { data: {}, setData(k, v) { this.data[k] = v; }, getData(k) { return this.data[k]; } };
const th0 = doc.querySelector("#device-table thead th[data-key]");
const evDrag = new w.Event("dragstart", { bubbles: true });
evDrag.dataTransfer = dt;
th0.dispatchEvent(evDrag);
const th3 = doc.querySelectorAll("#device-table thead th[data-key]")[3];
const evDrop = new w.Event("drop", { bubbles: true, cancelable: true });
evDrop.dataTransfer = dt;
th3.dispatchEvent(evDrop);
const afterCols = thKeys();
check("Spalten-Drag: Reihenfolge geaendert (th0 vor th3 eingefuegt)", afterCols[0] === beforeCols[1] && afterCols[2] === beforeCols[0]);
const savedCols = JSON.parse(w.localStorage.getItem("fox_table_cols") || "null");
check("Spalten-Drag: localStorage persistiert", Array.isArray(savedCols) && savedCols[2] === beforeCols[0]);

const bodyRow = doc.querySelector("#device-table tbody tr");
const bodyCells = bodyRow ? [...bodyRow.children].filter((c) => !c.classList.contains("sel-col")) : [];
check(
  "Spalten-Drag: Body-Zellen folgen der neuen Reihenfolge (ip, mac, hostname, vendor, …)",
  !!bodyRow && bodyCells[0].textContent.includes("10.0.0.5") && bodyCells[2].textContent.startsWith("nas")
);
check("Quelle-Spalte: Header + Zelle vorhanden", !!doc.querySelector('#device-table th[data-key="source"]') && bodyRow.textContent.includes("ping+arp,tr064"));
check("IPv6-Spalte: Header th[data-key=ip6] mit Label", !!doc.querySelector('#device-table th[data-key="ip6"]') && doc.querySelector('#device-table th[data-key="ip6"]').textContent.includes("IPv6"));
check(
  "IPv6-Spalte: nas-Zeile zeigt fdf1:3afe:ed39::10, andere Zeilen Strich",
  (() => {
    const rows = [...doc.querySelectorAll("#device-table tbody tr")];
    const nas = rows.find((r) => r.textContent.includes("nas"));
    const idx = [...doc.querySelectorAll("#device-table thead th")].findIndex((t) => t.dataset.key === "ip6");
    const other = rows.find((r) => !r.textContent.includes("nas"));
    return !!nas && nas.children[idx].textContent.trim() === "fdf1:3afe:ed39::10" && !!other && other.children[idx].textContent.trim() === "–";
  })()
);

const resizer = doc.querySelector("#device-table thead th .resizer");
const rKey = resizer.closest("th").dataset.key;
resizer.dispatchEvent(new w.MouseEvent("mousedown", { bubbles: true, clientX: 100 }));
doc.dispatchEvent(new w.MouseEvent("mousemove", { bubbles: true, clientX: 170 }));
doc.dispatchEvent(new w.MouseEvent("mouseup", { bubbles: true, clientX: 170 }));
await sleep(20);
const savedWidths = JSON.parse(w.localStorage.getItem("fox_table_widths") || "{}");
const colEl = doc.querySelector(`#device-table colgroup col[data-key="${rKey}"]`);
check("Spalten-Resize: Breite >= 60px in localStorage gespeichert", typeof savedWidths[rKey] === "number" && savedWidths[rKey] >= 60);
check("Spalten-Resize: col-Breite live gesetzt", !!colEl && colEl.style.width.endsWith("px"));

const ipThIdx = [...doc.querySelectorAll("#device-table thead th")].findIndex((t) => t.dataset.key === "ip");
const ipCell = doc.querySelector("#device-table tbody tr").children[ipThIdx];
check("Web-Links: IP-Zelle bleibt pur (keine Links)", ipCell.querySelector("a") === null && ipCell.textContent.trim() === "10.0.0.5");

const hnThIdx = [...doc.querySelectorAll("#device-table thead th")].findIndex((t) => t.dataset.key === "hostname");
const hnCell = doc.querySelector("#device-table tbody tr").children[hnThIdx];
check(
  "Web-Links: Hostname-Zelle mit (http, https) als Links",
  hnCell.querySelector('a[href="http://10.0.0.5"]') !== null &&
    hnCell.querySelector('a[href="https://10.0.0.5"]') !== null &&
    hnCell.textContent.includes("(http, https)")
);
const webLinksSrc = fs.readFileSync(path.join(repo, "app/static/app.js"), "utf8").match(/const WEB_PORTS[\s\S]*?\nfunction webLinks[\s\S]*?\n\}/)[0];
const v6links = w.eval(webLinksSrc + "\n;webLinks({ ip: '2003:db8::5', ports_str: '80;8080;443;8443' })");
check(
  "IPv6: webLinks mit Klammern ([2003:db8::5], :8080/:8443 mit Port)",
  v6links.some((l) => l.url === "http://[2003:db8::5]") &&
    v6links.some((l) => l.url === "http://[2003:db8::5]:8080") &&
    v6links.some((l) => l.url === "https://[2003:db8::5]") &&
    v6links.some((l) => l.url === "https://[2003:db8::5]:8443")
);

doc.querySelector("#device-table tbody tr").dispatchEvent(new w.MouseEvent("click", { bubbles: true }));
await sleep(80);
check(
  "Web-Links: Detail-Panel Hostname mit beiden Links, genau 2 Links gesamt (IP pur)",
  $("#detail-content").innerHTML.includes('href="http://10.0.0.5"') &&
    $("#detail-content").innerHTML.includes('href="https://10.0.0.5"') &&
    doc.querySelectorAll("#detail-content a").length === 2
);
check("Web-Links: Sidebar oeffnet bei Zeilenklick", vis($("#detail")));
check("Detail: IPv6-Zeile mit Adresse aus NDP-Match", $("#detail-content").textContent.includes("fdf1:3afe:ed39::10"));


check("Header: Version aus /api/meta sichtbar (v1.6.5)", $("#hdr-version") && $("#hdr-version").textContent === "v1.6.5");
check("Karte: virtuelles WLAN-Node wird gerendert", !!cyInstance && cyInstance._els.some((e) => e.data && e.data.id === "wlan:192.168.178.1" && e.data.virtual));
check(
  "Karte: Internet-Knoten mit WAN-IP + Kante zum Gateway",
  !!cyInstance &&
    cyInstance._els.some((e) => e.data && e.data.id === "internet" && e.data.label.includes("79.227.229.246")) &&
    cyInstance._els.some((e) => e.data && e.data.source === "internet")
);
const devNodes = cyInstance._els.filter((e) => e.data && !e.data.virtual && e.position);
check(
  "Karte: Ring-Initialpositionen (nicht alle 0,0, verteilt)",
  devNodes.length >= 3 && new Set(devNodes.slice(0, 4).map((e) => `${Math.round(e.position.x)},${Math.round(e.position.y)}`)).size > 1
);
// Knotendesign v1.6.1
const EMOJI = /[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/u;
check("Design: kein Emoji in Knoten-Labels", cyInstance._els.every((e) => !e.data || !e.data.label || !EMOJI.test(e.data.label)));
check("Design: Geraete-Label zweizeilig (Name, IP · Kategorie)", devNodes.length > 0 && devNodes.every((e) => e.data.label.split("\n").length === 2) && devNodes.some((e) => e.data.label === "nas\n10.0.0.5 · Server/NAS"));
check("Design: Internet-Label 'Internet' + 'WAN <IP>'", cyInstance._els.some((e) => e.data && e.data.id === "internet" && e.data.label === "Internet\nWAN 79.227.229.246"));
check("Design: jedes Geraet hat ein Symbol, Netzknoten 40 px, Endgeraete 34 px",
  devNodes.every((e) => !!e.data.icon) &&
  cyInstance._els.some((e) => e.data && e.data.id === "d8:47:32:8e:ee:06" && e.data.size === 40 && e.data.icon === "network") &&
  cyInstance._els.some((e) => e.data && e.data.id === "aa:bb:cc:dd:ee:ff" && e.data.size === 34 && e.data.icon === "server"));
check("Design: jede Kategorie hat ein eigenes Symbol (nur Unbekannt = Fragezeichen)",
  ["Router", "Repeater/AP", "Switch", "Server/NAS", "Client", "Mobilgerät", "Multimedia", "Drucker", "Smart-Home/IoT", "Internet"].every((c) => w.eval(`iconKeyFor(${JSON.stringify(c)})`) !== "unknown") &&
  w.eval(`iconKeyFor("Unbekannt")`) === "unknown");
check("Design: Feinsymbole Notebook/Tablet/Konsole", w.eval(`iconKeyFor("Client", "mdns:MacBookPro18,1")`) === "laptop" && w.eval(`iconKeyFor("Mobilgerät", "mdns:iPad13,4")`) === "tablet" && w.eval(`iconKeyFor("Multimedia", "", "PS5-123")`) === "gamepad");
const sampleUri = w.eval(`iconUri("router", "#e2e8f0")`);
check("Design: Symbol als lokale data:-URI (CSP img-src data:), mit Zwischenspeicher", sampleUri.startsWith("data:image/svg+xml") && decodeURIComponent(sampleUri).includes("<path") && w.eval(`iconUri("router", "#e2e8f0") === iconUri("router", "#e2e8f0")`));
check("Design: Wurzelring nur am Gateway", (() => {
  const roots = cyInstance._els.filter((e) => e.data && e.data.root);
  return roots.length === 1 && roots[0].data.id === "192.168.178.1";
})());
const nodeStyle = cyInstance._style.find((x) => x.selector === "node");
const edgeStyle = cyInstance._style.find((x) => x.selector === "edge");
const offStyle = cyInstance._style.find((x) => x.selector === "node[status='offline']");
check("Design: neutraler Koerper, gerade Kanten 1,5 px, Deckkraft 0,8", !!nodeStyle && nodeStyle.style["background-color"] === "#1e293b" && nodeStyle.style["border-width"] === 1.5 && !!edgeStyle && edgeStyle.style.width === 1.5 && edgeStyle.style.opacity === 0.8 && edgeStyle.style["curve-style"] === "straight");
check("Design: WLAN gestrichelt, Powerline gepunktet, Standort-Kanten schwach", cyInstance._style.some((x) => x.selector === "edge[conn='wlan']" && x.style["line-style"] === "dashed") && cyInstance._style.some((x) => x.selector === "edge[conn='plc']" && x.style["line-style"] === "dotted") && cyInstance._style.some((x) => x.selector === "edge[?cross]" && x.style.opacity === 0.35));
check("A11y: Offline blendet nur den Koerper ab (keine Gesamt-Deckkraft), gestrichelt", !!offStyle && offStyle.style.opacity === undefined && offStyle.style["background-opacity"] === 0.45 && offStyle.style["border-style"] === "dashed");
check("A11y: Labels ab Zoom 0,5 ausgeblendet (min-zoomed-font-size)", nodeStyle.style["min-zoomed-font-size"] === 6 && nodeStyle.style["font-size"] === 11);
// Kontrast nach WCAG 2.2 (relative Luminanz)
const lum = (hex) => { const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4)); return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]; };
const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
for (const th of ["dark", "light"]) {
  const P = JSON.parse(w.eval(`JSON.stringify(mapPalette(${JSON.stringify(th)}))`));
  const texts = [["text", P.text], ["textOff", P.textOff], ["frameText", P.frameText]];
  const marks = [["border", P.border], ["root", P.root], ["edge", P.edge], ["hl", P.hl], ["sel", P.sel], ["repeater", P.repeater]];
  const badT = texts.filter(([, c]) => ratio(c, P.bg) < 4.5).map(([k, c]) => `${k} ${ratio(c, P.bg).toFixed(2)}`);
  const badM = marks.filter(([, c]) => ratio(c, P.bg) < 3).map(([k, c]) => `${k} ${ratio(c, P.bg).toFixed(2)}`);
  const iconOk = ratio(P.icon, P.body) >= 3;
  check(`A11y Kontrast ${th}: Text >= 4,5:1, Raender/Linien/Symbole >= 3:1${badT.length + badM.length ? " – " + [...badT, ...badM].join(", ") : ""}`, badT.length === 0 && badM.length === 0 && iconOk);
}
check("Legende: einklappbar (details/summary) mit Symbol + Text je Kategorie und Linienarten",
  !!$("#map-legend summary") && doc.querySelectorAll("#legend-list li img[alt='']").length === 4 && $("#legend-list").textContent.includes("Switch") &&
  [...doc.querySelectorAll("#legend-list li")].every((li) => li.textContent.trim().length > 0) &&
  ["LAN", "WLAN", "Powerline"].every((k) => $("#legend-list").textContent.includes(k)));
cyInstance._zoom = 0.5;
cyInstance._handlers["zoom"]();
check("Karte: Zoom < 0.85 -> Label-Funktion (nur Hubs)", typeof cyInstance._labelStyle === "function" && cyInstance._labelStyle({ data: (k) => (k === "hub" ? true : "HubLabel") }) === "HubLabel" && cyInstance._labelStyle({ data: (k) => (k === "hub" ? false : "ClientLabel") }) === "");
cyInstance._zoom = 2;
cyInstance._handlers["zoom"]();
check("Karte: Zoom >= 0.85 -> alle Labels sichtbar", cyInstance._labelStyle === "data(label)");
cyInstance._zoom = 1;
check("Karte: Hub-Flags (Switch/Internet hub, Client nicht)", cyInstance._els.some((e) => e.data && e.data.id === "d8:47:32:8e:ee:06" && e.data.hub === true) && cyInstance._els.some((e) => e.data && e.data.id === "internet" && e.data.hub === true) && cyInstance._els.some((e) => e.data && e.data.id === "aa:bb:cc:00:11:22" && !e.data.hub));
check("Karte: Auto-Gruppe aus bei <=25 Geraeten; shouldAutoGroup(4)=false, (30)=true", $("#chk-groups").checked === false && w.eval("shouldAutoGroup(4)") === false && w.eval("shouldAutoGroup(30)") === true);
check(
  "Karte: Kanten gerendert + virtueller Gateway-Knoten (Gateway nicht in Geraeteliste)",
  !!cyInstance &&
    cyInstance._els.some((e) => e.data && e.data.source && e.data.target) &&
    cyInstance._els.some((e) => e.data && e.data.id === "192.168.178.1" && e.data.virtual && e.data.label.includes("Gateway"))
);

check(
  "Karte: Kanten zeigen Eltern -> Kind (Gateway -> Switch, Internet -> Gateway)",
  cyInstance._els.some((e) => e.data && e.data.source === "192.168.178.1" && e.data.target === "d8:47:32:8e:ee:06") &&
    cyInstance._els.some((e) => e.data && e.data.source === "internet" && e.data.target === "192.168.178.1")
);
check("Karte: Auto-Layout ohne gespeicherte Positionen = Baum (preset)", cyInstance._lastLayout === "preset");
{
  // v1.5.4: steht das Gateway als Geraet in der Liste, wird kein virtueller Gateway-Knoten erzeugt
  const fritz = { mac: "3c:a6:2f:00:00:01", ip: "192.168.178.1", hostname: "fritz.box", category: "Router", status: "online", subnet: "192.168.178.0/24", connected_to: "" };
  DEVS.push(fritz);
  await w.eval("loadDevices()");
  const els = cyInstance._els;
  DEVS.pop();
  check(
    "Bugfix v1.5.4: Gateway-IP wird auf das Router-Geraet abgebildet (kein doppelter Gateway-Knoten)",
    !els.some((e) => e.data && e.data.id === "192.168.178.1") &&
      els.some((e) => e.data && e.data.source === "3c:a6:2f:00:00:01" && e.data.target === "d8:47:32:8e:ee:06") &&
      els.some((e) => e.data && e.data.source === "internet" && e.data.target === "3c:a6:2f:00:00:01")
  );
  const pos = w.eval("computeTreePositions")(els);
  const y = (id) => pos[id] && pos[id].y;
  check(
    "Baum: Internet oben, Router darunter, darunter Switch und WLAN, WLAN-Geraet unter WLAN",
    y("internet") < y("3c:a6:2f:00:00:01") && y("3c:a6:2f:00:00:01") < y("d8:47:32:8e:ee:06") && y("3c:a6:2f:00:00:01") < y("wlan:192.168.178.1") && y("wlan:192.168.178.1") < y("aa:bb:cc:00:11:22")
  );
  check("Baum: jeder Knoten hat eine Position", els.filter((e) => e.data && !e.data.source && !e.data.subnet).every((e) => pos[e.data.id]));
  await w.eval("loadDevices()");
}
{
  // 40 Endgeraete an einem Router: Raster statt einer Zeile, keine zwei Knoten auf derselben Position
  const els = [{ data: { id: "r", hub: true } }];
  for (let i = 0; i < 40; i++) {
    els.push({ data: { id: "c" + i, name: "c" + i } });
    els.push({ data: { source: "r", target: "c" + i } });
  }
  els.push({ data: { id: "lonely", name: "lonely" } });
  const pos = w.eval("computeTreePositions")(els);
  const xs = Object.values(pos).map((p) => p.x);
  const keys = new Set(Object.values(pos).map((p) => p.x + "," + p.y));
  check(
    "Baum: 40 Endgeraete im Raster (Breite <= 8 Spalten), keine Ueberlagerung, ungebundene Knoten darunter",
    Math.max(...xs) - Math.min(...xs) <= 8 * 170 && keys.size === Object.keys(pos).length && pos.lonely.y > pos.c39.y
  );
  const cyc = [{ data: { id: "a" } }, { data: { id: "b" } }, { data: { source: "a", target: "b" } }, { data: { source: "b", target: "a" } }];
  const pc = w.eval("computeTreePositions")(cyc);
  check("Baum: Zyklus ohne Endlosschleife, beide Knoten positioniert", !!pc.a && !!pc.b);
}
check(
  "Kategorien v1.6.0: Begruendung lesbar, Repeater ist Netzknoten",
  w.eval(`reasonText({ category_reason: "host:iphone" })`) === "Hostname „iphone“" &&
    w.eval(`reasonText({ category_reason: "port:62078" })`) === "offener Port 62078" &&
    w.eval(`reasonText({ category_reason: "mesh:slave" })`) === "FRITZ!Box-Mesh (Repeater)" &&
    w.eval(`reasonText({ category_reason: "host:x", category_override: "Client" })`) === "manuell gesetzt" &&
    w.eval(`reasonText({ category_reason: "" })`) === "–" &&
    w.eval(`isNetCategory("Repeater/AP")`) === true && w.eval(`isNetCategory("Client")`) === false
);
check(
  "Mesh: Anschluss lesbar (LAN 1, 5 GHz, 2,4 GHz, leer)",
  w.eval(`portLabel("LAN:1")`) === "LAN 1" && w.eval(`portLabel("AP:5G:0")`) === "5 GHz" &&
    w.eval(`portLabel("UPLINK:2G:0")`) === "2,4 GHz" && w.eval(`portLabel("")`) === "" &&
    w.eval(`connectionText({ connection: "wlan", link_port: "AP:5G:0" })`) === "WLAN · 5 GHz" &&
    w.eval(`connectionText({ connection: "", link_port: "" })`) === "–"
);
check("parentId: Hostname wird auf Geraet abgebildet", w.eval(`parentId({ connected_to: "TL-SG108E-GZ" })`) === "d8:47:32:8e:ee:06");
check("parentId: unbekannte MAC ergibt keinen virtuellen Gateway-Knoten", w.eval(`parentId({ connected_to: "de:ad:be:ef:00:01" })`) === null);

const parentSel = $("#ed-parent");
check("Detail: Verbunden-mit-Select mit Switch-Option", !!parentSel && parentSel.innerHTML.includes("TL-SG108E-GZ"));
if (parentSel) {
  parentSel.value = "d8:47:32:8e:ee:06";
  $("#ed-parent-save").click();
  await sleep(60);
  const lastPatch = [...calls].reverse().find((c) => c.url.includes("/api/device/") && c.method === "PATCH" && c.body && c.body.includes("connected_to"));
  check("Detail: Parent speichern -> PATCH mit connected_to=Switch-MAC", !!lastPatch && lastPatch.body.includes("d8:47:32:8e:ee:06"));
}

$("#nav [data-view='log']").click();
await sleep(100);
check("Log: Log-Ansicht sichtbar, Karte versteckt", vis($("#view-log")) && !vis($("#view-map")));
check("Log: GET /api/logs wurde abgesetzt", calls.some((c) => c.url.includes("/api/logs")));
check("Log: Inhalt gerendert (ERROR-Zeile sichtbar)", $("#log-view").textContent.includes("Scan-Fehler"));
check("Log: Level-Farben als Spans (lv-INFO + lv-ERROR)", !!$("#log-view .lv-INFO") && !!$("#log-view .lv-ERROR"));
check("Log: HTML in Logzeilen wird escaped (kein <b>-Element)", $("#log-view").querySelector("b") === null && $("#log-view").textContent.includes("<b>boom</b>"));

const logCallsBefore = calls.filter((c) => c.url.includes("/api/logs")).length;
$("#btn-log-refresh").click();
await sleep(50);
check("Log: Aktualisieren -> erneuter GET /api/logs", calls.filter((c) => c.url.includes("/api/logs")).length === logCallsBefore + 1);

$("#log-level").value = "ERROR";
$("#log-level").dispatchEvent(new w.Event("change"));
await sleep(50);
check("Log: Level-Filter -> GET /api/logs?...level=ERROR", calls.some((c) => c.url.includes("/api/logs") && c.url.includes("level=ERROR")));

const logCallCount = () => calls.filter((c) => c.url.includes("/api/logs")).length;
const logCallsBeforeAuto = logCallCount();
await sleep(5600);
check("Log: Auto-Refresh aktualisiert automatisch, solange Log-Ansicht sichtbar", logCallCount() > logCallsBeforeAuto);

$("#nav [data-view='map']").click();
await sleep(50);
$("#btn-settings").click();
await sleep(50);
const patchCount = () => calls.filter((c) => c.url.includes("/api/settings") && c.method === "PATCH").length;
const patchBase = patchCount();
$("#st-interval").value = "5";
$("#settings-form").dispatchEvent(new w.Event("submit", { cancelable: true }));
await sleep(50);
check("Settings: Intervall 5 -> kein PATCH, Fehlermeldung sichtbar", patchCount() === patchBase && $("#settings-msg").textContent.includes("Intervall"));
$("#st-subnets").value = "keine-ip";
$("#settings-form").dispatchEvent(new w.Event("submit", { cancelable: true }));
await sleep(50);
check("Settings: Subnetz 'keine-ip' -> kein PATCH, Fehlermeldung", patchCount() === patchBase && $("#settings-msg").textContent.includes("Subnetz"));
$("#st-interval").value = "600";
$("#st-subnets").value = "";
$("#settings-form").dispatchEvent(new w.Event("submit", { cancelable: true }));
await sleep(50);
check("Settings: gueltige Werte -> PATCH /api/settings", patchCount() === patchBase + 1);

const patchBase2 = patchCount();
$("#st-retention").value = "-1";
$("#settings-form").dispatchEvent(new w.Event("submit", { cancelable: true }));
await sleep(50);
check("Settings: Retention -1 -> kein PATCH, Fehlermeldung", patchCount() === patchBase2 && $("#settings-msg").textContent.includes("Retention"));
$("#st-retention").value = "14";
$("#settings-form").dispatchEvent(new w.Event("submit", { cancelable: true }));
await sleep(50);
check("Settings: Retention 14 -> PATCH", patchCount() === patchBase2 + 1);

check("Settings: Felder Whitelist/Auto-Export-Intervall/mDNS vorhanden", !!$("#st-whitelist") && !!$("#st-autoexport-interval") && !!$("#st-mdns"));
check("Settings: OUI-Online-Felder vorhanden (Checkbox/Max/URL)", !!$("#st-ouionline") && !!$("#st-ouimax") && !!$("#st-ouiurl"));
const patchBase8 = patchCount();
$("#st-ouimax").value = "-1";
$("#settings-form").dispatchEvent(new w.Event("submit", { cancelable: true }));
await sleep(50);
check("Settings: oui_online_max=-1 -> kein PATCH, Fehlermeldung", patchCount() === patchBase8 && $("#settings-msg").textContent.length > 0);
$("#st-ouimax").value = "25";
$("#st-ouiurl").value = "https://api.macvendors.com";
$("#settings-form").dispatchEvent(new w.Event("submit", { cancelable: true }));
await sleep(50);
const lastPatch8 = [...calls].reverse().find((c) => c.url.includes("/api/settings") && c.method === "PATCH");
check("Settings: OUI gueltig -> PATCH enthaelt oui_online_max=25 + oui_online_url", patchCount() === patchBase8 + 1 && !!lastPatch8 && lastPatch8.body.includes('"oui_online_max":25') && lastPatch8.body.includes('"oui_online_url":"https://api.macvendors.com"'));
const patchBase3 = patchCount();
$("#st-whitelist").value = "bogus!!";
$("#settings-form").dispatchEvent(new w.Event("submit", { cancelable: true }));
await sleep(50);
check("Settings: Whitelist 'bogus!!' -> kein PATCH, Fehlermeldung", patchCount() === patchBase3 && $("#settings-msg").textContent.includes("Whitelist"));
$("#st-whitelist").value = "AA:BB:CC:DD:EE:FF, 192.168.178.50";
$("#st-autoexport-interval").value = "-1";
$("#settings-form").dispatchEvent(new w.Event("submit", { cancelable: true }));
await sleep(50);
check("Settings: Auto-Export-Intervall -1 -> kein PATCH, Fehlermeldung", patchCount() === patchBase3 && $("#settings-msg").textContent.includes("Auto-Export"));
$("#st-autoexport-interval").value = "12";
$("#settings-form").dispatchEvent(new w.Event("submit", { cancelable: true }));
await sleep(50);
check("Settings: Whitelist + Intervall 12 gueltig -> PATCH", patchCount() === patchBase3 + 1);
const lastSettingsPatch = [...calls].reverse().find((c) => c.url.includes("/api/settings") && c.method === "PATCH");
check(
  "Settings: PATCH enthaelt alarm_whitelist + auto_export_interval_hours + mdns_enabled",
  !!lastSettingsPatch && lastSettingsPatch.body.includes("alarm_whitelist") && lastSettingsPatch.body.includes('"auto_export_interval_hours":12') && lastSettingsPatch.body.includes("mdns_enabled")
);
const patchBase4 = patchCount();
$("#st-sites").value = "Kaputt";
$("#settings-form").dispatchEvent(new w.Event("submit", { cancelable: true }));
await sleep(50);
check("Settings: Standorte 'Kaputt' -> kein PATCH, Fehlermeldung", patchCount() === patchBase4 && $("#settings-msg").textContent.includes("Standorte"));
$("#st-sites").value = "Zuhause:192.168.178.0/24; Remote:192.168.179.0/24";
$("#settings-form").dispatchEvent(new w.Event("submit", { cancelable: true }));
await sleep(50);
check("Settings: Standorte gueltig -> PATCH mit sites", patchCount() === patchBase4 + 1 && [...calls].reverse().find((c) => c.url.includes("/api/settings") && c.method === "PATCH").body.includes('"sites"'));
const patchBase5 = patchCount();
$("#st-subnets").value = "2003:db8::/999";
$("#settings-form").dispatchEvent(new w.Event("submit", { cancelable: true }));
await sleep(50);
check("Settings: Subnetz 2003:db8::/999 -> kein PATCH, Fehlermeldung", patchCount() === patchBase5 && $("#settings-msg").textContent.includes("Subnetz"));
$("#st-subnets").value = "2003:db8::/64, 192.168.178.0/24";
$("#settings-form").dispatchEvent(new w.Event("submit", { cancelable: true }));
await sleep(50);
check("Settings: IPv6-Subnetz 2003:db8::/64 gueltig -> PATCH", patchCount() === patchBase5 + 1);
$("#st-subnets").value = "";

check(
  "Settings: Compose-Felder vorhanden (fritz/snmp/notify/ports/timeout/exportdir)",
  ["#st-fritzurl", "#st-fritzurls", "#st-fritzuser", "#st-snmpcommunity", "#st-notifywebhook", "#st-notifygotify", "#st-notifyntfy", "#st-ports", "#st-scantimeout", "#st-autoexportdir"].every((s) => !!$(s))
);
const patchBase6 = patchCount();
$("#st-notifywebhook").value = "keine-url";
$("#settings-form").dispatchEvent(new w.Event("submit", { cancelable: true }));
await sleep(50);
check("Settings: Webhook 'keine-url' -> kein PATCH, Fehlermeldung", patchCount() === patchBase6 && $("#settings-msg").textContent.length > 0);
$("#st-notifywebhook").value = "https://hook.example/x";
$("#st-fritzurl").value = "192.168.178.1:49000";
$("#settings-form").dispatchEvent(new w.Event("submit", { cancelable: true }));
await sleep(50);
const lastPatch6 = [...calls].reverse().find((c) => c.url.includes("/api/settings") && c.method === "PATCH");
check(
  "Settings: gueltig -> PATCH enthaelt fritz_url + notify_webhook + scan_timeout + ports",
  patchCount() === patchBase6 + 1 &&
    !!lastPatch6 &&
    lastPatch6.body.includes('"fritz_url":"192.168.178.1:49000"') &&
    lastPatch6.body.includes('"notify_webhook":"https://hook.example/x"') &&
    lastPatch6.body.includes("scan_timeout") &&
    lastPatch6.body.includes("ports")
);

check("Settings: TR-064-Passwortfeld vorhanden (type=password)", !!$("#st-fritzpass") && $("#st-fritzpass").type === "password");
const patchBase7 = patchCount();
$("#st-fritzpass").value = "neuGeheim123";
$("#settings-form").dispatchEvent(new w.Event("submit", { cancelable: true }));
await sleep(50);
const patchWithPass = [...calls].reverse().find((c) => c.url.includes("/api/settings") && c.method === "PATCH");
check("Settings: Passwort gesetzt -> PATCH enthaelt fritz_pass", patchCount() === patchBase7 + 1 && !!patchWithPass && patchWithPass.body.includes('"fritz_pass":"neuGeheim123"'));
$("#st-fritzpass").value = "";
$("#settings-form").dispatchEvent(new w.Event("submit", { cancelable: true }));
await sleep(50);
const patchWithoutPass = [...calls].reverse().find((c) => c.url.includes("/api/settings") && c.method === "PATCH");
check("Settings: Passwort leer -> PATCH ohne fritz_pass (write-only, bleibt unveraendert)", patchCount() === patchBase7 + 2 && !!patchWithoutPass && !patchWithoutPass.body.includes("fritz_pass"));

check("Layout: Select vorhanden, Default 'auto'", $("#layout-select").value === "auto");
$("#layout-select").value = "grid";
$("#layout-select").dispatchEvent(new w.Event("change"));
await sleep(20);
check("Layout: Wechsel auf Raster -> cy.layout('grid')", cyInstance._lastLayout === "grid");
$("#layout-select").value = "tree";
$("#layout-select").dispatchEvent(new w.Event("change"));
await sleep(20);
check(
  "Layout: Wechsel auf Hierarchisch -> eigener Baum (preset mit Positionen)",
  cyInstance._lastLayout === "preset" && typeof cyInstance._lastLayoutOpts.positions === "function"
);
$("#btn-layout-reset").click();
await sleep(60);
check("Layout: Reset -> POST /api/layout/reset", calls.some((c) => c.url.includes("/api/layout/reset") && c.method === "POST"));

check("Nur online: Default AN (initial status=online, 4 Zeilen, Button toggled, fox_online=1)", $("#filter-status").value === "online" && doc.querySelectorAll("#device-table tbody tr").length === 4 && $("#btn-online").classList.contains("toggled") && w.localStorage.getItem("fox_online") === "1");
$("#btn-online").click();
await sleep(80);
check("Nur online: Klick -> alle 5 Zeilen, GET ohne status=online, fox_online=0", doc.querySelectorAll("#device-table tbody tr").length === 5 && ![...calls].reverse().find((c) => c.url.includes("/api/devices")).url.includes("status=online") && w.localStorage.getItem("fox_online") === "0");
$("#btn-online").click();
await sleep(80);
check("Nur online: erneuter Klick -> wieder nur 4 Zeilen (online)", doc.querySelectorAll("#device-table tbody tr").length === 4);
$("#btn-online").click();
await sleep(80);
check("Nur online: danach wieder alle 5 (Filter reset fuer Gruppen-Checks)", doc.querySelectorAll("#device-table tbody tr").length === 5);

const macThIdx = [...doc.querySelectorAll("#device-table thead th")].findIndex((t) => t.dataset.key === "mac");
const remoteRow = [...doc.querySelectorAll("#device-table tbody tr")].find((r) => r.textContent.includes("remote-plug"));
check("MAC-less (VPN-remote): MAC-Zelle zeigt Strich", !!remoteRow && remoteRow.children[macThIdx].textContent.trim() === "–");

const fakeNode = {
  data(k) { return k === "id" ? "aa:bb:cc:dd:ee:ff" : undefined; },
  closedNeighborhood() { return { addClass(c) { cyInstance._spotClass = c; } }; },
};
cyInstance._handlers["tap:node"]({ target: fakeNode });
await sleep(30);
check("Spotlight: Tap -> Nachbarschaft 'spot', Rest 'dim', fit() gerufen", cyInstance._spotClass === "spot" && cyInstance._dimmedClass === "dim" && cyInstance._fitCalls > 0);
cyInstance._handlers["tap"]({ target: cyInstance });
check("Spotlight: Hintergrund-Tap -> clear (removeClass 'spot dim')", cyInstance._removedClass === "spot dim");

check("Gruppen: Checkbox vorhanden + initial aus", !!$("#chk-groups") && !$("#chk-groups").checked);
check("Gruppen: initial keine Subnetz-Nodes", !cyInstance._els.some((e) => e.data && e.data.subnet));
$("#chk-groups").checked = true;
$("#chk-groups").dispatchEvent(new w.Event("change"));
await sleep(30);
check(
  "Gruppen an: Subnetz-Nodes fuer alle 3 Subnetze",
  ["subnet:10.0.0.0/24", "subnet:192.168.178.0/24", "subnet:192.168.179.0/24"].every((id) => cyInstance._els.some((e) => e.data && e.data.id === id && e.data.subnet))
);
const gpos = cyInstance._els.filter((e) => e.data && e.data.subnet && e.position).map((e) => e.position);
check(
  "Gruppen an: Subnetz-Knoten auf eigenem Raster (zu Beginn keine Ueberlappung)",
  gpos.length === 3 && new Set(gpos.map((p) => p.x + "," + p.y)).size === 3
);
check(
  "Gruppen an: Geraete haben Parent (wlan-tv -> subnet:192.168.178.0/24)",
  cyInstance._els.some((e) => e.data && e.data.id === "aa:bb:cc:00:11:22" && e.data.parent === "subnet:192.168.178.0/24")
);
check(
  "Gruppen an: WLAN-Kante bleibt geraetebasiert (wlan:... -> wlan-tv)",
  cyInstance._els.some((e) => e.data && e.data.source === "wlan:192.168.178.1" && e.data.target === "aa:bb:cc:00:11:22")
);
check(
  "Gruppen an: Kanten bleiben geraetebasiert, auch ueber Subnetze (Switch -> remote-plug)",
  cyInstance._els.some((e) => e.data && e.data.source === "d8:47:32:8e:ee:06" && e.data.target === "ip:192.168.179.20") &&
    !cyInstance._els.some((e) => e.data && e.data.source && String(e.data.source).startsWith("subnet:"))
);
check(
  "Standorte: Gruppen-Label mit Standortname (192.168.179.0/24 · Remote)",
  cyInstance._els.some((e) => e.data && e.data.id === "subnet:192.168.179.0/24" && e.data.label.includes("192.168.179.0/24 · Remote"))
);
check("Gruppen an: localStorage fox_groups=subnet", w.localStorage.getItem("fox_groups") === "subnet");
$("#chk-groups").checked = false;
$("#chk-groups").dispatchEvent(new w.Event("change"));
await sleep(30);
check(
  "Gruppen aus: keine Subnetz-Nodes mehr, remote-plug ohne Parent",
  !cyInstance._els.some((e) => e.data && e.data.subnet) && cyInstance._els.some((e) => e.data && e.data.id === "ip:192.168.179.20" && !e.data.parent)
);
check("Ohne IP: Checkbox chk-noip vorhanden + Default angehakt", !!$("#chk-noip") && $("#chk-noip").checked);
check("Ohne IP: Knoten ohne IP auf der Karte ausgeblendet (Default)", !cyInstance._els.some((e) => e.data && e.data.id === "76:84:18:83:f1:3c"));
check("Ohne IP: in der Tabelle trotzdem sichtbar (5 Zeilen)", doc.querySelectorAll("#device-table tbody tr").length === 5);
$("#chk-noip").checked = false;
$("#chk-noip").dispatchEvent(new w.Event("change"));
await sleep(30);
check(
  "Ohne IP: abgehakt -> Knoten erscheint auf der Karte, fox_noip=0",
  cyInstance._els.some((e) => e.data && e.data.id === "76:84:18:83:f1:3c") && w.localStorage.getItem("fox_noip") === "0"
);

const switchFakeNode = {
  data(k) { return k === "id" ? "d8:47:32:8e:ee:06" : undefined; },
  closedNeighborhood() { return { addClass() {} }; },
};
cyInstance._handlers["tap:node"]({ target: switchFakeNode });
await sleep(80);
const colBtn = $("#ed-collapse");
check("Collapse: Switch-Detail hat ed-collapse mit Kinder-Anzahl (1)", !!colBtn && colBtn.textContent.includes("(1)"));
colBtn.click();
await sleep(120);
check("Collapse: remote-plug-Knoten aus der Karte entfernt", !cyInstance._els.some((e) => e.data && e.data.id === "ip:192.168.179.20"));
check("Collapse: Switch-Label enthaelt (+1)", cyInstance._els.some((e) => e.data && e.data.id === "d8:47:32:8e:ee:06" && e.data.label.includes("(+1)")));
check("Collapse: localStorage fox_collapsed enthaelt Switch-MAC", JSON.parse(w.localStorage.getItem("fox_collapsed") || "[]").includes("d8:47:32:8e:ee:06"));
check("Collapse: Button wechselt zu 'einblenden'", !!$("#ed-collapse") && $("#ed-collapse").textContent.includes("einblenden"));
$("#ed-collapse").click();
await sleep(120);
check("Collapse: erneuter Klick -> remote-plug wieder sichtbar", cyInstance._els.some((e) => e.data && e.data.id === "ip:192.168.179.20"));

check("A11y: html lang=de", doc.documentElement.getAttribute("lang") === "de");
check("A11y: Skip-Link + main#main", !!doc.querySelector("a.skip-link[href='#main']") && doc.querySelector("main").id === "main");
check("A11y: Suche/Filter/Layout mit aria-label", ["#search", "#filter-category", "#filter-status", "#layout-select"].every((s) => $(s) && !!$(s).getAttribute("aria-label")));
check("A11y: scan-status role=status, settings-msg role=alert", $("#scan-status").getAttribute("role") === "status" && $("#settings-msg").getAttribute("role") === "alert");
check("A11y: Tabs role=tablist/tab + aria-selected", doc.querySelector(".tabs").getAttribute("role") === "tablist" && $("#tab-detail").getAttribute("role") === "tab" && $("#tab-detail").getAttribute("aria-selected") === "true");
check("A11y: th scope=col", [...doc.querySelectorAll("#device-table thead th")].every((t) => t.getAttribute("scope") === "col"));
check("A11y: CSS :focus-visible + --accent-strong + active=accent-strong", css.includes(":focus-visible") && css.includes("--accent-strong") && /button\.active\s*\{[^}]*var\(--accent-strong\)/.test(css));
check("A11y: Karte hat visuell versteckten Tastatur-Hinweis", !!doc.querySelector("#view-map .visually-hidden"));

const row0 = doc.querySelector("#device-table tbody tr");
check("A11y: Tabellenzeile tabindex=0 + aria-label", !!row0 && row0.getAttribute("tabindex") === "0" && (row0.getAttribute("aria-label") || "").startsWith("Details:"));
const devGetBefore = calls.filter((c) => c.url.includes("/api/device/") && c.method === "GET").length;
row0.dispatchEvent(new w.KeyboardEvent("keydown", { bubbles: true, key: "Enter" }));
await sleep(80);
check("A11y: Enter auf Zeile -> GET /api/device/ (Detail per Tastatur)", calls.filter((c) => c.url.includes("/api/device/") && c.method === "GET").length > devGetBefore);

const thFirst = doc.querySelector("#device-table thead th[data-key]");
const keysBefore = thKeys();
thFirst.dispatchEvent(new w.KeyboardEvent("keydown", { bubbles: true, key: "ArrowRight", altKey: true }));
await sleep(20);
const keysAfter = thKeys();
check("A11y: Alt+Pfeil rechts auf th -> Spalte per Tastatur verschoben", keysAfter[1] === keysBefore[0] && keysAfter[0] === keysBefore[1]);

cyInstance._handlers["tap:node"]({ target: switchFakeNode });
await sleep(80);
check("A11y: Angeschlossene Geräte als <button class=dev-link>", !!$("#detail-content button.dev-link[data-mac='ip:192.168.179.20']"));

// Sicherheit (v1.4.1): Werte aus dem Netz duerfen in der Detailansicht kein HTML/JS erzeugen.
const xssNode = { data(k) { return k === "id" ? "66:66:66:66:66:66" : undefined; }, closedNeighborhood() { return { addClass() {} }; } };
cyInstance._handlers["tap:node"]({ target: xssNode });
await sleep(80);
const det = $("#detail-content");
check(
  "Sicherheit: Detailansicht escaped Hostname/Hersteller/Notiz/Dienst/Event (kein XSS)",
  !det.querySelector("img, script, svg, b") && w.__xss === undefined &&
    det.textContent.includes('<img src=x onerror="window.__xss=1">') && det.textContent.includes("<script>window.__xss=2</script>")
);
check("Sicherheit: Notiz bleibt im value-Attribut gekapselt", !!$("#ed-note") && $("#ed-note").value.includes("onfocus") && !$("#ed-note").hasAttribute("onfocus"));
check("Bugfix: Kategorie-Optionen tragen den kanonischen Wert (sprachunabhaengig)", [...doc.querySelectorAll("#ed-cat option")].every((o) => o.value && !o.value.startsWith("cat.")));

// Mehrfach-Zuordnung von Hand (v1.6.0)
doc.querySelector("button[data-view=table]").click();
await sleep(30);
const selBoxes = () => [...doc.querySelectorAll("#device-table tbody td.sel-col input[type=checkbox]")];
check("Mehrfach: Auswahl-Checkbox je Zeile mit aria-label", selBoxes().length > 0 && selBoxes().every((c) => (c.getAttribute("aria-label") || "").length > 3));
check("Mehrfach: Kopf-Checkbox 'alle' mit aria-label", !!$("#sel-all") && !!$("#sel-all").getAttribute("aria-label"));
check("Mehrfach: Setzen ohne Auswahl deaktiviert", $("#bulk-apply").disabled && $("#bulk-clear").disabled);
const rowsBefore = doc.querySelectorAll("#detail-content h2").length;
const cb0 = selBoxes()[0];
cb0.click();
await sleep(10);
check("Mehrfach: Checkbox-Klick oeffnet keine Detailansicht und zaehlt", $("#bulk-count").textContent.startsWith("1") && !$("#bulk-apply").disabled);
check("Mehrfach: Kopf-Checkbox teilweise (indeterminate)", $("#sel-all").indeterminate === true);
check("Mehrfach: Ziel-Liste nur Netzknoten, ohne ausgewaehlte", [...doc.querySelectorAll("#bulk-parent option")].some((o) => o.value === "d8:47:32:8e:ee:06") && ![...doc.querySelectorAll("#bulk-parent option")].some((o) => o.value === "aa:bb:cc:dd:ee:ff"));
$("#sel-all").click();
await sleep(20);
check("Mehrfach: 'alle' waehlt alle Zeilen", selBoxes().every((c) => c.checked) && $("#sel-all").checked);
selBoxes().forEach((c) => { if (c.closest("tr").textContent.includes("TL-SG108E-GZ")) c.click(); });
await sleep(10);
$("#bulk-parent").value = "d8:47:32:8e:ee:06";
const nSel = selBoxes().filter((c) => c.checked).length;
$("#bulk-apply").click();
await sleep(60);
const bulkCall = calls.filter((c) => c.url.includes("/api/devices/connect")).pop();
const bulkBody = bulkCall ? JSON.parse(bulkCall.body) : null;
check("Mehrfach: POST /api/devices/connect mit MACs und Ziel", !!bulkCall && bulkCall.method === "POST" && bulkBody.connected_to === "d8:47:32:8e:ee:06" && bulkBody.macs.length === nSel && !bulkBody.macs.includes("d8:47:32:8e:ee:06"));
check("Mehrfach: Ergebnis per role=status gemeldet, Auswahl geleert", $("#bulk-result").getAttribute("role") === "status" && $("#bulk-result").textContent.includes(String(nSel)) && $("#bulk-apply").disabled);
check("Mehrfach: Leiste als Gruppe beschriftet", $("#bulk-bar").getAttribute("role") === "group" && !!$("#bulk-bar").getAttribute("aria-labelledby"));
void rowsBefore;

// VPN-Erkennung (z. B. FRITZ!Box IPSec .201 / WireGuard .202)
doc.querySelector("button[data-view=table]").click();
await sleep(30);
const vpnRow = [...doc.querySelectorAll("#device-table tbody tr")].find((r) => r.textContent.includes("wlan-tv"));
check("VPN: Badge in Tabellenzeile (wlan-tv)", !!vpnRow && !!vpnRow.querySelector(".badge-vpn") && vpnRow.querySelector(".badge-vpn").textContent === "VPN");
check("VPN: Knoten traegt data.vpn=1", cyInstance._els.some((e) => e.data && e.data.id === "aa:bb:cc:00:11:22" && e.data.vpn === 1));
check("VPN: Knotenlabel enthaelt VPN", cyInstance._els.some((e) => e.data && e.data.id === "aa:bb:cc:00:11:22" && String(e.data.label).includes("VPN")));
check("VPN: Kartenstil enthaelt node[vpn = 1]", cyInstance._style.some((s) => s.selector === "node[vpn = 1]"));
const vpnNode = { data(k) { return k === "id" ? "aa:bb:cc:00:11:22" : undefined; }, closedNeighborhood() { return { addClass() {} }; } };
cyInstance._handlers["tap:node"]({ target: vpnNode });
await sleep(80);
check("VPN: Detail zeigt VPN-Verbindung = ja", $("#detail-content").textContent.includes("VPN") && $("#detail-content").textContent.includes("ja"));
check("VPN: Settings-Feld st-vpnpool mit off (Default) gefuellt", !!$("#st-vpnpool") && $("#st-vpnpool").value === "off");
const vpnPatchBase = patchCount();
$("#st-vpnpool").value = "auto, 10.8.0.0/24";
$("#settings-form").dispatchEvent(new w.Event("submit", { cancelable: true }));
await sleep(50);
check(
  "VPN: gueltiger Pool -> PATCH enthaelt vpn_pool",
  patchCount() === vpnPatchBase + 1 && [...calls].reverse().find((c) => c.url.includes("/api/settings") && c.method === "PATCH").body.includes('"vpn_pool":"auto, 10.8.0.0/24"')
);
$("#st-vpnpool").value = "kaputt";
$("#settings-form").dispatchEvent(new w.Event("submit", { cancelable: true }));
await sleep(50);
check("VPN: ungueltiger Pool -> kein PATCH (clientseitige Validierung)", patchCount() === vpnPatchBase + 1);

const loginHtml = fs.readFileSync(path.join(repo, "app/static/login.html"), "utf8");
check("A11y: login.html mit sichtbaren Labels + role=alert", loginHtml.includes('for="login-user"') && loginHtml.includes('for="login-pass"') && loginHtml.includes('role="alert"'));
check("Sicherheit: login.html ohne Inline-Skript (CSP script-src 'self')", !/<script>/.test(loginHtml) && loginHtml.includes('src="/static/login.js"'));

console.log(failures === 0 ? "ALL UI CHECKS PASSED" : failures + " UI CHECKS FAILED");
process.exit(failures === 0 ? 0 : 1);
