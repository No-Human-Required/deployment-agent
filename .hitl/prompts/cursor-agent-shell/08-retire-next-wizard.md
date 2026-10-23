# Retire Next wizard

## Goal

Demote or remove `apps/web` as the primary product UI so the Vite agent shell is the documented entrypoint; leave companion BFF untouched.

## Developer Review

- **Output:** Root README and package scripts point to Vite shell + `apps/agent`; `apps/web` clearly secondary/retired or removed if already hollow; no broken monorepo scripts.
- **Ownership:** Root `README.md`, `package.json` / workspace manifests, `apps/web` (demote/remove), maybe `docs/`. Do not delete `apps/agent`.
- **Depends on:** 07.
- **Acceptance:** Docs/scripts no longer tell users to run Next as primary; Vite path documented; build of Vite shell still works.

## Context

- `apps/web` may already be incomplete after earlier tree damage — treat as retireable.
- Product FE = Vite `src/` on :5173; BFF = `apps/agent` :8000.

## Requirements

1. Update root README: primary run = Vite + agent; Next demoted or removed.
2. Fix root scripts (`dev:web` etc.) so they don’t imply Next is primary (remove or mark legacy).
3. If `apps/web` is empty/broken, remove or leave a short README stating retired.
4. `npm run build` (Vite) still passes; `execution-notes/08-retire-next-wizard.md`.

## Relevant Skills

- `.cursor/skills/technical-documentation/SKILL.md` if present
- `.cursor/skills/system-architecture/SKILL.md`

## Acceptance Criteria

- [ ] Primary docs/scripts → Vite shell.
- [ ] Next not presented as product UI.
- [ ] Vite build passes.

## Verification

```sh
npm run build
# skim README for Vite-first instructions
```

## Non-goals

Full docs rewrite (09); capability changes.

## Execution Handoff

Auto slice; do not edit `prompt-plan.md`; write execution note only.
