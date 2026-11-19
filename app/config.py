from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NETZ_", env_file=".env", extra="ignore")

    data_dir: str = "/data"
    host: str = "0.0.0.0"
    port: int = 8399
    subnets: str = ""
    subnet: str = ""
    scan_interval: int = 900
    scan_timeout: float = 1.0
    port_top: int = 1000
    ports: str = ""
    fritz_url: str = ""
    fritz_user: str = ""
    fritz_pass: str = ""
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
    theme: str = "dark"
    auto_export: bool = False
    auto_export_dir: str = "exports"
    app_version: str = "0.1.0"

    @property
    def subnet_list(self) -> list[str]:
        raw = self.subnets or self.subnet
        return [s.strip() for s in raw.split(",") if s.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
