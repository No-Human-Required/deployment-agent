import type { ApprovalResult, OrchestratorRun, ViewPayload } from "./schemas";
import { viewPayloadSchema } from "./schemas";

type Locale = "en" | "fa";

const hitlRisk = {
  en: "Writes run only after you approve. Typing “approve” in chat is not authorization.",
  fa: "اجرای نوشتن فقط پس از تأیید صریح انجام می‌شود. نوشتن «تأیید» در گفتگو مجوز نیست.",
} as const;

export type MapOrchestratorCardsOptions = {
  /**
   * `inspector` — full internals (readiness, op ids, tool ids).
   * `chat` — plan + HITL approval only; no readiness dump / UUID / tool-id spam.
   */
  surface?: "chat" | "inspector";
};

/**
 * Map companion orchestrator session fields into GenUI ViewPayload cards.
 * HITL approve/reject stays on the approval card controls — never chat text.
 */
export function mapOrchestratorToCards(
  run: OrchestratorRun,
  language: Locale = "en",
  options: MapOrchestratorCardsOptions = {},
): ViewPayload[] {
  const surface = options.surface ?? "inspector";
  const forChat = surface === "chat";
  const cards: ViewPayload[] = [];

  if (run.readiness && !forChat) {
    cards.push(
      viewPayloadSchema.parse({
        type: "readiness_findings",
        data: {
          ready: run.readiness.ready,
          open_needs: run.readiness.open_needs,
          notes: run.readiness.notes ?? null,
          platform: run.readiness.platform ?? null,
          findings: run.readiness.findings,
        },
      }),
    );
  }

  // Troubleshoot / maintain GenUI — useful outcomes, not readiness dumps.
  if (run.evidence) {
    cards.push(
      viewPayloadSchema.parse({
        type: "evidence_pack",
        data: {
          version: run.evidence.version,
          project_name: run.evidence.project_name,
          symptom: run.evidence.symptom ?? null,
          collected_at: run.evidence.collected_at,
          facts: run.evidence.facts,
          gaps: run.evidence.gaps,
          sanitized_log_excerpts: forChat
            ? run.evidence.sanitized_log_excerpts.slice(0, 5)
            : run.evidence.sanitized_log_excerpts,
          complete: run.evidence.complete,
        },
      }),
    );
  }

  if (run.diagnosis) {
    cards.push(
      viewPayloadSchema.parse({
        type: "diagnosis",
        data: {
          version: run.diagnosis.version,
          evidence_version: run.diagnosis.evidence_version,
          created_at: run.diagnosis.created_at,
          summary: run.diagnosis.summary ?? null,
          insufficient_evidence: run.diagnosis.insufficient_evidence,
          hypotheses: run.diagnosis.hypotheses,
          data_gaps: run.diagnosis.data_gaps,
          next_read_or_question: run.diagnosis.next_read_or_question ?? null,
        },
      }),
    );
  }

  if (run.monitor) {
    cards.push(
      viewPayloadSchema.parse({
        type: "monitor_status",
        data: {
          monitor_id: forChat ? "monitor" : run.monitor.monitor_id,
          target: run.monitor.target,
          enabled: run.monitor.enabled,
          last_status: run.monitor.last_status,
          stale: run.monitor.stale,
          healthy_live: run.monitor.healthy_live,
          grants_write_permission: run.monitor.grants_write_permission,
          last_checked_at: run.monitor.last_checked_at ?? null,
          consecutive_misses: run.monitor.consecutive_misses,
        },
      }),
    );
  }

  if (run.plan_body) {
    cards.push(
      viewPayloadSchema.parse({
        type: "plan",
        data: {
          summary: run.plan_body.summary ?? run.summary,
          version: run.plan_body.version,
          steps: run.plan_body.steps.map((step) => ({
            id: step.id,
            action: step.action,
            tool_id: forChat ? null : (step.tool_id ?? null),
            effects: step.effects,
          })),
          effects: run.plan_body.effects,
          content_hash: forChat ? null : (run.content_hash ?? null),
          case_id: forChat ? null : run.case_id,
          plan_id: forChat ? null : (run.plan_id ?? null),
          target_platform: run.plan_body.target_platform ?? null,
        },
      }),
    );

    cards.push(
      viewPayloadSchema.parse({
        type: "approval",
        data: {
          action: run.plan_body.summary ?? run.summary,
          risk: hitlRisk[language],
          expires_at: run.approval?.expires_at ?? "",
          execution_id: run.plan_id ?? run.case_id,
        },
      }),
    );
  }

  if (run.operation && !forChat) {
    cards.push(
      viewPayloadSchema.parse({
        type: "operation_status",
        data: {
          operation_id: run.operation.id,
          state: run.operation.state,
          plan_id: run.operation.plan_id ?? run.plan_id ?? null,
          case_id: run.operation.case_id ?? run.case_id,
          fingerprints: run.operation.fingerprints,
        },
      }),
    );

    if (run.stage === "verified") {
      cards.push(
        viewPayloadSchema.parse({
          type: "verification_result",
          data: {
            operation_id: run.operation.id,
            state: run.operation.state,
            verified: true,
            summary: run.summary,
            mode: "LIVE",
          },
        }),
      );
    }
  }

  return cards;
}

