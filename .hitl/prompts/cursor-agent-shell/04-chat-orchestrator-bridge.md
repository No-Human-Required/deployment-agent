# Chat orchestrator bridge

## Goal

Wire the Vite shell chat to the companion LangGraph orchestrator BFF so a user goal creates/advances a Case (plan → HITL approve → execute → verify), with Inspector showing operation timeline — replacing the thin `backend/` investigation/approval path.

## Developer Review

- **Output:** Chat send creates/continues orchestrator cases via `apps/agent` `/api/orchestrator/*`; approval actions use explicit UI (not chat-text “approve”); Inspector activity/timeline reflects case/operation status; thin investigation client paths removed or gated behind companion.
- **Ownership:** `src/lib/api.ts` + schemas for orchestrator; `src/App.tsx` chat/inspector flow; optional `src/components/*` for approval/plan display stubs (full GenUI allowlist is slice 05). May read companion schemas under `apps/agent/app/schemas/` and `apps/agent/app/api/orchestrator.py` for contracts — do not rewrite agent domain logic unless a tiny CORS/origin fix is required.
- **Depends on:** 03.
- **Acceptance:** Build/tests pass; documented happy path from chat message → plan awaiting approval → approve → execute (HITL preserved); Inspector updates; secrets still never echoed.

## Context

- Companion orchestrator routes (prefix `/api/orchestrator`): `POST /cases`, `/assess_readiness`, `/create_plan`, `/approve_plan`, `/execute_plan`, `/continue_or_stop`, `/verify_result`, plus ops/troubleshoot/patch endpoints; `GET /operations/{operation_id}`, `POST /resume_operation`.
- Propose ≠ execute: writes require approval tokens / explicit approve endpoints.
- Slice 02 left thin MVP `investigation` / `approval` client shapes — replace for the main chat path.
- Settings (03) configures Liara + Aval; chat may need workspace_id from settings view.
- GenUI rich cards (PlanCard, ApprovalCard, …) are slice 05 — here a minimal structured plan/approval UI is enough (can reuse existing GenerativeCard/Approval patterns in `src/` if present).

## Requirements

1. Add typed client helpers for at least: create case, create/assess plan, approve plan, execute plan, verify result, get operation (extend as needed for the chat happy path).
2. Chat compose: user message → create case (or attach to active case) → drive readiness/plan; show assistant/status messages in the thread.
3. When plan awaits approval, show explicit Approve / Reject (or Stop) controls that call companion approve/continue endpoints — never treat free-text “approve” as authorization.
4. Inspector: show case id, current stage, recent operations/events/timeline from orchestrator responses.
5. Error handling for missing Liara/Aval config (nudge Settings).
6. `npm test` + `npm run build`; `execution-notes/04-chat-orchestrator-bridge.md`.
7. Prefer FA/RTL copy where the shell already toggles locale.

## Relevant Skills

- `.cursor/skills/agent-orchestration/SKILL.md`
- `.cursor/skills/api-design/SKILL.md`
- `.cursor/skills/ux-design/SKILL.md`

## Acceptance Criteria

- [ ] Primary chat path uses `/api/orchestrator/*` (not thin `backend/` investigate).
- [ ] HITL: gated execute only after explicit approve control.
- [ ] Inspector reflects case/operation progress.
- [ ] Build and tests pass.

## Verification

```sh
npm test
npm run build
# optional live: agent up + configured settings; send a chat goal and observe plan/approval UI
```

## Non-goals

Full GenUI card allowlist (05); live My Services/Deployments pages (06); UI excellence pass (07); retiring Next (08).

## Execution Handoff

Auto slice; do not edit `prompt-plan.md`; write execution note only.
