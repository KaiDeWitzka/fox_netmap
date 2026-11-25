"use strict";

const EMBED = location.pathname.startsWith("/embed");
const TOKEN = new URLSearchParams(location.search).get("token") || "";

// Kartenstil (seit v1.6.1): neutrale Knoten, Kategorie über Symbol und Text, nicht über Farbe (WCAG 1.4.1).
// Kontrast gegen den Hintergrund: Text >= 4,5:1, Ränder/Symbole >= 3:1 (WCAG 1.4.3, 1.4.11). Geprüft in tests/ui_dom_check.mjs.
const MAP_PALETTES = {
  dark: {
    bg: "#0f172a", body: "#1e293b", border: "#64748b", root: "#38bdf8", repeater: "#cbd5e1", icon: "#e2e8f0",
    text: "#e2e8f0", textOff: "#cbd5e1", edge: "#64748b", hl: "#facc15", sel: "#ffffff", frame: "#38bdf8", frameText: "#94a3b8",
  },
  light: {
    bg: "#f8fafc", body: "#ffffff", border: "#64748b", root: "#0284c7", repeater: "#334155", icon: "#334155",
    text: "#0f172a", textOff: "#334155", edge: "#64748b", hl: "#b45309", sel: "#0f172a", frame: "#0284c7", frameText: "#475569",
  },
};

function mapPalette(theme) {
  const th = theme || document.documentElement.dataset.theme || "dark";
  return MAP_PALETTES[th] || MAP_PALETTES.dark;
}

// Netzknoten werden größer gezeichnet, damit die Hierarchie in der Übersicht erkennbar ist.
const HUB_SIZE = 40;
const NODE_SIZE = 34;

// Ab wie vielen Knoten die Karte als "gross" gilt (dichtere Darstellung noetig)
function bigMap(n) {
  return n > 60;
}
// Label erst ab staerkerem Zoom zeigen, wenn viele Knoten sichtbar sind
function labelZoomThreshold(n) {
  return n > 80 ? 1.3 : n > 40 ? 1.05 : 0.85;
}
// Knotengroessen schrumpfen bei grossen Karten leicht
function nodeSizes(n) {
  return bigMap(n) ? { node: 28, hub: 34 } : { node: NODE_SIZE, hub: HUB_SIZE };
}
// Baum-Abstaende wachsen bei grossen Karten (TREE bleibt Default fuer kleine Karten)
function treeScale(n) {
  return bigMap(n) ? { col: 150, level: 150, row: 116 } : TREE;
}
const NAME_MAX = 20;

function shortName(v) {
  const s = String(v || "");
  return s.length > NAME_MAX ? s.slice(0, NAME_MAX - 1) + "…" : s;
}

let META = { gateway: "", wan_ip: "", wan_status: "", wan_endpoint: "" };
let SITES = [];
let SITE_MAP = {};

const QP = new URLSearchParams(location.search);
let LANG = QP.get("lang") || localStorage.getItem("fox_lang") || "de";
if (!LANGS.some(([c]) => c === LANG)) LANG = "de";

// Sicherheit: Alle Werte, die per innerHTML eingesetzt werden, MUESSEN durch esc() laufen.
// Hostnamen, Hersteller, Notizen, Dienst- und Event-Texte stammen aus dem Netz (mDNS, DNS,
// TR-064, OUI-Online-Lookup) bzw. aus Benutzereingaben und sind nicht vertrauenswuerdig.
const ESC_MAP = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;", "`": "&#96;" };
function esc(v) {
  return String(v ?? "").replace(/[&<>"'`]/g, (c) => ESC_MAP[c]);
}

function safeUrl(u) {
  return /^https?:\/\//i.test(String(u || "")) ? String(u) : "#";
}

function t(key, vars) {
  let s = (I18N[LANG] && I18N[LANG][key]) || I18N.de[key] || key;
  if (vars) for (const k of Object.keys(vars)) s = s.split("{" + k + "}").join(String(vars[k]));
  return s;
}

function applyI18n() {
  document.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
  document.querySelectorAll("[data-i18n-ph]").forEach((el) => { el.placeholder = t(el.dataset.i18nPh); });
  document.querySelectorAll("[data-i18n-title]").forEach((el) => { el.title = t(el.dataset.i18nTitle); });
  document.querySelectorAll("[data-i18n-aria]").forEach((el) => { el.setAttribute("aria-label", t(el.dataset.i18nAria)); });
  document.documentElement.lang = LANG;
  document.title = t("app.title");
}

let collapsed = new Set(JSON.parse(localStorage.getItem("fox_collapsed") || "[]"));
let groupMode = localStorage.getItem("fox_groups") || "none";
// Geräte ohne IP (z. B. TR-064-Host nur mit MAC/Name) erst auf der Karte zeigen, wenn angehakt (Default: ausblenden)
let hideNoIp = localStorage.getItem("fox_noip") ?? "1";

function groupOf(d) {
  return d.subnet ? "subnet:" + d.subnet : null;
}

function childCount(mac) {
  return devices.filter((d) => parentId(d) === mac).length;
}

function toggleCollapse(mac) {
  if (collapsed.has(mac)) collapsed.delete(mac);
  else collapsed.add(mac);
  localStorage.setItem("fox_collapsed", JSON.stringify([...collapsed]));
}

function isHiddenByCollapse(mac) {
  let p = parentId(devices.find((d) => d.mac === mac) || {});
  let hops = 0;
  while (p && hops++ < 10) {
    if (collapsed.has(p)) return true;
    const pd = devices.find((x) => x.mac === p) || devices.find((x) => x.ip === p);
    if (!pd) return false;
    p = parentId(pd);
  }
  return false;
}

let devices = [];
let categories = [];
let cy = null;
let sortKey = "hostname";
let sortDir = 1;

const TABLE_COLS = [
  ["hostname", "cols.hostname"], ["ip", "cols.ip"], ["ip6", "cols.ip6"], ["mac", "cols.mac"], ["vendor", "cols.vendor"], ["source", "cols.source"],
  ["category", "cols.category"], ["status", "cols.status"], ["subnet", "cols.subnet"], ["site", "cols.site"], ["room", "cols.room"],
  ["ports_str", "cols.ports"], ["connected_to", "cols.connected"], ["note", "cols.note"], ["last_seen", "cols.lastSeen"],
];

function loadColOrder() {
  try {
    const saved = JSON.parse(localStorage.getItem("fox_table_cols") || "null");
    if (Array.isArray(saved) && saved.length === TABLE_COLS.length && saved.every((k) => TABLE_COLS.some(([key]) => key === k)))
      return saved;
  } catch (e) {
    // ungültiger Stand -> Default
  }
  return TABLE_COLS.map(([k]) => k);
}

let colOrder = loadColOrder();

function loadColWidths() {
  try {
    const s = JSON.parse(localStorage.getItem("fox_table_widths") || "{}");
    return s && typeof s === "object" ? s : {};
  } catch (e) {
    return {};
  }
}

let colWidths = loadColWidths();
let suppressSortClick = false;
// Mehrfach-Zuordnung: ausgewählte Geräte (MAC) in der Tabelle
const selectedMacs = new Set();

const LAYOUTS = { force: "cose", tree: "breadthfirst", circle: "circle", concentric: "concentric", grid: "grid" };

function currentLayout() {
  return localStorage.getItem("fox_layout") || "auto";
}

function applyLayout() {
  if (!cy || !devices.length) return;
  const choice = currentLayout();
  const hasPos = devices.every((d) => typeof d.x === "number" && typeof d.y === "number");
  let opts;
  if (choice === "auto" && hasPos) {
    opts = { name: "preset", animate: false };
  } else if (choice === "auto" || choice === "tree") {
    // Baum nach Topologie: Internet -> Router -> Switch -> Endgeraete (Anforderung "Layout", 01-anforderungen.md)
    const pos = computeTreePositions(lastElements);
    opts = { name: "preset", animate: false, positions: (node) => pos[node.id()] || node.position() };
  } else if (choice === "force") {
    const big = devices.length > 60;
    opts = {
      name: "cose", animate: false, padding: 30,
      idealEdgeLength: big ? 90 : 110,
      nodeRepulsion: big ? 22000 : 15000,
      nodeOverlap: big ? 30 : 20,
      spacingFactor: big ? 1.25 : 1.1,
    };
  } else {
    opts = { name: LAYOUTS[choice], animate: false };
  }
  cy.layout(opts).run();
  cy.fit(undefined, 40);
}

let lastElements = [];

const TREE = { col: 170, level: 140, row: 92 };

