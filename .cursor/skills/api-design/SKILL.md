---
name: api-design
description: Define and review caller-provider contracts for endpoints, services, events, or integrations, including errors, compatibility, and authorization semantics.
---

# API design

## Role and reasoning standards

Reason as a senior principal engineer accountable for caller outcomes and the provider's ability to honor its contract. Every consequential promise needs a precise meaning, an owner capable of fulfilling it, and evidence that it holds. Separate required guarantees, verified capabilities, and untested assumptions.

Challenge the boundary before designing the interface: why is an API needed, who owns the capability, and can an existing contract satisfy the use case? Model the domain capability rather than exposing storage structure by default. Recommend the smallest sufficient contract and explain meaningful alternatives and their costs.

Scale depth to impact and uncertainty. These standards guide reasoning, not a mandatory questionnaire or permission to redesign adjacent systems. A narrow change may need only a short contract delta and targeted checks.

## Load relevant guidance

- Read [synchronous APIs](references/synchronous-apis.md) for request/response operations, retriable mutations, query semantics, or long-running operations initiated by requests.
- Read [events](references/events.md) for published events, message consumers, asynchronous delivery, or replay.
- Read [external integrations](references/external-integrations.md) when depending on a provider outside the team's control, including inbound webhooks.

Combine references when boundaries overlap; do not load unrelated modes by default. References supply decision criteria, not universal technology choices.

## Evidence and questions

Inspect actual consumers, handlers, schemas, tests, installed versions, and applicable upstream documentation. Identify current behavior separately from intended behavior. Establish caller identity, capability ownership, data sensitivity, usage patterns, and compatibility obligations. Cite the code, examples, or documentation supporting consequential decisions; do not invent unavailable external guarantees.

For each important operation, establish caller intent, preconditions, permitted state transitions, invariants, observable success and failure, and what happens when the outcome is unknown. Use concrete examples to expose ambiguity before choosing transport, framework, or payload shapes. Ask the user about consequential missing requirements; answer discoverable implementation questions from evidence.

## Failure modes and decisions

Apply the following where they affect the changed contract:

- **Consistency and failure:** identify when an operation takes effect, what readers can observe, how concurrent operations interact, and how callers recover after ambiguous outcomes. Do not promise retries, atomicity, ordering, or cancellation that the implementation cannot enforce across relevant failures.
- **Authorization:** establish which actors may perform which operations on which resources and fields, how tenant boundaries are enforced, and what errors reveal. Check access to both submitted references and returned data; authentication alone is insufficient.
- **Compatibility:** examine actual consumers and rollout order. Consider behavioral changes as well as schema shape: defaults, error handling, ordering, enum values, validation, timing, and retry behavior may break callers. Specify coexistence and retirement expectations when relevant.
- **Operational limits:** derive appropriate payload/page bounds, deadlines, rate limits, backpressure, and diagnostic context from expected usage and provider capabilities. Do not invent capacity or latency commitments without evidence. Distinguish contractual guarantees from internal targets.
- **Verification:** map important promises to observable examples or checks that could disprove them. Include relevant access, failure, concurrency, and old-consumer cases. Distinguish tests performed from checks proposed and documentation claims from verified runtime behavior.

## Contributions across stages

- Requirements: consumer scenarios, externally observable outcomes, invariants, and evidence of success.
- Structure: justified provider/caller boundaries, contract ownership, and integration dependencies. Bring persistent integrity questions to the data-modeling skill when needed.
- Technical decisions: precise semantics, meaningful alternatives, compatibility, rollout, and operational tradeoffs supported by evidence.
- Verification and reconciliation: check both ends of changed contracts, compare delivered guarantees with agreed ones, and carry actual findings into downstream prompts. Unproven promises remain explicit open decisions.

## Expected output

For consequential changes, capture the following in the shared plan or selected prompt, keeping detail proportional to the task:

- Consumer scenarios, including important failure and recovery paths.
- Contract decisions: operations, invariants, guarantees, limitations, and responsible owners.
- Recommended approach, meaningful alternatives rejected, and reasons.
- Compatibility and rollout implications for existing consumers.
- Verification evidence or proposed checks, with limitations clearly labeled.
- Open decisions and the evidence needed before a credible commitment.

Link existing schemas instead of duplicating them. Create a formal specification only when warranted. A small change can capture these as concise notes; do not require a separate design document or manufacture irrelevant concerns.
