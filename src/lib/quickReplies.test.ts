import { describe, expect, it } from "vitest";
import {
  approvalReplies,
  conversationIntentReplies,
  fixOptionReplies,
  generativeAwaitingUser,
  intakeServiceReplies,
  whatNextReplies,
} from "./quickReplies";

describe("quickReplies", () => {
  it("offers conversational intents in FA", () => {
    const replies = conversationIntentReplies("fa");
    expect(replies.length).toBeGreaterThanOrEqual(3);
    expect(replies.every((item) => item.kind === "prompt" && item.prompt)).toBe(true);
  });

  it("keeps HITL approve/reject as explicit controls", () => {
    expect(approvalReplies("fa").map((item) => item.kind)).toEqual(["approve", "reject"]);
  });

  it("exposes what-next chips after terminal plain messages", () => {
    expect(whatNextReplies("fa").length).toBeGreaterThanOrEqual(3);
    expect(generativeAwaitingUser("awaiting_approval")).toBe(true);
    expect(generativeAwaitingUser("awaiting_intake")).toBe(true);
    expect(generativeAwaitingUser("verified")).toBe(false);
    expect(generativeAwaitingUser("rejected")).toBe(false);
  });

  it("maps services and enabled fix options to chips", () => {
    expect(
      intakeServiceReplies(
        [
          { id: "a", name: "api" },
          { id: "b", name: "web" },
        ],
        "en",
      ).map((item) => item.value),
    ).toEqual(["api", "web"]);

    expect(
      fixOptionReplies([
        { id: "1", label: "Restart", enabled: true },
        { id: "2", label: "Blocked", enabled: false },
      ]),
    ).toEqual([{ id: "fix-1", kind: "fix", label: "Restart", value: "1" }]);
  });
});
