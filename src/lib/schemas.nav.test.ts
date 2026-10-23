import { describe, expect, it } from "vitest";
import {
  liaraDomainsResultSchema,
  liaraPlansResultSchema,
  liaraProjectMonitoringSchema,
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

  it("parses project monitoring happy path", () => {
    const parsed = liaraProjectMonitoringSchema.parse({
      project: {
        name: "demo-app",
        project_id: "demo-app",
        type: "node",
        status: "RUNNING",
        isDeployed: true,
        plan_id: "free",
        region: "iran",
        scale: 1,
        default_url: "https://demo-app.liara.run",
        kind: "app",
      },
      plan: {
        id: "free",
        label: "Free",
        hint: "RAM 0.5 GB · CPU 0.5",
        price_monthly: 0,
        ram_gb: 0.5,
      },
      domains: [
        {
          id: "dom-1",
          name: "app.example.com",
          status: "ACTIVE",
          certificates_status: "ACTIVE",
          project: "demo-app",
        },
      ],
      cpu: { available: true, series: { data: [{ t: 1, v: 12 }] }, latest: 12 },
      memory: { available: true, series: { data: [{ t: 1, v: 256 }] }, latest: 256 },
      logs: {
        available: true,
        lines: [
          {
            message: "boot ok",
            timestamp: "2026-10-23T10:00:00Z",
            stream: "stdout",
          },
        ],
        truncated: false,
      },
      gaps: [],
      source: "liara_monitoring",
    });
    expect(parsed.project.name).toBe("demo-app");
    expect(parsed.project.default_url).toBe("https://demo-app.liara.run");
    expect(parsed.plan?.id).toBe("free");
    expect(parsed.domains).toHaveLength(1);
    expect(parsed.cpu.available).toBe(true);
    expect(parsed.cpu.latest).toBe(12);
    expect(parsed.logs.lines).toHaveLength(1);
    expect(parsed.logs.lines[0]?.stream).toBe("stdout");
    expect(parsed.gaps).toEqual([]);
  });

  it("parses database monitoring payload", () => {
    const parsed = liaraProjectMonitoringSchema.parse({
      project: {
        name: "demo-postgres",
        project_id: "db-1",
        type: "postgres",
        status: "RUNNING",
        plan_id: "small-g2",
        version: "16.14",
        volume_size_gb: 5,
        kind: "database",
      },
      plan: {
        id: "small-g2",
        label: "small-g2",
        price_monthly: 475000,
        ram_gb: 1,
      },
      domains: [],
      cpu: { available: false, series: null, latest: null },
      memory: { available: false, series: null, latest: null },
      logs: { available: false, lines: [], truncated: false },
      gaps: [
        { source: "cpu", reason: "not_applicable", message: "CPU metrics not exposed" },
      ],
      source: "liara_database_monitoring",
    });
    expect(parsed.project.kind).toBe("database");
    expect(parsed.project.version).toBe("16.14");
    expect(parsed.plan?.price_monthly).toBe(475000);
    expect(parsed.domains).toEqual([]);
  });

  it("parses monitoring with soft gaps", () => {
    const parsed = liaraProjectMonitoringSchema.parse({
      project: {
        name: "quiet-app",
        project_id: "quiet-app",
        status: "STOPPED",
        isDeployed: false,
      },
      cpu: { available: false, series: null },
      memory: { available: false, series: null },
      logs: { available: false, lines: [], truncated: false },
      gaps: [
        { source: "cpu", reason: "missing_or_empty", message: "cpu metrics unavailable" },
        { source: "logs", reason: "empty", message: "No recent log lines" },
      ],
      source: "liara_monitoring",
    });
    expect(parsed.cpu.available).toBe(false);
    expect(parsed.gaps.map((g) => g.source)).toEqual(["cpu", "logs"]);
  });

  it("rejects monitoring without project name", () => {
    expect(() =>
      liaraProjectMonitoringSchema.parse({
        project: { project_id: "x" },
        cpu: { available: false, series: null },
        memory: { available: false, series: null },
        logs: { available: false, lines: [], truncated: false },
        gaps: [],
        source: "liara_monitoring",
      }),
    ).toThrow();
  });
});
