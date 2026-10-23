# Sidebar services above folders

## Goal

Show Liara services as an account-scoped section **above** Folders in the sidebar, with status dots (online / error / stopped / unknown), working even when no local project folder is selected.

## Developer Review

- **Output:** Services section in `App.tsx` sidebar above the folders accordion; shared status-tone helper + test; FA/EN labels; empty/error states when no token or no projects.
- **Ownership:** `src/App.tsx`, `src/index.css` (reuse `.status-dot` where possible), `src/lib/serviceStatus.ts` (or similar) + vitest.
- **Public API:** none (consumes existing `getServices` / prove-read catalog).
- **Dependencies:** none (disjoint from 01). Click → monitoring navigation is wired in 03; this slice may select/highlight a service in state and leave a clear hook, or no-op click until 03 — prefer setting `selectedServiceId` / navigating to a monitoring nav key if cheap without fetching metrics yet.
- **Acceptance:** With services in state, they appear above Folders without requiring a workspace folder; tones match agreed mapping; without token/services, clear empty copy.
- **Open decision:** none.

## Context

Sibling plan: `prompt-plan.md`. Services already load via `refreshCatalog` → `getServices` but are not listed above folders. User decided services are independent of folders. Status tones: online green, error red, stopped gray, else muted. Existing `.status-dot` / My Services cards in `NavigationView` are references.

## Requirements

1. Add a **Services** sidebar section above the Folders section label/tree.
2. Each row: service name + status dot reflecting tone from project `status` / deploy flags.
3. Mapping (case-insensitive recommended): `RUNNING|STARTED|READY|ACTIVE` → online; `FAILED|ERROR|CRASH` → error; `STOPPED` → stopped; else unknown. If only `isDeployed` is known, treat truthy as online-leaning only when status absent — prefer explicit status.
4. Section works with no local folder selected (same visibility model as Settings).
5. Empty: no token / catalog idle/error / zero services — short FA+EN strings consistent with `shellCopy`.
6. Do not bind a service to a folder path.
7. Non-goals: full monitoring panel data fetch (03); redesign folders accordion.

## Relevant Skills

- `.cursor/skills/agent-workspace-ux/SKILL.md`
- `.cursor/skills/ux-design/SKILL.md`

## Technical Notes

- Reuse `services`, `servicesState`, `servicesError`, `refreshCatalog` already in `App.tsx`.
- Extract pure `serviceStatusTone(status: string, isDeployed?: boolean)` for unit tests.
- Preserve RTL-friendly layout; labels in both `en` and `fa` `shellCopy` blocks.
- Accessibility: list semantics, status not color-only (title/aria-label with tone or status text).

## Structure / File Guidance

- `src/App.tsx` — sidebar markup above folders.
- `src/lib/serviceStatus.ts` + `src/lib/serviceStatus.test.ts`.
- `src/index.css` — tone variants for dots if not already sufficient.

## Implementation Instructions

Slice only. Write `execution-notes/02-sidebar-services-list.md`. Do not edit `prompt-plan.md`. Do not commit.

## Acceptance Criteria

- [ ] Services render above Folders when catalog has items.
- [ ] Works without a selected local folder.
- [ ] Status dots use agreed tones; unit tests cover mapping.
- [ ] Empty/error states are clear in FA and EN.
- [ ] No folder↔service coupling introduced.

## Verification

- `npm test` (or project’s vitest script) for `serviceStatus` tests.
- Manual note: visual check of sidebar order if app running (optional).

## Execution Handoff

Auto → `execution-notes/02-sidebar-services-list.md` → coordinator.

## Non-goals

BFF monitoring endpoints (01); per-service metrics/logs UI (03); changing wallet/settings footer.
