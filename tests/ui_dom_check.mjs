import fs from "node:fs";
import path from "node:path";
import { JSDOM } from "jsdom";

const repo = path.resolve(new URL("..", import.meta.url).pathname);
const html = fs
  .readFileSync(path.join(repo, "app/static/index.html"), "utf8")
  .replace('<script src="/static/vendor/cytoscape.min.js"></script>', "")
  .replace('<script src="/static/app.js"></script>', "");
const css = fs.readFileSync(path.join(repo, "app/static/styles.css"), "utf8");

const dom = new JSDOM(html, { url: "http://localhost/", runScripts: "dangerously", pretendToBeVisual: true });
const w = dom.window;
const doc = w.document;
const style = doc.createElement("style");
style.textContent = css;
doc.head.appendChild(style);

const calls = [];
w.fetch = async (url, opts = {}) => {
  calls.push({ url: String(url), method: opts.method || "GET" });
  const json = async () => {
    if (String(url).includes("/api/devices"))
      return [
        {
          mac: "aa:bb:cc:dd:ee:ff", ip: "10.0.0.5", hostname: "nas", vendor: "Synology",
          category: "Server/NAS", status: "online", subnet: "10.0.0.0/24", source: "ping+arp,tr064",
          ports_str: "80;443", connected_to: "10.0.0.1", note: "", last_seen: "2026-01-01T10:00:00+00:00",
          port_count: 2, x: null, y: null,
        },
        {
          mac: "ip:192.168.179.20", ip: "192.168.179.20", hostname: "remote-plug", vendor: "",
          category: "Smart-Home/IoT", status: "online", subnet: "192.168.179.0/24", source: "tcp",
          ports_str: "", connected_to: "192.168.178.1", note: "", last_seen: "2026-01-01T10:00:00+00:00",
          port_count: 0, x: null, y: null,
        },
      ];
    if (String(url).includes("/api/categories")) return ["Router", "Switch", "Client"];
    if (String(url).includes("/api/device/"))
      return {
        mac: "aa:bb:cc:dd:ee:ff", ip: "10.0.0.5", hostname: "nas", vendor: "Synology",
        category: "Server/NAS", status: "online", subnet: "10.0.0.0/24", source: "ping+arp,tr064", note: "",
        first_seen: "2026-01-01T09:00:00+00:00", last_seen: "2026-01-01T10:00:00+00:00",
        ports: [{ port: 80, proto: "tcp", service: "http" }, { port: 443, proto: "tcp", service: "https" }],
        layout: {}, history: [], events: [],
      };
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
      };
    if (String(url).includes("/api/tokens")) return [];
    if (String(url).includes("/api/logs"))
      return {
        file: "/data/netmap.log",
        total: 2,
        returned: 2,
        lines: ["2026-01-01 10:00:00 INFO fox_netmap: Scan fertig: 3 Geraete, 0 neu", "2026-01-01 10:00:01 ERROR fox_netmap scanner: Scan-Fehler: boom"],
      };
    if (String(url).includes("/api/scan")) return { last_scan: null, next_scan: null, scanning: 0 };
    return {};
  };
  return { ok: true, status: 200, json, cookies: {} };
};
const cyStub = {
  on() {},
  elements: () => ({ remove() {} }),
  add() {},
  layout: () => ({ run() {} }),
  fit() {},
  resize() {},
  nodes: () => ({ removeClass() {} }),
  edges: () => ({ removeClass() {}, filter: () => ({ addClass() {} }) }),
  getElementById: () => ({ addClass() {} }),
};
w.cytoscape = () => cyStub;
w.print = () => calls.push({ url: "window.print", method: "CALL" });

w.eval(fs.readFileSync(path.join(repo, "app/static/app.js"), "utf8"));
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

$("#nav [data-view='table']").click();
check("Tabelle: Tabellenansicht sichtbar", vis($("#view-table")));
check("Tabelle: Karte versteckt", !vis($("#view-map")));

