import { z } from "zod";

const stepSchema = z.object({
  title: z.string(),
  detail: z.string(),
  tool: z.string(),
  status: z.string(),
});

const logSchema = z.object({
  time: z.string(),
  level: z.string(),
  message: z.string(),
  source: z.string(),
});

const metricSchema = z.object({
  name: z.string(),
  value: z.number(),
  unit: z.string(),
  change: z.string(),
  tone: z.string(),
});

export const modeSchema = z.enum(["LIVE", "DEMO", "UNCONFIGURED"]);

export const serviceSchema = z.object({
  id: z.string(),
  name: z.string(),
  app_type: z.string(),
  region: z.string(),
  status: z.string(),
  url: z.string(),
  uptime: z.string(),
});

/** Companion-aligned GenUI step row (plan card). */
const genuiPlanStepSchema = z.object({
  id: z.string(),
  action: z.string(),
  tool_id: z.string().nullable().optional(),
  effects: z.array(z.string()).default([]),
});

const genuiFindingSchema = z.object({
  code: z.string(),
  message: z.string(),
  severity: z.string().default("error"),
  evidence_paths: z.array(z.string()).default([]),
});

/** Strict allowlist of GenerativeCard types (unknown → viewPayloadSchema fallback). */
export const knownViewPayloadSchema = z.discriminatedUnion("type", [
  z.object({
    type: z.literal("service_status"),
    data: z.object({ name: z.string(), status: z.string(), url: z.string(), mode: z.string() }),
  }),
  z.object({
    type: z.literal("deployment_progress"),
    data: z.object({ version: z.string(), progress: z.number(), status: z.string() }),
  }),
  z.object({
    type: z.literal("timeline"),
    data: z.object({ steps: z.array(stepSchema), status: z.string() }),
  }),
  z.object({
    type: z.literal("tool_call"),
    data: z.object({ tools: z.array(stepSchema), mode: z.string() }),
  }),
  z.object({
    type: z.literal("log_viewer"),
    data: z.object({ logs: z.array(logSchema), mode: z.string() }),
  }),
  z.object({
    type: z.literal("metric"),
    data: z.object({ metrics: z.array(metricSchema), mode: z.string() }),
  }),
  z.object({
    type: z.literal("error_analysis"),
    data: z.object({ title: z.string(), summary: z.string(), evidence: z.array(z.string()) }),
  }),
  z.object({
    type: z.literal("root_cause"),
    data: z.object({
      title: z.string(),
      confidence: z.string(),
      description: z.string(),
      evidence: z.array(z.string()),
    }),
  }),
  z.object({
    type: z.literal("plan"),
    data: z.object({
      summary: z.string().nullable().optional(),
      version: z.number().int().positive().optional(),
      steps: z.array(genuiPlanStepSchema).default([]),
      effects: z.array(z.string()).default([]),
      content_hash: z.string().nullable().optional(),
      case_id: z.string().nullable().optional(),
      plan_id: z.string().nullable().optional(),
      target_platform: z.string().nullable().optional(),
    }),
  }),
  z.object({
    type: z.literal("approval"),
    data: z.object({
      action: z.string(),
      risk: z.string(),
      expires_at: z.string(),
      execution_id: z.string(),
    }),
  }),
  z.object({
    type: z.literal("readiness_findings"),
    data: z.object({
      ready: z.boolean(),
      open_needs: z.array(z.string()).default([]),
      notes: z.string().nullable().optional(),
      platform: z.string().nullable().optional(),
      findings: z.array(genuiFindingSchema).default([]),
    }),
  }),
  z.object({
    type: z.literal("evidence_pack"),
    data: z.object({
      version: z.string().min(1),
      project_name: z.string().min(1),
      symptom: z.string().nullable().optional(),
      collected_at: z.string(),
      facts: z
        .array(
          z.object({
            id: z.string(),
            source: z.string(),
            summary: z.string(),
            stale: z.boolean().default(false),
          }),
        )
        .default([]),
      gaps: z
        .array(
          z.object({
            source: z.string(),
            reason: z.string(),
            impact: z.string(),
          }),
        )
        .default([]),
      sanitized_log_excerpts: z.array(z.string()).default([]),
      complete: z.boolean().default(false),
    }),
  }),
  z.object({
    type: z.literal("diagnosis"),
    data: z.object({
      version: z.string().min(1),
      evidence_version: z.string().min(1),
      created_at: z.string(),
      summary: z.string().nullable().optional(),
      insufficient_evidence: z.boolean().default(false),
      hypotheses: z
        .array(
          z.object({
            id: z.string(),
            rank: z.number().int().positive(),
            statement: z.string(),
          }),
        )
        .default([]),
      data_gaps: z
        .array(
          z.object({
            source: z.string(),
            reason: z.string(),
            impact: z.string(),
          }),
        )
        .default([]),
      next_read_or_question: z.string().nullable().optional(),
    }),
  }),
  z.object({
    type: z.literal("dependency_plan"),
    data: z.object({
      version: z.string().min(1),
      summary: z.string().nullable().optional(),
      required_kinds: z.array(z.string()).default([]),
      findings: z
        .array(
          z.object({
            kind: z.string(),
            code: z.string(),
            message: z.string(),
            severity: z.string().default("error"),
          }),
        )
        .default([]),
      create_database_enabled: z.boolean().default(false),
      create_disk_enabled: z.boolean().default(false),
      open_needs: z.array(z.string()).default([]),
      can_claim_complete_success: z.boolean().default(false),
    }),
  }),
  z.object({
    type: z.literal("patch_diff"),
    data: z.object({
      summary: z.string().nullable().optional(),
      rationale: z.string().min(1),
      unified_diff: z.string().min(1),
      files_changed: z.array(z.string()).default([]),
      content_hash: z.string().min(8),
      sandbox_passed: z.boolean().nullable().optional(),
      ready_for_release: z.boolean().default(false),
      patch_record_approved: z.boolean().default(false),
      release_approved: z.boolean().default(false),
      open_needs: z.array(z.string()).default([]),
    }),
  }),
  z.object({
    type: z.literal("monitor_status"),
    data: z.object({
      monitor_id: z.string().min(1),
      target: z.string().min(1),
      enabled: z.boolean(),
      last_status: z.string(),
      stale: z.boolean().default(false),
      healthy_live: z.boolean().default(false),
      grants_write_permission: z.boolean().default(false),
      last_checked_at: z.string().nullable().optional(),
      consecutive_misses: z.number().int().nonnegative().default(0),
    }),
  }),
  z.object({
    type: z.literal("incident"),
    data: z.object({
      incident_id: z.string().min(1),
      status: z.string(),
      title: z.string().min(1),
      alert_count: z.number().int().positive().default(1),
      write_authorized: z.boolean().default(false),
      monitor_id: z.string().nullable().optional(),
      case_id: z.string().nullable().optional(),
      opened_at: z.string().nullable().optional(),
    }),
  }),
  z.object({
    type: z.literal("operation_status"),
    data: z.object({
      operation_id: z.string().min(1),
      state: z.string(),
      plan_id: z.string().nullable().optional(),
      case_id: z.string().nullable().optional(),
      fingerprints: z.array(z.string()).default([]),
    }),
  }),
  z.object({
    type: z.literal("verification_result"),
    data: z.object({
      operation_id: z.string().min(1),
      state: z.string(),
      verified: z.boolean(),
      summary: z.string().nullable().optional(),
      mode: z.string().optional(),
    }),
  }),
  z.object({
    type: z.literal("operation_result"),
    data: z.object({
      action: z.string(),
      service: z.string(),
      operation_id: z.string(),
      result: z.string(),
      verified_at: z.string(),
      mode: z.string(),
    }),
  }),
  z.object({
    type: z.literal("service_health"),
    data: z.object({ status: z.string(), uptime: z.string(), mode: z.string() }),
  }),
  /** In-chat GenUI intake before createPlan (service / plan / platform / domain). */
  z.object({
    type: z.literal("intake"),
    data: z.object({
      kind: z.enum(["deploy", "ops_resize", "domain", "troubleshoot", "maintain_monitor"]),
      title: z.string().min(1),
      prompt: z.string().nullable().optional(),
      services: z
        .array(
          z.object({
            id: z.string().min(1),
            name: z.string().min(1),
            status: z.string().optional(),
          }),
        )
        .default([]),
      plans: z
        .array(
          z.object({
            id: z.string().min(1),
            label: z.string().min(1),
            hint: z.string().nullable().optional(),
            price_monthly: z.number().nullable().optional(),
            ram_gb: z.number().nullable().optional(),
            tier: z.number().int().positive().optional(),
          }),
        )
        .default([]),
      platforms: z
        .array(
          z.object({
            id: z.string().min(1),
            label: z.string().min(1),
            hint: z.string().nullable().optional(),
            icon: z.string().nullable().optional(),
          }),
        )
        .default([]),
      require_plan: z.boolean().default(false),
      require_domain: z.boolean().default(false),
      require_platform: z.boolean().default(false),
      suggested_platform: z.string().nullable().optional(),
      suggested_service_name: z.string().nullable().optional(),
      prefer_new_service: z.boolean().default(false),
      load_error: z.string().nullable().optional(),
      settings_cta: z.boolean().default(false),
    }),
  }),
]);

