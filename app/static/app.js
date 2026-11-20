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
};

let devices = [];
let categories = [];
let cy = null;
let sortKey = "hostname";
let sortDir = 1;

const TABLE_COLS = [
  ["hostname", "Hostname"], ["ip", "IP"], ["mac", "MAC"], ["vendor", "Hersteller"], ["source", "Quelle"],
  ["category", "Kategorie"], ["status", "Status"], ["subnet", "Subnetz"],
  ["ports_str", "Ports"], ["connected_to", "Verbunden mit"], ["note", "Notiz"], ["last_seen", "Zuletzt gesehen"],
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
  if (q) p.set("q", q);
  if (c) p.set("category", c);
  if (s) p.set("status", s);
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
  document.getElementById("tab-detail").classList.toggle("active", isDetail);
  document.getElementById("tab-settings").classList.toggle("active", !isDetail);
  document.getElementById("detail-content").hidden = !isDetail;
  document.getElementById("settings-content").hidden = isDetail;
  if (!isDetail) loadSettings();
}

async function loadCategories() {
  const r = await api("/api/categories");
  categories = r.ok ? await r.json() : Object.keys(CATEGORY_COLORS);
  const sel = document.getElementById("filter-category");
  for (const c of categories) {
    const o = document.createElement("option");
    o.value = c;
    o.textContent = c;
    sel.appendChild(o);
  }
}

async function loadDevices() {
  const r = await api("/api/devices?" + currentFilters());
  if (!r.ok) return;
  devices = await r.json();
  renderMap();
  renderTable();
}

function parentId(d) {
  const ct = d.connected_to || "";
  if (!ct) return null;
  if (devices.some((x) => x.mac === ct)) return ct;
  const byIp = devices.find((x) => x.ip === ct);
  return byIp ? byIp.mac : null;
}

function buildElements() {
  const nodes = devices.map((d) => ({
    data: {
      id: d.mac,
      label: d.hostname || d.ip || d.mac,
      category: d.category,
      status: d.status,
      color: CATEGORY_COLORS[d.category] || CATEGORY_COLORS.Unbekannt,
      ports: d.port_count || 0,
    },
    position: { x: d.x || 0, y: d.y || 0 },
  }));
  const edges = [];
  for (const d of devices) {
    const p = parentId(d);
    if (p && p !== d.mac) edges.push({ data: { source: d.mac, target: p } });
  }
  return [...nodes, ...edges];
}

function renderMap() {
  const container = document.getElementById("map");
  if (!cy) {
    cy = cytoscape({
      container,
      style: [
        { selector: "node", style: { label: "data(label)", "font-size": 10, "text-valign": "bottom", "text-margin-y": 5, width: 26, height: 26, "background-color": "data(color)", color: "#e2e8f0", "text-background-color": "#0f172a", "text-background-opacity": 0.7, "text-background-padding": 2 } },
        { selector: "node[status='offline']", style: { opacity: 0.4 } },
        { selector: "node:selected", style: { "border-width": 3, "border-color": "#fff" } },
        { selector: "node.hl", style: { "border-width": 4, "border-color": "#facc15" } },
        { selector: "edge", style: { "line-color": "#64748b", width: 1.5, "curve-style": "bezier" } },
        { selector: "edge.hl", style: { "line-color": "#facc15", width: 3 } },
      ],
      wheelSensitivity: 0.2,
    });
    cy.on("tap", "node", (e) => showDetail(e.target.data("id")));
    cy.on("dragfree", "node", (e) => {
      if (EMBED) return;
      const p = e.target.position();
      api("/api/device/" + e.target.data("id"), { method: "PATCH", body: JSON.stringify({ x: p.x, y: p.y }) });
    });
  }
  cy.elements().remove();
  cy.add(buildElements());
  const hasPos = devices.length > 0 && devices.every((d) => typeof d.x === "number" && typeof d.y === "number");
  cy.layout(hasPos ? { name: "preset" } : { name: "breadthfirst", directed: true, spacingFactor: 1.3, animate: false }).run();
  cy.fit(undefined, 40);
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
  const hostLinks = webLinks(d).map((l) => `<a href="${l.url}" target="_blank" rel="noopener noreferrer" style="color:var(--accent)">${l.label}</a>`).join(", ");
  const rows = [
    ["Hostname", (d.hostname || d.ip || "") + (hostLinks ? ` (${hostLinks})` : "")], ["IP", d.ip], ["MAC", (d.mac || "").startsWith("ip:") ? "– (nur IP bekannt)" : d.mac], ["Hersteller", d.vendor],
    ["Kategorie", d.category], ["Status", d.status], ["Subnetz", d.subnet], ["Quelle", d.source],
    ["Verbunden mit", d.layout.connected_to || ""], ["Notiz", d.note],
    ["Erstmals gesehen", d.first_seen], ["Zuletzt gesehen", d.last_seen],
  ];
  let html = `<h2>${d.hostname || d.ip}</h2><table>` + rows.map(([k, v]) => `<tr><td>${k}</td><td>${v ?? ""}</td></tr>`).join("") + "</table>";
  html += `<h3>Offene Ports (${d.ports.length})</h3><div class="chips">` + (d.ports.map((p) => `<span>${p.port}${p.service ? " " + p.service : ""}</span>`).join("") || "–") + "</div>";
  if (children.length) {
    html += `<h3>Angeschlossene Geräte (${children.length})</h3><ul>` + children.map((c) => `<li><span class="dev-link" data-mac="${c.mac}">${c.hostname || c.ip}</span> (${c.category})</li>`).join("") + "</ul>";
  }
  if (!EMBED) {
    html += `<h3>Bearbeiten</h3><div class="edit-row"><select id="ed-cat">` + categories.map((c) => `<option ${c === d.category ? "selected" : ""}>${c}</option>`).join("") + `</select><input id="ed-note" type="text" placeholder="Notiz" value="${(d.note || "").replace(/"/g, "&quot;")}"><button id="ed-save">Speichern</button></div>`;
  }
  html += `<h3>Verlauf (neu zuerst)</h3><ul>` + d.history.slice(0, 20).map((h) => `<li>${h.ts} – ${h.status}</li>`).join("") + "</ul>";
  html += `<h3>Ereignisse</h3><ul>` + d.events.map((e) => `<li>${e.ts} – ${e.type}${e.detail ? " " + e.detail : ""}</li>`).join("") + "</ul>";
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
  showSidebar("detail");
}

