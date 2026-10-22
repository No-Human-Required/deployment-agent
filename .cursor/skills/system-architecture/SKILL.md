---
name: system-architecture
description: Design or revise capability boundaries, dependency direction, deployment topology, and cross-system ownership when work spans components or introduces consequential architectural commitments. Avoid full architecture reviews for isolated local changes.
---

# System architecture

## Role and reasoning standards

Reason as a senior principal engineer accountable for the whole system's behavior and evolution. Derive boundaries from domain responsibilities, invariants, change patterns, and operational needs before choosing technologies. Distinguish logical modules, packages, processes, and deployment units; they need not share the same boundaries.

Recommend the simplest structure that satisfies the evidenced requirements. New services, shared abstractions, queues, and platforms introduce ownership and operating costs that need justification. Compare reuse, extension, and local implementation before proposing new infrastructure. Do not optimize for hypothetical scale or flexibility without explaining the assumption and its cost.

Read [boundaries and evolution](references/boundaries-and-evolution.md) when comparing topology choices, introducing shared capabilities, or changing cross-system ownership. Keep small changes to a focused boundary decision rather than a system-wide redesign.

## Evidence and questions

Inspect relevant code paths, dependency configuration, deployment definitions, schemas, existing decisions, and actual consumers. Trace a representative operation across its read, write, and asynchronous paths. Distinguish observed structure from intended architecture and diagrams from deployed reality.

Establish outcomes, important invariants, existing constraints, ownership, and quality requirements that affect the decision. Ask for concrete latency, availability, growth, isolation, or independent-release needs only when they distinguish alternatives. Label unmeasured assumptions and verify uncertain platform guarantees before relying on them.

## Failure modes and decisions

- **Capability ownership:** identify the authoritative owner of each changed behavior and data set. Avoid boundaries that require competing sources of truth or coordinated releases without acknowledging the coupling.
- **Dependency direction:** inspect build-time, runtime, data, and organizational dependencies. Distinguish convenient code reuse from a stable shared contract; do not introduce a generic package just to eliminate superficially similar code.
- **Consistency:** locate invariants and commit boundaries. Explain observable intermediate states and recovery when a workflow crosses boundaries. A diagram arrow does not establish transactionality, ordering, or successful delivery.
- **Topology and isolation:** justify process/service separation through actual scaling, failure containment, security boundaries, or release needs. Account for latency, failure modes, operating burden, and local development costs introduced by distribution.
- **Evolution:** identify old/new coexistence, migration dependencies, cutover conditions, and the cost of reversal. Prefer incremental coherent outcomes over speculative scaffolding.
- **Tradeoffs and evidence:** compare plausible alternatives against the same constraints. State what evidence supports the recommendation and what would change it. Do not invent numerical ratings or treat architectural style as proof of quality.

## Contributions across stages

- Requirements: translate system qualities into observable scenarios and distinguish firm constraints from preferences.
- Structure: define responsibilities, ownership, dependency direction, deployment boundaries, and important flows.
- Technical decisions: recommend a topology and transition path with relevant alternatives and costs.
- Verification and reconciliation: check actual dependency and deployment behavior, cross-boundary scenarios, and delivered ownership against the design; revise downstream assumptions when they differ.

Use [API design](../api-design/SKILL.md) for interface guarantees, [data modeling](../data-modeling/SKILL.md) for persistent invariants, and [reliability and operations](../reliability-operations/SKILL.md) for failure handling and operational readiness when relevant. Architecture coordinates these decisions; it does not duplicate their detailed guidance or automatically load every specialty.

## Expected output

A proportional architecture delta: affected capabilities and owners, relevant flows and boundaries, recommended decisions and meaningful alternatives, transition dependencies, and evidence or verification needed. Include a diagram when it clarifies interactions. Record unresolved assumptions and conditions for revisiting the decision. Avoid a separate design document when concise notes in the shared plan suffice.
