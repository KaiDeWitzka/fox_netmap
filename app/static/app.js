"use strict";

const EMBED = location.pathname.startsWith("/embed");
const TOKEN = new URLSearchParams(location.search).get("token") || "";

const CATEGORY_COLORS = {
  Router: "#f97316",
  Switch: "#38bdf8",
  "Server/NAS": "#a78bfa",
  Client: "#34d399",
  Drucker: "#f472b6",
  "Smart-Home/IoT": "#facc15",
  Unbekannt: "#9ca3af",
  WLAN: "#e879f9",
  Internet: "#94a3b8",
  Gateway: "#38bdf8",
};

const CATEGORY_ICONS = {
  Router: "📡",
  Switch: "🔀",
  "Server/NAS": "🖥️",
  Client: "💻",
  Drucker: "🖨️",
  "Smart-Home/IoT": "💡",
  Unbekannt: "❓",
  WLAN: "📶",
  Internet: "🌐",
};

let META = { gateway: "", wan_ip: "", wan_status: "" };
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
  ["hostname", "cols.hostname"], ["ip", "cols.ip"], ["mac", "cols.mac"], ["vendor", "cols.vendor"], ["source", "cols.source"],
  ["category", "cols.category"], ["status", "cols.status"], ["subnet", "cols.subnet"], ["site", "cols.site"],
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

const LAYOUTS = { force: "cose", tree: "breadthfirst", circle: "circle", concentric: "concentric", grid: "grid" };

function currentLayout() {
  return localStorage.getItem("fox_layout") || "auto";
}

function applyLayout() {
  if (!cy || !devices.length) return;
  const choice = currentLayout();
  const hasPos = devices.every((d) => typeof d.x === "number" && typeof d.y === "number");
  let opts;
  if (choice === "auto") {
    if (hasPos) {
      opts = { name: "preset" };
    } else {
      const big = devices.length > 60;
      opts = {
        name: "cose", animate: false, padding: 30,
        idealEdgeLength: big ? 90 : 130,
        nodeRepulsion: big ? 22000 : 12000,
        nodeOverlap: big ? 30 : 20,
        spacingFactor: big ? 1.25 : 1.1,
      };
    }
  } else if (choice === "tree") {
    opts = { name: "breadthfirst", directed: true, spacingFactor: 1.3, animate: false };
  } else {
    opts = { name: LAYOUTS[choice], animate: false };
  }
  cy.layout(opts).run();
  cy.fit(undefined, 40);
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
}

function currentFilters() {
  const p = new URLSearchParams();
  const q = document.getElementById("search").value.trim();
  const c = document.getElementById("filter-category").value;
  const s = document.getElementById("filter-status").value;
  const site = document.getElementById("filter-site").value;
  if (q) p.set("q", q);
  if (c) p.set("category", c);
  if (s) p.set("status", s);
  if (site) p.set("site", site);
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
  categories = r.ok ? await r.json() : Object.keys(CATEGORY_COLORS);
  fillCategoryOptions();
}

function shouldAutoGroup(n) {
  return !localStorage.getItem("fox_groups") && n > 40;
}

