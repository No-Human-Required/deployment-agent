# Schema evolution and backfills

Use this guidance for existing data and independently deployed readers or writers. Choose stages based on actual compatibility and operational constraints, not a prescribed migration pattern.

## Preconditions and coexistence

Inspect historical data, all affected readers/writers, deployment order, and applicable database behavior. Identify incompatible records and decide whether to reject, quarantine, repair, or explicitly preserve them; do not invent domain values to make a constraint pass.

Establish which old and new versions must coexist. Determine whether expansion, backfill, validation, and retirement need separate steps. For dual writes or read fallback, specify the source of truth, divergence detection, and when compatibility paths can be removed. A new column or schema version alone does not establish compatibility.

## Execution and interruption

Define the transformation and invariants before execution mechanics. For large or interruptible work, establish stable batching, checkpoint meaning, retry behavior, and interaction with concurrent writes. Check whether restarting, replaying a batch, or modifying a record during backfill could corrupt or overwrite newer data.

Set operational bounds and stop conditions from actual constraints: lock duration, write amplification, replica lag, storage, and acceptable throughput where relevant. Distinguish measured rehearsal behavior from production estimates. Do not label a migration online or zero-downtime without supporting engine behavior and rollout evidence.

## Validation and recovery

Verify relevant invariants and semantic correspondence, not just row counts or script completion. Select representative historic edge cases and interrupted executions. Where full checks are impractical, explain sampling limitations and residual uncertainty.

Separate stopping a job, rolling back application code, reversing a transformation, and restoring data. State when each remains possible and what would be lost. A backup claim needs an applicable restoration path; irreversible transformations may require forward repair. Identify the point after which old consumers cannot safely return.

Produce a reviewable migration plan or artifact within scope. Planning and local rehearsal do not authorize running it against live data.
