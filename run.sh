#!/usr/bin/env bash
# Development and deployment helpers. Run from the project root.
set -euo pipefail

APP="sarkariworld.main:app"
# Loopback by default: the app is only reachable from this machine, and the
# reverse proxy in front of it is what the outside world talks to. Override
# with HOST=0.0.0.0 only when the proxy lives on another host or in another
# container, and make sure a firewall stands in front of it.
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
WORKERS="${WORKERS:-4}"

case "${1:-dev}" in
  dev)   uv run uvicorn "$APP" --reload --host "$HOST" --port "$PORT" ;;

  # Production: no --reload, several workers, and X-Forwarded-* trusted only
  # from the named proxy so client IPs and https:// are read correctly.
  prod)  uv run uvicorn "$APP" \
           --host "$HOST" \
           --port "$PORT" \
           --workers "$WORKERS" \
           --proxy-headers \
           --forwarded-allow-ips "${PROXY_IPS:-127.0.0.1}" ;;

  # Background, survives terminal close. PM2 owns the process from here.
  start)   pm2 start ecosystem.config.cjs && pm2 save ;;
  restart) pm2 restart sarkariworld-api-py ;;
  kill)    pm2 stop sarkariworld-api-py && pm2 delete sarkariworld-api-py ;;
  logs)    pm2 logs sarkariworld-api-py ;;
  status)  pm2 status ;;

  stop)  if pkill -f "uvicorn $APP"; then
           echo "stopped"
         else
           echo "nothing running"
         fi ;;

  ps)    pgrep -fl "uvicorn $APP" || echo "nothing running" ;;

  test)  uv run pytest ;;
  it)    uv run pytest tests/integration ;;   # needs a database
  check) uv run ruff check . && uv run ruff format --check . && uv run mypy sarkariworld ;;
  fix)   uv run ruff check --fix . && uv run ruff format . ;;
  *)     echo "usage: ./run.sh [dev|prod|start|restart|kill|logs|status|stop|ps|test|it|check|fix]" >&2; exit 1 ;;
esac
