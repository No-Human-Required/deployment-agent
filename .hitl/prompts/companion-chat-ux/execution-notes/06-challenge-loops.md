# 06-challenge-loops — execution note

- 06-challenge-loops.md
  - status: implemented
  - execution conversation / checkout: hitl-slice-builder / liara-agent (repo root)
  - changed files / artifacts:
    - `src/lib/challengeLoops.ts` — catalog inventory + `resolveChallengeLoopRoute` / `extractProjectNameFromGoal`
    - `src/lib/challengeLoops.test.ts` — area coverage, routing, client contract shapes
    - `src/lib/intake.ts` — `troubleshoot` / `maintain_monitor` intake kinds (service-only)
    - `src/lib/intake.test.ts` — updated gating expectations
    - `src/lib/schemas.ts` — intake kinds; evidence / diagnosis / fix_options / monitor on `orchestratorRun`
    - `src/lib/api.ts` — `collectEvidence`, `diagnoseCase`, `proposeFixOptions`, `createPlanFromFix`, `enableMonitor`
    - `src/lib/orchestratorCards.ts` — chat GenUI for evidence / diagnosis / monitor (no readiness dump)
    - `src/components/agent-ui/GenerativeCard.tsx` — intake kinds for troubleshoot/maintain
    - `src/components/PlanApprovalPanel.tsx` — quiet GenUI includes evidence/monitor
    - `src/App.tsx` — route after assess: deploy/ops/domain intake+HITL; troubleshoot evidence→fix→HITL; maintain enable (≠ write); no deploy stub for those loops
  - verification run and results:
    - `npm test -- --run` — 9 files, 48 passed
    - `cd apps/agent && uv run pytest tests/test_orchestrator.py tests/test_deploy.py tests/test_ops.py tests/test_maintain.py tests/test_troubleshoot.py tests/test_liara_domains.py -q` — 53 passed
  - verification not run and limitations:
    - No live Liara writes / paid ops
    - No live collect_evidence against a real project token
    - No browser walkthrough of Investigate → Approve
    - `npm run build` not run
    - Recovery plan HITL path (`POST /api/maintain/recovery/plan`) exists on BFF + agent tests; shell CTA still uses enable-monitor (recovery remains API-ready, not a separate nav button)
  - finalization basis, if finalized: (coordinator owns)
  - implementation decisions / findings:
    - **Gap fixed:** maintain/troubleshoot goals previously fell through `create_plan` → deploy stub. Routed via `resolveChallengeLoopRoute` so Investigate / monitor CTAs hit real BFF paths.
    - Troubleshoot: `collect_evidence` → `diagnose` → `propose_fix_options` → first enabled option → `create_plan_from_fix` → existing HITL Approve; if no enabled option, stop at diagnosis with clear limitation text (no fake deploy plan).
    - Maintain: `enableMonitor` (grants_write_permission false); chat shows monitor_status GenUI; recovery still requires separate HITL on BFF.
    - Deploy / ops resize / domain unchanged: GenUI intake → `create_plan` payloads → HITL.
    - Domains list contract cited from slice 05 (+ extended in challengeLoops.test).
  - deviations from prompt: none material. Recovery CTA not added as new product surface (non-goal); documented as live-safe limitation.
  - specialist findings / selection changes:
    - investigation-debugging: root cause was shell routing to deploy stub, not missing BFF — applied.
    - system-architecture (light): keep writes behind HITL; monitor enable ≠ write auth — applied.
    - agent-workspace-ux: useful GenUI for evidence/diagnosis/monitor; chat stays free of readiness/UUID dumps — applied.
  - learning candidates, if any: none (definition matched; implementation-only routing fix).
  - implications for remaining prompts: none — last companion-chat-ux slice.
  - blocking reason / skipped rationale, if applicable: none

## Capability evidence table

| Challenge area | Shell entry | Client / BFF path | Evidence | HITL / writes | Live-only limitation |
| --- | --- | --- | --- | --- | --- |
| Setup / first deploy | Chat deploy/setup goal → GenUI intake | `create_case` → `assess_readiness`(+`app_path`) → intake → `create_plan(deploy)` → approve/execute | `intake.test.ts` payloads; `challengeLoops.test.ts` route + plan schema; agent `test_deploy.py` / `test_orchestrator.py` | Approve required | No live Liara deploy in this slice |
| Ops (resize) | Chat resize goal → GenUI intake | `create_plan(ops.resize)` → approve/execute | `intake.test.ts` ops payload; `challengeLoops.test.ts`; agent `test_ops.py` | Approve required | No live resize |
| Monitor / maintain | Monitoring nav incidents + CTA | `GET /api/maintain/incidents`; CTA → `enableMonitor` (≠ write) | `schemas.nav.test.ts` incidents; `challengeLoops.test.ts` monitor schema + route; agent `test_maintain.py` | Enable ≠ write; recovery HITL on BFF | No live health checks against real URL |
| Troubleshoot | My Services Investigate / chat | `collect_evidence` → `diagnose` → `propose_fix_options` → `create_plan_from_fix` → HITL | `challengeLoops.test.ts` routing + evidence/fix schemas; agent `test_troubleshoot.py` | Fix writes need Approve | No live evidence against real project |
| Domains | Domains nav list + attach CTA | `GET /api/liara/domains`; CTA → domain intake → `create_plan(ops.domain)` → HITL | Slice 05 notes + `schemas.nav.test.ts` + `challengeLoops.test.ts` domains parse | Attach needs Approve | No live domain create/SSL |
