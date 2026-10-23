/**
 * Intent-gated GenUI intake: which fields to collect before createPlan,
 * and how confirmed values map to deploy / ops / deps payloads.
 */

import { inferGoalIntent, type GoalIntent, type Locale } from "./requestTimeline";
import { enrichPlatformOptions } from "./liaraPlatforms";

export type IntakeKind =
  | "deploy"
  | "ops_resize"
  | "domain"
  | "troubleshoot"
  | "maintain_monitor";

export type IntakeServiceOption = {
  id: string;
  name: string;
  status?: string;
};

export type IntakePlanOption = {
  id: string;
  label: string;
  hint?: string | null;
  price_monthly?: number | null;
  ram_gb?: number | null;
  tier?: number;
};

export type IntakePlatformOption = {
  id: string;
  label: string;
  hint?: string | null;
  icon?: string | null;
};

export type IntakeDraft = {
  kind: IntakeKind;
  services: IntakeServiceOption[];
  plans: IntakePlanOption[];
  platforms?: IntakePlatformOption[];
  require_plan: boolean;
  require_domain: boolean;
  require_platform?: boolean;
  /** Suggested Liara platform id from local readiness (user may change). */
  suggested_platform?: string | null;
  /** Suggested new service name from folder (deploy). */
  suggested_service_name?: string | null;
  /** Prefer creating a new service instead of picking an existing one. */
  prefer_new_service?: boolean;
  load_error?: string | null;
};

export type IntakeSelection = {
  kind: IntakeKind;
  project_name: string;
  plan_id?: string;
  platform?: string;
  domain_name?: string;
  app_path?: string | null;
};

const RESIZE_RE =
  /resize|scale|تغییر\s*اندازه|تغییر\s*پلن|پلن\s*سرویس|upgrade\s*plan|downgrade|بزرگ‌?تر|کوچک‌?تر/i;

/**
 * When non-null, show in-chat GenUI before createPlan (not for pure Q&A).
 */
export function resolveIntakeKind(goal: string): IntakeKind | null {
  const intent = inferGoalIntent(goal);
  if (intent === "domain") return "domain";
  if (intent === "deploy") return "deploy";
  if (RESIZE_RE.test(goal)) return "ops_resize";
  // Troubleshoot / maintain intake only when the shell has no project yet —
  // `resolveChallengeLoopRoute` prefers an embedded/selected project first.
  if (intent === "troubleshoot") return "troubleshoot";
  if (intent === "maintain") return "maintain_monitor";
  return null;
}

export function needsIntake(goal: string): boolean {
  return resolveIntakeKind(goal) !== null;
}

export function intakeRequirements(kind: IntakeKind): {
  require_plan: boolean;
  require_domain: boolean;
  require_platform: boolean;
  prefer_new_service: boolean;
} {
  switch (kind) {
    case "deploy":
      return {
        require_plan: true,
        require_domain: false,
        require_platform: true,
        prefer_new_service: true,
      };
    case "ops_resize":
      return {
        require_plan: true,
        require_domain: false,
        require_platform: false,
        prefer_new_service: false,
      };
    case "domain":
      return {
        require_plan: false,
        require_domain: true,
        require_platform: false,
        prefer_new_service: false,
      };
    case "troubleshoot":
    case "maintain_monitor":
      return {
        require_plan: false,
        require_domain: false,
        require_platform: false,
        prefer_new_service: false,
      };
  }
}

/** Map confirmed intake → create_plan body fragments (client contract). */
export function buildPlanPayloads(selection: IntakeSelection): {
  deploy?: Record<string, unknown>;
  ops?: Record<string, unknown>;
  deps?: Record<string, unknown>;
} {
  const project = selection.project_name.trim();
  const planId = selection.plan_id?.trim();
  const appPath = selection.app_path?.trim() || undefined;
  const domain = selection.domain_name?.trim();

  if (selection.kind === "deploy") {
    const platform = selection.platform?.trim();
    const deploy: Record<string, unknown> = {
      project_name: project,
      ...(planId ? { plan_id: planId } : {}),
      ...(platform ? { platform } : {}),
      ...(appPath ? { app_path: appPath } : {}),
    };
    // Dependency discovery runs server-side inside deploy drafting (do not pass
    // `deps` here — that would replace the deploy plan with a deps-only plan).
    return { deploy };
  }

  if (selection.kind === "ops_resize") {
    return {
      ops: {
        kind: "resize",
        project_name: project,
        ...(planId ? { plan_id: planId } : {}),
      },
    };
  }

  if (selection.kind === "domain") {
    return {
      ops: {
        kind: "domain",
        project_name: project,
        ...(domain ? { domain_name: domain } : {}),
        provision_ssl: true,
      },
    };
  }

  // troubleshoot / maintain_monitor — no create_plan payload; App routes specially.
  return {};
}

