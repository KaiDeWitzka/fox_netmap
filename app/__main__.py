import sys


def main() -> None:
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
    from .web import create_app

    settings = get_settings()
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
