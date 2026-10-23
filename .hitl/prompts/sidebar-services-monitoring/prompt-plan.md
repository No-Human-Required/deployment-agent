# Prompt Plan

## Developer Overview

- **Goal:** سرویس‌های لیارا به‌عنوان موجودیت مستقل حساب کاربری در سایدبار (بالای پوشه‌ها) با نقطه وضعیت؛ کلیک → مانیتورینگ همان سرویس در ناحیه اصلی (وضعیت زنده، CPU/RAM در صورت دسترسی API، لاگ‌های اخیر + CTA Investigate).
- **Expected outputs:** BFF read endpoints برای جزئیات/متریک/لاگ؛ نگاشت وضعیت → tone؛ بخش سایدبار Services؛ view مانیتورینگ per-service در شِل.
- **Ownership:** UI `src/` (به‌ویژه `App.tsx`, `NavigationView.tsx`, `api.ts`, CSS)؛ BFF `apps/agent/app/api/liara.py` + schemas/tests؛ کلاینت موجود `liara_client.py` بدون اختراع API بالادستی.
- **Boundaries:** بدون write/ops جدید؛ بدون وابستگی سرویس به پوشه محلی؛ محدودیت API لیارا باید به کاربر اعلام شود.
- **Acceptance evidence:** با توکن معتبر، لیست بالای پوشه‌ها؛ رنگ نقطه مطابق وضعیت؛ کلیک پنل مانیتورینگ همان سرویس را در main pane نشان می‌دهد؛ بدون پوشه هم کار می‌کند؛ بدون توکن/بدون سرویس empty state روشن.
- **Open decisions:** توافق روی لیست promptها (در انتظار).

## Decision Topics

| Topic | Status | Current answer | Next question |
| --- | --- | --- | --- |
| Outcome | decided | سایدبار سرویس‌ها + نقطه وضعیت + مانیتورینگ per-service | — |
| Monitoring content | decided | وضعیت زنده + CPU/RAM + لاگ اخیر + Investigate | — |
| Panel placement | decided | ناحیه اصلی (NavigationView / main pane) | — |
| Folder coupling | decided | سرویس مستقل از پوشه؛ حتی بدون فولدر نمایش داده شود | — |
| Status tones | decided | آنلاین سبز؛ خطا قرمز؛ استاپ خاکستری؛ ناشناخته muted | — |
| Prompt list | proposed | 3 اسلایس عمودی (پایین) | توافق روی لیست؟ |

## Run Mode

- mode: auto
- run state: (pending list agreement)
- enabled by: `/hitl-define --auto` (2026-10-23)
- pause reason: awaiting agreement to proposed prompt list

## Source Identity

| Source | Ref | Authority |
| --- | --- | --- |
| User intention | chat FA 2026-10-23 | Primary |
| Challenge brief | `challenge.md` Monitoring & Maintenance | Challenge capabilities |
| Prior UX plan | `.hitl/prompts/companion-chat-ux/` | Folder-first shell (complete) |
| Codebase | `App.tsx`, `NavigationView.tsx`, `liara_client.py`, `api.ts` | Current wiring |

## Task Framing

- **Outcome:** کاربر سرویس‌های لیارا را بالای پوشه‌ها می‌بیند، سلامت تقریبی را از نقطه وضعیت می‌فهمد، و با کلیک مانیتورینگ همان سرویس را در main pane می‌بیند — هم‌راستا با پایش `challenge.md`.
- **Affected:** End users (FA/RTL)؛ سایدبار و nav؛ BFF Liara read paths.
- **Scope:** لیست حساب‌محور؛ نگاشت وضعیت؛ BFF برای detail/metrics/logs؛ UI مانیتورینگ per-service؛ سیم‌کشی کلیک سایدبار.
- **Non-goals:** اتصال سرویس↔پوشه؛ داشبورد incident عمومی به‌عنوان هدف اصلی کلیک؛ write/restart از این اسلایس‌ها؛ نصب claudedesignskills / انیمیشن‌های سنگین؛ clone کامل پنل لیارا.
- **Deliverable types:** Code (UI + BFF) + tests/verification.

