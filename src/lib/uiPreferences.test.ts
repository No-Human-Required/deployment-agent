import { afterEach, describe, expect, it, vi } from "vitest";
import { loadUiPreferences, patchUiPreferences, saveUiPreferences } from "./uiPreferences";

function stubLocalStorage() {
  const store = new Map<string, string>();
  vi.stubGlobal("window", {
    localStorage: {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => {
        store.set(key, value);
      },
      clear: () => store.clear(),
    },
  });
  return store;
}

describe("uiPreferences", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("defaults to resume + quick replies enabled", () => {
    stubLocalStorage();
    expect(loadUiPreferences()).toEqual({
      resumeConversationOnRefresh: true,
      quickRepliesEnabled: true,
      lastConversationId: null,
    });
  });

  it("persists patches", () => {
    stubLocalStorage();
    const next = patchUiPreferences({
      resumeConversationOnRefresh: false,
      lastConversationId: "c-1",
    });
    expect(next.resumeConversationOnRefresh).toBe(false);
    expect(next.lastConversationId).toBe("c-1");
    expect(loadUiPreferences().lastConversationId).toBe("c-1");
    saveUiPreferences({
      resumeConversationOnRefresh: true,
      quickRepliesEnabled: false,
      lastConversationId: null,
    });
    expect(loadUiPreferences().quickRepliesEnabled).toBe(false);
  });
});
