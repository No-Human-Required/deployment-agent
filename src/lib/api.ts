import { z } from "zod";
import {
  approvePlanResultSchema,
  createPlanResultSchema,
  diagnosisSchema,
  evidencePackSchema,
  fixOptionsPayloadSchema,
  healthSchema,
  liaraDomainsResultSchema,
  liaraPlansResultSchema,
  liaraProjectMonitoringSchema,
  liaraProjectSummarySchema,
  maintainAuditResultSchema,
  maintainIncidentsResultSchema,
  monitorStatusSchema,
  operationPayloadSchema,
  orchestratorCaseSchema,
  proveLiaraReadSchema,
  readinessAssessmentSchema,
  readySchema,
  serviceSchema,
  settingsViewSchema,
  type ApprovePlanResult,
  type CreatePlanResult,
  type Diagnosis,
  type EvidencePack,
  type FixOptionsPayload,
  type LiaraDomain,
  type LiaraPlan,
  type LiaraProjectMonitoring,
  type MaintainAuditEvent,
  type MaintainIncident,
  type MonitorStatus,
  type OperationPayload,
  type OrchestratorCase,
  type ProveLiaraReadResult,
  type ReadinessAssessment,
  type SettingsView,
} from "./schemas";
import { assessReadinessPayload } from "./quietChat";
import { sortPlansWeakToStrong } from "./sortPlans";

export type Service = z.infer<typeof serviceSchema>;

export type SettingsUpdateBody = {
  workspace_id?: string;
  liara_api_base_url?: string;
  /** Pass empty string to clear team id (companion contract). */
  liara_team_id?: string;
  /** Raw token — accepted once; never returned on GET. */
  liara_api_token?: string;
  llm_base_url?: string;
  llm_model?: string;
  /** Raw Aval key — accepted once; never returned on GET. */
  llm_api_key?: string;
};

function formatDetail(body: unknown, status: number): string {
  if (typeof body === "object" && body !== null && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (typeof detail === "object" && detail !== null) {
      if ("message" in detail && typeof (detail as { message: unknown }).message === "string") {
        return (detail as { message: string }).message;
      }
      try {
        return JSON.stringify(detail);
      } catch {
        return `درخواست ناموفق بود (کد ${status})`;
      }
    }
  }
  return `درخواست ناموفق بود (کد ${status})`;
}

async function request(path: string, init?: RequestInit): Promise<unknown> {
  const response = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => ({}));
    throw new Error(formatDetail(body, response.status));
  }
  if (response.status === 204) return null;
  return response.json();
}

function projectsToServices(projects: z.infer<typeof liaraProjectSummarySchema>[]): Service[] {
  return projects
    .map((project) => {
      const id = project.project_id != null ? String(project.project_id) : "";
      if (!id) return null;
      const status =
        project.status != null && String(project.status).length > 0
          ? String(project.status)
          : project.isDeployed
            ? "deployed"
            : "unknown";
      return serviceSchema.parse({
        id,
        name: id,
        app_type: project.type != null ? String(project.type) : "unknown",
        region: "—",
        status,
        url: "",
        uptime: "—",
      });
    })
    .filter((row): row is Service => row !== null);
}

const pickPathResultSchema = z.object({
  path: z.string().nullable(),
  cancelled: z.boolean(),
  platform: z.string(),
});

export type PickPathResult = z.infer<typeof pickPathResultSchema>;

/** Native OS folder/file picker via companion (`POST /api/local/pick-path`). */
export async function pickLocalPath(
  mode: "directory" | "file" = "directory",
): Promise<PickPathResult> {
  return pickPathResultSchema.parse(
    await request("/api/local/pick-path", {
      method: "POST",
      body: JSON.stringify({ mode }),
    }),
  );
}

export async function getHealth(): Promise<z.infer<typeof healthSchema>> {
  return healthSchema.parse(await request("/health"));
}

export async function getReady(): Promise<z.infer<typeof readySchema>> {
  return readySchema.parse(await request("/ready"));
}

/**
 * Live services catalog from companion prove-read projects.
 * No dedicated projects-list BFF exists yet — prove-read is the read path.
 */
export async function getServices(workspaceId?: string): Promise<Service[]> {
  const prove = await proveLiaraRead(workspaceId);
  return projectsToServices(prove.projects ?? []);
}

