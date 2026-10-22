# Decisions and readiness

Use this guidance when uncertainty or cross-system work makes decomposition consequential.

## Resolve the right problem

Translate a requested mechanism into its intended outcome without discarding the user's explicit choices. Establish current behavior, affected actors, desired change, and what evidence would show improvement. Where sources disagree, record source authority and implications instead of resolving disagreement by recency or confidence of phrasing alone.

For a consequential decision, capture the question, constraints, credible alternatives, recommendation, evidence, owner, and remaining uncertainty. Explain costs in terms of the task: migration effort, compatibility, operational load, recoverability, or user impact. Distinguish a reversible local choice from a shared commitment requiring coordination. Reopen decisions when evidence changes their basis, not merely because another alternative exists.

## Make uncertainty actionable

For a blocking unknown, identify the decision it affects, the smallest evidence-gathering action, and the condition for stopping. An investigation slice should produce a finding or decision aid, not promise a favored answer. Continue independent work when its assumptions genuinely do not depend on that result.

Check dependencies through shared schemas, ownership, invariants, fixtures, and deployment order as well as code imports. Mark unresolved contract consumers provisional. Do not claim parallel safety where two slices could each make a reasonable but incompatible decision.

## Readiness and reconciliation

A ready slice has a coherent outcome, known required inputs, accepted boundaries, feasible verification, and explicit unresolved questions that do not prevent its execution. Its deliverable may be evidence rather than code. A useful acceptance criterion distinguishes success from a plausible incomplete result.

At reconciliation, compare what was promised with what exists and what was verified. Identify changes to dependent assumptions before drafting the next slice. Keep task completion separate from pending workflow-improvement proposals; `/hitl-improve` reviews those separately. Approval gates and shared-file coordination remain governed by the main workflow; do not create additional gates for routine choices.
