import { describe, expect, it } from "vitest";
import { composerSkills } from "./composerSkills";
import { liaraServiceConsoleUrl } from "./liaraLinks";

describe("composer skills + liara links", () => {
  it("exposes a small set of starter skills", () => {
    expect(composerSkills("fa")).toHaveLength(3);
    expect(composerSkills("fa").every((skill) => skill.prompt.length > 0)).toBe(true);
  });

  it("builds a console URL for a Liara app", () => {
    expect(liaraServiceConsoleUrl("demo-api")).toBe("https://console.liara.ir/apps/demo-api");
  });
});
