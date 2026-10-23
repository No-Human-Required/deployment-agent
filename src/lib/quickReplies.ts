/**
 * In-chat quick replies under assistant messages — speed GenUI paths
 * without replacing HITL Approve as the write authorization gate.
 */

export type QuickReplyKind =
  | "prompt"
  | "approve"
  | "reject"
  | "settings"
  | "fix"
  | "intake_service";

export type QuickReply = {
  id: string;
  label: string;
  kind: QuickReplyKind;
  /** Free-text goal for `prompt` replies. */
  prompt?: string;
  /** Fix option id or service project name. */
  value?: string;
};

type Locale = "en" | "fa";

export function conversationIntentReplies(language: Locale): QuickReply[] {
  if (language === "fa") {
    return [
      { id: "intent-deploy", kind: "prompt", label: "دیپلوی پروژه", prompt: "این پروژه را دیپلوی کن" },
      {
        id: "intent-troubleshoot",
        kind: "prompt",
        label: "عیب‌یابی سرویس",
        prompt: "بررسی خطای HTTP 500",
      },
      {
        id: "intent-domain",
        kind: "prompt",
        label: "اتصال دامنه",
        prompt: "دامنه سفارشی را به سرویس وصل کن",
      },
      {
        id: "intent-monitor",
        kind: "prompt",
        label: "فعال‌سازی پایش",
        prompt: "یک مانیتور پایش برای فضای کار فعال کن",
      },
    ];
  }
  return [
    { id: "intent-deploy", kind: "prompt", label: "Deploy project", prompt: "Deploy this project" },
    {
      id: "intent-troubleshoot",
      kind: "prompt",
      label: "Troubleshoot service",
      prompt: "Investigate HTTP 500 errors",
    },
    {
      id: "intent-domain",
      kind: "prompt",
      label: "Attach domain",
      prompt: "Attach a custom domain to my service",
    },
    {
      id: "intent-monitor",
      kind: "prompt",
      label: "Enable monitor",
      prompt: "Enable a maintain monitor for this workspace",
    },
  ];
}

export function approvalReplies(language: Locale): QuickReply[] {
  return language === "fa"
    ? [
        { id: "hitl-approve", kind: "approve", label: "تأیید و اجرا" },
        { id: "hitl-reject", kind: "reject", label: "رد طرح" },
      ]
    : [
        { id: "hitl-approve", kind: "approve", label: "Approve & run" },
        { id: "hitl-reject", kind: "reject", label: "Reject plan" },
      ];
}

export function settingsReply(language: Locale): QuickReply {
  return language === "fa"
    ? { id: "open-settings", kind: "settings", label: "باز کردن تنظیمات" }
    : { id: "open-settings", kind: "settings", label: "Open Settings" };
}

export function verifiedFollowUpReplies(language: Locale): QuickReply[] {
  if (language === "fa") {
    return [
      {
        id: "follow-status",
        kind: "prompt",
        label: "وضعیت سرویس",
        prompt: "وضعیت سلامت سرویس را نشان بده",
      },
      {
        id: "follow-monitor",
        kind: "prompt",
        label: "پایش را فعال کن",
        prompt: "یک مانیتور پایش برای فضای کار فعال کن",
      },
      ...conversationIntentReplies(language).slice(0, 2),
    ];
  }
  return [
    {
      id: "follow-status",
      kind: "prompt",
      label: "Service health",
      prompt: "Show me service health",
    },
    {
      id: "follow-monitor",
      kind: "prompt",
      label: "Enable monitor",
      prompt: "Enable a maintain monitor for this workspace",
    },
    ...conversationIntentReplies(language).slice(0, 2),
  ];
}

/**
 * “What next?” chips after a terminal plain assistant message —
 * only when no generative UI is still waiting for the user.
 */
export function whatNextReplies(language: Locale): QuickReply[] {
  return conversationIntentReplies(language);
}

/** Stages where a GenUI surface (intake / HITL / fix pick) owns the next action. */
export function generativeAwaitingUser(stage: string | null | undefined): boolean {
  return (
    stage === "awaiting_intake" ||
    stage === "awaiting_approval" ||
    stage === "planning" ||
    stage === "approving" ||
    stage === "executing" ||
    stage === "verifying"
  );
}

/** Service chips when intake only needs a project (no plan/domain form). */
export function intakeServiceReplies(
  services: { id: string; name: string }[],
  language: Locale,
  limit = 5,
): QuickReply[] {
  const chips = services.slice(0, limit).map((service) => ({
    id: `svc-${service.id}`,
    kind: "intake_service" as const,
    label: service.name,
    value: service.name,
  }));
  if (chips.length === 0) {
    return [settingsReply(language)];
  }
  return chips;
}

export function fixOptionReplies(
  options: { id: string; label: string; enabled: boolean }[],
): QuickReply[] {
  return options
    .filter((option) => option.enabled)
    .slice(0, 6)
    .map((option) => ({
      id: `fix-${option.id}`,
      kind: "fix" as const,
      label: option.label,
      value: option.id,
    }));
}

export function diagnosisFollowUpReplies(
  language: Locale,
  nextQuestion?: string | null,
): QuickReply[] {
  const replies: QuickReply[] = [];
  const q = nextQuestion?.trim();
  if (q) {
    replies.push({
      id: "diag-next",
      kind: "prompt",
      label: language === "fa" ? "ادامه بررسی" : "Continue investigation",
      prompt: q,
    });
  }
  replies.push(
    ...(language === "fa"
      ? [
          {
            id: "diag-other",
            kind: "prompt" as const,
            label: "سرویس دیگر",
            prompt: "سرویس دیگری را عیب‌یابی کن",
          },
        ]
      : [
          {
            id: "diag-other",
            kind: "prompt" as const,
            label: "Another service",
            prompt: "Investigate another service",
          },
        ]),
  );
  return replies;
}
