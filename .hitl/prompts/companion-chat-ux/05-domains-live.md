# Domains live

## Goal

Replace the Domains nav stub with a live surface backed by Liara domain APIs (list/check via BFF; attach/SSL remain HITL write paths already modeled in the agent).

## Developer Review

- **Output:** `apps/agent` HTTP endpoint(s) exposing `LiaraClient.list_domains` (and check if useful); Vite Domains nav loads real data for a selected project/service; clear errors when token/project missing; writes still via existing WriteGuard/HITL (chat intake from 04 may start domain ops — do not bypass Approve).
- **Ownership:** `apps/agent/app/api/` (+ tests), `src/lib/api.ts`, `NavigationView.tsx` Domains render, schemas as needed.
- **Dependencies:** 01 (settings/token), 04 (chat domain intake exists — nav is separate).
- **Acceptance:** With token + project, Domains page shows list (or empty state); API failures are explicit; no fake domains; create/attach still requires HITL if initiated from UI (link to chat or reuse ops plan — prefer “start domain goal in chat” CTA over silent writes).
- **Open decision:** None — list is read-only on the page; mutations go through orchestrator HITL.

## Context

`LiaraClient.list_domains(project=)` exists; no FastAPI route yet; `NavigationView.renderDomains` is a muted stub. Challenge requires domain guidance + real API use.

## Requirements

1. Add authenticated BFF read route(s) for listing domains by project (workspace token), with tests (mocked Liara client).
2. Wire FE `getDomains(project)` (or equivalent) and Domains nav UI: project/service selector if needed, list status, empty/error states (FA/EN).
3. Do not invent mock domain rows when API fails — show the error.
4. Provide a clear path to attach a domain via chat HITL (e.g. CTA that starts a domain goal) rather than writing from the nav without Approve.
5. Non-goals: challenge E2E matrix (06); redesigning quiet chat/timeline/intake.

## Relevant Skills

- `.cursor/skills/api-design/SKILL.md`
- `.cursor/skills/investigation-debugging/SKILL.md`
- `.cursor/skills/ux-design/SKILL.md`

## Technical Notes

- Follow existing `apps/agent` router/deps patterns (workspace_id, settings token).
- Mirror styles of My Services / Deployments surfaces in `NavigationView`.
- Run `cd apps/agent && uv run pytest` for new Python tests; `npm test` for FE.

## Implementation Instructions

Slice only. Write `execution-notes/05-domains-live.md`. Do not edit `prompt-plan.md`. Do not commit. Do not call live Liara writes in verification.

## Acceptance Criteria

- [ ] BFF list domains endpoint works in unit/integration tests with mocked client.
- [ ] Domains nav no longer shows only the “API not available” stub when token+project available.
- [ ] Empty list and error states are clear.
- [ ] No unattended domain create from the nav page.
- [ ] FE and/or agent tests cover the new contract.

## Verification

- Agent: `uv run pytest` for touched tests.
- FE: `npm test`.
- Note unrun live API checks.

## Execution Handoff

Auto → `execution-notes/05-domains-live.md` → coordinator.

## Non-goals

Full challenge smoke (06); changing intake GenUI (04) unless a tiny nav CTA needs it.
