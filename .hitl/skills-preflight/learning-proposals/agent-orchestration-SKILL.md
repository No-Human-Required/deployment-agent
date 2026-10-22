---
name: agent-orchestration
description: Design or revise AI agent workflows with tool use, structured outputs, human-in-the-loop gates, persistence, and safe execution boundaries. Use when building LangGraph/LangChain-style agents, approval-gated operations, or schema-bound orchestration—not for plain RAG pipelines or one-shot LLM prompts.
---

# Agent orchestration

## Role and reasoning standards

Reason as a senior engineer accountable for agent reliability and user control. Model the workflow as explicit steps with owned state, not as free-form chat that happens to call APIs. Separate what the model may propose from what the system may execute. Prefer the smallest graph that meets evidenced needs: linear tools when enough; branching, loops, and interrupts only when they change outcomes.

Treat model text as untrusted input. Executable effects require validated structured output, authorization, and an owned executor—never “the model said so.” Do not invent provider capabilities, latency SLAs, or autonomous recovery that the runtime cannot enforce.

When implementing with LangGraph, load the environment's `langgraph-fundamentals` skill (if present) for StateGraph mechanics; this specialist owns product decisions (gates, schemas, tool boundaries), not framework API trivia.

## Evidence and questions

Inspect existing graphs, tool registries, schemas, checkpointers, approval records, and failure logs. Trace one representative user goal from intent through tool calls to durable outcome. Establish which steps need human approval, which are read-only, and what happens when a write times out or the model fails schema validation.

Ask only questions that change graph shape, approval policy, or verification. Prefer repository and API evidence over speculative multi-agent designs.

## Failure modes and decisions

- **Propose vs execute:** model outputs plans, diagnoses, or tool arguments; a non-model layer validates, authorizes, and performs side effects. Reject paths where the LLM holds raw credentials or directly mutates production without an approval record when the product requires HITL.
- **Structured contracts:** consequential outputs use schemas (plan steps, diagnosis, patch intent). On validation failure: no write fallback; surface a bounded retry or open-need state.
- **HITL interrupts:** sensitive writes pause with a concrete, reviewable proposal (scope, effect, cost known/unknown, recovery). Rejection, edit, and expiry invalidate dependent execution; do not silently continue.
- **Persistence:** long-running work survives process crash and browser close via checkpointed operation identity; retries are idempotent or reconcile-read-only after unknown outcomes.
- **Tool registry:** each tool has status (documented / tested / enabled / disabled), preconditions, side effects, and recovery. Disabled or untested tools must not be presented as complete capabilities.
- **Secrets and telemetry:** pass secret references, never secret values, into model context, logs, URLs, or exports. Sanitize tool results before LLM consumption.
- **Scope control:** prefer one orchestrator with clear nodes over multiple competing agents unless ownership and handoff are explicit. Do not add RAG, multi-agent swarms, or decision-model classifiers unless they discriminate a real requirement.

## Contributions across stages

- Requirements: agent-visible outcomes, approval obligations, open-need vs success criteria, non-goals for autonomy.
- Structure: graph nodes/edges, state ownership, tool boundaries, interrupt points, checkpointer placement.
- Technical decisions: LangGraph vs simpler chains, schema libraries, idempotency and reconcile strategy, model failure policy.
- Verification and reconciliation: schema-fail paths, approval expiry, duplicate submit, timeout-after-write, and “model text ≠ executed command” checks.

Use [API design](../api-design/SKILL.md) for tool/provider contracts, [reliability and operations](../reliability-operations/SKILL.md) for unknown outcomes and recovery, [system architecture](../system-architecture/SKILL.md) for process boundaries, and [generative-ui](../generative-ui/SKILL.md) when agent outputs drive UI surfaces. Do not duplicate UX journey ownership from [UX design](../ux-design/SKILL.md).

## Expected output

A proportional orchestration delta: graph or step map, state fields that matter, schemas for consequential outputs, HITL gate list, tool registry expectations, failure/reconcile behavior, and verification scenarios. Record assumptions about model and provider limits. Avoid a standalone agent design doc when shared-plan notes suffice.

## Out of scope

- Pure RAG indexing/retrieval design → use a RAG-specific skill if present.
- Visual journey, accessibility, and RTL product UX → UX design.
- Mapping validated agent payloads onto UI components → generative-ui.
- Standing security policy documents beyond orchestration-relevant secret hygiene.
