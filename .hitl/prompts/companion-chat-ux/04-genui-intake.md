# GenUI intake

## Goal

After the user’s intent is clear, collect required fields with **in-chat GenUI cards** (service, plan, domain name, etc.) before running a write plan — using the selected workspace folder as `app_path` when deploy/local ops need it.

## Developer Review

- **Output:** Intent-gated intake cards in the chat transcript; submitting selections feeds orchestrator `createPlan` / deploy/ops/deps config (including `app_path` from workspace). HITL Approve still required for writes.
- **Ownership:** `src/lib/schemas.ts` (new view types if needed), `GenerativeCard.tsx`, `App.tsx` flow, `api.ts`, tests. Prefer client-side intake that then calls existing `createPlan` with `deploy`/`ops`/`deps` payloads over a large BFF redesign.
- **Dependencies:** 02–03 finalized. Workspace folder from 01.
- **Acceptance:** For deploy-like goals, user sees service (and plan when needed) cards before execute; domain intent asks for service + domain; values are applied to the plan path; chat stays free of readiness dumps.
- **Open decision:** None — if live services fail to load, show clear error + Settings CTA.

## Context

Plan decisions: Intake GenUI; Deploy target = folder + Liara service via GenUI; `deploy.app_path` deferred from 02 to this slice.  
Existing GenUI has plan/approval/readiness/etc. but no dedicated service/plan picker card — add minimal card type(s).

## Requirements

1. Detect when intake is needed (deploy/setup, ops resize, domain, …) vs pure Q&A; do not force cards on every message.
2. Show in-chat GenUI to select Liara service from live list (and plan from `getLiaraPlans` when required); domain flow: service + domain name.
3. On confirm, pass `app_path` (workspace folder) into deploy/deps plan creation where applicable; then proceed to plan + HITL as today.
4. Keep conversational replies; do not dump internals.
5. Non-goals: Domains **nav page** list API (05), full challenge smoke (06). Domain **chat intake** for attach is in scope here if it unblocks createPlan/ops; page wiring is 05.

## Relevant Skills

- `.cursor/skills/agent-workspace-ux/SKILL.md`
- `.cursor/skills/ux-design/SKILL.md`
- `.cursor/skills/api-design/SKILL.md` (only if client contract shapes change)

## Technical Notes

- Reuse `getServices` / `getLiaraPlans` from `src/lib/api.ts`.
- Extend `knownViewPayloadSchema` + `GenerativeCard` for picker UI; keep Zod strict.
- Wire `createPlan({ deploy: { app_path, project_name, … } })` when intake completes for deploy intents.

## Implementation Instructions

Slice only. Write `execution-notes/04-genui-intake.md`. Do not edit `prompt-plan.md`. Do not commit.

## Acceptance Criteria

- [ ] Deploy/setup intent surfaces service (+ plan if needed) GenUI in chat before write execution.
- [ ] Confirmed intake includes workspace `app_path` on deploy-related plan creation when folder is set.
- [ ] Domain-oriented intake can collect service + domain name in chat (HITL still for writes).
- [ ] HITL Approve remains the authorization gate.
- [ ] Tests for new schema/card mapping / intake helpers where practical.

## Verification

- `npm test`; note unrun live Liara UI checks.

## Execution Handoff

Auto → `execution-notes/04-genui-intake.md` → coordinator.

## Non-goals

Domains nav BFF page (05); challenge E2E matrix (06); redesigning Inspector timeline (03 done).
