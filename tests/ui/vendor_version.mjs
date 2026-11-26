// W5 D-5: vendored cytoscape.min.js passt zu package.json/package-lock und THIRD_PARTY.md (Hash)
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
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
  const pkg = JSON.parse(fs.readFileSync(path.join(repo, "package.json"), "utf8"));
  const lock = JSON.parse(fs.readFileSync(path.join(repo, "package-lock.json"), "utf8"));
  const range = pkg.devDependencies && pkg.devDependencies.cytoscape;
  const locked = lock.packages && lock.packages["node_modules/cytoscape"] && lock.packages["node_modules/cytoscape"].version;
  check("vendor_version: cytoscape in package.json gefuehrt", !!range);
  check(`vendor_version: Lock-Version ${locked} passt zu Range ${range}`, !!locked && !!range && locked.split(".")[0] === String(range).replace(/^[^\d]*/, "").split(".")[0]);
  const vendor = fs.readFileSync(path.join(repo, "app/static/vendor/cytoscape.min.js"), "utf8");
  const sha = crypto.createHash("sha256").update(vendor).digest("hex");
  const md = fs.readFileSync(path.join(repo, "THIRD_PARTY.md"), "utf8");
  check("vendored_cytoscape_matches_package_json: THIRD_PARTY.md nennt Lock-Version", !!locked && md.includes(locked));
  check("vendored_cytoscape_matches_package_json: THIRD_PARTY.md nennt sha256 des vendored Files", md.includes(sha.slice(0, 16)));
  check("vendored_cytoscape_matches_package_json: Datei nicht leer", vendor.length > 100000);
  check("vendored_cytoscape_matches_package_json: MIT-Lizenz im Kopf", vendor.includes("MIT") || vendor.includes("Permission is hereby granted"));
  return failures;
}

standalone(run);
