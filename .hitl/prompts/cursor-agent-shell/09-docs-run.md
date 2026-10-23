# Docs + run

## Goal

Document the agent-workspace UX and how to run the full stack (Vite shell + `apps/agent` + Docker) end-to-end for demos and developers.

## Developer Review

- **Output:** Updated README and/or `docs/liara-companion.md` (or new short runbook) covering: env, compose, migrate, agent, Vite, Settings (Liara+Aval), chat HITL flow, ports; known limitations.
- **Ownership:** `README.md`, `docs/**`, maybe `.env.example` comments. No feature work.
- **Depends on:** 08.
- **Acceptance:** A new developer can follow docs to bring up shell+agent; HITL/propose≠execute called out; ports accurate (5173 / 8000 / Postgres 5433 if still used).

## Context

- Postgres often on host 5433 in this project; confirm `docker-compose.yml`.
- Aval defaults: `https://api.avalai.ir/v1`, model user-configurable.
- Auto-run completed slices 01–08 — docs should match reality.

## Requirements

1. Root quickstart: Docker → migrate/seed → agent → Vite (`npm run dev` / `dev:all`).
2. Settings + prove-read + chat approve flow briefly.
3. Link challenge/PRD if present; note Next retired.
4. `execution-notes/09-docs-run.md`.
5. Optional: smoke that README commands’ paths exist.

## Relevant Skills

- `.cursor/skills/technical-documentation/SKILL.md` if present

## Acceptance Criteria

- [ ] Runbook matches current stack.
- [ ] HITL called out.
- [ ] No secret examples with real credentials.

## Verification

```sh
# docs review + path existence checks
test -f apps/agent/pyproject.toml && test -f src/App.tsx && test -f vite.config.ts
```

## Non-goals

New features; commits/PRs.

## Execution Handoff

Auto slice; do not edit `prompt-plan.md`; write execution note only. Final slice of agreed list.
