# GenUI cards parity

## Goal

Bring companion GenUI card types into the Vite shell chat/inspector allowlist so orchestrator/ops/troubleshoot/deps/patch/monitor results render as structured cards (not wall-of-text), with HITL approvals staying on explicit card actions.

## Developer Review

- **Output:** Extended `ViewPayload` schemas + `GenerativeCard` (and/or small view components) covering plan, approval, evidence, diagnosis, ops/domain, dependency plan, patch diff, monitor/incident — wired where orchestrator/chat already surfaces structured payloads; unknown types fall back safely.
- **Ownership:** `src/lib/schemas.ts`, `src/components/agent-ui/**`, chat/inspector rendering in `src/App.tsx` / `Inspector.tsx` / `PlanApprovalPanel.tsx` as needed. Prefer mapping companion response fields into cards; avoid rewriting `apps/agent` unless adding a thin `ui` hint already supported.
- **Depends on:** 04.
- **Acceptance:** Build/tests pass; at least plan + approval + one evidence/diagnosis-style card render from fixtures or mapped orchestrator data; unknown payload → safe fallback; approve still button-based.

## Context

- Existing shell: `src/components/agent-ui/GenerativeCard.tsx` + `ViewPayload` discriminated union (service_status, deployment_progress, timeline, tool_call, log_viewer, metric, error_analysis, root_cause, approval, operation_result, service_health, unsupported).
- Companion Next GenUI registry (historical): PlanCard, ApprovalCard, EvidencePack, DiagnosisCard, FixOptions, EnvDiff, DomainStatus, DependencyPlan, PatchDiff, MonitorStatus, IncidentCard, OperationStatus, ReadinessFindings, RecoveryPlan, VerificationResult, Handoff, OpenNeed, UnknownFallback.
- Slice 04 already has `PlanApprovalPanel` — integrate or replace with GenerativeCard `plan`/`approval` types without losing HITL.
- FA/RTL: follow shell locale toggle.

## Requirements

1. Add Zod card types for companion-relevant surfaces (minimum: `plan`, `approval`, `evidence_pack` or `readiness_findings`, `diagnosis`, `dependency_plan`, `patch_diff`, `incident`/`monitor_status`, `operation_status`/`verification_result`). Keep `unsupported` fallback.
2. Implement renderers in `GenerativeCard` or split views under `src/components/agent-ui/views/`.
3. Chat/inspector: when orchestrator returns plan/steps/findings, emit/map into these cards (reuse 04 data shapes).
4. Vitest for schema parsing of new card types (accept good / reject garbage).
5. `npm test` + `npm run build`; `execution-notes/05-genui-cards-parity.md`.

## Relevant Skills

- `.cursor/skills/generative-ui/SKILL.md` (if present)
- `.cursor/skills/ux-design/SKILL.md`
- `.cursor/skills/api-design/SKILL.md`

## Acceptance Criteria

- [ ] Plan and approval cards render with explicit approve/reject actions.
- [ ] ≥3 additional companion card kinds render with fixtures or live-mapped data.
- [ ] Unknown types do not crash UI.
- [ ] Build and tests pass; HITL still button-gated.

## Verification

```sh
npm test
npm run build
```

## Non-goals

Live nav catalog pages (06); visual excellence pass (07); retiring Next (08).

## Execution Handoff

Auto slice; do not edit `prompt-plan.md`; write execution note only.
