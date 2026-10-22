---
name: hitl-next
description: Reconcile HITL prompt outcomes and write the next ready prompts, or continue the agreed auto loop.
docs:
  - docs/agent/workflows/command-interface.md
  - docs/agent/workflows/prompt-plan-contract.md
  - docs/agent/workflows/auto-run.md
  - docs/agent/repository-quality-contract.md
  - docs/agent/workflows/workflow-learning.md
---

# HITL next

## Interface

**Purpose:** Reconcile execution outcomes and prepare the next ready prompts. Auto mode continues the agreed build/next loop.

**Usage:** `/hitl-next [--auto] [<prompt-folder>]` or `/hitl-next --help`

### Input

| Name | Accepted forms | If omitted |
| --- | --- | --- |
| `<prompt-folder>` | Path or Cursor reference to `.hitl/prompts/<task>/` or its `prompt-plan.md`. | Use the plan already unambiguous in this conversation; otherwise offer up to 10 actual task folders through `AskQuestion`, or ask for a path in chat when none can be listed. |

### Options

| Option | Value | Effect | Persistence |
| --- | --- | --- | --- |
| `--auto` | None | Enable and run the agreed build/next loop. | Saved as `mode: auto` in this task's plan. |
| `--help` | None | Show this interface and stop before task work. | None. |

Without `--auto`, use the plan's saved mode; an older plan with no Run Mode is manual. Options may appear before or after the folder. Follow `docs/agent/workflows/command-interface.md` for parsing, missing input, help, and standard errors.

### Examples

- `/hitl-next .hitl/prompts/email-package/`
- `/hitl-next --auto .hitl/prompts/email-package/`
- `/hitl-next .hitl/prompts/email-package/prompt-plan.md --auto`
- `/hitl-next --help`

### Command-specific errors

| Situation | Response |
| --- | --- |
| Folder or plan file is missing or invalid | Offer actual valid task folders through `AskQuestion`; if none can be listed, ask for a path in chat or suggest `/hitl-define`. Make no changes before resolution. |
| Plan has no agreed prompt list in auto mode | Return to the unresolved definition decision; do not save auto mode or start the loop. |
| No work is ready | Report the specific blocker, in-flight work, or completed plan; do not invent a prompt. |

Resolve the folder before reading its plan. Read the saved **Run Mode**; a supplied `--auto` enables it for this plan only after validating the agreed list. In manual mode, this command reconciles outcomes and writes prompts without implementing deliverables. In auto mode, it coordinates the full build/next loop.

Read the shared plan, `docs/agent/repository-quality-contract.md`, and `docs/agent/workflows/prompt-plan-contract.md` for Shared memory, Approval and uncertainty, Dependency map and parallel work, Progress contract, and Prompt-file contract.

## Auto mode

When auto mode is active, read and follow `docs/agent/workflows/auto-run.md`. Require an agreed prompt list. Reconcile completed work first, then write ready prompts, claim and delegate one slice at a time, verify it, and continue. Do not stop after writing prompts or ask the routine manual prompt-writing/finalization questions. Pause for the documented stop conditions and give a brief update after each completed prompt. `/hitl-review` and `/hitl-submit` remain separate manual commands.

## Reconcile first

Inspect actual repository and artifact state alongside execution reports. Review statuses, changed files/artifacts, verification, decisions, deviations, and implications. Do not trust statuses alone or assume work in another checkout has landed. Ask a focused question when ambiguity affects readiness.

Reconcile parallel outcomes together: detect overlapping ownership, incompatible contracts, duplicated work, merge conflicts, and missing evidence. Preserve each execution entry; do not overwrite another executor's report. Reconcile investigation findings and non-code artifacts as carefully as implementation code.

Apply `.cursor/skills/discovery-orchestrator/SKILL.md` to reassess expertise when outcomes expose new concerns. Load only relevant specialist guidance. Update skill selection, requirements, structure, decisions, execution progress, reconciliation notes, dependency map, agreed list, and overall progress as needed. Surface material changes for agreement before using them downstream.

## Identify ready work

When incorporating executor reports, fold any definition-rooted learning candidates into this task's `Learning Candidates` section without classifying or applying them. Capture new observations noticed during reconciliation the same way, per `docs/agent/workflows/workflow-learning.md`; record implementation-only corrections in reconciliation notes instead. Pending improvements do not block prompt handoffs or task completion. Do not inspect standing guidance, draft proposals, or apply skill changes here.

A prompt is ready when dependencies are finalized or explicitly skipped, required outcomes exist or have been removed through an agreed scope change, and no unresolved conflict or in-flight overlap blocks it. More than one prompt may be ready if genuinely parallel-safe.

New prompts normally have `not written` status. Previously drafted prompts may need revision when dependency outcomes changed; explicitly identify the revision and coordinate with any executor before changing a handed-off or `building` prompt. Do not revise in-flight instructions silently or regenerate finalized work. A blocked prompt can become ready after its blocking condition is verified resolved.

Do not draft blocked downstream work unless the user explicitly requests a labeled provisional draft. If nothing is ready, report the specific blocker or in-flight work; if all agreed prompts are finalized or skipped, report completion instead of asking to write more. In manual mode, `/hitl-build` already finalizes the last remaining slice, so a follow-up `/hitl-next` is not required after that build.

## Confirm and write

Show a concise reconciliation summary, changed statuses/decisions, next files to write or revise, parallel eligibility, credible pending definition-quality candidates, and consequential risks or assumptions. For files not yet written, show the planned developer view; for existing files, show or link their short **Developer Review** cards. If candidates remain (`captured`, `deferred`, `proposed`, or `approved`), mention `/hitl-improve` (optionally with this folder) for later review. In manual mode ask: “Do you want me to write or revise these next prompt files?” Proceed after clear agreement, or existing explicit authorization covering this action and scope. In auto mode, write files within the agreed list without this routine question; material changes still require agreement.

Use the Prompt-file contract, relevant specialist paths and standards, current accepted outcomes, quality expectations, and local assets. Include a short **Developer Review** card in each prompt. Each handoff names the selected prompt and shared plan as required context. In manual mode, direct execution through `/hitl-build` in a dedicated conversation; in auto mode, hand the claimed slice to the coordinator's builder subagent.

Update drafted prompts, execution handoffs, dependency map, and progress. Set newly handed-off prompts to `handed off`. Preserve historical execution evidence when revising. In manual mode, tell the user which files are ready and which can execute in parallel. In auto mode, continue the loop instead of ending at this handoff.
