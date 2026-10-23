/**
 * Client-only UI preferences (localStorage). Not workspace/server secrets.
 */

const STORAGE_KEY = "liara-agent.ui-preferences.v1";

export type UiPreferences = {
  /** Restore last open conversation after a full page refresh. */
  resumeConversationOnRefresh: boolean;
  /** Show in-chat quick-reply chips when appropriate. */
  quickRepliesEnabled: boolean;
  /** Last active conversation id for resume-on-refresh. */
  lastConversationId: string | null;
};

const DEFAULTS: UiPreferences = {
  resumeConversationOnRefresh: true,
  quickRepliesEnabled: true,
  lastConversationId: null,
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export function loadUiPreferences(): UiPreferences {
  if (typeof window === "undefined") return { ...DEFAULTS };
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULTS };
    const parsed: unknown = JSON.parse(raw);
    if (!isRecord(parsed)) return { ...DEFAULTS };
    return {
      resumeConversationOnRefresh:
        typeof parsed.resumeConversationOnRefresh === "boolean"
          ? parsed.resumeConversationOnRefresh
          : DEFAULTS.resumeConversationOnRefresh,
      quickRepliesEnabled:
        typeof parsed.quickRepliesEnabled === "boolean"
          ? parsed.quickRepliesEnabled
          : DEFAULTS.quickRepliesEnabled,
      lastConversationId:
        typeof parsed.lastConversationId === "string" && parsed.lastConversationId.trim()
          ? parsed.lastConversationId.trim()
          : null,
    };
  } catch {
    return { ...DEFAULTS };
  }
}

export function saveUiPreferences(next: UiPreferences): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    // Quota / private mode — ignore; prefs stay in-memory for the session.
  }
}

export function patchUiPreferences(patch: Partial<UiPreferences>): UiPreferences {
  const next = { ...loadUiPreferences(), ...patch };
  saveUiPreferences(next);
  return next;
}