function renderTable() {
  const thead = document.querySelector("#device-table thead");
  const tbody = document.querySelector("#device-table tbody");
  const cols = colOrder.map((k) => TABLE_COLS.find(([key]) => key === k));
  const colgroup = document.querySelector("#device-table colgroup");
  if (colgroup) {
    colgroup.innerHTML = colOrder.map((k) => `<col data-key="${k}"${colWidths[k] ? ` style="width:${colWidths[k]}px"` : ""}>`).join("");
  }
  thead.innerHTML = "<tr>" + cols.map(([k, label]) => `<th data-key="${k}" draggable="true">${label}${sortKey === k ? (sortDir > 0 ? " ▲" : " ▼") : ""}<span class="resizer"></span></th>`).join("") + "</tr>";
  thead.querySelectorAll("th").forEach((th) => th.addEventListener("click", () => {
    if (suppressSortClick) { suppressSortClick = false; return; }
    const k = th.dataset.key;
    if (sortKey === k) sortDir *= -1; else { sortKey = k; sortDir = 1; }
    renderTable();
  }));
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
    tr.addEventListener("click", (e) => { if (e.target.tagName !== "SELECT" && e.target.tagName !== "INPUT") showDetail(d.mac); });
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
    for (const p of ports) {
      const scheme = WEB_PORTS[p];
      if (scheme) {
        links.push({
          url: `${scheme}://${d.ip}${p === 80 || p === 443 ? "" : ":" + p}`,
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
    td.innerHTML = `<span class="status-dot status-${d.status}"></span>${d.status}`;
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
        a.style.color = "var(--accent)";
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
    for (const c of categories) { const o = document.createElement("option"); o.value = c; o.textContent = c; if (c === d.category) o.selected = true; sel.appendChild(o); }
    sel.addEventListener("change", () => api("/api/device/" + d.mac, { method: "PATCH", body: JSON.stringify({ category: sel.value }) }).then(loadDevices));
    td.appendChild(sel);
  } else if (key === "note" && !EMBED) {
    const inp = document.createElement("input");
    inp.value = d.note || "";
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
    document.querySelectorAll("#nav button").forEach((x) => x.classList.remove("active"));
    b.classList.add("active");
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

async function loadLogs() {
  const lines = document.getElementById("log-lines").value;
  const level = document.getElementById("log-level").value;
  const r = await api(`/api/logs?lines=${lines}&level=${level}`);
  if (!r.ok) return;
  const data = await r.json();
  document.getElementById("log-view").textContent = data.lines.join("\n") || "(noch keine Log-Eintraege)";
  document.getElementById("log-status").textContent = `${data.returned}/${data.total} Zeilen · ${data.file}`;
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
  document.getElementById("filter-status").addEventListener("change", loadDevices);
  document.getElementById("btn-theme").addEventListener("click", () => {
    const cur = document.documentElement.dataset.theme;
    applyTheme(cur === "dark" ? "light" : "dark");
  });
  document.getElementById("btn-print").addEventListener("click", () => {
    document.querySelector('[data-view="table"]').click();
    setTimeout(() => window.print(), 100);
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
      scan_interval: parseInt(document.getElementById("st-interval").value, 10),
      subnets: document.getElementById("st-subnets").value,
      port_top: parseInt(document.getElementById("st-porttop").value, 10),
      history_hours: parseInt(document.getElementById("st-history").value, 10),
      device_retention_days: parseInt(document.getElementById("st-retention").value, 10),
      snmp_enabled: document.getElementById("st-snmp").checked,
      snmp_switches: document.getElementById("st-switches").value,
      auth_enabled: document.getElementById("st-auth").checked,
      auto_export: document.getElementById("st-autoexport").checked,
    };
    const errs = validateSettings(body);
    if (errs.length) {
      msg.textContent = "Plausibilitätsprüfung: " + errs.join("; ");
      return;
    }
    const r = await api("/api/settings", { method: "PATCH", body: JSON.stringify(body) });
    if (r.ok) {
      msg.textContent = "Gespeichert.";
    } else {
      let detail = "Fehler beim Speichern";
      try { detail = (await r.json()).detail || detail; } catch (err) { /* ignorieren */ }
      msg.textContent = "Abgelehnt: " + detail;
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
      const t = await r.json();
      document.getElementById("token-result").textContent = "Embed-URL: " + location.origin + t.embed_url;
      loadTokens();
    }
  });
}

function validIp(s) {
  const m = s.match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/);
  return !!m && m.slice(1).map(Number).every((o) => o <= 255);
}

function validCidr(s) {
  const m = s.match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})\/(\d{1,2})$/);
  return !!m && m.slice(1, 5).map(Number).every((o) => o <= 255) && Number(m[5]) <= 32;
}

