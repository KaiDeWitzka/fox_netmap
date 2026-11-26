"""Backward-Compat (W7/Q-4): Die Routen liegen jetzt in app/routers/* (Registrierung in app/web.py),
die Fachlogik in app/services/*. Dieses Modul re-exportiert die Namen, die bestehender Code importiert
(Tests und Altcode): require_auth, require_auth_or_token, SettingsPatch, CATEGORIES."""

from .routers.common import get_conn, require_auth, require_auth_or_token  # noqa: F401
from .routers.settings import SettingsPatch  # noqa: F401
from .scanner.categorize import CATEGORIES  # noqa: F401
