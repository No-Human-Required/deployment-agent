import { z } from "zod";

/** One event from `GET /api/agent/runs/{id}/events` (SSE). Unknown fields pass through. */
export const agentEventSchema = z
  .object({
    seq: z.number().int(),
    type: z.string(),
    ts: z.number().optional(),
  })
  .passthrough();

export type AgentEvent = z.infer<typeof agentEventSchema> & Record<string, unknown>;

export const agentOutcomeSchema = z
  .object({
    success: z.boolean(),
    verified: z.boolean().optional(),
    summary: z.string(),
    url: z.string().optional(),
    budget_exhausted: z.boolean().optional(),
  })
  .passthrough();

export type AgentOutcome = z.infer<typeof agentOutcomeSchema>;

export type AgentRunStatus =
  | "proposed"
  | "starting"
  | "running"
  | "awaiting_approval"
  | "done"
  | "error"
  | "cancelled";

export const agentRunViewSchema = z.object({
  status: z.enum(["proposed", "starting", "running", "awaiting_approval", "done", "error", "cancelled"]),
  goal: z.string(),
  projectName: z.string(),
  runId: z.string().optional(),
  events: z.array(agentEventSchema).default([]),
  outcome: agentOutcomeSchema.optional(),
  pendingApproval: z.array(z.object({ name: z.string(), args: z.record(z.unknown()).optional() }).passthrough()).optional(),
  error: z.string().optional(),
});

export type AgentRunView = z.infer<typeof agentRunViewSchema>;

export const startAgentRunResultSchema = z.object({
  run_id: z.string(),
  status: z.string(),
  project_name: z.string(),
  project_root: z.string(),
});

export const agentRunSnapshotSchema = z
  .object({
    run_id: z.string(),
    status: z.string(),
    outcome: agentOutcomeSchema.nullable().optional(),
    pending_approval: z.record(z.unknown()).nullable().optional(),
    events: z.array(agentEventSchema),
  })
  .passthrough();

const MAX_STORED_TEXT = 600;

function trimEvent(event: AgentEvent): AgentEvent {
  const out: AgentEvent = { ...event };
  for (const key of ["preview", "text", "diff"] as const) {
    const value = out[key];
    const limit = key === "diff" ? 4000 : MAX_STORED_TEXT;
    if (typeof value === "string" && value.length > limit) {
      out[key] = `${value.slice(0, limit)}…`;
    }
  }
  return out;
}

/** Fold one server event into the chat-side view (idempotent by seq). */
export function applyAgentEvent(view: AgentRunView, event: AgentEvent): AgentRunView {
  if (view.events.some((existing) => existing.seq === event.seq)) return view;
  const next: AgentRunView = { ...view, events: [...view.events, trimEvent(event)] };
  switch (event.type) {
    case "approval_required": {
      const calls = Array.isArray(event.calls) ? (event.calls as AgentRunView["pendingApproval"]) : [];
      return { ...next, status: "awaiting_approval", pendingApproval: calls };
    }
    case "approval_resolved":
      return { ...next, status: "running", pendingApproval: undefined };
    case "user_note":
      return next.status === "starting" ? { ...next, status: "running" } : next;
    case "done": {
      const parsed = agentOutcomeSchema.safeParse(event.outcome);
      return { ...next, status: "done", outcome: parsed.success ? parsed.data : undefined, pendingApproval: undefined };
    }
    case "error":
      return { ...next, status: "error", error: String(event.message ?? "agent error") };
    default:
      return next.status === "starting" ? { ...next, status: "running" } : next;
  }
}

export function lastSeq(view: AgentRunView): number {
  return view.events.reduce((max, event) => Math.max(max, event.seq), 0);
}

export function isAgentRunLive(view: AgentRunView | undefined): boolean {
  return Boolean(view?.runId) && (view?.status === "running" || view?.status === "awaiting_approval" || view?.status === "starting");
}

const TOOL_LABELS_FA: Record<string, string> = {
  load_skill: "خواندن دستورالعمل",
  list_skills: "فهرست دستورالعمل‌ها",
  liara_docs_index: "فهرست مستندات لیارا",
  liara_docs_fetch: "خواندن مستندات لیارا",
  web_fetch: "جستجو در وب",
  list_dir: "مرور پوشه‌ها",
  read_file: "خواندن فایل",
  grep: "جستجو در کد",
  edit_file: "ویرایش کد",
  write_file: "نوشتن فایل",
  run_command: "اجرای دستور ساخت",
  liara_list_apps: "فهرست اپ‌ها",
  liara_get_project: "وضعیت اپ در لیارا",
  liara_list_releases: "بررسی انتشارها",
  liara_build_logs: "لاگ ساخت",
  liara_runtime_logs: "لاگ اجرای سرویس",
  liara_list_databases: "فهرست دیتابیس‌ها",
  liara_deploy: "استقرار روی لیارا",
  liara_set_envs: "تنظیم متغیرهای محیطی",
  liara_connect_database: "اتصال دیتابیس",
  liara_restart: "ری‌استارت",
  liara_create_app: "ساخت اپ جدید",
  liara_create_database: "ساخت دیتابیس",
  liara_create_disk: "ساخت دیسک",
  liara_attach_domain: "اتصال دامنه",
  http_check: "بررسی آدرس",
  wait: "صبر",
  finish: "پایان",
};

export function toolLabel(name: string, language: "fa" | "en"): string {
  if (language === "fa") return TOOL_LABELS_FA[name] ?? name;
  return name.replace(/^liara_/, "liara · ").replace(/_/g, " ");
}

/** One-line hint from tool args shown next to the label (file path, URL, command…). */
export function toolArgHint(args: unknown): string {
  if (!args || typeof args !== "object") return "";
  const record = args as Record<string, unknown>;
  for (const key of ["path", "path_or_url", "url", "command", "name", "release_id", "app_dir", "database_id"]) {
    const value = record[key];
    if (typeof value === "string" && value.trim()) return value.length > 80 ? `${value.slice(0, 80)}…` : value;
  }
  if (Array.isArray(record.variables)) return record.variables.join(", ");
  return "";
}
