# UI excellence pass

## Goal

Raise the Vite agent shell to the agreed “excellent” bar: motion, visual hierarchy, empty/loading/error polish, and first-class FA/RTL — without changing product capability scope.

## Developer Review

- **Output:** Cohesive motion and hierarchy across chat, inspector, Settings, nav, and GenUI cards; intentional loading/empty/error; FA/RTL gaps closed for primary surfaces; no generic AI-slop purple/glow clutter.
- **Ownership:** `src/**` styles/components (especially `index.css`, motion usage, layout). Prefer Motion already in the stack. Do not add Three.js/WebXR. Do not change BFF contracts.
- **Depends on:** 05, 06.
- **Acceptance:** Build/tests pass; noticeable polish vs pre-07; RTL/FA usable for Settings + chat + nav; reduced visual noise.

## Context

- User required excellent UI; `claudedesignskills` was a catalogue stub — Motion-first is the right craft for this ops agent.
- Existing: Framer/Motion, Tailwind-ish utilities, custom CSS in `src/index.css`.
- Avoid purple-on-white / cream-serif / broadsheet clichés per project FE rules; preserve LiaraOps visual identity.

## Requirements

1. Hierarchy: clearer primary chat vs secondary inspector/nav; refine spacing/type where cheap.
2. Motion: 2–3 intentional transitions (nav switch, card enter, approval panel) — not noisy.
3. Empty/loading/error consistency across Settings, nav surfaces, chat waiting states.
4. FA/RTL: layout/mirroring polish for locale toggle; no broken direction on forms/cards.
5. GenUI cards: tighten density/contrast for readability.
6. `npm test` + `npm run build`; `execution-notes/07-ui-excellence.md`.

## Relevant Skills

- `.cursor/skills/ux-design/SKILL.md`
- frontend-design / animate skills if available under user skills — Motion-first only

## Acceptance Criteria

- [ ] Motion present and purposeful on key surfaces.
- [ ] Empty/loading/error feel consistent.
- [ ] FA locale does not break layout.
- [ ] Build and tests pass.

## Verification

```sh
npm test
npm run build
```

## Non-goals

New features; retiring Next (08); docs rewrite (09) beyond tiny copy tweaks.

## Execution Handoff

Auto slice; do not edit `prompt-plan.md`; write execution note only.
