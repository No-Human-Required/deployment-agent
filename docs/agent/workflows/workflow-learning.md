# Definition learning

Improve the quality of `/hitl-define` output by correcting its specialist guidance and skill selection. Evidence may arise during initial framing, later definition, or execution. The proposed improvement must address a definition decision that lacks needed guidance, or a defect such as a missed requirement, weak boundary or API decision, poor decomposition, or unnecessary question that better skill guidance or selection would have prevented. A task plan supplies evidence; it is not the improvement target.

`/hitl-define` may review and apply a skill improvement inline when it can materially help the definition underway. `/hitl-improve` reviews accumulated or deferred candidates separately. Both use the same proposal, validation, and approval procedure below. Neither command improves the model's underlying capabilities.

## Capture evidence without interrupting

Notice meaningful corrections and downstream surprises that point to a definition gap. Record only a plausible reusable lesson, including the expected better definition output. A changed task requirement, implementation mistake, failed experiment, project convention, or personal preference alone is not a skill defect. Correct the current task within its authorization; that does not authorize changing standing skill guidance.

Use the `Learning Candidates` section in `prompt-plan.md`. Executors place possible definition gaps in their own execution entry or `execution-notes/<prompt-stem>.md` when parallel updates require isolation. `/hitl-next` may fold those reports into this task's shared section without classifying them; `/hitl-build` does the same when it finalizes the last remaining slice. `/hitl-improve` may consolidate duplicates across the chosen plans. Store concise paraphrases and evidence references, not full conversations, secrets, or unnecessary personal data. State when source evidence cannot be accessed.

For each candidate, capture:

```md
- L01: <short definition guidance gap>
  - status: captured
  - current task evidence / observed definition output and correction, if any:
  - expected definition output with better guidance:
  - source reference / evidence limitation:
  - suspected skill or selection cause / confidence:
  - potential reusable scope and counterexample:
```

Do not invent candidates to fill the section. If there are none, leave it empty or record “None observed.”

## Decide when to review

During `/hitl-define`, after initial task framing and catalog inspection, check whether missing or misleading guidance would materially weaken a decision needed now. Revisit this when new evidence exposes a gap. If the cause is clear and a reusable skill change could improve the current definition, follow the inline review below before relying on the new guidance. Do not require a speculative skill preflight, propose a skill for every task, or halt useful discovery for an uncertain or minor gap. Continue with existing skills and general expertise when sufficient; record a candidate for `/hitl-improve` if the issue merits later review.

`/hitl-define --skills-first` is the explicit exception to that timing. Before definition, inspect the supplied intention and current catalog, report missing skills or explicitly report none, and invite developer-nominated additions. The developer can request a skill that the agent did not flag. Draft and review any requested additions using the same concrete proposal and approval procedure below. Wait for explicit confirmation that no more skills should be added before starting definition; an empty finding or approval of one proposal does not clear this gate.

`/hitl-build` and `/hitl-next` capture only evidence of a definition-rooted gap. They do not classify, draft, or apply skill changes. Pending candidates do not block task completion or unrelated prompt handoffs. At a natural handoff, mention credible pending candidates briefly; the developer can run `/hitl-improve` when ready. `/hitl-improve` scans task `prompt-plan.md` files by default or one folder when supplied.

## Classify the cause

Read the current task evidence, any definition output produced so far, existing skills, and catalog before deciding:

| Cause | Appropriate response |
| --- | --- |
| Task-specific requirement, changed scope, implementation defect, project convention, or unsupported observation | Correct or record it in task context; dismiss or defer the skill candidate |
| Relevant skill was missed | Consider a narrow change to selection signals or discovery-orchestrator guidance if the current routing was unclear; do not duplicate the skill |
| Existing specialist guidance was missing or misleading | Propose a narrow change to that skill |
| Distinct reusable expertise gap with no suitable skill | Consider a new specialist and catalog entry |
| Unclear cause or weak evidence | Defer pending evidence, or dismiss with a reason |

One clear failure can justify a narrow fix; one anecdote does not justify a universal rule. Prefer improving an existing skill over adding an overlapping specialist. A new specialist needs distinct selection signals, reusable reasoning standards, and realistic use cases. In `--skills-first`, a developer-nominated skill is sufficient reason to prepare a proposal; identify overlap and scope honestly so the developer can decide on the exact change. General expertise remains available while a proposal is pending.

## Prepare a concrete proposal

Draft exact edits only in the inline `/hitl-define` review or `/hitl-improve`. A captured candidate alone never changes active guidance. Put larger proposals in a task-local `learning-proposals/L01.md` and link them from the shared plan. Proposal files are review artifacts, not active skills.

Add these fields during review:

```md
  - classification and evidence:
  - current guidance and selection inspected:
  - proposed target skill/catalog files and exact edits:
  - expected change to definition output and scope exclusions:
  - validation cases and observed results:
  - approval decision and approved scope:
  - applied change reference / restoration information:
  - follow-up observations:
```

Propose the smallest useful change, including deletion or simplification when accumulated rules caused the problem. Explain why that edit addresses the cause. For a new skill, show its complete draft and catalog entry so the developer can review the actual standing guidance that would become active. Do not change command behavior, project policy, or unrelated documentation through this skill-improvement path.

## Validate before activation

Check the proposal against the current definition gap or observed failure, another representative case, and a counterexample where it should not apply. Explain how the change would affect the output of `/hitl-define` in each case. Check for contradictions with existing guidance, overlapping skill selection, unnecessary questions, and unintended scope or permission expansion.

Use safe, bounded local trials when practical. Separate a reasoned walkthrough from actual agent execution; report what was performed and what remains untested. Check changed file references and metadata. Do not manufacture passing evidence or treat the same model's agreement as independent validation.

## Approval, application, and follow-up

Show the exact proposed skill and catalog edits, reasons, expected definition behavior, scope, and validation limitations. Ask whether to apply **this** proposal, allowing **Agree**, **Discuss**, or **Skip**. During `/hitl-define`, ask directly in chat as part of the definition conversation; do not use `AskQuestion` or `AskQuestions`. During standalone `/hitl-improve`, use `AskQuestion` when available, or ask in chat otherwise. A skip leaves the candidate proposed but unapplied for later review unless the developer explicitly defers or rejects it. Human approval of the concrete change is required before it becomes active, including during `/hitl-define --auto`. Approval of feature work, acknowledgement of a correction, or agreement to a prompt list does not approve a standing skill change. Existing explicit approval of the same concrete proposal counts; do not ask again.

After approval, re-read target files. If they changed materially, reconcile the proposal and obtain agreement to any changed scope before applying. Apply approved changes sequentially. Record the approval and applied delta. Use an existing commit reference when available; otherwise retain the precise patch and prior affected text in the proposal so a later reversal can be reviewed. Do not commit, overwrite unrelated edits, or revert automatically as part of this process.

For an inline change, refresh skill selection and read the approved guidance before continuing the affected definition decisions. If the developer defers or declines, do not treat the draft as active guidance; continue with current skills and general expertise where feasible, and retain any blocking uncertainty in the plan. `/hitl-improve` applies the same procedure without resuming task deliverables.

Use statuses `captured`, `deferred`, `dismissed`, `proposed`, `approved`, `applied`, and `reverted`. Record reasons for deferral or dismissal and conditions for revisiting. Approval without successful application remains `approved`. An applied change is not automatically a proven improvement. On later relevant definitions, note whether it reduced the original omission or rework and whether it added friction. Revisit or propose reversal when evidence warrants it; do not claim cross-conversation memory or monitoring that is not present.
