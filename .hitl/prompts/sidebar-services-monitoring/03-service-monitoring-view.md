# Per-service monitoring main view

## Goal

Clicking a sidebar service opens a main-pane monitoring view for that service: live status, CPU/RAM when available, recent logs, explicit API gaps, and an Investigate CTA into chat — without requiring a local folder.

## Developer Review

- **Output:** Wired sidebar click → main NavigationView (or equivalent) service monitoring; FE client for 01’s BFF; selected-service highlight; Investigate handoff reusing existing My Services pattern.
- **Ownership:** `src/App.tsx`, `src/components/nav/NavigationView.tsx`, `src/lib/api.ts` (+ schemas), CSS as needed.
- **Dependencies:** 01 (monitoring BFF), 02 (sidebar list / selection hooks).
- **Acceptance:** Click shows monitoring for that project; available metrics/logs render; gaps shown clearly; works without folder; Investigate starts chat goal for that service.
- **Open decision:** none.

## Context

Sibling plan + finalized notes from 01 and 02. Prior Monitoring nav showed incidents only and was unreachable from the sidebar. Challenge wants health + resources + logs. Panel placement decided: main pane, not side inspector.

## Requirements

1. Consume 01’s monitoring contract from the frontend (`api.ts` + zod schemas as needed).
2. On sidebar service click: set selection, navigate main pane to service monitoring for that project.
3. Show: project name, status (with tone), CPU/RAM summary or chart/spark if series present (keep simple — table/last value OK), recent log lines, gap messages when unavailable.
4. Investigate CTA: reuse existing handoff that starts an investigate/chat goal with the service in context (see My Services “Investigate” in `NavigationView` / App).
5. Loading and error states for the fetch; refresh control optional but welcome.
6. Works with no local workspace folder.
7. Highlight the selected service in the sidebar.

## Relevant Skills

- `.cursor/skills/agent-workspace-ux/SKILL.md`
- `.cursor/skills/ux-design/SKILL.md`
- `.cursor/skills/api-design/SKILL.md`

## Technical Notes

- Prefer extending `NavigationView` activeNav (e.g. Monitoring mode with `selectedProject`) over a one-off parallel tree.
- Match existing card/section visual language; FA/EN copy.
- Do not dump raw orchestrator internals into the pane.
- If 01 used a combined endpoint, one FE fetch is enough.

## Structure / File Guidance

- `src/lib/api.ts`, `src/lib/schemas.ts`
- `src/components/nav/NavigationView.tsx`
- `src/App.tsx` (navigate + selection from sidebar)
- Optional small presentational component if it keeps NavigationView readable

## Implementation Instructions

Slice only. Write `execution-notes/03-service-monitoring-view.md`. Do not edit `prompt-plan.md`. Do not commit. Reconcile against actual 01 response shape and 02 sidebar markup — do not assume provisional drafts.

## Acceptance Criteria

- [ ] Sidebar click opens main-pane monitoring for that service.
- [ ] Status + available CPU/RAM/logs display; gaps are explicit.
- [ ] Investigate CTA works without requiring a folder for opening the pane (chat may still gate send if product requires folder — do not break existing folder gate for chat send).
- [ ] Selected service is visually indicated in the sidebar.
- [ ] FE tests or typed client cover the monitoring response schema at least lightly.

## Verification

- `npm test` for touched FE tests.
- Note unrun live Liara/UI smoke.

## Execution Handoff

Auto → `execution-notes/03-service-monitoring-view.md` → coordinator. Last slice: finalize in place after verification.

## Non-goals

New write ops; incident-monitor redesign; folder↔service binding; claudedesignskills animations.
