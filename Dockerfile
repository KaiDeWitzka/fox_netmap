# Basis-Image per Digest gepinnt (reproduzierbar, manipulationssicher). Dependabot aktualisiert den Digest.
FROM python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b

ARG VERSION=dev
LABEL org.opencontainers.image.title="fox_netmap" \
      org.opencontainers.image.description="Interaktive Netzwerkkarte des Heimnetzes" \
      org.opencontainers.image.source="https://github.com/KaiDeWitzka/fox_netmap" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="${VERSION}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# libcap2-bin nur für setcap während des Builds; danach wieder entfernt.
RUN apt-get -o Acquire::Retries=5 -o Acquire::http::Timeout=30 update \
    && apt-get -o Acquire::Retries=5 -o Acquire::http::Timeout=30 install -y --no-install-recommends \
       iputils-ping iproute2 snmp libcap2-bin \
    && apt-get -o Acquire::Retries=5 -o Acquire::http::Timeout=30 upgrade -y --no-install-recommends \
    && setcap cap_net_raw+ep "$(readlink -f /bin/ping)" \
    && apt-get purge -y libcap2-bin && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Unprivilegierter App-Benutzer (feste IDs, damit Bind-Mounts vorhersehbar sind)
RUN groupadd --system --gid 10001 netmap \
    && useradd --system --uid 10001 --gid 10001 --no-create-home --home-dir /tmp --shell /usr/sbin/nologin netmap

WORKDIR /app

COPY requirements.txt .
# --require-hashes: Nur exakt die in requirements.txt festgelegten Pakete (Version + SHA-256) werden installiert.
RUN pip install --no-cache-dir --require-hashes --no-deps -r requirements.txt

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