export const viewPayloadSchema = z.union([
  knownViewPayloadSchema,
  z.object({
    type: z.string(),
    data: z.record(z.string(), z.unknown()),
  }).transform((payload) => ({
    type: "unsupported" as const,
    data: { originalType: payload.type },
  })),
]);

export const investigationSchema = z.object({
  execution_id: z.string(),
  status: z.enum(["awaiting_approval", "rejected", "completed"]),
  service: serviceSchema,
  summary: z.string(),
  probable_cause: z.string(),
  evidence: z.array(z.string()),
  timeline: z.array(stepSchema),
  logs: z.array(logSchema),
  metrics: z.array(metricSchema),
  components: z.array(viewPayloadSchema),
  mode: modeSchema,
});

export const operationResultSchema = z.object({
  action: z.string(),
  service: z.string(),
  operation_id: z.string(),
  result: z.string(),
  verified_at: z.string(),
  mode: modeSchema,
});

export const approvalResultSchema = z.object({
  execution_id: z.string(),
  status: z.enum(["rejected", "completed"]),
  message: z.string(),
  audit: z.array(z.object({ time: z.string(), event: z.string(), actor: z.string() })),
  result: operationResultSchema.nullable(),
  mode: modeSchema,
});

/** Companion `apps/agent` redacted settings — nested liara + aval; never raw secrets. */
export const settingsViewSchema = z.object({
  workspace_id: z.string(),
  liara: z.object({
    api_base_url: z.string(),
    team_id: z.string().nullable(),
    token_configured: z.boolean(),
    token_label: z.string().nullable(),
  }),
  aval: z.object({
    base_url: z.string().nullable(),
    model: z.string().nullable(),
    api_key_configured: z.boolean(),
    api_key_label: z.string().nullable(),
  }),
});

