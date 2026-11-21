#!/bin/sh
# Führt Trivy in einem per Digest gepinnten Container aus (CI und lokal).
#
# Hintergrund: Im März 2026 wurden die Tags von aquasecurity/trivy-action und setup-trivy auf
# Schadcode umgebogen (CVE-2026-33634, GHSA-69fq-xp46-6x23, BSI-Warnung 2026-237970-1032).
# Deshalb kein trivy-action, sondern das offizielle Image mit unveränderlichem Digest.
# Update: Version + Digest gemeinsam ändern, Digest prüfen mit
#   docker buildx imagetools inspect ghcr.io/aquasecurity/trivy:<version>
#
# Aufruf: scripts/trivy.sh <trivy-argumente…>   (Arbeitsverzeichnis wird nach /work gemountet)
set -eu

TRIVY_IMAGE="ghcr.io/aquasecurity/trivy:0.76.2@sha256:8f6bb947dbc528902e11f2f5be52f7b519f6a39d5d148f41166f2040499768fb"

exec docker run --rm \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v "${TRIVY_CACHE_DIR:-$HOME/.cache/trivy}:/root/.cache/trivy" \
    -v "$PWD:/work" -w /work \
    ${TRIVY_USERNAME:+-e TRIVY_USERNAME} ${TRIVY_PASSWORD:+-e TRIVY_PASSWORD} \
    "$TRIVY_IMAGE" "$@"