// Ordnet die Knoten als Baum an. Endgeraete (Knoten ohne Kinder) eines Knotens werden kompakt in einem
// Raster darunter gesetzt, damit 40 Geraete an der FRITZ!Box keine endlose Zeile ergeben. Knoten ohne
// Verbindung landen in einem Raster unter dem Baum. Reine Funktion, damit sie testbar ist.
function computeTreePositions(els) {
  const nodes = els.filter((e) => e.data && !e.data.source && !e.data.subnet).map((e) => e.data);
  const T = treeScale(nodes.length);
  const ids = new Set(nodes.map((n) => n.id));
  const byId = Object.fromEntries(nodes.map((n) => [n.id, n]));
  const kids = {};
  const indeg = {};
  for (const e of els) {
    if (!e.data || !e.data.source) continue;
    const { source: s, target: t2 } = e.data;
    if (!ids.has(s) || !ids.has(t2) || s === t2) continue;
    (kids[s] = kids[s] || []).push(t2);
    indeg[t2] = (indeg[t2] || 0) + 1;
  }
  const label = (id) => String((byId[id] && (byId[id].name || byId[id].label)) || id).toLowerCase();
  const sortKey = (id) => [byId[id] && byId[id].hub ? 0 : 1, (byId[id] && byId[id].subnetKey) || "", label(id)];
  const cmp = (a, b) => {
    const ka = sortKey(a);
    const kb = sortKey(b);
    for (let i = 0; i < ka.length; i++) if (ka[i] !== kb[i]) return ka[i] < kb[i] ? -1 : 1;
    return 0;
  };
  // Baum aus dem Graphen: jeder Knoten genau einmal (Schutz gegen Zyklen und Mehrfach-Eltern)
  const seen = new Set();
  const tree = {};
  const build = (id) => {
    seen.add(id);
    tree[id] = [];
    for (const c of (kids[id] || []).slice().sort(cmp)) {
      if (seen.has(c)) continue;
      seen.add(c);
      tree[id].push(c);
    }
    for (const c of tree[id]) build(c);
  };
  const rootRank = (id) => (id === "internet" ? 0 : byId[id] && byId[id].hub ? 1 : 2);
  const roots = nodes
    .map((n) => n.id)
    .filter((id) => !indeg[id] && (kids[id] || []).length)
    .sort((a, b) => rootRank(a) - rootRank(b) || cmp(a, b));
  for (const r of roots) if (!seen.has(r)) build(r);
  // Zyklen ohne Wurzel: ersten Knoten als Wurzel nehmen
  for (const n of nodes) if (!seen.has(n.id) && (kids[n.id] || []).length) { roots.push(n.id); build(n.id); }

  const leafCols = (n) => (n <= 2 ? Math.max(1, n) : Math.min(8, Math.ceil(Math.sqrt(n * 1.5))));
  const split = (id) => {
    const ch = tree[id] || [];
    return { branches: ch.filter((c) => tree[c].length), leaves: ch.filter((c) => !tree[c].length) };
  };
  const wMemo = {};
  const width = (id) => {
    if (wMemo[id] !== undefined) return wMemo[id];
    const { branches, leaves } = split(id);
    const leafW = leaves.length ? leafCols(leaves.length) * T.col : 0;
    const sum = branches.reduce((a, b) => a + width(b), 0) + leafW;
    return (wMemo[id] = Math.max(T.col, sum));
  };
  const pos = {};
  let maxY = 0;
  const place = (id, left, depth) => {
    const w = width(id);
    const y = depth * T.level;
    pos[id] = { x: left + w / 2, y };
    maxY = Math.max(maxY, y);
    const { branches, leaves } = split(id);
    const leafW = leaves.length ? leafCols(leaves.length) * T.col : 0;
    let cur = left + (w - (branches.reduce((a, b) => a + width(b), 0) + leafW)) / 2;
    const half = Math.ceil(branches.length / 2);
    // Verzweigungen links und rechts, Endgeraete-Raster in der Mitte direkt unter dem Knoten
    for (const b of branches.slice(0, half)) { place(b, cur, depth + 1); cur += width(b); }
    const cols = leafCols(leaves.length);
    leaves.forEach((l, i) => {
      const ly = (depth + 1) * T.level + Math.floor(i / cols) * T.row;
      pos[l] = { x: cur + (i % cols) * T.col + T.col / 2, y: ly };
      maxY = Math.max(maxY, ly);
    });
    cur += leafW;
    for (const b of branches.slice(half)) { place(b, cur, depth + 1); cur += width(b); }
  };
  let left = 0;
  for (const r of roots) {
    if (pos[r]) continue;
    place(r, left, 0);
    left += width(r) + T.col;
  }
  // Nicht zugeordnete Knoten als Raster unter dem Baum
  const orphans = nodes.map((n) => n.id).filter((id) => !pos[id]).sort(cmp);
  if (orphans.length) {
    const cols = Math.max(4, Math.floor(Math.max(left, T.col * 4) / T.col));
    const top = (roots.length ? maxY + T.level : 0);
    orphans.forEach((id, i) => {
      pos[id] = { x: (i % cols) * T.col + T.col / 2, y: top + Math.floor(i / cols) * T.row };
    });
  }
  return pos;
}

function api(path, opts = {}) {
  const url = TOKEN ? path + (path.includes("?") ? "&" : "?") + "token=" + encodeURIComponent(TOKEN) : path;
  return fetch(url, { headers: { "Content-Type": "application/json" }, ...opts }).then((r) => {
    if (r.status === 401 && !EMBED) location.href = "/login";
    return r;
  });
}

function applyTheme(theme) {
  const t = theme || localStorage.getItem("fox_theme") || document.documentElement.dataset.theme || "dark";
  document.documentElement.dataset.theme = t;
  localStorage.setItem("fox_theme", t);
  // Karte, Legende und Tabellensymbole folgen dem Theme
  if (typeof cy !== "undefined" && cy) cy.style(mapStyle());
  if (typeof renderLegend === "function") renderLegend();
  if (typeof devices !== "undefined" && devices.length && typeof renderTable === "function") renderTable();
}

function currentFilters() {
  const p = new URLSearchParams();
  const q = document.getElementById("search").value.trim();
  const c = document.getElementById("filter-category").value;
  const s = document.getElementById("filter-status").value;
  const site = document.getElementById("filter-site").value;
  const room = document.getElementById("filter-room").value;
  if (q) p.set("q", q);
  if (c) p.set("category", c);
  if (s) p.set("status", s);
  if (site) p.set("site", site);
  if (room) p.set("room", room);
  return p.toString();
}

function showSidebar(tab) {
  const aside = document.getElementById("detail");
  aside.hidden = false;
  activateTab(tab);
}

function hideSidebar() {
  document.getElementById("detail").hidden = true;
}

function activateTab(tab) {
  const isDetail = tab === "detail";
  const tabDetail = document.getElementById("tab-detail");
  const tabSettings = document.getElementById("tab-settings");
  tabDetail.classList.toggle("active", isDetail);
  tabDetail.setAttribute("aria-selected", String(isDetail));
  tabSettings.classList.toggle("active", !isDetail);
  tabSettings.setAttribute("aria-selected", String(!isDetail));
  document.getElementById("detail-content").hidden = !isDetail;
  document.getElementById("settings-content").hidden = isDetail;
  if (!isDetail) loadSettings();
}

function fillCategoryOptions() {
  const sel = document.getElementById("filter-category");
  const cur = sel.value;
  sel.innerHTML = `<option value="">${esc(t("filter.allCategories"))}</option>`;
  for (const c of categories) {
    const o = document.createElement("option");
    o.value = c;
    o.textContent = t("cat." + c);
    sel.appendChild(o);
  }
  sel.value = cur;
}

async function loadCategories() {
  const r = await api("/api/categories");
  categories = r.ok ? await r.json() : Object.keys(CATEGORY_ICON_KEYS).filter((c) => !["Internet", "Gateway", "WLAN"].includes(c));
  fillCategoryOptions();
  renderLegend();
}

function shouldAutoGroup(n) {
  return !localStorage.getItem("fox_groups") && n > 25;
}

function maybeAutoGroup() {
  if (shouldAutoGroup(devices.length)) {
    groupMode = "subnet";
    localStorage.setItem("fox_groups", "subnet");
    const chk = document.getElementById("chk-groups");
    if (chk) chk.checked = true;
    const chkR = document.getElementById("chk-rooms");
    if (chkR) chkR.checked = false;
  }
}

async function loadDevices() {
  const r = await api("/api/devices?" + currentFilters());
  if (!r.ok) return;
  devices = await r.json();
  maybeAutoGroup();
  renderMap();
  renderTable();
}

async function loadMeta() {
  const r = await api("/api/meta");
  if (r.ok) META = await r.json();
  document.getElementById("hdr-version").textContent = META.version ? "v" + META.version : "";
}

async function loadSites() {
  const r = await api("/api/sites");
  if (!r.ok) return;
  const data = await r.json();
  SITES = data.names || [];
  SITE_MAP = data.map || {};
  const sel = document.getElementById("filter-site");
  for (const name of SITES) {
    const o = document.createElement("option");
    o.value = name;
    o.textContent = name;
    sel.appendChild(o);
  }
}

async function loadRooms() {
  const r = await api("/api/rooms");
  if (!r.ok) return;
  const names = await r.json();
  const sel = document.getElementById("filter-room");
  if (!sel) return;
  const cur = sel.value;
  sel.innerHTML = `<option value="">${esc(t("filter.allRooms"))}</option>`;
  for (const name of names) {
    const o = document.createElement("option");
    o.value = name;
    o.textContent = name;
    sel.appendChild(o);
  }
  sel.value = cur;
}

function isIpLike(s) {
  return /^\d+\.\d+\.\d+\.\d+$/.test(s) || (s.includes(":") && !/^([0-9a-f]{2}:){5}[0-9a-f]{2}$/i.test(s) && !s.startsWith("ip:"));
}

// Vorgaenger eines Geraets als Knoten-ID. Reihenfolge: WLAN-Knoten, MAC, IP, Hostname eines bekannten
// Geraets; erst wenn kein Geraet passt, bleibt eine IP als virtueller Gateway-Knoten stehen (v1.5.4: vorher
// wurde eine IP sofort zurueckgegeben, die FRITZ!Box erschien dann doppelt als "Gateway").
// Netzknoten, an denen andere Geraete haengen koennen (Baum-Layout, Kinder-Liste, Zuordnung)
function isNetCategory(c) {
  return c === "Router" || c === "Switch" || c === "Repeater/AP";
}

// Begruendung der automatischen Einordnung (v1.6.0), z. B. "host:iphone" -> "Hostname „iphone“"
function reasonText(d) {
  if (d.category_override) return t("why.manual");
  const r = String(d.category_reason || "");
  if (!r) return "–";
  const i = r.indexOf(":");
  const kind = i < 0 ? r : r.slice(0, i);
  const val = i < 0 ? "" : r.slice(i + 1);
  if (kind === "mesh") return t(val === "master" ? "why.meshMaster" : "why.meshSlave");
  const key = { gateway: "why.gateway", host: "why.host", vendor: "why.vendor", port: "why.port", svc: "why.svc", mdns: "why.model", mac: "why.randomMac" }[kind];
  return key ? t(key, { v: val }) : r;
}

