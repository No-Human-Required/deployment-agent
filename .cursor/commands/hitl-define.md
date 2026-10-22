---
name: hitl-define
description: Develop an intention into an agreed HITL prompt plan, with optional automatic execution after definition.
docs:
  - docs/agent/workflows/command-interface.md
  - docs/agent/workflows/prompt-plan-contract.md
  - docs/agent/workflows/auto-run.md
  - docs/agent/repository-quality-contract.md
  - docs/agent/workflows/workflow-learning.md
---

# HITL define

## Interface

**Purpose:** Develop an intention into a resumable, collaborative prompt plan. Auto mode executes the agreed slices after definition.

**Usage:** `/hitl-define [--auto] [--skills-first] [<intention-or-source>]` or `/hitl-define --help`

### Input

| Name | Accepted forms | If omitted |
| --- | --- | --- |
| `<intention-or-source>` | Free-text intention, issue/source link, local file or folder path, or Cursor reference; an existing `prompt-plan.md` resumes that plan. | Resume a plan already unambiguous in this conversation. If clearly resuming among existing plans, offer up to 10 actual plans through `AskQuestion`. Otherwise ask in chat for the intention or source. |

Do not require a detailed specification upfront. Resolve a referenced source before treating it as authoritative; ask only for inaccessible content needed to proceed.

### Options

| Option | Value | Effect | Persistence |
| --- | --- | --- | --- |
| `--auto` | None | After collaborative definition and agreement to the prompt list, run the build/next loop. | Saved as `mode: auto` in this task's plan. |
| `--skills-first` | None | Before definition, inspect the intention for missing specialist skills, report the findings, let the developer request additional skills, and wait for explicit confirmation that no more skills should be added. | Applies to this invocation; record the outcome in the task plan after the gate. |
| `--help` | None | Show this interface and stop before task work. | None. |

Options may appear before or after the input. Follow `docs/agent/workflows/command-interface.md` for parsing, missing input, help, and standard errors.

### Examples

- `/hitl-define Add an email delivery package`
- `/hitl-define --auto Add an email delivery package`
- `/hitl-define --skills-first Add an email delivery package`
- `/hitl-define --auto --skills-first Add an email delivery package`
- `/hitl-define .hitl/prompts/email-package/prompt-plan.md`
- `/hitl-define --help`

### Command-specific errors

| Situation | Response |
| --- | --- |
| Missing intention and no unambiguous plan | Ask in chat for the intention or source. If clearly resuming among existing plans, use `AskQuestion` with up to 10 actual plans. Make no plan changes before an answer. |
| Referenced source is inaccessible or ambiguous | Ask in chat for the missing content or valid reference; use `AskQuestion` only when actual alternative sources can be listed. Do not invent source content. |

Definition remains a discussion in either mode. Without `--auto`, this conversation orchestrates discovery, decomposition, handoffs, and reconciliation without implementing deliverables. With `--auto`, it becomes the coordinator for the agreed build/next loop after definition.

Read `docs/agent/workflows/prompt-plan-contract.md` for Shared memory, Approval and uncertainty, Dependency map and parallel work, Progress contract, and Prompt-file contract. If `--auto` is supplied or the plan records auto mode, also read `docs/agent/workflows/auto-run.md`. First apply `.cursor/skills/discovery-orchestrator/SKILL.md`, including its catalog and only the selected specialist bodies. If `--skills-first` is supplied, complete the skill preflight below before stage 1 or any definition discussion. Otherwise, after initial framing, check whether a missing or misleading skill would materially weaken this definition; revisit as evidence develops. Follow `docs/agent/workflows/workflow-learning.md` for an inline skill proposal when justified. Then use the stages below flexibly: combine stages already answered by evidence, defer dependent questions, and omit irrelevant inputs. Manual mode preserves the explicit decomposition and prompt-writing gates; auto mode keeps the collaborative definition and agreed-list gate, then executes that list without later routine approvals. Neither mode authorizes an unapproved standing skill change.

## Optional skill preflight (`--skills-first`)

Resolve the supplied intention or source and inspect only enough repository context to understand its likely expertise needs. Compare those needs with the specialist catalog and relevant existing skills. Identify distinct, reusable skills that are missing; distinguish them from existing skills that merely need selection or a narrow improvement. Do not begin requirements discovery, create or update the task plan, decompose work, or make definition decisions during this preflight.

Report the missing skills by name with a short reason and proposed selection signal. Explicitly say when none are identified. In either case, invite the developer to name any skills they want added, including skills the preflight did not suggest, and to choose which suggested skills to pursue. Treat a user-nominated skill as a request to prepare it even when the agent did not identify a gap; do not reject it solely because an existing skill overlaps. Explain overlap in the proposal so the developer can choose the intended scope. Resolve only the details needed to draft that skill; do not turn this into task definition.