## Selected Skills

| Path | Reason | Status |
| --- | --- | --- |
| `.cursor/skills/discovery-orchestrator/SKILL.md` | Coordination | active |
| `.cursor/skills/agent-workspace-ux/SKILL.md` | Sidebar vs folder-first; global vs workspace surfaces | active |
| `.cursor/skills/ux-design/SKILL.md` | Status affordance, empty/error states, a11y | active |
| `.cursor/skills/api-design/SKILL.md` | New Liara read BFF contracts | active |
| `claudedesignskills` (marketplace stub) | Not required for status dots / monitoring panel | deferred / not used |

## Source Requirements

### From user (supplied)

- اگر سرویس در لیارا هست، بالای پوشه‌ها لیست شود.
- کنار سرویس‌ها: آنلاین = نقطه وضعیت؛ خطا = قرمز؛ استاپ = خاکستری.
- کلیک → نمایش monitoring.
- رجوع به قابلیت‌های پایش در `challenge.md`.
- پاسخ‌ها RTL.
- تأیید: پنل per-service (وضعیت + CPU/RAM + لاگ + Investigate).
- تأیید: باز شدن در ناحیه اصلی.
- تأیید: سرویس موجودیت مستقل؛ ربطی به پوشه ندارد.

### From challenge.md (Monitoring & Maintenance)

- سلامت سرویس و منابع (CPU/RAM در صورت دسترسی).
- لاگ‌های مرتبط.
- اعلام محدودیت API وقتی داده در دسترس نیست.

## Clarifications

- «Monitoring» در این تسک = داشبورد per-service، نه صرفاً لیست incidentهای `maintain`.
- لیست فعلی سرویس‌ها از `prove-read` می‌ماند برای کاتالوگ سبک؛ مانیتورینگ از endpointهای جدید detail/metrics/logs تغذیه می‌شود.

## Structure and Boundaries

```text
Sidebar (account-global)
  Services section  ← NEW (above Folders)
  Folders section   ← existing workspace-scoped chats
  Wallets / Settings

Main pane
  New Chat | Settings | Service Monitoring (selected service)  ← NEW wiring
```

- **Ownership:** services list state می‌تواند در `App.tsx` بماند (قبلاً `services`/`refreshCatalog`)؛ monitoring fetch در view/API جدید.
- **Does not own:** write ops, folder↔service binding, GenUI chat cards beyond Investigate handoff.

## Technical Decisions

| Decision | Choice | Reason |
| --- | --- | --- |
| Status tones | map Liara `status`/`isDeployed`: RUNNING/STARTED/READY/ACTIVE → online (green); FAILED/ERROR/CRASH → error (red); STOPPED → stopped (gray); else unknown (muted) | Matches user + existing `ops.post_action_health` healthy set |
| Catalog source | keep `getServices` via prove-read for sidebar list | Already wired; avoid duplicate list API unless needed |
| Monitoring reads | new BFF under `/api/liara/projects/{name}/…` wrapping `get_project`, `get_cpu_metrics`, `get_memory_metrics`, `get_logs` | Client methods exist; no dashboard BFF today |
| API gaps | show explicit empty/unavailable copy when metrics/logs missing | challenge.md requirement |
| Panel host | extend/reuse `NavigationView` Monitoring (or dedicated service-monitor mode) selected from sidebar click | Existing nav surface orphaned from sidebar |
| Folder gate | services + monitoring work without local folder | Decided independent entity |
| Motion | reuse `.status-dot` CSS; no claudedesignskills | Proportional |

## Supporting Inputs

- `challenge.md` lines 19–23 (monitoring).
- Existing `.status-dot` / `.status-badge` in `src/index.css` and My Services cards.
- `LiaraClient.get_project` / metrics / logs; healthy statuses in `ops.py`.

## Assets

(none)

## Conflicts / Open Questions

- (none blocking) Exact Monitoring view layout polish deferred to implementer within existing design system.
- Prompt list agreement pending.

## Assumptions

