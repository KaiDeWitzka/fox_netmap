// D-5: cytoscape aus node_modules (package.json, via npm/Dependabot gepflegt) ins vendor-Verzeichnis
// kopieren und den SHA-256-Hash in THIRD_PARTY.md eintragen. Aufruf: npm run update:vendor
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";

const repo = path.resolve(new URL("..", import.meta.url).pathname);
const src = path.join(repo, "node_modules", "cytoscape", "dist", "cytoscape.min.js");
const dst = path.join(repo, "app", "static", "vendor", "cytoscape.min.js");
const thirdParty = path.join(repo, "THIRD_PARTY.md");

if (!fs.existsSync(src)) {
  console.error("node_modules/cytoscape fehlt - zuerst `npm install` ausfuehren");
  process.exit(1);
}
const pkg = JSON.parse(fs.readFileSync(path.join(repo, "node_modules", "cytoscape", "package.json"), "utf8"));
const code = fs.readFileSync(src, "utf8");
fs.writeFileSync(dst, code);
const sha = crypto.createHash("sha256").update(code).digest("hex");

let md = fs.readFileSync(thirdParty, "utf8");
md = md.replace(
  /\| Cytoscape\.js \| [^|]+ \| `app\/static\/vendor\/cytoscape\.min\.js` \| [^|]+ \| [^|]+ \|/,
  `| Cytoscape.js | ${pkg.version} (sha256:${sha.slice(0, 16)}…) | \`app/static/vendor/cytoscape.min.js\` | MIT, Copyright (c) 2016-2026 The Cytoscape Consortium | <https://github.com/cytoscape/cytoscape.js> – Version und Hash per \`npm run update:vendor\` gepflegt |`,
);
fs.writeFileSync(thirdParty, md);
console.log(`cytoscape ${pkg.version} -> app/static/vendor/cytoscape.min.js (sha256:${sha})`);