/** Chat transcript cards: conversation + HITL only. */
export function mapOrchestratorToChatCards(
  run: OrchestratorRun,
  language: Locale = "en",
): ViewPayload[] {
  return mapOrchestratorToCards(run, language, { surface: "chat" });
}

/** Synthesize legacy ApprovalResult for GenerativeCard decision chrome. */
export function approvalResultFromRun(run: OrchestratorRun): ApprovalResult | null {
  if (run.stage === "awaiting_approval") return null;

  if (run.stage === "rejected" || run.stage === "stopped") {
    return {
      execution_id: run.plan_id ?? run.case_id,
      status: "rejected",
      message: run.summary,
      audit: run.events,
      result: null,
      mode: "LIVE",
    };
  }

  if (
    run.approval
    || run.stage === "approving"
    || run.stage === "executing"
    || run.stage === "verifying"
    || run.stage === "verified"
  ) {
    return {
      execution_id: run.approval?.approval_id ?? run.plan_id ?? run.case_id,
      status: "completed",
      message: run.summary,
      audit: run.events,
      result: null,
      mode: "LIVE",
    };
  }

  return null;
}

/** Fixture payloads for schema/UI coverage of companion card kinds not yet live-mapped. */
export const companionCardFixtures: ViewPayload[] = [
  viewPayloadSchema.parse({
    type: "evidence_pack",
    data: {
      version: "ev-20261023-demo",
      project_name: "demo-api",
      symptom: "HTTP 500 on /health",
      collected_at: "2026-10-23T10:00:00.000Z",
      facts: [
        { id: "f1", source: "logs", summary: "Unhandled TypeError in handler", stale: false },
      ],
      gaps: [{ source: "metrics", reason: "window empty", impact: "cannot rank load hypothesis" }],
      sanitized_log_excerpts: ["ERROR TypeError: x is not a function"],
      complete: false,
    },
  }),
  viewPayloadSchema.parse({
    type: "diagnosis",
    data: {
      version: "dx-20261023-demo",
      evidence_version: "ev-20261023-demo",
      created_at: "2026-10-23T10:01:00.000Z",
      summary: "Likely null callback in health route; evidence incomplete for deploy regression.",
      insufficient_evidence: true,
      hypotheses: [
        { id: "h1", rank: 1, statement: "Null callback passed to health handler" },
      ],
      data_gaps: [{ source: "events", reason: "no deploy events in window", impact: "cannot confirm regression" }],
      next_read_or_question: "Collect deploy events for the last hour",
    },
  }),
  viewPayloadSchema.parse({
    type: "dependency_plan",
    data: {
      version: "dep-1",
      summary: "App requires Postgres; create is gated.",
      required_kinds: ["database"],
      findings: [
        { kind: "database", code: "missing_database", message: "No DATABASE_URL", severity: "error" },
      ],
      create_database_enabled: false,
      create_disk_enabled: false,
      open_needs: ["approve_create_database"],
      can_claim_complete_success: false,
    },
  }),
  viewPayloadSchema.parse({
    type: "patch_diff",
    data: {
      summary: "Guard null callback in health route",
      rationale: "Evidence fact f1 points at TypeError in health handler",
      unified_diff: "--- a/src/health.ts\n+++ b/src/health.ts\n@@ -1 +1 @@\n-cb();\n+cb?.();\n",
      files_changed: ["src/health.ts"],
      content_hash: "patchhash01234567",
      sandbox_passed: true,
      ready_for_release: false,
      patch_record_approved: false,
      release_approved: false,
      open_needs: ["approve_patch_record"],
    },
  }),
  viewPayloadSchema.parse({
    type: "monitor_status",
    data: {
      monitor_id: "mon-1",
      target: "https://demo.liara.run/health",
      enabled: true,
      last_status: "miss",
      stale: true,
      healthy_live: false,
      grants_write_permission: false,
      last_checked_at: "2026-10-23T09:55:00.000Z",
      consecutive_misses: 3,
    },
  }),
  viewPayloadSchema.parse({
    type: "incident",
    data: {
      incident_id: "inc-1",
      status: "open",
      title: "Health check misses",
      alert_count: 3,
      write_authorized: false,
      monitor_id: "mon-1",
      case_id: null,
      opened_at: "2026-10-23T09:56:00.000Z",
    },
  }),
];
