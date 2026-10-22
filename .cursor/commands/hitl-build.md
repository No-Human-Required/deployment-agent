---
name: hitl-build
description: Build one eligible HITL prompt in this conversation, or coordinate the agreed list in auto mode.
docs:
  - docs/agent/workflows/command-interface.md
  - docs/agent/workflows/prompt-plan-contract.md
  - docs/agent/workflows/auto-run.md
  - docs/agent/repository-quality-contract.md
  - docs/agent/workflows/workflow-learning.md
---

# HITL build

## Interface

**Purpose:** Build one eligible prompt in manual mode, or coordinate the agreed build/next loop in auto mode.

**Usage:** `/hitl-build [--auto] [<prompt-folder>]` or `/hitl-build --help`

### Input

| Name | Accepted forms | If omitted |
| --- | --- | --- |
| `<prompt-folder>` | Path or Cursor reference to `.hitl/prompts/<task>/` or its `prompt-plan.md` | Use the plan already unambiguous in this conversation. Otherwise offer actual task folders through `AskQuestion`, or ask for a path in chat when none can be listed. |

The input identifies a task plan, not an individual numbered prompt. Manual mode offers the eligible prompt picker after the plan is resolved.

### Options

| Option | Value | Effect | Persistence |
| --- | --- | --- | --- |
| `--auto` | None | Enable and run the agreed build/next loop. | Saved as `mode: auto` in this task's plan. |
| `--help` | None | Show this interface and stop before task work. | None. |

Without `--auto`, use the plan's saved mode; an older plan with no Run Mode is manual. Options may appear before or after the folder. Follow `docs/agent/workflows/command-interface.md` for parsing, help, and standard errors.

### Examples

- `/hitl-build .hitl/prompts/email-package/`
- `/hitl-build --auto .hitl/prompts/email-package/`
- `/hitl-build .hitl/prompts/email-package/prompt-plan.md --auto`
- `/hitl-build --help`

### Command-specific errors

| Situation | Response |
| --- | --- |
| Folder or plan file does not exist, or the folder lacks `prompt-plan.md` | Explain the issue and offer actual valid folders through `AskQuestion`; if none can be listed, ask for a path in chat or suggest `/hitl-define`. Make no changes before resolution. |
| Plan has no agreed prompt list in auto mode | Return to the unresolved definition decision; do not save auto mode or start the loop. |
| No eligible prompt in manual mode | Report whether work is unwritten, claimed, completed, or blocked; do not invent work. |

Do not open Plan mode in either execution mode. Do not rewrite the chosen prompt into a new plan.

## Preflight

Stop with clear guidance when a check fails. Recover missing input with actual choices or a direct chat question; do not invent work.

1. **Invocation** — Apply the Interface and `docs/agent/workflows/command-interface.md` first. Return immediately for `--help` or an invalid invocation.
2. **Plan present?** — Resolve the folder from the input or unambiguous conversation context. A `prompt-plan.md` reference resolves to its parent folder. If a folder is needed, use `AskQuestion` with up to the 10 most relevant actual folders under `.hitl/prompts/` that contain `prompt-plan.md`; allow the developer to enter another path or reference. If none exist, ask for the path in chat or suggest `/hitl-define`. Validate the answer before continuing. If the given path is invalid, use the command-specific error response.
3. **Run Mode** — Read the saved mode and determine the effective mode. A supplied `--auto` requests auto mode; a later invocation without the flag follows the saved mode. If auto mode is requested, check that the prompt list is agreed before saving the mode.
4. **Contracts** — Read the shared plan, the numbered prompt files beside it, `docs/agent/repository-quality-contract.md`, and `docs/agent/workflows/prompt-plan-contract.md` for Progress contract, Dependency map and parallel work, and the implement-as-written rule. After validating an auto request, save `mode: auto` for this plan.
5. **Repo evidence** — Inspect current repository evidence. Do not trust statuses alone.
6. **Manual eligibility** — In manual mode, a prompt is **eligible** when all of the following hold:
   - Its numbered file exists beside `prompt-plan.md`
   - Dependencies are `finalized` or `skipped`, and required outcomes actually exist (a skip does not supply a missing artifact)
   - No unresolved conflict or overlapping in-flight work blocks it
   - Its status is not `building`, `planning`, `planned`, `implementing`, `implemented`, `finalized`, `blocked`, or `skipped`