For each skill the developer wants added, draft the complete skill and catalog entry, check overlap and selection boundaries, and show the exact edits for approval under `docs/agent/workflows/workflow-learning.md`. Apply only approved edits, then refresh the catalog and report what was added, declined, or remains pending. Repeat the invitation to add skills after each response or batch. A suggested skill is not automatically approved; a request to add a skill is not approval of unseen standing guidance.

Ask directly in chat for explicit confirmation that no more skills should be added before beginning stage 1. This gate applies even when the preflight found none, the developer declined all suggestions, an existing plan is being resumed, or `--auto` is active. Do not infer confirmation from silence, approval of one skill, or agreement about the task. After confirmation, record the preflight findings and outcome in `Selected Skills` (and any proposal references in `Learning Candidates`) when creating or updating the plan, then start definition. Continue to notice later evidence-backed skill gaps through the normal inline learning procedure; the preflight confirmation does not approve later skill edits.

## Keep the discussion navigable

Maintain **Decision Topics** in `prompt-plan.md` using short names such as `Outcome`, `API boundary`, or `Rollout`, not a long numbered questionnaire. Track consequential unresolved topics as `open`, `proposed`, `decided`, or `deferred`, with the current answer and next question; omit trivial or already answered topics. Discuss one topic at a time. After a decision, update the board and the authoritative requirement/decision sections. When switching topics, show only a compact list of open or deferred topics and let the developer return to any topic by name. Bundle only questions that genuinely need one joint answer; do not make the developer reply by point number. Keep the **Developer Overview** current as the decisions develop.

Bring every collaborative definition topic to the developer in normal chat, including requirements, scope, assumptions, boundaries, design inputs, technical choices, skill-improvement proposals, and agreement to the prompt list or writing handoff. Ask one focused question at a time, with a recommendation and concise alternatives when useful, then wait for the reply. Do not use `AskQuestion` or `AskQuestions` for these discussions, even when the alternatives are finite. Use `AskQuestion` only to recover a missing or ambiguous command input from actual selectable values under the Interface rules, such as choosing an existing plan to resume. Once the input is resolved, keep the definition conversation in chat.

## 1. Frame the intention and begin shared memory

Accept direct text, issue links, notes, files, images, or available connectors. A broad intention is sufficient to begin; do not require detailed requirements upfront or ask the user to repeat supplied context. Ask for the intended outcome if it is missing. Use available connectors for supplied sources; if inaccessible, request only the missing content needed to proceed.

Identify affected users/systems, scope, non-goals, deliverable types, and evidence of success. Suggest an issue key or short hyphenated task name and confirm it if unclear. Once known, create `.hitl/prompts/<task>/prompt-plan.md` using the Shared memory template. On resumption, read that file and inspect relevant current evidence instead of relying on chat history.

Record initial specialist selection and rationale. Skills can support any subsequent stage; their selection is provisional. For tasks without an applicable specialist, use general engineering judgment. If a clear, reusable guidance gap would affect a decision needed in this definition, draft and validate the smallest skill or catalog change, show the exact proposal, and obtain the developer's approval before activating it. Refresh selection and use approved guidance in the affected decisions. If the gap is uncertain, minor, or deferred, record a learning candidate when warranted and continue where feasible.

## 2. Develop requirements

Follow `docs/agent/workflows/workflow-learning.md` throughout discovery. Capture evidence-backed definition-quality candidates; keep task-specific corrections in requirements. Review an inline candidate only when an approved skill change could improve the current definition; otherwise leave it for `/hitl-improve`. A proposal does not become active guidance until the developer approves its exact edits, including in auto mode. Include reporting of definition-rooted gaps in generated execution handoffs.

Use selected specialists to clarify desired behavior, system guarantees, constraints, and acceptance criteria. Ask outcome questions before ownership or implementation questions unless they are inseparable. Inspect existing evidence before asking discoverable questions. Distinguish supplied requirements, recommendations, and assumptions; confirm material inferred requirements before relying on them.

Record deferred questions. When uncertainty prevents responsible implementation planning, propose a bounded investigation deliverable with its own success criteria. Do not require every downstream unknown to be solved before an independent investigation can proceed.

## 3. Establish structure and boundaries, where useful

