#!/usr/bin/env bash
# Development and deployment helpers. Run from the project root.
set -euo pipefail

WORKERS="${WORKERS:-4}"
PORT="${PORT:-8000}"

case "${1:-dev}" in
  dev)   uv run uvicorn sarkariworld.main:app --reload --port "$PORT" ;;

  # Production. No --reload. --proxy-headers makes the app trust the
  # reverse proxy's X-Forwarded-* so client IPs and https:// are correct;
  # restrict --forwarded-allow-ips to the proxy's address, never leave it
  # open to the internet.
  prod)  uv run uvicorn sarkariworld.main:app \
           --host 0.0.0.0 \
           --port "$PORT" \
           --workers "$WORKERS" \
           --proxy-headers \
           --forwarded-allow-ips "${PROXY_IPS:-127.0.0.1}" \
           --no-access-log ;;

  test)  uv run pytest ;;
  it)    uv run pytest tests/integration ;;   # needs a database
  check) uv run ruff check . && uv run ruff format --check . && uv run mypy sarkariworld ;;
  fix)   uv run ruff check --fix . && uv run ruff format . ;;
  *)     echo "usage: ./run.sh [dev|prod|test|it|check|fix]" >&2; exit 1 ;;
esac
