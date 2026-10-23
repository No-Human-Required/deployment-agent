# Specialist catalog

All skill paths below are relative to this catalog. Load only relevant bodies. Multiple skills may apply to one task and at more than one workflow stage.

| Skill | Selection signals | Expected contribution |
| --- | --- | --- |
| [UX design](../../ux-design/SKILL.md) | Human-facing behavior, interactions, accessibility, visual interpretation | Journeys, state coverage, interaction boundaries, observable experience criteria |
| [Agent workspace UX](../../agent-workspace-ux/SKILL.md) | Folder-first agent shells, chat threads per workspace, agent progress disclosure, in-chat GenUI/HITL patterns (Cursor-like companions) | Workspace gate, thread scoping, chat vs timeline/inspector, intake timing, global vs project-scoped surfaces |
| [API design](../../api-design/SKILL.md) | A caller/provider contract changes; integrations or asynchronous interfaces | Contract semantics, failures, authorization boundaries, compatibility and contract checks |
| [Analytics instrumentation](../../analytics-instrumentation/SKILL.md) | Behavioral analytics, shared tracking packages, event catalogues, identity or consent transitions, acquisition, or experiment measurement | Interpretable measures, event placement and ownership, privacy boundaries, collection quality, and validation against product decisions |
| [Data modeling](../../data-modeling/SKILL.md) | Persistent structure, invariants, queries, schema evolution or backfills | Model and ownership, integrity constraints, evolution and data verification |
| [Investigation and debugging](../../investigation-debugging/SKILL.md) | Unexplained behavior, uncertain feasibility, regression, evidence needed before a decision | Reproduction or research question, discriminating evidence, bounded findings and next decision |
| [System architecture](../../system-architecture/SKILL.md) | Cross-system ownership, shared capabilities, dependency direction, or consequential topology changes | Justified boundaries, system flows, architecture tradeoffs, and incremental transition decisions |
| [Reliability and operations](../../reliability-operations/SKILL.md) | Availability needs, background processing, distributed dependencies, overload, or recovery requirements | Bounded failure policies, observable objectives, operational ownership, and recovery evidence |
| [Technical documentation](../../technical-documentation/SKILL.md) | Developer documentation, API guides, architecture decisions, migration guides, or runbooks are substantial deliverables | Reader task and canonical location, source-grounded claims, usable structure, and documentation verification |

Security, infrastructure, performance, rollout, and other concerns remain valid even without a dedicated skill. Use general expertise and source evidence; record a specialist gap if it affects confidence. Do not force such tasks into a listed specialty.

Architecture owns system boundaries and their tradeoffs; API and data specialists refine interface and persistence guarantees. Reliability owns runtime failure handling and operational evidence; investigation establishes causes of unexplained behavior. Combine these only when the task crosses those concerns. Infrastructure provisioning, full security reviews, and performance optimization are not automatically added by selecting architecture or reliability.

Analytics instrumentation owns the meaning and validity of behavioral measures in code. Select it for product or acquisition tracking and experiment evidence, including when the implementation also needs API or architecture guidance. Do not select it for error logs, infrastructure metrics, or business events whose only purpose is reliable message delivery.

## Extending the catalog

Add a specialist when evidence demonstrates a distinct reusable need; a single clear failure may justify a narrow addition, but a catalog gap alone does not. Give it a narrow description, reasoning standards, relevant evidence, failure modes, expected outputs, and contributions across workflow stages. Follow the existing specialist structure; avoid copying orchestration and approval rules into each skill. Update this catalog with its actual file link and selection signals.

Definition-rooted additions follow [definition learning](../../../../docs/agent/workflows/workflow-learning.md): draft the complete skill and catalog entry, validate their selection boundaries, and obtain approval before making them active. `/hitl-define` may do this inline when it would help the current task; `/hitl-improve` handles accumulated or deferred candidates.
