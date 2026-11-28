"use strict";
/*
 * Gerätesymbole für Karte, Legende und Tabelle (seit v1.6.1).
 * Pfade aus Lucide (https://lucide.dev), unverändert übernommen, lokal ausgeliefert (kein CDN).
 *
 * ISC License
 *
 * Copyright (c) 2026 Lucide Icons and Contributors
 *
 * Permission to use, copy, modify, and/or distribute this software for any
 * purpose with or without fee is hereby granted, provided that the above
 * copyright notice and this permission notice appear in all copies.
 *
 * THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
 * WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
 * MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
 * ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
 * WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
 * ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
 * OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
 *
 * ---
 *
 * The following Lucide icons are derived from the Feather project:
 *
 * airplay, alert-circle, alert-octagon, alert-triangle, aperture, arrow-down-circle, arrow-down-left, arrow-down-right, arrow-down, arrow-left-circle, arrow-left, arrow-right-circle, arrow-right, arrow-up-circle, arrow-up-left, arrow-up-right, arrow-up, at-sign, calendar, cast, check, chevron-down, chevron-left, chevron-right, chevron-up, chevrons-down, chevrons-left, chevrons-right, chevrons-up, circle, clipboard, clock, code, columns, command, compass, corner-down-left, corner-down-right, corner-left-down, corner-left-up, corner-right-down, corner-right-up, corner-up-left, corner-up-right, crosshair, database, divide-circle, divide-square, dollar-sign, download, external-link, feather, frown, hash, headphones, help-circle, info, italic, key, layout, life-buoy, link-2, link, loader, lock, log-in, log-out, maximize, meh, minimize, minimize-2, minus-circle, minus-square, minus, monitor, moon, more-horizontal, more-vertical, move, music, navigation-2, navigation, octagon, pause-circle, percent, plus-circle, plus-square, plus, power, radio, rss, search, server, share, shopping-bag, sidebar, smartphone, smile, square, table-2, tablet, target, terminal, trash-2, trash, triangle, tv, type, upload, x-circle, x-octagon, x-square, x, zoom-in, zoom-out
 *
 * The MIT License (MIT) (for the icons listed above)
 *
 * Copyright (c) 2013-present Cole Bemis
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */

