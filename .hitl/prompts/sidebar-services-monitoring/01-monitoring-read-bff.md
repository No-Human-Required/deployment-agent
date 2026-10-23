# Liara monitoring read BFF

## Goal

Expose authenticated BFF read endpoints for a Liara project's live detail, CPU/memory metrics, and recent logs, wrapping existing `LiaraClient` methods — so the monitoring UI can load real data without inventing upstream APIs.

## Developer Review

- **Output:** HTTP routes under `/api/liara/projects/{name}/…` (or equivalent) returning sanitized public shapes for project status, metrics series (or gap), and log lines (or gap); pytest with mocked client.
- **Ownership:** `apps/agent/app/api/liara.py` (+ thin helper/schemas if needed), `apps/agent/tests/`.
- **Public API:** New read-only endpoints; no writes. Credential resolution via existing `SettingsService` + `workspace_id` query like `/domains` and `/plans`.
- **Dependencies:** none.
- **Acceptance:** 200 with stable JSON; 400 without credentials; 502/404 mapped from `LiaraClientError`; missing metrics/logs return explicit gap fields, not crashes.
- **Open decision:** none.

## Context

Sibling plan: `prompt-plan.md`. Challenge Monitoring & Maintenance needs health + CPU/RAM + logs when available. `LiaraClient` already has `get_project`, `get_cpu_metrics`, `get_memory_metrics`, `get_logs`. BFF today only exposes prove-read, plans, domains — no dashboard reads. Orchestrator `collect_evidence` is case-scoped and unsuitable as a UI feed.

## Requirements

1. Add read endpoint(s) for project detail (at least `name`/`project_id`, `type`, `status`, `isDeployed`, and any safe public fields useful for health).
2. Add read endpoint(s) or a combined monitoring payload for CPU metrics, memory metrics, and recent logs.
3. When Liara returns empty/unsupported metrics or logs, respond with an explicit gap/unavailable indicator (message or `available: false`), not fake series.
4. Reuse credential resolution and error mapping patterns from `list_domains` / `list_plans`.
5. Cover happy path + missing credentials + client 404/auth errors + empty metrics/logs in tests (mock `LiaraClient`).
6. Do not change frontend in this slice (slice 03 consumes the contract).

## Relevant Skills

- `.cursor/skills/api-design/SKILL.md`

## Technical Notes

- Follow FastAPI router style in `apps/agent/app/api/liara.py`.
- Prefer one combined `GET /api/liara/projects/{name}/monitoring?workspace_id=` returning `{ project, cpu, memory, logs, gaps }` **or** separate routes — pick one coherent contract and document it in the response shape; combined is preferred for fewer round-trips.
- Cap log lines (e.g. last 50–100) and strip/omit secrets if present in messages when feasible (reuse sanitize patterns from troubleshoot if cheap).
- Healthy status vocabulary used elsewhere: `RUNNING`, `STARTED`, `READY`, `ACTIVE`; unhealthy includes `STOPPED`, `FAILED`, `ERROR`, `CRASH` — return raw `status`/`isDeployed`; do not invent enums beyond what Liara returns.
- Map `LiaraNotFoundError` → 404 when applicable; other client errors → 502 with `exc.to_dict()` like existing routes.

## Structure / File Guidance

- Extend `apps/agent/app/api/liara.py`.
- Add `apps/agent/tests/test_liara_monitoring.py` (or extend existing liara API tests).
- Optional small normalizer helper next to the router or under `app/services/`.

## Implementation Instructions

Implement only this slice. Write `execution-notes/01-monitoring-read-bff.md` with progress-contract fields. Do not edit `prompt-plan.md`. Do not commit. Do not call live Liara in verification.

## Acceptance Criteria

- [ ] Authenticated monitoring read path exists and returns a documented JSON shape.
- [ ] Missing/empty metrics or logs are explicit gaps.
- [ ] Pytest covers success, credential missing, and client error paths.
- [ ] No write/ops endpoints added.

## Verification

- `cd apps/agent && uv run pytest` for new/touched tests (at least the monitoring tests).
- Note any unrun live Liara checks.

## Execution Handoff

Auto mode: coordinator claims this prompt → `hitl-slice-builder` → `execution-notes/01-monitoring-read-bff.md` → coordinator reconciles before dependents.

## Non-goals

Sidebar UI; monitoring main view; frontend `api.ts` wiring; restart/resize; incident monitors under `/api/maintain`.