/** Public project rows from `POST /api/liara/prove-read` (live services catalog). */
export const liaraProjectSummarySchema = z.object({
  project_id: z.union([z.string(), z.number()]).nullable().optional(),
  type: z.string().nullable().optional(),
  status: z.string().nullable().optional(),
  isDeployed: z.boolean().nullable().optional(),
});

export const proveLiaraReadSchema = z.object({
  ok: z.boolean(),
  me: z.record(z.string(), z.unknown()).optional(),
  project_count: z.number(),
  projects: z.array(liaraProjectSummarySchema).optional(),
  registry: z
    .object({
      tool_id: z.string(),
      status: z.string(),
      updated: z.boolean(),
    })
    .optional(),
});

/** Selectable PaaS plan rows from `GET /api/liara/plans` (account catalog, not release history). */
export const liaraPlanSchema = z.object({
  id: z.string(),
  label: z.string(),
  hint: z.string().nullable().optional(),
  available: z.boolean().optional(),
  region: z.string().nullable().optional(),
  price_monthly: z.number().nullable().optional(),
  ram_gb: z.number().nullable().optional(),
  tier: z.number().int().positive().optional(),
});

export const liaraPlansResultSchema = z.object({
  plans: z.array(liaraPlanSchema),
  source: z.string().optional(),
});

