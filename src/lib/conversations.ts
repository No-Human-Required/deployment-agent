import { z } from "zod";
import { normalizeWorkspaceKey } from "./workspace";
import { orchestratorRunSchema } from "./schemas";

const chatMessageSchema = z.object({
  id: z.string().min(1),
  role: z.enum(["user", "assistant"]),
  text: z.string(),
  kind: z.enum(["demo", "live"]).optional(),
});

const conversationLooseSchema = z.object({
  id: z.string().min(1),
  title: z.string().min(1),
  serviceId: z.string().min(1),
  messages: z.array(chatMessageSchema),
  updatedAt: z.string().min(1),
  orchestratorRun: z.unknown().optional().nullable(),
});

export const conversationSchema = z.object({
  id: z.string().min(1),
  title: z.string().min(1),
  serviceId: z.string().min(1),
  messages: z.array(chatMessageSchema),
  updatedAt: z.string().datetime({ offset: true }),
  /** Companion orchestrator session (case / plan / HITL / operation). */
  orchestratorRun: orchestratorRunSchema.nullable(),
});

/** Orphan bucket for pre-v3 flat history (never selected as a live workspace). */
export const UNSCOPED_CONVERSATION_KEY = "__unscoped__";

const conversationStoreV3Schema = z.object({
  version: z.literal(3),
  byWorkspace: z.record(z.string(), z.array(conversationSchema).max(8)),
});

const legacyFlatStoreSchema = z.object({
  version: z.union([z.literal(1), z.literal(2)]),
  conversations: z.array(conversationLooseSchema).max(8),
});

export type Conversation = z.infer<typeof conversationSchema>;
type StoragePort = Pick<Storage, "getItem" | "setItem" | "removeItem">;
type StoreV3 = z.infer<typeof conversationStoreV3Schema>;

const STORAGE_KEY = "liaraops-ai:conversation-history";
const MAX_PER_WORKSPACE = 8;

const ERR = {
  unavailable: "تاریخچه گفتگو در این مرورگر در دسترس نیست. جلسه فعلی همچنان کار می‌کند.",
  unreadable: "تاریخچه ذخیره‌شده قابل خواندن نبود؛ پاک شد تا بتوانید دوباره شروع کنید.",
  unsupported: "قالب تاریخچه قدیمی بود؛ به نسخه جدید مهاجرت داده شد.",
  saveValidation: "ذخیره تاریخچه ممکن نشد (داده نامعتبر).",
  saveStorage: "ذخیره تاریخچه در این مرورگر ممکن نشد. فضای ذخیره‌سازی را بررسی کنید.",
} as const;

function normalizeConversation(raw: z.infer<typeof conversationLooseSchema>): Conversation | null {
  let updatedAt = raw.updatedAt;
  // Accept plain ISO without forcing offset parse failure
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

  const candidate = {
    id: raw.id,
    title: raw.title,
    serviceId: raw.serviceId || "workspace",
    messages: raw.messages,
    updatedAt,
    orchestratorRun,
  };
  const ok = conversationSchema.safeParse(candidate);
  return ok.success ? ok.data : null;
}

function normalizeList(rawList: unknown[]): Conversation[] {
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

function emptyStore(): StoreV3 {
  return { version: 3, byWorkspace: {} };
}

function persistStore(storage: StoragePort, store: StoreV3): string | null {
  const parsed = conversationStoreV3Schema.safeParse(store);
  if (!parsed.success) {
    return ERR.saveValidation;
  }
  try {
    storage.setItem(STORAGE_KEY, JSON.stringify(parsed.data));
    return null;
  } catch {
    return ERR.saveStorage;
  }
}

function readStore(storage: StoragePort): {
  store: StoreV3;
  error: string | null;
} {
  let raw: string | null;
  try {
    raw = storage.getItem(STORAGE_KEY);
  } catch {
    return { store: emptyStore(), error: ERR.unavailable };
  }

  if (raw === null) return { store: emptyStore(), error: null };

  let decoded: unknown;
  try {
    decoded = JSON.parse(raw);
  } catch {
    try {
      storage.removeItem(STORAGE_KEY);
    } catch {
      /* ignore */
    }
    return { store: emptyStore(), error: ERR.unreadable };
  }

  const strict = conversationStoreV3Schema.safeParse(decoded);
  if (strict.success) {
    return { store: strict.data, error: null };
  }

  const legacy = legacyFlatStoreSchema.safeParse(decoded);
  if (legacy.success) {
    const conversations = normalizeList(legacy.data.conversations);
    const store: StoreV3 = {
      version: 3,
      byWorkspace:
        conversations.length > 0 ? { [UNSCOPED_CONVERSATION_KEY]: conversations } : {},
    };
    const saveError = persistStore(storage, store);
    return {
      store,
      error:
        saveError
        ?? (conversations.length === 0 && legacy.data.conversations.length > 0
          ? ERR.unsupported
          : null),
    };
  }

  try {
    storage.removeItem(STORAGE_KEY);
  } catch {
    /* ignore */
  }
  return { store: emptyStore(), error: ERR.unreadable };
}

export function loadConversationHistory(
  storage: StoragePort,
  workspaceKey: string | null,
): {
  conversations: Conversation[];
  error: string | null;
} {
  const { store, error } = readStore(storage);
  if (!workspaceKey) {
    return { conversations: [], error };
  }
  const key = normalizeWorkspaceKey(workspaceKey);
  if (!key || key === UNSCOPED_CONVERSATION_KEY) {
    return { conversations: [], error };
  }
  return {
    conversations: store.byWorkspace[key] ?? [],
    error,
  };
}

/** All workspace → conversation lists (skips orphan unscoped bucket). */
export function loadAllConversationHistory(storage: StoragePort): {
  byWorkspace: Record<string, Conversation[]>;
  error: string | null;
} {
  const { store, error } = readStore(storage);
  const byWorkspace: Record<string, Conversation[]> = {};
  for (const [rawKey, list] of Object.entries(store.byWorkspace)) {
    const key = normalizeWorkspaceKey(rawKey);
    if (!key || key === UNSCOPED_CONVERSATION_KEY) continue;
    byWorkspace[key] = list;
  }
  return { byWorkspace, error };
}

/** Find a conversation id across workspace buckets. */
export function findConversationInHistory(
  storage: StoragePort,
  conversationId: string,
): { workspaceKey: string; conversation: Conversation } | null {
  const { byWorkspace } = loadAllConversationHistory(storage);
  for (const [workspaceKey, list] of Object.entries(byWorkspace)) {
    const conversation = list.find((item) => item.id === conversationId);
    if (conversation) return { workspaceKey, conversation };
  }
  return null;
}

export function saveConversationHistory(
  storage: StoragePort,
  workspaceKey: string,
  conversations: unknown,
): string | null {
  const key = normalizeWorkspaceKey(workspaceKey);
  if (!key || key === UNSCOPED_CONVERSATION_KEY) {
    return ERR.saveValidation;
  }

  const { store, error: readError } = readStore(storage);
  if (readError === ERR.unavailable) {
    return ERR.saveStorage;
  }

  const list = Array.isArray(conversations) ? conversations : [];
  const normalized = normalizeList(list);
  const next: StoreV3 = {
    version: 3,
    byWorkspace: {
      ...store.byWorkspace,
      [key]: normalized,
    },
  };
  if (normalized.length === 0) {
    delete next.byWorkspace[key];
  }

  const parsed = conversationStoreV3Schema.safeParse(next);
  if (!parsed.success) {
    return ERR.saveValidation;
  }

  return persistStore(storage, parsed.data);
}
