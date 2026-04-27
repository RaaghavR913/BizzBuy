#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

mode="${1:-local}"
case "$mode" in
  local|dev)
    env_file=".env.local"
    compose_file="docker-compose.yml"
    missing_message="Missing .env.local. Create it from .env.example before starting the local Docker stack."
    shift || true
    ;;
  production|prod)
    env_file=".env.production"
    compose_file="docker-compose.production.yml"
    missing_message="Missing .env.production. Create it with production values before starting the production Docker stack."
    shift || true
    ;;
  *)
    echo "Usage: $0 [local|production] [docker compose args...]" >&2
    echo "Examples:" >&2
    echo "  $0 local" >&2
    echo "  $0 production up --build -d" >&2
    echo "  $0 local down" >&2
    exit 2
    ;;
esac

if [[ ! -f "$env_file" ]]; then
  echo "$missing_message" >&2
  exit 1
fi

export DOCKER_BUILDKIT="${DOCKER_BUILDKIT:-0}"
export COMPOSE_BAKE="${COMPOSE_BAKE:-false}"

if [[ "$#" -eq 0 ]]; then
  set -- up --build
fi

exec docker compose --env-file "$env_file" -f "$compose_file" "$@"
