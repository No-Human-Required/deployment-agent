---
name: reliability-operations
description: Define failure containment, recovery, observability, capacity, and operational ownership for services, workers, and dependency-heavy workflows when availability or durable processing matters. Avoid imposing production operations on isolated local changes.
---

# Reliability and operations

## Role and reasoning standards

Reason as a senior principal engineer accountable for useful service under failure and for the people operating it. Tie reliability work to user-visible outcomes, durable processing, and explicit recovery needs. Distinguish desired objectives, observed service behavior, and enforceable guarantees.

Every consequential failure policy needs a trigger, bounded response, observable outcome, recovery path, and owner. Prefer the smallest mechanism that addresses the credible failure; retries, redundancy, circuit breakers, and alerts are not inherently improvements. Account for their complexity and failure modes.

Read [failure and recovery](references/failure-and-recovery.md) for distributed dependencies, queues, overload, or recovery-sensitive state. Use [observability and readiness](references/observability-and-readiness.md) when defining operational signals, objectives, or a handoff to operators. Load only guidance relevant to the changed system.

## Evidence and questions

Inspect relevant runtime configuration, dependency behavior, existing metrics/logs/traces, incidents, runbooks, deployment lifecycle, and backup or recovery procedures. Trace the user operation or job through its required dependencies, including background completion. Record unavailable evidence rather than assuming monitoring or recovery already exists.

Establish which outcomes matter, acceptable delay or loss, expected workload, ownership, and operational constraints. Derive objectives and resource budgets from requirements and measurements; do not invent availability percentages, recovery times, capacity claims, or staffing arrangements. Verify platform/version-specific behavior before depending on it.

## Failure modes and decisions

- **Failure containment:** distinguish local, dependency, and shared-resource failures. Identify which users, tenants, jobs, or capabilities are affected and what remains usable. A fallback must preserve agreed semantics rather than disguise failure as success.
- **Bounded work:** coordinate deadlines, cancellation, retry budgets, concurrency, queues, and resource limits across layers. Consider whether recovery attempts amplify an outage or continue after the result is no longer useful.
- **Durable processing:** distinguish acceptance, persistence, execution, and completion. Define recovery for interrupted work, duplicates, partial effects, and unknown outcomes using actual contract and data guarantees.
- **Capacity and overload:** identify the limiting resource and what happens when demand exceeds it. Derive admission, backpressure, or shedding choices from acceptable user outcomes; do not assume scaling removes downstream limits.
- **Recovery:** specify how failures are detected, service is restored, and data is reconciled. Distinguish application rollback from data recovery. Rehearsal evidence matters more than the existence of a backup or runbook.
- **Observability and ownership:** choose signals that reveal impact and support a concrete response. Establish who can act and what action is feasible; do not create alerts with no actionable distinction or responsible owner.

## Contributions across stages

- Requirements: define critical service or job outcomes, acceptable degradation, and recovery needs.
- Structure: map failure domains, shared bottlenecks, runtime dependencies, and operational owners.
- Technical decisions: specify bounded failure policies, capacity assumptions, signals, and recovery steps with tradeoffs.
- Verification and reconciliation: check representative failure/recovery behavior, report limits of rehearsal, and compare delivered behavior with objectives before downstream promises are finalized.

Coordinate with [API design](../api-design/SKILL.md) for caller-visible semantics, [data modeling](../data-modeling/SKILL.md) for durable integrity, and [system architecture](../system-architecture/SKILL.md) for topology choices. Use [investigation](../investigation-debugging/SKILL.md) for unexplained failures. This skill does not automatically authorize incident actions, production load tests, deployments, or destructive recovery.

## Expected output

A scoped operational contract: critical outcomes and objectives, relevant failure scenarios and bounded responses, detection signals and owners, recovery conditions, and validation evidence. Include concise runbook steps when an operator must act, with prerequisites, stop conditions, and post-recovery checks. Clearly distinguish measured results, proposed checks, assumptions, and accepted limitations; do not require a full operations program for a small change.
