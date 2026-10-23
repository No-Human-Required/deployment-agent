/**
 * User-facing progress timeline derived from the current goal / plan —
 * not the internal orchestrator pipeline (create_case, assess_readiness, …).
 */

import type { OrchestratorStage, PlanVersion } from "./schemas";

export type Locale = "en" | "fa";

export type GoalIntent = "deploy" | "troubleshoot" | "domain" | "maintain" | "generic";

export type TimelineStatus =
  | "pending"
  | "waiting"
  | "done"
  | "error"
  | "rejected"
  | "verified";

export type RequestTimelineStep = {
  title: string;
  detail: string;
  /** Stable key for status updates; not shown as the primary label. */
  tool: string;
  status: TimelineStatus | string;
};

export type BuildRequestTimelineInput = {
  language: Locale;
  goal: string;
  stage: OrchestratorStage;
  planBody?: PlanVersion | null;
  readiness?: { ready: boolean; open_needs: string[] } | null;
  operationState?: string | null;
  error?: string | null;
};

const ACTION_LABELS: Record<string, { en: string; fa: string }> = {
  prepare_deploy_stub: { en: "Prepare deploy", fa: "آماده‌سازی استقرار" },
  create_project: { en: "Create cloud project", fa: "ایجاد پروژه ابری" },
  deploy_app: { en: "Deploy the app", fa: "استقرار برنامه" },
  set_env: { en: "Set environment variables", fa: "تنظیم متغیرهای محیطی" },
  attach_domain: { en: "Attach domain", fa: "اتصال دامنه" },
  provision_ssl: { en: "Enable SSL", fa: "فعال‌سازی SSL" },
  check_logs: { en: "Review logs", fa: "بررسی گزارش‌ها" },
  gather_evidence: { en: "Gather evidence", fa: "جمع‌آوری شواهد" },
  propose_fix: { en: "Propose a fix", fa: "پیشنهاد رفع اشکال" },
  stub: { en: "Planned action", fa: "اقدام برنامه‌ریزی‌شده" },
};

/**
 * Heuristic intent from the user goal (FA/EN keywords).
 * Used for stub steps before a plan body exists.
 */
export function inferGoalIntent(goal: string): GoalIntent {
  const g = goal.toLowerCase();
  if (
    /دامنه|domain|ssl|dns|irnic|cert|\.com\b|\.ir\b|connect\s+\S+\.(com|ir|net|org)/.test(g)
  ) {
    return "domain";
  }
  if (
    /اشکال|خطا|دیباگ|رفع|troubleshoot|debug|fix|incident|investigate|500|error|لاگ|log|bug/.test(
      g,
    )
  ) {
    return "troubleshoot";
  }
  if (/مانیتور|نگهداری|maintain|monitor|health|slow|منابع|resource|متریک/.test(g)) {
    return "maintain";
  }
  if (
    /استقرار|دیپلوی|deploy|release|انتشار|راه‌اندازی|setup|نصب|first deploy|اولین/.test(g)
  ) {
    return "deploy";
  }
  return "generic";
}

/** Human title for a plan step action — never prefer raw tool_id. */
export function labelPlanStepAction(action: string, language: Locale): string {
  const key = action.trim().toLowerCase();
  const mapped = ACTION_LABELS[key];
  if (mapped) return mapped[language];

  const cleaned = action
    .replace(/[_-]+/g, " ")
    .replace(/\bstub\b/gi, "")
    .replace(/\s+/g, " ")
    .trim();
  if (!cleaned) {
    return language === "fa" ? "گام طرح" : "Plan step";
  }
  if (language === "fa") return cleaned;
  return cleaned.replace(/\b\w/g, (ch) => ch.toUpperCase());
}

