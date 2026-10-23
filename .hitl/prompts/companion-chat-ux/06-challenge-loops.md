# Challenge loops

## Goal

Prove (and fix gaps within agreed scope) that challenge.md capability areas work through the cleaned chat UX: setup/deploy, ops, monitoring/maintain, troubleshooting, Domains (list + HITL attach path), with HITL for sensitive writes.

## Developer Review

- **Output:** Evidence matrix (tests and/or documented smoke with mocked/live-safe checks) covering each challenge area via the new shell path; fix wiring bugs discovered that block those loops **without** expanding beyond companion-chat-ux decisions.
- **Ownership:** Prefer tests in `src/lib/*` and `apps/agent/tests`; small App/api fixes if a loop is broken. Write findings in the execution note.
- **Dependencies:** 01–05 finalized.
- **Acceptance:** For each area — setup/deploy (intake→plan→HITL path), ops, monitor/maintain, troubleshoot, domains — either automated evidence of the path or a fixed break with regression test; list remaining live-only limitations honestly.
- **Open decision:** None — do not require paid live Liara writes; mocks/fixtures preferred.

## Context

Challenge brief: `challenge.md`. Prior slices delivered workspace gate, quiet chat, request timeline, GenUI intake, Domains list. Orchestrator/services largely exist from earlier companion work.

## Requirements

1. Inventory how each challenge area is reached from the shell (chat goal strings, nav CTAs, APIs).
2. Add or extend tests that lock critical client/BFF contracts for those journeys (intake kinds, createPlan payloads, domains list, maintain/troubleshoot entry points as already exposed).
3. Fix concrete breaks found in-repo that prevent a challenge loop from being startable through the cleaned UX.
4. Do not reintroduce chat noise; do not weaken HITL.
5. Record a short capability evidence table in the execution note.

## Relevant Skills

- `.cursor/skills/investigation-debugging/SKILL.md`
- `.cursor/skills/system-architecture/SKILL.md` (light)
- `.cursor/skills/agent-workspace-ux/SKILL.md`

## Technical Notes

- FE: `npm test`. Agent: `uv run pytest` for relevant suites (orchestrator, deploy, ops, maintain, troubleshoot, domains).
- Prefer fixture/mocked HTTP over live tokens.

## Implementation Instructions

Slice only. Write `execution-notes/06-challenge-loops.md` with progress fields **and** a capability evidence table. Do not edit `prompt-plan.md`. Do not commit. Do not perform unauthorized live writes.

## Acceptance Criteria

- [ ] Evidence for deploy/setup path through intake + plan shaping (tests).
- [ ] Evidence for ops and domain HITL plan shaping (tests or fixed wiring).
- [ ] Evidence for monitor/maintain and troubleshoot entry (API/client or UI hook tests).
- [ ] Domains list contract covered (already in 05 — cite or extend).
- [ ] Any blocking UX/API gap found is fixed or explicitly listed as out-of-scope limitation with reason.
- [ ] Full `npm test` green; relevant agent pytest green.

## Verification

Run the tests above; note unrun live end-to-end checks.

## Execution Handoff

Auto → `execution-notes/06-challenge-loops.md` → coordinator finalizes task if criteria met.

## Non-goals

New product surfaces beyond gap fixes; skill changes; git commit/push; `/hitl-review`.
