import { describe, expect, it } from "vitest";
import {
  enrichPlatformOptions,
  LIARA_PLATFORMS,
  suggestLiaraPlatform,
  suggestServiceNameFromPackage,
  suggestServiceNameFromPath,
} from "./liaraPlatforms";

describe("liaraPlatforms", () => {
  it("exposes Liara icons for every catalog platform", () => {
    expect(LIARA_PLATFORMS.length).toBeGreaterThanOrEqual(10);
    for (const row of LIARA_PLATFORMS) {
      expect(row.icon.length).toBeGreaterThan(8);
      expect(
        row.icon.startsWith("data:image/svg+xml") ||
          row.icon.includes("platform-icons") ||
          row.icon.endsWith(".svg"),
      ).toBe(true);
    }
  });

  it("enrichPlatformOptions fills missing icons from catalog", () => {
    const enriched = enrichPlatformOptions([{ id: "node", label: "NodeJS" }]);
    expect(enriched[0]?.icon).toBeTruthy();
    expect(enriched[0]?.icon.length).toBeGreaterThan(8);
  });

  it("maps readiness next/nodejs to Liara platform ids", () => {
    expect(suggestLiaraPlatform({ readinessPlatform: "next" }).id).toBe("next");
    expect(suggestLiaraPlatform({ readinessPlatform: "nodejs" }).id).toBe("node");
    expect(suggestLiaraPlatform({ readinessPlatform: null }).id).toBe("node");
  });

  it("prefers package.json name for new service id", () => {
    expect(suggestServiceNameFromPackage("@scope/Interview Flow", "/tmp/x")).toBe(
      "interview-flow",
    );
    expect(suggestServiceNameFromPath("/Users/me/Projects/Interview Flow")).toBe(
      "interview-flow",
    );
  });
});
