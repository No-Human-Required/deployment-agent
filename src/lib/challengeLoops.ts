/**
 * Challenge.md capability loops through the cleaned chat UX.
 * Inventory + routing helpers — keeps deploy/ops/domain on intake+HITL,
 * and routes maintain/troubleshoot away from the deploy stub plan.
 */

import { resolveIntakeKind, type IntakeKind } from "./intake";
import { inferGoalIntent, type GoalIntent } from "./requestTimeline";

export type ChallengeArea =
  | "setup_deploy"
  | "ops"
  | "monitor_maintain"
  | "troubleshoot"
  | "domains";

export type ChallengeLoopRoute =
  | { area: ChallengeArea; mode: "intake"; intakeKind: IntakeKind; projectHint?: string }
  | { area: ChallengeArea; mode: "troubleshoot"; projectName: string }
  | { area: ChallengeArea; mode: "maintain_monitor"; target: string }
  | { area: ChallengeArea; mode: "generic_plan" }
  | { mode: "conversation" };

/** Greetings / short chit-chat — reply in chat; do not draft a deploy plan. */
export function isConversationalGoal(goal: string): boolean {
  const text = goal.trim();
  if (!text) return true;
  if (
    /^(سلام|درود|هی|هِی|صبح بخیر|عصر بخیر|شب خوش|hi+|hello|hey|yo|sup)([\s!.?؟…]*)$/iu.test(
      text,
    )
  ) {
    return true;
  }
  const intent = inferGoalIntent(text);
  if (intent !== "generic") return false;
  // Short generic prompts without ops keywords stay conversational.
  if (text.length > 80) return false;
  return !/(deploy|دیپلوی|دپلوی|استقرار|سرویس|پروژه|دامنه|domain|لاگ|log|خطا|error|500|restart|resize|پایش|monitor|عیب|debug|troubleshoot)/i.test(
    text,
  );
}

export type ChallengeLoopCatalogEntry = {
  area: ChallengeArea;
  title: string;
  shellEntry: string;
  clientApis: string[];
  hitlWrites: boolean;
};

/** Static inventory for evidence matrix / docs. */
export const CHALLENGE_LOOP_CATALOG: ChallengeLoopCatalogEntry[] = [
  {
    area: "setup_deploy",
    title: "Initial setup & first deploy",
    shellEntry: "Chat goal (deploy/setup) or suggestion cards → GenUI intake → create_plan(deploy+app_path) → HITL",
    clientApis: [
      "POST /api/orchestrator/cases",
      "POST /api/orchestrator/assess_readiness",
      "POST /api/orchestrator/create_plan (deploy)",
      "POST /api/orchestrator/approve_plan",
      "POST /api/orchestrator/execute_plan",
    ],
    hitlWrites: true,
  },
  {
    area: "ops",
    title: "Deployment & operations (resize / restart via plan)",
    shellEntry: "Chat resize/ops goal → GenUI intake → create_plan(ops) → HITL",
    clientApis: [
      "POST /api/orchestrator/create_plan (ops.resize|restart|env)",
      "POST /api/orchestrator/approve_plan",
      "POST /api/orchestrator/execute_plan",
    ],
    hitlWrites: true,
  },
  {
    area: "monitor_maintain",
    title: "Monitoring & maintenance",
    shellEntry:
      "Monitoring nav (GET incidents) + CTA → chat enable-monitor → POST /api/maintain/monitors/enable (≠ write auth); recovery still HITL",
    clientApis: [
      "GET /api/maintain/incidents",
      "GET /api/maintain/audit",
      "POST /api/maintain/monitors/enable",
      "POST /api/maintain/recovery/plan (HITL via approve+execute)",
    ],
    hitlWrites: false,
  },
  {
    area: "troubleshoot",
    title: "Intelligent troubleshooting",
    shellEntry:
      "My Services Investigate / chat debug goal → collect_evidence → diagnose → propose_fix → create_plan_from_fix → HITL",
    clientApis: [
      "POST /api/orchestrator/collect_evidence",
      "POST /api/orchestrator/diagnose",
      "POST /api/orchestrator/propose_fix_options",
      "POST /api/orchestrator/create_plan_from_fix",
      "POST /api/orchestrator/approve_plan",
    ],
    hitlWrites: true,
  },
  {
    area: "domains",
    title: "Domains list + HITL attach",
    shellEntry: "Domains nav GET list; CTA → chat domain intake → create_plan(ops.domain) → HITL",
    clientApis: [
      "GET /api/liara/domains",
      "POST /api/orchestrator/create_plan (ops.domain)",
      "POST /api/orchestrator/approve_plan",
    ],
    hitlWrites: true,
  },
];

