import { describe, expect, it } from "vitest";
import { proveLiaraReadSchema, settingsViewSchema } from "./schemas";

describe("companion settings public view", () => {
  it("parses nested liara + aval redacted shape", () => {
    const view = settingsViewSchema.parse({
      workspace_id: "11111111-1111-1111-1111-111111111111",
      liara: {
        api_base_url: "https://api.liara.ir",
        team_id: "team-abc",
        token_configured: true,
        token_label: "Liara API token",
      },
      aval: {
        base_url: "https://api.avalai.ir/v1",
        model: "gpt-4o-mini",
        api_key_configured: true,
        api_key_label: "Aval AI API key",
      },
    });

    expect(view.liara.token_configured).toBe(true);
    expect(view.aval.api_key_configured).toBe(true);
    expect(JSON.stringify(view)).not.toMatch(/sk-|Bearer|secret/i);
  });

  it("rejects flat thin-backend settings shape", () => {
    const result = settingsViewSchema.safeParse({
      token_configured: true,
      team_id: null,
      api_base_url: "https://api.liara.ir",
      allow_live_writes: false,
      mode: "LIVE",
    });
    expect(result.success).toBe(false);
  });

  it("parses prove-read without requiring secret fields", () => {
    const prove = proveLiaraReadSchema.parse({
      ok: true,
      project_count: 2,
      projects: [
        { project_id: "atlas-api", type: "node", status: "RUNNING", isDeployed: true },
        { project_id: "web", type: "next", status: null, isDeployed: false },
      ],
      registry: { tool_id: "list_get_projects", status: "tested", updated: true },
    });
    expect(prove.project_count).toBe(2);
    expect(prove.projects?.[0]?.project_id).toBe("atlas-api");
  });
});