/** Domain rows from `GET /api/liara/domains` (read-only list for a project). */
export const liaraDomainSchema = z.object({
  id: z.string(),
  name: z.string(),
  status: z.string().nullable().optional(),
  certificates_status: z.string().nullable().optional(),
  project: z.string().nullable().optional(),
  type: z.string().nullable().optional(),
  cname_record: z.string().nullable().optional(),
});

export const liaraDomainsResultSchema = z.object({
  domains: z.array(liaraDomainSchema),
  project: z.string(),
  source: z.string().optional(),
});

/** Maintain incident card from `GET /api/maintain/incidents`. */
export const maintainIncidentSchema = z.object({
  incident_id: z.string(),
  monitor_id: z.string().nullable().optional(),
  case_id: z.string().nullable().optional(),
  status: z.string(),
  title: z.string(),
  alert_count: z.number().int().nonnegative().default(1),
  dedupe_key: z.string().optional(),
  write_authorized: z.boolean().optional(),
  opened_at: z.string().nullable().optional(),
  resolved_at: z.string().nullable().optional(),
});

export const maintainIncidentsResultSchema = z.object({
  incidents: z.array(maintainIncidentSchema),
});

/** Sanitized audit row from `GET /api/maintain/audit`. */
export const maintainAuditEventSchema = z.object({
  id: z.string(),
  event_type: z.string(),
  actor: z.string().nullable().optional(),
  case_id: z.string().nullable().optional(),
  created_at: z.string().nullable().optional(),
  payload: z.record(z.string(), z.unknown()).optional(),
});

export const maintainAuditResultSchema = z.object({
  events: z.array(maintainAuditEventSchema),
});

export const healthSchema = z.object({
  status: z.string(),
});

export const readySchema = z.object({
  status: z.string(),
  database: z.boolean(),
});

/** Companion orchestrator — case create response. */
export const orchestratorCaseSchema = z.object({
  id: z.string().uuid(),
  workspace_id: z.string().uuid(),
  goal: z.string(),
});

export const findingPayloadSchema = z.object({
  code: z.string(),
  message: z.string(),
  evidence_paths: z.array(z.string()).default([]),
  severity: z.string().default("error"),
});

export const readinessAssessmentSchema = z.object({
  ready: z.boolean(),
  open_needs: z.array(z.string()).default([]),
  notes: z.string().nullable().optional(),
  platform: z.string().nullable().optional(),
  package_name: z.string().nullable().optional(),
  findings: z.array(findingPayloadSchema).default([]),
  detected_port: z.number().nullable().optional(),
  start_script: z.string().nullable().optional(),
});

export const planStepSchema = z.object({
  id: z.string(),
  action: z.string(),
  tool_id: z.string().nullable().optional(),
  effects: z.array(z.string()).default([]),
  cost_known: z.boolean().default(false),
  cost_estimate: z.string().nullable().optional(),
  params: z.record(z.string(), z.unknown()).default({}),
});

export const planVersionSchema = z.object({
  version: z.number().int().positive(),
  steps: z.array(planStepSchema).min(1),
  effects: z.array(z.string()).default([]),
  cost_known: z.boolean().default(false),
  cost_summary: z.string().nullable().optional(),
  summary: z.string().nullable().optional(),
  target_platform: z.string().nullable().optional(),
});

export const createPlanResultSchema = z.object({
  plan_id: z.string().uuid(),
  version: z.number().int().positive(),
  content_hash: z.string().min(8),
  body: planVersionSchema,
});

export const approvePlanResultSchema = z.object({
  approval_id: z.string().uuid(),
  plan_id: z.string().uuid(),
  plan_hash: z.string().min(8),
  status: z.string(),
  expires_at: z.string().nullable().optional(),
  scope: z.record(z.string(), z.unknown()).optional(),
});

