# LiaraOps AI («همراه لیارا»)

Cursor-like agent workspace: Vite shell (`src/`) on **:5173** talking to the companion BFF (`apps/agent`) on **:8000**.

Product docs / runbook: [docs/liara-companion.md](docs/liara-companion.md). Challenge brief: [challenge.md](challenge.md). Product PRD: [liara-prd-v0.3.md](liara-prd-v0.3.md).

## Requirements

- Node.js 20+ and npm
- Python 3.12 + [uv](https://github.com/astral-sh/uv) for `apps/agent`
- Docker Compose for local Postgres + Redis (Postgres host port **5433** by convention)
- Root `.env` with a Fernet `SECRETS_MASTER_KEY` (required to encrypt Settings secrets)

## Quick start

```bash
# 0) Env (never commit real tokens)
cp .env.example .env
# Generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Set SECRETS_MASTER_KEY=... in .env

# 1) Infra — Postgres (:5433) + Redis (:6379)
# Expects a root docker-compose.yml matching apps/agent DATABASE_URL defaults.
docker compose up -d

# 2) Companion BFF on :8000
cd apps/agent
uv sync --group dev
uv run alembic upgrade head
uv run python -m app.scripts.seed_registry
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

In another terminal (repo root):

```bash
npm install
npm run dev
```

Or once the agent venv is ready:

```bash
npm run dev:all   # AGENT (:8000) + SHELL (:5173)
```

Open [http://localhost:5173](http://localhost:5173). Vite proxies `/api`, `/health`, and `/ready` to [http://127.0.0.1:8000](http://127.0.0.1:8000).

API docs: [http://localhost:8000/docs](http://localhost:8000/docs).

**Important:** serve `apps/agent` (`app.main:app`), not the legacy thin `backend/` MVP.

## Ports

| Surface | Port | Notes |
| --- | --- | --- |
| Vite agent shell | **5173** | Product UI (`src/`) |
| Companion BFF | **8000** | `apps/agent` |
| Postgres (host) | **5433** | Maps to container 5432; avoids clash with local 5432 |
| Redis (host) | **6379** | Compose service when present |

## Settings (Liara + Aval)

1. Open **Settings** in the shell.
2. **Liara:** API base (`https://api.liara.ir`), optional Team ID, API token (paste only when setting/rotating).
3. **Aval AI:** base URL (default `https://api.avalai.ir/v1`), model (user-configurable; shell default placeholder `gpt-5.6-luna`), API key (paste only when setting/rotating).
4. **Save**, then **Prove connection** (`POST /api/liara/prove-read`).

`GET /api/settings` returns a redacted nested view (`liara` + `aval` masks/labels only). Raw tokens and Aval keys are accepted once on `PUT` and are **never echoed**.

## Chat HITL (propose ≠ execute)

Sensitive work goes through the companion orchestrator:

1. Chat a goal → case + readiness + **plan** (proposal only).
2. Explicit **Approve** on the plan/approval card (chat-text “approve” is not authorization).
3. Only then **execute** → verify; Inspector shows timeline/activity.

Writes also need companion write-guard env (`LIARA_ALLOW_LIVE_WRITES=1` plus a configured token) where live Liara mutations are intended. Without approval, `execute_plan` fails closed.

## Architecture

- `src/` — React + TypeScript + Vite agent workspace (product UI)
- `apps/agent/` — companion FastAPI BFF (product backend)
- `backend/` — thin FastAPI MVP (legacy reference only)
- `apps/web/` — **retired** Next.js wizard stub (not product UI; see `apps/web/README.md`)

## Checks

```bash
npm run build
npm test
cd apps/agent && uv run pytest
```

## Known limitations

- Root `docker-compose.yml` may be absent from some checkouts; if `docker compose up -d` fails, recreate Postgres on host **5433** and Redis on **6379** to match `apps/agent` defaults (`postgresql://liara:liara@localhost:5433/liara_companion`). See [docs/liara-companion.md](docs/liara-companion.md).
- Vite same-origin proxy is the normal browser path; direct browser calls to `:8000` may need `WEB_ORIGIN` including `http://localhost:5173` (BFF CORS historically defaults toward `:3000`).
- Live Liara writes stay off unless explicitly gated; Aval is optional (stub plans when unset).
- Conversation history in the shell may still be local/interim depending on wiring; do not assume server-side thread durability without checking.
