import { describe, expect, it } from "vitest";
import {
  buildPlanPayloads,
  intakeKindForGoalIntent,
  intakeRequirements,
  needsIntake,
  resolveIntakeKind,
  toIntakeViewPayload,
} from "./intake";
import { knownViewPayloadSchema } from "./schemas";
import { inferGoalIntent } from "./requestTimeline";

describe("GenUI intake helpers", () => {
  it("requires intake for deploy, domain, resize, troubleshoot, maintain — not pure Q&A", () => {
    expect(needsIntake("Deploy my Node app to Liara")).toBe(true);
    expect(needsIntake("استقرار اولین نسخه")).toBe(true);
    expect(needsIntake("Connect example.com to my service")).toBe(true);
    expect(needsIntake("اتصال دامنه example.com")).toBe(true);
    expect(needsIntake("Resize the api plan")).toBe(true);
    expect(needsIntake("تغییر پلن سرویس")).toBe(true);
    expect(needsIntake("Investigate HTTP 500 errors")).toBe(true);
    expect(needsIntake("Enable a maintain monitor for this workspace")).toBe(true);

    expect(needsIntake("What is my account balance?")).toBe(false);
    expect(needsIntake("سلام، چطور کمکتون کنم؟")).toBe(false);
  });

  it("aligns intake kind with goal intent heuristics", () => {
    expect(resolveIntakeKind("first deploy setup")).toBe("deploy");
    expect(resolveIntakeKind("attach domain ssl")).toBe("domain");
    expect(resolveIntakeKind("resize plan for api")).toBe("ops_resize");
    expect(resolveIntakeKind("Investigate HTTP 500 errors")).toBe("troubleshoot");
    expect(resolveIntakeKind("Enable a maintain monitor")).toBe("maintain_monitor");

    expect(intakeKindForGoalIntent(inferGoalIntent("deploy now"), "deploy now")).toBe("deploy");
    expect(intakeKindForGoalIntent(inferGoalIntent("health check"), "health check")).toBe(
      "maintain_monitor",
    );
  });

  it("builds deploy payload with workspace app_path and platform", () => {
    const payloads = buildPlanPayloads({
      kind: "deploy",
      project_name: "my-app",
      plan_id: "free",
      platform: "node",
      app_path: "/Users/me/project",
    });
    expect(payloads.deploy).toEqual({
      project_name: "my-app",
      plan_id: "free",
      platform: "node",
      app_path: "/Users/me/project",
    });
    expect(payloads.ops).toBeUndefined();
    expect(payloads.deps).toBeUndefined();
  });

  it("marks deploy intake as prefer-new-service with platform required", () => {
    expect(intakeRequirements("deploy")).toEqual({
      require_plan: true,
      require_domain: false,
      require_platform: true,
      prefer_new_service: true,
    });
  });

  it("builds domain and resize ops payloads without inventing app_path", () => {
    expect(
      buildPlanPayloads({
        kind: "domain",
        project_name: "web",
        domain_name: "example.com",
        app_path: "/ignored-for-domain",
      }).ops,
    ).toEqual({
      kind: "domain",
      project_name: "web",
      domain_name: "example.com",
      provision_ssl: true,
    });

    expect(
      buildPlanPayloads({
        kind: "ops_resize",
        project_name: "api",
        plan_id: "g2",
      }).ops,
    ).toEqual({
      kind: "resize",
      project_name: "api",
      plan_id: "g2",
    });
  });

  it("maps intake draft to a strict GenUI card payload", () => {
    const payload = toIntakeViewPayload(
      {
        kind: "deploy",
        services: [{ id: "svc-1", name: "svc-1", status: "running" }],
        plans: [{ id: "free", label: "Free", hint: "shared" }],
        require_plan: true,
        require_domain: false,
        load_error: null,
      },
      "en",
    );
    const parsed = knownViewPayloadSchema.parse(payload);
    expect(parsed.type).toBe("intake");
    if (parsed.type === "intake") {
      expect(parsed.data.kind).toBe("deploy");
      expect(parsed.data.require_plan).toBe(true);
      expect(parsed.data.services).toHaveLength(1);
      expect(parsed.data.settings_cta).toBe(false);
    }
  });

  it("flags settings CTA when catalog load failed", () => {
    const payload = toIntakeViewPayload(
      {
        kind: "domain",
        services: [],
        plans: [],
        require_plan: false,
        require_domain: true,
        load_error: "token missing",
      },
      "fa",
    );
    expect(payload.data.settings_cta).toBe(true);
    expect(knownViewPayloadSchema.parse(payload).type).toBe("intake");
  });
});
