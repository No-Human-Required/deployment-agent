import { z } from "zod";

const localWorkspaceSchema = z.object({
  version: z.literal(1),
  path: z.string().min(1),
  displayName: z.string().min(1),
});

const workspaceStoreV2Schema = z.object({
  version: z.literal(2),
  activePath: z.string().min(1).nullable(),
  recent: z.array(localWorkspaceSchema).max(12),
});

export type LocalWorkspace = z.infer<typeof localWorkspaceSchema>;
export type WorkspaceStoreV2 = z.infer<typeof workspaceStoreV2Schema>;
type StoragePort = Pick<Storage, "getItem" | "setItem" | "removeItem">;

export const LOCAL_WORKSPACE_STORAGE_KEY = "liaraops-ai:local-workspace";
const MAX_RECENT = 8;

const ERR = {
  unavailable: "فضای کار محلی در این مرورگر در دسترس نیست.",
  unreadable: "فضای کار ذخیره‌شده قابل خواندن نبود؛ پاک شد تا بتوانید دوباره انتخاب کنید.",
  saveValidation: "ذخیره فضای کار ممکن نشد (داده نامعتبر).",
  saveStorage: "ذخیره فضای کار در این مرورگر ممکن نشد. فضای ذخیره‌سازی را بررسی کنید.",
} as const;

/** Stable identity for a local folder path (trim + strip trailing separators). */
export function normalizeWorkspaceKey(path: string): string {
  let value = path.trim().replace(/\u0000/g, "");
  if (!value) return "";
  // Preserve drive / UNC shape; only strip trailing / or \ when length > 1.
  if (value.length > 1) {
    value = value.replace(/[/\\]+$/, "");
  }
  return value;
}

/** Last path segment for chrome (FA/EN-agnostic). */
export function folderDisplayName(path: string): string {
  const key = normalizeWorkspaceKey(path);
  const parts = key.replace(/\\/g, "/").split("/").filter(Boolean);
  return parts[parts.length - 1] || key;
}

function sanitizeWorkspace(raw: LocalWorkspace): LocalWorkspace | null {
  const path = normalizeWorkspaceKey(raw.path);
  if (!path) return null;
  return {
    version: 1,
    path,
    displayName: raw.displayName.trim() || folderDisplayName(path),
  };
}

function pushRecent(recent: LocalWorkspace[], next: LocalWorkspace): LocalWorkspace[] {
  const key = normalizeWorkspaceKey(next.path);
  const rest = recent.filter((item) => normalizeWorkspaceKey(item.path) !== key);
  return [next, ...rest].slice(0, MAX_RECENT);
}

function readRawStore(storage: StoragePort): {
  store: WorkspaceStoreV2 | null;
  error: string | null;
} {
  let raw: string | null;
  try {
    raw = storage.getItem(LOCAL_WORKSPACE_STORAGE_KEY);
  } catch {
    return { store: null, error: ERR.unavailable };
  }

  if (raw === null) {
    return { store: { version: 2, activePath: null, recent: [] }, error: null };
  }

  let decoded: unknown;
  try {
    decoded = JSON.parse(raw);
  } catch {
    try {
      storage.removeItem(LOCAL_WORKSPACE_STORAGE_KEY);
    } catch {
      /* ignore */
    }
    return { store: null, error: ERR.unreadable };
  }

  const v2 = workspaceStoreV2Schema.safeParse(decoded);
  if (v2.success) {
    const recent = v2.data.recent
      .map((item) => sanitizeWorkspace(item))
      .filter((item): item is LocalWorkspace => item !== null);
    let activePath = v2.data.activePath ? normalizeWorkspaceKey(v2.data.activePath) : null;
    if (activePath && !recent.some((item) => item.path === activePath)) {
      activePath = recent[0]?.path ?? null;
    }
    return { store: { version: 2, activePath, recent }, error: null };
  }

  // Legacy v1: single active workspace object.
  const v1 = localWorkspaceSchema.safeParse(decoded);
  if (v1.success) {
    const workspace = sanitizeWorkspace(v1.data);
    if (!workspace) {
      try {
        storage.removeItem(LOCAL_WORKSPACE_STORAGE_KEY);
      } catch {
        /* ignore */
      }
      return { store: null, error: ERR.unreadable };
    }
    return {
      store: { version: 2, activePath: workspace.path, recent: [workspace] },
      error: null,
    };
  }

  try {
    storage.removeItem(LOCAL_WORKSPACE_STORAGE_KEY);
  } catch {
    /* ignore */
  }
  return { store: null, error: ERR.unreadable };
}

function writeStore(storage: StoragePort, store: WorkspaceStoreV2): string | null {
  const recent = store.recent
    .map((item) => sanitizeWorkspace(item))
    .filter((item): item is LocalWorkspace => item !== null)
    .slice(0, MAX_RECENT);
  let activePath = store.activePath ? normalizeWorkspaceKey(store.activePath) : null;
  if (activePath && !recent.some((item) => item.path === activePath)) {
    activePath = recent[0]?.path ?? null;
  }
  const payload: WorkspaceStoreV2 = { version: 2, activePath, recent };
  const parsed = workspaceStoreV2Schema.safeParse(payload);
  if (!parsed.success) return ERR.saveValidation;
  try {
    storage.setItem(LOCAL_WORKSPACE_STORAGE_KEY, JSON.stringify(parsed.data));
    return null;
  } catch {
    return ERR.saveStorage;
  }
}

export function loadLocalWorkspace(storage: StoragePort): {
  workspace: LocalWorkspace | null;
  recent: LocalWorkspace[];
  error: string | null;
} {
  const { store, error } = readRawStore(storage);
  if (!store) return { workspace: null, recent: [], error };
  const workspace =
    store.activePath != null
      ? store.recent.find((item) => item.path === store.activePath) ?? null
      : null;
  return { workspace, recent: store.recent, error };
}

export function listRecentWorkspaces(storage: StoragePort): LocalWorkspace[] {
  return loadLocalWorkspace(storage).recent;
}

export function saveLocalWorkspace(
  storage: StoragePort,
  workspace: LocalWorkspace | null,
): string | null {
  if (workspace === null) {
    const { store } = readRawStore(storage);
    if (!store) {
      try {
        storage.removeItem(LOCAL_WORKSPACE_STORAGE_KEY);
        return null;
      } catch {
        return ERR.saveStorage;
      }
    }
    return writeStore(storage, { version: 2, activePath: null, recent: store.recent });
  }

  const next = sanitizeWorkspace(workspace);
  if (!next) return ERR.saveValidation;

  const { store, error } = readRawStore(storage);
  if (error && !store) return error;
  const base = store ?? { version: 2 as const, activePath: null, recent: [] as LocalWorkspace[] };
  return writeStore(storage, {
    version: 2,
    activePath: next.path,
    recent: pushRecent(base.recent, next),
  });
}

/** Switch active folder to an already-known recent path (no OS picker). */
export function activateRecentWorkspace(
  storage: StoragePort,
  path: string,
): { workspace: LocalWorkspace | null; error: string | null } {
  const key = normalizeWorkspaceKey(path);
  const { store, error } = readRawStore(storage);
  if (!store) return { workspace: null, error: error ?? ERR.unreadable };
  const found = store.recent.find((item) => item.path === key);
  if (!found) return { workspace: null, error: ERR.saveValidation };
  const saveError = writeStore(storage, {
    version: 2,
    activePath: found.path,
    recent: pushRecent(store.recent, found),
  });
  if (saveError) return { workspace: null, error: saveError };
  return { workspace: found, error: null };
}
