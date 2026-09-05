#!/usr/bin/env bash
# Development helpers. Run from the project root.
set -euo pipefail

case "${1:-dev}" in
  dev)   uv run uvicorn sarkariworld.main:app --reload ;;
  test)  uv run pytest ;;
  it)    uv run pytest tests/integration ;;   # needs a database
  check) uv run ruff check . && uv run ruff format --check . && uv run mypy sarkariworld ;;
  fix)   uv run ruff check --fix . && uv run ruff format . ;;
  *)     echo "usage: ./run.sh [dev|test|it|check|fix]" >&2; exit 1 ;;
esac