/** Account PaaS plan catalog (`GET /api/liara/plans`) — not deployment release history. */
export async function getLiaraPlans(workspaceId?: string): Promise<LiaraPlan[]> {
  const query = workspaceId ? `?workspace_id=${encodeURIComponent(workspaceId)}` : "";
  const raw = await request(`/api/liara/plans${query}`);
  // Always re-sort client-side so GenUI order is weak → strong even if cache/order drifts.
  return sortPlansWeakToStrong(liaraPlansResultSchema.parse(raw).plans);
}

export type AccountBalances = {
  liara: {
    configured: boolean;
    balance: number | null;
    currency: string;
    team_name?: string | null;
    error: string | null;
  };
  aval: {
    configured: boolean;
    remaining_irt: number | null;
    currency: string;
    error: string | null;
  };
};

/** Liara wallet + Aval credit for Settings header (`GET /api/settings/balances`). */
export async function getAccountBalances(workspaceId?: string): Promise<AccountBalances> {
  const query = workspaceId ? `?workspace_id=${encodeURIComponent(workspaceId)}` : "";
  return (await request(`/api/settings/balances${query}`)) as AccountBalances;
}

/** Domains for a Liara project (`GET /api/liara/domains`) — read-only; attach via HITL chat. */
export async function getDomains(
  project: string,
  workspaceId?: string,
): Promise<LiaraDomain[]> {
  const params = new URLSearchParams({ project });
  if (workspaceId) params.set("workspace_id", workspaceId);
  const raw = await request(`/api/liara/domains?${params.toString()}`);
  return liaraDomainsResultSchema.parse(raw).domains;
}

/**
 * Per-project monitoring feed (`GET /api/liara/projects/{name}/monitoring`).
 * Soft gaps for missing metrics/logs stay on HTTP 200; hard project errors throw.
 */
export async function getProjectMonitoring(
  projectName: string,
  workspaceId?: string,
): Promise<LiaraProjectMonitoring> {
  const name = projectName.trim();
  if (!name) throw new Error("project name is required");
  const query = workspaceId ? `?workspace_id=${encodeURIComponent(workspaceId)}` : "";
  const raw = await request(
    `/api/liara/projects/${encodeURIComponent(name)}/monitoring${query}`,
  );
  return liaraProjectMonitoringSchema.parse(raw);
}

/** Open/resolved incidents for a workspace (`GET /api/maintain/incidents`). */
export async function getIncidents(
  workspaceId: string,
  status?: string,
): Promise<MaintainIncident[]> {
  const params = new URLSearchParams({ workspace_id: workspaceId });
  if (status) params.set("status", status);
  const raw = await request(`/api/maintain/incidents?${params.toString()}`);
  return maintainIncidentsResultSchema.parse(raw).incidents;
}

/** Sanitized audit events (`GET /api/maintain/audit`) — no secret values. */
export async function getAuditEvents(
  workspaceId: string,
  options?: { caseId?: string; limit?: number },
): Promise<MaintainAuditEvent[]> {
  const params = new URLSearchParams({ workspace_id: workspaceId });
  if (options?.caseId) params.set("case_id", options.caseId);
  if (options?.limit != null) params.set("limit", String(options.limit));
  const raw = await request(`/api/maintain/audit?${params.toString()}`);
  return maintainAuditResultSchema.parse(raw).events;
}

export async function getSettings(workspaceId?: string): Promise<SettingsView> {
  const query = workspaceId ? `?workspace_id=${encodeURIComponent(workspaceId)}` : "";
  return settingsViewSchema.parse(await request(`/api/settings${query}`));
}

