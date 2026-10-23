# Liara companion — developer runbook

How to run the product stack for demos and local development: **Vite agent shell** + **`apps/agent` BFF** + Docker Postgres/Redis.

Authoritative product UI: repo-root `src/` (not `apps/web`). Authoritative API: `apps/agent` (not thin `backend/`).

Related: root [README.md](../README.md), [challenge.md](../challenge.md), [liara-prd-v0.3.md](../liara-prd-v0.3.md), companion detail [apps/agent/README.md](../apps/agent/README.md).

## Prerequisites

- Node 20+, npm
- Python 3.12, [uv](https://github.com/astral-sh/uv)
- Docker with Compose
- A Fernet key as `SECRETS_MASTER_KEY` in root `.env` (see `.env.example`)

## Expected ports

| Service | Host port |
| --- | --- |
| Vite shell | 5173 |
| `apps/agent` (uvicorn) | 8000 |
| Postgres | 5433 → container 5432 |
| Redis | 6379 |

Default DB URL in `apps/agent` when `DATABASE_URL` is unset:

`postgresql://liara:liara@localhost:5433/liara_companion`

## Bring-up sequence

### 1. Environment

```bash
cp .env.example .env
# Set SECRETS_MASTER_KEY (Fernet). Do not put live Liara/Aval tokens in .env for day-to-day use — use Settings UI.
```

Optional env knobs (not secrets for demos): `VITE_API_PROXY_TARGET` (default `http://127.0.0.1:8000`), `LIARA_ALLOW_LIVE_WRITES=1` only when intentional live writes are approved.

### 2. Infra (Postgres + Redis)

```bash
docker compose up -d
```

Expected Compose services (restore/create root `docker-compose.yml` if missing):

- **postgres** `postgres:16-alpine`, ports `5433:5432`, user/password/db `liara` / `liara` / `liara_companion`
- **redis** `redis:7-alpine`, ports `6379:6379`

Checkpoint: `docker compose ps` healthy; host can reach Postgres on 5433.

### 3. Migrate + seed + agent

```bash
cd apps/agent
uv sync --group dev
uv run alembic upgrade head
uv run python -m app.scripts.seed_registry
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Checkpoint: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health) and `/ready` (Postgres). OpenAPI: `/docs`.

### 4. Vite shell

From repo root:

```bash
npm install
npm run dev
# or: npm run dev:all   # starts agent + shell together
```

Checkpoint: [http://localhost:5173](http://localhost:5173). Dev proxy forwards `/api`, `/health`, `/ready` to the BFF.

## Settings: Liara + Aval

In the shell **Settings** nav:

| Block | Fields | Notes |
| --- | --- | --- |
| Liara | API base, Team ID, token | Base default `https://api.liara.ir`; token paste-only |
| Aval | base URL, model, API key | Base default `https://api.avalai.ir/v1`; model user-configurable |

After save, use **Prove connection** (`POST /api/liara/prove-read`). Success updates registry read capability; it does not enable writes.

Secrets: `GET /api/settings` returns configured flags and labels only — never raw tokens or Aval keys.

## Chat HITL flow

Propose ≠ execute:

1. User sends a goal in chat → companion creates/attaches a **case**, assesses readiness, builds a **plan**.
2. UI shows a plan / approval card. User must click explicit **Approve** (reject stops before provider write). Free-text “approve” in chat is refused.
3. Shell calls `approve_plan` then `execute_plan` → `verify_result`. Inspector surfaces activity/timeline.

Live Liara mutations additionally require write-guard configuration. Without a non-expired approval, execute fails closed (e.g. HTTP 409).

## Retired / non-product paths

- **`apps/web`** — retired Next.js wizard; do not use as product UI.
- **`backend/`** — thin MVP reference; do not point Vite or demos at it.

## Verification smoke

```bash
test -f apps/agent/pyproject.toml && test -f src/App.tsx && test -f vite.config.ts
npm run build
cd apps/agent && uv run pytest
```

## Known limitations

- Some checkouts lack root `docker-compose.yml`; recreate per the services above before relying on `docker compose up -d`.
- Browser → Vite proxy → BFF is the supported path. Calling `:8000` from the browser directly may need `WEB_ORIGIN` to include `http://localhost:5173` (CORS allowlist historically includes `:3000`).
- Aval optional: without an Aval key, orchestrator nodes may use deterministic stub plans.
- Live writes default off (`LIARA_ALLOW_LIVE_WRITES` not `1`).
- Do not paste real credentials into docs, tickets, or committed `.env` files.
