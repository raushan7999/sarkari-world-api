# Sarkari World API

FastAPI service behind the public website, admin console and Android app.
Replaces the Node/Express `sarkariworld-api`, which it has now retired, and
owns the same Postgres database.

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
| `/openapi.json` | OpenAPI 3.1 schema |

`/openapi.json` is not optional if you want `/docs` — Swagger UI is a
JavaScript page that fetches the spec, so disabling the spec disables the UI
with it. ReDoc is deliberately not mounted; it renders the same document
`/docs` already serves.

`ENABLE_DOCS=false` turns both off (the API keeps serving); set it in
production if the surface should not be publicly browsable.

### Importing into Postman

**Import → Link → `http://127.0.0.1:8000/openapi.json`.** The spec declares its
`servers` entry, so the generated collection points at the right host instead
of guessing; set `BASE_URL` per environment.

The document is **OpenAPI 3.1**, which FastAPI emits by default. Postman's 3.1
support is newer than its 3.0 support, so on an older Postman version some
`anyOf` nullable fields and `const` values may import with weaker schema
detail. Requests, paths, auth and bodies all come through either way — update
Postman if the schemas look thin.

The spec documents both security schemes (bearer JWT and `X-API-Key`), every
error status each route can return (401/403/404/409/422) against the real
`ErrorResponse` shape, and 47 component schemas. Every operation carries a
summary, description and typed response model.

## Checks

```bash
uv run pytest        # 88 tests (58 unit + 30 integration)
uv run ruff check .
uv run ruff format .
uv run mypy src      # strict
```

`tests/integration/` runs against a real database and is **skipped
automatically** when `DATABASE_URL` is unreachable, so the suite passes
without Postgres. Those tests read existing rows and clean up everything they
write, so they are safe against a developer database.

## Layout

```
src/
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

## Schema ownership

This service now owns DDL. `migrations/` holds plain, idempotent SQL applied in
lexical order by `deploy/migrate-prod.sh`; see `migrations/README.md` for what
each file does and why two of them are specific to this database.

The tables are still the ones Prisma created — quoted PascalCase names, native
Postgres enum types — and `models/` maps onto them. The retired Node service's
Prisma schema is kept at `migrations/reference/schema.prisma`, because it is the
only written definition of the crawler tables this API never reads
(`SarkariWebsite`, `GoogleSearchQuery`, `CrawlRun`, `SearchKeywordGroup`) but
sibling apps do.

Two ways this service differs from the Node one it replaced, which matter to
anything still pointed at the old contract:

- **Response shapes.** The Node API wrapped everything in `{ok: true, ...}`.
  This service returns the resource directly and uses `{"error": {...}}` for
  failures.
- **Sessions.** This service issues standard JWTs; Node issued a hand-rolled
  HMAC token. Tokens never validated across the two. API keys are shared — they
  live in the database.

Endpoint paths match: both serve under `/v1/...`. Override with
`API_V1_PREFIX` if you need something else.

## Endpoints

| Area | Routes |
|---|---|
| Ops | `GET /health`, `GET /health/db` |
| Public | `GET /v1/category`, `/search`, `/{category}`, `/article/{slug}` |
| Auth | `GET /auth/providers`, `/auth/me`, `POST /auth/logout`, `/auth/{provider}` |
| Account | `GET /account/bookmarks`, `POST /account/bookmarks/toggle` |
| Admin | `dashboard`, `meta`, `posts` (7), `users` (3), `web-urls` (5), `bookmarks` (2) |
| Publish | `POST /admin/publish/articles` (markdown ingest, always draft) |

Article detail is `/article/{slug}`, not a bare `/{slug}`: FastAPI matches
routes in declaration order with no fall-through, so a root-level `/{slug}`
catch-all cannot coexist with `/{category}`.

## Auth

**People sign in with Google, and only Google.** There is no password login and
no other provider — `POST /v1/auth/{provider}` 404s for anything else.
A first sign-in creates the account at role `user`; signing in again never
changes a role, so nobody can promote themselves.

### Roles

`user` → `editor` → `admin`, changed only by an admin through
`PATCH /v1/admin/users/{id}/role` (self-changes are refused, so the last
admin cannot lock themselves out).

| Role | Can |
|---|---|
| `user` | Read public content, manage their own bookmarks |
| `editor` | All of the above, plus create and edit articles |
| `admin` | Everything, including deletes, user roles and API keys |

Guards are declared on routers — `require_auth`, `require_role(...)`,
`require_manage` (staff, with DELETE restricted to admins) — so a new route
under `/admin` inherits them rather than needing its own.

### API keys (machines)

Server-to-server callers (the content agent, CI) use `X-API-Key: sw_…`.

```bash
POST   /v1/admin/users/{id}/api-key   # issue or rotate; admin only
DELETE /v1/admin/users/{id}/api-key   # revoke
```

- **Editors and admins only** — issuing one for a plain `user` is refused
- **Valid 30 days**, derived from the issue date; rotation is manual (call
  POST again, which invalidates the previous key immediately)
- **Dies on demotion** — validity is re-checked against the owner's current
  role on every request, so a key never outlives the privilege it was issued
  against
- The secret is returned **once**; only a bcrypt hash is stored, so a lost key
  must be rotated, not recovered

Verification does an indexed prefix lookup then one bcrypt compare, and runs
bcrypt even on a prefix miss so timing cannot reveal which prefixes exist.

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
