# Settings + Aval/Liara in shell

## Goal

Complete Settings UX in the Vite agent shell for both Liara and Aval AI (nested companion model): save credentials without echoing secrets, show configured labels, and prove Liara read — so chat/ops slices can rely on configured workspace settings.

## Developer Review

- **Output:** Settings nav surface with Liara (base URL, team id, token) + Aval (base URL, model, API key) fields wired to `src/lib/api.ts` companion contracts; prove-read control; clear configured/not-configured status; FA/RTL acceptable polish for this surface (full excellence pass is 07).
- **Ownership:** `src/App.tsx` Settings region (or extracted `src/components/Settings*.tsx` if cleaner); may extend `src/lib/api.ts` / schemas only if companion gaps appear. Do not rewrite orchestrator chat (04).
- **Depends on:** 02.
- **Acceptance:** Build + tests pass; saving Aval fields updates redacted view (`api_key_configured` / labels); Liara prove-read still works; secrets never rendered from GET.

## Context

- Companion `GET/PUT /api/settings` nested public view (already typed in slice 02).
- Current shell Settings is Liara-only (token/team/base); Aval fields exist on schema but not in UI.
- `apps/agent` sources are restored and pytest green; BFF on `:8000` via Vite proxy.
- Defaults previously used in companion: Aval base `https://api.avalai.ir/v1`, model `gpt-5.6-luna` (user may override).

## Requirements

1. Settings form: Liara section (api_base_url, team_id, token input only when setting/rotating) + Aval section (base_url, model, api_key input when setting/rotating).
2. On load, populate non-secret fields from `getSettings()`; show `*_configured` / `*_label` status; never display raw secrets from the server.
3. Save via `saveSettings` — only send secret fields when the user typed a new value; empty team id clears per companion contract.
4. Keep / improve Prove Liara read control and success/error messaging.
5. Empty/error/loading states for Settings; no secret echo in messages or Inspector dumps.
6. `npm run build` and `npm test` pass; write `execution-notes/03-settings-shell.md`.

## Relevant Skills

- `.cursor/skills/ux-design/SKILL.md`
- `.cursor/skills/api-design/SKILL.md`
- `.cursor/skills/generative-ui/SKILL.md` (optional if using a small status card)

## Acceptance Criteria

- [ ] Aval base_url, model, and api_key can be saved and reflect on next GET as configured/labels only.
- [ ] Liara token save + prove-read still work.
- [ ] No secret values appear in UI from GET responses.
- [ ] Build and unit tests pass.

## Verification

```sh
npm test
npm run build
# optional live: with apps/agent up, save Aval fields then GET /api/settings via proxy
```

## Non-goals

Orchestrator chat bridge, GenUI plan cards, nav services/deployments live data, retiring `apps/web`.

## Execution Handoff

Auto slice; do not edit `prompt-plan.md`; write execution note only.