function validateSettings(v) {
  const errs = [];
  if (!Number.isInteger(v.scan_interval) || v.scan_interval < 30 || v.scan_interval > 86400)
    errs.push("Scan-Intervall: 30–86400 s");
  if (!Number.isInteger(v.port_top) || v.port_top < 0 || v.port_top > 65535)
    errs.push("Port-Umfang: 0 (alle) bis 65535");
  if (!Number.isInteger(v.history_hours) || v.history_hours < 1 || v.history_hours > 87600)
    errs.push("Historie: 1–87600 Stunden");
  if (!Number.isInteger(v.device_retention_days) || v.device_retention_days < 0 || v.device_retention_days > 3650)
    errs.push("Retention: 0–3650 Tage (0 = nie löschen)");
  if (v.theme !== "dark" && v.theme !== "light") errs.push("Theme: dark oder light");
  for (const sn of v.subnets.split(",").map((s) => s.trim()).filter(Boolean))
    if (!validCidr(sn)) errs.push(`Subnetz ungültig (CIDR erwartet): ${sn}`);
  for (const ip of v.snmp_switches.split(",").map((s) => s.trim()).filter(Boolean))
    if (!validIp(ip)) errs.push(`SNMP-Switch-IP ungültig: ${ip}`);
  return errs;
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
  el.textContent =
    (s.scanning ? "Scan läuft… " : "") +
    (s.last_scan ? "letzter Scan: " + s.last_scan : "noch kein Scan") +
    (s.next_scan ? " · nächster Scan: " + s.next_scan : "");
  if (!s.scanning && (wasScanning || (s.last_scan && s.last_scan !== lastScanSeen))) loadDevices();
  wasScanning = !!s.scanning;
  if (s.last_scan) lastScanSeen = s.last_scan;
}

async function loadSettings() {
  const r = await api("/api/settings");
  if (!r.ok) return;
  const s = await r.json();
  document.getElementById("st-theme").value = s.theme;
  document.getElementById("st-interval").value = s.scan_interval;
  document.getElementById("st-subnets").value = s.subnets;
  document.getElementById("st-porttop").value = s.port_top;
  document.getElementById("st-history").value = s.history_hours;
  document.getElementById("st-retention").value = s.device_retention_days;
  document.getElementById("st-snmp").checked = String(s.snmp_enabled) === "true" || s.snmp_enabled === true;
  document.getElementById("st-switches").value = s.snmp_switches;
  document.getElementById("st-auth").checked = String(s.auth_enabled) === "true" || s.auth_enabled === true;
  document.getElementById("st-autoexport").checked = String(s.auto_export) === "true" || s.auto_export === true;
  loadTokens();
}

async function loadTokens() {
  const r = await api("/api/tokens");
  if (!r.ok) return;
  const list = await r.json();
  const ul = document.getElementById("token-list");
  ul.innerHTML = "";
  for (const t of list) {
    const li = document.createElement("li");
    li.textContent = `${location.origin}/embed?token=${t.token} (Ablauf: ${t.expires || "nie"}, Subnetze: ${t.subnets || "alle"}, Kategorien: ${t.categories || "alle"}) `;
    const del = document.createElement("button");
    del.textContent = "löschen";
    del.addEventListener("click", async () => { await api("/api/tokens/" + t.token, { method: "DELETE" }); loadTokens(); });
    li.appendChild(del);
    ul.appendChild(li);
  }
}

async function init() {
  applyTheme();
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
  await loadCategories();
  bindNav();
  bindFilters();
  bindSidebar();
  bindScan();
  bindTableDrag();
  bindLog();
  startLogTimer();
  await loadDevices();
  pollScanStatus();
  setInterval(pollScanStatus, 5000);
}

init();
