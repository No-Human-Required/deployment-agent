import { useEffect, useState } from "react";
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
  type Service,
} from "../../lib/api";
import type { Conversation } from "../../lib/conversations";
import type {
  LiaraDomain,
  LiaraPlan,
  MaintainAuditEvent,
  MaintainIncident,
  SettingsView,
} from "../../lib/schemas";
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
      subtitle: "Incidents from the companion maintain API.",
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
      subtitle: "حوادث از API نگهداری همراه.",
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
    live: "LIVE",
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
    live: "زنده",
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

  const [plans, setPlans] = useState<LiaraPlan[]>([]);
  const [plansState, setPlansState] = useState<LoadState>("idle");
  const [plansError, setPlansError] = useState("");

  const [incidents, setIncidents] = useState<MaintainIncident[]>([]);
  const [incidentsState, setIncidentsState] = useState<LoadState>("idle");
  const [incidentsError, setIncidentsError] = useState("");

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
    if (activeNav === "Monitoring") void loadIncidents();
    if (activeNav === "Agent History") void loadAudit();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reload when surface / credentials change
  }, [activeNav, workspaceId, tokenConfigured]);

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

  const topbarMode =
    tokenConfigured || activeNav === "Agent History"
      ? "topbar-mode topbar-mode-live"
      : "topbar-mode";

  const topbarLabel = t.live;

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

  function renderMonitoring() {
    if (!workspaceId) {
      return (
        <StateCard
          tone="warn"
          title={t.monitorNeedWorkspace}
          body={t.noTokenBody}
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
          body={t.monitorEmptyBody}
          actionLabel={t.monitorCta}
          onAction={onStartMonitorGoal}
        />
      );
    }
    return (
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
    if (activeNav === "Monitoring") void loadIncidents();
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
        <span className={`logical-end ${topbarMode}`}>
          <span /> {topbarLabel}
        </span>
      </header>
      <div className="nav-view-content">
        <motion.div
          key={activeNav}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.22, ease: [0.22, 0.75, 0.28, 1] }}
        >
          <div className="section-hero">
            <div className="section-hero-icon">
              <Icon size={20} />
            </div>
            <div>
              <h1>{content.title}</h1>
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
