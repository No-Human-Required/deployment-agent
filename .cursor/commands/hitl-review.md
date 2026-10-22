---
name: hitl-review
description: Review the staged Git snapshot for principle violations and bugs, then attend findings manually or with --auto-attend.
docs:
  - docs/agent/workflows/command-interface.md
  - docs/agent/workflows/violation-review.md
  - docs/agent/repository-quality-contract.md
---

# HITL review

## Interface

**Purpose:** Review the current staged Git snapshot, then attend violation and bug findings.

**Usage:** `/hitl-review [--auto-attend]` or `/hitl-review --help`

### Input

| Name | Source / accepted forms | If empty or omitted |
| --- | --- | --- |
| Staged files (implicit) | Current Git index, including its staged patch and paths. The command takes no positional argument. | If the index is empty, stop and ask the developer to stage the files they want reviewed. |

### Options

| Option | Value | Effect | Persistence |
| --- | --- | --- | --- |
| `--auto-attend` | None | After the review starts, act on each finding using the agent's own verdict without a routine per-finding approval question. | This invocation only. |
| `--help` | None | Show this interface and stop before inspecting the index or starting a paid review. | None. |

Follow `docs/agent/workflows/command-interface.md` for parsing, help, and standard errors. A path argument is unsupported; do not stage it or substitute it for the index. Review exactly the staged snapshot the developer confirms.

### Examples

- `/hitl-review`
- `/hitl-review --auto-attend`
- `/hitl-review --help`

### Command-specific errors

| Situation | Response |
| --- | --- |
| Git index is empty | Tell the developer to stage the paths to review, then rerun the command; do not start a paid review. |
| Review runner is inconclusive | Report the limitation and follow the existing empty/inconclusive report rules; do not invent findings. |

Review **work the developer has staged**, when they ask — not at commit or push. The Git index is the only input. Do not treat the working-tree diff as the review surface. `--auto-attend` does not inherit from the build/next auto mode and does not run `/hitl-submit`.

## Confirm the index

Read `docs/agent/workflows/violation-review.md`. Check `git diff --cached --name-status`.

If the index is empty, stop. Tell the user to stage the paths they want reviewed, then run `/hitl-review` again.

If the index is non-empty, capture a fingerprint of the staged patch and list the staged paths and statuses. Use the AskQuestion tool: **Review this staged snapshot?** with **Proceed** and **Cancel**. Do not start a paid or CLI review before they answer. If they cancel, stop. After **Proceed**, verify that the staged patch still has the same fingerprint; if it changed, show the new staged paths and statuses and ask again before running the review.

## Violation review, then attend

Run `pnpm review:violations`. The runner writes `.hitl/reviews/violation-review.md` and the snapshot under `.hitl/reviews/run/` (`staged.patch` and staged file contents). That snapshot, not later working-tree edits, is the authority for this pass. The runner loads repo-root `.env` when present and calls OpenRouter; do not inspect `.env` or require the key in the agent process.

If the report is empty or inconclusive, explain that and skip the card queue. Do not invent findings.

Otherwise work the **Findings** queue by following **Attending to findings** in `docs/agent/workflows/violation-review.md` exactly. In manual mode, use the existing chat options Agree / Discuss / Skip / Skip with reason, with principle-card calibration only for skip-with-reason. With `--auto-attend`, report each verdict and act on it under the auto-attend rules without that routine question. Do not rerun `pnpm review:violations` for fixes staged during this run; re-evaluate later findings against the updated index. Rerun only if the user asks or an external index change invalidates the snapshot.

After each authorized **Fix** (an explicit Agree in manual mode, or a Fix verdict under `--auto-attend`), apply the edit and stage only the fix before the next finding. Preserve unrelated staged and unstaged hunks; if the fix cannot be staged without including unrelated work, pause. Do not stage `.hitl/` reports, secrets, or skip-with-reason principle-card edits. Finish that queue (including its summary), then run the bug review. Do not ask whether to run it. In that summary, list the staged fix paths.

## Bug review on the same snapshot

After the violation queue is finished or skipped, run `pnpm review:bugs` immediately. Do not ask.

1. It reads the already captured `.hitl/reviews/run/staged.patch`, materializes a temp tree from the current index, and writes `.hitl/reviews/bug-review.md` plus scratch files under `.hitl/reviews/run/cache/`. Do not invent a second review CLI recipe. Do not recompute `git diff`. The runner loads repo-root `.env` when present; do not inspect that file or require the key in the agent process. Auto-staged violation fixes may make this report `stale`; that expected index change is not a reason to skip attending.
2. If that report is empty or inconclusive, explain and skip the bug-review queue. Do not retry paid calls.

### Attend bug-review comments

Build a second queue from `.hitl/reviews/bug-review.md`: review key issues first, then improve suggestions, in document order. These comments have **no principle card**.

For each item, give one verdict (**Fix** / **No change** / **Needs context**) in chat. In manual mode, ask **“What would you like to do for this comment?”** with **Agree**, **Discuss**, and **Skip** only. With `--auto-attend`, act on the verdict without that routine question: fix a supported issue, record No change with a reason, or pause for the missing context. Do not offer **Skip with reason**. Do not edit `docs/agent/code-conventions/` or any selection/detail file.

Otherwise follow the same mode's authorization and staging rules as the card queue: wait for a decision in manual mode; under `--auto-attend`, the flag authorizes a supported Fix verdict. Stage only the fix before presenting the next item, and re-evaluate later items after that staged edit. Do not stage unrelated work, `.hitl/` reports, or secrets.

After the last bug-review item, summarize both queues separately (violation outcomes vs bug-review outcomes), verification, and the staged fix paths.
