// Zentraler API-Client (Q-10, F-3/F-4): api() liefert die Rohantwort, apiJson() wirft ApiError
// bei !ok und bei Netzwerkfehlern. Aufrufer zeigen Fehler ueber showAlert() an (app.js).
// EMBED/TOKEN/setOffline werden in app.js deklariert und sind zur Laufzeit verfuegbar.
class ApiError extends Error {
  constructor(status, detail) {
    super(detail || "HTTP " + status);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail || "";
  }
}

function api(path, opts = {}) {
  const hasToken = typeof TOKEN !== "undefined" && TOKEN;
  const url = hasToken ? path + (path.includes("?") ? "&" : "?") + "token=" + encodeURIComponent(TOKEN) : path;
  return fetch(url, { headers: { "Content-Type": "application/json" }, ...opts })
    .then((r) => {
      if (r.status === 401 && typeof EMBED !== "undefined" && !EMBED) location.href = "/login";
      if (typeof setOffline === "function") setOffline(false);
      return r;
    })
    .catch((e) => {
      if (typeof setOffline === "function") setOffline(true);
      throw e;
    });
}

async function apiJson(path, opts = {}) {
  const r = await api(path, opts);
  let body = null;
  try {
    body = await r.json();
  } catch (e) {
    // Antwort ohne JSON-Body (z. B. leere 204) - body bleibt null
  }
  if (!r.ok) {
    const detail = body && body.detail ? String(body.detail) : "HTTP " + r.status;
    throw new ApiError(r.status, detail);
  }
  return body;
}
