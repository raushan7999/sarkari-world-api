# dev run
  uv run uvicorn src.main:app --reload

# production (background, survives terminal close)
  pm2 start ecosystem.config.cjs



uv run pytest                    # 88 tests
uv run pytest tests/integration  # DB-backed only
uv run ruff check . && uv run mypy src