// Anschluss laut FRITZ!Box-Mesh lesbar machen: "LAN:1" -> "LAN 1", "AP:5G:0" -> "5 GHz"
function portLabel(p) {
  const s = String(p || "").toUpperCase();
  const lan = s.match(/^LAN:(\d+)$/);
  if (lan) return "LAN " + lan[1];
  const band = s.match(/:(2|5|6)G(:|$)/);
  if (band) return (band[1] === "2" ? (LANG === "en" ? "2.4" : "2,4") : band[1]) + " GHz";
  return "";
}

function connectionText(d) {
  if (!d.connection) return "–";
  const port = portLabel(d.link_port);
  return d.connection.toUpperCase() + (port ? " · " + port : "");
}

function parentId(d) {
  const ct = d.connected_to || "";
  if (!ct) return null;
  if (ct.startsWith("wlan:")) return ct;
  if (devices.some((x) => x.mac === ct)) return ct;
  const byIp = devices.find((x) => x.ip && x.ip === ct);
  if (byIp) return byIp.mac;
  const lc = ct.toLowerCase();
  const byHost = devices.find((x) => x.hostname && x.hostname.toLowerCase() === lc);
  if (byHost) return byHost.mac;
  return isIpLike(ct) ? ct : null;
}

// Ziel der Internet-Kante: zuerst das Geraet mit der Gateway-IP, sonst den TR-064-Endpunkt
// (z. B. "fritz.box", kann auch mehrere kommasepariert sein) per IP / Hostname auf ein Geraet
// abbilden, sonst virtueller Gateway-Knoten ueber die Gateway-IP (bzw. Endpunkt-IP).
function routerTargetId() {
  // VPN-Knoten (vpn=1) duerfen nie das Ziel der Internet-Kante sein: Ein VPN-Client
  // kann zufaellig denselben Hostnamen wie der TR-064-Endpunkt tragen (z. B. fritz.box
  // auf einer VPN-Adresse wie .201+). Der echte Router haengt am Gateway bzw. an der
  // Endpunkt-IP; ohne Geraetetreffer landet die Kante am virtuellen Gateway-Knoten.
  const notVpn = (x) => !x.vpn;
  if (META.gateway) {
    const g = devices.find((x) => notVpn(x) && x.ip === META.gateway);
    if (g) return g.mac;
  }
  for (const epRaw of (META.wan_endpoint || "").split(",")) {
    const ep = epRaw.split(":")[0].trim().toLowerCase();
    if (!ep) continue;
    const byIp = devices.find((x) => notVpn(x) && x.ip && x.ip.toLowerCase() === ep);
    if (byIp) return byIp.mac;
    const byHost = devices.find((x) => notVpn(x) && (x.hostname || "").toLowerCase() === ep);
    if (byHost) return byHost.mac;
  }
  if (META.gateway) return META.gateway;
  const epIp = (META.wan_endpoint || "").split(",").map((s) => s.split(":")[0].trim()).find((s) => s && isIpLike(s));
  return epIp || null;
}

function buildElements() {
  // Ohne IP nur in der Tabelle, nicht auf der Karte (bis "Ohne IP ausblenden" deaktiviert wird)
  const list = hideNoIp === "1" ? devices.filter((d) => d.ip) : devices;
  const n = Math.max(1, list.length);
  const R = Math.max(220, 32 * Math.sqrt(n));
  const sizes = nodeSizes(list.length);
  const grouping = groupMode === "subnet" || groupMode === "room";
  const groupKeyOf = (d) => (groupMode === "room" ? d.room || "" : d.subnet || "");
  const groupIdOf = (k) => (groupMode === "room" ? "room:" : "subnet:") + k;
  const nodes = [];
  const edges = [];
  const nodeIds = new Set();
  const addNode = (nd) => {
    nodes.push(nd);
    nodeIds.add(nd.data.id);
  };

  // Subnetz-Gruppen zu Beginn auf einem Raster positionieren, damit sie nicht übereinander liegen
  const groupPos = {};
  if (grouping) {
    const keys = groupMode === "room" ? [...new Set(list.map(groupKeyOf))] : [...new Set(list.map(groupKeyOf).filter(Boolean))];
    const cols = Math.max(1, Math.ceil(Math.sqrt(keys.length)));
    const maxCnt = Math.max(1, ...keys.map((k) => list.filter((d) => groupKeyOf(d) === k).length));
    const G = 430 + 26 * Math.sqrt(maxCnt);
    const labelOf = (k) => (groupMode === "room" ? k || t("room.unassigned") : k + (SITE_MAP[k] ? " · " + SITE_MAP[k] : ""));
    keys.forEach((k, gi) => {
      const gx = (gi % cols) * G;
      const gy = Math.floor(gi / cols) * G;
      const gid = groupIdOf(k);
      groupPos[gid] = { x: gx, y: gy };
      addNode({
        data: {
          id: gid,
          label: labelOf(k) + "  (" + list.filter((d) => groupKeyOf(d) === k).length + ")",
          subnet: true, // Markierung "Gruppenrahmen" (Raum-Gruppen eingeschlossen)
          virtual: true,
          status: "online",
        },
        position: { x: gx, y: gy },
      });
    });
  }

  const groupIdx = {};
  list.forEach((d, i) => {
    if (isHiddenByCollapse(d.mac)) return;
    let x = d.x;
    let y = d.y;
    if (typeof x !== "number" || typeof y !== "number") {
      const gk = grouping ? groupKeyOf(d) : null;
      const gp = gk !== null ? groupPos[groupIdOf(gk)] : null;
      if (gp) {
        // Kinder ohne gespeicherte Position ringförmig um das Gruppenzentrum (überlappt nicht mit anderen Gruppen)
        const cnt = list.filter((x) => groupKeyOf(x) === gk).length;
        const k = (groupIdx[gk] = (groupIdx[gk] || 0) + 1);
        const rr = 80 + 13 * Math.sqrt(Math.max(1, cnt));
        const a2 = (k / Math.max(1, cnt)) * Math.PI * 2;
        x = gp.x + Math.cos(a2) * rr;
        y = gp.y + Math.sin(a2) * rr;
      } else {
        const a = (i / n) * Math.PI * 2;
        x = Math.cos(a) * R;
        y = Math.sin(a) * R;
      }
    }
    const kids = childCount(d.mac);
    const fullName = d.hostname || d.ip || d.mac;
    // Zwei Zeilen wie im Soll-Entwurf: Name, darunter "IP · Kategorie" (+N eingeklappt, offline als Text)
    const second = [d.ip && d.ip !== fullName ? d.ip : "", t("cat." + d.category)].filter(Boolean).join(" · ") +
      (collapsed.has(d.mac) && kids ? ` (+${kids})` : "") + (d.status === "offline" ? " · " + t("map.offline") : "") + (d.vpn ? " · " + t("vpn.badge") : "");
    const hub = isNetCategory(d.category);
    const nd = {
      data: {
        id: d.mac,
        label: shortName(fullName) + "\n" + second,
        fullName,
        category: d.category,
        status: d.status,
        icon: iconKeyFor(d.category, d.category_reason, d.hostname),
        size: hub ? sizes.hub : sizes.node,
        root: !!META.gateway && d.ip === META.gateway,
        ports: d.port_count || 0,
        hub,
        name: (d.hostname || d.ip || d.mac).toLowerCase(),
        subnetKey: d.subnet || "",
        vpn: d.vpn ? 1 : 0,
      },
      position: { x, y },
    };
    if (grouping) {
      const gid = groupIdOf(groupKeyOf(d));
      if (groupPos[gid]) nd.data.parent = gid;
    }
    addNode(nd);
  });

  if (META.gateway || META.wan_ip || META.wan_endpoint) {
    addNode({
      data: {
        id: "internet",
        label: t("internet.node") + (META.wan_ip ? "\nWAN " + META.wan_ip : ""),
        fullName: t("internet.node"),
        category: "Internet",
        status: META.wan_status && META.wan_status.toLowerCase() !== "connected" ? "offline" : "online",
        icon: "globe",
        size: sizes.node,
        virtual: true,
        hub: true,
      },
      position: { x: -R * 1.6, y: 0 },
    });
  }

  for (const d of list) {
    if (!nodeIds.has(d.mac)) continue;
    const p = parentId(d);
    if (!p || p === d.mac) continue;
    // Kanten zeigen vom Vorgaenger zum Geraet (Eltern -> Kind), damit das Baum-Layout oben beginnt.
    // Auch bei Subnetz-Gruppierung bleiben die Kanten zwischen Geraeten erhalten; der Rahmen ist nur Hintergrund.
    const pd = devices.find((x) => x.mac === p);
    const siteA = pd && pd.subnet ? SITE_MAP[pd.subnet] || pd.subnet : "";
    const siteB = d.subnet ? SITE_MAP[d.subnet] || d.subnet : "";
    // Kanten zwischen Standorten (z. B. VPN) schwächer zeichnen
    const cross = !!(siteA && siteB && siteA !== siteB);
    edges.push({ data: { id: "e:" + p + ">" + d.mac, source: p, target: d.mac, conn: d.connection || "", cross } });
  }

  const wlanIds = [...new Set(list.filter((d) => (d.connected_to || "").startsWith("wlan:")).map((d) => d.connected_to))];
  for (const w of wlanIds) {
    addNode({ data: { id: w, label: t("wlan.node"), fullName: t("wlan.node"), category: "WLAN", status: "online", icon: "wifi", size: NODE_SIZE, virtual: true, hub: true } });
    const gw = list.find((x) => x.ip === w.slice(5));
    edges.push({ data: { id: "e:" + w, source: gw ? gw.mac : w.slice(5), target: w, conn: "wlan" } });
  }
  const rt = routerTargetId();
  if (rt) {
    edges.push({ data: { id: "e:internet", source: "internet", target: rt, wan: true } });
  }
  for (const e of edges) {
    for (const end of [e.data.source, e.data.target]) {
      if (nodeIds.has(end)) continue;
      if (!isIpLike(end)) continue;
      addNode({
        data: {
          id: end,
          label: t("gw.node", { ip: end }),
          fullName: t("gw.node", { ip: end }),
          category: "Gateway",
          status: "online",
          icon: "router",
          size: HUB_SIZE,
          root: end === META.gateway,
          virtual: true,
          hub: true,
        },
      });
    }
  }
  // Kanten zu Knoten, die nicht angezeigt werden (z. B. offline ausgeblendet oder eingeklappt), entfallen.
  return [...nodes, ...edges.filter((e) => nodeIds.has(e.data.source) && nodeIds.has(e.data.target))];
}

