# Restore Vite agent shell from main

## Goal

Bring the Cursor-like agent workspace UI from git branch `main` (`src/`, Vite root tooling) onto the current working tree so `pnpm`/`npm run dev` serves an excellent base shell on port 5173, without deleting `apps/agent` or `apps/web`.

## Developer Review

- **Output:** Working Vite+React shell at repo root (or documented path) with `src/App.tsx` chat+nav+inspector; `npm install` + `npm run build` (or pnpm equivalent) succeed; default language can stay as on main for now (FA polish later).
- **Ownership:** Root Vite files + `src/**`. Do not rewire to `apps/agent` yet (slice 02). Do not delete companion apps.
- **Depends on:** none.
- **Acceptance:** Dev server starts; production build passes; UI visibly matches main shell chrome.

## Context

- Source of truth for UI: `git show main:src/...`, `main:package.json`, `main:vite.config.ts`, `main:index.html`, `main:tsconfig*.json`, `main:components.json` if present.
- Current tree also has `apps/agent` (companion BFF) and `apps/web` (Next). Preserve both.
- If root `package.json` conflicts with monorepo tooling, prefer restoring Vite root scripts from `main` and keep `apps/*` installable via their own manifests; document how to run shell vs agent.
- UI quality bar: excellent — keep Motion and visual system from main; no ugly regressions.

## Requirements

1. Restore `src/` tree and Vite entry (`index.html`, `vite.config.ts`, tsconfigs) from `main`.
2. Restore root frontend `package.json` dependencies/scripts needed for Vite (merge carefully if a monorepo package.json already exists — do not wipe `apps/` scripts without replacing run docs).
3. `npm install` (or pnpm) at the path that owns the Vite app; `npm run build` passes.
4. Smoke: `npm run dev` listens on 5173 (or document port); homepage shows agent workspace chrome.
5. Do not point API client at `apps/agent` yet beyond whatever main already proxies to `:8000` (thin backend may still be referenced — leave for 02).
6. Write `execution-notes/01-restore-vite-shell.md`.

## Relevant Skills

- `.cursor/skills/ux-design/SKILL.md`
- `.cursor/skills/system-architecture/SKILL.md`
- `docs/agent/repository-quality-contract.md`

## Implementation Instructions

Prefer `git checkout main -- <paths>` for fidelity. Resolve conflicts without dropping companion apps. No commit/push. Do not edit `prompt-plan.md`.

## Acceptance Criteria

- [ ] `src/App.tsx` (or equivalent) present with chat/nav/inspector structure from main.
- [ ] Vite build succeeds.
- [ ] `apps/agent` and `apps/web` still present.
- [ ] README or short note on how to run the shell.

## Verification

```sh
# from the Vite app root after restore
npm install
npm run build
# optional: npm run dev and curl :5173
```

## Execution Handoff

Auto slice; execution note required; coordinator owns plan.

## Non-goals

Wiring companion orchestrator; GenUI parity; retiring Next; docs challenge rewrite.
