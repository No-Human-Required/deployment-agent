---
name: data-modeling
description: Design persistent data structures, ownership, integrity constraints, access patterns, and safe schema evolution or backfills.
---

# Data modeling

## Role and reasoning standards

Reason from domain meaning, lifecycle, invariants, and access patterns before choosing tables or storage technology. Separate the source of truth from derived data. Make consistency and evolution costs explicit; do not assume a schema change is safe just because fresh data passes validation.

Apply senior principal engineering judgment to every consequential invariant: identify its authoritative owner, enforcement boundary, concurrent failure cases, and verification evidence. Recommend the smallest model that serves actual requirements; explain normalization, duplication, and consistency tradeoffs rather than prescribing a universal schema style.

Read [schema evolution and backfills](references/schema-evolution.md) when changing existing persisted data, constraints, or writer/reader versions. Do not impose a migration program on a new isolated model without existing data or consumers.

## Evidence and questions

Inspect current schemas, migrations, writers/readers, representative sanitized data, and database versions. Establish identifiers, cardinality, optional versus unknown values, units/time semantics, retention, and ownership where relevant. Ask for volume and availability constraints when they affect the design, not as a routine questionnaire.

Trace the full write and read paths, including jobs, imports, caches, and external writers relevant to the invariant. Check observed data quality and distribution before assuming uniqueness, completeness, or uniform workloads. Distinguish measured cardinality and query behavior from estimates. Verify engine/version-specific behavior against applicable documentation before promising locking, transaction, or online-migration guarantees.

## Failure modes and decisions

Consider duplicates, orphan records, concurrent writes, transaction boundaries, tenancy isolation, indexing against actual queries, and historical invalid data. For evolution, distinguish new installations from existing data; consider expand/backfill/validate/contract phases, resumability, mixed-version compatibility, and interruption. Specify recovery options honestly: irreversible data loss cannot be solved by a nominal rollback script. Planning a production operation does not authorize executing it.

- **Domain semantics:** distinguish identity from mutable attributes, absent from unknown values, event time from recording time, and current state from historical facts where relevant. Make cardinality and lifecycle rules explicit before choosing constraints.
- **Integrity and consistency:** identify which guarantees storage enforces and which depend on coordinated writers. Challenge read-then-write checks under concurrency. Define what happens when cross-boundary invariants cannot be committed atomically, without claiming a local transaction covers external effects.
- **Ownership and isolation:** establish who may read or modify records and how tenant-scoped identities and relationships remain isolated. Do not rely on an assumed application filter as evidence of an enforced invariant.
- **Access and scale:** derive indexes and denormalization from actual query predicates, ordering, selectivity, write cost, and growth. Account for hot keys and skew where material. A proposed index is not a proven performance improvement.
- **Lifecycle:** distinguish canonical data, rebuildable projections, caches, and historical records. Define relevant retention, deletion propagation, and rebuild behavior; do not silently introduce indefinite retention or assume a projection is authoritative.

## Contributions across stages

- Requirements: business invariants, data lifecycle, and acceptable consistency or downtime.
- Structure: entities, ownership, relationships, sources of truth, and read/write paths.
- Technical decisions: constraints, transactions, query/index tradeoffs, migration sequencing and recovery.
- Verification and reconciliation: integrity checks and representative migration rehearsals; compare actual schema/data outcomes and update dependent contracts.

## Expected output

A model or schema delta with domain meaning, authoritative owners, important invariants and enforcement points, access-pattern tradeoffs, and measurable integrity criteria. Include evidence-backed evolution and recovery steps when needed, with preconditions and unresolved risks. Distinguish verified properties from proposed checks and estimates. Avoid unnecessary storage redesign, speculative entities, and separate documentation for trivial changes.
