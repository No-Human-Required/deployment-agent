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

/** Useful outcome after verify — state only, no operation UUID spam. */
export function verificationAssistantText(language: Locale, state: string): string {
  if (language === "fa") {
    return `اجرا انجام شد. وضعیت نهایی: ${state}.`;
  }
  return `Execution finished. Final state: ${state}.`;
}
