import { useEffect, useRef, useState } from "react";
import {
  Activity,
  ArrowUp,
  Check,
  CircleHelp,
  Clock3,
  Globe2,
  LayoutDashboard,
  Menu,
  MessageSquare,
  Plus,
  RefreshCw,
  Server,
  Settings2,
  Sparkles,
} from "lucide-react";
import { motion } from "motion/react";
import {
  getAuditEvents,
  getDomains,
  getIncidents,
  getLiaraPlans,
  getProjectMonitoring,
  type Service,
} from "../../lib/api";
import type { Conversation } from "../../lib/conversations";
import type {
  LiaraDomain,
  LiaraPlan,
  LiaraProjectMonitoring,
  MaintainAuditEvent,
  MaintainIncident,
  SettingsView,
} from "../../lib/schemas";
import { serviceStatusTone, serviceStatusToneLabel } from "../../lib/serviceStatus";
import { Button } from "../ui/button";
import { Card } from "../ui/card";

export type NavSurface =
  | "My Services"
  | "Deployments"
  | "Monitoring"
  | "Domains"
  | "Agent History"
  | "Settings"
  | "New Chat";

type Language = "en" | "fa";
type LoadState = "idle" | "loading" | "ready" | "error";

type Props = {
  activeNav: NavSurface;
  language: Language;
  settingsView: SettingsView | null;
  services: Service[];
  servicesState: LoadState;
  servicesError: string;
  /** Account service selected from sidebar — drives per-project monitoring pane. */
  selectedServiceId?: string | null;
  history: Conversation[];
  onOpenConversation: (conversation: Conversation) => void;
  onStart: () => void;
  onOpenNav: () => void;
  onOpenSettings: () => void;
  onRefreshServices: () => void | Promise<void>;
  onInvestigate: (service: Service) => void;
  onStartMonitorGoal: () => void;
  /** Starts chat intake for domain attach — never writes from this nav surface. */
  onStartDomainGoal: (projectName?: string) => void;
};

/** Format a Liara metric sample for display (CPU fraction or memory bytes). */
function formatMetricLatest(value: number, kind: "cpu" | "memory"): string {
  if (kind === "cpu") {
    // Liara CPU series is typically a core-fraction; show as percent when < 10.
    if (value >= 0 && value <= 10) return `${(value * 100).toFixed(1)}%`;
    return value.toFixed(3);
  }
  if (value >= 1024 * 1024 * 1024) return `${(value / (1024 * 1024 * 1024)).toFixed(2)} GiB`;
  if (value >= 1024 * 1024) return `${(value / (1024 * 1024)).toFixed(1)} MiB`;
  if (value >= 1024) return `${(value / 1024).toFixed(0)} KiB`;
  return `${Math.round(value)} B`;
}

/** Last numeric-ish value from a Liara metrics series (list or `{ result|data|values|… }`). */
function lastMetricSummary(series: unknown): number | null {
  const formatPoint = (point: unknown): number | null => {
    if (point == null) return null;
    if (typeof point === "number" && Number.isFinite(point)) return point;
    if (typeof point === "string" && point.trim()) {
      const n = Number(point);
      return Number.isFinite(n) ? n : null;
    }
    if (Array.isArray(point) && point.length >= 2) {
      return formatPoint(point[1]);
    }
    if (typeof point === "object" && !Array.isArray(point)) {
      const row = point as Record<string, unknown>;
      for (const key of ["v", "value", "cpu", "memory", "usage", "y"]) {
        const val = formatPoint(row[key]);
        if (val != null) return val;
      }
    }
    return null;
  };
  if (series == null) return null;
  if (Array.isArray(series) && series.length > 0) {
    for (let i = series.length - 1; i >= 0; i -= 1) {
      const found = formatPoint(series[i]);
      if (found != null) return found;
    }
    return null;
  }
  if (typeof series === "object") {
    const obj = series as Record<string, unknown>;
    const result = obj.result;
    if (Array.isArray(result)) {
      let best: number | null = null;
      for (const row of result) {
        if (!row || typeof row !== "object") continue;
        const values = (row as Record<string, unknown>).values;
        if (!Array.isArray(values) || values.length === 0) continue;
        const found = formatPoint(values[values.length - 1]);
        if (found != null) best = best == null ? found : Math.max(best, found);
      }
      if (best != null) return best;
    }
    for (const key of ["data", "metrics", "values", "series", "points"]) {
      const nested = obj[key];
      if (Array.isArray(nested) && nested.length > 0) {
        const found = formatPoint(nested[nested.length - 1]);
        if (found != null) return found;
      }
    }
  }
  return null;
}

function metricDisplay(
  block: { available: boolean; series?: unknown; latest?: number | null },
  kind: "cpu" | "memory",
): string | null {
  if (!block.available) return null;
  const latest =
    typeof block.latest === "number" && Number.isFinite(block.latest)
      ? block.latest
      : lastMetricSummary(block.series);
  return latest == null ? null : formatMetricLatest(latest, kind);
}

function statusBadgeClass(tone: ReturnType<typeof serviceStatusTone>): string {
  if (tone === "online") return "status-badge status-good";
  if (tone === "error") return "status-badge status-error";
  if (tone === "stopped") return "status-badge status-muted";
  return "status-badge status-muted";
}

