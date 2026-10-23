# API client → apps/agent

## Goal

Point the Vite shell’s API client at the companion `apps/agent` BFF (settings, health/ready, CORS) instead of the thin `backend/` MVP, so subsequent slices can call orchestrator APIs.

## Developer Review

- **Output:** `src/lib/api.ts` (+ schemas as needed) talks to `apps/agent` shapes; proxy still `:8000`; settings get/save and prove-read work against companion; document that `uvicorn` must run `apps/agent` not `backend`.
- **Ownership:** `src/lib/**`, maybe `vite.config.ts` proxy; minimal `apps/agent` CORS tweaks if required.
- **Depends on:** 01.
- **Acceptance:** Typecheck/build pass; mocked or live GET settings against agent contract; README run instructions use `apps/agent`.

## Context

- Companion settings: `GET/PUT /api/settings` with `liara` + `aval` nested public view (see apps/agent).
- Thin main backend had flatter settings — adapt client/types.
- Do not implement full orchestrator chat bridge yet (04).

## Requirements

1. Align Zod schemas / TS types with companion settings public model.
2. Update `getSettings` / `saveSettings` / prove endpoints to companion paths.
3. Services list: map from companion prove/projects if available, or keep stub with clear error until 06.
4. README: how to run `apps/agent` + Vite shell together.
5. `npm run build` passes; add/adjust vitest if settings parsing tests exist.
6. `execution-notes/02-api-client-apps-agent.md`.

## Relevant Skills

- `.cursor/skills/api-design/SKILL.md`
- `.cursor/skills/system-architecture/SKILL.md`

## Acceptance Criteria

- [ ] Shell builds.
- [ ] Settings API types match companion redacted view.
- [ ] Run docs point to `apps/agent` on :8000.
- [ ] No secret echo in client handling.

## Verification

```sh
npm run build
# optional: with agent up, curl /api/settings via proxy
```

## Non-goals

Chat orchestrator, GenUI parity, retiring Next.
