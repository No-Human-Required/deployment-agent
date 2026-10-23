import { z } from "zod";
import { normalizeWorkspaceKey } from "./workspace";
import { orchestratorRunSchema } from "./schemas";

const quickReplySchema = z.object({
  id: z.string().min(1),
  label: z.string().min(1),
  kind: z.enum([
    "prompt",
    "approve",
    "reject",
    "settings",
    "fix",
    "intake_service",
  ]),
  prompt: z.string().optional(),
  value: z.string().optional(),
});

const chatMessageSchema = z.object({
  id: z.string().min(1),
  role: z.enum(["user", "assistant"]),
  text: z.string(),
  kind: z.enum(["demo", "live"]).optional(),
  quickReplies: z.array(quickReplySchema).max(8).optional(),
});

const contextServiceSchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
});

const conversationLooseSchema = z.object({
  id: z.string().min(1),
  title: z.string().min(1),
  serviceId: z.string().min(1),
  contextServices: z.array(contextServiceSchema).max(8).optional(),
  messages: z.array(chatMessageSchema),
  updatedAt: z.string().min(1),
  orchestratorRun: z.unknown().optional().nullable(),
});

export const conversationSchema = z.object({
  id: z.string().min(1),
  title: z.string().min(1),
  serviceId: z.string().min(1),
  /** Liara services attached as chat context (from composer +). */
  contextServices: z.array(contextServiceSchema).max(8).default([]),
  messages: z.array(chatMessageSchema),
  updatedAt: z.string().datetime({ offset: true }),
  /** Companion orchestrator session (case / plan / HITL / operation). */
  orchestratorRun: orchestratorRunSchema.nullable(),
});

/** Orphan bucket label retained for validation only (never written to DB). */
export const UNSCOPED_CONVERSATION_KEY = "__unscoped__";

export type Conversation = z.infer<typeof conversationSchema>;

const MAX_PER_WORKSPACE = 8;

const ERR = {
  unavailable: "تاریخچه گفتگو از پایگاه‌داده در دسترس نیست. جلسه فعلی همچنان کار می‌کند.",
  saveValidation: "ذخیره تاریخچه ممکن نشد (داده نامعتبر).",
  saveStorage: "ذخیره تاریخچه در پایگاه‌داده ممکن نشد.",
} as const;

export function normalizeConversation(
  raw: z.infer<typeof conversationLooseSchema>,
): Conversation | null {
  let updatedAt = raw.updatedAt;
  if (!Number.isNaN(Date.parse(updatedAt))) {
    updatedAt = new Date(updatedAt).toISOString();
  } else {
    updatedAt = new Date().toISOString();
  }

  let orchestratorRun: Conversation["orchestratorRun"] = null;
  if (raw.orchestratorRun != null) {
    const parsed = orchestratorRunSchema.safeParse(raw.orchestratorRun);
    orchestratorRun = parsed.success ? parsed.data : null;
  }

  const legacyService =
    raw.serviceId && raw.serviceId !== "workspace"
      ? [{ id: raw.serviceId, name: raw.serviceId }]
      : [];
  const contextServices =
    raw.contextServices && raw.contextServices.length > 0
      ? raw.contextServices
      : legacyService;

  const candidate = {
    id: raw.id,
    title: raw.title,
    serviceId: contextServices[0]?.id ?? (raw.serviceId || "workspace"),
    contextServices,
    messages: raw.messages,
    updatedAt,
    orchestratorRun,
  };
  const ok = conversationSchema.safeParse(candidate);
  return ok.success ? ok.data : null;
}

export function normalizeConversationList(rawList: unknown[]): Conversation[] {
  const out: Conversation[] = [];
  for (const item of rawList) {
    const loose = conversationLooseSchema.safeParse(item);
    if (!loose.success) continue;
    const normalized = normalizeConversation(loose.data);
    if (normalized) out.push(normalized);
    if (out.length >= MAX_PER_WORKSPACE) break;
  }
  return out;
}

