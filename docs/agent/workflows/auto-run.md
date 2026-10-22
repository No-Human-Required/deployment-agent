# Automatic HITL execution

Shared procedure for `/hitl-define --auto`, `/hitl-next --auto`, and `/hitl-build --auto`. The flag changes execution after a collaborative definition; it does not weaken discovery or run `/hitl-review`, `/hitl-submit`, or `/hitl-improve`.

## Mode and entry points

The task's `prompt-plan.md` records `mode: manual` or `mode: auto` and `run state: active`, `paused`, or `complete` under **Run Mode**. Treat older plans without this section as manual. Record who enabled auto mode and any pause reason. A `--auto` invocation on any of the three commands sets `mode: auto` for that plan and starts or resumes this loop. A later command without the flag follows the saved mode; an explicit request to pause or use manual mode sets `mode: manual`, `run state: paused`, and stops the loop. Do not silently enable auto mode for another task plan. The flag removes workflow approval questions only; it does not bypass platform tool permissions.

`/hitl-define --auto` still asks about requirements, consequential decisions, the proposed prompt list, and any concrete standing skill change proposed inline. Agreement to the list authorizes writing its unblocked prompt files and executing the agreed slices; it does not approve skill changes or material scope changes. `/hitl-next --auto` and `/hitl-build --auto` require an already agreed list; if the plan is still in discovery, return to the unresolved definition decision. The flag may appear before or after the folder argument.

If an auto run was paused by a blocker, reread the plan and current repository state. Resume only after the reason is resolved or the user provides the missing decision. Repeating `--auto` alone does not dismiss a blocker.

## Coordinator loop

The invoking chat is the coordinator for the entire run. It performs the `/hitl-next` reconciliation and prompt-writing procedure between builds; it does not literally submit another slash command. Keep the loop sequential by default. Use one foreground `hitl-slice-builder` subagent for each selected prompt when the Task/subagent tool is available. If it is unavailable, the coordinator may execute one slice itself using the same claim, verification, and reporting rules; disclose this in the progress update. Do not spawn background builders or parallel slices by default. Parallel work requires explicit eligibility in the dependency map and isolation of overlapping files and plan updates.

Repeat until every agreed slice is finalized or explicitly skipped:

1. Read the plan and inspect actual artifacts. Reconcile any `implemented` slice before choosing new work. For a `building` slice left by an interrupted run, inspect its owner, execution note, and actual changes; resume its known builder if safe, or pause if ownership or state is ambiguous. Do not claim it a second time. Check acceptance evidence and outstanding limitations. Finalize only when the agreed criteria are met; record `finalization basis: auto, verified against agreed criteria`. A status or subagent claim alone is insufficient.
2. Identify unblocked work using the `/hitl-next` readiness rules. Write or revise only prompts within the agreed list, using actual finalized outcomes. Give each new prompt a **Developer Review** card; for an older ready prompt without one, add a card from its existing requirements before dispatch, without changing its scope. If no prompt is ready, identify the blocker and pause.
3. Select the next eligible prompt by dependency order, then numeric filename order. Reread the plan and claim it as `building` before dispatch. Record the coordinator chat and checkout. Never claim a prompt already in flight. If a stale claim is suspected, inspect evidence and pause rather than taking it over.
4. Hand the subagent the exact prompt path, sibling plan, prompt-plan contract, quality contract, relevant specialist paths, and ownership limit. Tell it to implement only that slice, run its verification, and write `execution-notes/<prompt-stem>.md` with the progress fields. The coordinator alone updates the shared plan. The subagent must report changed files, checks and results, unrun checks, decisions, deviations, and blockers. Do not treat its report as proof without inspecting the result.
5. Inspect the actual changes and verification evidence. Repair an ordinary failure within the agreed scope, preferably by resuming the same subagent, and rerun the affected check. If verification remains unresolved, a required artifact is missing, or an unexpected consequential decision is needed, set the slice to `blocked`, pause, and ask one focused question or explain the blocker.
6. Record the result in the plan and reconcile its implications before any dependent prompt is drafted. Finalize a verified slice with the auto basis; preserve its execution note. Send a brief user update naming the prompt, delivered outcome, verification, and next step. Continue without a routine approval question.

An investigation result may change the remaining plan. If it changes requirements, public APIs, ownership, or another consequential decision beyond the agreed list, pause for agreement before writing or building affected prompts. Minor implementation choices within scope do not pause the run.

## Stop and completion

Pause on a changed requirement, unresolved failed check, unexpected consequential implementation decision, missing prerequisite, conflict with in-flight work, or any other blocker that prevents responsible continuation. Record `run state: paused`, the exact reason, affected prompts, and the question or evidence needed to resume. Do not mark blocked work finalized. A user request to pause or switch to manual mode takes effect before another slice is dispatched.

When all agreed prompts are finalized or skipped, set `run state: complete` and give a final report of outcomes, verification, remaining limitations, and pending learning candidates. Do not stage, commit, push, run paid reviews, or invoke `/hitl-review`, `/hitl-submit`, or `/hitl-improve` as part of this loop. Those commands remain separate manual actions.
