import { z } from "zod";

const localWorkspaceSchema = z.object({
  version: z.literal(1),
  path: z.string().min(1),
  displayName: z.string().min(1),
});

export type LocalWorkspace = z.infer<typeof localWorkspaceSchema>;

const ERR = {
  unavailable: "فضای کار محلی از پایگاه‌داده در دسترس نیست.",
  saveValidation: "ذخیره فضای کار ممکن نشد (داده نامعتبر).",
  saveStorage: "ذخیره فضای کار در پایگاه‌داده ممکن نشد.",
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

function parseFolderPayload(raw: unknown): {
  workspace: LocalWorkspace | null;
  recent: LocalWorkspace[];
} {
  if (typeof raw !== "object" || raw === null) {
    return { workspace: null, recent: [] };
  }
  const recentRaw = Array.isArray((raw as { recent?: unknown }).recent)
    ? (raw as { recent: unknown[] }).recent
    : [];
  const recent: LocalWorkspace[] = [];
  for (const item of recentRaw) {
    const parsed = localWorkspaceSchema.safeParse(item);
    if (!parsed.success) continue;
    const sanitized = sanitizeWorkspace(parsed.data);
    if (sanitized) recent.push(sanitized);
  }
  const activeParsed = localWorkspaceSchema.safeParse(
    (raw as { workspace?: unknown }).workspace,
  );
  const workspace = activeParsed.success
    ? sanitizeWorkspace(activeParsed.data)
    : null;
  return { workspace, recent };
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

export async function loadLocalWorkspace(workspaceId: string): Promise<{
  workspace: LocalWorkspace | null;
  recent: LocalWorkspace[];
  error: string | null;
}> {
  try {
    const raw = await apiRequest(
      `/api/folders?workspace_id=${encodeURIComponent(workspaceId)}`,
    );
    const parsed = parseFolderPayload(raw);
    return { ...parsed, error: null };
  } catch {
    return { workspace: null, recent: [], error: ERR.unavailable };
  }
}

export async function listRecentWorkspaces(
  workspaceId: string,
): Promise<LocalWorkspace[]> {
  return (await loadLocalWorkspace(workspaceId)).recent;
}

export async function saveLocalWorkspace(
  workspaceId: string,
  workspace: LocalWorkspace | null,
): Promise<{ workspace: LocalWorkspace | null; recent: LocalWorkspace[]; error: string | null }> {
  if (workspace === null) {
    try {
      const raw = await apiRequest("/api/folders", {
        method: "PUT",
        body: JSON.stringify({
          workspace_id: workspaceId,
          clear_active: true,
        }),
      });
      return { ...parseFolderPayload(raw), error: null };
    } catch {
      return { workspace: null, recent: [], error: ERR.saveStorage };
    }
  }

  const next = sanitizeWorkspace(workspace);
  if (!next) {
    return { workspace: null, recent: [], error: ERR.saveValidation };
  }

  try {
    const raw = await apiRequest("/api/folders", {
      method: "PUT",
      body: JSON.stringify({
        workspace_id: workspaceId,
        path: next.path,
        displayName: next.displayName,
      }),
    });
    return { ...parseFolderPayload(raw), error: null };
  } catch {
    return { workspace: null, recent: [], error: ERR.saveStorage };
  }
}

/** Switch active folder to an already-known recent path (no OS picker). */
export async function activateRecentWorkspace(
  workspaceId: string,
  path: string,
): Promise<{ workspace: LocalWorkspace | null; recent: LocalWorkspace[]; error: string | null }> {
  const key = normalizeWorkspaceKey(path);
  if (!key) {
    return { workspace: null, recent: [], error: ERR.saveValidation };
  }
  try {
    const raw = await apiRequest("/api/folders/activate", {
      method: "POST",
      body: JSON.stringify({
        workspace_id: workspaceId,
        path: key,
      }),
    });
    return { ...parseFolderPayload(raw), error: null };
  } catch {
    return { workspace: null, recent: [], error: ERR.saveStorage };
  }
}