let spotlightNode = null;

function applySpotlight(node) {
  const nhood = node.closedNeighborhood();
  cy.elements().removeClass("spot dim");
  nhood.addClass("spot");
  cy.elements().not(nhood).addClass("dim");
  cy.fit(nhood, 60);
}

function clearSpotlight() {
  spotlightNode = null;
  if (!cy) return;
  cy.elements().removeClass("spot dim");
  cy.fit(undefined, 40);
}

function updateZoomLabels() {
  if (!cy) return;
  const showAll = cy.zoom() >= labelZoomThreshold(devices.length);
  const label = showAll ? "data(label)" : (ele) => (ele.data("hub") ? ele.data("label") : "");
  cy.style().selector("node").style("label", label).update();
}

// Bewegung nur, wenn erwünscht (prefers-reduced-motion), und nur für Zustandswechsel, nicht beim Aufbau.
function motionMs() {
  const reduce = typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  return reduce ? "0ms" : "150ms";
}

function mapStyle(theme) {
  const P = mapPalette(theme);
  const tr = { "transition-property": "border-width, border-color, opacity, line-color, width", "transition-duration": motionMs(), "transition-timing-function": "ease-out" };
  return [
    {
      selector: "node",
      style: {
        label: "data(label)", "font-size": 11, "line-height": 1.35, "text-wrap": "wrap", "text-max-width": "160px",
        "text-valign": "bottom", "text-halign": "center", "text-margin-y": 5, color: P.text,
        "text-outline-color": P.bg, "text-outline-width": 2, "min-zoomed-font-size": 6,
        width: "data(size)", height: "data(size)", shape: "ellipse",
        "background-color": P.body, "border-width": 1.5, "border-color": P.border,
        "background-image": (ele) => iconUri(ele.data("icon") || "unknown", P.icon),
        "background-width": "55%", "background-height": "55%", "background-clip": "none", "background-image-containment": "inside",
        ...tr,
      },
    },
    {
      selector: "node[subnet]",
      style: {
        "background-color": P.frame, "background-opacity": 0.06, "background-image": "none", "border-width": 1.5, "border-style": "dashed",
        "border-color": P.frame, "border-opacity": 0.55, shape: "round-rectangle", label: "data(label)", "text-valign": "top",
        "text-margin-y": -8, "font-size": 12, "font-weight": 600, color: P.frameText, "text-outline-width": 0, padding: 22,
      },
    },
    { selector: "node[?root]", style: { "border-width": 3, "border-color": P.root, "outline-width": 1.5, "outline-style": "dashed", "outline-color": P.root, "outline-opacity": 0.8, "outline-offset": 4 } },
    { selector: "node[category='Repeater/AP']", style: { "border-color": P.repeater } },
    // Offline: nur der Körper wird abgeblendet und gestrichelt, die Beschriftung bleibt lesbar (>= 4,5:1) und nennt "offline"
    { selector: "node[status='offline']", style: { "background-opacity": 0.45, "background-image-opacity": 0.6, "border-style": "dashed", color: P.textOff } },
    // VPN-Client (z. B. FRITZ!Box IPSec/WireGuard): auffaelliger gestrichelter Rand
    { selector: "node[vpn = 1]", style: { "border-style": "dashed", "border-width": 2.5, "border-color": "#f59e0b" } },
    { selector: "node:selected", style: { "border-width": 3, "border-color": P.sel } },
    { selector: "node.hl", style: { "border-width": 4, "border-color": P.hl } },
    { selector: "node.spot", style: { "border-width": 5, "border-color": P.hl } },
    { selector: "edge", style: { "line-color": P.edge, width: 1.5, opacity: 0.8, "curve-style": "straight", ...tr } },
    { selector: "edge[conn='wlan']", style: { "line-style": "dashed", "line-dash-pattern": [5, 4] } },
    { selector: "edge[conn='plc']", style: { "line-style": "dotted" } },
    { selector: "edge[?cross]", style: { opacity: 0.35 } },
    { selector: "edge[?wan]", style: { width: 2, opacity: 0.8 } },
    { selector: "edge.hl", style: { "line-color": P.hl, width: 3, opacity: 1 } },
    { selector: "edge.spot", style: { "line-color": P.hl, width: 3.5, opacity: 1 } },
    { selector: ".dim", style: { opacity: 0.12 } },
  ];
}

// Legende (unten links, einklappbar): Symbole mit Kategorienamen und Linienarten als Textalternative zur Karte
function renderLegend() {
  const box = document.getElementById("legend-list");
  if (!box) return;
  const P = mapPalette();
  const cats = [...new Set([...(categories && categories.length ? categories : Object.keys(CATEGORY_ICON_KEYS)), "Internet"])]
    .filter((c) => CATEGORY_ICON_KEYS[c]);
  const line = (dash) => `<svg width="28" height="10" aria-hidden="true" focusable="false"><line x1="1" y1="5" x2="27" y2="5" stroke="${P.edge}" stroke-width="2"${dash ? ` stroke-dasharray="${dash}"` : ""} stroke-linecap="round"/></svg>`;
  const ring = `<svg width="28" height="28" viewBox="0 0 28 28" aria-hidden="true" focusable="false"><circle cx="14" cy="14" r="8" fill="${P.body}" stroke="${P.root}" stroke-width="3"/><circle cx="14" cy="14" r="12" fill="none" stroke="${P.root}" stroke-width="1.5" stroke-dasharray="3 2"/></svg>`;
  const off = `<svg width="28" height="28" viewBox="0 0 28 28" aria-hidden="true" focusable="false"><circle cx="14" cy="14" r="10" fill="${P.body}" fill-opacity="0.45" stroke="${P.border}" stroke-width="1.5" stroke-dasharray="3 2"/></svg>`;
  box.innerHTML =
    cats.map((c) => `<li><img src="${iconUri(CATEGORY_ICON_KEYS[c], P.icon)}" alt="" width="18" height="18"><span>${esc(c === "Internet" ? t("internet.node") : t("cat." + c))}</span></li>`).join("") +
    `<li>${ring}<span>${esc(t("legend.gateway"))}</span></li>` +
    `<li>${off}<span>${esc(t("legend.offline"))}</span></li>` +
    `<li>${line("")}<span>LAN</span></li>` +
    `<li>${line("5 4")}<span>WLAN</span></li>` +
    `<li>${line("1 4")}<span>${esc(t("legend.plc"))}</span></li>` +
    `<li>${line("").replace('stroke-width="2"', 'stroke-width="2" stroke-opacity="0.35"')}<span>${esc(t("legend.cross"))}</span></li>`;
}

function bindLegend() {
  const det = document.getElementById("map-legend");
  if (!det) return;
  det.open = localStorage.getItem("fox_legend") === "1";
  det.addEventListener("toggle", () => localStorage.setItem("fox_legend", det.open ? "1" : "0"));
}

function renderMap() {
  const container = document.getElementById("map");
  spotlightNode = null;
  if (!cy) {
    cy = cytoscape({
      container,
      style: mapStyle(),
      wheelSensitivity: 0.2,
    });
    cy.on("tap", "node", (e) => {
      if (e.target.data("virtual")) return;
      const id = e.target.data("id");
      if (spotlightNode === id) clearSpotlight();
      else {
        spotlightNode = id;
        applySpotlight(e.target);
      }
      showDetail(id);
    });
    cy.on("tap", (e) => { if (e.target === cy) clearSpotlight(); });
    cy.on("dragfree", "node", (e) => {
      if (EMBED || e.target.data("virtual")) return;
      const p = e.target.position();
      api("/api/device/" + e.target.data("id"), { method: "PATCH", body: JSON.stringify({ x: p.x, y: p.y }) });
    });
    cy.on("zoom", updateZoomLabels);
    // Voller Name als Tooltip (Beschriftung wird ab 20 Zeichen gekürzt)
    cy.on("mouseover", "node", (e) => { container.title = e.target.data("fullName") || ""; });
    cy.on("mouseout", "node", () => { container.title = ""; });
    updateZoomLabels();
  }
  cy.elements().remove();
  lastElements = buildElements();
  cy.add(lastElements);
  applyLayout();
}

