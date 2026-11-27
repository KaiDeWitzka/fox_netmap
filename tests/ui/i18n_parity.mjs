// W5 F-13/F-14/Q-11: alle Sprachen gleiche Schluesselmenge; jede Kategorie hat cat.* in jeder Sprache
import fs from "node:fs";
import path from "node:path";
import { standalone } from "./harness.mjs";

const repo = path.resolve(new URL("../..", import.meta.url).pathname);

// die 10 echten CATEGORIES aus app/scanner/categorize.py (Internet/Gateway/WLAN sind virtuelle
// Kartenknoten mit eigenen Schluesseln internet.node/gw.node/wlan.node)
const CATS = ["Router", "Repeater/AP", "Switch", "Server/NAS", "Client", "Mobilgerät", "Multimedia", "Drucker", "Smart-Home/IoT", "Unbekannt"];
const VIRTUAL = ["internet.node", "gw.node", "wlan.node"];

export async function run() {
  let failures = 0;
  const check = (name, cond) => {
    if (!cond) {
      failures++;
      console.error("FAIL:", name);
    }
  };
  const src = fs.readFileSync(path.join(repo, "app/static/i18n.js"), "utf8");
  const { I18N } = new Function(src + "; return { I18N };")();
  const langs = Object.keys(I18N);
  const deKeys = Object.keys(I18N.de).sort();
  check("i18n_parity: 6 Sprachen", langs.length === 6);
  for (const l of langs) {
    const keys = Object.keys(I18N[l]).sort();
    check(`i18n_parity: ${l} hat dieselbe Schluesselmenge wie de (${deKeys.length})`, JSON.stringify(keys) === JSON.stringify(deKeys));
    for (const c of CATS) {
      check(`i18n_parity: ${l} hat cat.${c}`, typeof I18N[l]["cat." + c] === "string" && I18N[l]["cat." + c].length > 0);
    }
    for (const k of VIRTUAL) {
      check(`i18n_parity: ${l} hat ${k}`, typeof I18N[l][k] === "string" && I18N[l][k].length > 0);
    }
  }
  return failures;
}

standalone(run);
