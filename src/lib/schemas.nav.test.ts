import { describe, expect, it } from "vitest";
import {
  liaraDomainsResultSchema,
  liaraPlansResultSchema,
  maintainAuditResultSchema,
  maintainIncidentsResultSchema,
} from "./schemas";

describe("nav surface companion schemas", () => {
  it("parses liara plans list", () => {
    const parsed = liaraPlansResultSchema.parse({
      plans: [
        { id: "free", label: "Free", hint: "RAM 0.5 GB", available: true, region: "iran" },
        { id: "g2-2x", label: "g2-2x", hint: null },
      ],
      source: "liara_me",
    });
    expect(parsed.plans).toHaveLength(2);
    expect(parsed.plans[0]?.id).toBe("free");
  });

  it("rejects non-array plans payload", () => {
    expect(() => liaraPlansResultSchema.parse({ plans: "free" })).toThrow();
  });

  it("parses liara domains list", () => {
    const parsed = liaraDomainsResultSchema.parse({
      domains: [
        {
          id: "dom-1",
          name: "example.com",
          status: "ACTIVE",
          certificates_status: "PENDING",
          project: "demo-app",
          type: "PROJECT",
          cname_record: "demo-app.liara.run",
        },
      ],
      project: "demo-app",
      source: "liara_domains",
    });
    expect(parsed.domains).toHaveLength(1);
    expect(parsed.domains[0]?.name).toBe("example.com");
    expect(parsed.project).toBe("demo-app");
  });

  it("rejects domains payload without project", () => {
    expect(() =>
      liaraDomainsResultSchema.parse({
        domains: [{ id: "x", name: "a.com" }],
      }),
    ).toThrow();
  });

  it("parses maintain incidents", () => {
    const parsed = maintainIncidentsResultSchema.parse({
      incidents: [
        {
          incident_id: "11111111-1111-4111-8111-111111111111",
          status: "open",
          title: "Missed checks",
          alert_count: 2,
          write_authorized: false,
        },
      ],
    });
    expect(parsed.incidents[0]?.title).toBe("Missed checks");
    expect(parsed.incidents[0]?.write_authorized).toBe(false);
  });

  it("parses maintain audit events", () => {
    const parsed = maintainAuditResultSchema.parse({
      events: [
        {
          id: "22222222-2222-4222-8222-222222222222",
          event_type: "maintain.monitor_enabled",
          actor: "user",
          case_id: null,
          created_at: "2026-10-23T10:00:00+00:00",
          payload: { target: "https://example.com" },
        },
      ],
    });
    expect(parsed.events[0]?.event_type).toContain("maintain");
  });

  it("rejects incident without required title", () => {
    expect(() =>
      maintainIncidentsResultSchema.parse({
        incidents: [{ incident_id: "x", status: "open" }],
      }),
    ).toThrow();
  });
});
