// W5 F-5: gespeicherte x/y je Knoten bleiben im Auto-Layout erhalten, auch wenn andere Knoten keine haben
import { makeHarness, sleep, standalone } from "./harness.mjs";

const dev = (mac, ip, extra = {}) => ({
  mac, ip, ip6: "", hostname: ip, vendor: "", category: "Client", status: "online",
  subnet: "10.0.0.0/24", site: "", source: "ping+arp", room: "", ports_str: "", connected_to: "",
  note: "", last_seen: "2026-01-01T10:00:00+00:00", port_count: 0, x: null, y: null, connection: "",
  ...extra,
});

export async function run() {
  const h = makeHarness({
    devices: [
      dev("aa:bb:cc:dd:ee:ff", "10.0.0.5", { x: 111, y: 222 }),
      dev("bb:bb:bb:bb:bb:02", "10.0.0.6"),
    ],
  });
  await sleep(150);
  await h.w.eval("loadDevices()");
  await sleep(50);
  const cy = h.cy();
  const opts = cy._lastLayoutOpts;
  h.check("layout_positions: Auto-Layout mit positions-Funktion (preset)", cy._lastLayout === "preset" && !!opts && typeof opts.positions === "function");
  if (!opts || typeof opts.positions !== "function") return h.failures;
  const pA = opts.positions({ id: () => "aa:bb:cc:dd:ee:ff", position: () => ({ x: 0, y: 0 }) });
  const pB = opts.positions({ id: () => "bb:bb:bb:bb:bb:02", position: () => ({ x: 0, y: 0 }) });
  h.check("saved_positions_survive_unpositioned_node: gespeicherte x/y werden verwendet", pA.x === 111 && pA.y === 222);
  h.check("saved_positions_survive_unpositioned_node: unpositionierter Knoten faellt auf Baum-Position zurueck", pB.x !== 111 || pB.y !== 222);
  return h.failures;
}

standalone(run);
