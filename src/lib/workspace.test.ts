import { afterEach, describe, expect, it, vi } from "vitest";
import {
  activateRecentWorkspace,
  folderDisplayName,
  loadLocalWorkspace,
  normalizeWorkspaceKey,
  saveLocalWorkspace,
} from "./workspace";

const workspaceId = "11111111-1111-1111-1111-111111111111";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("local workspace helpers", () => {
  it("normalizes trailing separators and derives display names", () => {
    expect(normalizeWorkspaceKey("/Users/me/app/")).toBe("/Users/me/app");
    expect(normalizeWorkspaceKey("C:\\proj\\\\")).toBe("C:\\proj");
    expect(folderDisplayName("/Users/me/liara-agent")).toBe("liara-agent");
  });
});

describe("local workspace API", () => {
  it("round-trips selected folder through the companion database", async () => {
    const payload = {
      workspace: {
        version: 1,
        path: "/Users/me/demo",
        displayName: "demo",
      },
      recent: [
        {
          version: 1,
          path: "/Users/me/demo",
          displayName: "demo",
        },
      ],
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_input: RequestInfo, init?: RequestInit) => {
        if (init?.method === "PUT" || init?.method === "POST") {
          return new Response(JSON.stringify(payload), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response(JSON.stringify(payload), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }),
    );

    const saved = await saveLocalWorkspace(workspaceId, {
      version: 1,
      path: "/Users/me/demo/",
      displayName: "demo",
    });
    expect(saved.error).toBeNull();
    expect(saved.workspace?.path).toBe("/Users/me/demo");

    const loaded = await loadLocalWorkspace(workspaceId);
    expect(loaded.workspace?.displayName).toBe("demo");
    expect(loaded.recent).toHaveLength(1);

    const activated = await activateRecentWorkspace(workspaceId, "/Users/me/demo");
    expect(activated.workspace?.path).toBe("/Users/me/demo");
  });

  it("surfaces database outages in Persian", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new Error("down");
      }),
    );
    expect((await loadLocalWorkspace(workspaceId)).error).toMatch(/پایگاه/);
  });
});
