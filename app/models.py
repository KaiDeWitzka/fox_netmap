"""Response-Models (W7/TL-5): response_model= an den JSON-Routen, damit der Vertrag im OpenAPI-Schema
sichtbar ist. Bei dynamischen Dicts (scan_state) bleibt extra='allow', damit keine Spalte herausfaellt."""

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    status: str


class MetaResponse(BaseModel):
    version: str
    gateway: str
    gateway6: str
    wan_ip: str
    wan_status: str
    wan_endpoint: str


class SitesResponse(BaseModel):
    names: list[str]
    map: dict[str, str]


class ScanStatusResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    last_scan: str | None = None
    next_scan: str | None = None
    scanning: int = 0
    last_error: str | None = None
    last_error_at: str | None = None
    consecutive_failures: int = 0
    scan_started_at: str | None = None
    scan_age_limit_s: int = 0
    stale_scanning: bool = False
    last_notify_status: str = ""
    last_notify_at: str = ""


class TokenListItem(BaseModel):
    id: str
    hint: str
    expires: str
    subnets: str
    categories: str
    created: str
