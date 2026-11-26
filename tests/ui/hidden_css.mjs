// T-16 (W6): [hidden] wird per CSS erzwungen (40f10cb) - #view-map{display:flex} darf das
// hidden-Attribut nicht ueberschreiben, sonst waere die Tabellenansicht nie sichtbar.
import fs from "node:fs";
import path from "node:path";
import { makeHarness, sleep, standalone } from "./harness.mjs";

const repo = path.resolve(new URL("../..", import.meta.url).pathname);

export async function run() {
  const h = makeHarness({});
  const deadline = Date.now() + 5000;
  while (Date.now() < deadline && !h.calls.some((c) => c.url.includes("/api/devices"))) await sleep(10);
  const css = fs.readFileSync(path.join(repo, "app/static/styles.css"), "utf8");
  h.check("hidden_css: [hidden]{display:none!important} steht im Stylesheet (40f10cb)", /\[hidden\]\s*\{[^}]*display:\s*none\s*!important/.test(css));
  const table = h.doc.getElementById("view-table");
  h.check("hidden_css: #view-table ist per hidden-Attribut unsichtbar", h.w.getComputedStyle(table).display === "none");
  table.hidden = false;
  h.check("hidden_css: ohne hidden-Attribut ist die Ansicht sichtbar", h.w.getComputedStyle(table).display !== "none");
  return h.failures;
}

standalone(run);
