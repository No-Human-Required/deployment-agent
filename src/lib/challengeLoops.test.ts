import { describe, expect, it } from "vitest";
import {
  CHALLENGE_LOOP_CATALOG,
  catalogEntry,
  extractProjectNameFromGoal,
  resolveChallengeLoopRoute,
} from "./challengeLoops";
import { buildPlanPayloads, resolveIntakeKind } from "./intake";
import {
  createPlanResultSchema,
  evidencePackSchema,
  fixOptionsPayloadSchema,
  liaraDomainsResultSchema,
  maintainIncidentsResultSchema,
  monitorStatusSchema,
} from "./schemas";

describe("challenge loop inventory", () => {
  it("covers all challenge.md capability areas", () => {
    const areas = CHALLENGE_LOOP_CATALOG.map((row) => row.area).sort();
    expect(areas).toEqual(
      ["domains", "monitor_maintain", "ops", "setup_deploy", "troubleshoot"].sort(),
    );
    expect(catalogEntry("domains").clientApis.some((api) => api.includes("/domains"))).toBe(
      true,
    );
    expect(catalogEntry("setup_deploy").hitlWrites).toBe(true);
    expect(catalogEntry("monitor_maintain").hitlWrites).toBe(false);
  });
});

describe("challenge loop routing", () => {
  it("keeps greetings conversational without drafting a plan", () => {
    expect(resolveChallengeLoopRoute("سلام")).toEqual({ mode: "conversation" });
    expect(resolveChallengeLoopRoute("Hello!")).toEqual({ mode: "conversation" });
    expect(resolveChallengeLoopRoute("Deploy my Node app to Liara").mode).not.toBe(
      "conversation",
    );
  });

  it("routes deploy and domain through GenUI intake (HITL later)", () => {
    expect(resolveChallengeLoopRoute("Deploy my Node app to Liara")).toEqual({
      area: "setup_deploy",
      mode: "intake",
      intakeKind: "deploy",
      projectHint: undefined,
    });
    // Common informal Persian spelling without ی after د
    expect(resolveChallengeLoopRoute("سلام من میخوام دپلوی کنم")).toEqual({
      area: "setup_deploy",
      mode: "intake",
      intakeKind: "deploy",
      projectHint: undefined,
    });
    expect(resolveChallengeLoopRoute("Attach a custom domain to service web-app")).toMatchObject({
      area: "domains",
      mode: "intake",
      intakeKind: "domain",
      projectHint: "web-app",
    });
    expect(resolveIntakeKind("Resize the api plan")).toBe("ops_resize");
    expect(
      buildPlanPayloads({
        kind: "ops_resize",
        project_name: "api",
        plan_id: "g2",
      }).ops,
    ).toEqual({ kind: "resize", project_name: "api", plan_id: "g2" });
  });

  it("extracts project from Investigate CTA and skips intake", () => {
    expect(extractProjectNameFromGoal("Investigate service demo-api")).toBe("demo-api");
    expect(extractProjectNameFromGoal("بررسی وضعیت سرویس my-app")).toBe("my-app");

    expect(resolveChallengeLoopRoute("Investigate service demo-api")).toEqual({
      area: "troubleshoot",
      mode: "troubleshoot",
      projectName: "demo-api",
    });
    expect(
      resolveChallengeLoopRoute("Investigate HTTP 500 errors", {
        selectedServiceId: "from-nav",
      }),
    ).toEqual({
      area: "troubleshoot",
      mode: "troubleshoot",
      projectName: "from-nav",
    });
    expect(resolveChallengeLoopRoute("Investigate HTTP 500 errors")).toEqual({
      area: "troubleshoot",
      mode: "intake",
      intakeKind: "troubleshoot",
    });
  });

  it("routes composer deploy-check / status prompts to troubleshoot (not deploy)", () => {
    expect(
      resolveChallengeLoopRoute("وضعیت آخرین استقرار و سلامت سرویس را بررسی کن"),
    ).toEqual({
      area: "troubleshoot",
      mode: "intake",
      intakeKind: "troubleshoot",
    });
    expect(
      resolveChallengeLoopRoute("Check the latest deployment and service health", {
        selectedServiceId: "shop-api",
      }),
    ).toEqual({
      area: "troubleshoot",
      mode: "troubleshoot",
      projectName: "shop-api",
    });
  });

  it("routes maintain monitor CTA to enable path (or service intake)", () => {
    expect(
      resolveChallengeLoopRoute("Enable a maintain monitor for this workspace", {
        selectedServiceId: "health-app",
      }),
    ).toEqual({
      area: "monitor_maintain",
      mode: "maintain_monitor",
      target: "health-app",
    });
    expect(resolveChallengeLoopRoute("Enable a maintain monitor for this workspace")).toEqual({
      area: "monitor_maintain",
      mode: "intake",
      intakeKind: "maintain_monitor",
    });
  });
});

describe("challenge loop client contracts", () => {
  it("locks deploy plan, domains list, maintain incidents, evidence, fix, monitor shapes", () => {
    const plan = createPlanResultSchema.parse({
      plan_id: "33333333-3333-3333-3333-333333333333",
      version: 1,
      content_hash: "abcdef0123456789",
      body: {
        version: 1,
        steps: [
          {
            id: "s1",
            action: "prepare_deploy_stub",
            tool_id: "create_project",
            effects: [],
            cost_known: false,
            params: { project_name: "demo", app_path: "/tmp/app" },
          },
        ],
        effects: [],
        cost_known: false,
        summary: "Deploy plan",
      },
    });
    expect(plan.body.steps[0]?.params?.app_path).toBe("/tmp/app");

    expect(
      liaraDomainsResultSchema.parse({
        domains: [{ id: "d1", name: "example.com" }],
        project: "demo",
        source: "liara_domains",
      }).domains,
    ).toHaveLength(1);

    expect(
      maintainIncidentsResultSchema.parse({
        incidents: [
          {
            incident_id: "11111111-1111-4111-8111-111111111111",
            status: "open",
            title: "Missed checks",
            alert_count: 1,
            write_authorized: false,
          },
        ],
      }).incidents[0]?.write_authorized,
    ).toBe(false);

    const evidence = evidencePackSchema.parse({
      version: "ev-20261023a",
      project_name: "demo",
      collected_at: "2026-10-23T12:00:00.000Z",
      facts: [{ id: "f1", source: "logs", summary: "stderr spike", stale: false }],
      gaps: [],
      sanitized_log_excerpts: ["ERROR boom"],
      complete: true,
    });
    expect(evidence.project_name).toBe("demo");

    const fixes = fixOptionsPayloadSchema.parse({
      diagnosis_version: "dx-20261023a",
      evidence_version: evidence.version,
      options: [
        {
          id: "restart",
          tool_id: "restart_resize",
          label: "Restart",
          rationale: "Process stuck",
          enabled: true,
          params: { project_name: "demo" },
        },
      ],
      open_needs: [],
    });
    expect(fixes.options[0]?.enabled).toBe(true);

    const monitor = monitorStatusSchema.parse({
      monitor_id: "mon-1",
      target: "demo",
      enabled: true,
      last_status: "never",
      grants_write_permission: false,
    });
    expect(monitor.grants_write_permission).toBe(false);

    expect(
      buildPlanPayloads({
        kind: "deploy",
        project_name: "demo",
        plan_id: "free",
        app_path: "/Users/me/app",
      }).deploy,
    ).toEqual({
      project_name: "demo",
      plan_id: "free",
      app_path: "/Users/me/app",
    });
  });
});
