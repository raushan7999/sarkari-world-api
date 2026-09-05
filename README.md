# Sarkari World API

FastAPI + PostgreSQL service with structured JSON logging.

## Setup

```bash
uv sync
cp .env.example .env   # then set DATABASE_URL
```

## Run

```bash
uv run uvicorn src.main:app --reload
```

Server: http://127.0.0.1:8000 · Swagger: `/docs` · ReDoc: `/redoc` · Schema: `/openapi.json`

## Checks

```bash
uv run pytest        # tests
uv run ruff check .  # lint
uv run ruff format . # format
uv run mypy src      # types
```

## Layout

```
src/
├── main.py               # create_app() factory + lifespan
├── dependencies.py       # shared deps (SessionDep)
├── exceptions.py         # AppError hierarchy + handlers
├── config/settings.py    # Settings (env / .env)
├── constants/            # shared constants
├── db/
│   ├── base.py           # DeclarativeBase
│   └── session.py        # engine, pool, get_session
├── models/               # SQLAlchemy models
├── schemas/              # Pydantic request/response models
├── routers/              # APIRouter modules
├── middleware/           # one module per middleware
├── scripts/              # one-off scripts
└── utils/logger.py       # structlog setup
tests/
```

## Adding an endpoint

1. Schemas in `src/schemas/<feature>.py`
2. Router in `src/routers/<feature>.py`:

```python
from fastapi import APIRouter
from src.dependencies import SessionDep
from src.schemas.job import JobRead

router = APIRouter(prefix="/jobs", tags=["jobs"])

@router.get("", response_model=list[JobRead])
async def list_jobs(session: SessionDep) -> list[JobRead]:
    ...
```

3. Register in `src/routers/__init__.py`:

```python
api_router.include_router(jobs.router)
```

It lands under `/api/v1`. Health checks stay unversioned at `/health` so probes
survive version bumps.

## Logging

```python
from src.utils.logger import get_logger

logger = get_logger(__name__)
logger.info("job_created", job_id=42)
```

`configure_logging()` routes structlog **and** the standard library (uvicorn,
SQLAlchemy) through one chain, so every line on stdout is JSON with the same
keys. `LOG_JSON=false` gives coloured console output for local dev.

`RequestContextMiddleware` binds `request_id`, `method` and `path` to the async
context, so **every** line logged during a request carries them, whichever
module wrote it. Add your own with `bind_request_context(user_id=...)`, or
per-logger with `logger.bind(...)`.

## Errors

Raise from `src/exceptions.py` and every response gets the same envelope:

```python
raise NotFoundError("Job 42 not found")
```

```json
{"error": {"code": "not_found", "message": "Job 42 not found", "request_id": "..."}}
```

## Database

`src/db/session.py` builds one `AsyncEngine` per process — the engine owns the
connection pool, so it is never rebuilt per request. Engine construction is
lazy; no socket opens until the first query. Inject a session:

```python
from src.dependencies import SessionDep

async def handler(session: SessionDep):
    ...
```

Sessions roll back on exception and return their connection to the pool; the
pool is drained on shutdown by the lifespan. Tune with `DB_POOL_SIZE`,
`DB_MAX_OVERFLOW`, `DB_POOL_RECYCLE`, `DB_POOL_TIMEOUT`, `DB_ECHO`.
`GET /health/db` pings it.
