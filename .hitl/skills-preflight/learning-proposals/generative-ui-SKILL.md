---
name: generative-ui
description: Design UI surfaces driven by structured agent or model output—plan cards, approval flows, live operation status, and progressive chat-to-UI composition. Use when generative or agent-backed interfaces map schemas to components; not for static marketing pages or unconstrained model-authored HTML/CSS.
---

# Generative UI

## Role and reasoning standards

Reason as a principal engineer for agent-facing interfaces: the UI must make proposals, permissions, progress, and outcomes legible without implying stronger system guarantees than exist. Prefer schema-bound component composition over free-form generated markup. The model may choose among allowed view types and fill validated slots; it must not invent new privileged actions or hidden writes through the UI layer.

Recommend the smallest set of reusable surfaces that cover the product loop (goal → evidence → plan → approval → run → result). Do not add GenUI frameworks, streaming kits, or animation suites unless they reduce real ambiguity for this product.

## Boundary with UX design

[UX design](../ux-design/SKILL.md) owns journeys, accessibility, RTL/responsive behavior, and interaction reliability. This skill owns how validated agent payloads become those surfaces: which schema fields map to which components, what is generative vs fixed chrome, and how streaming/partial output appears without lying about completion. Load UX design whenever human-facing acceptance criteria matter; do not treat generative-ui as a substitute.

## Evidence and questions

Inspect existing component libraries, agent output schemas, approval records, and operation status models. Confirm whether visual designs exist and their authority. Establish locale (e.g. Persian RTL) and which tokens stay LTR (IDs, diffs, logs, URLs).

Ask whether UI is chat-primary, form-primary, or hybrid only when it changes information architecture. Prefer evidence from the PRD and current schemas over speculative dashboard density.

## Failure modes and decisions

- **Schema → view:** define an allowlist of view kinds (e.g. readiness findings, plan card, approval, step progress, open-need, verification). Unknown kinds degrade to a safe readable fallback—never to executable controls.
- **Authority of display:** generated copy is suggestion until the user accepts; buttons that mutate systems require an approval or policy gate already decided by the orchestrator, not by the renderer.
- **Partial and streaming output:** show incomplete regions as incomplete; do not enable confirm on a half-built plan. Stopping generation must clarify whether backend work continues.
- **State honesty:** distinguish draft proposal, submitted approval, accepted operation, unknown provider outcome, and verified result. Optimistic UI must match reversibility.
- **Secrets and dense data:** never render secret values; redact in exports. Place machine identifiers and diffs in LTR islands inside RTL layouts when required.
- **Empty / error / limited capability:** when a tool is disabled or API-limited, say so in the same surface—do not fake success with demo data in a “complete” claim.
- **Motion and chrome:** use motion only to clarify status hierarchy; avoid decorative GenUI that obscures the active decision.

## Contributions across stages

- Requirements: observable UI outcomes for plan review, approval, run status, and open-need handoff; non-goals for freeform generated pages.
- Structure: view allowlist, payload→component map, ownership of chrome vs generative slots.
- Technical decisions: streaming transport, component registry, RTL/LTR rules, fallback rendering.
- Verification: keyboard/focus on dynamic regions, approval disabled until schema-complete, stale stream ignored, redaction checks, mobile width from agreed minimum.

Use [agent-orchestration](../agent-orchestration/SKILL.md) for schemas and HITL gates that feed these views, and UX design for journey and a11y standards. API and reliability skills apply when UI promises match backend contracts.

## Expected output

A proportional UI composition plan: allowlisted views, schema field mapping, streaming/partial rules, approval affordances, RTL/LTR conventions, fallbacks for limited capabilities, and acceptance checks. Prefer notes in the shared plan over a separate design system unless reuse demands it.

## Out of scope

- Creative/marketing motion suites and 3D toolchains.
- Unconstrained “LLM writes the whole page” without a component allowlist.
- Backend graph topology and tool registry (agent-orchestration).
- General product journey definition without generative payload mapping (UX design alone).
