# Synchronous APIs

Use this guidance for changed request/response semantics. Focus on the operations and risks in scope; do not turn it into a blanket endpoint audit.

## Operation and representation semantics

Define whether the operation reads, replaces, partially updates, or initiates work. Distinguish omitted, null, empty, and default values where callers can observe different behavior. Establish identifier scope, units, time representation, validation boundaries, and which fields callers may set. Existing transport conventions constrain representation, but do not decide domain semantics.

Separate invalid input, denied access, missing resources, state conflicts, and transient dependency failures when callers need different recovery behavior. Define stable machine-readable error meaning and useful diagnostic correlation without exposing internal details or sensitive existence information. For batch operations, specify whole-batch versus per-item effects and partial-result semantics.

## Retriable mutations and ambiguous outcomes

Establish what identifies one logical operation, its caller/tenant scope, and how concurrent duplicates are coordinated. Decide what happens when the same identity arrives with different input, when a prior attempt is still running, and when stored results expire. Explain the supported retry window and the response to a duplicate.

Inspect how the business effect and duplicate-detection record survive failures; a lookup before a write alone does not establish safe concurrent retries. Consider downstream side effects separately. Do not prescribe a storage technique without inspecting the actual boundary and guarantees.

A timeout may leave the operation committed with its response lost. Define how callers discover the result or retry safely. Cancellation of a request does not necessarily cancel committed work. For long-running work, establish the distinction between acceptance and completion, status visibility, terminal states, and cancellation races.

## Concurrent writes and queries

Identify invariants affected by competing mutations. Choose conflict handling intentionally: conditional writes, serialization, merge semantics, or last-write-wins may be appropriate under different requirements. Explain what callers observe and how they recover; do not assume an application-level check makes a multi-step operation atomic.

For collections, establish bounded page sizes, deterministic ordering and tie-breaking, and cursor/filter scope where relevant. Describe expected behavior as records change between pages; do not promise snapshot consistency unless supported. Define read-after-write expectations, cache freshness, and invalidation only to the extent they matter to consumer outcomes.

## Evidence to seek

Use relevant contract or integration checks to distinguish promised behavior from plausible implementation: a mutation succeeds but the response is lost; two duplicates arrive concurrently; stale updates compete; a cross-tenant reference is submitted; a collection changes between pages. Include old-consumer behavior when changing defaults, errors, or response values. Select cases that challenge this change rather than demanding all cases for every endpoint.