async function showDetail(mac) {
  const r = await api("/api/device/" + mac);
  if (!r.ok) return;
  const d = await r.json();
  cy.nodes().removeClass("hl");
  cy.edges().removeClass("hl");
  const isNet = isNetCategory(d.category);
  const children = isNet ? devices.filter((x) => parentId(x) === mac) : [];
  for (const c of children) {
    cy.getElementById(c.mac).addClass("hl");
    cy.edges().filter((e) => e.data("target") === c.mac).addClass("hl");
  }
  const el = document.getElementById("detail-content");
  const hostLinks = webLinks(d).map((l) => `<a href="${esc(safeUrl(l.url))}" target="_blank" rel="noopener noreferrer" class="ext-link">${esc(l.label)}</a>`).join(", ");
  const rows = [
    [t("d.hostname"), esc(d.hostname || d.ip || "") + (hostLinks ? ` (${hostLinks})` : "")], ["IP", esc(d.ip)], ["IPv6", esc(d.ip6 || "\u2013")], [t("d.mac"), (d.mac || "").startsWith("ip:") ? esc(t("d.macUnknown")) : esc(d.mac)], [t("d.vendor"), esc(d.vendor)],
    [t("d.category"), esc(t("cat." + d.category))], [t("d.reason"), esc(reasonText(d))], [t("d.status"), esc(d.status)], [t("d.subnet"), esc(d.subnet)], [t("d.site"), esc(d.site || "–")], [t("d.room"), esc(d.room || "–")], [t("d.source"), esc(d.source)],
    [t("d.vpn"), d.vpn ? t("d.yes") : "–"],
    [t("d.connection"), esc(connectionText(d))], [t("d.connected"), esc(d.layout.connected_to || t("d.auto"))], [t("d.note"), esc(d.note)],
    [t("d.firstSeen"), esc(d.first_seen)], [t("d.lastSeen"), esc(d.last_seen)],
  ];
  let html = `<h2>${esc(d.hostname || d.ip)}</h2><table>` + rows.map(([k, v]) => `<tr><th scope="row">${esc(k)}</th><td>${v ?? ""}</td></tr>`).join("") + "</table>";
  html += `<h3>${t("d.ports", { n: d.ports.length })}</h3><div class="chips">` + (d.ports.map((p) => `<span>${esc(p.port)}${p.service ? " " + esc(p.service) : ""}</span>`).join("") || "–") + "</div>";
  if (children.length) {
    html += `<h3>${t("d.children", { n: children.length })}</h3><ul>` + children.map((c) => `<li><button type="button" class="dev-link" data-mac="${esc(c.mac)}">${esc(c.hostname || c.ip)}</button> (${esc(t("cat." + c.category))})</li>`).join("") + "</ul>";
  }
  if (!EMBED) {
    html += `<h3>${t("d.edit")}</h3><div class="edit-row"><select id="ed-cat">` + categories.map((c) => `<option value="${esc(c)}"${c === d.category ? " selected" : ""}>${esc(t("cat." + c))}</option>`).join("") + `</select><input id="ed-note" type="text" placeholder="${esc(t("cols.note"))}" value="${esc(d.note)}"><input id="ed-room" type="text" maxlength="64" placeholder="${esc(t("det.roomPh"))}" value="${esc(d.room || "")}" aria-label="${esc(t("d.room"))}"><button id="ed-save">${t("btn.save")}</button></div>`;
    const parents = devices.filter((x) => isNetCategory(x.category));
    const cur = d.layout.connected_to || "";
    html += `<h3>${t("d.connected")}</h3><div class="edit-row"><select id="ed-parent"><option value="">${t("d.auto")}</option>` + parents.map((x) => `<option value="${esc(x.mac)}"${cur === x.mac ? " selected" : ""}>${esc(x.hostname || x.ip)} (${esc(x.ip)})</option>`).join("") + `</select><button id="ed-parent-save">${t("btn.set")}</button></div>`;
    if (isNet) {
      const kids = childCount(mac);
      html += `<div class="edit-row"><button id="ed-collapse">${collapsed.has(mac) ? t("collapse.show", { n: kids }) : t("collapse.hide", { n: kids })}</button></div>`;
    }
  }
  html += `<h3>${t("d.history")}</h3><ul>` + d.history.slice(0, 20).map((h) => `<li>${esc(h.ts)} – ${esc(h.status)}</li>`).join("") + "</ul>";
  html += `<h3>${t("d.events")}</h3><ul>` + d.events.map((e) => `<li>${esc(e.ts)} – ${esc(e.type)}${e.detail ? " " + esc(e.detail) : ""}</li>`).join("") + "</ul>";
  // Endgültige Aktion bewusst am Ende des Panels, getrennt von den Bearbeiten-Funktionen
  if (!EMBED) {
    html += `<h3>${t("d.deleteTitle")}</h3><p class="muted" id="ed-delete-hint">${t("d.deleteHint")}</p><div class="edit-row"><button id="ed-delete" class="danger" aria-describedby="ed-delete-hint">${t("btn.deleteDevice")}</button></div>`;
  }
  el.innerHTML = html;
  el.querySelectorAll(".dev-link").forEach((n) => n.addEventListener("click", () => showDetail(n.dataset.mac)));
  const save = document.getElementById("ed-save");
  if (save) {
    save.addEventListener("click", async () => {
      await api("/api/device/" + mac, { method: "PATCH", body: JSON.stringify({ category: document.getElementById("ed-cat").value, note: document.getElementById("ed-note").value, room: document.getElementById("ed-room").value }) });
      await loadDevices();
      showDetail(mac);
    });
  }
  const psave = document.getElementById("ed-parent-save");
  if (psave) {
    psave.addEventListener("click", async () => {
      await api("/api/device/" + mac, { method: "PATCH", body: JSON.stringify({ connected_to: document.getElementById("ed-parent").value }) });
      await loadDevices();
      showDetail(mac);
    });
  }
  const delBtn = document.getElementById("ed-delete");
  if (delBtn) {
    delBtn.addEventListener("click", async () => {
      if (!confirm(t("d.deleteConfirm", { name: d.hostname || d.ip || mac }))) return;
      const res = await api("/api/device/" + mac, { method: "DELETE" });
      if (!res.ok) return;
      hideSidebar();
      await loadDevices();
      document.getElementById("main")?.focus();
    });
  }
  const collapseBtn = document.getElementById("ed-collapse");
  if (collapseBtn) {
    collapseBtn.addEventListener("click", async () => {
      toggleCollapse(mac);
      await loadDevices();
      showDetail(mac);
    });
  }
  showSidebar("detail");
}

function renderTable() {
  const thead = document.querySelector("#device-table thead");
  const tbody = document.querySelector("#device-table tbody");
  const cols = colOrder.map((k) => { const pair = TABLE_COLS.find(([key]) => key === k); return [k, t(pair[1])]; });
  const colgroup = document.querySelector("#device-table colgroup");
  if (colgroup) {
    colgroup.innerHTML = (EMBED ? "" : '<col class="sel-col">') + colOrder.map((k) => `<col data-key="${esc(k)}"${colWidths[k] ? ` style="width:${Number(colWidths[k]) || 0}px"` : ""}>`).join("");
  }
  for (const m of [...selectedMacs]) if (!devices.some((d) => d.mac === m)) selectedMacs.delete(m);
  const selHead = EMBED ? "" : `<th scope="col" class="sel-col"><input type="checkbox" id="sel-all" aria-label="${esc(t("bulk.all"))}"></th>`;
  thead.innerHTML = "<tr>" + selHead + cols.map(([k, label]) => `<th data-key="${esc(k)}" scope="col" draggable="true">${esc(label)}${sortKey === k ? (sortDir > 0 ? " ▲" : " ▼") : ""}<span class="resizer"></span></th>`).join("") + "</tr>";
  thead.querySelectorAll("th[data-key]").forEach((th) => {
    th.addEventListener("click", () => {
      if (suppressSortClick) { suppressSortClick = false; return; }
      const k = th.dataset.key;
      if (sortKey === k) sortDir *= -1; else { sortKey = k; sortDir = 1; }
      renderTable();
    });
    th.addEventListener("keydown", (e) => {
      if (!e.altKey) return;
      const dir = e.key === "ArrowLeft" ? -1 : e.key === "ArrowRight" ? 1 : 0;
      if (!dir) return;
      e.preventDefault();
      const k = th.dataset.key;
      const idx = colOrder.indexOf(k);
      const ni = idx + dir;
      if (ni < 0 || ni >= colOrder.length) return;
      colOrder.splice(ni, 0, colOrder.splice(idx, 1)[0]);
      localStorage.setItem("fox_table_cols", JSON.stringify(colOrder));
      renderTable();
    });
  });
  const rows = [...devices].sort((a, b) => {
    const va = String(a[sortKey] ?? "").toLowerCase();
    const vb = String(b[sortKey] ?? "").toLowerCase();
    return (va < vb ? -1 : va > vb ? 1 : 0) * sortDir;
  });
  tbody.innerHTML = "";
  const frag = document.createDocumentFragment(); // ab ~200 Zeilen spuerbar schneller
  for (const d of rows) {
    const tr = document.createElement("tr");
    if (!EMBED) {
      const td = document.createElement("td");
      td.className = "sel-col";
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.checked = selectedMacs.has(d.mac);
      cb.setAttribute("aria-label", t("bulk.row", { v: d.hostname || d.ip || d.mac }));
      cb.addEventListener("change", () => {
        if (cb.checked) selectedMacs.add(d.mac); else selectedMacs.delete(d.mac);
        tr.classList.toggle("selected", cb.checked);
        updateBulkBar();
      });
      tr.classList.toggle("selected", cb.checked);
      td.appendChild(cb);
      tr.appendChild(td);
    }
    for (const key of colOrder) {
      tr.appendChild(buildCell(d, key));
    }
    tr.tabIndex = 0;
    tr.setAttribute("aria-label", t("row.aria", { v: d.hostname || d.ip || d.mac }));
    tr.addEventListener("click", (e) => { if (e.target.tagName !== "SELECT" && e.target.tagName !== "INPUT") showDetail(d.mac); });
    tr.addEventListener("keydown", (e) => {
      if ((e.key === "Enter" || e.key === " ") && e.target.tagName !== "SELECT" && e.target.tagName !== "INPUT") {
        e.preventDefault();
        showDetail(d.mac);
      }
    });
    frag.appendChild(tr);
  }
  tbody.appendChild(frag);
  const all = document.getElementById("sel-all");
  if (all) {
    all.addEventListener("change", () => {
      if (all.checked) devices.forEach((d) => selectedMacs.add(d.mac)); else selectedMacs.clear();
      renderTable();
      document.getElementById("sel-all")?.focus();
    });
  }
  updateBulkBar();
}

function updateBulkBar() {
  const bar = document.getElementById("bulk-bar");
  if (!bar) return;
  if (EMBED) { bar.hidden = true; return; }
  const n = selectedMacs.size;
  document.getElementById("bulk-count").textContent = t("bulk.count", { n });
  document.getElementById("bulk-apply").disabled = n === 0;
  document.getElementById("bulk-clear").disabled = n === 0;
  const all = document.getElementById("sel-all");
  if (all) {
    all.checked = n > 0 && n === devices.length;
    all.indeterminate = n > 0 && n < devices.length;
  }
  const sel = document.getElementById("bulk-parent");
  const prev = sel.value;
  const parents = devices.filter((x) => isNetCategory(x.category) && !selectedMacs.has(x.mac));
  sel.innerHTML = `<option value="">${esc(t("d.auto"))}</option>` + parents.map((x) => `<option value="${esc(x.mac)}">${esc(x.hostname || x.ip)} (${esc(x.ip)})</option>`).join("");
  if (parents.some((x) => x.mac === prev)) sel.value = prev;
}

