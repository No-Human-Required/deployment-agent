import { describe, expect, it } from "vitest";
import {
  buildRequestTimeline,
  inferGoalIntent,
  labelPlanStepAction,
  timelineStatusLabel,
} from "./requestTimeline";

describe("inferGoalIntent", () => {
  it("marks awaiting_intake as waiting on the prep step", () => {
    const steps = buildRequestTimeline({
      language: "en",
      goal: "Deploy my Node app",
      stage: "awaiting_intake",
      readiness: { ready: true, open_needs: [] },
    });
    expect(steps.some((s) => s.tool === "prep.intake" && s.status === "waiting")).toBe(true);
    expect(steps.map((s) => s.title).join(" ")).toMatch(/service|plan|domain/i);
  });

  it("distinguishes deploy, troubleshoot, and domain goals", () => {
    expect(inferGoalIntent("Deploy my Node app to Liara")).toBe("deploy");
    expect(inferGoalIntent("استقرار اولین نسخه")).toBe("deploy");
    expect(inferGoalIntent("سلام من میخوام دپلوی کنم")).toBe("deploy");
    expect(inferGoalIntent("می‌خوام دیپلوی کنم")).toBe("deploy");
    expect(inferGoalIntent("Investigate HTTP 500 errors")).toBe("troubleshoot");
    expect(inferGoalIntent("رفع خطای ۵۰۰")).toBe("troubleshoot");
    expect(inferGoalIntent("Connect custom domain and SSL")).toBe("domain");
    expect(inferGoalIntent("اتصال دامنه")).toBe("domain");
  });
});

describe("labelPlanStepAction", () => {
  it("uses human labels and never prefers tool ids", () => {
    expect(labelPlanStepAction("prepare_deploy_stub", "en")).toBe("Prepare deploy");
    expect(labelPlanStepAction("prepare_deploy_stub", "fa")).toBe("آماده‌سازی استقرار");
    expect(labelPlanStepAction("gather_evidence", "en")).toMatch(/evidence/i);
    expect(labelPlanStepAction("weird_custom_action", "en")).toBe("Weird Custom Action");
  });
});

describe("buildRequestTimeline", () => {
  it("uses intent stubs before a plan — not create_case / assess_readiness titles", () => {
    const deploy = buildRequestTimeline({
      language: "en",
      goal: "Deploy demo app",
      stage: "assessing",
    });
    const titles = deploy.map((s) => s.title).join(" | ");
    expect(titles).toMatch(/deploy/i);
    expect(titles).not.toMatch(/create_case|assess_readiness|Create plan/i);
    expect(deploy.some((s) => /create_case|assess_readiness/.test(s.tool))).toBe(false);

    const trouble = buildRequestTimeline({
      language: "fa",
      goal: "Investigate HTTP 500",
      stage: "planning",
      readiness: { ready: true, open_needs: [] },
    });
    const faTitles = trouble.map((s) => s.title).join(" | ");
    expect(faTitles).toMatch(/مشکل|نشانه‌|رفع/);
    expect(faTitles).not.toMatch(/ایجاد پرونده|ارزیابی آمادگی/);
  });

  it("aligns timeline with plan_body steps when present", () => {
    const planBody = {
      version: 1,
      steps: [
        {
          id: "s1",
          action: "prepare_deploy_stub",
          tool_id: "create_project",
          effects: [],
          cost_known: false,
          params: {},
        },
        {
          id: "s2",
          action: "deploy_app",
          tool_id: "liara_deploy",
          effects: [],
          cost_known: false,
          params: {},
        },
      ],
      effects: [],
      cost_known: false,
      summary: "Deploy plan",
    };

    const waiting = buildRequestTimeline({
      language: "en",
      goal: "Deploy demo",
      stage: "awaiting_approval",
      planBody,
    });

    expect(waiting.map((s) => s.title)).toEqual([
      "Prepare deploy",
      "Deploy the app",
      "Your approval",
    ]);
    expect(waiting.every((s) => !/create_case|assess_readiness|create_plan/.test(s.title))).toBe(
      true,
    );
    expect(waiting.find((s) => s.tool === "hitl.approve")?.status).toBe("waiting");
    // Primary labels are not raw tool_ids
    expect(waiting.some((s) => s.title === "create_project" || s.title === "liara_deploy")).toBe(
      false,
    );

    const verified = buildRequestTimeline({
      language: "en",
      goal: "Deploy demo",
      stage: "verified",
      planBody,
      operationState: "verified_stub",
    });
    expect(verified.find((s) => s.tool === "run.verify")?.status).toBe("verified");
    expect(verified.filter((s) => s.tool.startsWith("plan.")).every((s) => s.status === "done")).toBe(
      true,
    );
    expect(verified.some((s) => /[0-9a-f]{8}-[0-9a-f]{4}/i.test(s.detail))).toBe(false);
  });

  it("updates statuses across approval → execute → verify", () => {
    const planBody = {
      version: 1,
      steps: [{ id: "s1", action: "stub", effects: [], cost_known: false, params: {} }],
      effects: [],
      cost_known: false,
    };

    const executing = buildRequestTimeline({
      language: "fa",
      goal: "generic ask",
      stage: "executing",
      planBody,
    });
    expect(executing.find((s) => s.tool === "hitl.approve")?.status).toBe("done");
    expect(executing.find((s) => s.tool === "run.execute")?.status).toBe("pending");

    const rejected = buildRequestTimeline({
      language: "en",
      goal: "generic ask",
      stage: "rejected",
      planBody,
    });
    expect(rejected.find((s) => s.tool === "hitl.approve")?.status).toBe("rejected");
  });
});

describe("timelineStatusLabel", () => {
  it("localizes common statuses", () => {
    expect(timelineStatusLabel("waiting", "fa")).toMatch(/تأیید/);
    expect(timelineStatusLabel("done", "en")).toBe("done");
  });
});