export const operationPayloadSchema = z.object({
  id: z.string().uuid(),
  state: z.string(),
  fingerprints: z.array(z.string()).default([]),
  client_request_id: z.string().nullable().optional(),
  plan_id: z.string().uuid().nullable().optional(),
  case_id: z.string().uuid().nullable().optional(),
  checkpoint: z.record(z.string(), z.unknown()).nullable().optional(),
});

export const orchestratorStageSchema = z.enum([
  "assessing",
  "planning",
  "awaiting_intake",
  "awaiting_approval",
  "approving",
  "executing",
  "verifying",
  "verified",
  "rejected",
  "stopped",
  "error",
]);

/** Pending GenUI intake fields before create_plan (client session). */
export const orchestratorIntakeSchema = z.object({
  kind: z.enum(["deploy", "ops_resize", "domain", "troubleshoot", "maintain_monitor"]),
  services: z
    .array(
      z.object({
        id: z.string().min(1),
        name: z.string().min(1),
        status: z.string().optional(),
      }),
    )
    .default([]),
  plans: z
    .array(
      z.object({
        id: z.string().min(1),
        label: z.string().min(1),
        hint: z.string().nullable().optional(),
        price_monthly: z.number().nullable().optional(),
        ram_gb: z.number().nullable().optional(),
        tier: z.number().int().positive().optional(),
      }),
    )
    .default([]),
  platforms: z
    .array(
      z.object({
        id: z.string().min(1),
        label: z.string().min(1),
        hint: z.string().nullable().optional(),
        icon: z.string().nullable().optional(),
      }),
    )
    .default([]),
  require_plan: z.boolean().default(false),
  require_domain: z.boolean().default(false),
  require_platform: z.boolean().default(false),
  suggested_platform: z.string().nullable().optional(),
  suggested_service_name: z.string().nullable().optional(),
  prefer_new_service: z.boolean().default(false),
  load_error: z.string().nullable().optional(),
});

/** Evidence pack from `POST /api/orchestrator/collect_evidence`. */
export const evidencePackSchema = z.object({
  version: z.string().min(1),
  project_name: z.string().min(1),
  symptom: z.string().nullable().optional(),
  collected_at: z.string(),
  facts: z
    .array(
      z.object({
        id: z.string(),
        source: z.string(),
        summary: z.string(),
        stale: z.boolean().default(false),
      }),
    )
    .default([]),
  gaps: z
    .array(
      z.object({
        source: z.string(),
        reason: z.string(),
        impact: z.string(),
      }),
    )
    .default([]),
  sanitized_log_excerpts: z.array(z.string()).default([]),
  complete: z.boolean().default(false),
});

/** Diagnosis from `POST /api/orchestrator/diagnose`. */
export const diagnosisSchema = z.object({
  version: z.string().min(1),
  evidence_version: z.string().min(1),
  created_at: z.string(),
  summary: z.string().nullable().optional(),
  insufficient_evidence: z.boolean().default(false),
  hypotheses: z
    .array(
      z.object({
        id: z.string(),
        rank: z.number().int().positive(),
        statement: z.string(),
      }),
    )
    .default([]),
  data_gaps: z
    .array(
      z.object({
        source: z.string(),
        reason: z.string(),
        impact: z.string(),
      }),
    )
    .default([]),
  next_read_or_question: z.string().nullable().optional(),
});

/** Fix options from `POST /api/orchestrator/propose_fix_options`. */
export const fixOptionsPayloadSchema = z.object({
  diagnosis_version: z.string(),
  evidence_version: z.string(),
  options: z
    .array(
      z.object({
        id: z.string().min(1),
        tool_id: z.string().min(1),
        label: z.string().min(1),
        rationale: z.string().min(1),
        enabled: z.boolean().default(false),
        disabled_reason: z.string().nullable().optional(),
        verification_method: z.string().optional(),
        params: z.record(z.string(), z.unknown()).default({}),
      }),
    )
    .default([]),
  open_needs: z.array(z.string()).default([]),
});