/** Words that look like service names but are intent nouns (e.g. "service health"). */
const PROJECT_NAME_STOPWORDS = new Set([
  "health",
  "status",
  "logs",
  "log",
  "error",
  "errors",
  "monitor",
  "domain",
  "ssl",
  "deploy",
  "deployment",
  "release",
  "plan",
  "سلامت",
  "وضعیت",
  "لاگ",
  "خطا",
  "دامنه",
  "استقرار",
]);

/**
 * Pull a Liara project/service name from common shell CTA / chat phrasings.
 */
export function extractProjectNameFromGoal(goal: string): string | null {
  const text = goal.trim();
  const patterns: RegExp[] = [
    /Investigate service\s+([^\s,]+)/i,
    /بررسی وضعیت سرویس\s+([^\s,]+)/i,
    /Attach a custom domain to service\s+([^\s,]+)/i,
    /دامنه سفارشی را به سرویس\s+([^\s,]+)\s+وصل/i,
    /(?:service|سرویس|project|پروژه)\s+([a-z0-9][\w.-]{0,127})/i,
  ];
  for (const pattern of patterns) {
    const match = text.match(pattern);
    const name = match?.[1]?.replace(/[؟?!.،,]+$/u, "").trim();
    if (!name) continue;
    if (PROJECT_NAME_STOPWORDS.has(name.toLowerCase())) continue;
    return name;
  }
  return null;
}

export function challengeAreaForIntent(intent: GoalIntent): ChallengeArea | null {
  switch (intent) {
    case "deploy":
      return "setup_deploy";
    case "domain":
      return "domains";
    case "troubleshoot":
      return "troubleshoot";
    case "maintain":
      return "monitor_maintain";
    default:
      return null;
  }
}

/**
 * Decide how the cleaned shell should continue after readiness.
 * Prefer explicit project hints (nav Investigate / selected service) over intake.
 */
export function resolveChallengeLoopRoute(
  goal: string,
  options?: { selectedServiceId?: string | null },
): ChallengeLoopRoute {
  if (isConversationalGoal(goal)) {
    return { mode: "conversation" };
  }

  const intent = inferGoalIntent(goal);
  const projectHint =
    extractProjectNameFromGoal(goal) || options?.selectedServiceId?.trim() || undefined;

  const intakeKind = resolveIntakeKind(goal);
  if (intakeKind === "domain") {
    return { area: "domains", mode: "intake", intakeKind, projectHint };
  }
  if (intakeKind === "ops_resize") {
    return { area: "ops", mode: "intake", intakeKind, projectHint };
  }
  if (intakeKind === "deploy") {
    return { area: "setup_deploy", mode: "intake", intakeKind, projectHint };
  }

  if (intent === "troubleshoot") {
    if (projectHint) {
      return { area: "troubleshoot", mode: "troubleshoot", projectName: projectHint };
    }
    return { area: "troubleshoot", mode: "intake", intakeKind: "troubleshoot" };
  }

  if (intent === "maintain") {
    if (projectHint) {
      return { area: "monitor_maintain", mode: "maintain_monitor", target: projectHint };
    }
    return { area: "monitor_maintain", mode: "intake", intakeKind: "maintain_monitor" };
  }

  const area = challengeAreaForIntent(intent) ?? "setup_deploy";
  return { area, mode: "generic_plan" };
}

export function catalogEntry(area: ChallengeArea): ChallengeLoopCatalogEntry {
  const row = CHALLENGE_LOOP_CATALOG.find((entry) => entry.area === area);
  if (!row) {
    throw new Error(`Unknown challenge area: ${area}`);
  }
  return row;
}
