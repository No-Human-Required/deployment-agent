/**
 * Quiet chat helpers — keep transcript conversational; leave internals in Inspector.
 */

type Locale = "en" | "fa";

/** Shape POST /assess_readiness body; omit empty app_path. */
export function assessReadinessPayload(
  workspaceId: string,
  caseId: string,
  appPath?: string | null,
): { workspace_id: string; case_id: string; app_path?: string } {
  const trimmed = appPath?.trim();
  return {
    workspace_id: workspaceId,
    case_id: caseId,
    ...(trimmed ? { app_path: trimmed } : {}),
  };
}

/** Short human reply after a plan is ready — no case UUID / readiness dump. */
export function planReadyAssistantText(
  language: Locale,
  planSummary: string | null | undefined,
): string {
  const summary = planSummary?.trim();
  if (language === "fa") {
    if (summary) {
      return `${summary} اگر موافقید، از دکمه تأیید روی کارت طرح استفاده کنید.`;
    }
    return "درخواستتان را گرفتم و یک طرح پیشنهادی آماده کردم. برای اجرا از دکمه تأیید استفاده کنید — نوشتن در گفتگو مجوز نیست.";
  }
  if (summary) {
    return `${summary} If that looks right, use Approve on the plan card.`;
  }
  return "I have a proposed plan ready. Use Approve on the plan card to execute — chat text is not authorization.";
}

const FAIL_STATES = new Set([
  "verify_failed",
  "blocked",
  "deps_blocked",
  "deps_partial",
  "unknown",
  "handoff",
]);

function verificationDetail(
  language: Locale,
  state: string,
  checkpoint?: Record<string, unknown> | null,
): string | null {
  const verification =
    checkpoint && typeof checkpoint.verification === "object" && checkpoint.verification
      ? (checkpoint.verification as Record<string, unknown>)
      : null;
  const openNeeds = Array.isArray(checkpoint?.open_needs)
    ? (checkpoint?.open_needs as unknown[]).map(String)
    : [];

  if (language === "fa") {
    if (state === "verify_failed") {
      const bits: string[] = [];
      if (verification?.release_ok === false) {
        bits.push("انتشار در لیارا تأیید نشد");
      }
      if (verification?.http_ok === false) {
        if (verification.http_stub_detected) {
          bits.push(
            "آدرس عمومی فقط یک پاسخ آزمایشی (مثل ok/hello-world) برگرداند — اپ واقعی تأیید نشد",
          );
        } else {
          const status = verification.http_status;
          bits.push(
            typeof status === "number"
              ? `پاسخ HTTP سرویس ناموفق بود (${status})`
              : "پاسخ HTTP سرویس ناموفق بود",
          );
        }
      }
      const appUrl = verification?.app_url;
      if (typeof appUrl === "string" && appUrl.trim()) {
        bits.push(`آدرس بررسی‌شده: ${appUrl.trim()}`);
      }
      if (verification?.blocked_by_dependencies) {
        bits.push("پیش‌نیازهای وابستگی هنوز باز هستند");
      }
      if (openNeeds.some((n) => /dependenc/i.test(n))) {
        bits.push("احتمالاً دیتابیس یا دیسک به اپ وصل نیست");
      }
      if (bits.length) return bits.join("؛ ") + ".";
      return "راستی‌آزمایی ناموفق بود؛ الان علت را از لاگ و وضعیت سرویس بررسی می‌کنم.";
    }
    if (state === "blocked" || state === "deps_blocked") {
      return "اجرا کامل نشد چون پیش‌نیازها باز مانده‌اند.";
    }
    return null;
  }

  if (state === "verify_failed") {
    const bits: string[] = [];
    if (verification?.release_ok === false) bits.push("release was not confirmed");
    if (verification?.http_ok === false) {
      if (verification.http_stub_detected) {
        bits.push(
          "public URL returned a smoke stub (ok/hello-world) — real app not verified",
        );
      } else {
        const status = verification.http_status;
        bits.push(
          typeof status === "number" ? `HTTP check failed (${status})` : "HTTP check failed",
        );
      }
    }
    const appUrl = verification?.app_url;
    if (typeof appUrl === "string" && appUrl.trim()) {
      bits.push(`checked URL: ${appUrl.trim()}`);
    }
    if (verification?.blocked_by_dependencies) bits.push("dependency prerequisites are still open");
    if (openNeeds.some((n) => /dependenc/i.test(n))) {
      bits.push("database or disk may not be wired to the app");
    }
    if (bits.length) return `${bits.join("; ")}.`;
    return "Verification failed; I’ll inspect logs and service status next.";
  }
  if (state === "blocked" || state === "deps_blocked") {
    return "Execution did not complete because prerequisites are still open.";
  }
  return null;
}

/** Useful outcome after verify — explain failures; no operation UUID spam. */
export function verificationAssistantText(
  language: Locale,
  state: string,
  checkpoint?: Record<string, unknown> | null,
): string {
  const detail = verificationDetail(language, state, checkpoint);
  const completeSuccess = checkpoint?.complete_success;
  const openNeeds = Array.isArray(checkpoint?.open_needs)
    ? (checkpoint?.open_needs as unknown[]).map(String)
    : [];
  const depWarn = openNeeds.some((n) => /dependenc/i.test(n));

  if (language === "fa") {
    if (FAIL_STATES.has(state)) {
      return detail
        ? `اجرا تمام شد اما نتیجه تأیید نشد (${state}). ${detail}`
        : `اجرا تمام شد اما نتیجه تأیید نشد (${state}).`;
    }
    if (state === "verified" && completeSuccess === false && depWarn) {
      return "انتشار انجام و تأیید شد، اما پیش‌نیازهایی مثل دیتابیس/دیسک هنوز باز هستند — سرویس ممکن است تا اتصال آن‌ها کامل کار نکند.";
    }
    return `اجرا انجام شد. وضعیت نهایی: ${state}.`;
  }
  if (FAIL_STATES.has(state)) {
    return detail
      ? `Execution finished but verification did not succeed (${state}). ${detail}`
      : `Execution finished but verification did not succeed (${state}).`;
  }
  if (state === "verified" && completeSuccess === false && depWarn) {
    return "Release verified, but dependency prerequisites (e.g. database/disk) are still open — the app may not fully work until they are wired.";
  }
  return `Execution finished. Final state: ${state}.`;
}

export function verificationNeedsTroubleshoot(state: string): boolean {
  return FAIL_STATES.has(state);
}

/** Project name from an operation checkpoint after deploy/ops execute. */
export function projectNameFromOperationCheckpoint(
  checkpoint?: Record<string, unknown> | null,
): string | null {
  if (!checkpoint || typeof checkpoint !== "object") return null;
  const providerIds =
    checkpoint.provider_ids && typeof checkpoint.provider_ids === "object"
      ? (checkpoint.provider_ids as Record<string, unknown>)
      : null;
  const fromProvider = providerIds?.project_name;
  if (typeof fromProvider === "string" && fromProvider.trim()) return fromProvider.trim();
  const direct = checkpoint.project_name;
  if (typeof direct === "string" && direct.trim()) return direct.trim();
  return null;
}