function bindBulk() {
  const bar = document.getElementById("bulk-bar");
  if (!bar) return;
  if (EMBED) { bar.hidden = true; return; }
  const result = document.getElementById("bulk-result");
  document.getElementById("bulk-clear").addEventListener("click", () => {
    selectedMacs.clear();
    result.textContent = "";
    renderTable();
  });
  document.getElementById("bulk-apply").addEventListener("click", async () => {
    const macs = [...selectedMacs];
    if (!macs.length) return;
    const target = document.getElementById("bulk-parent").value;
    const r = await api("/api/devices/connect", { method: "POST", body: JSON.stringify({ macs, connected_to: target }) });
    if (r.ok) {
      const body = await r.json();
      result.textContent = t("bulk.done", { n: body.count });
      selectedMacs.clear();
      await loadDevices();
    } else {
      let detail = "";
      try { detail = (await r.json()).detail || ""; } catch (err) { /* ignorieren */ }
      result.textContent = String(detail).includes("cycle") ? t("bulk.errCycle") : t("bulk.err");
    }
  });
}

const WEB_PORTS = { 80: "http", 8080: "http", 443: "https", 8443: "https" };

function webLinks(d) {
  let ports;
  if (Array.isArray(d.ports) && d.ports.length) {
    ports = d.ports.map((p) => (typeof p === "object" ? p.port : p));
  } else {
    ports = String(d.ports_str || "").split(";").map((s) => parseInt(s, 10));
  }
  const links = [];
  if (d.ip) {
    const host = d.ip.includes(":") ? `[${d.ip}]` : d.ip;
    for (const p of ports) {
      const scheme = WEB_PORTS[p];
      if (scheme) {
        links.push({
          url: `${scheme}://${host}${p === 80 || p === 443 ? "" : ":" + p}`,
          port: p,
          scheme,
          label: scheme + (p === 80 || p === 443 ? "" : ":" + p),
        });
      }
    }
  }
  return links;
}

function buildCell(d, key) {
  const td = document.createElement("td");
  if (key === "status") {
    const dot = document.createElement("span");
    dot.className = "status-dot status-" + String(d.status || "").replace(/[^a-z]/gi, "");
    td.appendChild(dot);
    td.appendChild(document.createTextNode(d.status ?? ""));
  } else if (key === "hostname") {
    const label = d.hostname || d.ip || "";
    td.textContent = label;
    td.title = label;
    const links = webLinks(d);
    if (links.length) {
      td.appendChild(document.createTextNode(" ("));
      links.forEach((l, i) => {
        if (i > 0) td.appendChild(document.createTextNode(", "));
        const a = document.createElement("a");
        a.href = l.url;
        a.target = "_blank";
        a.rel = "noopener noreferrer";
        a.textContent = l.label;
        a.title = l.url;
        a.className = "ext-link";
        td.appendChild(a);
      });
      td.appendChild(document.createTextNode(")"));
    }
    if (d.vpn) {
      td.appendChild(document.createTextNode(" "));
      const b = document.createElement("span");
      b.className = "badge-vpn";
      b.textContent = t("vpn.badge");
      b.title = t("vpn.badgeTitle");
      td.appendChild(b);
    }
  } else if (key === "ip6") {
    const v6 = d.ip6 || "";
    td.textContent = v6 || "–";
    td.title = v6;
  } else if (key === "mac") {
    const m = d.mac || "";
    td.textContent = m.startsWith("ip:") ? "–" : m;
    td.title = m.startsWith("ip:") ? `nur IP bekannt (${m.slice(3)})` : m;
  } else if (key === "category") {
    // Gleiches Symbol wie in Karte und Legende; der Kategoriename steht daneben als Text
    const img = document.createElement("img");
    img.className = "cat-icon";
    img.alt = "";
    img.width = 16;
    img.height = 16;
    img.src = iconUri(iconKeyFor(d.category, d.category_reason, d.hostname), mapPalette().icon);
    td.appendChild(img);
    if (EMBED) {
      td.appendChild(document.createTextNode(t("cat." + d.category)));
      td.title = t("cat." + d.category);
      return td;
    }
    const sel = document.createElement("select");
    for (const c of categories) { const o = document.createElement("option"); o.value = c; o.textContent = t("cat." + c); if (c === d.category) o.selected = true; sel.appendChild(o); }
    sel.addEventListener("change", () => api("/api/device/" + d.mac, { method: "PATCH", body: JSON.stringify({ category: sel.value }) }).then(loadDevices));
    td.appendChild(sel);
  } else if (key === "note" && !EMBED) {
    const inp = document.createElement("input");
    inp.value = d.note || "";
    inp.placeholder = t("cols.note");
    inp.addEventListener("change", () => api("/api/device/" + d.mac, { method: "PATCH", body: JSON.stringify({ note: inp.value }) }).then(loadDevices));
    td.appendChild(inp);
  } else {
    td.textContent = d[key] ?? "";
    td.title = String(d[key] ?? "");
  }
  return td;
}

function bindTableDrag() {
  const thead = document.querySelector("#device-table thead");
  let dragKey = null;
  thead.addEventListener("dragstart", (e) => {
    const th = e.target.closest("th[data-key]");
    if (!th) return;
    dragKey = th.dataset.key;
    e.dataTransfer.setData("text/plain", dragKey);
    e.dataTransfer.effectAllowed = "move";
  });
  thead.addEventListener("dragover", (e) => {
    const th = e.target.closest("th[data-key]");
    if (th && dragKey) {
      e.preventDefault();
      th.classList.add("drag-over");
    }
  });
  thead.addEventListener("dragleave", (e) => {
    const th = e.target.closest("th[data-key]");
    if (th) th.classList.remove("drag-over");
  });
  thead.addEventListener("drop", (e) => {
    const th = e.target.closest("th[data-key]");
    if (!th || !dragKey) return;
    e.preventDefault();
    const target = th.dataset.key;
    th.classList.remove("drag-over");
    if (target !== dragKey) {
      colOrder = colOrder.filter((k) => k !== dragKey);
      colOrder.splice(colOrder.indexOf(target), 0, dragKey);
      localStorage.setItem("fox_table_cols", JSON.stringify(colOrder));
      renderTable();
    }
    dragKey = null;
  });
  thead.addEventListener("dragend", () => {
    dragKey = null;
    thead.querySelectorAll("th.drag-over").forEach((t) => t.classList.remove("drag-over"));
  });
  thead.addEventListener("mousedown", (e) => {
    const handle = e.target.closest(".resizer");
    if (!handle) return;
    e.preventDefault();
    e.stopPropagation();
    const th = handle.closest("th");
    const key = th.dataset.key;
    th.draggable = false;
    const startX = e.clientX;
    const startW = colWidths[key] || th.getBoundingClientRect().width || 120;
    let moved = false;
    const onMove = (ev) => {
      const w = Math.max(60, Math.round(startW + (ev.clientX - startX)));
      if (Math.abs(ev.clientX - startX) > 3) moved = true;
      colWidths[key] = w;
      const col = document.querySelector(`#device-table colgroup col[data-key="${key}"]`);
      if (col) col.style.width = w + "px";
    };
    const onUp = () => {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
      th.draggable = true;
      if (moved) suppressSortClick = true;
      localStorage.setItem("fox_table_widths", JSON.stringify(colWidths));
    };
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  });
}

function bindNav() {
  document.querySelectorAll("#nav button").forEach((b) => b.addEventListener("click", () => {
    document.querySelectorAll("#nav button").forEach((x) => { x.classList.remove("active"); x.setAttribute("aria-pressed", "false"); });
    b.classList.add("active");
    b.setAttribute("aria-pressed", "true");
    document.querySelectorAll(".view").forEach((v) => (v.hidden = v.id !== "view-" + b.dataset.view));
    if (b.dataset.view === "map" && cy) setTimeout(() => { cy.resize(); cy.fit(undefined, 40); }, 50);
    if (b.dataset.view === "log") loadLogs();
  }));
}

let logTimer = null;

function startLogTimer() {
  if (logTimer) clearInterval(logTimer);
  logTimer = null;
  if (document.getElementById("log-auto").checked) {
    logTimer = setInterval(() => {
      if (!document.getElementById("view-log").hidden) loadLogs();
    }, 5000);
  }
}

const LOG_LV_RE = /^(\S+ \S+)\s+(DEBUG|INFO|WARNING|WARN|ERROR|CRITICAL)\b(.*)$/;

function renderLogLines(lines) {
  const el = document.getElementById("log-view");
  if (!lines.length) {
    el.textContent = t("log.empty");
    return;
  }
  el.innerHTML = lines
    .map((l) => {
      const m = LOG_LV_RE.exec(l);
      if (!m) return `<div class="log-line">${esc(l)}</div>`;
      const lv = m[2] === "WARNING" ? "WARN" : m[2];
      return `<div class="log-line"><span class="log-ts">${esc(m[1])}</span> <span class="lv lv-${lv}">${lv}</span> <span class="log-msg">${esc(m[3])}</span></div>`;
    })
    .join("");
}

async function loadLogs() {
  const lines = document.getElementById("log-lines").value;
  const level = document.getElementById("log-level").value;
  const r = await api(`/api/logs?lines=${lines}&level=${level}`);
  if (!r.ok) return;
  const data = await r.json();
  renderLogLines(data.lines);
  document.getElementById("log-status").textContent = t("log.meta", { ret: data.returned, total: data.total, file: data.file });
}

