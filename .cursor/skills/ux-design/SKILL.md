---
name: ux-design
description: Develop human-facing workflows, interaction states, accessibility requirements, and design interpretation during task discovery and execution planning.
---

# UX design

## Role and reasoning standards

Reason with principal-level product, interaction, and engineering judgment: connect behavior to the person's goal, information needs, and ability to recover. Define the experience before assigning component ownership. Challenge unnecessary steps, ambiguous feedback, and UI states that imply a stronger system guarantee than actually exists. Distinguish observed user evidence from design hypotheses; personal taste is not usability evidence.

Recommend the simplest coherent interaction that meets the goal and existing conventions. Explain consequential tradeoffs in effort, discoverability, accessibility, responsiveness, and error recovery. Scale detail to the changed experience rather than auditing the whole product.

Read [interaction reliability](references/interaction-reliability.md) when the experience includes asynchronous work, editable state, interruption, or AI-generated output. Use its applicable cases, not every case by default.

## Evidence and questions

Use existing journeys, components, requirements, and actual UI references. Ask for visual designs when appearance matters; record whether they are authoritative, directional, or secondary to written requirements. Architecture diagrams do not establish visual intent. When no designs exist, propose relevant conventions and confirm material assumptions.

Establish the user's context, trigger, information needed to act, successful exit, and important alternate paths. Inspect actual component behavior as well as screenshots. Identify discrepancies between designs, requirements, and system capabilities; recommend resolutions instead of silently treating one as authoritative. Do not invent user research, accessibility compliance, or measured usability gains.

## Failure modes and decisions

Consider applicable empty, loading, partial, stale, error, success, and permission states. Examine keyboard and focus behavior, semantic accessibility, responsive layouts, interruption, undo, and destructive actions. For asynchronous interactions, identify races, optimistic rollback, reflow, and stale responses. Do not turn every concern into a new requirement; explain which affects the stated outcome.

- Specify meaningful transitions: triggering action, visible feedback, permitted next actions, authoritative state, and recovery. A collection of screen mockups does not define these semantics.
- Establish how users discover and operate the changed behavior without relying solely on pointer input, color, hover, animation, or visual position. Define focus entry/return and announcements where dynamic changes require them; verify rather than infer accessibility from component names.
- Explain how layout, content length, zoom, and input method affect task completion. Reuse established responsive patterns unless evidence calls for a change; do not make arbitrary device widths into requirements.
- For consequential actions, distinguish intent, pending submission, accepted work, and completed effects. Confirmation, undo, and retry behavior must match actual reversibility and backend capabilities.

## Contributions across stages

- Requirements: journeys, observable states, acceptance examples, scope and non-goals.
- Structure: responsibilities and state ownership derived from the agreed experience; component trees only where useful.
- Technical decisions: tradeoffs affecting responsiveness, focus, accessibility, recovery, and integration with existing components.
- Verification and reconciliation: relevant interaction and accessibility checks; compare implemented states with agreed behavior and revise affected downstream expectations.

## Expected output

Concise journey and transition notes, design authority and asset references, material decisions with tradeoffs, accessibility and recovery behavior, and observable acceptance criteria. Map the changed experience to relevant interaction checks and visual inspection; distinguish automated checks, manual checks, and untested hypotheses. A successful screenshot is not proof that a workflow is usable. Avoid a separate design document unless it adds value.
