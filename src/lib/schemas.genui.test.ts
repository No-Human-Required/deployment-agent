import { describe, expect, it } from "vitest";
import {
  companionCardFixtures,
  mapOrchestratorToCards,
  mapOrchestratorToChatCards,
} from "./orchestratorCards";
import {
  knownViewPayloadSchema,
  orchestratorRunSchema,
  viewPayloadSchema,
} from "./schemas";
import {
  assessReadinessPayload,
  planReadyAssistantText,
} from "./quietChat";

describe("GenUI view payload schemas", () => {
  it("accepts plan + approval + readiness + intake companion cards", () => {
    const plan = knownViewPayloadSchema.parse({
      type: "plan",
      data: {
        summary: "Stub plan",
        version: 1,
        steps: [{ id: "s1", action: "prepare_deploy_stub", tool_id: "create_project", effects: [] }],
        effects: ["would_create_project"],
        content_hash: "abcdef0123456789",
        case_id: "11111111-1111-1111-1111-111111111111",
        plan_id: "33333333-3333-3333-3333-333333333333",
      },
    });
    expect(plan.type).toBe("plan");

    const intake = knownViewPayloadSchema.parse({
      type: "intake",
      data: {
        kind: "deploy",
        title: "Choose service & plan",
        prompt: "Pick a service",
        services: [{ id: "app", name: "app", status: "RUNNING" }],
        plans: [{ id: "free", label: "Free" }],
        require_plan: true,
        require_domain: false,
      },
    });
    expect(intake.type).toBe("intake");

    const approval = knownViewPayloadSchema.parse({
      type: "approval",
      data: {
        action: "Execute stub plan",
        risk: "Writes require Approve",
        expires_at: "",
        execution_id: "33333333-3333-3333-3333-333333333333",
      },
    });
    expect(approval.type).toBe("approval");

    const readiness = knownViewPayloadSchema.parse({
      type: "readiness_findings",
      data: {
        ready: true,
        open_needs: ["llm_stub_mode"],
        notes: "deterministic stub mode",
        findings: [],
      },
    });
    expect(readiness.type).toBe("readiness_findings");
  });

  it("accepts companion fixture card kinds", () => {
    const types = companionCardFixtures.map((card) => card.type);
    expect(types).toEqual([
      "evidence_pack",
      "diagnosis",
      "dependency_plan",
      "patch_diff",
      "monitor_status",
      "incident",
    ]);
    for (const fixture of companionCardFixtures) {
      expect(knownViewPayloadSchema.parse(fixture).type).toBe(fixture.type);
    }
  });

  it("maps unknown types to unsupported without throwing", () => {
    const fallback = viewPayloadSchema.parse({
      type: "totally_unknown_card",
      data: { anything: true },
    });
    expect(fallback).toEqual({
      type: "unsupported",
      data: { originalType: "totally_unknown_card" },
    });
  });

  it("rejects garbage for known card shapes", () => {
    expect(
      knownViewPayloadSchema.safeParse({
        type: "plan",
        data: { steps: "not-an-array" },
      }).success,
    ).toBe(false);

    expect(
      knownViewPayloadSchema.safeParse({
        type: "diagnosis",
        data: { version: 12, evidence_version: null },
      }).success,
    ).toBe(false);

    expect(
      knownViewPayloadSchema.safeParse({
        type: "patch_diff",
        data: { rationale: "", unified_diff: "", content_hash: "short" },
      }).success,
    ).toBe(false);

    expect(
      knownViewPayloadSchema.safeParse({
        type: "monitor_status",
        data: { monitor_id: "", target: "", enabled: "yes" },
      }).success,
    ).toBe(false);
  });

  it("maps orchestrator run into readiness + plan + approval cards", () => {
    const run = orchestratorRunSchema.parse({
      case_id: "11111111-1111-1111-1111-111111111111",
      workspace_id: "22222222-2222-2222-2222-222222222222",
      goal: "Deploy demo",
      stage: "awaiting_approval",
      summary: "Plan ready",
      readiness: {
        ready: true,
        open_needs: [],
        notes: "ok",
        findings: [],
      },
      plan_id: "33333333-3333-3333-3333-333333333333",
      content_hash: "abcdef0123456789",
      plan_body: {
        version: 1,
        steps: [{
          id: "s1",
          action: "stub",
          tool_id: "create_case",
          effects: [],
          cost_known: false,
          params: {},
        }],
        effects: [],
        cost_known: false,
        summary: "Stub",
      },
      timeline: [],
      events: [],
    });

    const cards = mapOrchestratorToCards(run, "en");
    expect(cards.map((card) => card.type)).toEqual([
      "readiness_findings",
      "plan",
      "approval",
    ]);
    expect(JSON.stringify(cards)).not.toMatch(/sk-|Bearer|api_token|llm_api_key/i);
  });

  it("keeps chat cards quiet (no readiness / UUID / tool_id dump)", () => {
    const run = orchestratorRunSchema.parse({
      case_id: "11111111-1111-1111-1111-111111111111",
      workspace_id: "22222222-2222-2222-2222-222222222222",
      goal: "Deploy demo",
      stage: "awaiting_approval",
      summary: "Plan ready",
      readiness: {
        ready: true,
        open_needs: ["llm_stub_mode"],
        notes: "پرونده=11111111-1111-1111-1111-111111111111؛ مدل زبانی آماده است",
        findings: [],
      },
      plan_id: "33333333-3333-3333-3333-333333333333",
      content_hash: "abcdef0123456789",
      plan_body: {
        version: 1,
        steps: [{
          id: "s1",
          action: "prepare",
          tool_id: "assess_readiness",
          effects: [],
          cost_known: false,
          params: {},
        }],
        effects: [],
        cost_known: false,
        summary: "آماده استقرار",
      },
      timeline: [],
      events: [],
    });

    const chatCards = mapOrchestratorToChatCards(run, "fa");
    expect(chatCards.map((card) => card.type)).toEqual(["plan", "approval"]);
    const serialized = JSON.stringify(chatCards);
    expect(serialized).not.toMatch(/readiness_findings|نتیجه بررسی آمادگی/);
    expect(serialized).not.toMatch(/assess_readiness|create_case/);
    expect(serialized).not.toMatch(/11111111-1111-1111-1111-111111111111/);
    expect(serialized).not.toMatch(/مدل زبانی آماده/);

    const planCard = chatCards[0];
    expect(planCard.type).toBe("plan");
    if (planCard.type === "plan") {
      expect(planCard.data.case_id).toBeNull();
      expect(planCard.data.plan_id).toBeNull();
      expect(planCard.data.content_hash).toBeNull();
      expect(planCard.data.steps[0]?.tool_id).toBeNull();
    }
  });

  it("shapes assess_readiness payload with app_path when folder set", () => {
    expect(assessReadinessPayload("ws", "case", "/Users/me/app")).toEqual({
      workspace_id: "ws",
      case_id: "case",
      app_path: "/Users/me/app",
    });
    expect(assessReadinessPayload("ws", "case", "  ")).toEqual({
      workspace_id: "ws",
      case_id: "case",
    });
    expect(assessReadinessPayload("ws", "case", null)).not.toHaveProperty("app_path");
  });

  it("writes conversational plan-ready copy without readiness noise", () => {
    const fa = planReadyAssistantText("fa", "طرح استقرار آماده است");
    expect(fa).toContain("طرح استقرار آماده است");
    expect(fa).toMatch(/تأیید/);
    expect(fa).not.toMatch(/آمادگی|UUID|create_case|assess_readiness|پرونده=/);
  });
});