function formatDetail(body: unknown, status: number): string {
  if (typeof body === "object" && body !== null && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
  }
  return `درخواست ناموفق بود (کد ${status})`;
}

async function apiRequest(path: string, init?: RequestInit): Promise<unknown> {
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

function qs(workspaceId: string, extra?: Record<string, string>): string {
  const params = new URLSearchParams({ workspace_id: workspaceId, ...extra });
  return params.toString();
}

export async function loadConversationHistory(
  workspaceId: string,
  workspaceKey: string | null,
): Promise<{
  conversations: Conversation[];
  error: string | null;
}> {
  if (!workspaceKey) {
    return { conversations: [], error: null };
  }
  const key = normalizeWorkspaceKey(workspaceKey);
  if (!key || key === UNSCOPED_CONVERSATION_KEY) {
    return { conversations: [], error: null };
  }
  try {
    const raw = await apiRequest(
      `/api/conversations?${qs(workspaceId, { folder_key: key })}`,
    );
    const list = Array.isArray((raw as { conversations?: unknown }).conversations)
      ? (raw as { conversations: unknown[] }).conversations
      : [];
    return { conversations: normalizeConversationList(list), error: null };
  } catch {
    return { conversations: [], error: ERR.unavailable };
  }
}

/** All folder → conversation lists. */
export async function loadAllConversationHistory(workspaceId: string): Promise<{
  byWorkspace: Record<string, Conversation[]>;
  error: string | null;
}> {
  try {
    const raw = await apiRequest(
      `/api/conversations?${qs(workspaceId, { all_folders: "true" })}`,
    );
    const byRaw =
      typeof raw === "object" &&
      raw !== null &&
      "byWorkspace" in raw &&
      typeof (raw as { byWorkspace: unknown }).byWorkspace === "object" &&
      (raw as { byWorkspace: unknown }).byWorkspace !== null
        ? ((raw as { byWorkspace: Record<string, unknown> }).byWorkspace)
        : {};
    const byWorkspace: Record<string, Conversation[]> = {};
    for (const [rawKey, list] of Object.entries(byRaw)) {
      const key = normalizeWorkspaceKey(rawKey);
      if (!key || key === UNSCOPED_CONVERSATION_KEY) continue;
      byWorkspace[key] = normalizeConversationList(Array.isArray(list) ? list : []);
    }
    return { byWorkspace, error: null };
  } catch {
    return { byWorkspace: {}, error: ERR.unavailable };
  }
}

/** Find a conversation id across folder buckets. */
export async function findConversationInHistory(
  workspaceId: string,
  conversationId: string,
): Promise<{ workspaceKey: string; conversation: Conversation } | null> {
  try {
    const raw = await apiRequest(
      `/api/conversations/by-id/${encodeURIComponent(conversationId)}?${qs(workspaceId)}`,
    );
    if (typeof raw !== "object" || raw === null) return null;
    const workspaceKey = normalizeWorkspaceKey(
      String((raw as { workspaceKey?: unknown }).workspaceKey ?? ""),
    );
    const loose = conversationLooseSchema.safeParse(
      (raw as { conversation?: unknown }).conversation,
    );
    if (!workspaceKey || !loose.success) return null;
    const conversation = normalizeConversation(loose.data);
    if (!conversation) return null;
    return { workspaceKey, conversation };
  } catch {
    return null;
  }
}

export async function saveConversationHistory(
  workspaceId: string,
  workspaceKey: string,
  conversations: unknown,
): Promise<string | null> {
  const key = normalizeWorkspaceKey(workspaceKey);
  if (!key || key === UNSCOPED_CONVERSATION_KEY) {
    return ERR.saveValidation;
  }

  const list = Array.isArray(conversations) ? conversations : [];
  const normalized = normalizeConversationList(list);

  try {
    await apiRequest("/api/conversations", {
      method: "PUT",
      body: JSON.stringify({
        workspace_id: workspaceId,
        folder_key: key,
        conversations: normalized,
      }),
    });
    return null;
  } catch {
    return ERR.saveStorage;
  }
}
