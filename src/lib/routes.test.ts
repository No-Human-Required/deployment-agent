import { describe, expect, it } from "vitest";
import { appRoutePath, parseAppRoute } from "./routes";

describe("app routes", () => {
  it("parses chat and settings paths", () => {
    expect(parseAppRoute("/")).toEqual({ kind: "chat", conversationId: null });
    expect(parseAppRoute("/chat")).toEqual({ kind: "chat", conversationId: null });
    expect(parseAppRoute("/chat/new")).toEqual({ kind: "chat", conversationId: null });
    expect(parseAppRoute("/chat/abc-123")).toEqual({ kind: "chat", conversationId: "abc-123" });
    expect(parseAppRoute("/settings")).toEqual({ kind: "settings" });
  });

  it("builds stable pathnames", () => {
    expect(appRoutePath({ kind: "chat", conversationId: null })).toBe("/");
    expect(appRoutePath({ kind: "chat", conversationId: "c1" })).toBe("/chat/c1");
    expect(appRoutePath({ kind: "settings" })).toBe("/settings");
  });
});
