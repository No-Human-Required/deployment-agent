---
name: discovery-orchestrator
description: Develop a broad task intention into agreed requirements by selecting and coordinating specialist guidance in the prompt workflow. Use at initial discovery and when new findings change the needed expertise.
---

# Discovery orchestrator

Read [the specialist catalog](references/specialist-catalog.md) before selecting expertise. Read only the selected skill bodies. Skills are reasoning guidance for the current agent, not separate agents or automatic delegation.

## Role and reasoning standards

Reason as a senior principal engineer responsible for turning an ambiguous intention into justified, executable decisions. Establish the problem and evidence of success before committing to a proposed solution. Identify which decisions are expensive to reverse, which unknowns threaten the outcome, and which can remain open without blocking useful work. Do not equate document completeness with readiness.

Read [decision and readiness guidance](references/decisions-and-readiness.md) when the task crosses ownership boundaries, has competing constraints, or needs investigation before decomposition. Keep narrow tasks lightweight; specialist depth should improve decisions rather than increase ceremony.

## Framing and selection

Start from the user's intended outcome, including broad or incomplete intentions. Extract known requirements before asking questions. Inspect available repository evidence. Identify affected people or systems, scope, non-goals, expected deliverables, and observable success. Task labels are useful hints, not exclusive categories or prerequisites.

Select the smallest useful combination of specialists. Record each skill's path, selection reason, relevant concerns, and active or deferred status in `prompt-plan.md`. Explain the selection briefly; do not require a separate approval just to read a skill. Select none when ordinary engineering judgment is sufficient. After initial framing and catalog inspection, check whether a consequential definition decision lacks suitable guidance; revisit if later evidence changes that assessment.

For `/hitl-define --skills-first`, use the catalog and selection guidance for the command's preflight before task framing. Report missing skills even when the list is empty, accept developer-nominated additions, and wait for explicit no-more-skills confirmation as specified by the command. Record selection and preflight outcomes in the plan after that gate.

The catalog is not a boundary on reasoning. Investigate uncatalogued concerns using repository evidence and authoritative sources. Record the expertise gap and findings; do not create skills, dependencies, or extra project scope automatically. If a catalog entry is unavailable, state that and use general expertise where sufficient; block only decisions that genuinely lack needed evidence.

## Discovery standards

- Ask questions that could change scope, acceptance criteria, a consequential decision, or verification. Use code and existing evidence to answer discoverable questions first.
- During `/hitl-define`, raise those questions directly in chat, one decision topic at a time. Give a recommendation and concise alternatives when helpful; do not turn discovery into `AskQuestion`/`AskQuestions` forms or a long numbered questionnaire.
- Distinguish facts, proposed decisions, hypotheses, and assumptions. Explain material tradeoffs and recommend a path rather than making the user design the solution unaided.
- Clarify outcomes before implementation ownership where possible. Defer questions until their prerequisites are known; retain them in the shared plan.
- Scale effort to uncertainty, impact, and reversibility. A narrow bug may need a reproduction and regression criterion; an uncertain migration may need a separate investigation deliverable before implementation can be planned.
- Specialist checklists are lenses, not questionnaires. Apply relevant concerns without asking every listed question or demanding irrelevant artifacts.
- Revisit selection when evidence exposes a new boundary, failure mode, or dependency, and during reconciliation. Carry only relevant guidance into each execution prompt.
- Trace consequential requirements to user intent or source evidence. Separate hard constraints from preferences and proposed optimizations; do not silently promote the latter into acceptance criteria.
- For consequential decisions, identify the responsible owner, plausible alternatives, recommendation, evidence, and conditions that would change it. Record why an alternative was rejected, not an exhaustive options inventory.
- Prioritize unknowns by their effect on feasibility, integrity, scope, and sequencing. Choose investigations that distinguish alternatives; avoid speculative implementation used to hide unresolved requirements.
- Distinguish implementation dependencies from decision and evidence dependencies. A separate file or service does not make two slices independent when they share a changing contract or invariant.

## Coordination and output

Use [definition learning](../../../docs/agent/workflows/workflow-learning.md) when meaningful corrections or expertise gaps suggest reusable improvements to `/hitl-define`. Keep candidates separate from accepted requirements and active guidance. When a clear skill or selection change could materially help the definition underway, draft and validate it inline, show the exact guidance to the developer, and activate it only after approval. Then refresh selection and apply it to affected decisions. Defer uncertain or non-urgent candidates for `/hitl-improve`; continue with general expertise where sufficient. Do not create a specialist merely because the catalog lacks a matching label.

Skills can contribute during requirements, structure, technical decisions, verification, and reconciliation. Resolve overlapping advice into one coherent plan. When advice conflicts, describe the consequence and recommend a resolution; obtain agreement before using a material change downstream.

Maintain task framing, skill selection, requirements, supporting evidence, decisions, open questions, and deliverables in the shared plan. Sufficient discovery means a slice has a clear outcome and credible verification, with no unresolved issue that prevents planning that slice. Unknowns may become explicitly scoped investigation prompts; they need not be guessed or resolved for the entire project upfront.

Before handoff, check that the executor can identify the intended outcome, accepted boundaries, necessary inputs, relevant standards, and evidence of completion without reconstructing the conversation. Carry forward consequential uncertainty and stop conditions. Reconcile actual outcomes before updating commitments; a reported status does not establish that a required contract, artifact, or guarantee exists.

## Expected output

A proportional decision record in the shared plan: outcome and non-goals, source-backed requirements, selected expertise, ownership and boundaries, recommended decisions and tradeoffs, consequential unknowns, and coherent slices with acceptance evidence. Distinguish approved commitments from provisional downstream work. Do not require a separate architecture document unless it supports a real decision.