const ICON_PATHS = {
  "globe": "<circle cx=\"12\" cy=\"12\" r=\"10\"/> <path d=\"M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20\"/> <path d=\"M2 12h20\"/>",
  "router": "<rect width=\"20\" height=\"8\" x=\"2\" y=\"14\" rx=\"2\"/> <path d=\"M6.01 18H6\"/> <path d=\"M10.01 18H10\"/> <path d=\"M15 10v4\"/> <path d=\"M17.84 7.17a4 4 0 0 0-5.66 0\"/> <path d=\"M20.66 4.34a8 8 0 0 0-11.31 0\"/>",
  "wifi": "<path d=\"M12 20h.01\"/> <path d=\"M2 8.82a15 15 0 0 1 20 0\"/> <path d=\"M5 12.859a10 10 0 0 1 14 0\"/> <path d=\"M8.5 16.429a5 5 0 0 1 7 0\"/>",
  "network": "<rect x=\"16\" y=\"16\" width=\"6\" height=\"6\" rx=\"1\"/> <rect x=\"2\" y=\"16\" width=\"6\" height=\"6\" rx=\"1\"/> <rect x=\"9\" y=\"2\" width=\"6\" height=\"6\" rx=\"1\"/> <path d=\"M5 16v-3a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v3\"/> <path d=\"M12 12V8\"/>",
  "server": "<rect width=\"20\" height=\"8\" x=\"2\" y=\"2\" rx=\"2\" ry=\"2\"/> <rect width=\"20\" height=\"8\" x=\"2\" y=\"14\" rx=\"2\" ry=\"2\"/> <line x1=\"6\" x2=\"6.01\" y1=\"6\" y2=\"6\"/> <line x1=\"6\" x2=\"6.01\" y1=\"18\" y2=\"18\"/>",
  "monitor": "<rect width=\"20\" height=\"14\" x=\"2\" y=\"3\" rx=\"2\"/> <line x1=\"8\" x2=\"16\" y1=\"21\" y2=\"21\"/> <line x1=\"12\" x2=\"12\" y1=\"17\" y2=\"21\"/>",
  "laptop": "<path d=\"M18 5a2 2 0 0 1 2 2v8.526a2 2 0 0 0 .212.897l1.068 2.127a1 1 0 0 1-.9 1.45H3.62a1 1 0 0 1-.9-1.45l1.068-2.127A2 2 0 0 0 4 15.526V7a2 2 0 0 1 2-2z\"/> <path d=\"M20.054 15.987H3.946\"/>",
  "smartphone": "<rect width=\"14\" height=\"20\" x=\"5\" y=\"2\" rx=\"2\" ry=\"2\"/> <path d=\"M12 18h.01\"/>",
  "tablet": "<rect width=\"16\" height=\"20\" x=\"4\" y=\"2\" rx=\"2\" ry=\"2\"/> <line x1=\"12\" x2=\"12.01\" y1=\"18\" y2=\"18\"/>",
  "tv": "<path d=\"m17 2-5 5-5-5\"/> <rect width=\"20\" height=\"15\" x=\"2\" y=\"7\" rx=\"2\"/>",
  "gamepad": "<line x1=\"6\" x2=\"10\" y1=\"11\" y2=\"11\"/> <line x1=\"8\" x2=\"8\" y1=\"9\" y2=\"13\"/> <line x1=\"15\" x2=\"15.01\" y1=\"12\" y2=\"12\"/> <line x1=\"18\" x2=\"18.01\" y1=\"10\" y2=\"10\"/> <path d=\"M17.32 5H6.68a4 4 0 0 0-3.978 3.59c-.006.052-.01.101-.017.152C2.604 9.416 2 14.456 2 16a3 3 0 0 0 3 3c1 0 1.5-.5 2-1l1.414-1.414A2 2 0 0 1 9.828 16h4.344a2 2 0 0 1 1.414.586L17 18c.5.5 1 1 2 1a3 3 0 0 0 3-3c0-1.545-.604-6.584-.685-7.258-.007-.05-.011-.1-.017-.151A4 4 0 0 0 17.32 5z\"/>",
  "printer": "<path d=\"M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2\"/> <path d=\"M6 9V3a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v6\"/> <rect x=\"6\" y=\"14\" width=\"12\" height=\"8\" rx=\"1\"/>",
  "lightbulb": "<path d=\"M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5\"/> <path d=\"M9 18h6\"/> <path d=\"M10 22h4\"/>",
  "unknown": "<circle cx=\"12\" cy=\"12\" r=\"10\"/> <path d=\"M9 9.5a3 2.5 0 016 0c0 2-2 2-3 3.5\"/> <path d=\"M12 17h.01\"/>",
  "box": "<path d=\"M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z\"/> <path d=\"m3.3 7 8.7 5 8.7-5\"/> <path d=\"M12 22V12\"/>",

};

// Kategorie -> Symbol. Einzige Stelle der Zuordnung (Karte, Legende, Tabelle).
const CATEGORY_ICON_KEYS = {
  Internet: "globe",
  Router: "router",
  Gateway: "router",
  "Repeater/AP": "wifi",
  WLAN: "wifi",
  Switch: "network",
  "Server/NAS": "server",
  Client: "monitor",
  "Mobilgerät": "smartphone",
  Multimedia: "tv",
  Drucker: "printer",
  "Smart-Home/IoT": "lightbulb",
  Container: "box",
  Unbekannt: "unknown",
};

// Feinere Symbole innerhalb einer Kategorie (Notebook, Tablet, Konsole) aus Begründung und Hostname.
function iconKeyFor(category, reason, hostname) {
  const r = String(reason || "").toLowerCase();
  const h = String(hostname || "").toLowerCase();
  if (category === "Client" && (/macbook|laptop|notebook|thinkpad|^nb-|yoga/.test(r + " " + h))) return "laptop";
  if (category === "Mobilgerät" && /ipad|tablet|galaxy-tab|^tab/.test(r + " " + h)) return "tablet";
  if (category === "Multimedia" && /ps[345]|playstation|xbox|switch-|nintendo|steamdeck/.test(r + " " + h)) return "gamepad";
  return CATEGORY_ICON_KEYS[category] || "unknown";
}

const _iconCache = new Map();

// Liefert eine data:-URI (CSP: img-src 'self' data:). Ergebnis wird je Symbol und Farbe zwischengespeichert.
function iconUri(key, color) {
  const k = (ICON_PATHS[key] ? key : "unknown") + "|" + color;
  let uri = _iconCache.get(k);
  if (!uri) {
    const svg = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="' + color +
      '" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' + ICON_PATHS[k.split("|")[0]] + "</svg>";
    uri = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg);
    _iconCache.set(k, uri);
  }
  return uri;
}