const meta = {
  en: {
    "My Services": {
      title: "Your services",
      subtitle: "Projects from your Liara account (live prove-read).",
      icon: Server,
    },
    Deployments: {
      title: "Deployments",
      subtitle: "Deploy status from projects plus account PaaS plans.",
      icon: LayoutDashboard,
    },
    Monitoring: {
      title: "Monitoring",
      subtitle: "Live status, resources, and logs for a selected service.",
      icon: Activity,
    },
    Domains: {
      title: "Domains",
      subtitle: "Custom domains for a selected Liara project (live list).",
      icon: Globe2,
    },
    "Agent History": {
      title: "Agent history",
      subtitle: "Saved chats and optional companion audit events.",
      icon: Clock3,
    },
    Settings: {
      title: "Workspace settings",
      subtitle: "Manage preferences and agent behavior.",
      icon: Settings2,
    },
    "New Chat": {
      title: "Agent workspace",
      subtitle: "Start a conversation.",
      icon: MessageSquare,
    },
  },
  fa: {
    "My Services": {
      title: "سرویس‌های شما",
      subtitle: "پروژه‌های حساب لیارا (خواندن زنده).",
      icon: Server,
    },
    Deployments: {
      title: "استقرارها",
      subtitle: "وضعیت استقرار پروژه‌ها و پلن‌های PaaS حساب.",
      icon: LayoutDashboard,
    },
    Monitoring: {
      title: "پایش",
      subtitle: "وضعیت زنده، منابع و لاگ برای سرویس انتخاب‌شده.",
      icon: Activity,
    },
    Domains: {
      title: "دامنه‌ها",
      subtitle: "دامنه‌های سفارشی برای پروژهٔ انتخاب‌شده لیارا (فهرست زنده).",
      icon: Globe2,
    },
    "Agent History": {
      title: "تاریخچه عامل",
      subtitle: "گفتگوهای ذخیره‌شده و رویدادهای ممیزی همراه (در صورت وجود).",
      icon: Clock3,
    },
    Settings: {
      title: "تنظیمات فضای کار",
      subtitle: "ترجیحات و رفتار عامل.",
      icon: Settings2,
    },
    "New Chat": {
      title: "فضای کار عامل",
      subtitle: "گفتگو را شروع کنید.",
      icon: MessageSquare,
    },
  },
} as const;

const labels = {
  en: {
    newChat: "New chat",
    refresh: "Refresh",
    connected: "Connected",
    setup: "Needs setup",
    loading: "Loading…",
    retry: "Retry",
    openSettings: "Open Settings",
    noTokenTitle: "Liara token not configured",
    noTokenBody: "Save your API token in Settings, then refresh to load real services. Demo catalogs are not shown.",
    servicesEmptyTitle: "No projects found",
    servicesEmptyBody: "Prove-read succeeded but returned no projects for this workspace.",
    servicesError: "Could not load services.",
    deployEyebrow: "PROJECT DEPLOY STATUS",
    plansEyebrow: "ACCOUNT PAAS PLANS",
    deployEmpty: "No deployed project status to show yet.",
    plansEmpty: "No selectable PaaS plans returned for this account.",
    plansHint: "These are account plan IDs from Liara me — not release history.",
    deployed: "Deployed",
    notDeployed: "Not deployed",
    unknown: "Unknown",
    monitorEyebrow: "INCIDENTS",
    monitorEmptyTitle: "No incidents",
    monitorEmptyBody: "Enable a monitor from chat when you are ready. Listing by monitor id exists; there is no fake metric dashboard.",
    monitorCta: "Ask agent to set up monitoring",
    monitorNeedWorkspace: "Workspace settings are required to list incidents.",
    serviceMonitorPick: "Select a service from the sidebar to open its monitoring view.",
    serviceMonitorEyebrow: "SERVICE",
    serviceMonitorCpu: "CPU",
    serviceMonitorMemory: "Memory",
    serviceMonitorPlan: "Active plan",
    serviceMonitorPlanCost: "Monthly plan cost",
    serviceMonitorPlanUnknown: "Plan price unavailable",
    serviceMonitorScale: "Scale",
    serviceMonitorUrl: "Default URL",
    serviceMonitorDomains: "Domains",
    serviceMonitorNoDomains: "No custom domains attached",
    serviceMonitorLogs: "Recent logs",
    serviceMonitorLogsEmpty: "No recent log lines",
    serviceMonitorGaps: "API gaps",
    serviceMonitorUnavailable: "Unavailable from Liara API",
    serviceMonitorLast: "Last value",
    serviceMonitorNoValue: "Series present — no single summary value",
    serviceMonitorTruncated: "Showing latest lines (truncated)",
    serviceMonitorError: "Could not load monitoring for this service.",
    serviceMonitorMeta: "Type · plan · region",
    serviceMonitorDeployed: "Deployed",
    serviceMonitorNotDeployed: "Not deployed",
    domainsEyebrow: "DOMAINS FOR PROJECT",
    domainsProjectLabel: "Project",
    domainsPickProject: "Select a project to list domains",
    domainsNeedServices: "Load projects first (My Services), then pick one here.",
    domainsEmptyTitle: "No domains on this project",
    domainsEmptyBody:
      "Liara returned an empty domain list. Attach a custom domain through chat — approval is required before any write.",
    domainsCta: "Attach domain via chat",
    domainsError: "Could not load domains.",
    domainsSsl: "SSL",
    domainsCname: "CNAME",
    historyEyebrow: "SAVED CONVERSATIONS",
    auditEyebrow: "COMPANION AUDIT",
    historyEmpty: "No agent runs yet. Start a chat to investigate your first issue.",
    auditEmpty: "No audit events for this workspace yet.",
    auditUnavailable: "Audit list needs a loaded workspace id.",
    open: "Open",
    alerts: "alerts",
    investigate: "Investigate",
  },
  fa: {
    newChat: "گفتگوی جدید",
    refresh: "بازنشانی",
    connected: "متصل",
    setup: "نیاز به پیکربندی",
    loading: "در حال بارگذاری…",
    retry: "تلاش دوباره",
    openSettings: "باز کردن تنظیمات",
    noTokenTitle: "توکن لیارا پیکربندی نشده",
    noTokenBody: "توکن را در تنظیمات ذخیره کنید، سپس بازنشانی کنید. کاتالوگ نمایشی نشان داده نمی‌شود.",
    servicesEmptyTitle: "پروژه‌ای یافت نشد",
    servicesEmptyBody: "خواندن موفق بود اما پروژه‌ای برای این فضای کار برنگشت.",
    servicesError: "بارگذاری سرویس‌ها ممکن نشد.",
    deployEyebrow: "وضعیت استقرار پروژه",
    plansEyebrow: "پلن‌های PaaS حساب",
    deployEmpty: "هنوز وضعیت استقراری برای نمایش نیست.",
    plansEmpty: "پلنی برای این حساب برنگشت.",
    plansHint: "این شناسه‌های پلن حساب از لیارا هستند — نه تاریخچه انتشار.",
    deployed: "استقرار یافته",
    notDeployed: "استقرار نیافته",
    unknown: "نامشخص",
    monitorEyebrow: "حوادث",
    monitorEmptyTitle: "حادثه‌ای نیست",
    monitorEmptyBody: "وقتی آماده بودید از گفتگو مانیتور را فعال کنید. داشبورد متریک جعلی نمایش داده نمی‌شود.",
    monitorCta: "از عامل بخواهید پایش را راه‌اندازی کند",
    monitorNeedWorkspace: "برای فهرست حوادث، تنظیمات فضای کار لازم است.",
    serviceMonitorPick: "از سایدبار یک سرویس انتخاب کنید تا پایش آن باز شود.",
    serviceMonitorEyebrow: "سرویس",
    serviceMonitorCpu: "پردازنده",
    serviceMonitorMemory: "حافظه",
    serviceMonitorPlan: "پلن فعال",
    serviceMonitorPlanCost: "هزینه ماهانه پلن",
    serviceMonitorPlanUnknown: "قیمت پلن نامشخص",
    serviceMonitorScale: "مقیاس",
    serviceMonitorUrl: "آدرس پیش‌فرض",
    serviceMonitorDomains: "دامنه‌ها",
    serviceMonitorNoDomains: "دامنهٔ سفارشی متصل نیست",
    serviceMonitorLogs: "لاگ‌های اخیر",
    serviceMonitorLogsEmpty: "لاگ اخیری نیست",
    serviceMonitorGaps: "محدودیت‌های API",
    serviceMonitorUnavailable: "از API لیارا در دسترس نیست",
    serviceMonitorLast: "آخرین مقدار",
    serviceMonitorNoValue: "سری موجود است — مقدار خلاصهٔ تکی نیست",
    serviceMonitorTruncated: "آخرین خطوط (کوتاه‌شده)",
    serviceMonitorError: "بارگذاری پایش این سرویس ممکن نشد.",
    serviceMonitorMeta: "نوع · پلن · منطقه",
    serviceMonitorDeployed: "استقرار یافته",
    serviceMonitorNotDeployed: "استقرار نیافته",
    domainsEyebrow: "دامنه‌های پروژه",
    domainsProjectLabel: "پروژه",
    domainsPickProject: "برای دیدن دامنه‌ها یک پروژه انتخاب کنید",
    domainsNeedServices: "ابتدا پروژه‌ها را از «سرویس‌های شما» بارگذاری کنید، سپس اینجا انتخاب کنید.",
    domainsEmptyTitle: "دامنه‌ای روی این پروژه نیست",
    domainsEmptyBody:
      "لیارا فهرست خالی برگرداند. اتصال دامنه از گفتگو انجام می‌شود — قبل از هر نوشتن تأیید لازم است.",
    domainsCta: "اتصال دامنه از گفتگو",
    domainsError: "بارگذاری دامنه‌ها ممکن نشد.",
    domainsSsl: "SSL",
    domainsCname: "CNAME",
    historyEyebrow: "گفتگوهای ذخیره‌شده",
    auditEyebrow: "ممیزی همراه",
    historyEmpty: "هنوز اجرایی نیست. برای بررسی اولین مسئله گفتگو را شروع کنید.",
    auditEmpty: "هنوز رویداد ممیزی برای این فضای کار نیست.",
    auditUnavailable: "فهرست ممیزی به شناسه فضای کار نیاز دارد.",
    open: "باز کردن",
    alerts: "هشدار",
    investigate: "بررسی",
  },
};

