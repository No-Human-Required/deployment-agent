# Request timeline

## Goal

Show a user-facing progress timeline derived from the **current request / plan**, not the fixed internal pipeline labels (`create_case`, `assess_readiness`, …).

## Developer Review

- **Output:** Inspector (or existing timeline surface) lists human-readable steps for the active goal with pending/done/error; labels adapt to intent (deploy vs troubleshoot vs domain vs generic).
- **Ownership:** `src/App.tsx` timeline construction, `Inspector.tsx` as needed, small helper module + tests. Prefer mapping plan steps / goal heuristics over inventing a new BFF.
- **Dependencies:** `02-quiet-conversation` finalized — chat stays quiet; timeline is the progress surface.
- **Acceptance:** After a plan exists, timeline reflects plan/request steps in FA/EN-friendly language; no raw tool ids as primary labels; status updates as run progresses.
- **Open decision:** None — if plan body has steps, prefer those; else intent-based stub steps until plan arrives.

## Context

Plan: `.hitl/prompts/companion-chat-ux/prompt-plan.md`.  
Timeline decided: request-derived. Chat noise handled in 02 (`orchestratorCards` chat vs inspector).  
Current: `orchestratorRun.timeline` often uses tool names like `create_case` / `assess_readiness`.

## Requirements

1. Replace primary timeline titles/details that expose internal tool ids with user-facing copy derived from the goal and/or `plan_body` steps.
2. Keep statuses (pending/done/error) and useful short details (without UUIDs as the main text).
3. Update timeline as the run moves (planning → awaiting approval → executing → done/error).
4. Do not reintroduce timeline dumps into chat bubbles.
5. Non-goals: GenUI intake (04), Domains (05), challenge E2E (06).

## Relevant Skills

- `.cursor/skills/agent-workspace-ux/SKILL.md`
- `.cursor/skills/ux-design/SKILL.md`

## Technical Notes

- Inspect how `timeline` is set in `startOrchestratorGoal` and after approve/execute.
- If `plan_body.steps` (or equivalent) exists, map to timeline entries.
- FA/EN via existing language toggle.

## Implementation Instructions

Slice only. Write `execution-notes/03-request-timeline.md`. Do not edit `prompt-plan.md`. Do not commit.

## Acceptance Criteria

- [ ] Timeline labels are understandable for a non-engineer (FA/EN).
- [ ] Deploy-like vs other goals do not all show the same create_case/assess_readiness wording as primary titles.
- [ ] When a plan with steps exists, timeline aligns with those steps.
- [ ] Chat remains free of tool-id timeline spam.
- [ ] Tests cover mapping helper(s) where practical.

## Verification

- `npm test` for affected suites; note unrun UI checks.

## Execution Handoff

Auto: implement → `execution-notes/03-request-timeline.md` → coordinator reconciles.

## Non-goals

GenUI cards, Domains API, full challenge loops.
