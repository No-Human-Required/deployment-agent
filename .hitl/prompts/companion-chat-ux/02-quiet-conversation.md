# Quiet conversation

## Goal

Stop dumping orchestrator internals into chat bubbles; keep a natural dialogue until the user’s intent is clear; pass the selected workspace folder as `app_path` into companion/orchestrator calls.

## Developer Review

- **Output:** Chat transcript shows conversation + useful summaries only (no readiness/UUID/raw tool dumps). Project-bound API calls include `app_path` from slice 01 workspace. Orchestrator may still run behind the scenes; disclosure belongs in later timeline/Inspector slices, not message spam.
- **Ownership:** `src/App.tsx`, card/message rendering (`GenerativeCard`, Inspector hooks as needed), `src/lib/api.ts` call sites. Prefer not expanding backend contracts unless a call already accepts `app_path` and the UI simply omits it.
- **Dependencies:** `01-workspace-chat-list` finalized — use `localWorkspace.path` / workspace key.
- **Acceptance:** New/continued chats do not show «نتیجه بررسی آمادگی», case UUIDs, model-ready strings, or `create_case`/`assess_readiness` tool labels in bubbles; `assessReadiness` / plan / deploy-related client calls that support `app_path` receive the folder path when set.
- **Open decision:** None — keep HITL approve buttons; do not remove plan approval.

## Context

Sibling plan: `.hitl/prompts/companion-chat-ux/prompt-plan.md`.  
Decisions: Chat noise decided; Intake GenUI is slice 04 (do not build full GenUI here); Timeline is slice 03.  
Slice 01 delivered: `src/lib/workspace.ts`, gated chat, `pickLocalPath`, conversations v3 by folder.

## Requirements

1. Remove or stop appending internal orchestrator telemetry into assistant/user message bubbles (readiness findings card spam, UUID case lines, raw tool timeline as chat text).
2. Prefer short conversational assistant replies while gathering intent; do not auto-surface full readiness/plan dumps as the first response pattern.
3. When a local workspace folder is selected, pass it as `app_path` to orchestrator/client helpers that already accept it (at minimum readiness/plan paths used from the shell).
4. Preserve HITL: sensitive execution still requires Approve control (propose ≠ execute).
5. Do not implement request-derived timeline UI (03), GenUI intake cards (04), Domains (05), or full challenge smoke (06).

## Relevant Skills

- `.cursor/skills/agent-workspace-ux/SKILL.md`
- `.cursor/skills/ux-design/SKILL.md`

## Technical Notes

- Inspect `startOrchestratorGoal` and message/card rendering in `App.tsx` / `GenerativeCard.tsx` / `orchestratorCards.ts`.
- Internal run state may remain in `orchestratorRun` for Inspector; just keep it out of the transcript unless framed as a short human summary.
- FA/EN strings for any new user-facing copy.

## Structure / File Guidance

- Likely: `src/App.tsx`, `src/components/agent-ui/GenerativeCard.tsx`, `src/lib/orchestratorCards.ts`, tests under `src/lib/*.test.ts`.

## Implementation Instructions

Implement only this slice. Write `execution-notes/02-quiet-conversation.md`. Do not edit `prompt-plan.md`. Do not commit.

## Acceptance Criteria

- [ ] Starting a chat no longer dumps readiness/UUID/tool-id noise into the message list.
- [ ] Assistant responses stay conversational until a clearer intake/plan UX (later slices) takes over.
- [ ] With a selected folder, relevant API calls include `app_path`.
- [ ] HITL approve path still works for plan execution.
- [ ] Tests updated/added where practical for card/message filtering or API payload shaping.

## Verification

- `npm test` for affected suites.
- Note any unrun manual chat walkthrough.

## Execution Handoff

- Prompt: `.hitl/prompts/companion-chat-ux/02-quiet-conversation.md`
- Plan: `.hitl/prompts/companion-chat-ux/prompt-plan.md`
- Auto mode: implement → execution note → coordinator reconciles.

## Non-goals

- Timeline UI, GenUI service/plan cards, Domains BFF, challenge E2E proof.