function bindLog() {
  document.getElementById("btn-log-refresh").addEventListener("click", loadLogs);
  document.getElementById("log-level").addEventListener("change", loadLogs);
  document.getElementById("log-lines").addEventListener("change", loadLogs);
  document.getElementById("log-auto").addEventListener("change", startLogTimer);
}

function bindFilters() {
  let t = null;
  document.getElementById("search").addEventListener("input", () => { clearTimeout(t); t = setTimeout(loadDevices, 300); });
  document.getElementById("filter-category").addEventListener("change", loadDevices);
  document.getElementById("filter-site").addEventListener("change", loadDevices);
  document.getElementById("filter-room").addEventListener("change", loadDevices);
  const statusSel = document.getElementById("filter-status");
  const btnOnline = document.getElementById("btn-online");
  const syncOnline = () => {
    const on = statusSel.value === "online";
    btnOnline.classList.toggle("toggled", on);
    btnOnline.setAttribute("aria-pressed", String(on));
    localStorage.setItem("fox_online", on ? "1" : "0");
  };
  statusSel.value = localStorage.getItem("fox_online") === "0" ? "" : "online";
  btnOnline.addEventListener("click", () => {
    statusSel.value = statusSel.value === "online" ? "" : "online";
    syncOnline();
    loadDevices();
  });
  statusSel.addEventListener("change", () => { syncOnline(); loadDevices(); });
  syncOnline();
  document.getElementById("btn-theme").addEventListener("click", () => {
    const cur = document.documentElement.dataset.theme;
    applyTheme(cur === "dark" ? "light" : "dark");
  });
  document.getElementById("btn-print").addEventListener("click", () => {
    document.querySelector('[data-view="table"]').click();
    setTimeout(() => window.print(), 100);
  });
  const pdfOri = document.getElementById("pdf-orientation");
  pdfOri.value = localStorage.getItem("fox_pdf_orientation") || "portrait";
  pdfOri.addEventListener("change", () => localStorage.setItem("fox_pdf_orientation", pdfOri.value));
  document.getElementById("btn-pdf").addEventListener("click", async () => {
    const btn = document.getElementById("btn-pdf");
    btn.disabled = true;
    try {
      let image = null;
      if (cy && typeof cy.png === "function") {
        const bg = document.documentElement.dataset.theme === "light" ? "#f8fafc" : "#0f172a";
        image = cy.png({ output: "datauri", full: true, scale: 2, bg });
      }
      const r = await api("/api/export/pdf", { method: "POST", body: JSON.stringify({ image, title: "Netzwerkkarte", orientation: document.getElementById("pdf-orientation").value }) });
      if (!r.ok) throw new Error("HTTP " + r.status);
      const blob = await r.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "fox_netmap-" + new Date().toISOString().replace(/[:.]/g, "-") + ".pdf";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(a.href);
    } catch (e) {
      console.error("PDF-Export fehlgeschlagen", e);
      btn.textContent = t("err.pdf");
      setTimeout(() => { btn.textContent = t("btn.pdf"); }, 2500);
    } finally {
      btn.disabled = false;
    }
  });
}

function bindSidebar() {
  document.getElementById("tab-detail").addEventListener("click", () => activateTab("detail"));
  document.getElementById("tab-settings").addEventListener("click", () => activateTab("settings"));
  document.getElementById("btn-close-detail").addEventListener("click", hideSidebar);
  document.getElementById("btn-settings").addEventListener("click", () => showSidebar("settings"));
  document.getElementById("settings-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const msg = document.getElementById("settings-msg");
    const body = {
      theme: document.getElementById("st-theme").value,
      lang: document.getElementById("st-lang").value,
      scan_interval: parseInt(document.getElementById("st-interval").value, 10),
      subnets: document.getElementById("st-subnets").value,
      scan_timeout: parseFloat(document.getElementById("st-scantimeout").value),
      port_top: parseInt(document.getElementById("st-porttop").value, 10),
      ports: document.getElementById("st-ports").value,
      history_hours: parseInt(document.getElementById("st-history").value, 10),
      device_retention_days: parseInt(document.getElementById("st-retention").value, 10),
      event_retention_days: parseInt(document.getElementById("st-eventretention").value, 10),
      snmp_enabled: document.getElementById("st-snmp").checked,
      snmp_switches: document.getElementById("st-switches").value,
      snmp_community: document.getElementById("st-snmpcommunity").value,
      fritz_url: document.getElementById("st-fritzurl").value,
      fritz_urls: document.getElementById("st-fritzurls").value,
      fritz_user: document.getElementById("st-fritzuser").value,
      notify_webhook: document.getElementById("st-notifywebhook").value,
      notify_gotify: document.getElementById("st-notifygotify").value,
      notify_ntfy: document.getElementById("st-notifyntfy").value,
      auth_enabled: document.getElementById("st-auth").checked,
      auto_export: document.getElementById("st-autoexport").checked,
      auto_export_interval_hours: parseInt(document.getElementById("st-autoexport-interval").value, 10),
      auto_export_dir: document.getElementById("st-autoexportdir").value,
      mdns_enabled: document.getElementById("st-mdns").checked,
      oui_online_enabled: document.getElementById("st-ouionline").checked,
      oui_online_max: parseInt(document.getElementById("st-ouimax").value, 10),
      oui_online_url: document.getElementById("st-ouiurl").value,
      alarm_whitelist: document.getElementById("st-whitelist").value,
      sites: document.getElementById("st-sites").value,
      vpn_pool: document.getElementById("st-vpnpool").value,
    };
    const fritzPassVal = document.getElementById("st-fritzpass").value;
    if (fritzPassVal) body.fritz_pass = fritzPassVal;
    const errs = validateSettings(body);
    if (errs.length) {
      msg.textContent = t("msg.check") + errs.join("; ");
      return;
    }
    const r = await api("/api/settings", { method: "PATCH", body: JSON.stringify(body) });
    if (r.ok) {
      msg.textContent = t("msg.saved");
    } else {
      let detail = "Fehler beim Speichern";
      try { detail = (await r.json()).detail || detail; } catch (err) { /* ignorieren */ }
      msg.textContent = t("msg.rejected") + detail;
    }
  });
  document.getElementById("token-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const hours = document.getElementById("tk-hours").value;
    const r = await api("/api/tokens", {
      method: "POST",
      body: JSON.stringify({
        expires_hours: hours ? parseInt(hours, 10) : null,
        subnets: document.getElementById("tk-subnets").value,
        categories: document.getElementById("tk-categories").value,
      }),
    });
    if (r.ok) {
      const tk = await r.json();
      document.getElementById("token-result").textContent = t("tk.resultPrefix") + location.origin + tk.embed_url + " " + t("tk.once");
      loadTokens();
    }
  });
}

function validIp(s) {
  const m = s.match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/);
  return !!m && m.slice(1).map(Number).every((o) => o <= 255);
}

function validIpAny(s) {
  if (validIp(s)) return true;
  return s.includes(":") && /^[0-9a-fA-F:]+$/.test(s) && s.replace(/:/g, "").length <= 32;
}

function validMac(s) {
  return /^([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}$/.test(s);
}

function validCidr(s) {
  const m = s.match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})\/(\d{1,2})$/);
  return !!m && m.slice(1, 5).map(Number).every((o) => o <= 255) && Number(m[5]) <= 32;
}

function validCidrAny(s) {
  if (validCidr(s)) return true;
  const m = s.match(/^([0-9a-fA-F:]+)\/(\d{1,3})$/);
  return !!m && m[1].includes(":") && m[1].replace(/:/g, "").length <= 32 && Number(m[2]) <= 128;
}

function validSites(str) {
  for (const part of String(str || "").split(";").map((p) => p.trim()).filter(Boolean)) {
    if (!part.includes(":")) return false;
    const name = part.split(":")[0].trim();
    const subs = part.slice(part.indexOf(":") + 1);
    if (!name) return false;
    for (const sn of subs.split(",").map((x) => x.trim()).filter(Boolean))
      if (!validCidrAny(sn)) return false;
  }
  return true;
}

function validateSettings(v) {
  const errs = [];
  if (!Number.isInteger(v.scan_interval) || v.scan_interval < 30 || v.scan_interval > 86400)
    errs.push(t("err.interval"));
  if (!isFinite(v.scan_timeout) || v.scan_timeout < 0.2 || v.scan_timeout > 10)
    errs.push(t("err.scanTimeout"));
  for (const p of String(v.ports || "").split(",").map((x) => x.trim()).filter(Boolean))
    if (!/^\d+$/.test(p) || Number(p) < 1 || Number(p) > 65535) errs.push(t("err.ports", { v: p }));
  for (const key of ["fritz_url", "fritz_urls"]) {
    for (const e of String(v[key] || "").split(",").map((x) => x.trim()).filter(Boolean))
      if (!/^(https?:\/\/|\/?[a-zA-Z0-9.\-]+(:\d+)?$)/.test(e)) errs.push(t("err.endpoint", { v: e }));
  }
  for (const key of ["notify_webhook", "notify_gotify", "notify_ntfy"]) {
    const u = String(v[key] || "").trim();
    if (u && !/^https?:\/\/.+/.test(u)) errs.push(t("err.url", { v: u }));
  }
  if (String(v.snmp_community || "").trim() && /\s/.test(String(v.snmp_community).trim())) errs.push(t("err.community"));
  if (String(v.fritz_pass || "").length > 256) errs.push(t("err.fritzPass"));
  if (!Number.isInteger(v.oui_online_max) || v.oui_online_max < 0 || v.oui_online_max > 200)
    errs.push(t("err.ouiMax"));
  const ouiUrl = String(v.oui_online_url || "").trim();
  if (ouiUrl && !/^https?:\/\/.+/.test(ouiUrl)) errs.push(t("err.url", { v: ouiUrl }));
  const aed = String(v.auto_export_dir || "").trim();
  if (aed && (aed.startsWith("/") || aed.split("/").includes(".."))) errs.push(t("err.exportdir"));
  if (!Number.isInteger(v.port_top) || v.port_top < 0 || v.port_top > 65535)
    errs.push(t("err.porttop"));
  if (!Number.isInteger(v.history_hours) || v.history_hours < 1 || v.history_hours > 87600)
    errs.push(t("err.history"));
  if (!Number.isInteger(v.device_retention_days) || v.device_retention_days < 0 || v.device_retention_days > 3650)
    errs.push(t("err.retention"));
  if (!Number.isInteger(v.event_retention_days) || v.event_retention_days < 0 || v.event_retention_days > 3650)
    errs.push(t("err.eventRetention"));
  if (!Number.isInteger(v.auto_export_interval_hours) || v.auto_export_interval_hours < 0 || v.auto_export_interval_hours > 720)
    errs.push(t("err.intervalExport"));
  for (const e of String(v.alarm_whitelist || "").split(",").map((s) => s.trim()).filter(Boolean))
    if (!validIpAny(e) && !validMac(e)) errs.push(t("err.whitelist", { v: e }));
  if (!validSites(v.sites || "")) errs.push(t("err.sites"));
  for (const tok of String(v.vpn_pool ?? "off").split(",").map((s) => s.trim()).filter(Boolean)) {
    const low = tok.toLowerCase();
    if (low === "auto" || low === "off" || low === "0") continue;
    if (tok.includes("-")) {
      const parts = tok.split("-");
      if (parts.length !== 2 || !validIpAny(parts[0].trim()) || !validIpAny(parts[1].trim())) errs.push(t("err.vpnPool", { v: tok }));
    } else if (!validCidrAny(tok)) errs.push(t("err.vpnPool", { v: tok }));
  }
  if (v.theme !== "dark" && v.theme !== "light") errs.push(t("err.theme"));
  if (v.lang && !LANGS.some(([c]) => c === v.lang)) errs.push(t("err.lang"));
  for (const sn of v.subnets.split(",").map((s) => s.trim()).filter(Boolean))
    if (!validCidrAny(sn)) errs.push(t("err.subnet", { v: sn }));
  for (const ip of v.snmp_switches.split(",").map((s) => s.trim()).filter(Boolean))
    if (!validIp(ip)) errs.push(t("err.snmp", { v: ip }));
  return errs;
}

