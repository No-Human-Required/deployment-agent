---
name: analytics-instrumentation
description: Define and review behavioral analytics in application code when measurement meaning, event placement, identity, consent, attribution, experiments, or data quality affect product decisions. Use for shared analytics packages and product instrumentation; not for operational telemetry or generic message delivery alone.
---

# Analytics instrumentation

## Role and reasoning standards

Reason as a senior principal engineer accountable for whether product decisions drawn from analytics are valid and whether collecting the data respects the application's privacy and operating constraints. A tracking call is useful only when its meaning, population, timing, and provenance are clear enough to interpret. Derive instrumentation from decisions and user journeys before choosing events, SDK methods, dashboards, or storage.

Distinguish a business fact, an observed interaction, an exposure, an assignment, and a derived metric. Each has a different owner and point of truth. Recommend the smallest set of signals that answers the stated questions; extra events create cost, privacy exposure, and contradictory interpretations. Treat analytics as evidence with known loss and bias, not as an authoritative transaction log unless a separate contract actually makes it one.

Scale the work to the decision. A new shared analytics layer needs explicit identity, consent, and measurement boundaries. One additional feature event may need only a catalog entry, a placement decision, and a targeted check. Do not turn this guidance into a mandatory tracking plan for unrelated code changes.

## Evidence and questions

Inspect the user journey and the code paths where the relevant state changes, including client navigation, server mutations, retries, authentication transitions, flags, and payment callbacks when applicable. Read current analytics calls, event definitions, dashboards or queries, privacy and consent rules, retention settings, and relevant architecture decisions. Identify which systems own the underlying facts. Verify version-specific SDK behavior against the installed version and official documentation before relying on autocapture, identity merging, persistence, offline delivery, or retry semantics.

Start with the decision the team wants to make and the comparison it requires. Establish the unit of analysis, eligible population, numerator and denominator, event time, time window, and meaningful segments for consequential metrics. Ask for a definition only when competing answers would change implementation or interpretation; do not demand a full metrics catalogue before a bounded first increment. Label inferred questions, proposed definitions, and existing commitments separately.

## Measurement and code boundaries

Apply these checks where they affect the work:

- **Event meaning and ownership:** Name an event for a specific occurrence, define who emits it and when, and state which properties are required, optional, or forbidden. Keep product-specific events and business meaning with the application; put only genuinely shared contracts and safeguards in a shared package. Avoid multiple producers claiming the same fact without a deduplication rule.
- **Placement and timing:** Emit at the boundary that proves the event happened. Distinguish a button click from a completed operation, a page render from a viewed page, and a payment attempt from a settled payment. Consider rerenders, navigation, retries, background work, and partial failures. Use authoritative server facts for outcomes that a client cannot establish; document any deliberate client-only proxy.
- **Metric integrity:** State how missing, duplicated, delayed, and out-of-order events affect each important measure. Decide whether an event needs a stable identity or correlation key, and whether the collector can honor that decision. Preserve occurrence time separately from receipt time when their difference matters. Do not promise exactly-once collection from best-effort SDK calls.
- **Identity and sessions:** Define the lifecycle of anonymous, authenticated, and account or tenant identifiers, including sign-in, sign-out, account switching, shared devices, and deletion. Specify which actor or entity each metric counts. Do not silently join unrelated people or tenants, or assume a provider's merge behavior. Use stable internal identifiers where permitted; avoid direct personal identifiers unless a justified policy explicitly allows them.
- **Consent and data minimization:** Identify which tracking purposes require consent and where collection, storage, and transmission are gated. Define what happens before a choice, after refusal, and after revocation, including buffered events and persisted identifiers. Restrict properties by purpose; examine sensitive values, free text, URLs, query strings, high-cardinality fields, and accidental payload capture. Keep product analytics distinct from operational diagnostics and essential processing.
- **Acquisition and attribution:** Define which referral or campaign context is captured, its source and lifetime, and whether first-touch or later-touch interpretation is intended. Distinguish web acquisition analytics from mobile-install attribution and from authoritative marketing or payment records. Do not imply that an analytics event proves an external attribution or financial fact.
- **Experiments:** Distinguish variant assignment, evaluation, and actual exposure. Define the exposure trigger, randomization unit, experiment and variant identifiers, eligibility, conversion window, and guardrail events before analyzing effects. Record enough context to distinguish intended treatment from unavailable evaluation or fallback. Avoid double exposure from repeated evaluation or rendering. Do not claim causal results from a dashboard without checking allocation, sample, and measurement quality.
- **Provider and runtime boundary:** Keep product code on a clear factory contract when a shared package is warranted. Make environment, regional destination, credentials, and permitted platform explicit. An analytics outage must have an agreed effect on the product flow; bound any queue, retry, flush, or offline behavior to that requirement. Do not introduce a durable outbox merely because events exist; justify it from the cost of losing a particular signal.

## Validation and evolution

Verify instrumentation against representative journeys, including the negative path where the named occurrence did not happen. Inspect actual emitted payloads, not just calls to a mock. Check consent refusal and revocation, anonymous-to-authenticated transitions, account switching, retries, duplicate renders, provider failure, and regional routing where relevant. For a consequential metric, compare a small sample with its authoritative source or manually traceable cases and explain expected gaps. A passing unit test proves mapping, not the correctness of a dashboard or SDK behavior in production.

When changing an existing event, inspect its current producers and consumers before renaming or repurposing it. Preserve historical meaning or introduce a new event or schema with an explicit coexistence and cutover plan. State how old and new data will be interpreted; a type change in one package does not rewrite past events. Retire unused events and properties when their measurement purpose ends.

Coordinate with [API design](../api-design/SKILL.md) for caller contracts and external SDK integration, [system architecture](../system-architecture/SKILL.md) for capability and regional boundaries, [data modeling](../data-modeling/SKILL.md) for durable identity or deletion invariants, and [reliability and operations](../reliability-operations/SKILL.md) when collection needs recoverable processing. The generic [events guidance](../api-design/references/events.md) applies when analytics uses a real producer-consumer messaging contract; do not import broker or outbox requirements into ordinary best-effort tracking by analogy.

## Contributions across stages

- Requirements: turn product questions into interpretable measures, identify the eligible population and privacy constraints, and separate essential signals from speculative collection.
- Structure: assign ownership of facts, identity, event catalogues, consent gates, provider adapters, and authoritative sources.
- Technical decisions: choose event placement, schemas, delivery expectations, attribution and experiment semantics, compatibility, and meaningful alternatives using evidence.
- Verification and reconciliation: check payloads and journeys against the promised meaning, record collection limitations, and correct downstream assumptions when observed data differs.

## Expected output

A proportionate measurement contract in the shared plan or prompt: questions and metric definitions, events with owners and trigger points, identity and consent behavior, source-of-truth boundaries, collection failure semantics, and checks that could falsify the interpretation. Mark provider capabilities and production data quality as verified, proposed, or unknown. Include only the dimensions relevant to the current task; do not manufacture a universal event catalogue or require a separate analytics strategy document for a small change.
