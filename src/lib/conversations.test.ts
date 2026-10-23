import { describe, expect, it } from "vitest";
import {
  findConversationInHistory,
  loadAllConversationHistory,
  loadConversationHistory,
  saveConversationHistory,
  UNSCOPED_CONVERSATION_KEY,
  type Conversation,
} from "./conversations";

const key = "liaraops-ai:conversation-history";
const folderA = "/Users/me/project-a";
const folderB = "/Users/me/project-b";

class MemoryStorage {
  private values = new Map<string, string>();

  getItem(name: string) {
    return this.values.get(name) ?? null;
  }

  setItem(name: string, value: string) {
    this.values.set(name, value);
  }

  removeItem(name: string) {
    this.values.delete(name);
  }
}

function conversation(id = "conversation-1", title = "بررسی خطای HTTP 500"): Conversation {
  return {
    id,
    title,
    serviceId: "atlas-api",
    messages: [{ id: "message-1", role: "user", text: title }],
    updatedAt: "2026-10-23T07:00:00.000Z",
    orchestratorRun: null,
  };
}

describe("conversation history", () => {
  it("round-trips validated history scoped to a workspace folder", () => {
    const storage = new MemoryStorage();
    const original = [conversation()];

    expect(saveConversationHistory(storage, folderA, original)).toBeNull();
    expect(loadConversationHistory(storage, folderA)).toEqual({
      conversations: original,
      error: null,
    });
    expect(loadConversationHistory(storage, folderB)).toEqual({
      conversations: [],
      error: null,
    });
    expect(loadConversationHistory(storage, null)).toEqual({
      conversations: [],
      error: null,
    });
  });

  it("keeps separate lists when switching folders", () => {
    const storage = new MemoryStorage();
    const a = [conversation("a1", "چت فولدر آ")];
    const b = [conversation("b1", "چت فولدر ب")];

    expect(saveConversationHistory(storage, `${folderA}/`, a)).toBeNull();
    expect(saveConversationHistory(storage, folderB, b)).toBeNull();

    expect(loadConversationHistory(storage, folderA).conversations.map((c) => c.id)).toEqual(["a1"]);
    expect(loadConversationHistory(storage, folderB).conversations.map((c) => c.id)).toEqual(["b1"]);
  });

  it("clears unreadable JSON so the app can start fresh", () => {
    const storage = new MemoryStorage();
    storage.setItem(key, "{not-json");

    const loaded = loadConversationHistory(storage, folderA);

    expect(loaded.conversations).toEqual([]);
    expect(loaded.error).toMatch(/قابل خواندن نبود/);
    expect(storage.getItem(key)).toBeNull();
  });

  it("migrates legacy flat v1 stores into an unscoped bucket", () => {
    const storage = new MemoryStorage();
    storage.setItem(
      key,
      JSON.stringify({
        version: 1,
        conversations: [
          {
            id: "c1",
            title: "قدیمی",
            serviceId: "svc",
            messages: [{ id: "m1", role: "user", text: "سلام" }],
            updatedAt: "2026-10-23T07:00:00.000Z",
          },
        ],
      }),
    );

    const forFolder = loadConversationHistory(storage, folderA);
    expect(forFolder.error).toBeNull();
    expect(forFolder.conversations).toEqual([]);

    const raw = JSON.parse(storage.getItem(key) ?? "{}") as {
      version: number;
      byWorkspace: Record<string, Conversation[]>;
    };
    expect(raw.version).toBe(3);
    expect(raw.byWorkspace[UNSCOPED_CONVERSATION_KEY]?.[0]?.id).toBe("c1");
  });

  it("drops invalid orchestrator runs on save", () => {
    const storage = new MemoryStorage();
    expect(
      saveConversationHistory(storage, folderA, [
        { ...conversation(), orchestratorRun: { unsafe: true } },
      ]),
    ).toBeNull();
    expect(loadConversationHistory(storage, folderA).conversations[0]?.orchestratorRun).toBeNull();
  });

  it("finds a conversation across folder buckets", () => {
    const storage = new MemoryStorage();
    saveConversationHistory(storage, folderA, [conversation("a1", "الف")]);
    saveConversationHistory(storage, folderB, [conversation("b1", "ب")]);

    expect(findConversationInHistory(storage, "b1")).toEqual({
      workspaceKey: folderB,
      conversation: conversation("b1", "ب"),
    });
    expect(findConversationInHistory(storage, "missing")).toBeNull();
    expect(Object.keys(loadAllConversationHistory(storage).byWorkspace).sort()).toEqual(
      [folderA, folderB].sort(),
    );
  });

  it("surfaces storage access and quota errors in Persian", () => {
    const unavailableStorage = {
      getItem() {
        throw new Error("storage disabled");
      },
      setItem() {
        throw new Error("quota exceeded");
      },
      removeItem() {
        throw new Error("quota exceeded");
      },
    };

    expect(loadConversationHistory(unavailableStorage, folderA).error).toMatch(/در دسترس نیست/);
    expect(saveConversationHistory(unavailableStorage, folderA, [conversation()])).toMatch(/ممکن نشد/);
  });
});
