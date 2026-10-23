import { describe, expect, it } from "vitest";
import {
  activateRecentWorkspace,
  folderDisplayName,
  listRecentWorkspaces,
  loadLocalWorkspace,
  LOCAL_WORKSPACE_STORAGE_KEY,
  normalizeWorkspaceKey,
  saveLocalWorkspace,
} from "./workspace";

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

describe("local workspace persistence", () => {
  it("normalizes trailing separators and derives display names", () => {
    expect(normalizeWorkspaceKey("/Users/me/app/")).toBe("/Users/me/app");
    expect(normalizeWorkspaceKey("C:\\proj\\\\")).toBe("C:\\proj");
    expect(folderDisplayName("/Users/me/liara-agent")).toBe("liara-agent");
  });

  it("round-trips selected folder across reloads", () => {
    const storage = new MemoryStorage();
    expect(
      saveLocalWorkspace(storage, {
        version: 1,
        path: "/Users/me/demo/",
        displayName: "demo",
      }),
    ).toBeNull();

    expect(loadLocalWorkspace(storage)).toEqual({
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
      error: null,
    });
  });

  it("keeps multiple recent folders and can switch active", () => {
    const storage = new MemoryStorage();
    saveLocalWorkspace(storage, { version: 1, path: "/a/one", displayName: "one" });
    saveLocalWorkspace(storage, { version: 1, path: "/a/two", displayName: "two" });

    const recent = listRecentWorkspaces(storage);
    expect(recent.map((item) => item.path)).toEqual(["/a/two", "/a/one"]);
    expect(loadLocalWorkspace(storage).workspace?.path).toBe("/a/two");

    const switched = activateRecentWorkspace(storage, "/a/one");
    expect(switched.error).toBeNull();
    expect(switched.workspace?.path).toBe("/a/one");
    expect(loadLocalWorkspace(storage).workspace?.path).toBe("/a/one");
    expect(listRecentWorkspaces(storage)[0]?.path).toBe("/a/one");
  });

  it("migrates legacy v1 single-object blobs", () => {
    const storage = new MemoryStorage();
    storage.setItem(
      LOCAL_WORKSPACE_STORAGE_KEY,
      JSON.stringify({ version: 1, path: "/legacy/app", displayName: "app" }),
    );
    const loaded = loadLocalWorkspace(storage);
    expect(loaded.workspace?.path).toBe("/legacy/app");
    expect(loaded.recent).toHaveLength(1);
  });

  it("clears unreadable blobs", () => {
    const storage = new MemoryStorage();
    storage.setItem(LOCAL_WORKSPACE_STORAGE_KEY, "{bad");
    const loaded = loadLocalWorkspace(storage);
    expect(loaded.workspace).toBeNull();
    expect(loaded.error).toMatch(/قابل خواندن نبود/);
    expect(storage.getItem(LOCAL_WORKSPACE_STORAGE_KEY)).toBeNull();
  });
});