$("#btn-settings").click();
await sleep(50);
check("Tabelle + ⚙: Sidebar sichtbar", vis($("#detail")));
check("Tabelle + ⚙: Settings-Tab aktiv", $("#settings-content").hidden === false && $("#detail-content").hidden === true);

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
check("Header: Suche + 2 Filter vorhanden", $("#search") && $("#filter-category") && $("#filter-status"));

$("#search").value = "nas";
$("#search").dispatchEvent(new w.Event("input"));
await sleep(400);
check("Suche: GET /api/devices?q=nas", calls.some((c) => c.url.includes("/api/devices") && c.url.includes("q=nas")));

const thKeys = () => [...doc.querySelectorAll("#device-table thead th")].map((t) => t.dataset.key);
const beforeCols = thKeys();
check("Spalten: draggable-Header", doc.querySelectorAll("#device-table thead th[draggable='true']").length === beforeCols.length);
const dt = { data: {}, setData(k, v) { this.data[k] = v; }, getData(k) { return this.data[k]; } };
const th0 = doc.querySelector("#device-table thead th");
const evDrag = new w.Event("dragstart", { bubbles: true });
evDrag.dataTransfer = dt;
th0.dispatchEvent(evDrag);
const th3 = doc.querySelectorAll("#device-table thead th")[3];
const evDrop = new w.Event("drop", { bubbles: true, cancelable: true });
evDrop.dataTransfer = dt;
th3.dispatchEvent(evDrop);
const afterCols = thKeys();
check("Spalten-Drag: Reihenfolge geaendert (th0 vor th3 eingefuegt)", afterCols[0] === beforeCols[1] && afterCols[2] === beforeCols[0]);
const savedCols = JSON.parse(w.localStorage.getItem("fox_table_cols") || "null");
check("Spalten-Drag: localStorage persistiert", Array.isArray(savedCols) && savedCols[2] === beforeCols[0]);

const bodyRow = doc.querySelector("#device-table tbody tr");
check(
  "Spalten-Drag: Body-Zellen folgen der neuen Reihenfolge (ip, mac, hostname, vendor, …)",
  !!bodyRow && bodyRow.children[0].textContent.includes("10.0.0.5") && bodyRow.children[2].textContent.startsWith("nas")
);
check("Quelle-Spalte: Header + Zelle vorhanden", !!doc.querySelector('#device-table th[data-key="source"]') && bodyRow.textContent.includes("ping+arp,tr064"));

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

doc.querySelector("#device-table tbody tr").dispatchEvent(new w.MouseEvent("click", { bubbles: true }));
await sleep(80);
check(
  "Web-Links: Detail-Panel Hostname mit beiden Links, genau 2 Links gesamt (IP pur)",
  $("#detail-content").innerHTML.includes('href="http://10.0.0.5"') &&
    $("#detail-content").innerHTML.includes('href="https://10.0.0.5"') &&
    doc.querySelectorAll("#detail-content a").length === 2
);
check("Web-Links: Sidebar oeffnet bei Zeilenklick", vis($("#detail")));

const macThIdx = [...doc.querySelectorAll("#device-table thead th")].findIndex((t) => t.dataset.key === "mac");
const remoteRow = [...doc.querySelectorAll("#device-table tbody tr")].find((r) => r.textContent.includes("remote-plug"));
check("MAC-less (VPN-remote): MAC-Zelle zeigt Strich", !!remoteRow && remoteRow.children[macThIdx].textContent.trim() === "–");

$("#nav [data-view='log']").click();
await sleep(100);
check("Log: Log-Ansicht sichtbar, Karte versteckt", vis($("#view-log")) && !vis($("#view-map")));
check("Log: GET /api/logs wurde abgesetzt", calls.some((c) => c.url.includes("/api/logs")));
check("Log: Inhalt gerendert (ERROR-Zeile sichtbar)", $("#log-view").textContent.includes("Scan-Fehler"));

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

console.log(failures === 0 ? "ALL UI CHECKS PASSED" : failures + " UI CHECKS FAILED");
process.exit(failures === 0 ? 0 : 1);
