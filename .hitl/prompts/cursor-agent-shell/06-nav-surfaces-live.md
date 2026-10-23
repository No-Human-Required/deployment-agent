# Nav surfaces live

## Goal

Back My Services, Deployments, Monitoring, Domains, and Agent History nav surfaces with real companion APIs (or honest empty/error states), replacing demo placeholders.

## Developer Review

- **Output:** Each nav surface loads from `apps/agent` where APIs exist; clear empty/loading/error; no fake success. History uses conversation store and/or companion audit/cases if available.
- **Ownership:** `src/App.tsx` nav content regions and/or `src/components/nav/*`; `src/lib/api.ts` helpers. Prefer read-only list endpoints; do not add ungated writes.
- **Depends on:** 04 (05 may land in parallel chronologically — integrate cards if useful but not required).
- **Acceptance:** Build/tests pass; Services uses live catalog (improve beyond prove-read if better endpoint exists); Monitoring/Domains/Deployments show live or explicit “not configured / no data”; History lists prior chats.

## Context

- Companion: `POST /api/liara/prove-read` (projects), `GET /api/liara/plans`, maintain `GET /api/maintain/monitors/{id}`, `GET /api/maintain/incidents`, `GET /api/maintain/audit`; orchestrator cases/operations. Domains/env ops may be plan-gated — list/read only here.
- Current shell still has placeholder copy for several nav pages (see `NavPlaceholder` / demo blocks in `App.tsx`).
- Slice 02 interim: `getServices` via prove-read — keep or replace with clearer dedicated flow.

## Requirements

1. My Services: live list with refresh; empty when no token; error surfacing.
2. Deployments: best-effort from plans/operations/prove-read; honest empty if none.
3. Monitoring: list monitors/incidents from maintain API when possible; else empty + CTA.
4. Domains: read-only summary if API available; else explicit unsupported/empty (no fake domains).
5. Agent History: list saved conversations (local store OK) with open-in-chat; optional audit entries if cheap.
6. Loading/error/empty for each surface; FA/RTL where shell already toggles.
7. `npm test` + `npm run build`; `execution-notes/06-nav-surfaces-live.md`.

## Relevant Skills

- `.cursor/skills/api-design/SKILL.md`
- `.cursor/skills/ux-design/SKILL.md`

## Acceptance Criteria

- [ ] No demo-fake services when token missing (prompt Settings).
- [ ] At least Services + History are live/useful; other surfaces live or honestly empty.
- [ ] Build and tests pass.

## Verification

```sh
npm test
npm run build
```

## Non-goals

UI excellence polish (07); retiring Next (08); new agent write capabilities.

## Execution Handoff

Auto slice; do not edit `prompt-plan.md`; write execution note only.
