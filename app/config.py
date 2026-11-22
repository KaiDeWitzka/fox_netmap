import ipaddress
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NETZ_", env_file=".env", extra="ignore")

    data_dir: str = "/data"
    host: str = "0.0.0.0"
    port: int = 8399
    subnets: str = ""
    subnet: str = ""
    sites: str = ""
    scan_interval: int = 900
    scan_timeout: float = 1.0
    port_top: int = 1000
    ports: str = ""
    fritz_url: str = ""
    fritz_urls: str = ""
    fritz_user: str = ""
    fritz_pass: str = ""
    # Mesh-Topologie der FRITZ!Box (TR-064 X_AVM-DE_GetMeshListPath) fuer die Karte nutzen
    fritz_mesh: bool = True
    snmp_enabled: bool = True
    snmp_community: str = "public"
    snmp_switches: str = ""
    auth_enabled: bool = True
    auth_user: str = "admin"
    auth_pass: str = ""
    notify_webhook: str = ""
    notify_gotify: str = ""
    notify_gotify_token: str = ""
    notify_ntfy: str = ""
    notify_ntfy_token: str = ""
    history_hours: int = 720
    device_retention_days: int = 30
    theme: str = "dark"
    lang: str = "de"
    auto_export: bool = False
    auto_export_dir: str = "exports"
    auto_export_interval_hours: int = 24
    mdns_enabled: bool = True
    # Privacy by Default (DSGVO Art. 25): MAC-Präfixe gehen nur nach ausdrücklichem Einschalten an Dritte.
    oui_online_enabled: bool = False
    oui_online_max: int = 10
    oui_online_url: str = "https://api.macvendors.com"
    alarm_whitelist: str = ""
    # Erlaubte Einbetter fuer /embed (CSP frame-ancestors), z. B. "https://wiki.example.org 'self'". "*" = alle.
    embed_ancestors: str = "*"
    # Secure-Flag des Session-Cookies: "auto" (bei HTTPS bzw. X-Forwarded-Proto: https), "true" oder "false".
    cookie_secure: str = "auto"
    app_version: str = "1.6.0-rc.2"

    @property
    def subnet_list(self) -> list[str]:
        raw = self.subnets or self.subnet
        return [s.strip() for s in raw.split(",") if s.strip()]

    @property
    def site_map(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for part in self.sites.split(";"):
            part = part.strip()
            if not part or ":" not in part:
                continue
            name, _, subs = part.partition(":")
            name = name.strip()
            if not name:
                continue
            for sn in subs.split(","):
                sn = sn.strip()
                if not sn:
                    continue
                out[sn] = name
                try:
                    out[str(ipaddress.ip_network(sn, strict=False))] = name
                except ValueError:
                    continue
        return out

    @property
    def site_names(self) -> list[str]:
        return sorted(set(self.site_map.values()))


@lru_cache
def get_settings() -> Settings:
    return Settings()