function bindLayout() {
  const sel = document.getElementById("layout-select");
  sel.value = currentLayout();
  sel.addEventListener("change", () => {
    localStorage.setItem("fox_layout", sel.value);
    applyLayout();
  });
  document.getElementById("btn-layout-reset").addEventListener("click", async () => {
    await api("/api/layout/reset", { method: "POST" });
    await loadDevices();
  });
}

function bindGroups() {
  const chk = document.getElementById("chk-groups");
  const chkR = document.getElementById("chk-rooms");
  if (chk) {
    chk.checked = groupMode === "subnet";
    chk.addEventListener("change", () => {
      groupMode = chk.checked ? "subnet" : "none";
      if (chk.checked && chkR) chkR.checked = false;
      localStorage.setItem("fox_groups", groupMode);
      renderMap();
    });
  }
  if (chkR) {
    chkR.checked = groupMode === "room";
    chkR.addEventListener("change", () => {
      groupMode = chkR.checked ? "room" : "none";
      if (chkR.checked && chk) chk.checked = false;
      localStorage.setItem("fox_groups", groupMode);
      renderMap();
    });
  }
  const noip = document.getElementById("chk-noip");
  if (noip) {
    noip.checked = hideNoIp === "1";
    noip.addEventListener("change", () => {
      hideNoIp = noip.checked ? "1" : "0";
      localStorage.setItem("fox_noip", hideNoIp);
      renderMap();
    });
  }
}

function bindScan() {
  const btn = document.getElementById("btn-scan");
  if (EMBED) return;
  btn.addEventListener("click", async () => { await api("/api/scan", { method: "POST" }); pollScanStatus(); });
}

let lastScanSeen = null;
let wasScanning = false;

async function pollScanStatus() {
  const r = await api("/api/scan/status");
  if (!r.ok) return;
  const s = await r.json();
  const el = document.getElementById("scan-status");
  el.classList.toggle("running", !!s.scanning);
  const text =
    (s.scanning ? t("scan.running") : "") +
    (s.last_scan ? t("scan.last") + s.last_scan : t("scan.none")) +
    (s.next_scan ? t("scan.next") + s.next_scan : "");
  // Live-Region nur bei echter Änderung neu schreiben, sonst lesen Screenreader alle 5 s dasselbe vor.
  if (el.textContent !== text) el.textContent = text;
  if (!s.scanning && (wasScanning || (s.last_scan && s.last_scan !== lastScanSeen))) loadDevices();
  wasScanning = !!s.scanning;
  if (s.last_scan) lastScanSeen = s.last_scan;
}

async function loadSettings() {
  const r = await api("/api/settings");
  if (!r.ok) return;
  const s = await r.json();
  document.getElementById("st-theme").value = s.theme;
  document.getElementById("st-lang").value = s.lang || "de";
  document.getElementById("st-interval").value = s.scan_interval;
  document.getElementById("st-subnets").value = s.subnets;
  document.getElementById("st-scantimeout").value = s.scan_timeout;
  document.getElementById("st-porttop").value = s.port_top;
  document.getElementById("st-ports").value = s.ports || "";
  document.getElementById("st-snmpcommunity").value = s.snmp_community || "";
  document.getElementById("st-fritzurl").value = s.fritz_url || "";
  document.getElementById("st-fritzurls").value = s.fritz_urls || "";
  document.getElementById("st-fritzuser").value = s.fritz_user || "";
  document.getElementById("st-notifywebhook").value = s.notify_webhook || "";
  document.getElementById("st-notifygotify").value = s.notify_gotify || "";
  document.getElementById("st-notifyntfy").value = s.notify_ntfy || "";
  document.getElementById("st-autoexportdir").value = s.auto_export_dir || "";
  document.getElementById("st-ouionline").checked = !!s.oui_online_enabled;
  document.getElementById("st-ouimax").value = s.oui_online_max ?? 10;
  document.getElementById("st-ouiurl").value = s.oui_online_url || "";
  document.getElementById("st-history").value = s.history_hours;
  document.getElementById("st-retention").value = s.device_retention_days;
  document.getElementById("st-eventretention").value = s.event_retention_days ?? 90;
  document.getElementById("st-snmp").checked = String(s.snmp_enabled) === "true" || s.snmp_enabled === true;
  document.getElementById("st-switches").value = s.snmp_switches;
  document.getElementById("st-auth").checked = String(s.auth_enabled) === "true" || s.auth_enabled === true;
  document.getElementById("st-autoexport").checked = String(s.auto_export) === "true" || s.auto_export === true;
  document.getElementById("st-autoexport-interval").value = s.auto_export_interval_hours;
  document.getElementById("st-mdns").checked = String(s.mdns_enabled) === "true" || s.mdns_enabled === true;
  document.getElementById("st-whitelist").value = s.alarm_whitelist || "";
  document.getElementById("st-sites").value = s.sites || "";
  document.getElementById("st-vpnpool").value = s.vpn_pool || "off";
  loadTokens();
}

async function loadTokens() {
  const r = await api("/api/tokens");
  if (!r.ok) return;
  const list = await r.json();
  const ul = document.getElementById("token-list");
  ul.innerHTML = "";
  for (const tk of list) {
    const li = document.createElement("li");
    li.textContent = `${location.origin}/embed?token=${tk.hint}… (${t("tok.expires")}${tk.expires || t("tok.never")}, ${t("tok.subnets")}${tk.subnets || t("tok.all")}, ${t("tok.cats")}${tk.categories || t("tok.all")}) `;
    const del = document.createElement("button");
    del.textContent = t("tok.delete");
    del.setAttribute("aria-label", t("tok.delete") + " " + tk.hint + "…");
    del.addEventListener("click", async () => { await api("/api/tokens/" + encodeURIComponent(tk.id), { method: "DELETE" }); loadTokens(); });
    li.appendChild(del);
    ul.appendChild(li);
  }
}

function fillLangSelects() {
  for (const sel of [document.getElementById("lang-select"), document.getElementById("st-lang")]) {
    if (!sel) continue;
    sel.innerHTML = "";
    for (const [code, name] of LANGS) {
      const o = document.createElement("option");
      o.value = code;
      o.textContent = name;
      sel.appendChild(o);
    }
    sel.value = LANG;
  }
}

async function setLang(l) {
  if (!LANGS.some(([c]) => c === l)) l = "de";
  LANG = l;
  localStorage.setItem("fox_lang", l);
  fillLangSelects();
  applyI18n();
  renderTable();
  fillCategoryOptions();
  renderLegend();
  if (cy) renderMap();
  if (!EMBED) await api("/api/settings", { method: "PATCH", body: JSON.stringify({ lang: l }) });
}

async function init() {
  applyTheme();
  fillLangSelects();
  applyI18n();
  document.getElementById("lang-select").addEventListener("change", (e) => setLang(e.target.value));
  if (!EMBED) {
    const me = await api("/api/me");
    if (me.status === 401) return;
    document.getElementById("btn-logout").addEventListener("click", async () => {
      await api("/api/logout", { method: "POST" });
      location.href = "/login";
    });
  } else {
    document.body.classList.add("embed");
  }
  if (!EMBED) {
    const rs = await api("/api/settings");
    if (rs.ok) {
      const sv = await rs.json();
      if (sv.lang && LANGS.some(([c]) => c === sv.lang) && sv.lang !== LANG) {
        LANG = sv.lang;
        localStorage.setItem("fox_lang", LANG);
        fillLangSelects();
        applyI18n();
      }
    }
  }
  await loadCategories();
  await loadMeta();
  await loadSites();
  await loadRooms();
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") clearSpotlight(); });
  bindNav();
  bindFilters();
  bindSidebar();
  bindScan();
  bindTableDrag();
  bindBulk();
  bindLegend();
  bindLog();
  bindLayout();
  bindGroups();
  startLogTimer();
  await loadDevices();
  pollScanStatus();
  setInterval(pollScanStatus, 5000);
}

init();
