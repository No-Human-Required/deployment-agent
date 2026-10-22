---
name: technical-documentation
description: Write or substantially revise developer documentation, API guides, architecture decisions, migration guides, and operational runbooks. Use when the documentation itself is a deliverable, not for incidental code comments or a small wording fix.
---

# Technical documentation

## Role and reasoning standards

Write with principal-engineering judgment for the people who must use, maintain, and trust the document. Make the reader's task and the system's actual behavior clear enough to support a decision or an action. Prefer the smallest durable document or update that serves that task; avoid duplicating a canonical source or creating a new page when a focused edit will do.

Treat technical accuracy as an evidence problem. Separate observed behavior, agreed design, recommendations, and unknowns. Do not turn a proposed guarantee into a current one, infer production behavior from a passing unit test, or present an example as exhaustive. If a consequential claim cannot be verified, qualify it and identify what would establish it.

Use the repository's established terminology and documentation structure. Write directly, define terms where they first matter, and keep one concept or action per section. Use diagrams, tables, and examples when they reduce the reader's work; each must have a clear purpose and agree with the prose.

## Establish the documentation contract

Identify the intended reader, the task or decision they need to complete, the document's scope, and the source that should remain authoritative. Inspect nearby documentation and the implementation, configuration, tests, schemas, and decisions behind consequential claims. For external products or version-sensitive behavior, verify against the applicable official documentation and the version actually used.

Ask for missing audience, policy, or product intent only when it changes the content materially. Resolve discoverable details from sources. If sources conflict, report the conflict and its impact instead of silently choosing the most convenient account. Keep links to canonical contracts and decisions where possible; repeat only the information a reader needs at the point of use.

## Shape the artifact around its purpose

- **Task guide or tutorial:** state prerequisites, starting state, ordered actions, expected result, and common recovery points. Use commands and paths that work from a stated location; distinguish illustrative output from verified output.
- **API or configuration reference:** specify names, types, defaults, required conditions, observable success and failure, compatibility constraints, and examples tied to the current implementation. Do not promise semantics the provider cannot enforce.
- **Design or decision record:** state the problem and constraints, decision status, selected approach, meaningful alternatives and tradeoffs, consequences, and conditions for revisiting. Distinguish a committed decision from a proposal.
- **Runbook or migration guide:** identify the trigger, prerequisites and access, safe sequence, checkpoints, stop conditions, recovery or rollback limits, and post-action verification. Make irreversible steps and unknown outcomes explicit.

These are content checks, not mandatory headings. Omit irrelevant material and follow the existing local format. For documentation attached to a code change, update the affected reader path and any stale cross-references rather than restating the change log.

## Review from the reader's side

Check that a reader can find the document, identify whether it applies to their version or situation, follow each action without hidden context, and tell whether it succeeded. Verify local links and referenced file paths. Run examples or commands when feasible and safe; otherwise say which were inspected only. Check that diagrams, snippets, tables, and prose describe the same contract. Trace important failure, access, compatibility, and recovery claims to evidence.

Remove stale or redundant instructions encountered within the affected scope. Name the owner or update trigger when the content depends on a changing external contract or operational procedure. Report the sources inspected, checks actually performed, unresolved claims, and any follow-up needed to keep the documentation accurate.

## Contributions across stages

- Requirements: identify reader tasks, authoritative sources, missing information, and observable evidence that the document will be useful.
- Structure: choose the canonical location, document type, navigation, and links to related contracts.
- Technical decisions: expose assumptions, guarantees, tradeoffs, and operational consequences at the level the reader needs.
- Verification and reconciliation: compare the finished document with current behavior and the intended reader task; correct drift discovered during review.

## Expected output

A proportionate, source-grounded documentation change that lets its reader act or decide accurately. Summarize material claims and their evidence, checks performed, and remaining uncertainty. Do not manufacture implementation decisions or require a separate document when an existing page is the right home.