/** Monitor status from `POST /api/maintain/monitors/enable`. */
export const monitorStatusSchema = z.object({
  monitor_id: z.string().min(1),
  target: z.string().min(1),
  enabled: z.boolean(),
  last_status: z.string().default("never"),
  stale: z.boolean().default(false),
  healthy_live: z.boolean().default(false),
  grants_write_permission: z.boolean().default(false),
  last_checked_at: z.string().nullable().optional(),
  consecutive_misses: z.number().int().nonnegative().default(0),
});

const timelineEventSchema = z.object({
  title: z.string(),
  detail: z.string(),
  tool: z.string(),
  status: z.string(),
});

const auditEventSchema = z.object({
  time: z.string(),
  event: z.string(),
  actor: z.string(),
});

/**
 * Client-side orchestrator session for chat + Inspector.
 * Propose ≠ execute: stage stays `awaiting_approval` until explicit Approve control.
 * Intake (service/plan/domain) may precede plan drafting when intent requires it.
 */
export const orchestratorRunSchema = z.object({
  case_id: z.string().uuid(),
  workspace_id: z.string().uuid(),
  goal: z.string(),
  stage: orchestratorStageSchema,
  summary: z.string(),
  readiness: readinessAssessmentSchema.nullable().optional(),
  intake: orchestratorIntakeSchema.nullable().optional(),
  evidence: evidencePackSchema.nullable().optional(),
  diagnosis: diagnosisSchema.nullable().optional(),
  fix_options: fixOptionsPayloadSchema.nullable().optional(),
  monitor: monitorStatusSchema.nullable().optional(),
  plan_id: z.string().uuid().nullable().optional(),
  plan_version: z.number().int().positive().nullable().optional(),
  content_hash: z.string().nullable().optional(),
  plan_body: planVersionSchema.nullable().optional(),
  approval: approvePlanResultSchema.nullable().optional(),
  operation: operationPayloadSchema.nullable().optional(),
  timeline: z.array(timelineEventSchema).default([]),
  events: z.array(auditEventSchema).default([]),
  error: z.string().nullable().optional(),
});

export type ViewPayload = z.infer<typeof viewPayloadSchema>;
export type Investigation = z.infer<typeof investigationSchema>;
export type ApprovalResult = z.infer<typeof approvalResultSchema>;
export type SettingsView = z.infer<typeof settingsViewSchema>;
export type ProveLiaraReadResult = z.infer<typeof proveLiaraReadSchema>;
export type LiaraPlan = z.infer<typeof liaraPlanSchema>;
export type LiaraPlansResult = z.infer<typeof liaraPlansResultSchema>;
export type LiaraDomain = z.infer<typeof liaraDomainSchema>;
export type LiaraDomainsResult = z.infer<typeof liaraDomainsResultSchema>;
export type MaintainIncident = z.infer<typeof maintainIncidentSchema>;
export type MaintainAuditEvent = z.infer<typeof maintainAuditEventSchema>;
export type EvidencePack = z.infer<typeof evidencePackSchema>;
export type Diagnosis = z.infer<typeof diagnosisSchema>;
export type FixOptionsPayload = z.infer<typeof fixOptionsPayloadSchema>;
export type MonitorStatus = z.infer<typeof monitorStatusSchema>;
export type OrchestratorCase = z.infer<typeof orchestratorCaseSchema>;
export type ReadinessAssessment = z.infer<typeof readinessAssessmentSchema>;
export type CreatePlanResult = z.infer<typeof createPlanResultSchema>;
export type ApprovePlanResult = z.infer<typeof approvePlanResultSchema>;
export type OperationPayload = z.infer<typeof operationPayloadSchema>;
export type OrchestratorRun = z.infer<typeof orchestratorRunSchema>;
export type OrchestratorStage = z.infer<typeof orchestratorStageSchema>;
export type PlanVersion = z.infer<typeof planVersionSchema>;
export type PlanStep = z.infer<typeof planStepSchema>;
