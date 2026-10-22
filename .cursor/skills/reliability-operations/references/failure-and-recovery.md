# Failure and recovery

Use this guidance for dependency failures, overload, interrupted jobs, and recovery-sensitive data.

## Budgets and containment

Trace a critical operation end to end. Account for nested timeouts, retries already supplied by SDKs or workers, and work that continues after cancellation. Establish which failures are transient, which retries are safe, and where attempts stop. Consider concurrent retry amplification and recovery load, not just one successful retry.

Define bounded queues and concurrency according to workload and downstream capacity. For overload, identify whether work is rejected, delayed, deprioritized, or shed, and how callers distinguish those outcomes. Evaluate fairness and shared-resource contention where tenant isolation matters. An unbounded queue can convert overload into memory exhaustion or unusable delay.

Specify what a fallback preserves and sacrifices: freshness, completeness, latency, or functionality. Do not return stale or partial results as authoritative unless the contract permits it. Redundancy must account for shared failure domains and actual failover behavior rather than counting replicas alone.

## Background work and shutdown

Establish when accepted work is durable, how ownership transfers between workers, and what happens if a process stops before or after a side effect. Coordinate acknowledgment, leases, retries, and deduplication with actual data and interface guarantees. A retried job can repeat an external effect even if local state is transactional.

Define applicable drain, readiness, shutdown, and restart behavior. Determine how poison work is isolated and who can inspect or replay it. Preserve diagnostic context without retaining sensitive payloads unnecessarily. Recovery must not silently reorder or discard work that the business contract requires.

## Restoration and validation

Separate restart, failover, rollback, restore, and forward repair. Establish prerequisites, authority, data-loss tolerance, reconciliation needs, and conditions for stopping a recovery attempt. Restore service health and confirm business integrity; a running process does not prove complete recovery.

Select scoped local or authorized non-production rehearsals for relevant failure windows: dependency timeout, worker interruption, capacity exhaustion, lost response, or restore into a compatible environment. Record environment differences and untested cases. Production fault injection, load generation, or destructive recovery requires explicit authorization; a design request alone does not grant it.
