import { afterEach, describe, expect, it, vi } from "vitest";
import {
  findConversationInHistory,
  loadAllConversationHistory,
  loadConversationHistory,
  normalizeConversationList,
  saveConversationHistory,
  type Conversation,
} from "./conversations";

const folderA = "/Users/me/project-a";
const folderB = "/Users/me/project-b";
const workspaceId = "11111111-1111-1111-1111-111111111111";

function conversation(id = "conversation-1", title = "بررسی خطای HTTP 500"): Conversation {
  return {
    id,
    title,
    serviceId: "atlas-api",
    contextServices: [{ id: "atlas-api", name: "atlas-api" }],
    messages: [{ id: "message-1", role: "user", text: title }],
    updatedAt: "2026-10-23T07:00:00.000Z",
    orchestratorRun: null,
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("conversation normalization", () => {
  it("drops invalid orchestrator runs", () => {
    const [normalized] = normalizeConversationList([
      { ...conversation(), orchestratorRun: { unsafe: true } },
    ]);
    expect(normalized?.orchestratorRun).toBeNull();
  });

  it("caps lists at 8", () => {
    const list = Array.from({ length: 10 }, (_, i) => conversation(`c${i}`, `t${i}`));
    expect(normalizeConversationList(list)).toHaveLength(8);
  });
});

describe("conversation history API", () => {
  it("loads folder-scoped history from the companion database", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo) => {
        const url = String(input);
        expect(url).toContain("folder_key=");
        return new Response(
          JSON.stringify({ conversations: [conversation()] }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }),
    );

    await expect(loadConversationHistory(workspaceId, folderA)).resolves.toEqual({
      conversations: [conversation()],
      error: null,
    });
    await expect(loadConversationHistory(workspaceId, null)).resolves.toEqual({
      conversations: [],
      error: null,
    });
  });

  it("saves and finds conversations via API", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === "PUT") {
        return new Response(
          JSON.stringify({ conversations: [conversation("a1", "الف")] }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (url.includes("/by-id/")) {
        return new Response(
          JSON.stringify({
            workspaceKey: folderB,
            conversation: conversation("b1", "ب"),
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (url.includes("all_folders=true")) {
        return new Response(
          JSON.stringify({
            byWorkspace: {
              [folderA]: [conversation("a1", "الف")],
              [folderB]: [conversation("b1", "ب")],
            },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      return new Response("{}", { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);

    expect(await saveConversationHistory(workspaceId, folderA, [conversation("a1", "الف")])).toBeNull();
    expect(await findConversationInHistory(workspaceId, "b1")).toEqual({
      workspaceKey: folderB,
      conversation: conversation("b1", "ب"),
    });
    const all = await loadAllConversationHistory(workspaceId);
    expect(Object.keys(all.byWorkspace).sort()).toEqual([folderA, folderB].sort());
  });

  it("surfaces database outages in Persian", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new Error("network down");
      }),
    );

    expect((await loadConversationHistory(workspaceId, folderA)).error).toMatch(/پایگاه/);
    expect(await saveConversationHistory(workspaceId, folderA, [conversation()])).toMatch(/پایگاه/);
  });
});
