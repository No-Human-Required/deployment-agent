# Catalog patch (proposed)

Target: `.cursor/skills/discovery-orchestrator/references/specialist-catalog.md`

Insert these rows into the specialist table (after Analytics instrumentation, before Data modeling is fine; order is not semantic):

| Skill | Selection signals | Expected contribution |
| --- | --- | --- |
| [Agent orchestration](../../agent-orchestration/SKILL.md) | AI agent workflows, LangGraph/LangChain-style graphs, tool calling, schema-bound agent outputs, human-in-the-loop interrupts before sensitive writes | Graph/step design, propose-vs-execute boundaries, HITL gates, tool registry expectations, persistence and reconcile behavior |
| [Generative UI](../../generative-ui/SKILL.md) | UI composed from structured agent/model output; plan, approval, and live status surfaces; progressive chat-to-UI mapping | View allowlists, schema→component mapping, streaming/partial honesty, generative vs fixed chrome, safe fallbacks |

Also extend the “Combine these” paragraph with one sentence:

> Agent orchestration owns executable agent control flow and HITL gates; generative UI owns mapping validated agent payloads onto UI surfaces. Pair generative UI with UX design for journeys and accessibility; do not select generative UI for static non-agent screens, or agent orchestration for one-shot prompts without tools or approvals.

## File placements after approval

- `.cursor/skills/agent-orchestration/SKILL.md` ← content of `agent-orchestration-SKILL.md`
- `.cursor/skills/generative-ui/SKILL.md` ← content of `generative-ui-SKILL.md`
- Update catalog as above

## Declined in this preflight

- `secrets-and-sensitive-ops` — deferred; secret hygiene kept as concerns inside agent-orchestration + existing skills
- `claudedesign` — not proposed
- Generic `python` — deferred until stack choice
- `langchain-rag` — not selected for core ops agent

## Validation (walkthrough)

| Case | Expected selection |
| --- | --- |
| Liara companion: plan → approve → deploy graph | agent-orchestration (+ api, reliability as needed) |
| Plan/approval/status cards from agent JSON | generative-ui + ux-design |
| Static landing page, no agent payloads | neither new skill |
| Pure docs RAG over Liara docs only | not agent-orchestration; RAG skill if any |
| Counterexample: renaming a button label | ux-design only / general judgment |
