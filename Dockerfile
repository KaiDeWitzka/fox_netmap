# Zweistufiger Build auf uv-Basis (W0): Build-Stage installiert die gepinnten Pakete aus uv.lock,
# Runtime-Stage uebernimmt nur das venv + den App-Code. Basis-Images per Digest gepinnt.
FROM ghcr.io/astral-sh/uv:0.11.16@sha256:440fd6477af86a2f1b38080c539f1672cd22acb1b1a47e321dba5158ab08864d AS uv
FROM python:3.12-slim@sha256:4a68d3169325c47e1bafbb86425220f03fbdff6f079a419e8d39407183288217 AS build

COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /build
COPY pyproject.toml uv.lock ./
# --frozen: nur exakt die in uv.lock festgelegten Pakete (Version + Hash) werden installiert.
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.12-slim@sha256:4a68d3169325c47e1bafbb86425220f03fbdff6f079a419e8d39407183288217 AS runtime

ARG VERSION=dev
LABEL org.opencontainers.image.title="fox_netmap" \
      org.opencontainers.image.description="Interaktive Netzwerkkarte des Heimnetzes" \
      org.opencontainers.image.source="https://github.com/KaiDeWitzka/fox_netmap" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="${VERSION}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Systempakete: kein apt-get upgrade (der Digest-Pin des Basis-Images waere wertlos,
# Aktualitaet kommt ueber Dependabot-Digest-Updates und den Trivy-Scan). Ausnahme: Pakete mit
# gefixtem CVE werden explizit genannt, damit apt die gefixte Version aus dem Repo installiert
# (z. B. libzstd1: CVE-2026-124851 HIGH, Fix 1.5.7+dfsg-1+deb13u1, Basis-Image traegt noch -1).
# libcap2-bin nur fuer setcap waehrend des Builds; danach wieder entfernt.
RUN apt-get -o Acquire::Retries=5 -o Acquire::http::Timeout=30 update \
    && apt-get -o Acquire::Retries=5 -o Acquire::http::Timeout=30 install -y --no-install-recommends \
       iputils-ping iproute2 snmp libcap2-bin \
       libzstd1 \
    && setcap cap_net_raw+ep "$(readlink -f /bin/ping)" \
    && apt-get purge -y libcap2-bin && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Unprivilegierter App-Benutzer (feste IDs, damit Bind-Mounts vorhersehbar sind)
RUN groupadd --system --gid 10001 netmap \
    && useradd --system --uid 10001 --gid 10001 --no-create-home --home-dir /tmp --shell /usr/sbin/nologin netmap

WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH"

COPY --from=build /build/.venv /app/.venv
COPY app ./app
COPY docker/entrypoint.sh /usr/local/bin/fox-entrypoint
RUN chmod 0755 /usr/local/bin/fox-entrypoint \
    && mkdir -p /data && chown 10001:10001 /data

ENV NETZ_DATA_DIR=/data
VOLUME ["/data"]
EXPOSE 8399

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-m", "app", "health"]

# Startet als root nur, um Volume-Rechte zu korrigieren; der Entrypoint wechselt sofort auf UID 10001.
ENTRYPOINT ["fox-entrypoint"]
CMD ["web"]
