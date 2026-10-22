# External integrations

Use this guidance when an upstream provider controls part of the contract. Combine with synchronous or event guidance as applicable.

## Establish the actual dependency contract

Inspect the provider's applicable official documentation, configured API/SDK version, existing adapter, and observed behavior. Distinguish documented guarantees from assumptions and observations. If sources conflict, record the uncertainty before depending on a guarantee. Do not infer rate limits, retry safety, or sandbox/production equivalence from a successful example.

Identify the provider account/tenant mapping, credential ownership, required scopes, and domain owner responsible for reconciliation. Keep provider-specific payloads and failures at an appropriate boundary; translate only what the consuming application needs. Do not build a generic provider abstraction unless actual consumers or substitution requirements justify it.

## Failure budgets and recovery

Bound latency and retries across all layers, including retries already performed by the SDK. Use provider-supported retry semantics and rate-limit signals; establish a stopping condition and outcome when the budget is exhausted. If a write outcome is ambiguous, determine whether the provider supports stable operation identities, status lookup, or another reconciliation path. Blind retries are not a recovery strategy for potentially repeated side effects.

Establish acceptable degraded behavior during provider outages. Fallbacks, caches, or circuit breakers are choices justified by consumer needs, not mandatory additions. Make diagnostic correlation possible without logging credentials or sensitive payloads.

## Inbound webhooks

Verify origin and integrity using the provider's documented mechanism, including its exact payload and timestamp requirements. Establish replay tolerance, duplicate handling, event ordering, acknowledgment timing, and eventual processing failures. Acknowledging receipt and completing business effects are separate promises. Treat validly signed input as external data that still needs schema and domain validation.

## Rollout and evidence

Check provider version transitions, credential/scope changes, and behavior while old and new consumers coexist. Determine how local state is reconciled after partial success or missed notifications.

Use relevant provider fixtures, documented examples, local failure simulation, and authorized sandbox checks. Mocks prove behavior against the modeled contract, not the provider's current runtime behavior. Report which evidence was obtained and what remains uncertain; do not perform live writes merely to verify a design without authorization.
