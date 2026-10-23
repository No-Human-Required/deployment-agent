import { describe, expect, it } from "vitest";
import { serviceStatusTone, serviceStatusToneLabel } from "./serviceStatus";

describe("serviceStatusTone", () => {
  it("maps online statuses case-insensitively", () => {
    for (const status of ["RUNNING", "started", "Ready", "ACTIVE"]) {
      expect(serviceStatusTone(status)).toBe("online");
    }
  });

  it("maps error statuses including CRASHED", () => {
    for (const status of ["FAILED", "error", "CRASH", "crashed"]) {
      expect(serviceStatusTone(status)).toBe("error");
    }
  });

  it("maps STOPPED to stopped", () => {
    expect(serviceStatusTone("STOPPED")).toBe("stopped");
    expect(serviceStatusTone("stopped")).toBe("stopped");
  });

  it("returns unknown for unrecognized explicit status", () => {
    expect(serviceStatusTone("BUILDING")).toBe("unknown");
    expect(serviceStatusTone("unknown")).toBe("unknown");
  });

  it("prefers explicit status over isDeployed", () => {
    expect(serviceStatusTone("STOPPED", true)).toBe("stopped");
    expect(serviceStatusTone("FAILED", true)).toBe("error");
    expect(serviceStatusTone("RUNNING", false)).toBe("online");
  });

  it("leans online from isDeployed only when status is absent", () => {
    expect(serviceStatusTone("", true)).toBe("online");
    expect(serviceStatusTone(null, true)).toBe("online");
    expect(serviceStatusTone(undefined, true)).toBe("online");
    expect(serviceStatusTone("  ", true)).toBe("online");
    expect(serviceStatusTone("", false)).toBe("unknown");
    expect(serviceStatusTone(null, null)).toBe("unknown");
  });

  it("treats catalog deployed placeholder as online-leaning", () => {
    expect(serviceStatusTone("deployed")).toBe("online");
    expect(serviceStatusTone("DEPLOYED")).toBe("online");
  });
});

describe("serviceStatusToneLabel", () => {
  it("returns FA and EN labels", () => {
    expect(serviceStatusToneLabel("online", "en")).toBe("Online");
    expect(serviceStatusToneLabel("online", "fa")).toBe("آنلاین");
    expect(serviceStatusToneLabel("error", "fa")).toBe("خطا");
    expect(serviceStatusToneLabel("stopped", "en")).toBe("Stopped");
    expect(serviceStatusToneLabel("unknown", "fa")).toBe("نامشخص");
  });
});
