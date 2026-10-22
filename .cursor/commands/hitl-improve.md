---
name: hitl-improve
description: Review accumulated HITL definition-quality candidates and apply approved skill improvements.
docs:
  - docs/agent/workflows/command-interface.md
  - docs/agent/workflows/workflow-learning.md
  - docs/agent/workflows/prompt-plan-contract.md
---

# HITL improve

## Interface

**Purpose:** Improve future `/hitl-define` output by reviewing definition-rooted evidence and applying only approved skill or selection changes.

**Usage:** `/hitl-improve [<prompt-folder>]` or `/hitl-improve --help`

### Input

| Name | Accepted forms | If omitted |
| --- | --- | --- |
| `<prompt-folder>` | Path or Cursor reference to `.hitl/prompts/<task>/` or its `prompt-plan.md`. | Scan every task plan under `.hitl/prompts/` for definition-quality candidates. |

### Options

| Option | Value | Effect | Persistence |
| --- | --- | --- | --- |
| `--help` | None | Show this interface and stop before reading candidates or changing guidance. | None. |

Follow `docs/agent/workflows/command-interface.md` for parsing, help, and standard errors.

### Examples

- `/hitl-improve`
- `/hitl-improve .hitl/prompts/email-package/`
- `/hitl-improve --help`

### Command-specific errors

| Situation | Response |
| --- | --- |
| Supplied folder has no `prompt-plan.md` | Offer up to 10 actual valid task folders through `AskQuestion`; if none can be listed, ask for a path in chat. Make no changes before resolution. |
| No pending definition-quality candidates in the chosen scope | Report that the queue is empty and stop. |

Review accumulated or deferred evidence that `/hitl-define` could produce better plans through better skills or skill selection. This is the standalone path for the same improvement procedure available inline in `/hitl-define`. It does not implement task deliverables, write prompt files, or advance `/hitl-next`.

Read `docs/agent/workflows/workflow-learning.md` before classifying or editing. Read `docs/agent/workflows/prompt-plan-contract.md` for the shared-plan location and Learning Candidates section.

## Collect pending candidates

Find `prompt-plan.md` files in the chosen scope. Also read `execution-notes/` and `learning candidates` fields on progress entries for downstream evidence of a definition gap. A folder without a plan is out of scope.

A candidate is **pending** when its status is `captured`, `proposed`, or `approved`, or `deferred` whose revisit condition is met or that the user asks to reopen. Skip `dismissed`, `applied`, and `reverted` unless new evidence is present. Do not invent candidates.

Consolidate duplicates across the chosen scope. Preserve each source reference. Exclude task-only changes and implementation errors without a plausible definition cause. If the original evidence is inaccessible, record that limitation and do not invent a lesson.

If none are pending, say so and stop.

## Confirm the queue

Show a concise inventory grouped by task: id, short issue, status, and source path. Use the AskQuestion tool:

- If more than one task has pending items: show the most relevant task folders, plus **All pending** and **Cancel**, with at most 10 displayed options total. If tasks exceed the cap, allow a text answer for another folder and validate it against the pending set.
- If only one task: **Review pending** and **Cancel**

Do not start classification before they answer. If they cancel, stop without editing standing guidance.

## Review one candidate at a time

Follow `docs/agent/workflows/workflow-learning.md` for classification, proposal, validation, approval, and application.

For each selected candidate:

1. Read the actual current guidance and available evidence.
2. Classify whether the cause is skill selection, existing skill guidance, or a distinct missing skill. Dismiss or defer task-specific, unsupported, or unrelated observations with a reason; do not force a proposal.
3. When a skill change is justified, draft the smallest useful exact edits in the candidate record or `learning-proposals/<id>.md`. For a new skill, draft the complete skill and catalog entry. Validate against the recorded definition gap or failure, another representative case, and a counterexample.
4. Present the exact edits, expected change to `/hitl-define` output, reasons, scope, and validation limitations. Ask whether to apply **this** proposal. Use AskQuestion: **Agree**, **Discuss**, **Skip**. A cancelled or skipped question is not approval. Existing explicit approval of the same concrete proposal counts; do not ask again.
5. Apply only after approval. Re-read target files first; if they changed materially, reconcile and obtain agreement to any changed scope. Apply sequentially. Do not commit, overwrite unrelated edits, or revert automatically. Update the candidate status and references.

Default outcome can be no skill edits. Approval of prior feature work does not approve these changes.

## Finish

After the last selected candidate, summarize classifications, applied edits, deferred/dismissed items, skipped proposals, and what remains unstaged. Point back to any still-pending items. Do not start `/hitl-next` or implement task work.
