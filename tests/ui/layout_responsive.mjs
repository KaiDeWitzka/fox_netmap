// W5 F-16: 100dvh statt 100vh + schmale-Ansicht-Breakpoint in styles.css
import fs from "node:fs";
import path from "node:path";
import { makeHarness, sleep, standalone } from "./harness.mjs";

const repo = path.resolve(new URL("../..", import.meta.url).pathname);

export async function run() {
  const h = makeHarness({ devices: [] });
  await sleep(150);
  const css = fs.readFileSync(path.join(repo, "app/static/styles.css"), "utf8");
  h.check("layout_responsive: body nutzt 100dvh (mobile Adressleiste)", /height:\s*100dvh/.test(css));
  h.check("layout_responsive: Breakpoint fuer schmale Anzeigen vorhanden", /@media \(max-width: 760px\)/.test(css));
  const m = css.match(/@media \(max-width: 760px\)\s*\{([\s\S]*?)\n\}/);
  h.check("narrow_viewport_stacks_panels: Breakpoint-Block enthaelt aside#detail width:100%", !!m && /aside#detail\s*\{[^}]*width:\s*100%/.test(m[1]));
  return h.failures;
}

standalone(run);
