---
name: hitl-submit
description: Propose and, after confirmation, commit the current Git index without pushing.
docs:
  - docs/agent/workflows/command-interface.md
  - docs/agent/repository-quality-contract.md
---

# HITL submit

## Interface

**Purpose:** Propose a commit for the current Git index and create it only after confirmation.

**Usage:** `/hitl-submit [<commit-instructions>]` or `/hitl-submit --help`

### Input

| Name | Source / accepted forms | If empty or omitted |
| --- | --- | --- |
| Staged files (implicit) | Current Git index, including its staged patch and paths. | If the index is empty, stop and ask the developer to stage the files they want committed. |
| `<commit-instructions>` (optional positional) | Free text for the commit message or an explicit amend request. | Draft a conventional commit message from the staged diff and recent log. |

The staged index is the commit's file input; commit instructions only affect the proposal. A path in those instructions does not stage it. An amend request still follows the safety and confirmation rules below.

### Options

| Option | Value | Effect | Persistence |
| --- | --- | --- | --- |
| `--help` | None | Show this interface and stop before inspecting or changing the index. | None. |

Follow `docs/agent/workflows/command-interface.md` for parsing, help, and standard errors. Use `--` before literal commit instructions that begin with `--`.

### Examples

- `/hitl-submit`
- `/hitl-submit Use a docs: subject mentioning the HITL guide`
- `/hitl-submit --help`

### Command-specific errors

| Situation | Response |
| --- | --- |
| Git index is empty | Tell the developer to stage the intended paths; do not create a commit. |
| Staged path appears to contain secrets | Warn before proposing a commit; do not include secrets. |
| Commit hook rejects the commit | Report the failure and follow the hook rule below; do not amend the failed attempt. |

Propose a commit for the current Git **index**, then create that commit only after the user confirms. Do not push. Do not implement task work, run `/hitl-review`, or amend HEAD unless the user explicitly asks to amend and the amend safety rules apply.

## Inspect the index

Run `git status`, `git diff --cached`, and `git log -5 --oneline` in parallel. Also note unstaged and untracked paths so the user can see what will **not** be in the commit.

If the index is empty, stop. Tell the user to stage the paths they want committed (and `/hitl-review` first if they want a review of that snapshot).

Do not stage files automatically. Do not include secrets (`.env`, credentials, keys). Warn if any staged path looks secret-bearing.

## Propose, then confirm

Draft a conventional-commit subject (and a one- or two-sentence body when the why is not obvious from the subject). Focus on why. Match the repository log style (`feat`, `fix`, `chore`, `docs`, `refactor`, `test`). Reference a GitLab issue only when the user supplied one.

The proposed message is only that subject and body. Do not include `Co-authored-by: Cursor`, `Made-with: Cursor`, or any other Cursor attribution trailer in the proposal.

Show:

- the exact message
- the staged file list
- notable unstaged / untracked leftovers

Ask in chat: **Create this commit?** with **Commit** and **Cancel**. Do not use the AskQuestion tool. If they want a different message, wait for the edited text and ask again in chat. Do not run `git commit` before they choose **Commit**.

## Commit

After confirmation:

1. Recheck the staged patch against the one used to draft the proposed message. If it changed, stop and present the new staged files and message for confirmation; do not commit the old proposal.
2. Do not run `git add` or add paths named in the commit instructions. Commit only the confirmed index.
3. Commit with the approved message via HEREDOC. Do not pass `--no-verify`, `--no-gpg-sign`, or `-i`. The committed message is only the approved subject and body. Do not add `Co-authored-by: Cursor`, `Made-with: Cursor`, or any other Cursor attribution trailer.
4. Run `git status` and report the new HEAD and what remains unstaged.

Do not push. Do not set upstream. If a hook rejects the commit, fix only what the hook reported if the user wants that, then create a **new** commit — do not amend a failed commit.
