import os
import sys
from typing import Any


def main() -> None:
    os.umask(0o077)  # S-17: neue Dateien (DB, Log, Exporte) nur fuer den Besitzer
    mode = sys.argv[1] if len(sys.argv) > 1 else "web"
    if mode == "health":
        from .healthcheck import main as health_main

        sys.exit(health_main())
    if mode == "scanner":
        from .scanner.run import main as scanner_main

        scanner_main()
        return
    import uvicorn

    from .config import get_settings
    from .logsetup import install_access_log_filter
    from .web import create_app

    install_access_log_filter()  # S-12: token= schwaerzen im Accesslog
    settings = get_settings()
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port, **_uvicorn_kwargs())


def _uvicorn_kwargs() -> dict[str, Any]:
    # S-13: proxy_headers nur, wenn ausdruecklich konfiguriert (NETZ_FORWARDED_ALLOW_IPS);
    # sonst wertet uvicorn X-Forwarded-For nicht aus und die Doku stimmt.
    forwarded = os.environ.get("NETZ_FORWARDED_ALLOW_IPS", "").strip()
    return {
        "proxy_headers": bool(forwarded),
        "forwarded_allow_ips": forwarded or "127.0.0.1,::1",
    }


if __name__ == "__main__":
    main()
