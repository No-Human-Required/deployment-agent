# Agent (`apps/agent`)

FastAPI BFF + LangGraph orchestrator for «همراه لیارا».

Phase 0–1 skeleton: Workspace/Case/Audit, encrypted `SecretRef` store, capability
registry, Settings API, Liara HTTP client (read proof), LangGraph orchestrator
with schema-validated BFF commands and HITL approval before Liara deploy writes.

## Setup

```sh
# From repo root — Postgres + Redis (Postgres host port 5433)
docker compose up -d

cd apps/agent
uv sync --group dev
```

Copy root `.env.example` → `.env` and set `SECRETS_MASTER_KEY` (Fernet) before
storing secrets via Settings.

## Migrate

```sh
cd apps/agent
uv run alembic upgrade head
uv run python -m app.scripts.seed_registry
```

## Test

```sh
cd apps/agent
uv run pytest
```

## Run

```sh
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- `GET /health` → liveness
- `GET /ready` → Postgres check
- `GET /api/settings` → redacted settings (masks/labels only)
- `PUT /api/settings` → accepts raw secrets once; stores via SecretService
- `POST /api/liara/prove-read` → `GET /v1/me` + `GET /v1/projects`; on success
  sets registry `list_get_projects` → `tested` (not write-enabled)

### Orchestrator BFF (`/api/orchestrator`)

Propose ≠ execute: plans are schema-validated; `execute_plan` requires a
non-expired `approve_plan` record. Secrets are never passed into LLM prompts
(labels/refs only). Allowlisted Liara writes run only after approval.

| Method | Path | Notes |
| --- | --- | --- |
| POST | `/api/orchestrator/cases` | Create case (`workspace_id`, `goal`) |
| POST | `/api/orchestrator/assess_readiness` | Optional `app_path` → Node/Next findings |
| POST | `/api/orchestrator/create_plan` | Optional `plan` / `deploy`; invalid → 422, no write |
| POST | `/api/orchestrator/approve_plan` | HITL gate; stores plan_hash + expiry |
| POST | `/api/orchestrator/execute_plan` | Idempotent via `client_request_id`; 409 without approval |
| POST | `/api/orchestrator/continue_or_stop` | `decision`: `continue` \| `stop` |
| POST | `/api/orchestrator/verify_result` | Release check (+ optional HTTP); stub → `verified_stub` |
| POST | `/api/orchestrator/collect_evidence` | Phase-3: status/logs/events/metrics → evidenceVersion |
| POST | `/api/orchestrator/diagnose` | Phase-3: evidenceVersion → diagnosis (facts/hypotheses/gaps) |
| POST | `/api/orchestrator/propose_fix_options` | Direct-fix options (approval still required; `update_envs` disabled) |
| POST | `/api/orchestrator/create_plan_from_fix` | Map enabled fix option → ops plan |
| POST | `/api/orchestrator/verify_fix` | Same-method before/after; no autonomous next write (L-AC17) |
| POST | `/api/orchestrator/collect_evidence` | Phase-3: status/logs/events/metrics → evidenceVersion |
| POST | `/api/orchestrator/diagnose` | Phase-3: evidenceVersion → diagnosis (facts/hypotheses/gaps) |
| POST | `/api/orchestrator/propose_fix_options` | Direct-fix options (approval still required; `update_envs` disabled) |
| POST | `/api/orchestrator/create_plan_from_fix` | Map enabled fix option → ops plan |
| POST | `/api/orchestrator/verify_fix` | Same-method before/after; no autonomous next write (L-AC17) |
| POST | `/api/orchestrator/collect_evidence` | Phase-3: status/logs/events/metrics → evidenceVersion |
| POST | `/api/orchestrator/diagnose` | Phase-3: evidenceVersion → diagnosis (facts/hypotheses/gaps) |
| POST | `/api/orchestrator/propose_fix_options` | Direct-fix options (approval still required; `update_envs` disabled) |
| POST | `/api/orchestrator/create_plan_from_fix` | Map enabled fix option → ops plan |
| POST | `/api/orchestrator/verify_fix` | Same-method before/after; no autonomous next write (L-AC17) |
| POST | `/api/orchestrator/collect_evidence` | Phase-3: status/logs/events/metrics → evidenceVersion |
| POST | `/api/orchestrator/diagnose` | Phase-3: evidenceVersion → diagnosis (facts/hypotheses/gaps) |
| POST | `/api/orchestrator/propose_fix_options` | Direct-fix options (approval still required; `update_envs` disabled) |
| POST | `/api/orchestrator/create_plan_from_fix` | Map enabled fix option → ops plan |
| POST | `/api/orchestrator/verify_fix` | Same-method before/after; no autonomous next write (L-AC17) |
| POST | `/api/orchestrator/collect_evidence` | Phase-3: status/logs/events/metrics → evidenceVersion |
| POST | `/api/orchestrator/diagnose` | Phase-3: evidenceVersion → diagnosis (facts/hypotheses/gaps) |
| POST | `/api/orchestrator/propose_fix_options` | Direct-fix options (approval still required; `update_envs` disabled) |
| POST | `/api/orchestrator/create_plan_from_fix` | Map enabled fix option → ops plan |
| POST | `/api/orchestrator/verify_fix` | Same-method before/after; no autonomous next write (L-AC17) |
| POST | `/api/orchestrator/collect_evidence` | Phase-3: status/logs/events/metrics → evidenceVersion |
| POST | `/api/orchestrator/diagnose` | Phase-3: evidenceVersion → diagnosis (facts/hypotheses/gaps) |
| POST | `/api/orchestrator/propose_fix_options` | Direct-fix options (approval still required; `update_envs` disabled) |
| POST | `/api/orchestrator/create_plan_from_fix` | Map enabled fix option → ops plan |
| POST | `/api/orchestrator/verify_fix` | Same-method before/after; no autonomous next write (L-AC17) |
| POST | `/api/orchestrator/collect_evidence` | Phase-3: status/logs/events/metrics → evidenceVersion |
| POST | `/api/orchestrator/diagnose` | Phase-3: evidenceVersion → diagnosis (facts/hypotheses/gaps) |
| POST | `/api/orchestrator/propose_fix_options` | Direct-fix options (approval still required; `update_envs` disabled) |
| POST | `/api/orchestrator/create_plan_from_fix` | Map enabled fix option → ops plan |
| POST | `/api/orchestrator/verify_fix` | Same-method before/after; no autonomous next write (L-AC17) |
| POST | `/api/orchestrator/collect_evidence` | Phase-3: status/logs/events/metrics → evidenceVersion |
| POST | `/api/orchestrator/diagnose` | Phase-3: evidenceVersion → diagnosis (facts/hypotheses/gaps) |
| POST | `/api/orchestrator/propose_fix_options` | Direct-fix options (approval still required; `update_envs` disabled) |
| POST | `/api/orchestrator/create_plan_from_fix` | Map enabled fix option → ops plan |
| POST | `/api/orchestrator/verify_fix` | Same-method before/after; no autonomous next write (L-AC17) |
| POST | `/api/orchestrator/collect_evidence` | Phase-3: status/logs/events/metrics → evidenceVersion |
| POST | `/api/orchestrator/diagnose` | Phase-3: evidenceVersion → diagnosis (facts/hypotheses/gaps) |
| POST | `/api/orchestrator/propose_fix_options` | Direct-fix options (approval still required; `update_envs` disabled) |
| POST | `/api/orchestrator/create_plan_from_fix` | Map enabled fix option → ops plan |
| POST | `/api/orchestrator/verify_fix` | Same-method before/after; no autonomous next write (L-AC17) |
| POST | `/api/orchestrator/collect_evidence` | Phase-3: status/logs/events/metrics → evidenceVersion |
| POST | `/api/orchestrator/diagnose` | Phase-3: evidenceVersion → diagnosis (facts/hypotheses/gaps) |
| POST | `/api/orchestrator/propose_fix_options` | Direct-fix options (approval still required; `update_envs` disabled) |
| POST | `/api/orchestrator/create_plan_from_fix` | Map enabled fix option → ops plan |
| POST | `/api/orchestrator/verify_fix` | Same-method before/after; no autonomous next write (L-AC17) |
| POST | `/api/orchestrator/collect_evidence` | Phase-3: status/logs/events/metrics → evidenceVersion |
| POST | `/api/orchestrator/diagnose` | Phase-3: evidenceVersion → diagnosis (facts/hypotheses/gaps) |
| POST | `/api/orchestrator/propose_fix_options` | Direct-fix options (approval still required; `update_envs` disabled) |
| POST | `/api/orchestrator/create_plan_from_fix` | Map enabled fix option → ops plan |
| POST | `/api/orchestrator/verify_fix` | Same-method before/after; no autonomous next write (L-AC17) |
| POST | `/api/orchestrator/collect_evidence` | Phase-3: status/logs/events/metrics → evidenceVersion |
| POST | `/api/orchestrator/diagnose` | Phase-3: evidenceVersion → diagnosis (facts/hypotheses/gaps) |
| POST | `/api/orchestrator/propose_fix_options` | Direct-fix options (approval still required; `update_envs` disabled) |
| POST | `/api/orchestrator/create_plan_from_fix` | Map enabled fix option → ops plan |
| POST | `/api/orchestrator/verify_fix` | Same-method before/after; no autonomous next write (L-AC17) |
| POST | `/api/orchestrator/collect_evidence` | Phase-3: status/logs/events/metrics → evidenceVersion |
| POST | `/api/orchestrator/diagnose` | Phase-3: evidenceVersion → diagnosis (facts/hypotheses/gaps) |
| POST | `/api/orchestrator/propose_fix_options` | Direct-fix options (approval still required; `update_envs` disabled) |
| POST | `/api/orchestrator/create_plan_from_fix` | Map enabled fix option → ops plan |
| POST | `/api/orchestrator/verify_fix` | Same-method before/after; no autonomous next write (L-AC17) |
| POST | `/api/orchestrator/collect_evidence` | Phase-3: status/logs/events/metrics → evidenceVersion |
| POST | `/api/orchestrator/diagnose` | Phase-3: evidenceVersion → diagnosis (facts/hypotheses/gaps) |
| POST | `/api/orchestrator/propose_fix_options` | Direct-fix options (approval still required; `update_envs` disabled) |
| POST | `/api/orchestrator/create_plan_from_fix` | Map enabled fix option → ops plan |
| POST | `/api/orchestrator/verify_fix` | Same-method before/after; no autonomous next write (L-AC17) |
| POST | `/api/orchestrator/collect_evidence` | Phase-3: status/logs/events/metrics → evidenceVersion |
| POST | `/api/orchestrator/diagnose` | Phase-3: evidenceVersion → diagnosis (facts/hypotheses/gaps) |
| POST | `/api/orchestrator/propose_fix_options` | Direct-fix options (approval still required; `update_envs` disabled) |
| POST | `/api/orchestrator/create_plan_from_fix` | Map enabled fix option → ops plan |
| POST | `/api/orchestrator/verify_fix` | Same-method before/after; no autonomous next write (L-AC17) |
| POST | `/api/orchestrator/collect_evidence` | Phase-3: status/logs/events/metrics → evidenceVersion |
| POST | `/api/orchestrator/diagnose` | Phase-3: evidenceVersion → diagnosis (facts/hypotheses/gaps) |
| POST | `/api/orchestrator/propose_fix_options` | Direct-fix options (approval still required; `update_envs` disabled) |
| POST | `/api/orchestrator/create_plan_from_fix` | Map enabled fix option → ops plan |
| POST | `/api/orchestrator/verify_fix` | Same-method before/after; no autonomous next write (L-AC17) |
| POST | `/api/orchestrator/collect_evidence` | Phase-3: status/logs/events/metrics → evidenceVersion |
| POST | `/api/orchestrator/diagnose` | Phase-3: evidenceVersion → diagnosis (facts/hypotheses/gaps) |
| POST | `/api/orchestrator/propose_fix_options` | Direct-fix options (approval still required; `update_envs` disabled) |
| POST | `/api/orchestrator/create_plan_from_fix` | Map enabled fix option → ops plan |
| POST | `/api/orchestrator/verify_fix` | Same-method before/after; no autonomous next write (L-AC17) |
| POST | `/api/orchestrator/collect_evidence` | Phase-3: status/logs/events/metrics → evidenceVersion |
| POST | `/api/orchestrator/diagnose` | Phase-3: evidenceVersion → diagnosis (facts/hypotheses/gaps) |
| POST | `/api/orchestrator/propose_fix_options` | Direct-fix options (approval still required; `update_envs` disabled) |
| POST | `/api/orchestrator/create_plan_from_fix` | Map enabled fix option → ops plan |
| POST | `/api/orchestrator/verify_fix` | Same-method before/after; no autonomous next write (L-AC17) |
| POST | `/api/orchestrator/collect_evidence` | Phase-3: status/logs/events/metrics → evidenceVersion |
| POST | `/api/orchestrator/diagnose` | Phase-3: evidenceVersion → diagnosis (facts/hypotheses/gaps) |
| POST | `/api/orchestrator/propose_fix_options` | Direct-fix options (approval still required; `update_envs` disabled) |
| POST | `/api/orchestrator/create_plan_from_fix` | Map enabled fix option → ops plan |
| POST | `/api/orchestrator/verify_fix` | Same-method before/after; no autonomous next write (L-AC17) |
| POST | `/api/orchestrator/collect_evidence` | Phase-3: status/logs/events/metrics → evidenceVersion |
| POST | `/api/orchestrator/diagnose` | Phase-3: evidenceVersion → diagnosis (facts/hypotheses/gaps) |
| POST | `/api/orchestrator/propose_fix_options` | Direct-fix options (approval still required; `update_envs` disabled) |
| POST | `/api/orchestrator/create_plan_from_fix` | Map enabled fix option → ops plan |
| POST | `/api/orchestrator/verify_fix` | Same-method before/after; no autonomous next write (L-AC17) |
| POST | `/api/orchestrator/collect_evidence` | Phase-3: status/logs/events/metrics → evidenceVersion |
| POST | `/api/orchestrator/diagnose` | Phase-3: evidenceVersion → diagnosis (facts/hypotheses/gaps) |
| POST | `/api/orchestrator/propose_fix_options` | Direct-fix options (approval still required; `update_envs` disabled) |
| POST | `/api/orchestrator/create_plan_from_fix` | Map enabled fix option → ops plan |
| POST | `/api/orchestrator/verify_fix` | Same-method before/after; no autonomous next write (L-AC17) |
| POST | `/api/orchestrator/collect_evidence` | Phase-3: status/logs/events/metrics → evidenceVersion |
| POST | `/api/orchestrator/diagnose` | Phase-3: evidenceVersion → diagnosis (facts/hypotheses/gaps) |
| POST | `/api/orchestrator/propose_fix_options` | Direct-fix options (approval still required; `update_envs` disabled) |
| POST | `/api/orchestrator/create_plan_from_fix` | Map enabled fix option → ops plan |
| POST | `/api/orchestrator/verify_fix` | Same-method before/after; no autonomous next write (L-AC17) |
| POST | `/api/orchestrator/collect_evidence` | Phase-3: status/logs/events/metrics → evidenceVersion |
| POST | `/api/orchestrator/diagnose` | Phase-3: evidenceVersion → diagnosis (facts/hypotheses/gaps) |
| POST | `/api/orchestrator/propose_fix_options` | Direct-fix options (approval still required; `update_envs` disabled) |
| POST | `/api/orchestrator/create_plan_from_fix` | Map enabled fix option → ops plan |
| POST | `/api/orchestrator/verify_fix` | Same-method before/after; no autonomous next write (L-AC17) |
| POST | `/api/orchestrator/collect_evidence` | Phase-3: status/logs/events/metrics → evidenceVersion |
| POST | `/api/orchestrator/diagnose` | Phase-3: evidenceVersion → diagnosis (facts/hypotheses/gaps) |
| POST | `/api/orchestrator/propose_fix_options` | Direct-fix options (approval still required; `update_envs` disabled) |
| POST | `/api/orchestrator/create_plan_from_fix` | Map enabled fix option → ops plan |
| POST | `/api/orchestrator/verify_fix` | Same-method before/after; no autonomous next write (L-AC17) |
| POST | `/api/orchestrator/collect_evidence` | Phase-3: status/logs/events/metrics → evidenceVersion |
| POST | `/api/orchestrator/diagnose` | Phase-3: evidenceVersion → diagnosis (facts/hypotheses/gaps) |
| POST | `/api/orchestrator/propose_fix_options` | Direct-fix options (approval still required; `update_envs` disabled) |
| POST | `/api/orchestrator/create_plan_from_fix` | Map enabled fix option → ops plan |
| POST | `/api/orchestrator/verify_fix` | Same-method before/after; no autonomous next write (L-AC17) |
| POST | `/api/orchestrator/collect_evidence` | Phase-3: status/logs/events/metrics → evidenceVersion |
| POST | `/api/orchestrator/diagnose` | Phase-3: evidenceVersion → diagnosis (facts/hypotheses/gaps) |
| POST | `/api/orchestrator/propose_fix_options` | Direct-fix options (approval still required; `update_envs` disabled) |
| POST | `/api/orchestrator/create_plan_from_fix` | Map enabled fix option → ops plan |
| POST | `/api/orchestrator/verify_fix` | Same-method before/after; no autonomous next write (L-AC17) |
| POST | `/api/orchestrator/collect_evidence` | Phase-3: status/logs/events/metrics → evidenceVersion |
| POST | `/api/orchestrator/diagnose` | Phase-3: evidenceVersion → diagnosis (facts/hypotheses/gaps) |
| POST | `/api/orchestrator/propose_fix_options` | Direct-fix options (approval still required; `update_envs` disabled) |
| POST | `/api/orchestrator/create_plan_from_fix` | Map enabled fix option → ops plan |
| POST | `/api/orchestrator/verify_fix` | Same-method before/after; no autonomous next write (L-AC17) |
| POST | `/api/orchestrator/collect_evidence` | Phase-3: status/logs/events/metrics → evidenceVersion |
| POST | `/api/orchestrator/diagnose` | Phase-3: evidenceVersion → diagnosis (facts/hypotheses/gaps) |
| POST | `/api/orchestrator/propose_fix_options` | Direct-fix options (approval still required; `update_envs` disabled) |
| POST | `/api/orchestrator/create_plan_from_fix` | Map enabled fix option → ops plan |
| POST | `/api/orchestrator/verify_fix` | Same-method before/after; no autonomous next write (L-AC17) |
| POST | `/api/orchestrator/collect_evidence` | Phase-3: status/logs/events/metrics → evidenceVersion |
| POST | `/api/orchestrator/diagnose` | Phase-3: evidenceVersion → diagnosis (facts/hypotheses/gaps) |
| POST | `/api/orchestrator/propose_fix_options` | Direct-fix options (approval still required; `update_envs` disabled) |
| POST | `/api/orchestrator/create_plan_from_fix` | Map enabled fix option → ops plan |
| POST | `/api/orchestrator/verify_fix` | Same-method before/after; no autonomous next write (L-AC17) |
| POST | `/api/orchestrator/discover_dependencies` | Phase-4: file-backed DB/Redis/disk discovery → `dependency_plan` |
| POST | `/api/orchestrator/create_plan` + `deps` | Phase-4: approval-gated create plan (registry must enable writes) |
| POST | `/api/orchestrator/create_patch` | Phase-5: unified diff + rationale tied to evidence/diagnosis |
| POST | `/api/orchestrator/run_patch_sandbox` | Phase-5: temp copy, scrub secrets, allowlisted tests |
| POST | `/api/orchestrator/approve_patch_record` | Phase-5: record patch only (≠ release) |
| POST | `/api/orchestrator/approve_release` | Phase-5: Liara release; blocked if sandbox not ready |
| POST | `/api/orchestrator/create_patch` | Phase-5: unified diff + rationale tied to evidence/diagnosis |
| POST | `/api/orchestrator/run_patch_sandbox` | Phase-5: temp copy, scrub secrets, allowlisted tests |
| POST | `/api/orchestrator/approve_patch_record` | Phase-5: record patch only (≠ release) |
| POST | `/api/orchestrator/approve_release` | Phase-5: Liara release; blocked if sandbox not ready |
| POST | `/api/orchestrator/create_patch` | Phase-5: unified diff + rationale tied to evidence/diagnosis |
| POST | `/api/orchestrator/run_patch_sandbox` | Phase-5: temp copy, scrub secrets, allowlisted tests |
| POST | `/api/orchestrator/approve_patch_record` | Phase-5: record patch only (≠ release) |
| POST | `/api/orchestrator/approve_release` | Phase-5: Liara release; blocked if sandbox not ready |
| POST | `/api/orchestrator/create_patch` | Phase-5: unified diff + rationale tied to evidence/diagnosis |
| POST | `/api/orchestrator/run_patch_sandbox` | Phase-5: temp copy, scrub secrets, allowlisted tests |
| POST | `/api/orchestrator/approve_patch_record` | Phase-5: record patch only (≠ release) |
| POST | `/api/orchestrator/approve_release` | Phase-5: Liara release; blocked if sandbox not ready |
| POST | `/api/orchestrator/create_patch` | Phase-5: unified diff + rationale tied to evidence/diagnosis |
| POST | `/api/orchestrator/run_patch_sandbox` | Phase-5: temp copy, scrub secrets, allowlisted tests |
| POST | `/api/orchestrator/approve_patch_record` | Phase-5: record patch only (≠ release) |
| POST | `/api/orchestrator/approve_release` | Phase-5: Liara release; blocked if sandbox not ready |
| POST | `/api/orchestrator/create_patch` | Phase-5: unified diff + rationale tied to evidence/diagnosis |
| POST | `/api/orchestrator/run_patch_sandbox` | Phase-5: temp copy, scrub secrets, allowlisted tests |
| POST | `/api/orchestrator/approve_patch_record` | Phase-5: record patch only (≠ release) |
| POST | `/api/orchestrator/approve_release` | Phase-5: Liara release; blocked if sandbox not ready |
| POST | `/api/orchestrator/create_patch` | Phase-5: unified diff + rationale tied to evidence/diagnosis |
| POST | `/api/orchestrator/run_patch_sandbox` | Phase-5: temp copy, scrub secrets, allowlisted tests |
| POST | `/api/orchestrator/approve_patch_record` | Phase-5: record patch only (≠ release) |
| POST | `/api/orchestrator/approve_release` | Phase-5: Liara release; blocked if sandbox not ready |
| POST | `/api/orchestrator/create_patch` | Phase-5: unified diff + rationale tied to evidence/diagnosis |
| POST | `/api/orchestrator/run_patch_sandbox` | Phase-5: temp copy, scrub secrets, allowlisted tests |
| POST | `/api/orchestrator/approve_patch_record` | Phase-5: record patch only (≠ release) |
| POST | `/api/orchestrator/approve_release` | Phase-5: Liara release; blocked if sandbox not ready |
| POST | `/api/orchestrator/create_patch` | Phase-5: unified diff + rationale tied to evidence/diagnosis |
| POST | `/api/orchestrator/run_patch_sandbox` | Phase-5: temp copy, scrub secrets, allowlisted tests |
| POST | `/api/orchestrator/approve_patch_record` | Phase-5: record patch only (≠ release) |
| POST | `/api/orchestrator/approve_release` | Phase-5: Liara release; blocked if sandbox not ready |
| POST | `/api/orchestrator/create_patch` | Phase-5: unified diff + rationale tied to evidence/diagnosis |
| POST | `/api/orchestrator/run_patch_sandbox` | Phase-5: temp copy, scrub secrets, allowlisted tests |
| POST | `/api/orchestrator/approve_patch_record` | Phase-5: record patch only (≠ release) |
| POST | `/api/orchestrator/approve_release` | Phase-5: Liara release; blocked if sandbox not ready |
| POST | `/api/orchestrator/create_patch` | Phase-5: unified diff + rationale tied to evidence/diagnosis |
| POST | `/api/orchestrator/run_patch_sandbox` | Phase-5: temp copy, scrub secrets, allowlisted tests |
| POST | `/api/orchestrator/approve_patch_record` | Phase-5: record patch only (≠ release) |
| POST | `/api/orchestrator/approve_release` | Phase-5: Liara release; blocked if sandbox not ready |
| POST | `/api/orchestrator/create_patch` | Phase-5: unified diff + rationale tied to evidence/diagnosis |
| POST | `/api/orchestrator/run_patch_sandbox` | Phase-5: temp copy, scrub secrets, allowlisted tests |
| POST | `/api/orchestrator/approve_patch_record` | Phase-5: record patch only (≠ release) |
| POST | `/api/orchestrator/approve_release` | Phase-5: Liara release; blocked if sandbox not ready |
| POST | `/api/orchestrator/create_patch` | Phase-5: unified diff + rationale tied to evidence/diagnosis |
| POST | `/api/orchestrator/run_patch_sandbox` | Phase-5: temp copy, scrub secrets, allowlisted tests |
| POST | `/api/orchestrator/approve_patch_record` | Phase-5: record patch only (≠ release) |
| POST | `/api/orchestrator/approve_release` | Phase-5: Liara release; blocked if sandbox not ready |
| POST | `/api/orchestrator/create_patch` | Phase-5: unified diff + rationale tied to evidence/diagnosis |
| POST | `/api/orchestrator/run_patch_sandbox` | Phase-5: temp copy, scrub secrets, allowlisted tests |
| POST | `/api/orchestrator/approve_patch_record` | Phase-5: record patch only (≠ release) |
| POST | `/api/orchestrator/approve_release` | Phase-5: Liara release; blocked if sandbox not ready |
| POST | `/api/orchestrator/create_patch` | Phase-5: unified diff + rationale tied to evidence/diagnosis |
| POST | `/api/orchestrator/run_patch_sandbox` | Phase-5: temp copy, scrub secrets, allowlisted tests |
| POST | `/api/orchestrator/approve_patch_record` | Phase-5: record patch only (≠ release) |
| POST | `/api/orchestrator/approve_release` | Phase-5: Liara release; blocked if sandbox not ready |
| POST | `/api/orchestrator/create_patch` | Phase-5: unified diff + rationale tied to evidence/diagnosis |
| POST | `/api/orchestrator/run_patch_sandbox` | Phase-5: temp copy, scrub secrets, allowlisted tests |
| POST | `/api/orchestrator/approve_patch_record` | Phase-5: record patch only (≠ release) |
| POST | `/api/orchestrator/approve_release` | Phase-5: Liara release; blocked if sandbox not ready |
| POST | `/api/orchestrator/create_patch` | Phase-5: unified diff + rationale tied to evidence/diagnosis |
| POST | `/api/orchestrator/run_patch_sandbox` | Phase-5: temp copy, scrub secrets, allowlisted tests |
| POST | `/api/orchestrator/approve_patch_record` | Phase-5: record patch only (≠ release) |
| POST | `/api/orchestrator/approve_release` | Phase-5: Liara release; blocked if sandbox not ready |
| POST | `/api/orchestrator/create_patch` | Phase-5: unified diff + rationale tied to evidence/diagnosis |
| POST | `/api/orchestrator/run_patch_sandbox` | Phase-5: temp copy, scrub secrets, allowlisted tests |
| POST | `/api/orchestrator/approve_patch_record` | Phase-5: record patch only (≠ release) |
| POST | `/api/orchestrator/approve_release` | Phase-5: Liara release; blocked if sandbox not ready |
| POST | `/api/orchestrator/create_patch` | Phase-5: unified diff + rationale tied to evidence/diagnosis |
| POST | `/api/orchestrator/run_patch_sandbox` | Phase-5: temp copy, scrub secrets, allowlisted tests |
| POST | `/api/orchestrator/approve_patch_record` | Phase-5: record patch only (≠ release) |
| POST | `/api/orchestrator/approve_release` | Phase-5: Liara release; blocked if sandbox not ready |
| POST | `/api/orchestrator/create_patch` | Phase-5: unified diff + rationale tied to evidence/diagnosis |
| POST | `/api/orchestrator/run_patch_sandbox` | Phase-5: temp copy, scrub secrets, allowlisted tests |
| POST | `/api/orchestrator/approve_patch_record` | Phase-5: record patch only (≠ release) |
| POST | `/api/orchestrator/approve_release` | Phase-5: Liara release; blocked if sandbox not ready |
| POST | `/api/orchestrator/create_patch` | Phase-5: unified diff + rationale tied to evidence/diagnosis |
| POST | `/api/orchestrator/run_patch_sandbox` | Phase-5: temp copy, scrub secrets, allowlisted tests |
| POST | `/api/orchestrator/approve_patch_record` | Phase-5: record patch only (≠ release) |
| POST | `/api/orchestrator/approve_release` | Phase-5: Liara release; blocked if sandbox not ready |
| POST | `/api/orchestrator/create_patch` | Phase-5: unified diff + rationale tied to evidence/diagnosis |
| POST | `/api/orchestrator/run_patch_sandbox` | Phase-5: temp copy, scrub secrets, allowlisted tests |
| POST | `/api/orchestrator/approve_patch_record` | Phase-5: record patch only (≠ release) |
| POST | `/api/orchestrator/approve_release` | Phase-5: Liara release; blocked if sandbox not ready |
| POST | `/api/orchestrator/create_patch` | Phase-5: unified diff + rationale tied to evidence/diagnosis |
| POST | `/api/orchestrator/run_patch_sandbox` | Phase-5: temp copy, scrub secrets, allowlisted tests |
| POST | `/api/orchestrator/approve_patch_record` | Phase-5: record patch only (≠ release) |
| POST | `/api/orchestrator/approve_release` | Phase-5: Liara release; blocked if sandbox not ready |
| POST | `/api/orchestrator/create_patch` | Phase-5: unified diff + rationale tied to evidence/diagnosis |
| POST | `/api/orchestrator/run_patch_sandbox` | Phase-5: temp copy, scrub secrets, allowlisted tests |
| POST | `/api/orchestrator/approve_patch_record` | Phase-5: record patch only (≠ release) |
| POST | `/api/orchestrator/approve_release` | Phase-5: Liara release; blocked if sandbox not ready |
| POST | `/api/orchestrator/create_patch` | Phase-5: unified diff + rationale tied to evidence/diagnosis |
| POST | `/api/orchestrator/run_patch_sandbox` | Phase-5: temp copy, scrub secrets, allowlisted tests |
| POST | `/api/orchestrator/approve_patch_record` | Phase-5: record patch only (≠ release) |
| POST | `/api/orchestrator/approve_release` | Phase-5: Liara release; blocked if sandbox not ready |
| POST | `/api/orchestrator/create_patch` | Phase-5: unified diff + rationale tied to evidence/diagnosis |
| POST | `/api/orchestrator/run_patch_sandbox` | Phase-5: temp copy, scrub secrets, allowlisted tests |
| POST | `/api/orchestrator/approve_patch_record` | Phase-5: record patch only (≠ release) |
| POST | `/api/orchestrator/approve_release` | Phase-5: Liara release; blocked if sandbox not ready |
| POST | `/api/orchestrator/create_patch` | Phase-5: unified diff + rationale tied to evidence/diagnosis |
| POST | `/api/orchestrator/run_patch_sandbox` | Phase-5: temp copy, scrub secrets, allowlisted tests |
| POST | `/api/orchestrator/approve_patch_record` | Phase-5: record patch only (≠ release) |
| POST | `/api/orchestrator/approve_release` | Phase-5: Liara release; blocked if sandbox not ready |
| POST | `/api/orchestrator/create_patch` | Phase-5: unified diff + rationale tied to evidence/diagnosis |
| POST | `/api/orchestrator/run_patch_sandbox` | Phase-5: temp copy, scrub secrets, allowlisted tests |
| POST | `/api/orchestrator/approve_patch_record` | Phase-5: record patch only (≠ release) |
| POST | `/api/orchestrator/approve_release` | Phase-5: Liara release; blocked if sandbox not ready |

LangGraph graph (`app.orchestrator.graph`): `load_case → assess → create_plan →
await_approval (interrupt) → execute_stub → verify_stub`. Unit tests use
`MemorySaver` + mocked LLM (`FakeListChatModel`); live Aval is optional.

When Aval is not configured, nodes use deterministic stub plans (documented
choice). Wire Aval via Settings (`llm_base_url`, `llm_model`, `llm_api_key`).

Phase-1 deploy (behind approval + WriteGuard): `POST /v1/projects`,
`POST /v2/projects/{name}/sources`, `POST /v2/projects/{name}/releases`.
Live writes require `LIARA_API_TOKEN` **and** `LIARA_ALLOW_LIVE_WRITES=1`;
default tests use httpx mocks. Timeout → `unknown` + read-only reconcile.

Phase-2 ops (approval + WriteGuard): restart, resize (cost unknown), domains,
SSL (request accepted ≠ cert valid), DNS records only when zone owned (else
handoff). `update_envs` stays **disabled** until L-D03 merge/replace is proven.
Resume: `GET /api/orchestrator/operations/{id}` and
`POST /api/orchestrator/resume_operation` load by id / `client_request_id`
without duplicate writes.

Phase-3 troubleshoot: collect evidence (sanitize logs; missing metrics → gaps),
structured diagnosis (no confidence %), direct-fix options behind approval +
WriteGuard. Ineffective fix → open-need, zero autonomous retry.

Phase-3 troubleshoot: collect evidence (sanitize logs; missing metrics → gaps),
structured diagnosis (no confidence %), direct-fix options behind approval +
WriteGuard. Ineffective fix → open-need, zero autonomous retry.

Phase-3 troubleshoot: collect evidence (sanitize logs; missing metrics → gaps),
structured diagnosis (no confidence %), direct-fix options behind approval +
WriteGuard. Ineffective fix → open-need, zero autonomous retry.

Phase-3 troubleshoot: collect evidence (sanitize logs; missing metrics → gaps),
structured diagnosis (no confidence %), direct-fix options behind approval +
WriteGuard. Ineffective fix → open-need, zero autonomous retry.

Phase-3 troubleshoot: collect evidence (sanitize logs; missing metrics → gaps),
structured diagnosis (no confidence %), direct-fix options behind approval +
WriteGuard. Ineffective fix → open-need, zero autonomous retry.

Phase-3 troubleshoot: collect evidence (sanitize logs; missing metrics → gaps),
structured diagnosis (no confidence %), direct-fix options behind approval +
WriteGuard. Ineffective fix → open-need, zero autonomous retry.

Phase-3 troubleshoot: collect evidence (sanitize logs; missing metrics → gaps),
structured diagnosis (no confidence %), direct-fix options behind approval +
WriteGuard. Ineffective fix → open-need, zero autonomous retry.

Phase-3 troubleshoot: collect evidence (sanitize logs; missing metrics → gaps),
structured diagnosis (no confidence %), direct-fix options behind approval +
WriteGuard. Ineffective fix → open-need, zero autonomous retry.

Phase-3 troubleshoot: collect evidence (sanitize logs; missing metrics → gaps),
structured diagnosis (no confidence %), direct-fix options behind approval +
WriteGuard. Ineffective fix → open-need, zero autonomous retry.

Phase-3 troubleshoot: collect evidence (sanitize logs; missing metrics → gaps),
structured diagnosis (no confidence %), direct-fix options behind approval +
WriteGuard. Ineffective fix → open-need, zero autonomous retry.

Phase-3 troubleshoot: collect evidence (sanitize logs; missing metrics → gaps),
structured diagnosis (no confidence %), direct-fix options behind approval +
WriteGuard. Ineffective fix → open-need, zero autonomous retry.

Phase-3 troubleshoot: collect evidence (sanitize logs; missing metrics → gaps),
structured diagnosis (no confidence %), direct-fix options behind approval +
WriteGuard. Ineffective fix → open-need, zero autonomous retry.

Phase-3 troubleshoot: collect evidence (sanitize logs; missing metrics → gaps),
structured diagnosis (no confidence %), direct-fix options behind approval +
WriteGuard. Ineffective fix → open-need, zero autonomous retry.

Phase-3 troubleshoot: collect evidence (sanitize logs; missing metrics → gaps),
structured diagnosis (no confidence %), direct-fix options behind approval +
WriteGuard. Ineffective fix → open-need, zero autonomous retry.

Phase-3 troubleshoot: collect evidence (sanitize logs; missing metrics → gaps),
structured diagnosis (no confidence %), direct-fix options behind approval +
WriteGuard. Ineffective fix → open-need, zero autonomous retry.

Phase-3 troubleshoot: collect evidence (sanitize logs; missing metrics → gaps),
structured diagnosis (no confidence %), direct-fix options behind approval +
WriteGuard. Ineffective fix → open-need, zero autonomous retry.

Phase-3 troubleshoot: collect evidence (sanitize logs; missing metrics → gaps),
structured diagnosis (no confidence %), direct-fix options behind approval +
WriteGuard. Ineffective fix → open-need, zero autonomous retry.

Phase-3 troubleshoot: collect evidence (sanitize logs; missing metrics → gaps),
structured diagnosis (no confidence %), direct-fix options behind approval +
WriteGuard. Ineffective fix → open-need, zero autonomous retry.

Phase-3 troubleshoot: collect evidence (sanitize logs; missing metrics → gaps),
structured diagnosis (no confidence %), direct-fix options behind approval +
WriteGuard. Ineffective fix → open-need, zero autonomous retry.

Phase-3 troubleshoot: collect evidence (sanitize logs; missing metrics → gaps),
structured diagnosis (no confidence %), direct-fix options behind approval +
WriteGuard. Ineffective fix → open-need, zero autonomous retry.

Phase-3 troubleshoot: collect evidence (sanitize logs; missing metrics → gaps),
structured diagnosis (no confidence %), direct-fix options behind approval +
WriteGuard. Ineffective fix → open-need, zero autonomous retry.

Phase-3 troubleshoot: collect evidence (sanitize logs; missing metrics → gaps),
structured diagnosis (no confidence %), direct-fix options behind approval +
WriteGuard. Ineffective fix → open-need, zero autonomous retry.

Phase-3 troubleshoot: collect evidence (sanitize logs; missing metrics → gaps),
structured diagnosis (no confidence %), direct-fix options behind approval +
WriteGuard. Ineffective fix → open-need, zero autonomous retry.

Phase-3 troubleshoot: collect evidence (sanitize logs; missing metrics → gaps),
structured diagnosis (no confidence %), direct-fix options behind approval +
WriteGuard. Ineffective fix → open-need, zero autonomous retry.

Phase-3 troubleshoot: collect evidence (sanitize logs; missing metrics → gaps),
structured diagnosis (no confidence %), direct-fix options behind approval +
WriteGuard. Ineffective fix → open-need, zero autonomous retry.

Phase-3 troubleshoot: collect evidence (sanitize logs; missing metrics → gaps),
structured diagnosis (no confidence %), direct-fix options behind approval +
WriteGuard. Ineffective fix → open-need, zero autonomous retry.

Phase-3 troubleshoot: collect evidence (sanitize logs; missing metrics → gaps),
structured diagnosis (no confidence %), direct-fix options behind approval +
WriteGuard. Ineffective fix → open-need, zero autonomous retry.

Phase-3 troubleshoot: collect evidence (sanitize logs; missing metrics → gaps),
structured diagnosis (no confidence %), direct-fix options behind approval +
WriteGuard. Ineffective fix → open-need, zero autonomous retry.

Phase-3 troubleshoot: collect evidence (sanitize logs; missing metrics → gaps),
structured diagnosis (no confidence %), direct-fix options behind approval +
WriteGuard. Ineffective fix → open-need, zero autonomous retry.

Phase-4 dependencies: discover postgres/mysql/redis/disk from package.json /
`.env.example` / `liara.json` (file-backed). `create_database` and `create_disk`
stay **disabled** until L-D05 live proof; discovery + open-need/handoff always
work. When enabled, create is approval + WriteGuard; connection URLs go to
SecretService (never logged). Incomplete resources stay on
`Case.constraints.pending_resources`. Missing required deps block “complete
success” on verify.

Phase-5 code patch: `create_patch` builds a limited unified diff tied to
evidence/diagnosis ids; sandbox applies it on a **temp copy** (never live prod),
scrubs `SECRETS_MASTER_KEY` / `LIARA_API_TOKEN` / similar, and runs an allowlisted
test command. When network isolation is unavailable (plain subprocess), the
limitation is documented and `ready_for_release` stays false (fail-closed).
**Red tests never auto-release.** Approvals are separate:
`approve_patch_record` ≠ `approve_release`. Registry tool `sandbox_run` starts
documented and promotes to tested under mock. GenUI kind: `patch_diff` (+ reuse
`approval_card`).

Phase-6 maintain: `/api/maintain/*` — enable/disable monitors (enable ≠ write),
periodic check stub, incident dedupe/resolve, RecoveryBaseline before sensitive
writes, recovery plan draft (still needs fresh `approve_plan` + `execute_plan`),
sanitized audit list, owner/viewer roles (viewer cannot execute writes). Remaining
adapters (`adapter_django` / `laravel` / `dotnet` / `static` / `docker`) stay
**documented** only. GenUI: `monitor_status`, `incident_card`, `recovery_plan`.

CORS allows `WEB_ORIGIN` / `http://localhost:3000` for the web app.

## Local Liara token (do not commit)

1. **Settings UI** — open web `/settings`, paste token once, save (value is not echoed back).
2. **Env bootstrap** — put `LIARA_API_TOKEN` in root `.env` (gitignored). Optional for scripts.
3. **Prove read**:

```sh
# Uses Settings secret if saved; else LIARA_API_TOKEN from env
uv run python -m app.scripts.prove_liara_read
```

The script never prints the token. Live prove is optional; mocked tests cover
401/403/404/429/timeout without a real account.

## Liara client notes

- Auth: `Authorization: Bearer <TOKEN>` ([docs](https://docs.liara.ir/references/api/about/))
- Reads: `GET /v1/me`, `GET /v1/projects`, `GET /v1/projects/{name}`, releases, logs, events, metrics/cpu, metrics/memory
- Writes (allowlisted): `POST /v1/projects`, `POST /v2/projects/{name}/sources`, `POST /v2/projects/{name}/releases`
- Team scope: query param `teamID` when configured
- Errors classified: unauthorized / forbidden / not_found / rate_limited / timeout
- Response bodies sanitized before logging
- Live writes gated by `LIARA_ALLOW_LIVE_WRITES=1` (never print/commit tokens)
