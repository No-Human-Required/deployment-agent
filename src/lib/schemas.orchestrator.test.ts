import { describe, expect, it } from "vitest";
import {
  createPlanResultSchema,
  operationPayloadSchema,
  orchestratorCaseSchema,
  orchestratorRunSchema,
  readinessAssessmentSchema,
} from "./schemas";

describe("companion orchestrator schemas", () => {
  it("parses case, readiness, plan, and operation shapes", () => {
    const caseRow = orchestratorCaseSchema.parse({
      id: "11111111-1111-1111-1111-111111111111",
      workspace_id: "22222222-2222-2222-2222-222222222222",
      goal: "Deploy demo",
    });
    expect(caseRow.goal).toBe("Deploy demo");

    const readiness = readinessAssessmentSchema.parse({
      ready: true,
      open_needs: ["llm_stub_mode"],
      notes: "deterministic stub mode",
      findings: [],
    });
    expect(readiness.ready).toBe(true);

    const plan = createPlanResultSchema.parse({
      plan_id: "33333333-3333-3333-3333-333333333333",
      version: 1,
      content_hash: "abcdef0123456789",
      body: {
        version: 1,
        steps: [
          {
            id: "step-1",
            action: "prepare_deploy_stub",
            tool_id: "create_project",
            effects: ["would_create_project"],
            cost_known: false,
            params: {},
          },
        ],
        effects: ["would_create_project"],
        cost_known: false,
        summary: "Stub plan",
      },
    });
    expect(plan.body.steps).toHaveLength(1);

    const op = operationPayloadSchema.parse({
      id: "44444444-4444-4444-4444-444444444444",
      state: "verified_stub",
      fingerprints: [],
      client_request_id: "req-1",
      plan_id: plan.plan_id,
      case_id: caseRow.id,
      checkpoint: { verify_mode: "stub" },
    });
    expect(op.state).toBe("verified_stub");
  });

  it("parses orchestrator run awaiting approval without secret fields", () => {
    const run = orchestratorRunSchema.parse({
      case_id: "11111111-1111-1111-1111-111111111111",
      workspace_id: "22222222-2222-2222-2222-222222222222",
      goal: "Investigate HTTP 500",
      stage: "awaiting_approval",
      summary: "Plan ready for approval",
      plan_id: "33333333-3333-3333-3333-333333333333",
      content_hash: "abcdef0123456789",
      plan_body: {
        version: 1,
        steps: [{ id: "s1", action: "stub", effects: [], cost_known: false, params: {} }],
        effects: [],
        cost_known: false,
        summary: "Stub",
      },
      timeline: [
        { title: "Case created", detail: "ok", tool: "create_case", status: "done" },
        { title: "Awaiting approval", detail: "HITL", tool: "approve_plan", status: "waiting" },
      ],
      events: [{ time: "2026-10-23T07:00:00.000Z", event: "create_plan", actor: "orchestrator" }],
    });
    expect(run.stage).toBe("awaiting_approval");
    expect(JSON.stringify(run)).not.toMatch(/sk-|Bearer|api_token|llm_api_key/i);
  });

  it("rejects empty plan steps", () => {
    const result = createPlanResultSchema.safeParse({
      plan_id: "33333333-3333-3333-3333-333333333333",
      version: 1,
      content_hash: "abcdef0123456789",
      body: { version: 1, steps: [], effects: [], cost_known: false },
    });
    expect(result.success).toBe(false);
  });
});
