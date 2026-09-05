# Sarkari World API

FastAPI reimplementation of the Node/Express `sarkariworld-api`, serving the
public website, admin console and Android app over the same Postgres database.

## Setup

```bash
uv sync
cp .env.example .env   # set DATABASE_URL and SESSION_SECRET
```

## Run

```bash
./run.sh dev      # development, auto-reloads (foreground)
./run.sh prod     # production, foreground — dies when the terminal closes
./run.sh start    # production under PM2 — survives terminal close
./run.sh status   # PM2 process list
./run.sh logs     # tail the PM2 logs
./run.sh restart  # restart after a deploy
./run.sh kill     # stop and remove from PM2
```

`prod` runs in the foreground as a child of your shell, so closing the terminal
sends SIGHUP and kills it. Use `start` for anything that needs to stay up: PM2
owns the process, restarts it if it crashes, and caps memory.

To also survive a reboot, run `pm2 startup` once and follow the sudo command it
prints, then `pm2 save`.

Both bind `127.0.0.1` by default, so the app is reachable only from this
machine and the reverse proxy in front of it is what the outside world talks
to. Set `HOST=0.0.0.0` only when the proxy runs on another host or in another
container — and put a firewall in front of it.

### Production

```bash
ENVIRONMENT=production \
SESSION_SECRET="<32+ random chars>" \
BEHIND_TLS_PROXY=true \
DATABASE_URL="postgresql+asyncpg://..." \
WORKERS=4 PROXY_IPS=127.0.0.1 ./run.sh prod
```

`ENVIRONMENT=production` makes the app **refuse to boot** with a
`SESSION_SECRET` under 32 characters, rather than starting with forgeable
sessions.

**Size workers against the connection pool.** Each worker owns its own pool, so
total connections are `WORKERS x (DB_POOL_SIZE + DB_MAX_OVERFLOW)`. With the
defaults that is `4 x 15 = 60`; Postgres `max_connections` is typically 100 and
other clients need room too. Raising workers without lowering the pool will
exhaust the server.

`HOST`, `PORT`, `WORKERS` and `PROXY_IPS` are all environment overrides.

Put a reverse proxy in front for TLS and rate limiting — rate limiting is
deliberately not implemented in this service. `--proxy-headers` is on so
client IPs and `https://` are read from `X-Forwarded-*`; set `PROXY_IPS` to the
proxy's address and never leave it open.

## API docs

| URL | What |
| --- | --- |
| `/docs` | Swagger UI — has an **Authorize** button; paste a session JWT or an `sw_` API key and every protected endpoint is callable from the page |
| `/redoc` | ReDoc |
| `/openapi.json` | OpenAPI 3.1 schema |

The spec documents both security schemes (bearer JWT and `X-API-Key`), every
error status each route can return (401/403/404/409/422) against the real
`ErrorResponse` shape, and 47 component schemas. Every operation carries a
summary, description and typed response model.

## Checks

```bash
uv run pytest        # 88 tests (58 unit + 30 integration)
uv run ruff check .
uv run ruff format .
uv run mypy sarkariworld      # strict
```

`tests/integration/` runs against a real database and is **skipped
automatically** when `DATABASE_URL` is unreachable, so the suite passes
without Postgres. Those tests read existing rows and clean up everything they
write, so they are safe against a developer database.

## Layout

```
sarkariworld/
├── main.py               create_app() factory + lifespan
├── dependencies.py       DB session + auth guards
├── exceptions.py         AppError hierarchy + handlers
├── config/settings.py    pydantic-settings
├── constants/            article caps, auth constants
├── db/                   engine, pool, DeclarativeBase
├── models/               SQLAlchemy, mapped to existing tables
├── schemas/              Pydantic request/response shapes
├── services/             all database access
├── routers/v1/           public, auth, account, admin/
├── middleware/           request context, CSRF
└── utils/                dates, slugs, html, urls, payload
```

Layering: routers own HTTP and validation, services own database access,
schemas own the wire contract. A router never queries directly; a service never
serialises.

## Relationship to the Node service

Both read the **same Prisma-managed tables**. Prisma still owns DDL — there are
no migrations here, and `models/` maps onto the existing schema (quoted
PascalCase table names, native Postgres enum types).

Two deliberate incompatibilities:

- **Response shapes.** The Node API wraps everything in `{ok: true, ...}`. This
  service returns the resource directly and uses `{"error": {...}}` for
  failures, so clients need updating.
- **Sessions.** This service issues standard JWTs; Node issues a hand-rolled
  HMAC token. Tokens do not validate across services, so users signing in here
  are signed out there. API keys are shared — they live in the database.

Endpoint paths also differ: `/api/v1/...` here versus `/v1/...` there. Set
`API_V1_PREFIX=/v1` to match.

## Endpoints

| Area | Routes |
|---|---|
| Ops | `GET /health`, `GET /health/db` |
| Public | `GET /api/v1/category`, `/search`, `/{category}`, `/article/{slug}` |
| Auth | `GET /auth/providers`, `/auth/me`, `POST /auth/logout`, `/auth/{provider}` |
| Account | `GET /account/bookmarks`, `POST /account/bookmarks/toggle` |
| Admin | `dashboard`, `meta`, `posts` (7), `users` (3), `web-urls` (5), `bookmarks` (2) |
| Publish | `POST /admin/publish/articles` (markdown ingest, always draft) |

Article detail is `/article/{slug}`, not a bare `/{slug}`: FastAPI matches
routes in declaration order with no fall-through, so a root-level `/{slug}`
catch-all cannot coexist with `/{category}`.

## Auth

Three credential types, resolved in order and never raising — a bad credential
resolves to anonymous and the guards produce the 401/403:

1. **API key** — `X-API-Key: sw_…`. Indexed prefix lookup, then bcrypt. bcrypt
   runs even on a prefix miss so timing does not leak which prefixes exist.
2. **Session JWT** — `Authorization: Bearer …` or the `sw_session` cookie.
   Revoked via the shared `User.session_invalidated_at` column.
3. **Google ID token** — verified off the event loop, then upgraded to a JWT.

Guards: `require_auth`, `require_role(...)`, `require_manage` (staff, with
DELETE restricted to admins). Declared on routers, so a new route under
`/admin` inherits the guard rather than needing its own.

## Conventions worth knowing

- **IST everywhere.** Connections are pinned to `Asia/Kolkata` and every
  timestamp serialises as `+05:30`, never `Z`. Stored values are naive and
  IST-relative — unsetting `DB_TIMEZONE` shifts them by 5h30m.
- **Two validation layers on writes.** Pydantic rejects unknown keys
  (`extra="forbid"`), then `services/article_writes.py` allow-lists and
  normalises each field. Never build a model from a spread body.
- **All logs are JSON**, including uvicorn's and SQLAlchemy's. Every line
  during a request carries `request_id`, `method` and `path`.

## Not ported

- Rate limiting — the reverse proxy owns it.
- The crawler tables (`SarkariWebsite`, `GoogleSearchQuery`, `CrawlRun`,
  `SearchKeywordGroup`); this API never read them.
