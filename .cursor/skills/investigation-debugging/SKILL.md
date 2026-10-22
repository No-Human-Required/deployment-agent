---
name: investigation-debugging
description: Investigate unexplained behavior, regressions, or feasibility questions using bounded hypotheses and evidence before choosing a fix or implementation direction.
---

# Investigation and debugging

## Role and reasoning standards

Separate observations from explanations. Seek evidence that distinguishes plausible causes, rather than accumulating support for the first guess. A useful investigation may conclude that evidence is insufficient; it must still identify what was learned and the smallest next step.

Apply senior principal engineering judgment by separating the symptom, triggering conditions, causal mechanism, and systemic contributing factors. Distinguish containment from correction and a plausible explanation from a demonstrated cause. Optimize experiments for decision value and low disruption, not the number of logs or tests collected.

Read [causal investigation](references/causal-investigation.md) for intermittent failures, competing hypotheses, performance regressions, or uncertain feasibility. Small deterministic defects may need only a reproduction, a causal explanation, and a focused regression check.

## Evidence and questions

For bugs, establish expected versus observed behavior, reproduction conditions, environment/version, scope, and recent changes. For feasibility or research, state the decision to support and evidence needed. Inspect code, relevant logs, existing tests, and primary documentation; label limitations and avoid exposing sensitive data in artifacts.

Record enough provenance to interpret evidence: relevant revision/configuration, inputs, timing, and whether the result came from a real run, simulation, or documentation. Establish a baseline and whether the issue existed before suspected changes. Use the repository to answer discoverable questions; ask for missing evidence only when it can change the investigation.

## Failure modes and decisions

Reduce the failing case, track hypotheses and counterevidence, and prefer narrow experiments. Account for nondeterminism, async timing, stale state, environmental differences, and misleading correlations where relevant. Agree an investigation boundary when uncertainty could make work open-ended. Do not silently turn research into a system rewrite or treat an unverified hypothesis as a root cause.

- State competing explanations when evidence permits them, along with predictions that differ. Prefer the smallest experiment that can reject a meaningful alternative.
- Check test-harness and observability assumptions: a mock, timestamp, cache, or logging side effect can hide or manufacture the symptom. Missing logs are not automatically evidence that a code path did not run.
- Preserve relevant pre-fix evidence before a reset or cleanup destroys it. Keep experiments scoped and reversible; live external actions require their own authorization.
- Choose fixes that address the supported mechanism and preserve intended behavior. Explain when a workaround only reduces exposure or when a larger correction is necessary; do not bundle unrelated cleanup.
- Verify that the reproduction fails for the relevant reason before the fix and succeeds after it where feasible. For intermittent failures, report conditions and uncertainty rather than treating one passing run as proof.
- Stop or change direction when experiments no longer reduce consequential uncertainty. State what additional evidence or access would make progress possible.

## Contributions across stages

- Requirements: reproduction or research question, scope, and evidence of success.
- Structure: causal boundaries and likely ownership, provisional until supported.
- Technical decisions: discriminating experiments, fix alternatives, tradeoffs, and remaining uncertainty.
- Verification and reconciliation: regression evidence for a fix, or sourced findings for an investigation; downstream implementation depends on the resulting decision, not assumed findings.

## Expected output

Observed facts and their provenance, hypotheses with supporting and contrary evidence, the best-supported causal explanation or finding, and a recommended next decision. Include scope of impact, alternatives when consequential, and explicit uncertainty. For fixes, add before/after evidence and relevant neighboring behavior checks. For feasibility work, state the conditions under which the recommendation holds. Investigation-only prompts need not produce code; do not manufacture certainty to declare completion.