function formatPlanTomans(value: number | null | undefined, language: Language): string {
  if (value == null || Number.isNaN(value)) {
    return language === "fa" ? "قیمت نامشخص" : "Price n/a";
  }
  const rounded = Math.round(value);
  const formatted = new Intl.NumberFormat(language === "fa" ? "fa-IR" : "en-US").format(rounded);
  return language === "fa" ? `${formatted} تومان / ماه` : `${formatted} Tomans/mo`;
}

function formatLogTimestamp(raw: string | null | undefined, language: Language): string {
  if (!raw) return "";
  const parsed = Date.parse(raw);
  if (Number.isNaN(parsed)) return raw;
  return new Date(parsed).toLocaleString(language === "fa" ? "fa-IR" : "en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function StateCard({
  title,
  body,
  actionLabel,
  onAction,
  tone = "muted",
}: {
  title: string;
  body: string;
  actionLabel?: string;
  onAction?: () => void;
  tone?: "muted" | "warn" | "error" | "loading";
}) {
  return (
    <Card className={`nav-detail-card nav-state-card nav-state-${tone}`} role={tone === "error" ? "alert" : "status"}>
      {tone === "loading" ? (
        <div className="ui-loading-row" aria-busy="true">
          <span className="mini-spinner" />
          <span>{title}</span>
        </div>
      ) : (
        <>
          <h3>{title}</h3>
          {body ? <p>{body}</p> : null}
          {actionLabel && onAction ? (
            <Button className="mt-3" variant="secondary" onClick={onAction}>
              {actionLabel}
            </Button>
          ) : null}
        </>
      )}
    </Card>
  );
}

