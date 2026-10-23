# Workspace + chat list

## Goal

Add a Cursor-like local folder workspace gate: user selects an OS project folder before project-bound chat; conversation history is scoped to that folder and listed in the sidebar.

## Developer Review

- **Output:** Folder picker + persisted workspace path; chats keyed by folder; sidebar recent list for current folder only; general nav (e.g. Settings) usable without a folder.
- **Ownership:** Primarily `src/` (`App.tsx`, `conversations.ts`, related UI/CSS). Prefer native/browser-safe folder selection already used in repo if present (`local_fs` / file input); do not invent a new BFF unless required.
- **APIs:** No required public API change unless folder pick must go through agent; `app_path` persistence is client-side for this slice (agent injection is slice 02).
- **Dependencies:** None (first slice).
- **Acceptance:** Without folder → cannot start project chat (clear CTA to pick folder); after pick → empty or prior chats for that path; switch folder → different chat list; Settings/general still reachable.
- **Open decision:** None — use path string as workspace key (normalize consistently).

## Context

Sibling plan: `.hitl/prompts/companion-chat-ux/prompt-plan.md`.  
Agreed product model: Cursor Agent-like — pick folder first; chats live under that folder; general surfaces may sit outside workspace.  
Current: `src/lib/conversations.ts` stores a flat list under `liaraops-ai:conversation-history` (max 8), not keyed by folder. Sidebar has a non-functional `workspace-switch` and a “recent” list.

## Requirements

1. Persist selected local workspace folder path (and display name) across reloads.
2. Gate **New Chat** / sending project-bound messages until a folder is selected; show clear empty state + pick-folder action (FA/EN as existing i18n pattern).
3. Key conversation storage by workspace folder identity so lists do not mix across folders.
4. Sidebar shows chat list for the **current** folder; support open existing chat + new chat within folder.
5. Changing folder switches the visible chat list (and clears/resets active thread appropriately).
6. Global/general nav (at least Settings) remains available without a folder.
7. Do **not** in this slice: quiet-orchestrator rewrite, GenUI intake, Domains API, or challenge-loop fixes (later prompts).

## Relevant Skills

- `.cursor/skills/agent-workspace-ux/SKILL.md`
- `.cursor/skills/ux-design/SKILL.md`

## Technical Notes

- Reuse existing Vite/React/Tailwind/motion patterns in `src/`.
- Prefer extending `conversations.ts` (version bump if schema changes) over a parallel store.
- Folder selection: use the best existing approach in-repo (e.g. `webkitdirectory` / showDirectoryPicker / agent `local_fs` helper). Document chosen approach in the execution note.
- FA/RTL first-class copy for new strings.

## Structure / File Guidance

- Likely touch: `src/App.tsx`, `src/lib/conversations.ts`, tests under `src/lib/*.test.ts`, possibly `src/index.css` for empty-state.
- Keep Inspector/orchestrator behavior unchanged except where chat list / workspace chrome requires it.

## Implementation Instructions

Implement only this slice. Update schemas/tests for the new conversation store shape. Preserve unrelated working-tree changes. Write progress to `execution-notes/01-workspace-chat-list.md` using the progress-contract fields. Do **not** update `prompt-plan.md` (coordinator owns it).

## Acceptance Criteria

- [ ] User can select a local folder and see it reflected in the workspace chrome.
- [ ] Project chat is blocked with a clear CTA until a folder is selected.
- [ ] Conversations persist per folder; switching folders shows the correct list.
- [ ] Sidebar lists chats for the active folder; opening one restores messages.
- [ ] Settings (or equivalent general surface) works without a folder.
- [ ] Automated tests cover store keying / load-save for multi-folder history where practical.

## Verification

- Run `npm test` for affected vitest suites.
- Manually reason about empty / switch-folder / reload states (note any unrun UI checks).
- Do not require live Liara calls for this slice.

## Execution Handoff

- Prompt: `.hitl/prompts/companion-chat-ux/01-workspace-chat-list.md`
- Plan: `.hitl/prompts/companion-chat-ux/prompt-plan.md`
- Contracts: `docs/agent/workflows/prompt-plan-contract.md`, `docs/agent/repository-quality-contract.md`
- Mode: auto — implement this slice only; write `execution-notes/01-workspace-chat-list.md`; report changed files, verification, deviations, blockers.
- Coordinator will reconcile and finalize before dependents.

## Non-goals

- Orchestrator message cleanup (02), timeline (03), GenUI (04), Domains (05), full challenge smoke (06).
- Pixel-perfect Cursor clone.