In manual mode, treat a present file whose progress status is still `not written` or `handed off` as written. Prompts that are already `building` in this or another conversation are in process and must not be offered.

If none are eligible in manual mode, report why (nothing written, all claimed or done, or a blocker) and stop. Auto mode follows `docs/agent/workflows/auto-run.md`, which may first reconcile implemented work or write the next ready prompt.

## Plan

State the intended action before executing.

- **Manual** (default or saved `mode: manual`): build one unblocked, not-yet-built prompt in this conversation. Do not implement more than one prompt or launch subagents for other slices.
- **Auto** (saved `mode: auto` or `--auto`): read `docs/agent/workflows/auto-run.md` and act as the coordinator for the agreed list.

In auto mode, require an agreed prompt list; do not infer approval from a draft. Do not show the manual prompt picker or ask routine write, build, or finalization questions.

In manual mode, do not start implementation before the user answers the prompt picker.

## Commands

### Auto mode

When auto mode is active, act as the coordinator. Reconcile any already implemented work, write ready downstream prompts as needed, claim one eligible slice at a time, delegate it to `hitl-slice-builder` when available, verify the result, and repeat until the agreed plan is complete or a stop condition occurs. This is the only branch that may run multiple slices. Give a brief update after every completed prompt. Leave `/hitl-review` and `/hitl-submit` to separate manual invocations.

### Ask, then claim immediately

In manual mode, show a one-line goal and output summary for the eligible prompts being offered and point to each **Developer Review** card; keep the full files available. Use the AskQuestion tool to ask which eligible prompt to build. Order eligible prompts by dependency readiness, then numeric filename. Show at most 10 choices total, reserving slots for **Cancel** and an **Other eligible prompt** text entry when needed. Each prompt choice uses its filename stem as id and its filename and title as label. Do not ask this in chat. Validate an unlisted prompt against the same eligibility rules. Briefly restate the selected card before claiming it.

If the user cancels, stop without editing the plan.

After a prompt is chosen, **claim it before any other work**:

1. Reread `prompt-plan.md` immediately before saving.
2. If the chosen prompt is no longer eligible (another conversation claimed it, or a dependency changed), do not overwrite that entry. Tell the user and return to AskQuestion with the remaining eligible set.
3. Update only that prompt's progress entry: set `status` to `building`, record this conversation / checkout, and preserve every other entry.
4. Save the plan.

A parallel `/hitl-build` must not list a prompt once it is `building`. Do not implement until that save succeeds.

### Execute the claimed prompt

Read the claimed prompt file and only the specialist skills it names. Stay inside that slice. Do not revise or execute other prompts. Surface stale instructions or missing prerequisites, mark the slice `blocked` with a reason, and stop.

Implement the prompt as written. Apply local conventions and the quality contract.

## Verification

Run the prompt's verification and record unrun checks. Capture only definition-rooted learning candidates per `docs/agent/workflows/workflow-learning.md` in this prompt's progress entry. Record implementation-only corrections in the execution report, not as skill-improvement candidates.

When the deliverable and verification report are ready, reread the plan. Record changed files, verification, decisions, deviations, and implications in this prompt's progress entry.

This prompt is the **last remaining slice** when every other agreed prompt is `finalized` or `skipped`. In that case, set this prompt to `finalized` with `finalization basis: manual last slice`, disclose verification limitations, fold any learning candidates from this entry into the plan's `Learning Candidates` section without classifying them, and record plan completion.

Otherwise set this prompt to `implemented` only. Do not set `finalized` here; the user confirms that through orchestration.

A completed investigation states the decision its evidence supports; it does not authorize dependent implementation.

## Summary

Present a concise result block:

```
## Result
- **Action**: built <prompt> | auto-run | stopped
- **Status**: success | partial | failed | blocked
- **Details**: changed files, verification, progress status, limitations
```

## Next Steps

- **Last remaining slice finalized** — tell the user the plan is complete. Do not send them to `/hitl-next`. If learning candidates remain, mention `/hitl-improve`.
- **Non-final slice implemented** — tell the user to return with `/hitl-next <prompt-folder>`.
- **Blocked** — stop; do not continue to another slice in manual mode.
- **Auto complete** — leave `/hitl-review` and `/hitl-submit` to separate manual invocations.