export async function saveSettings(body: SettingsUpdateBody): Promise<SettingsView> {
  // Only forward known companion fields — never echo or round-trip secret values from GET.
  const payload: SettingsUpdateBody = {};
  if (body.workspace_id !== undefined) payload.workspace_id = body.workspace_id;
  if (body.liara_api_base_url !== undefined) payload.liara_api_base_url = body.liara_api_base_url;
  if (body.liara_team_id !== undefined) payload.liara_team_id = body.liara_team_id;
  if (body.liara_api_token !== undefined && body.liara_api_token.trim()) {
    payload.liara_api_token = body.liara_api_token.trim();
  }
  if (body.llm_base_url !== undefined) payload.llm_base_url = body.llm_base_url;
  if (body.llm_model !== undefined) payload.llm_model = body.llm_model;
  if (body.llm_api_key !== undefined && body.llm_api_key.trim()) {
    payload.llm_api_key = body.llm_api_key.trim();
  }
  return settingsViewSchema.parse(
    await request("/api/settings", {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  );
}

export async function proveLiaraRead(workspaceId?: string): Promise<ProveLiaraReadResult> {
  const raw = await request("/api/liara/prove-read", {
    method: "POST",
    body: JSON.stringify(workspaceId ? { workspace_id: workspaceId } : {}),
  });
  return proveLiaraReadSchema.parse(raw);
}

export type ProveLlmResult = {
  ok: boolean;
  base_url: string;
  model: string;
  api_key_label: string | null;
  message: string;
};

/** Live Aval AI credential check (`POST /api/settings/prove-llm`). */
export async function proveLlmConnection(workspaceId?: string): Promise<ProveLlmResult> {
  const query = workspaceId ? `?workspace_id=${encodeURIComponent(workspaceId)}` : "";
  return (await request(`/api/settings/prove-llm${query}`, { method: "POST" })) as ProveLlmResult;
}

/** Live Aval AI credential check (`POST /api/settings/prove-llm`) — no secret echo. */
export async function proveAvalAi(workspaceId?: string): Promise<{
  ok: boolean;
  base_url: string;
  model: string;
  api_key_label: string | null;
  message: string;
}> {
  const query = workspaceId ? `?workspace_id=${encodeURIComponent(workspaceId)}` : "";
  const raw = await request(`/api/settings/prove-llm${query}`, { method: "POST", body: "{}" });
  const body = raw as {
    ok?: boolean;
    base_url?: string;
    model?: string;
    api_key_label?: string | null;
    message?: string;
  };
  return {
    ok: Boolean(body.ok),
    base_url: String(body.base_url ?? ""),
    model: String(body.model ?? ""),
    api_key_label: body.api_key_label ?? null,
    message: String(body.message ?? "اتصال برقرار است."),
  };
}

// --- Companion orchestrator (`/api/orchestrator/*`) ---------------------------

export async function createCase(workspaceId: string, goal: string): Promise<OrchestratorCase> {
  return orchestratorCaseSchema.parse(
    await request("/api/orchestrator/cases", {
      method: "POST",
      body: JSON.stringify({ workspace_id: workspaceId, goal }),
    }),
  );
}

export async function assessReadiness(
  workspaceId: string,
  caseId: string,
  appPath?: string | null,
): Promise<ReadinessAssessment> {
  return readinessAssessmentSchema.parse(
    await request("/api/orchestrator/assess_readiness", {
      method: "POST",
      body: JSON.stringify(assessReadinessPayload(workspaceId, caseId, appPath)),
    }),
  );
}

export async function createPlan(args: {
  workspaceId: string;
  caseId: string;
  goal?: string;
  useLlm?: boolean;
  plan?: Record<string, unknown>;
  /** Deploy draft fields (e.g. app_path, project_name, plan_id). */
  deploy?: Record<string, unknown>;
  /** Ops draft fields (resize / domain / env / restart). */
  ops?: Record<string, unknown>;
  /** Deps draft fields (app_path, project_name, …). */
  deps?: Record<string, unknown>;
}): Promise<CreatePlanResult> {
  return createPlanResultSchema.parse(
    await request("/api/orchestrator/create_plan", {
      method: "POST",
      body: JSON.stringify({
        workspace_id: args.workspaceId,
        case_id: args.caseId,
        ...(args.goal ? { goal: args.goal } : {}),
        ...(args.useLlm !== undefined ? { use_llm: args.useLlm } : {}),
        ...(args.plan ? { plan: args.plan } : {}),
        ...(args.deploy ? { deploy: args.deploy } : {}),
        ...(args.ops ? { ops: args.ops } : {}),
        ...(args.deps ? { deps: args.deps } : {}),
      }),
    }),
  );
}

export async function approvePlan(
  workspaceId: string,
  planId: string,
): Promise<ApprovePlanResult> {
  return approvePlanResultSchema.parse(
    await request("/api/orchestrator/approve_plan", {
      method: "POST",
      body: JSON.stringify({ workspace_id: workspaceId, plan_id: planId }),
    }),
  );
}

export async function executePlan(args: {
  workspaceId: string;
  planId: string;
  clientRequestId: string;
  actorId?: string;
}): Promise<OperationPayload> {
  return operationPayloadSchema.parse(
    await request("/api/orchestrator/execute_plan", {
      method: "POST",
      body: JSON.stringify({
        workspace_id: args.workspaceId,
        plan_id: args.planId,
        client_request_id: args.clientRequestId,
        ...(args.actorId ? { actor_id: args.actorId } : {}),
      }),
    }),
  );
}

export async function continueOrStop(
  workspaceId: string,
  operationId: string,
  decision: "continue" | "stop",
): Promise<OperationPayload> {
  return operationPayloadSchema.parse(
    await request("/api/orchestrator/continue_or_stop", {
      method: "POST",
      body: JSON.stringify({
        workspace_id: workspaceId,
        operation_id: operationId,
        decision,
      }),
    }),
  );
}

export async function verifyResult(
  workspaceId: string,
  operationId: string,
): Promise<OperationPayload> {
  return operationPayloadSchema.parse(
    await request("/api/orchestrator/verify_result", {
      method: "POST",
      body: JSON.stringify({ workspace_id: workspaceId, operation_id: operationId }),
    }),
  );
}

export async function getOperation(
  workspaceId: string,
  operationId: string,
): Promise<OperationPayload> {
  const query = `?workspace_id=${encodeURIComponent(workspaceId)}`;
  return operationPayloadSchema.parse(
    await request(`/api/orchestrator/operations/${encodeURIComponent(operationId)}${query}`),
  );
}

/** Phase-3 troubleshoot: gather read-only evidence (no writes). */
export async function collectEvidence(args: {
  workspaceId: string;
  caseId: string;
  projectName: string;
  symptom?: string;
  windowNote?: string;
}): Promise<EvidencePack> {
  return evidencePackSchema.parse(
    await request("/api/orchestrator/collect_evidence", {
      method: "POST",
      body: JSON.stringify({
        workspace_id: args.workspaceId,
        case_id: args.caseId,
        project_name: args.projectName,
        ...(args.symptom ? { symptom: args.symptom } : {}),
        ...(args.windowNote ? { window_note: args.windowNote } : {}),
      }),
    }),
  );
}

export async function diagnoseCase(args: {
  workspaceId: string;
  caseId: string;
  evidenceVersion: string;
}): Promise<Diagnosis> {
  return diagnosisSchema.parse(
    await request("/api/orchestrator/diagnose", {
      method: "POST",
      body: JSON.stringify({
        workspace_id: args.workspaceId,
        case_id: args.caseId,
        evidence_version: args.evidenceVersion,
      }),
    }),
  );
}

export async function proposeFixOptions(args: {
  workspaceId: string;
  caseId: string;
  diagnosisVersion: string;
  projectName: string;
  planIdForResize?: string;
}): Promise<FixOptionsPayload> {
  return fixOptionsPayloadSchema.parse(
    await request("/api/orchestrator/propose_fix_options", {
      method: "POST",
      body: JSON.stringify({
        workspace_id: args.workspaceId,
        case_id: args.caseId,
        diagnosis_version: args.diagnosisVersion,
        project_name: args.projectName,
        ...(args.planIdForResize ? { plan_id_for_resize: args.planIdForResize } : {}),
      }),
    }),
  );
}

/** Turn an enabled fix option into an ops plan — still needs HITL approve+execute. */
export async function createPlanFromFix(args: {
  workspaceId: string;
  caseId: string;
  optionId: string;
}): Promise<CreatePlanResult> {
  return createPlanResultSchema.parse(
    await request("/api/orchestrator/create_plan_from_fix", {
      method: "POST",
      body: JSON.stringify({
        workspace_id: args.workspaceId,
        case_id: args.caseId,
        option_id: args.optionId,
      }),
    }),
  );
}

/**
 * Enable a maintain monitor (`POST /api/maintain/monitors/enable`).
 * Does not grant write permission — recovery still needs separate HITL.
 */
export async function enableMonitor(args: {
  workspaceId: string;
  target: string;
  caseId?: string;
  intervalSeconds?: number;
}): Promise<MonitorStatus> {
  return monitorStatusSchema.parse(
    await request("/api/maintain/monitors/enable", {
      method: "POST",
      body: JSON.stringify({
        workspace_id: args.workspaceId,
        target: args.target,
        ...(args.caseId ? { case_id: args.caseId } : {}),
        ...(args.intervalSeconds != null ? { interval_seconds: args.intervalSeconds } : {}),
      }),
    }),
  );
}
