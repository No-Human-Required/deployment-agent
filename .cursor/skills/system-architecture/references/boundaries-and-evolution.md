# Boundaries and evolution

Use this guidance for shared capabilities, topology decisions, or changes that cross ownership boundaries.

## Test proposed boundaries

Trace a representative operation and a relevant failure path through each candidate design. Identify who can change behavior, who owns state, which calls are required for success, and where an invariant could be violated. Examine whether a boundary contains coherent responsibility or merely mirrors a technical layer.

Compare logical separation within an existing process with separate deployment where both are credible. Independent deployment requires compatible contracts and operational ownership, not just a separate directory. Shared storage, synchronous dependencies, or synchronized release requirements may preserve coupling despite service separation.

For reusable packages, identify actual consumers and the stable capability they share. Compare the cost of local duplication with shared evolution, version compatibility, and configuration burden. Do not force unrelated consumers through an abstraction based only on similar code.

## Evaluate alternatives fairly

Use the same concrete scenarios and constraints for each plausible option. Consider behavior, data integrity, failure containment, deployment, developer workflow, and maintenance only where they change the decision. Explain the dominant tradeoff rather than accumulating unsupported scores.

For build-versus-reuse choices, check fit, integration cost, ownership, migration/exit cost, and operational dependencies. Verify relevant current product or platform capabilities before relying on them. Existing infrastructure is evidence of availability, not proof that it is appropriate for every task.

## Plan the transition

Distinguish destination structure from the next coherent increment. Identify old/new contract coexistence, authority during transition, data movement, and cutover/recovery conditions. Avoid a state where two components each believe they are authoritative without a reconciliation policy.

List decision dependencies as well as code dependencies; downstream interfaces should not harden around an unresolved ownership choice. Select verification that could expose an architectural mistake: an old consumer during rollout, an unavailable dependency, a conflicting concurrent write, or a capability that cannot be released independently as promised. A compile check alone cannot establish these system properties.
