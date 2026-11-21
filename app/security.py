"""Sicherheitsfunktionen: HTTP-Security-Header und Login-Drosselung.

Bezug IT-Grundschutz: APP.3.1 (Webanwendungen) und ORP.4 (Identitäts- und Berechtigungsmanagement).
Die Werte sind bewusst konservativ gewählt und in docs/03-sicherheit.md dokumentiert.
"""

import threading
import time

# --- Security-Header -------------------------------------------------------------------------

# 'unsafe-inline' nur für Styles: Cytoscape und die Spaltenbreiten der Tabelle setzen Inline-Styles.
# Skripte sind strikt auf 'self' beschränkt (kein Inline-JS, kein eval).
_CSP_BASE = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; "
    "connect-src 'self'; "
    "font-src 'self'; "
    "object-src 'none'; "
    "base-uri 'none'; "
    "form-action 'self'; "
)

STATIC_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    # no-referrer: verhindert, dass Embed-Tokens aus der URL über den Referer an Dritte abfließen.
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    "Cross-Origin-Opener-Policy": "same-origin",
}


def security_headers(path: str, embed_ancestors: str) -> dict[str, str]:
    """Liefert die Security-Header für einen Pfad.

    Nur /embed darf in fremde Seiten eingebettet werden (frame-ancestors aus NETZ_EMBED_ANCESTORS).
    Alle anderen Seiten verbieten Framing vollständig (Clickjacking-Schutz).
    """
    headers = dict(STATIC_HEADERS)
    if path.startswith("/embed"):
        ancestors = embed_ancestors.strip() or "*"
        headers["Content-Security-Policy"] = _CSP_BASE + f"frame-ancestors {ancestors}"
    else:
        headers["Content-Security-Policy"] = _CSP_BASE + "frame-ancestors 'none'"
        headers["X-Frame-Options"] = "DENY"
    return headers


# --- Login-Drosselung --------------------------------------------------------------------------


class LoginThrottle:
    """Begrenzt fehlgeschlagene Logins pro Client-IP und pro (IP, Benutzer).

    Nach ``max_per_user`` Fehlversuchen für dieselbe Kombination IP+Benutzer bzw. ``max_per_ip``
    Fehlversuchen von einer IP innerhalb von ``window`` Sekunden wird die IP für ``lockout``
    Sekunden gesperrt. Bewusst nicht pro Benutzer allein, damit ein Angreifer den Admin nicht
    netzweit aussperren kann. Zustand nur im Speicher (Neustart setzt zurück).
    """

    def __init__(self, max_per_user: int = 5, max_per_ip: int = 20, window: int = 900, lockout: int = 900):
        self.max_per_user = max_per_user
        self.max_per_ip = max_per_ip
        self.window = window
        self.lockout = lockout
        self._fails: dict[tuple[str, str], list[float]] = {}
        self._locked: dict[tuple[str, str], float] = {}
        self._lock = threading.Lock()

    def _prune(self, now: float) -> None:
        cutoff = now - self.window
        for key in list(self._fails):
            kept = [t for t in self._fails[key] if t > cutoff]
            if kept:
                self._fails[key] = kept
            else:
                del self._fails[key]
        for key in [k for k, until in self._locked.items() if until <= now]:
            del self._locked[key]

    def retry_after(self, ip: str, username: str, now: float | None = None) -> int:
        """Sekunden bis zum nächsten erlaubten Versuch, 0 = nicht gesperrt."""
        now = now or time.time()
        with self._lock:
            self._prune(now)
            until = max(self._locked.get(("ip", ip), 0), self._locked.get((ip, username.lower()), 0))
        return max(0, int(until - now + 0.999))

    def register_failure(self, ip: str, username: str, now: float | None = None) -> None:
        now = now or time.time()
        user_key = (ip, username.lower())
        ip_key = ("ip", ip)
        with self._lock:
            self._prune(now)
            for key, limit in ((user_key, self.max_per_user), (ip_key, self.max_per_ip)):
                attempts = self._fails.setdefault(key, [])
                attempts.append(now)
                if len(attempts) >= limit:
                    self._locked[key] = now + self.lockout
                    self._fails.pop(key, None)

    def register_success(self, ip: str, username: str) -> None:
        with self._lock:
            self._fails.pop((ip, username.lower()), None)

    def reset(self) -> None:
        with self._lock:
            self._fails.clear()
            self._locked.clear()