function stubPrepSteps(
  intent: GoalIntent,
  language: Locale,
): { tool: string; title: string }[] {
  const packs: Record<GoalIntent, { en: [string, string, string]; fa: [string, string, string] }> = {
    deploy: {
      en: ["Understand deploy request", "Check local project", "Draft deploy plan"],
      fa: ["درک درخواست استقرار", "بررسی پروژه محلی", "آماده‌سازی طرح استقرار"],
    },
    troubleshoot: {
      en: ["Understand the issue", "Gather clues", "Draft a fix plan"],
      fa: ["درک مشکل", "جمع‌آوری نشانه‌ها", "آماده‌سازی طرح رفع اشکال"],
    },
    domain: {
      en: ["Understand domain request", "Check domain readiness", "Draft domain plan"],
      fa: ["درک درخواست دامنه", "بررسی آمادگی دامنه", "آماده‌سازی طرح دامنه"],
    },
    maintain: {
      en: ["Understand maintain request", "Review health signals", "Draft maintain plan"],
      fa: ["درک درخواست نگهداری", "بررسی نشانه‌های سلامت", "آماده‌سازی طرح نگهداری"],
    },
    generic: {
      en: ["Understand your request", "Check workspace readiness", "Draft a plan"],
      fa: ["درک درخواست شما", "بررسی آمادگی فضای کار", "آماده‌سازی طرح"],
    },
  };
  const titles = packs[intent][language];
  return [
    { tool: "prep.understand", title: titles[0] },
    { tool: "prep.check", title: titles[1] },
    { tool: "prep.plan", title: titles[2] },
  ];
}

function readinessDetail(
  language: Locale,
  readiness: BuildRequestTimelineInput["readiness"],
): string {
  if (!readiness) {
    return language === "fa" ? "در حال بررسی…" : "Checking…";
  }
  if (readiness.ready) {
    return language === "fa" ? "آماده ادامه" : "Ready to continue";
  }
  const needs = readiness.open_needs
    .map((need) => need.replace(/[_-]+/g, " "))
    .filter(Boolean)
    .slice(0, 3)
    .join(language === "fa" ? "، " : ", ");
  if (needs) {
    return language === "fa" ? `نیازها: ${needs}` : `Needs: ${needs}`;
  }
  return language === "fa" ? "هنوز آماده نیست" : "Not ready yet";
}

function hitlLabels(language: Locale) {
  return language === "fa"
    ? {
        approve: "تأیید شما",
        approveWait: "در انتظار دکمه تأیید",
        approveDone: "تأیید شد",
        approveRejected: "رد شد — اجرایی انجام نشد",
        execute: "اجرای طرح",
        executeRun: "در حال اجرا…",
        executeDone: "اجرا انجام شد",
        verify: "بررسی نتیجه",
        verifyRun: "در حال بررسی…",
        planPending: "پس از تأیید اجرا می‌شود",
        planDone: "انجام شد",
        prepDone: "انجام شد",
        error: "خطا",
      }
    : {
        approve: "Your approval",
        approveWait: "Waiting for Approve",
        approveDone: "Approved",
        approveRejected: "Rejected — nothing executed",
        execute: "Run the plan",
        executeRun: "Running…",
        executeDone: "Finished running",
        verify: "Check the result",
        verifyRun: "Checking…",
        planPending: "Runs after you approve",
        planDone: "Done",
        prepDone: "Done",
        error: "Error",
      };
}

/**
 * Build the Inspector timeline for the active request.
 * Prefers `plan_body.steps` when present; otherwise intent-based stubs.
 */