Accept supplied diagrams, code, schemas, component trees, service maps, or textual descriptions. Otherwise infer relevant structure from the repo and requirements. Capture responsibilities, inputs/outputs or contracts, ownership, relationships, and state/data dependencies. For UI tasks this may be components and props; for backend tasks, services and interfaces; for data work, entities and pipelines; for infrastructure, resources and environments.

Show inferred structure and confirm consequential boundaries before using them. Do not demand a component tree for non-UI work. Record whether supplied structure is authoritative or directional.

## 4. Resolve technical decisions

Inspect affected projects and existing patterns. Establish relevant contracts, state/data ownership, dependency versions, compatibility, operational constraints, testing, rollout, and recovery. Selected specialists supply depth; their concerns are not a mandatory questionnaire.

Check installed library versions before specifying APIs. Verify uncertain or newly proposed APIs against official documentation. Propose decisions with reasons, confirm material assumptions, and defer choices blocked by investigation. Do not silently introduce dependencies or expand scope.

## 5. Gather supporting inputs as needed

Ask for artifacts relevant to the work: UI designs, API specifications, representative sanitized data, reproduction steps, logs, deployment constraints, benchmarks, or research sources. Reuse evidence already supplied.

When visual appearance matters, explicitly ask whether UI designs or references exist unless already answered. Record their authority; structural diagrams do not substitute for visual designs. If no designs exist, propose and confirm material design expectations from current patterns. Do not ask visual-design questions for tasks without visual scope.

Save supplied local assets under `.hitl/prompts/<task>/assets/` with stable descriptive names. Record source, authority, and local path in the plan. Preserve useful external links; disclose inaccessible sources. Do not imply an attachment was saved if it was not accessible.

## 6. Review quality, conflicts, and readiness

Read `docs/agent/repository-quality-contract.md` and record relevant project-specific checks. Consolidate requirements, specialist findings, structure, decisions, assets, and assumptions. Surface conflicting sources with their impact and a recommended resolution. Resolve conflicts before drafting affected prompts; independent slices may proceed when clearly unaffected.

When ready, summarize the proposed outcome and deliverables using the short **Developer Overview**: goal, expected outputs, important directories and ownership, public APIs and boundaries, acceptance evidence, and open decisions. In manual mode ask: “Do you want me to draft the high-level prompt list now?” Wait for clear agreement, unless that action has already been explicitly authorized for this scope. In auto mode, develop the list collaboratively without a separate permission question just to draft it; agreement to the proposed list is still required before execution.

## 7. Agree the prompt list and dependencies

Each item includes title, description, coherent increment or artifact, acceptance evidence, dependencies, expected touched areas, relevant skills, and parallel eligibility.

Prefer useful vertical slices for features. Other tasks may need reproduction and fix, a bounded research report, a documentation artifact, or staged migration steps. Include verification with the behavior it proves. Avoid layer-only scaffolding without a demonstrated dependency. Investigation-dependent work remains provisional until findings are reconciled.

Collaborate until the list is agreed. Show a compact plan view with each slice's goal, expected output, important directories/APIs/boundaries, dependencies, and acceptance evidence; keep the full plan available for detail. Record and show its dependency map as Mermaid. Parallel safety requires independent decisions and non-overlapping ownership, contracts, files, fixtures, and tests, unless a trivial interaction is explicitly accounted for. Shared plan updates are coordinated using the handoff rules, not assumed conflict-free.

In manual mode, explain that ready prompts run in dedicated conversations via `/hitl-build`, while downstream prompts will be written against actual finalized outcomes. Ask: “Do you want me to write the currently unblocked prompt files now?” Wait for clear agreement unless already authorized. In auto mode, explain that the agreed list will run sequentially in this coordinating chat, with a progress update after each slice, and that `/hitl-review` and `/hitl-submit` remain manual. Agreement to the list also authorizes writing its unblocked prompt files and starting the auto loop; do not ask again merely to write them.

## 8. Write and hand off ready prompts

Use the Prompt-file contract. Write only unblocked prompts, each with a short **Developer Review** card plus relevant specialist paths, accepted decisions, inputs, scoped deliverables, acceptance criteria, verification, and execution handoff. Blocked prompts are provisional only when explicitly requested and must be labeled as such.

Update drafted files, dependency status, and execution handoffs in the shared plan. In manual mode, invite iteration and explain which prompts may run in parallel and how results return through `/hitl-next <prompt-folder>`, except for the last remaining slice. In auto mode, record `mode: auto` and `run state: active`, then follow `docs/agent/workflows/auto-run.md` in this chat. Do not stop after writing the first ready prompt or ask for routine build/next approval.

Continue the applicable reconciliation loop until all agreed prompts are finalized or explicitly skipped. Do not equate writing prompt files with completing the task.
