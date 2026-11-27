// Gemeinsames jsdom-Harness fuer tests/ui/*.mjs (W5): Baut index.html ohne <script>-Tags,
// injiziert CSS + i18n/icons/api/app per eval, mockt fetch und cytoscape.
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { JSDOM } from "jsdom";

const repo = path.resolve(new URL("../..", import.meta.url).pathname);

export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export function makeHarness({ devices = [], meta = {}, scanStatus = {}, fetchImpl = null, url = "http://localhost/", editMode = false } = {}) {
  const html = fs
    .readFileSync(path.join(repo, "app/static/index.html"), "utf8")
    .replace('<script src="/static/vendor/cytoscape.min.js"></script>', "")
    .replace('<script src="/static/i18n.js"></script>', "")
    .replace('<script src="/static/icons.js"></script>', "")
    .replace('<script src="/static/api.js"></script>', "")
    .replace('<script src="/static/app.js"></script>', "");
  const css = fs.readFileSync(path.join(repo, "app/static/styles.css"), "utf8");

  const dom = new JSDOM(html, { url, runScripts: "dangerously", pretendToBeVisual: true });
  const w = dom.window;
  const doc = w.document;
  const style = doc.createElement("style");
  style.textContent = css;
  doc.head.appendChild(style);
  if (editMode) w.localStorage.setItem("fox_editmode", "1");

  const calls = [];
  const DEVS = devices;
  const okJson = (data, status = 200) => ({
    ok: status >= 200 && status < 300,
    status,
    json: async () => data,
    cookies: {},
    blob: async () => new w.Blob(["x"]),
  });
  const defaultFetch = async (u, opts = {}) => {
    calls.push({ url: String(u), method: opts.method || "GET", body: opts.body || null });
    const s = String(u);
    const method = opts.method || "GET";
    if (method !== "GET") return okJson({});
    if (s.includes("/api/devices/connect")) return okJson({ count: JSON.parse(opts.body).macs.length });
    if (s.includes("/api/devices")) return okJson(DEVS);
    if (s.includes("/api/rooms")) return okJson([...new Set(DEVS.map((d) => d.room).filter(Boolean))].sort());
    if (s.includes("/api/categories")) return okJson(["Router", "Switch", "Client", "Server/NAS"]);
    if (s.includes("/api/meta")) return okJson({ version: "1.6.18", gateway: "192.168.178.1", ...meta });
    if (s.includes("/api/sites")) return okJson({ names: ["Zuhause"], map: { "10.0.0.0/24": "Zuhause" } });
    if (s.includes("/api/device/")) {
      const mac = decodeURIComponent(s.split("/api/device/")[1].split("?")[0]);
      const d = DEVS.find((x) => x.mac === mac);
      return okJson({
        ports: [], layout: { connected_to: "", connected_manual: 0 }, history: [], events: [],
        ip6: "", vendor: "", site: "", room: "", source: "", note: "", first_seen: "2026-01-01T09:00:00+00:00",
        last_seen: "2026-01-01T10:00:00+00:00", connection: "", link_port: "", category_reason: "",
        ...(d || { mac, ip: "192.168.178.66", hostname: "x", category: "Client", status: "online", subnet: "192.168.178.0/24" }),
      });
    }
    if (s.includes("/api/scan/status")) return okJson({ scanning: 0, last_scan: null, next_scan: null, ...scanStatus });
    if (s.includes("/api/settings"))
      return okJson({
        theme: "dark", lang: "de", scan_interval: 900, subnets: "10.0.0.0/24", scan_timeout: 1, port_top: 100,
        ports: "", history_hours: 720, device_retention_days: 30, event_retention_days: 90, snmp_enabled: true,
        snmp_switches: "", snmp_community: { configured: true }, fritz_url: "", fritz_urls: "", fritz_user: "",
        fritz_pass: { configured: false }, tr064_insecure_tls: false, notify_webhook: "", notify_gotify: "",
        notify_ntfy: "", auto_export: false, auto_export_interval_hours: 24, auto_export_dir: "exports",
        mdns_enabled: true, oui_online_enabled: false, oui_online_max: 10, oui_online_url: "",
        alarm_whitelist: "", sites: "", vpn_pool: "off",
      });
    if (s.includes("/api/tokens")) return okJson([]);
    if (s.includes("/api/logs")) return okJson({ lines: [], returned: 0, total: 0, file: "netmap.log" });
    if (s.includes("/api/me")) return okJson({ username: "admin" });
    return okJson({});
  };
  w.fetch = fetchImpl ? (u, opts) => fetchImpl(u, opts || {}, defaultFetch) : defaultFetch;

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
  w.URL.createObjectURL = () => "blob:mock";
  w.URL.revokeObjectURL = () => {};

  w.eval(
    fs.readFileSync(path.join(repo, "app/static/i18n.js"), "utf8") +
      "\n;\n" +
      fs.readFileSync(path.join(repo, "app/static/icons.js"), "utf8") +
      "\n;\n" +
      fs.readFileSync(path.join(repo, "app/static/api.js"), "utf8") +
      "\n;\n" +
      fs.readFileSync(path.join(repo, "app/static/app.js"), "utf8")
  );

  let failures = 0;
  const check = (name, cond) => {
    if (!cond) {
      failures++;
      console.error("FAIL:", name);
    }
  };
  return {
    w,
    doc,
    calls,
    check,
    get failures() { return failures; },
    cy: () => cyInstance,
    okJson,
    sleep,
  };
}

export async function standalone(main) {
  if (import.meta.url !== pathToFileURL(process.argv[1] || "").href) return;
  try {
    const f = await main();
    console.log(f === 0 ? "OK" : f + " FAILED");
    process.exit(f === 0 ? 0 : 1);
  } catch (e) {
    console.error(e);
    process.exit(1);
  }
}
