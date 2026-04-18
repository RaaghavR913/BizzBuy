#!/usr/bin/env bash
# Run Docker Compose with settings that avoid known failures on Docker Desktop:
# Compose v5 + BuildKit/bake can leave locally built tags unresolved ("No such image")
# or fail container create ("No such container" / stale network refs) when the engine
# uses the containerd snapshotter. The classic builder tags images reliably.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export DOCKER_BUILDKIT="${DOCKER_BUILDKIT:-0}"
export COMPOSE_BAKE="${COMPOSE_BAKE:-false}"
exec docker compose "$@"
