# Causal investigation

Use this guidance when a straightforward reproduction does not distinguish the cause or when findings must support a consequential decision.

## Discriminating experiments

For each serious hypothesis, identify the mechanism, evidence for and against it, and an observation that would weaken it. Choose an experiment whose plausible outcomes separate explanations. Change one relevant factor at a time where possible; when that is impractical, disclose confounders. Do not repeatedly rerun the same inconclusive check without a reason.

Reduce inputs and dependencies while preserving the suspected mechanism. A smaller reproduction that removes concurrency, network boundaries, or data distribution may no longer represent the original failure. Compare with a known-good baseline when available, and distinguish environmental changes from code changes.

## Timing and performance

For intermittent behavior, capture ordering, concurrent actors, cancellation, retries, and state transitions relevant to the hypothesis. Instrumentation can alter timing; distinguish what the instrumentation proves from what it may obscure. Deterministic scheduling or fault injection can provide useful evidence but does not automatically reproduce production conditions.

For performance claims, establish the metric, comparable workload, environment, warm/cold conditions, and variability. Inspect distributions and bottlenecks relevant to user impact rather than relying only on an average or a single favorable sample. Do not add arbitrary repetition counts or numerical confidence unsupported by the experiment.

## Feasibility and decision support

Frame the decision and constraints before choosing a prototype. Target the assumption most likely to invalidate the approach. State what the experiment can establish and what remains outside it, such as production scale, compatibility, or operational reliability. A happy-path demonstration is evidence of that path, not proof of deployability.

## Closing the investigation

Explain the causal chain supported by evidence and why a proposed fix interrupts it. Include a targeted regression check and relevant boundary cases rather than mirroring implementation details. When full reproduction is unavailable, label indirect evidence and remaining alternatives explicitly.

Keep mitigation, root-cause correction, and future hardening separate in the report. Finish when the agreed decision is supported or the investigation boundary is reached; provide the smallest next evidence-gathering step if still blocked. Do not silently broaden an investigation into implementation or claim a cause merely because a workaround removed the symptom.