export function NavigationView({
  activeNav,
  language,
  settingsView,
  services,
  servicesState,
  servicesError,
  selectedServiceId = null,
  history,
  onOpenConversation,
  onStart,
  onOpenNav,
  onOpenSettings,
  onRefreshServices,
  onInvestigate,
  onStartMonitorGoal,
  onStartDomainGoal,
}: Props) {
  const t = labels[language];
  const content = meta[language][activeNav];
  const Icon = content.icon;
  const tokenConfigured = Boolean(settingsView?.liara.token_configured);
  const workspaceId = settingsView?.workspace_id;
  const selectedProject = selectedServiceId?.trim() || "";
  const selectedCatalogService = services.find((s) => s.id === selectedProject);
  const selectedKind = selectedCatalogService?.kind === "database" ? "database" : "app";

  const [plans, setPlans] = useState<LiaraPlan[]>([]);
  const [plansState, setPlansState] = useState<LoadState>("idle");
  const [plansError, setPlansError] = useState("");

  const [incidents, setIncidents] = useState<MaintainIncident[]>([]);
  const [incidentsState, setIncidentsState] = useState<LoadState>("idle");
  const [incidentsError, setIncidentsError] = useState("");

  const [serviceMonitoring, setServiceMonitoring] = useState<LiaraProjectMonitoring | null>(null);
  const [serviceMonitoringState, setServiceMonitoringState] = useState<LoadState>("idle");
  const [serviceMonitoringError, setServiceMonitoringError] = useState("");
  const serviceMonitoringRequestRef = useRef(0);

  const [audit, setAudit] = useState<MaintainAuditEvent[]>([]);
  const [auditState, setAuditState] = useState<LoadState>("idle");
  const [auditError, setAuditError] = useState("");

  const [domainProject, setDomainProject] = useState("");
  const [domains, setDomains] = useState<LiaraDomain[]>([]);
  const [domainsState, setDomainsState] = useState<LoadState>("idle");
  const [domainsError, setDomainsError] = useState("");

  async function loadPlans() {
    if (!tokenConfigured) {
      setPlans([]);
      setPlansState("ready");
      setPlansError("");
      return;
    }
    setPlansState("loading");
    setPlansError("");
    try {
      const rows = await getLiaraPlans(workspaceId);
      setPlans(rows);
      setPlansState("ready");
    } catch (cause) {
      setPlans([]);
      setPlansState("error");
      setPlansError(cause instanceof Error ? cause.message : t.servicesError);
    }
  }

  async function loadIncidents() {
    if (!workspaceId) {
      setIncidents([]);
      setIncidentsState("ready");
      setIncidentsError("");
      return;
    }
    setIncidentsState("loading");
    setIncidentsError("");
    try {
      const rows = await getIncidents(workspaceId);
      setIncidents(rows);
      setIncidentsState("ready");
    } catch (cause) {
      setIncidents([]);
      setIncidentsState("error");
      setIncidentsError(cause instanceof Error ? cause.message : t.servicesError);
    }
  }

  async function loadServiceMonitoring(
    projectName: string,
    kind: "app" | "database" = "app",
  ) {
    const requestId = ++serviceMonitoringRequestRef.current;
    if (!tokenConfigured) {
      if (requestId !== serviceMonitoringRequestRef.current) return;
      setServiceMonitoring(null);
      setServiceMonitoringState("ready");
      setServiceMonitoringError("");
      return;
    }
    const name = projectName.trim();
    if (!name) {
      if (requestId !== serviceMonitoringRequestRef.current) return;
      setServiceMonitoring(null);
      setServiceMonitoringState("idle");
      setServiceMonitoringError("");
      return;
    }
    setServiceMonitoringState("loading");
    setServiceMonitoringError("");
    try {
      const feed = await getProjectMonitoring(name, workspaceId, kind);
      if (requestId !== serviceMonitoringRequestRef.current) return;
      setServiceMonitoring(feed);
      setServiceMonitoringState("ready");
    } catch (cause) {
      if (requestId !== serviceMonitoringRequestRef.current) return;
      setServiceMonitoring(null);
      setServiceMonitoringState("error");
      setServiceMonitoringError(
        cause instanceof Error ? cause.message : t.serviceMonitorError,
      );
    }
  }

  async function loadAudit() {
    if (!workspaceId) {
      setAudit([]);
      setAuditState("ready");
      setAuditError("");
      return;
    }
    setAuditState("loading");
    setAuditError("");
    try {
      const rows = await getAuditEvents(workspaceId, { limit: 20 });
      setAudit(rows);
      setAuditState("ready");
    } catch (cause) {
      setAudit([]);
      setAuditState("error");
      setAuditError(cause instanceof Error ? cause.message : t.servicesError);
    }
  }

  async function loadDomains(projectName: string) {
    if (!tokenConfigured || !projectName) {
      setDomains([]);
      setDomainsState(projectName ? "idle" : "ready");
      setDomainsError("");
      return;
    }
    setDomainsState("loading");
    setDomainsError("");
    try {
      const rows = await getDomains(projectName, workspaceId);
      setDomains(rows);
      setDomainsState("ready");
    } catch (cause) {
      setDomains([]);
      setDomainsState("error");
      setDomainsError(cause instanceof Error ? cause.message : t.domainsError);
    }
  }

  useEffect(() => {
    if (activeNav === "Deployments") void loadPlans();
    if (activeNav === "Agent History") void loadAudit();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reload when surface / credentials change
  }, [activeNav, workspaceId, tokenConfigured]);

  useEffect(() => {
    if (activeNav !== "Monitoring") return;
    if (selectedProject) {
      void loadServiceMonitoring(selectedProject, selectedKind);
      return;
    }
    setServiceMonitoring(null);
    setServiceMonitoringState("idle");
    setServiceMonitoringError("");
    void loadIncidents();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- selection drives monitoring vs incidents
  }, [activeNav, selectedProject, selectedKind, workspaceId, tokenConfigured]);

  useEffect(() => {
    if (activeNav !== "Domains") return;
    if (!domainProject && services.length > 0) {
      setDomainProject(services[0]!.id);
      return;
    }
    if (domainProject && !services.some((s) => s.id === domainProject) && services.length > 0) {
      setDomainProject(services[0]!.id);
      return;
    }
    if (domainProject) void loadDomains(domainProject);
    else {
      setDomains([]);
      setDomainsState("ready");
      setDomainsError("");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- project / catalog drive reload
  }, [activeNav, domainProject, services, workspaceId, tokenConfigured]);

  const connectionOk = tokenConfigured || activeNav === "Agent History";
  const topbarLabel = connectionOk ? t.connected : t.setup;

  function renderServices() {
    if (!tokenConfigured) {
      return (
        <StateCard
          tone="warn"
          title={t.noTokenTitle}
          body={t.noTokenBody}
          actionLabel={t.openSettings}
          onAction={onOpenSettings}
        />
      );
    }
    if (servicesState === "loading") {
      return <StateCard tone="loading" title={t.loading} body="" />;
    }
    if (servicesState === "error") {
      return (
        <StateCard
          tone="error"
          title={t.servicesError}
          body={servicesError || t.servicesError}
          actionLabel={t.retry}
          onAction={() => void onRefreshServices()}
        />
      );
    }
    if (services.length === 0) {
      return (
        <StateCard
          title={t.servicesEmptyTitle}
          body={t.servicesEmptyBody}
          actionLabel={t.refresh}
          onAction={() => void onRefreshServices()}
        />
      );
    }
    return (
      <div className="service-grid">
        {services.map((service, index) => (
          <Card key={service.id} className="service-card p-5">
            <div className="flex items-center justify-between">
              <div className={`service-type-icon service-type-${index % 4}`}>
                <Server size={17} />
              </div>
              <span
                className={
                  /deploy|healthy|ok|running/i.test(service.status)
                    ? "status-badge status-good"
                    : "status-badge status-warn"
                }
              >
                <span className="status-dot" />
                {service.status}
              </span>
            </div>
            <h3>{service.name}</h3>
            <p>
              {service.app_type} · {service.region}
            </p>
            <div className="service-card-footer">
              <span>{service.uptime}</span>
              <button type="button" onClick={() => onInvestigate(service)}>
                {t.investigate} <ArrowUp size={12} />
              </button>
            </div>
          </Card>
        ))}
      </div>
    );
  }

  function deployLabel(service: Service) {
    if (/deploy/i.test(service.status)) return t.deployed;
    if (/unknown/i.test(service.status)) return t.unknown;
    return service.status || t.notDeployed;
  }

  function renderDeployments() {
    if (!tokenConfigured) {
      return (
        <StateCard
          tone="warn"
          title={t.noTokenTitle}
          body={t.noTokenBody}
          actionLabel={t.openSettings}
          onAction={onOpenSettings}
        />
      );
    }
    return (
      <div className="nav-stack">
        <Card className="nav-detail-card">
          <div className="section-eyebrow">{t.deployEyebrow}</div>
          {servicesState === "loading" ? (
            <div className="ui-loading-row" aria-busy="true"><span className="mini-spinner" /><span>{t.loading}</span></div>
          ) : services.length === 0 ? (
            <p className="nav-inline-muted">{t.deployEmpty}</p>
          ) : (
            services.map((service) => (
              <div className="release-row" key={service.id}>
                <span className="release-indicator">
                  <Check size={12} />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-slate-200">{service.name}</p>
                  <p className="mt-1 text-xs text-slate-600">
                    {service.app_type} · prove-read status
                  </p>
                </div>
                <span
                  className={
                    /deploy/i.test(service.status)
                      ? "status-badge status-good"
                      : "status-badge status-muted"
                  }
                >
                  {deployLabel(service)}
                </span>
              </div>
            ))
          )}
        </Card>
        <Card className="nav-detail-card">
          <div className="section-eyebrow">{t.plansEyebrow}</div>
          <p className="nav-inline-muted mb-3">{t.plansHint}</p>
          {plansState === "loading" ? (
            <div className="ui-loading-row" aria-busy="true"><span className="mini-spinner" /><span>{t.loading}</span></div>
          ) : plansState === "error" ? (
            <StateCard
              tone="error"
              title={plansError || t.servicesError}
              body=""
              actionLabel={t.retry}
              onAction={() => void loadPlans()}
            />
          ) : plans.length === 0 ? (
            <p className="nav-inline-muted">{t.plansEmpty}</p>
          ) : (
            plans.map((plan) => (
              <div className="release-row" key={plan.id}>
                <span className="release-indicator">
                  <LayoutDashboard size={12} />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-slate-200">{plan.label}</p>
                  <p className="mt-1 text-xs text-slate-600">
                    {plan.hint || plan.id}
                    {plan.region ? ` · ${plan.region}` : ""}
                  </p>
                </div>
                <span className="status-badge status-muted">{plan.id}</span>
              </div>
            ))
          )}
        </Card>
      </div>
    );
  }

  function renderServiceMonitoring() {
    if (!tokenConfigured) {
      return (
        <StateCard
          tone="warn"
          title={t.noTokenTitle}
          body={t.noTokenBody}
          actionLabel={t.openSettings}
          onAction={onOpenSettings}
        />
      );
    }
    if (serviceMonitoringState === "loading" || serviceMonitoringState === "idle") {
      return <StateCard tone="loading" title={t.loading} body="" />;
    }
    if (serviceMonitoringState === "error") {
      return (
        <StateCard
          tone="error"
          title={serviceMonitoringError || t.serviceMonitorError}
          body=""
          actionLabel={t.retry}
          onAction={() => void loadServiceMonitoring(selectedProject, selectedKind)}
        />
      );
    }
    const feed = serviceMonitoring;
    if (!feed) {
      return (
        <StateCard
          tone="error"
          title={t.serviceMonitorError}
          body=""
          actionLabel={t.retry}
          onAction={() => void loadServiceMonitoring(selectedProject, selectedKind)}
        />
      );
    }

    const project = feed.project;
    const tone = serviceStatusTone(project.status, project.isDeployed);
    const toneLabel = serviceStatusToneLabel(tone, language);
    const statusText = project.status?.trim() || toneLabel;
    const catalogService = services.find((s) => s.id === selectedProject);
    const investigateService: Service = catalogService ?? {
      id: project.project_id || project.name,
      name: project.name,
      app_type: project.type || "unknown",
      region: project.region || "—",
      status: statusText,
      url: "",
      uptime: "—",
      kind: project.kind === "database" ? "database" : "app",
    };
    const cpuSummary = metricDisplay(feed.cpu, "cpu");
    const memorySummary = metricDisplay(feed.memory, "memory");
    const plan = feed.plan ?? null;
    const planLabel = plan?.label || project.plan_id || null;
    const domains = feed.domains ?? [];
    const logsGap = feed.gaps.find((gap) => gap.source === "logs");
    const logsEmpty = logsGap?.reason === "empty" || logsGap?.reason === "empty_after_sanitize";
    const metaParts = [
      project.kind === "database" ? (language === "fa" ? "دیتابیس" : "Database") : null,
      project.type,
      planLabel,
      project.scale != null ? `${t.serviceMonitorScale} ×${project.scale}` : null,
      project.version ? `v${project.version}` : null,
      project.volume_size_gb != null ? `${project.volume_size_gb} GB` : null,
      project.region,
    ].filter((part): part is string => Boolean(part && String(part).trim()));
    const planCostText =
      plan?.price_monthly != null
        ? formatPlanTomans(plan.price_monthly, language)
        : planLabel
          ? t.serviceMonitorPlanUnknown
          : t.serviceMonitorUnavailable;

    return (
      <div className="nav-stack">
        <Card className="nav-detail-card">
          <div className="section-eyebrow">{t.serviceMonitorEyebrow}</div>
          <div className="service-monitor-header">
            <div className="min-w-0 flex-1">
              <h3 className="service-monitor-title">{project.name}</h3>
              <p className="nav-inline-muted mt-1">
                {metaParts.length > 0 ? metaParts.join(" · ") : t.serviceMonitorMeta}
                {project.isDeployed === true
                  ? ` · ${t.serviceMonitorDeployed}`
                  : project.isDeployed === false
                    ? ` · ${t.serviceMonitorNotDeployed}`
                    : ""}
              </p>
            </div>
            <span className={statusBadgeClass(tone)} title={statusText}>
              <span className={`status-dot status-dot-${tone}`} aria-hidden="true" />
              {statusText}
            </span>
          </div>
          <div className="service-monitor-actions">
            <Button
              variant="secondary"
              onClick={() => onInvestigate(investigateService)}
            >
              {t.investigate} <ArrowUp size={12} />
            </Button>
          </div>
        </Card>

        <div className="monitoring-grid monitoring-grid-4">
          <Card className="nav-detail-card monitor-card">
            <Activity size={14} />
            <span>{t.serviceMonitorCpu}</span>
            {feed.cpu.available ? (
              <>
                <strong>{cpuSummary ?? "—"}</strong>
                <small>
                  {cpuSummary ? t.serviceMonitorLast : t.serviceMonitorNoValue}
                </small>
              </>
            ) : (
              <>
                <strong className="monitor-unavailable">—</strong>
                <small>{t.serviceMonitorUnavailable}</small>
              </>
            )}
          </Card>
          <Card className="nav-detail-card monitor-card">
            <Server size={14} />
            <span>{t.serviceMonitorMemory}</span>
            {feed.memory.available ? (
              <>
                <strong>{memorySummary ?? "—"}</strong>
                <small>
                  {memorySummary ? t.serviceMonitorLast : t.serviceMonitorNoValue}
                </small>
              </>
            ) : (
              <>
                <strong className="monitor-unavailable">—</strong>
                <small>{t.serviceMonitorUnavailable}</small>
              </>
            )}
          </Card>
          <Card className="nav-detail-card monitor-card">
            <LayoutDashboard size={14} />
            <span>{t.serviceMonitorPlan}</span>
            {planLabel ? (
              <>
                <strong className="monitor-plan-label">{planLabel}</strong>
                <small>
                  {plan?.hint ? `${plan.hint} · ` : ""}
                  {t.serviceMonitorPlanCost}: {planCostText}
                </small>
              </>
            ) : (
              <>
                <strong className="monitor-unavailable">—</strong>
                <small>{t.serviceMonitorUnavailable}</small>
              </>
            )}
          </Card>
          <Card className="nav-detail-card monitor-card">
            <Globe2 size={14} />
            <span>{t.serviceMonitorDomains}</span>
            {project.default_url ? (
              <>
                <strong className="monitor-url-label">
                  <a href={project.default_url} target="_blank" rel="noreferrer">
                    {project.default_url.replace(/^https?:\/\//, "")}
                  </a>
                </strong>
                <small>
                  {domains.length > 0
                    ? `${domains.length} ${t.serviceMonitorDomains.toLowerCase()}`
                    : t.serviceMonitorNoDomains}
                </small>
              </>
            ) : domains.length > 0 ? (
              <>
                <strong>{domains.length}</strong>
                <small>{t.serviceMonitorDomains}</small>
              </>
            ) : (
              <>
                <strong className="monitor-unavailable">—</strong>
                <small>
                  {project.kind === "database"
                    ? t.serviceMonitorUnavailable
                    : t.serviceMonitorNoDomains}
                </small>
              </>
            )}
          </Card>
        </div>

        {project.kind !== "database" || domains.length > 0 ? (
          <Card className="nav-detail-card">
            <div className="section-eyebrow">{t.serviceMonitorDomains}</div>
            {project.default_url ? (
              <p className="service-monitor-url-row">
                <span className="nav-inline-muted">{t.serviceMonitorUrl}</span>
                <a href={project.default_url} target="_blank" rel="noreferrer">
                  {project.default_url}
                </a>
              </p>
            ) : null}
            {domains.length > 0 ? (
              <ul className="service-monitor-domains" aria-label={t.serviceMonitorDomains}>
                {domains.map((domain) => (
                  <li key={domain.id} className="domain-row">
                    <Globe2 size={14} />
                    <div className="min-w-0 flex-1">
                      <strong>{domain.name}</strong>
                      <span className="nav-inline-muted">
                        {[
                          domain.status,
                          domain.certificates_status
                            ? `${t.domainsSsl}: ${domain.certificates_status}`
                            : null,
                          domain.type,
                        ]
                          .filter(Boolean)
                          .join(" · ")}
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            ) : project.kind !== "database" ? (
              <p className="nav-inline-muted">{t.serviceMonitorNoDomains}</p>
            ) : null}
          </Card>
        ) : null}

        <Card className="nav-detail-card">
          <div className="section-eyebrow">{t.serviceMonitorLogs}</div>
          {feed.logs.available && feed.logs.lines.length > 0 ? (
            <>
              {feed.logs.truncated ? (
                <p className="nav-inline-muted mb-2">{t.serviceMonitorTruncated}</p>
              ) : null}
              <ul className="service-monitor-logs" aria-label={t.serviceMonitorLogs}>
                {feed.logs.lines.map((line, index) => {
                  const displayTime = formatLogTimestamp(line.timestamp, language);
                  return (
                    <li key={`${line.timestamp ?? "log"}-${index}`}>
                      <div className="service-monitor-log-meta">
                        {line.timestamp ? (
                          <time dateTime={line.timestamp}>{displayTime}</time>
                        ) : null}
                        {line.stream ? (
                          <span className="service-monitor-log-stream">{line.stream}</span>
                        ) : null}
                      </div>
                      <code>{line.message}</code>
                    </li>
                  );
                })}
              </ul>
            </>
          ) : (
            <p className="nav-inline-muted">
              {logsEmpty ? t.serviceMonitorLogsEmpty : t.serviceMonitorUnavailable}
            </p>
          )}
        </Card>

        {feed.gaps.length > 0 ? (
          <Card className="nav-detail-card" role="status">
            <div className="section-eyebrow">{t.serviceMonitorGaps}</div>
            <ul className="service-monitor-gaps">
              {feed.gaps.map((gap) => (
                <li key={`${gap.source}-${gap.reason}`}>
                  <strong>{gap.source}</strong>
                  <span>{gap.message}</span>
                </li>
              ))}
            </ul>
          </Card>
        ) : null}
      </div>
    );
  }

  function renderMonitoring() {
    if (selectedProject) {
      return renderServiceMonitoring();
    }
    if (!workspaceId) {
      return (
        <StateCard
          tone="warn"
          title={t.monitorNeedWorkspace}
          body={t.serviceMonitorPick}
          actionLabel={t.openSettings}
          onAction={onOpenSettings}
        />
      );
    }
    if (incidentsState === "loading") {
      return <StateCard tone="loading" title={t.loading} body="" />;
    }
    if (incidentsState === "error") {
      return (
        <StateCard
          tone="error"
          title={incidentsError || t.servicesError}
          body=""
          actionLabel={t.retry}
          onAction={() => void loadIncidents()}
        />
      );
    }
    if (incidents.length === 0) {
      return (
        <StateCard
          title={t.monitorEmptyTitle}
          body={`${t.monitorEmptyBody} ${t.serviceMonitorPick}`}
          actionLabel={t.monitorCta}
          onAction={onStartMonitorGoal}
        />
      );
    }
    return (
      <div className="nav-stack">
        <StateCard
          title={t.serviceMonitorPick}
          body=""
        />
        <Card className="nav-detail-card">
          <div className="section-eyebrow">{t.monitorEyebrow}</div>
          {incidents.map((incident) => (
            <div className="release-row" key={incident.incident_id}>
              <span className="release-indicator release-warn">
                <Activity size={12} />
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-sm text-slate-200">{incident.title}</p>
                <p className="mt-1 text-xs text-slate-600">
                  {incident.alert_count} {t.alerts}
                  {incident.opened_at
                    ? ` · ${new Date(incident.opened_at).toLocaleString()}`
                    : ""}
                </p>
              </div>
              <span
                className={
                  incident.status === "open"
                    ? "status-badge status-warn"
                    : "status-badge status-muted"
                }
              >
                {incident.status}
              </span>
            </div>
          ))}
        </Card>
      </div>
    );
  }

  function renderDomains() {
    if (!tokenConfigured) {
      return (
        <StateCard
          tone="warn"
          title={t.noTokenTitle}
          body={t.noTokenBody}
          actionLabel={t.openSettings}
          onAction={onOpenSettings}
        />
      );
    }
    if (servicesState === "loading" && services.length === 0) {
      return <StateCard tone="loading" title={t.loading} body="" />;
    }
    if (services.length === 0) {
      return (
        <StateCard
          tone="warn"
          title={t.servicesEmptyTitle}
          body={t.domainsNeedServices}
          actionLabel={t.refresh}
          onAction={() => void onRefreshServices()}
        />
      );
    }
    return (
      <div className="nav-stack">
        <Card className="nav-detail-card">
          <div className="section-eyebrow">{t.domainsEyebrow}</div>
          <label className="nav-domain-project">
            <span className="nav-inline-muted">{t.domainsProjectLabel}</span>
            <select
              className="intake-input nav-domain-select"
              value={domainProject}
              onChange={(event) => setDomainProject(event.target.value)}
              aria-label={t.domainsProjectLabel}
            >
              {services.map((service) => (
                <option key={service.id} value={service.id}>
                  {service.name}
                </option>
              ))}
            </select>
          </label>
          {!domainProject ? (
            <p className="nav-inline-muted mt-3">{t.domainsPickProject}</p>
          ) : domainsState === "loading" ? (
            <div className="ui-loading-row mt-3" aria-busy="true">
              <span className="mini-spinner" />
              <span>{t.loading}</span>
            </div>
          ) : domainsState === "error" ? (
            <div className="mt-3">
              <StateCard
                tone="error"
                title={domainsError || t.domainsError}
                body=""
                actionLabel={t.retry}
                onAction={() => void loadDomains(domainProject)}
              />
            </div>
          ) : domains.length === 0 ? (
            <div className="mt-3">
              <StateCard
                title={t.domainsEmptyTitle}
                body={t.domainsEmptyBody}
                actionLabel={t.domainsCta}
                onAction={() => onStartDomainGoal(domainProject)}
              />
            </div>
          ) : (
            <>
              {domains.map((domain) => (
                <div className="release-row" key={domain.id}>
                  <span className="release-indicator">
                    <Globe2 size={12} />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm text-slate-200">{domain.name}</p>
                    <p className="mt-1 text-xs text-slate-600">
                      {domain.cname_record
                        ? `${t.domainsCname}: ${domain.cname_record}`
                        : domain.project || domainProject}
                      {domain.certificates_status
                        ? ` · ${t.domainsSsl}: ${domain.certificates_status}`
                        : ""}
                    </p>
                  </div>
                  <span
                    className={
                      /active|ok|ready/i.test(domain.status || "")
                        ? "status-badge status-good"
                        : "status-badge status-muted"
                    }
                  >
                    {domain.status || t.unknown}
                  </span>
                </div>
              ))}
              <div className="mt-3">
                <Button variant="secondary" onClick={() => onStartDomainGoal(domainProject)}>
                  <Plus size={14} /> {t.domainsCta}
                </Button>
              </div>
            </>
          )}
        </Card>
      </div>
    );
  }

  function renderHistory() {
    return (
      <div className="nav-stack">
        <Card className="nav-detail-card">
          <div className="section-eyebrow">{t.historyEyebrow}</div>
          {history.length ? (
            history.map((conversation) => (
              <button
                className="release-row w-full text-start"
                key={conversation.id}
                type="button"
                onClick={() => onOpenConversation(conversation)}
              >
                <span className="release-indicator">
                  <Sparkles size={12} />
                </span>
                <span className="flex-1">
                  <span className="block text-sm text-slate-200">{conversation.title}</span>
                  <span className="mt-1 block text-xs text-slate-600">
                    {new Date(conversation.updatedAt).toLocaleString()}
                  </span>
                </span>
                <span className="status-badge status-muted">{t.open}</span>
              </button>
            ))
          ) : (
            <div className="inspector-empty compact">
              <Clock3 size={18} />
              <p>{t.historyEmpty}</p>
            </div>
          )}
        </Card>
        <Card className="nav-detail-card">
          <div className="section-eyebrow">{t.auditEyebrow}</div>
          {!workspaceId ? (
            <p className="nav-inline-muted">{t.auditUnavailable}</p>
          ) : auditState === "loading" ? (
            <div className="ui-loading-row" aria-busy="true"><span className="mini-spinner" /><span>{t.loading}</span></div>
          ) : auditState === "error" ? (
            <StateCard
              tone="error"
              title={auditError || t.servicesError}
              body=""
              actionLabel={t.retry}
              onAction={() => void loadAudit()}
            />
          ) : audit.length === 0 ? (
            <p className="nav-inline-muted">{t.auditEmpty}</p>
          ) : (
            audit.map((event) => (
              <div className="release-row" key={event.id}>
                <span className="release-indicator">
                  <CircleHelp size={12} />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-slate-200">{event.event_type}</p>
                  <p className="mt-1 text-xs text-slate-600">
                    {event.actor || "system"}
                    {event.created_at
                      ? ` · ${new Date(event.created_at).toLocaleString()}`
                      : ""}
                  </p>
                </div>
              </div>
            ))
          )}
        </Card>
      </div>
    );
  }

  const showRefresh =
    activeNav === "My Services"
    || activeNav === "Deployments"
    || activeNav === "Monitoring"
    || activeNav === "Domains"
    || activeNav === "Agent History";

  function onRefresh() {
    if (activeNav === "My Services" || activeNav === "Deployments") {
      void onRefreshServices();
      if (activeNav === "Deployments") void loadPlans();
      return;
    }
    if (activeNav === "Monitoring") {
      if (selectedProject) void loadServiceMonitoring(selectedProject, selectedKind);
      else void loadIncidents();
      return;
    }
    if (activeNav === "Domains") {
      void onRefreshServices();
      if (domainProject) void loadDomains(domainProject);
      return;
    }
    if (activeNav === "Agent History") void loadAudit();
  }

  return (
    <div className="nav-view-scroll">
      <header className="chat-topbar">
        <button className="mobile-menu icon-button" onClick={onOpenNav} aria-label="باز کردن منو">
          <Menu size={18} />
        </button>
        <div className="flex items-center gap-2">
          <span className="topbar-spark">
            <Icon size={14} />
          </span>
          <span className="text-sm font-medium text-slate-200">{content.title}</span>
        </div>
        <span
          className={`logical-end connection-chip ${connectionOk ? "connection-chip-ok" : "connection-chip-warn"}`}
          title={topbarLabel}
        >
          <span className="connection-chip-dot" aria-hidden />
          <span>{topbarLabel}</span>
        </span>
      </header>
      <div className="nav-view-content">
        <motion.div
          key={`${activeNav}:${selectedProject || "default"}`}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.22, ease: [0.22, 0.75, 0.28, 1] }}
        >
          <div className="section-hero">
            <div className="section-hero-icon">
              <Icon size={20} />
            </div>
            <div>
              <h1>
                {activeNav === "Monitoring" && selectedProject
                  ? selectedProject
                  : content.title}
              </h1>
              <p>{content.subtitle}</p>
            </div>
            <div className="logical-end flex items-center gap-2">
              {showRefresh ? (
                <Button variant="secondary" onClick={onRefresh} aria-label={t.refresh}>
                  <RefreshCw size={14} /> {t.refresh}
                </Button>
              ) : null}
              <Button variant="secondary" onClick={onStart}>
                <Plus size={14} /> {t.newChat}
              </Button>
            </div>
          </div>
          {activeNav === "My Services" && renderServices()}
          {activeNav === "Deployments" && renderDeployments()}
          {activeNav === "Monitoring" && renderMonitoring()}
          {activeNav === "Domains" && renderDomains()}
          {activeNav === "Agent History" && renderHistory()}
          {activeNav === "New Chat" && null}
        </motion.div>
      </div>
    </div>
  );
}
