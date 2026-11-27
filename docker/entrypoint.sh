#!/bin/sh
# fox_netmap Entrypoint: legt Rechte ab, bevor die Anwendung startet.
#
# Startet der Container als root (Standard), werden
#   1. Bestandsdaten im Daten-Volume einmalig an den App-Benutzer übergeben (Upgrade von <= v1.4.x,
#      als alles als root lief),
#   2. alle Capabilities aus dem Bounding-Set entfernt – der Scanner behält nur NET_RAW für ping –,
#   3. der Prozess als unprivilegierter Benutzer (UID/GID 10001) gestartet.
# Läuft der Container bereits als Nicht-root (z. B. `user:` in Compose/Runtipi), wird direkt gestartet.
set -eu

umask 077  # S-17: neue Dateien im Daten-Volume nur fuer den App-Benutzer

APP_UID="${APP_UID:-10001}"
APP_GID="${APP_GID:-10001}"
DATA_DIR="${NETZ_DATA_DIR:-/data}"
ROLE="${1:-web}"

if [ "$(id -u)" != "0" ]; then
    exec python -m app "$@"
fi

mkdir -p "$DATA_DIR"
# SF-7: Fehler der Rechtepruefung (z. B. NFS root_squash) sichtbar melden statt still zu uebergehen
probe_out="$(find "$DATA_DIR" \( ! -user "$APP_UID" -o ! -group "$APP_GID" \) -print -quit 2>/tmp/fox_netmap_find.err)" || {
    echo "[fox_netmap] WARN: Rechtepruefung in $DATA_DIR fehlgeschlagen ($(cat /tmp/fox_netmap_find.err 2>/dev/null)) - chown wird uebersprungen" >&2
    probe_out=""
}
if [ -n "$probe_out" ]; then
    echo "[fox_netmap] Uebernehme Dateien in $DATA_DIR fuer UID $APP_UID (einmalig nach Upgrade)"
    chown -R "$APP_UID:$APP_GID" "$DATA_DIR"
fi

export HOME=/tmp
case "$ROLE" in
    scanner)
        # ping braucht NET_RAW (Datei-Capability auf /bin/ping). no-new-privs würde das verhindern.
        exec setpriv --reuid="$APP_UID" --regid="$APP_GID" --clear-groups \
            --bounding-set=-all,+net_raw --inh-caps=-all \
            python -m app "$@"
        ;;
    *)
        exec setpriv --reuid="$APP_UID" --regid="$APP_GID" --clear-groups \
            --bounding-set=-all --inh-caps=-all --no-new-privs \
            python -m app "$@"
        ;;
esac
