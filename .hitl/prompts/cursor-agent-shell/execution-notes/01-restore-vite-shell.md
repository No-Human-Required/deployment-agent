# 01-restore-vite-shell — execution note

- 01-restore-vite-shell.md
  - status: implemented
  - execution conversation / checkout: hitl-slice-builder / liara-agent (`main-kamyar-before-kobra`)
  - changed files / artifacts:
    - Restored from `main` via `git checkout main --`:
      - `src/**` (App chat+nav+inspector, Inspector, GenerativeCard, ui, lib, css, main)
      - `index.html`, `vite.config.ts`
      - `package.json`, `package-lock.json`
      - `tsconfig.json`, `tsconfig.app.json`, `tsconfig.node.json`
      - `components.json`
      - `README.md`, `.env.example`
    - Edited `README.md`: Architecture now lists `apps/agent` + `apps/web`; added **Run the agent shell only** section (`npm run dev` → :5173; companion apps documented as separate).
    - Preserved (untouched): `apps/agent/`, `apps/web/`
    - Not restored (intentional): `pnpm-workspace.yaml` / `pnpm-lock.yaml` — root Vite app uses npm + `package-lock.json` per main README; workspace file would point at incomplete `apps/*` package manifests.
  - verification run and results:
    - `npm install` — success (159 packages, 0 vulnerabilities)
    - `npm run build` — success (`tsc -b && vite build`; dist produced)
    - `npm run dev` — listens on `:5173`; `curl http://127.0.0.1:5173/` → HTTP 200, Vite-served `index.html` (LiaraOps Agent Workspace)
    - Confirmed `src/App.tsx` has sidebar nav + chat + Inspector; `apps/agent` and `apps/web` still present after restore
  - verification not run and limitations:
    - No visual browser walkthrough of Motion chrome (smoke was HTTP + source structure)
    - `npm test` / thin `backend` API not run (out of slice acceptance)
    - Did not start `apps/agent` or `apps/web`
    - Dev server stopped after smoke
  - finalization basis, if finalized: (coordinator owns)
  - implementation decisions / findings:
    - Root had no `package.json`/`src/` on this branch; clean restore from `main` with no merge conflict against companion apps.
    - Kept Vite proxy target default `http://127.0.0.1:8000` (thin backend) — no `apps/agent` client rewire (slice 02).
    - UX: Motion shell, EN/FA copy, nav/chat/inspector structure intact from main.
    - Architecture: product UI = root Vite; product BFF remains `apps/agent` (unwired); Next `apps/web` secondary and preserved.
  - deviations from prompt: none material; skipped restoring pnpm workspace files to avoid a broken monorepo install path over incomplete `apps/web` package.json.
  - specialist findings / selection changes:
    - ux-design: restored chat-first workspace chrome (nav / chat / inspector) without inventing new journeys.
    - system-architecture: root Vite owns FE scripts; `apps/*` remain separate processes; no premature BFF coupling.
  - learning candidates, if any: none (definition matched repo state).
  - implications for remaining prompts:
    - Slice 02 can replace `src/lib/api.ts` proxy target / contracts toward `apps/agent`.
    - README already separates shell vs companion run paths; slice 09 can deepen docs.
  - blocking reason / skipped rationale, if applicable: none

## How to run the shell

```bash
# repo root
npm install
npm run dev
# → http://localhost:5173
# /api → http://127.0.0.1:8000 (thin backend until slice 02)
```