- Liara API token in Settings is required to load services; without it, empty/error copy — not a fake list.
- Prove-read status string is enough for sidebar dots; monitoring panel refreshes richer detail on open.
- Investigate CTA reuses existing chat handoff pattern from My Services cards.

## Deliverables and Evidence of Success

1. سایدبار: بخش سرویس‌ها بالای پوشه‌ها، مستقل از فولدر.
2. نقطه وضعیت با سه tone اصلی (+ unknown).
3. کلیک → main pane مانیتورینگ همان سرویس با وضعیت و در صورت امکان CPU/RAM/لاگ.
4. اعلام واضح وقتی متریک/لاگ در دسترس نیست.
5. تست‌های BFF برای happy/404/unauthorized؛ smoke/UI یا unit برای نگاشت وضعیت.

## Repository Quality Contract

- Root README: Vite `:5173` + `apps/agent` `:8000`.
- Verify: `apps/agent` pytest for new routes; frontend vitest for status mapping if extracted; manual smoke of sidebar → monitoring when token present.
- Do not invent Liara upstream APIs; surface gaps.

## Prompt Decomposition Strategy

Vertical slices: (1) BFF read contract, (2) sidebar list + tones, (3) monitoring main view wired to BFF + click. UI list can use existing catalog while monitoring waits on BFF — slice 2 unblocked after status helper exists (can ship with client-side map on prove-read status); slice 3 depends on 1.

## Agreed Prompt List

_(proposed — awaiting developer agreement)_

### 01 — Liara monitoring read BFF

- **Description:** Expose authenticated read endpoints for project detail, CPU/memory metrics, and recent logs via existing `LiaraClient`; document gap responses.
- **Increment:** Usable HTTP contract for the monitoring UI.
- **Acceptance:** Tests cover 200 shape, 401/404, and empty metrics/logs without crashing.
- **Depends on:** —
- **Touches:** `apps/agent/app/api/liara.py`, schemas, tests; maybe thin service helper.
- **Skills:** api-design
- **Parallel:** no (foundation)

### 02 — Sidebar services above folders

- **Description:** Account-scoped Services section above Folders with status dots (online/error/stopped/unknown); empty/error when no token or no projects; no folder required.
- **Increment:** Visible service inventory in the shell.
- **Acceptance:** Services render above folders without workspace; tones match mapping; RTL/FA labels.
- **Depends on:** — (uses existing `getServices`; status map helper)
- **Touches:** `src/App.tsx`, `src/index.css`, maybe `src/lib/serviceStatus.ts` + test
- **Skills:** agent-workspace-ux, ux-design
- **Parallel:** can start with 01 (disjoint files) if status map is frontend-only

### 03 — Per-service monitoring main view

- **Description:** Clicking a sidebar service opens main-pane monitoring for that service (live status, CPU/RAM, recent logs, Investigate CTA); clear API-limitation copy; highlight selected service.
- **Increment:** End-to-end sidebar → monitoring journey.
- **Acceptance:** Click navigates to monitoring for selected project; shows available data / gaps; Investigate hands off to chat; works without local folder.
- **Depends on:** 01 (data), 02 (entry points / selection)
- **Touches:** `src/App.tsx`, `src/components/nav/NavigationView.tsx`, `src/lib/api.ts`, CSS
- **Skills:** agent-workspace-ux, ux-design, api-design
- **Parallel:** no

## Prompt Dependency Map

```mermaid
flowchart TD
  P1["01 Monitoring read BFF"] --> P3["03 Per-service monitoring view"]
  P2["02 Sidebar services list"] --> P3
  P1 -. disjoint files .- P2
```

## Drafted Prompts

(none yet — write after list agreement)

## Execution Handoffs

(none)

## Prompt Execution Progress

(none)

## Reconciliation Notes

(none)

## Learning Candidates

- claudedesignskills stub attached but not useful for this shell feature; no standing skill change proposed.

## Progress

- 2026-10-23: Intention framed; monitoring content, placement, folder independence decided; plan created; prompt list proposed for agreement.
