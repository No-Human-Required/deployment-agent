---
name: agent-workspace-ux
description: Design and review agent workspace shells (folder-first context, chat threads, progress disclosure, in-chat GenUI, HITL) using patterns from Cursor-like and other well-known coding agents.
---

# Agent workspace UX

## Role and reasoning standards

Reason as a product engineer for **agent companions**: the person opens a workspace, talks in natural language, sees only useful progress, and authorizes consequential actions. Prefer conventions from mature agent UIs (e.g. Cursor Agent: pick folder → chats live in that workspace; clear thread list; tool/progress secondary to dialogue) adapted to this product — not a pixel clone.

Use [UX design](../ux-design/SKILL.md) for general interaction reliability, accessibility, and state coverage. This skill does not replace it; it specializes **agent shell** decisions.

Challenge dumps of internal orchestrator state into the transcript. Challenge starting high-impact work before workspace and required intake exist. Do not invent research claims about competitor products; cite observable conventions and the task's agreed requirements.

## Load when

- Folder/workspace-first agent UI, chats scoped to a project root
- Chat list / thread history UX for an agent product
- Separating dialogue from tool/timeline/inspector surfaces
- In-chat generative intake (service, plan, domain) after intent is clear
- HITL approve controls as part of the chat workspace (propose ≠ execute)

Defer to `ux-design` alone for non-agent screens (marketing, pure settings forms) unless they share the agent shell chrome.

## Evidence and questions

- Inspect current shell layout (sidebar, chat, inspector/nav) and how `app_path` / Liara identity are obtained today.
- Treat competitor agent UIs as **directional** references unless the developer marks one authoritative.
- Establish: how workspace is chosen; where threads are stored; what is global vs workspace-scoped; when GenUI appears; where progress lives; how CLI-local vs API-cloud actions share the same folder context.

## Failure modes and decisions

- **Missing workspace:** block project-bound actions; allow only clearly global surfaces (e.g. account settings) until a folder is selected.
- **Wrong disclosure:** internal ids, readiness dumps, and raw tool names in chat bubbles are defects unless the user explicitly opens a debug view.
- **Premature automation:** do not run deploy/ops writes before intent + required intake + HITL when sensitive.
- **Scope confusion:** workspace-scoped chats must not silently mix threads from another folder; switching folder switches (or clearly partitions) the thread list.
- **Local vs cloud:** local folder is the source for CLI/filesystem; Liara APIs operate on cloud resources selected in intake — both bound through the same user journey.

## Contributions across stages

- Requirements: workspace gate, thread model, disclosure rules, intake timing, global vs scoped surfaces.
- Structure: ownership of workspace state, conversation store keying, chat vs inspector responsibilities.
- Technical decisions: picker/OS integration, persistence keying by folder, when `app_path` is injected into agent calls.
- Verification: journeys for open-folder → chat list → intent → GenUI → timeline → HITL; empty/error workspace states.

## Expected output

Workspace and thread model, disclosure rules, intake/progress placement, global vs scoped navigation, and observable acceptance examples aligned with agreed product decisions.