function maybeAutoGroup() {
  if (shouldAutoGroup(devices.length)) {
    groupMode = "subnet";
    localStorage.setItem("fox_groups", "subnet");
    const chk = document.getElementById("chk-groups");
    if (chk) chk.checked = true;
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

function parentId(d) {
  const ct = d.connected_to || "";
  if (!ct) return null;
  if (ct.startsWith("wlan:")) return ct;
  if (devices.some((x) => x.mac === ct)) return ct;
  if (/^\d+\.\d+\.\d+\.\d+$/.test(ct) || ct.includes(":")) return ct;
  const byIp = devices.find((x) => x.ip === ct);
  return byIp ? byIp.mac : null;
}

function buildElements() {
  const n = Math.max(1, devices.length);
  const R = Math.max(220, 32 * Math.sqrt(n));
  const grouping = groupMode === "subnet";
  const nodes = [];
  const edges = [];
  const nodeIds = new Set();
  const addNode = (nd) => {
    nodes.push(nd);
    nodeIds.add(nd.data.id);
  };

  if (grouping) {
    for (const sn of [...new Set(devices.map((d) => d.subnet).filter(Boolean))]) {
      const siteName = SITE_MAP[sn] || "";
      addNode({
        data: {
          id: "subnet:" + sn,
          label: (siteName ? siteName + " · " : "") + sn + "  (" + devices.filter((d) => d.subnet === sn).length + ")",
          subnet: true,
          virtual: true,
          status: "online",
          color: CATEGORY_COLORS.Gateway,
        },
      });
    }
  }

  devices.forEach((d, i) => {
    if (isHiddenByCollapse(d.mac)) return;
    let x = d.x;
    let y = d.y;
    if (typeof x !== "number" || typeof y !== "number") {
      const a = (i / n) * Math.PI * 2;
      x = Math.cos(a) * R;
      y = Math.sin(a) * R;
    }
    const kids = childCount(d.mac);
    const label =
      (CATEGORY_ICONS[d.category] || "❓") + " " + (d.hostname || d.ip || d.mac) + (collapsed.has(d.mac) && kids ? ` (+${kids})` : "");
    const nd = {
      data: {
        id: d.mac,
        label,
        category: d.category,
        status: d.status,
        color: CATEGORY_COLORS[d.category] || CATEGORY_COLORS.Unbekannt,
        ports: d.port_count || 0,
      },
      position: { x, y },
    };
    if (grouping && d.subnet) nd.data.parent = "subnet:" + d.subnet;
    addNode(nd);
  });

  if (META.gateway || META.wan_ip) {
    addNode({
      data: {
        id: "internet",
        label: t("internet.node") + (META.wan_ip ? "  " + META.wan_ip : ""),
        category: "Internet",
        status: "online",
        color: CATEGORY_COLORS.Internet,
        virtual: true,
      },
      position: { x: -R * 1.6, y: 0 },
    });
  }

  for (const d of devices) {
    if (!nodeIds.has(d.mac)) continue;
    const p = parentId(d);
    if (!p || p === d.mac) continue;
    let src = d.mac;
    let tgt = p;
    if (grouping && d.subnet) {
      const pDev = devices.find((x) => x.mac === p) || devices.find((x) => x.ip === p);
      if (pDev) {
        const g1 = groupOf(d);
        const g2 = groupOf(pDev);
        if (g1 && g2 && g1 === g2) continue;
        if (g1) {
          src = g1;
          if (g2) tgt = g2;
        }
      }
    }
    edges.push({ data: { source: src, target: tgt } });
  }

  const wlanIds = [...new Set(devices.filter((d) => (d.connected_to || "").startsWith("wlan:")).map((d) => d.connected_to))];
  for (const w of wlanIds) {
    addNode({ data: { id: w, label: t("wlan.node"), category: "WLAN", status: "online", color: CATEGORY_COLORS.WLAN, virtual: true } });
    const gw = devices.find((x) => x.ip === w.slice(5));
    edges.push({ data: { source: w, target: gw ? gw.mac : w.slice(5) } });
  }
  if (META.gateway) {
    const gw = devices.find((x) => x.ip === META.gateway);
    edges.push({ data: { source: "internet", target: gw ? gw.mac : META.gateway } });
  }
  for (const e of edges) {
    if (!nodeIds.has(e.data.target)) {
      addNode({
        data: {
          id: e.data.target,
          label: t("gw.node", { ip: e.data.target }),
          category: "Gateway",
          status: "online",
          color: CATEGORY_COLORS.Gateway,
          virtual: true,
        },
      });
    }
  }
  return [...nodes, ...edges];
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
  const show = cy.zoom() >= 0.85;
  cy.style().selector("node").style("label", show ? "data(label)" : "").update();
}

function renderMap() {
  const container = document.getElementById("map");
  spotlightNode = null;
  if (!cy) {
    cy = cytoscape({
      container,
      style: [
        { selector: "node", style: { label: "data(label)", "font-size": 9, "text-valign": "bottom", "text-margin-y": 4, width: 20, height: 20, "background-color": "data(color)", color: "#e2e8f0", "text-background-color": "#0f172a", "text-background-opacity": 0.7, "text-background-padding": 2 } },
        { selector: "node[subnet]", style: { "background-color": "#38bdf8", "background-opacity": 0.07, "border-width": 1.5, "border-color": "#38bdf8", "border-opacity": 0.55, label: "data(label)", "text-valign": "top", "text-margin-y": -8, "font-size": 12, "font-weight": 600, color: "#94a3b8", padding: 22 } },
        { selector: "node[status='offline']", style: { opacity: 0.4 } },
        { selector: "node:selected", style: { "border-width": 3, "border-color": "#fff" } },
        { selector: "node.hl", style: { "border-width": 4, "border-color": "#facc15" } },
        { selector: "node.spot", style: { "border-width": 5, "border-color": "#facc15" } },
        { selector: "edge", style: { "line-color": "#64748b", width: 1, opacity: 0.45, "curve-style": "bezier" } },
        { selector: "edge.hl", style: { "line-color": "#facc15", width: 3 } },
        { selector: "edge.spot", style: { "line-color": "#facc15", width: 3.5 } },
        { selector: ".dim", style: { opacity: 0.12 } },
      ],
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
    updateZoomLabels();
  }
  cy.elements().remove();
  cy.add(buildElements());
  applyLayout();
}

async function showDetail(mac) {
  const r = await api("/api/device/" + mac);
  if (!r.ok) return;
  const d = await r.json();
  cy.nodes().removeClass("hl");
  cy.edges().removeClass("hl");
  const isNet = d.category === "Router" || d.category === "Switch";
  const children = isNet ? devices.filter((x) => parentId(x) === mac) : [];
  for (const c of children) {
    cy.getElementById(c.mac).addClass("hl");
    cy.edges().filter((e) => e.data("source") === c.mac).addClass("hl");
  }
  const el = document.getElementById("detail-content");
  const hostLinks = webLinks(d).map((l) => `<a href="${esc(safeUrl(l.url))}" target="_blank" rel="noopener noreferrer" class="ext-link">${esc(l.label)}</a>`).join(", ");
  const rows = [
    [t("d.hostname"), esc(d.hostname || d.ip || "") + (hostLinks ? ` (${hostLinks})` : "")], ["IP", esc(d.ip)], [t("d.mac"), (d.mac || "").startsWith("ip:") ? esc(t("d.macUnknown")) : esc(d.mac)], [t("d.vendor"), esc(d.vendor)],
    [t("d.category"), esc(t("cat." + d.category))], [t("d.status"), esc(d.status)], [t("d.subnet"), esc(d.subnet)], [t("d.site"), esc(d.site || "–")], [t("d.source"), esc(d.source)],
    [t("d.connection"), esc(d.connection ? d.connection.toUpperCase() : "–")], [t("d.connected"), esc(d.layout.connected_to || t("d.auto"))], [t("d.note"), esc(d.note)],
    [t("d.firstSeen"), esc(d.first_seen)], [t("d.lastSeen"), esc(d.last_seen)],
  ];
  let html = `<h2>${esc(d.hostname || d.ip)}</h2><table>` + rows.map(([k, v]) => `<tr><th scope="row">${esc(k)}</th><td>${v ?? ""}</td></tr>`).join("") + "</table>";
  html += `<h3>${t("d.ports", { n: d.ports.length })}</h3><div class="chips">` + (d.ports.map((p) => `<span>${esc(p.port)}${p.service ? " " + esc(p.service) : ""}</span>`).join("") || "–") + "</div>";
  if (children.length) {
    html += `<h3>${t("d.children", { n: children.length })}</h3><ul>` + children.map((c) => `<li><button type="button" class="dev-link" data-mac="${esc(c.mac)}">${esc(c.hostname || c.ip)}</button> (${esc(t("cat." + c.category))})</li>`).join("") + "</ul>";
  }
  if (!EMBED) {
    html += `<h3>${t("d.edit")}</h3><div class="edit-row"><select id="ed-cat">` + categories.map((c) => `<option value="${esc(c)}"${c === d.category ? " selected" : ""}>${esc(t("cat." + c))}</option>`).join("") + `</select><input id="ed-note" type="text" placeholder="${esc(t("cols.note"))}" value="${esc(d.note)}"><button id="ed-save">${t("btn.save")}</button></div>`;
    const parents = devices.filter((x) => x.category === "Router" || x.category === "Switch");
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
      await api("/api/device/" + mac, { method: "PATCH", body: JSON.stringify({ category: document.getElementById("ed-cat").value, note: document.getElementById("ed-note").value }) });
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
    colgroup.innerHTML = colOrder.map((k) => `<col data-key="${esc(k)}"${colWidths[k] ? ` style="width:${Number(colWidths[k]) || 0}px"` : ""}>`).join("");
  }
  thead.innerHTML = "<tr>" + cols.map(([k, label]) => `<th data-key="${esc(k)}" scope="col" draggable="true">${esc(label)}${sortKey === k ? (sortDir > 0 ? " ▲" : " ▼") : ""}<span class="resizer"></span></th>`).join("") + "</tr>";
  thead.querySelectorAll("th").forEach((th) => {
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
  for (const d of rows) {
    const tr = document.createElement("tr");
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
    tbody.appendChild(tr);
  }
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
  } else if (key === "mac") {
    const m = d.mac || "";
    td.textContent = m.startsWith("ip:") ? "–" : m;
    td.title = m.startsWith("ip:") ? `nur IP bekannt (${m.slice(3)})` : m;
  } else if (key === "category" && !EMBED) {
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
    const th = e.target.closest("th");
    if (!th) return;
    dragKey = th.dataset.key;
    e.dataTransfer.setData("text/plain", dragKey);
    e.dataTransfer.effectAllowed = "move";
  });
  thead.addEventListener("dragover", (e) => {
    const th = e.target.closest("th");
    if (th && dragKey) {
      e.preventDefault();
      th.classList.add("drag-over");
    }
  });
  thead.addEventListener("dragleave", (e) => {
    const th = e.target.closest("th");
    if (th) th.classList.remove("drag-over");
  });
  thead.addEventListener("drop", (e) => {
    const th = e.target.closest("th");
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
  const statusSel = document.getElementById("filter-status");
  const btnOnline = document.getElementById("btn-online");
  const syncOnline = () => {
    const on = statusSel.value === "online";
    btnOnline.classList.toggle("toggled", on);
    btnOnline.setAttribute("aria-pressed", String(on));
  };
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
      document.getElementById("token-result").textContent = t("tk.resultPrefix") + location.origin + tk.embed_url;
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
  if (!Number.isInteger(v.auto_export_interval_hours) || v.auto_export_interval_hours < 0 || v.auto_export_interval_hours > 720)
    errs.push(t("err.intervalExport"));
  for (const e of String(v.alarm_whitelist || "").split(",").map((s) => s.trim()).filter(Boolean))
    if (!validIpAny(e) && !validMac(e)) errs.push(t("err.whitelist", { v: e }));
  if (!validSites(v.sites || "")) errs.push(t("err.sites"));
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
  if (!chk) return;
  chk.checked = groupMode === "subnet";
  chk.addEventListener("change", () => {
    groupMode = chk.checked ? "subnet" : "none";
    localStorage.setItem("fox_groups", groupMode);
    renderMap();
  });
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
  document.getElementById("st-snmp").checked = String(s.snmp_enabled) === "true" || s.snmp_enabled === true;
  document.getElementById("st-switches").value = s.snmp_switches;
  document.getElementById("st-auth").checked = String(s.auth_enabled) === "true" || s.auth_enabled === true;
  document.getElementById("st-autoexport").checked = String(s.auto_export) === "true" || s.auto_export === true;
  document.getElementById("st-autoexport-interval").value = s.auto_export_interval_hours;
  document.getElementById("st-mdns").checked = String(s.mdns_enabled) === "true" || s.mdns_enabled === true;
  document.getElementById("st-whitelist").value = s.alarm_whitelist || "";
  document.getElementById("st-sites").value = s.sites || "";
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
    li.textContent = `${location.origin}/embed?token=${tk.token} (${t("tok.expires")}${tk.expires || t("tok.never")}, ${t("tok.subnets")}${tk.subnets || t("tok.all")}, ${t("tok.cats")}${tk.categories || t("tok.all")}) `;
    const del = document.createElement("button");
    del.textContent = t("tok.delete");
    del.addEventListener("click", async () => { await api("/api/tokens/" + tk.token, { method: "DELETE" }); loadTokens(); });
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
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") clearSpotlight(); });
  bindNav();
  bindFilters();
  bindSidebar();
  bindScan();
  bindTableDrag();
  bindLog();
  bindLayout();
  bindGroups();
  startLogTimer();
  await loadDevices();
  pollScanStatus();
  setInterval(pollScanStatus, 5000);
}

init();