export function buildRequestTimeline(input: BuildRequestTimelineInput): RequestTimelineStep[] {
  const { language, goal, stage, planBody, readiness, operationState, error } = input;
  const labels = hitlLabels(language);
  const intent = inferGoalIntent(goal);
  const errDetail = error?.trim() || labels.error;

  const markError = (steps: RequestTimelineStep[]): RequestTimelineStep[] => {
    if (stage !== "error") return steps;
    let marked = false;
    return steps.map((step) => {
      if (marked) return step;
      if (step.status === "pending" || step.status === "waiting") {
        marked = true;
        return { ...step, status: "error", detail: errDetail };
      }
      return step;
    }).map((step, index, all) => {
      if (marked) return step;
      if (index === all.length - 1) {
        return { ...step, status: "error", detail: errDetail };
      }
      return step;
    });
  };

  if (planBody?.steps?.length) {
    const planSteps: RequestTimelineStep[] = planBody.steps.map((step) => ({
      title: labelPlanStepAction(step.action, language),
      detail: labels.planPending,
      tool: `plan.${step.id}`,
      status: "pending" as const,
    }));

    const approve: RequestTimelineStep = {
      title: labels.approve,
      detail: labels.approveWait,
      tool: "hitl.approve",
      status: "waiting",
    };

    const execute: RequestTimelineStep = {
      title: labels.execute,
      detail: labels.executeRun,
      tool: "run.execute",
      status: "pending",
    };

    const verify: RequestTimelineStep = {
      title: labels.verify,
      detail: labels.verifyRun,
      tool: "run.verify",
      status: "pending",
    };

    if (stage === "awaiting_approval" || stage === "planning") {
      return markError([...planSteps, approve]);
    }

    if (stage === "rejected") {
      return [
        ...planSteps.map((step) => ({ ...step, status: "pending", detail: labels.planPending })),
        { ...approve, status: "rejected", detail: labels.approveRejected },
      ];
    }

    if (stage === "approving") {
      return markError([
        ...planSteps,
        { ...approve, status: "done", detail: labels.approveDone },
        { ...execute, status: "pending", detail: labels.executeRun },
      ]);
    }

    if (stage === "executing") {
      return markError([
        ...planSteps.map((step) => ({ ...step, status: "pending", detail: labels.executeRun })),
        { ...approve, status: "done", detail: labels.approveDone },
        { ...execute, status: "pending", detail: labels.executeRun },
      ]);
    }

    if (stage === "verifying") {
      return markError([
        ...planSteps.map((step) => ({ ...step, status: "done", detail: labels.planDone })),
        { ...approve, status: "done", detail: labels.approveDone },
        { ...execute, status: "done", detail: labels.executeDone },
        { ...verify, status: "pending", detail: labels.verifyRun },
      ]);
    }

    if (stage === "verified") {
      const stateDetail = operationState?.trim()
        ? language === "fa"
          ? `وضعیت: ${operationState}`
          : `State: ${operationState}`
        : labels.planDone;
      return [
        ...planSteps.map((step) => ({ ...step, status: "done", detail: labels.planDone })),
        { ...approve, status: "done", detail: labels.approveDone },
        { ...execute, status: "done", detail: labels.executeDone },
        { ...verify, status: "verified", detail: stateDetail },
      ];
    }

    if (stage === "error") {
      return markError([
        ...planSteps,
        { ...approve, status: "done", detail: labels.approveDone },
        { ...execute, status: "pending", detail: labels.executeRun },
        { ...verify, status: "pending", detail: labels.verifyRun },
      ]);
    }

    // assessing with a plan already present (restore) — treat like awaiting prep
    return markError([...planSteps, approve]);
  }

  // No plan yet — intent-based stubs for assessing / planning / early error
  const stubs = stubPrepSteps(intent, language);
  const [understand, check, draft] = stubs;

  const base: RequestTimelineStep[] = [
    {
      title: understand.title,
      detail: labels.prepDone,
      tool: understand.tool,
      status: "done",
    },
    {
      title: check.title,
      detail: readinessDetail(language, readiness),
      tool: check.tool,
      status: stage === "assessing" && !readiness ? "pending" : "done",
    },
    {
      title: draft.title,
      detail: language === "fa" ? "پس از بررسی" : "After readiness check",
      tool: draft.tool,
      status: "pending",
    },
  ];

  if (stage === "awaiting_intake") {
    base[1] = { ...base[1], status: "done", detail: readinessDetail(language, readiness) };
    base[2] = {
      title: language === "fa" ? "انتخاب سرویس / پلن / دامنه" : "Choose service / plan / domain",
      detail: language === "fa" ? "در انتظار انتخاب شما در چت" : "Waiting for your selection in chat",
      tool: "prep.intake",
      status: "waiting",
    };
    return markError(base);
  }

  if (readiness || stage === "planning") {
    base[1] = { ...base[1], status: "done", detail: readinessDetail(language, readiness) };
    base[2] = {
      ...base[2],
      status: "pending",
      detail: language === "fa" ? "در حال آماده‌سازی…" : "Preparing…",
    };
  } else {
    base[1] = { ...base[1], status: "pending", detail: readinessDetail(language, null) };
  }

  return markError(base);
}

/** Localized short status for Inspector chrome (not raw enum spam when avoidable). */
export function timelineStatusLabel(status: string, language: Locale): string {
  const map: Record<string, { en: string; fa: string }> = {
    pending: { en: "pending", fa: "در انتظار" },
    waiting: { en: "waiting", fa: "منتظر تأیید" },
    done: { en: "done", fa: "انجام شد" },
    verified: { en: "verified", fa: "تأیید شد" },
    rejected: { en: "rejected", fa: "رد شد" },
    error: { en: "error", fa: "خطا" },
  };
  return map[status]?.[language] ?? status;
}
