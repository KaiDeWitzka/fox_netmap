// T-13 (W6): Die jsdom-Fixture (devs_fixture.mjs) darf nicht von der echten API abweichen.
// tests/fixtures/api_devices_sample.json wird von tests/test_api_contract.py aus der echten
// API erzeugt und als Snapshot committet; hier wird die Schluessel-Paritaet geprueft.
import fs from "node:fs";
import path from "node:path";
import { DEVS } from "./devs_fixture.mjs";
import { standalone } from "./harness.mjs";

const repo = path.resolve(new URL("../..", import.meta.url).pathname);

export async function run() {
  let failures = 0;
  const check = (name, cond) => {
    if (!cond) {
      failures++;
      console.error("FAIL:", name);
    }
  };
  const samplePath = path.join(repo, "tests/fixtures/api_devices_sample.json");
  check("fixture_parity: api_devices_sample.json existiert (Snapshot aus echter API)", fs.existsSync(samplePath));
  const sample = JSON.parse(fs.readFileSync(samplePath, "utf8"));
  const apiKeys = new Set(sample.flatMap((d) => Object.keys(d)));
  check("fixture_parity: API-Snapshot enthaelt 5 Geraete", sample.length === 5);
  check(
    "fixture_parity: MACs der jsdom-Fixture kommen alle in der API-Antwort vor",
    DEVS.every((d) => sample.some((s) => s.mac === d.mac))
  );
  const missing = [...new Set(DEVS.flatMap((d) => Object.keys(d)))].filter((k) => !apiKeys.has(k));
  check(`fixture_parity: jeder Fixture-Schluessel existiert in der API-Antwort (fehlend: ${missing.join(",") || "-"})`, missing.length === 0);
  return failures;
}

standalone(run);