export function intakeAssistantPrompt(kind: IntakeKind, language: Locale): string {
  if (language === "fa") {
    switch (kind) {
      case "deploy":
        return "می‌توانید سرویس جدید بسازید یا یکی از موجودها را انتخاب کنید؛ پلتفرم از روی پروژه پیشنهاد می‌شود و پلن را هم مشخص کنید. پس از تأیید شما طرح نوشته می‌شود — هنوز اجرایی نیست.";
      case "ops_resize":
        return "سرویس و پلن جدید را انتخاب کنید. تغییر پلن فقط بعد از تأیید شما اجرا می‌شود.";
      case "domain":
        return "سرویس هدف و نام دامنه را وارد کنید. اتصال دامنه فقط بعد از تأیید شما انجام می‌شود.";
      case "troubleshoot":
        return "کدام سرویس را بررسی کنیم؟ بعد از انتخاب، شواهد جمع می‌شود؛ هر نوشتن اصلاحی فقط با تأیید شما.";
      case "maintain_monitor":
        return "کدام سرویس پایش شود؟ فعال‌سازی مانیتور اجازهٔ نوشتن حساس نمی‌دهد.";
    }
  }
  switch (kind) {
    case "deploy":
      return "Create a new Liara service or pick an existing one; platform is suggested from your project and you can change it. Then choose a plan — I’ll draft next; nothing runs until Approve.";
    case "ops_resize":
      return "Pick the service and the new plan. Resize only runs after you Approve.";
    case "domain":
      return "Pick the target service and enter the domain name. Attach runs only after you Approve.";
    case "troubleshoot":
      return "Which service should I investigate? I’ll gather evidence next — any write still needs your Approve.";
    case "maintain_monitor":
      return "Which service should I monitor? Enabling a monitor does not grant write permission.";
  }
}

export function intakeCardTitle(kind: IntakeKind, language: Locale): string {
  if (language === "fa") {
    switch (kind) {
      case "deploy":
        return "سرویس، پلتفرم و پلن";
      case "ops_resize":
        return "تغییر پلن سرویس";
      case "domain":
        return "اتصال دامنه";
      case "troubleshoot":
        return "انتخاب سرویس برای عیب‌یابی";
      case "maintain_monitor":
        return "انتخاب سرویس برای پایش";
    }
  }
  switch (kind) {
    case "deploy":
      return "Service, platform & plan";
    case "ops_resize":
      return "Resize service plan";
    case "domain":
      return "Attach domain";
    case "troubleshoot":
      return "Choose service to investigate";
    case "maintain_monitor":
      return "Choose service to monitor";
  }
}

/** Build GenUI intake payload from a loaded draft. */
export function toIntakeViewPayload(
  draft: IntakeDraft,
  language: Locale,
): {
  type: "intake";
  data: {
    kind: IntakeKind;
    title: string;
    prompt: string;
    services: IntakeServiceOption[];
    plans: IntakePlanOption[];
    platforms: IntakePlatformOption[];
    require_plan: boolean;
    require_domain: boolean;
    require_platform: boolean;
    suggested_platform: string | null;
    suggested_service_name: string | null;
    prefer_new_service: boolean;
    load_error: string | null;
    settings_cta: boolean;
  };
} {
  const platforms = draft.require_platform
    ? enrichPlatformOptions(draft.platforms)
    : [];
  return {
    type: "intake",
    data: {
      kind: draft.kind,
      title: intakeCardTitle(draft.kind, language),
      prompt: intakeAssistantPrompt(draft.kind, language),
      services: draft.services,
      plans: draft.plans,
      platforms,
      require_plan: draft.require_plan,
      require_domain: draft.require_domain,
      require_platform: Boolean(draft.require_platform),
      suggested_platform: draft.suggested_platform ?? null,
      suggested_service_name: draft.suggested_service_name ?? null,
      prefer_new_service: Boolean(draft.prefer_new_service),
      load_error: draft.load_error ?? null,
      settings_cta: Boolean(draft.load_error),
    },
  };
}

/** Exported for tests — intent → intake kind alignment. */
export function intakeKindForGoalIntent(
  intent: GoalIntent,
  goal: string,
): IntakeKind | null {
  if (intent === "domain") return "domain";
  if (intent === "deploy") return "deploy";
  if (RESIZE_RE.test(goal)) return "ops_resize";
  if (intent === "troubleshoot") return "troubleshoot";
  if (intent === "maintain") return "maintain_monitor";
  return null;
}
