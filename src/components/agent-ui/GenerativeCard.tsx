import {
  Activity,
  AlertCircle,
  ArrowDownRight,
  ArrowUpRight,
  Check,
  CheckCircle2,
  CircleDashed,
  ClipboardList,
  Clock3,
  Cloud,
  Database,
  ExternalLink,
  FileCode2,
  FileText,
  GitBranch,
  Globe2,
  LoaderCircle,
  Radio,
  Settings2,
  ShieldAlert,
  ShieldCheck,
  Siren,
  Stethoscope,
  Terminal,
  X,
  XCircle,
  Zap,
} from "lucide-react";
import { motion } from "motion/react";
import { useState, type ReactNode } from "react";
import type { ApprovalResult, ViewPayload } from "../../lib/schemas";
import { sortPlansWeakToStrong } from "../../lib/sortPlans";
import { Button } from "../ui/button";
import { Card } from "../ui/card";

type Locale = "en" | "fa";

export type IntakeConfirmValues = {
  project_name: string;
  plan_id?: string;
  platform?: string;
  domain_name?: string;
};

function formatTomans(value: number | null | undefined, language: Locale): string {
  if (value == null || Number.isNaN(value)) {
    return language === "fa" ? "قیمت نامشخص" : "Price n/a";
  }
  const rounded = Math.round(value);
  const formatted = new Intl.NumberFormat(language === "fa" ? "fa-IR" : "en-US").format(rounded);
  return language === "fa" ? `${formatted} تومان / ماه` : `${formatted} Tomans/mo`;
}

function PlanTierIcon({ tier }: { tier: number }) {
  const bars = Math.min(4, Math.max(1, tier <= 2 ? 1 : tier <= 4 ? 2 : tier <= 6 ? 3 : 4));
  return (
    <svg className="plan-tier-icon" viewBox="0 0 24 24" width="22" height="22" aria-hidden>
      {[0, 1, 2, 3].map((index) => (
        <rect
          key={index}
          x={3 + index * 5}
          y={18 - (index + 1) * 3.5}
          width="3.5"
          height={(index + 1) * 3.5}
          rx="1"
          fill={index < bars ? "currentColor" : "rgba(148,163,184,.35)"}
        />
      ))}
    </svg>
  );
}

type Props = {
  payload: ViewPayload;
  pending?: boolean;
  busy?: boolean;
  language?: Locale;
  approvalResult?: ApprovalResult | null;
  onApproval?: (decision: "approve" | "reject") => void;
  /** Confirm in-chat intake (service / plan / domain) before createPlan. */
  onIntakeConfirm?: (values: IntakeConfirmValues) => void;
  onOpenSettings?: () => void;
};

const cardCopy = {
  en: {
    approve: "Approve & run",
    reject: "Reject",
    pending: "Pending",
    awaiting: "Awaiting you",
    approved: "Approved",
    rejected: "Rejected",
    approvalRequired: "Approval required",
    approvalDecision: "Approval decision",
    proposedAction: "Proposed action",
    planTitle: "Proposed plan",
    steps: "Steps",
    readiness: "Readiness findings",
    evidence: "Evidence pack",
    diagnosis: "Diagnosis",
    deps: "Dependency plan",
    patch: "Patch diff",
    monitor: "Monitor status",
    incident: "Incident",
    opStatus: "Operation status",
    verification: "Verification result",
    unsupported: "Unsupported agent view",
    unsupportedBody: (type: string) =>
      `The view type “${type}” is not enabled. No action was taken.`,
    writeNotAuthorized: "Alert does not authorize writes",
    monitorNoWrite: "Enable ≠ write permission",
    intakeConfirm: "Continue",
    intakeService: "Service",
    intakePlan: "Plan",
    intakePlatform: "Platform",
    intakeDomain: "Custom domain (optional)",
    intakeDomainHint: "Leave empty to use the default liara.run URL after deploy.",
    intakeNewService: "New service",
    intakeNewServiceName: "New service name",
    intakeExistingService: "Existing service",
    intakeEmptyServices: "No existing services — enter a new name, or check Settings.",
    intakeSuggested: "Suggested from your project",
    intakeLoadError: "Could not load Liara catalog",
    openSettings: "Open Settings",
    intakeSelectService: "Select a service",
    intakeSelectPlan: "Choose a plan",
    intakeSelectPlatform: "Choose a platform",
    intakeEnterDomain: "Enter a domain (e.g. example.com)",
  },
  fa: {
    approve: "تأیید و اجرا",
    reject: "رد",
    pending: "در انتظار",
    awaiting: "در انتظار شما",
    approved: "تأیید شد",
    rejected: "رد شد",
    approvalRequired: "نیاز به تأیید",
    approvalDecision: "نتیجه تأیید",
    proposedAction: "اقدام پیشنهادی",
    planTitle: "طرح پیشنهادی",
    steps: "گام‌ها",
    readiness: "نتیجه بررسی آمادگی",
    evidence: "بسته شواهد",
    diagnosis: "تشخیص",
    deps: "طرح وابستگی",
    patch: "اختلاف وصله",
    monitor: "وضعیت پایش",
    incident: "حادثه",
    opStatus: "وضعیت عملیات",
    verification: "نتیجه راستی‌آزمایی",
    unsupported: "نمای پشتیبانی‌نشده",
    unsupportedBody: (type: string) =>
      `نوع نمای «${type}» فعال نیست. هیچ اقدامی انجام نشد.`,
    writeNotAuthorized: "هشدار مجوز نوشتن نمی‌دهد",
    monitorNoWrite: "فعال‌سازی ≠ مجوز نوشتن",
    intakeConfirm: "ادامه",
    intakeService: "سرویس",
    intakePlan: "پلن",
    intakePlatform: "پلتفرم",
    intakeDomain: "دامنه اختصاصی (اختیاری)",
    intakeDomainHint: "خالی بگذارید تا بعد از استقرار از آدرس پیش‌فرض liara.run استفاده شود.",
    intakeNewService: "سرویس جدید",
    intakeNewServiceName: "نام سرویس جدید",
    intakeExistingService: "سرویس موجود",
    intakeEmptyServices: "سرویس موجودی نیست — نام جدید وارد کنید یا تنظیمات را بررسی کنید.",
    intakeSuggested: "پیشنهاد بر اساس پروژه شما",
    intakeLoadError: "بارگذاری فهرست لیارا ناموفق بود",
    openSettings: "باز کردن تنظیمات",
    intakeSelectService: "یک سرویس انتخاب کنید",
    intakeSelectPlan: "یک پلن انتخاب کنید",
    intakeSelectPlatform: "یک پلتفرم انتخاب کنید",
    intakeEnterDomain: "دامنه را وارد کنید (مثلاً example.com)",
  },
};

function ModeTag({ mode }: { mode?: string }) {
  if (mode === "LIVE") {
    return <span className="demo-pill live-pill"><span className="status-dot" /> LIVE · Liara</span>;
  }
  return <span className="demo-pill"><span className="status-dot" /> DEMO · simulated</span>;
}

function Heading({ icon: Icon, title, right }: { icon: typeof Activity; title: string; right?: ReactNode }) {
  return (
    <div className="card-heading">
      <div className="card-heading-icon"><Icon size={15} /></div>
      <span>{title}</span>
      {right ? <div className="card-heading-actions">{right}</div> : null}
    </div>
  );
}

function UnsupportedCard({ type, language }: { type: string; language: Locale }) {
  const strings = cardCopy[language];
  return (
    <Card className="genui-card">
      <Heading icon={Database} title={strings.unsupported} />
      <p className="text-xs leading-relaxed text-slate-400">{strings.unsupportedBody(type)}</p>
    </Card>
  );
}

function EnterCard({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.22, ease: [0.22, 0.75, 0.28, 1] }}
    >
      {children}
    </motion.div>
  );
}

type IntakeData = {
  kind: "deploy" | "ops_resize" | "domain" | "troubleshoot" | "maintain_monitor";
  title: string;
  prompt?: string | null;
  services: { id: string; name: string; status?: string }[];
  plans: {
    id: string;
    label: string;
    hint?: string | null;
    price_monthly?: number | null;
    ram_gb?: number | null;
    tier?: number;
  }[];
  platforms?: { id: string; label: string; hint?: string | null; icon?: string | null }[];
  require_plan: boolean;
  require_domain: boolean;
  require_platform?: boolean;
  suggested_platform?: string | null;
  suggested_service_name?: string | null;
  prefer_new_service?: boolean;
  load_error?: string | null;
  settings_cta: boolean;
};

function IntakeCard({
  data,
  language,
  strings,
  busy,
  pending,
  onConfirm,
  onOpenSettings,
}: {
  data: IntakeData;
  language: Locale;
  strings: (typeof cardCopy)["en"];
  busy?: boolean;
  pending?: boolean;
  onConfirm?: (values: IntakeConfirmValues) => void;
  onOpenSettings?: () => void;
}) {
  const preferNew = Boolean(data.prefer_new_service) || data.services.length === 0;
  const [serviceMode, setServiceMode] = useState<"new" | "existing">(
    preferNew ? "new" : "existing",
  );
  const [serviceId, setServiceId] = useState(data.services[0]?.id ?? "");
  const [customName, setCustomName] = useState(data.suggested_service_name?.trim() || "");
  const [planId, setPlanId] = useState(
    () => sortPlansWeakToStrong(data.plans)[0]?.id ?? "",
  );
  const [platformId, setPlatformId] = useState(
    data.suggested_platform || data.platforms?.[0]?.id || "",
  );
  const [domainName, setDomainName] = useState("");
  const interactive = Boolean(pending && onConfirm);

  const projectName =
    serviceMode === "new"
      ? customName.trim()
      : data.services.find((s) => s.id === serviceId)?.name || serviceId;

  const canSubmit =
    Boolean(projectName) &&
    (!data.require_plan || Boolean(planId)) &&
    (!data.require_platform || Boolean(platformId)) &&
    (!data.require_domain || Boolean(domainName.trim()));

  const Icon =
    data.kind === "domain"
      ? Globe2
      : data.kind === "troubleshoot" || data.kind === "maintain_monitor"
        ? Activity
        : Cloud;

  return (
    <EnterCard>
      <Card className="genui-card intake-card">
        <Heading icon={Icon} title={data.title} />
        {data.prompt ? <p className="text-sm leading-relaxed text-slate-600">{data.prompt}</p> : null}

        {data.load_error ? (
          <div className="warn-callout mt-2.5 p-2.5">
            <p className="warn-callout-title">{strings.intakeLoadError}</p>
            <p className="warn-callout-body">{data.load_error}</p>
            {data.settings_cta && onOpenSettings ? (
              <Button variant="ghost" size="sm" className="mt-2" onClick={onOpenSettings} type="button">
                <Settings2 size={14} /> {strings.openSettings}
              </Button>
            ) : null}
          </div>
        ) : null}

        <div className="mt-3 space-y-3">
          <div>
            <p className="text-[11px] uppercase tracking-wide text-slate-500">{strings.intakeService}</p>
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              <button
                type="button"
                className={`intake-chip ${serviceMode === "new" ? "is-active" : ""}`}
                disabled={!interactive || busy}
                onClick={() => {
                  setServiceMode("new");
                  if (!customName.trim() && data.suggested_service_name) {
                    setCustomName(data.suggested_service_name);
                  }
                }}
              >
                {strings.intakeNewService}
              </button>
              {data.services.length > 0 ? (
                <button
                  type="button"
                  className={`intake-chip ${serviceMode === "existing" ? "is-active" : ""}`}
                  disabled={!interactive || busy}
                  onClick={() => setServiceMode("existing")}
                >
                  {strings.intakeExistingService}
                </button>
              ) : null}
            </div>

            {serviceMode === "new" ? (
              <>
                {data.services.length === 0 ? (
                  <p className="mt-1.5 text-[11px] text-slate-500">{strings.intakeEmptyServices}</p>
                ) : null}
                <input
                  className="intake-input mt-1.5"
                  value={customName}
                  disabled={!interactive || busy}
                  placeholder={strings.intakeNewServiceName}
                  aria-label={strings.intakeNewServiceName}
                  dir="ltr"
                  onChange={(event) => setCustomName(event.target.value)}
                />
              </>
            ) : (
              <div className="mt-1.5 max-h-40 space-y-1 overflow-auto">
                {data.services.map((service) => (
                  <label
                    key={service.id}
                    className={`intake-radio-row ${serviceId === service.id ? "is-active" : ""}`}
                  >
                    <input
                      type="radio"
                      name="intake-service"
                      className="accent-sky-600"
                      checked={serviceId === service.id}
                      disabled={!interactive || busy}
                      onChange={() => setServiceId(service.id)}
                    />
                    <span className="min-w-0 flex-1 truncate font-medium">{service.name}</span>
                    {service.status ? (
                      <span className="shrink-0 text-[10px] text-slate-500">{service.status}</span>
                    ) : null}
                  </label>
                ))}
              </div>
            )}
          </div>

          {data.require_platform ? (
            <div>
              <p className="text-[11px] uppercase tracking-wide text-slate-500">{strings.intakePlatform}</p>
              {data.suggested_platform ? (
                <p className="mt-1 text-[11px] text-sky-700">
                  {strings.intakeSuggested}
                  {": "}
                  <span className="font-medium" dir="ltr">
                    {(data.platforms ?? []).find((p) => p.id === data.suggested_platform)?.label ||
                      data.suggested_platform}
                  </span>
                </p>
              ) : null}
              <div className="intake-platform-grid mt-1.5" role="radiogroup" aria-label={strings.intakeSelectPlatform}>
                {(data.platforms ?? []).map((platform) => {
                  const active = platformId === platform.id;
                  const suggested = data.suggested_platform === platform.id;
                  const iconSrc = platform.icon || `/platform-icons/${platform.id}.svg`;
                  return (
                    <label
                      key={platform.id}
                      className={`intake-platform-tile ${active ? "is-active" : ""} ${suggested ? "is-suggested" : ""}`}
                    >
                      <input
                        type="radio"
                        name="intake-platform"
                        className="sr-only"
                        checked={active}
                        disabled={!interactive || busy}
                        onChange={() => setPlatformId(platform.id)}
                      />
                      <img
                        src={iconSrc}
                        alt=""
                        className="intake-platform-icon"
                        width={28}
                        height={28}
                        onError={(event) => {
                          const el = event.currentTarget;
                          if (el.dataset.fallback === "1") {
                            el.style.visibility = "hidden";
                            return;
                          }
                          el.dataset.fallback = "1";
                          el.src = `/platform-icons/${platform.id === "node" ? "nodejs" : platform.id}.svg`;
                        }}
                      />
                      <span className="intake-platform-name">{platform.label}</span>
                    </label>
                  );
                })}
              </div>
            </div>
          ) : null}

          {data.require_plan ? (
            <div>
              <p className="text-[11px] uppercase tracking-wide text-slate-500">{strings.intakePlan}</p>
              <div className="intake-plan-grid mt-1.5" role="radiogroup" aria-label={strings.intakeSelectPlan}>
                {sortPlansWeakToStrong(data.plans).map((plan, index) => {
                  const active = planId === plan.id;
                  const tier = plan.tier ?? index + 1;
                  return (
                    <label key={plan.id} className={`intake-plan-tile ${active ? "is-active" : ""}`}>
                      <input
                        type="radio"
                        name="intake-plan"
                        className="sr-only"
                        checked={active}
                        disabled={!interactive || busy}
                        onChange={() => setPlanId(plan.id)}
                      />
                      <span className="intake-plan-icon-wrap">
                        <PlanTierIcon tier={tier} />
                      </span>
                      <span className="intake-plan-copy">
                        <span className="intake-plan-name" dir="ltr">
                          {plan.label}
                        </span>
                        {plan.hint ? <span className="intake-plan-hint">{plan.hint}</span> : null}
                        <span className="intake-plan-price">{formatTomans(plan.price_monthly, language)}</span>
                      </span>
                    </label>
                  );
                })}
              </div>
            </div>
          ) : null}

          {data.require_domain || data.kind === "deploy" ? (
            <div>
              <p className="text-[11px] uppercase tracking-wide text-slate-500">{strings.intakeDomain}</p>
              {!data.require_domain && strings.intakeDomainHint ? (
                <p className="mt-0.5 text-[11px] text-slate-500">{strings.intakeDomainHint}</p>
              ) : null}
              <input
                className="intake-input mt-1.5"
                value={domainName}
                disabled={!interactive || busy}
                placeholder={strings.intakeEnterDomain}
                aria-label={strings.intakeEnterDomain}
                dir="ltr"
                onChange={(event) => setDomainName(event.target.value)}
              />
            </div>
          ) : null}
        </div>

        {interactive ? (
          <div className="mt-3 flex flex-wrap gap-2">
            <Button
              variant="success"
              size="sm"
              type="button"
              disabled={busy || !canSubmit}
              onClick={() => {
                if (!onConfirm || !canSubmit) return;
                onConfirm({
                  project_name: projectName,
                  ...(data.require_plan && planId ? { plan_id: planId } : {}),
                  ...(data.require_platform && platformId ? { platform: platformId } : {}),
                  ...((data.require_domain || data.kind === "deploy") && domainName.trim()
                    ? { domain_name: domainName.trim() }
                    : {}),
                });
              }}
            >
              {busy ? <LoaderCircle className="animate-spin" size={14} /> : <CheckCircle2 size={14} />}
              {strings.intakeConfirm}
            </Button>
          </div>
        ) : (
          <p className="mt-2.5 flex items-center gap-1 text-[11px] text-slate-500">
            <CircleDashed size={12} /> {language === "fa" ? "در انتظار انتخاب" : "Awaiting selection"}
          </p>
        )}
      </Card>
    </EnterCard>
  );
}

export function GenerativeCard({
  payload,
  pending,
  busy,
  language = "en",
  approvalResult,
  onApproval,
  onIntakeConfirm,
  onOpenSettings,
}: Props) {
  const strings = cardCopy[language];

  switch (payload.type) {
    case "intake":
      return (
        <IntakeCard
          data={payload.data}
          language={language}
          strings={strings}
          busy={busy}
          pending={pending}
          onConfirm={onIntakeConfirm}
          onOpenSettings={onOpenSettings}
        />
      );
    case "service_status":
      return (
        <EnterCard>
          <Card className="genui-card">
            <Heading icon={Cloud} title="Service overview" right={<ModeTag mode={payload.data.mode} />} />
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-white">{payload.data.name}</p>
                <a className="small-link" href={payload.data.url} target="_blank" rel="noreferrer">
                  {payload.data.url}<ExternalLink size={11} />
                </a>
              </div>
              <span className="status-badge status-warn"><span className="status-dot" />{payload.data.status}</span>
            </div>
          </Card>
        </EnterCard>
      );
    case "deployment_progress":
      return (
        <EnterCard>
          <Card className="genui-card">
            <Heading icon={Cloud} title="Current release" />
            <div className="flex items-center justify-between text-xs">
              <span className="font-mono text-slate-200">{payload.data.version}</span>
              <span className="text-slate-400">{payload.data.status}</span>
            </div>
            <div className="progress-track mt-2.5"><span style={{ width: `${payload.data.progress}%` }} /></div>
          </Card>
        </EnterCard>
      );
    case "timeline":
      return (
        <EnterCard>
          <Card className="genui-card">
            <Heading icon={Activity} title="Agent execution" right={<span className="live-label"><span /> Complete</span>} />
            <div className="timeline-list">
              {payload.data.steps.map((step, index) => (
                <div className="timeline-row" key={`${step.tool}-${index}`}>
                  <div className="timeline-marker"><Check size={11} /></div>
                  <div className="min-w-0 pb-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-xs font-medium text-slate-200">{step.title}</span>
                      <span className="tool-chip">{step.tool}</span>
                    </div>
                    <p className="mt-1 text-xs leading-relaxed text-slate-400">{step.detail}</p>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </EnterCard>
      );
    case "tool_call":
      return (
        <div className="tool-stack">
          {payload.data.tools.map((tool, index) => (
            <Card className="tool-row" key={`${tool.tool}-${index}`}>
              <span className="tool-icon"><Terminal size={13} /></span>
              <span className="min-w-0 flex-1 truncate font-mono text-[11px] text-slate-300">{tool.tool}</span>
              <span className="tool-complete"><Check size={12} /> done</span>
              <span className="tool-demo">{payload.data.mode === "LIVE" ? "LIVE" : "DEMO"}</span>
            </Card>
          ))}
        </div>
      );
    case "log_viewer":
      return (
        <EnterCard>
          <Card className="genui-card">
            <Heading icon={FileText} title="Recent logs" right={<ModeTag mode={payload.data.mode} />} />
            <div className="log-list">
              {payload.data.logs.map((log, index) => (
                <div className="log-row" key={`${log.time}-${index}`}>
                  <time>{log.time}</time>
                  <span className={log.level === "ERROR" ? "log-level-error" : "log-level-warn"}>{log.level}</span>
                  <span className="min-w-0 break-all font-mono text-[10px] text-slate-400">{log.message}</span>
                </div>
              ))}
            </div>
          </Card>
        </EnterCard>
      );
    case "metric":
      return (
        <div className="metric-grid">
          {payload.data.metrics.map((metric) => {
            const increase = metric.change.startsWith("+");
            return (
              <Card className="metric-card" key={metric.name}>
                <div className="flex items-center justify-between text-[11px] text-slate-500">
                  <span>{metric.name}</span>
                  <span className={increase ? "warn-note font-medium" : "font-medium text-emerald-700"}>
                    {increase ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
                  </span>
                </div>
                <div className="mt-2 flex items-baseline gap-1">
                  <strong>{metric.value}</strong><span>{metric.unit}</span>
                </div>
                <div className="mt-1 text-[10px] text-slate-600">{metric.change} vs previous hour</div>
              </Card>
            );
          })}
        </div>
      );
    case "error_analysis":
      return (
        <EnterCard>
          <Card className="genui-card border-rose-400/[.15] bg-rose-400/[.035]">
            <Heading icon={AlertCircle} title={payload.data.title} right={<span className="status-badge status-warn">Live analysis</span>} />
            <p className="text-sm text-slate-300">{payload.data.summary}</p>
            <div className="mt-2.5 flex flex-wrap gap-2">
              {payload.data.evidence.slice(0, 3).map((item) => (
                <span className="evidence-tag" key={item.slice(0, 48)}>{item.slice(0, 48)}{item.length > 48 ? "…" : ""}</span>
              ))}
            </div>
          </Card>
        </EnterCard>
      );
    case "root_cause":
      return (
        <EnterCard>
          <Card className="root-cause-card genui-card">
            <Heading
              icon={Zap}
              title="Probable root cause"
              right={<span className="confidence-badge"><span /> {payload.data.confidence} confidence</span>}
            />
            <h3 className="mb-1 text-sm font-semibold text-white">{payload.data.title}</h3>
            <p className="text-xs leading-relaxed text-slate-400">{payload.data.description}</p>
            <div className="mt-2.5 space-y-2">
              {payload.data.evidence.map((item, index) => (
                <div className="evidence-row" key={item}><span>{String(index + 1).padStart(2, "0")}</span>{item}</div>
              ))}
            </div>
          </Card>
        </EnterCard>
      );
    case "plan":
      return (
        <EnterCard>
          <Card className="genui-card">
            <Heading icon={ClipboardList} title={strings.planTitle} />
            {payload.data.summary ? <p className="text-sm leading-relaxed text-slate-200">{payload.data.summary}</p> : null}
            <div className="mt-2.5 space-y-1.5">
              <p className="text-[11px] uppercase tracking-wide text-slate-500">{strings.steps}</p>
              {payload.data.steps.map((step) => (
                <div
                  key={step.id}
                  className="rounded-lg border border-white/[.07] bg-black/20 px-2.5 py-1.5 text-xs text-slate-300"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium text-slate-100">{step.action}</span>
                    {step.tool_id ? <span className="tool-chip">{step.tool_id}</span> : null}
                  </div>
                  {step.effects.length > 0 ? (
                    <p className="mt-1 text-[11px] text-slate-500">{step.effects.join(" · ")}</p>
                  ) : null}
                </div>
              ))}
            </div>
            <div className="mt-2.5 grid grid-cols-2 gap-2 text-[10px] text-slate-500">
              {payload.data.case_id ? (
                <div>
                  <span className="detail-label">Case</span>
                  <p className="mt-1 font-mono text-slate-400">{payload.data.case_id.slice(0, 12)}…</p>
                </div>
              ) : null}
              {payload.data.content_hash ? (
                <div>
                  <span className="detail-label">Hash</span>
                  <p className="mt-1 font-mono text-slate-400">{payload.data.content_hash.slice(0, 12)}…</p>
                </div>
              ) : null}
            </div>
          </Card>
        </EnterCard>
      );
    case "approval":
      return (
        <EnterCard>
          <Card className="approval-card genui-card">
            <Heading
              icon={ShieldAlert}
              title={approvalResult ? strings.approvalDecision : strings.approvalRequired}
              right={approvalResult ? (
                <span className={approvalResult.status === "completed" ? "status-badge status-good" : "status-badge status-muted"}>
                  {approvalResult.status === "completed" ? strings.approved : strings.rejected}
                </span>
              ) : <span className="status-badge status-warn"><Clock3 size={11} /> {strings.awaiting}</span>}
            />
            {!approvalResult ? (
              <>
                <div className="rounded-lg border border-white/[.08] bg-black/20 p-2.5">
                  <p className="text-xs text-slate-500">{strings.proposedAction}</p>
                  <p className="mt-1 text-sm font-medium text-white">{payload.data.action}</p>
                </div>
                <div className="warn-callout-inline mt-2.5">
                  <ShieldAlert className="mt-0.5 shrink-0" size={14} />
                  <span>{payload.data.risk}</span>
                </div>
                {pending && onApproval ? (
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button variant="success" size="sm" onClick={() => onApproval("approve")} disabled={busy}>
                      {busy ? <LoaderCircle className="animate-spin" size={14} /> : <CheckCircle2 size={14} />}
                      {strings.approve}
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => onApproval("reject")} disabled={busy}>
                      <X size={14} /> {strings.reject}
                    </Button>
                  </div>
                ) : <p className="mt-2.5 flex items-center gap-1 text-[11px] text-slate-500"><CircleDashed size={12} /> {strings.pending}</p>}
              </>
            ) : (
              <div className="rounded-lg border border-white/[.07] bg-black/20 p-2.5 text-xs text-slate-300">
                <div className="flex items-center gap-2">
                  {approvalResult.status === "completed" ? <ShieldCheck className="text-emerald-300" size={15} /> : <XCircle className="text-slate-400" size={15} />}
                  {approvalResult.message}
                </div>
              </div>
            )}
          </Card>
        </EnterCard>
      );
    case "readiness_findings":
      return (
        <EnterCard>
          <Card className="genui-card">
            <Heading
              icon={ClipboardList}
              title={strings.readiness}
              right={
                <span className={`status-badge ${payload.data.ready ? "status-good" : "status-warn"}`}>
                  {payload.data.ready ? "ready" : "blocked"}
                </span>
              }
            />
            {payload.data.notes ? <p className="text-sm text-slate-300">{payload.data.notes}</p> : null}
            {payload.data.open_needs.length > 0 ? (
              <div className="mt-2.5 flex flex-wrap gap-2">
                {payload.data.open_needs.map((need) => (
                  <span className="evidence-tag" key={need}>{need}</span>
                ))}
              </div>
            ) : null}
            {payload.data.findings.length > 0 ? (
              <div className="mt-2.5 space-y-1.5">
                {payload.data.findings.map((finding) => (
                  <div className="rounded-lg border border-white/[.07] bg-black/20 px-2.5 py-1.5 text-xs" key={`${finding.code}-${finding.message}`}>
                    <span className="tool-chip">{finding.severity}</span>
                    <p className="mt-1 text-slate-300">{finding.message}</p>
                  </div>
                ))}
              </div>
            ) : null}
          </Card>
        </EnterCard>
      );
    case "evidence_pack":
      return (
        <EnterCard>
          <Card className="genui-card">
            <Heading
              icon={FileText}
              title={strings.evidence}
              right={<span className={`status-badge ${payload.data.complete ? "status-good" : "status-warn"}`}>
                {payload.data.complete ? "complete" : "gaps"}
              </span>}
            />
            <p className="text-sm font-medium text-white">{payload.data.project_name}</p>
            {payload.data.symptom ? <p className="mt-1 text-xs text-slate-400">{payload.data.symptom}</p> : null}
            <div className="mt-2.5 space-y-2">
              {payload.data.facts.map((fact) => (
                <div className="evidence-row" key={fact.id}><span>{fact.source}</span>{fact.summary}</div>
              ))}
            </div>
            {payload.data.gaps.length > 0 ? (
              <div className="mt-2.5 flex flex-wrap gap-2">
                {payload.data.gaps.map((gap) => (
                  <span className="evidence-tag" key={`${gap.source}-${gap.reason}`}>{gap.source}: {gap.reason}</span>
                ))}
              </div>
            ) : null}
          </Card>
        </EnterCard>
      );
    case "diagnosis":
      return (
        <EnterCard>
          <Card className="genui-card">
            <Heading
              icon={Stethoscope}
              title={strings.diagnosis}
              right={payload.data.insufficient_evidence
                ? <span className="status-badge status-warn">insufficient</span>
                : <span className="status-badge status-good">ranked</span>}
            />
            {payload.data.summary ? <p className="text-sm text-slate-300">{payload.data.summary}</p> : null}
            <div className="mt-2.5 space-y-1.5">
              {payload.data.hypotheses.map((hypothesis) => (
                <div className="rounded-lg border border-white/[.07] bg-black/20 px-2.5 py-1.5 text-xs" key={hypothesis.id}>
                  <span className="text-slate-500">#{hypothesis.rank}</span>
                  <p className="mt-1 text-slate-200">{hypothesis.statement}</p>
                </div>
              ))}
            </div>
            {payload.data.next_read_or_question ? (
              <p className="mt-2.5 text-[11px] text-slate-500">{payload.data.next_read_or_question}</p>
            ) : null}
          </Card>
        </EnterCard>
      );
    case "dependency_plan":
      return (
        <EnterCard>
          <Card className="genui-card">
            <Heading icon={GitBranch} title={strings.deps} />
            {payload.data.summary ? <p className="text-sm text-slate-300">{payload.data.summary}</p> : null}
            {payload.data.required_kinds.length > 0 ? (
              <div className="mt-2.5 flex flex-wrap gap-2">
                {payload.data.required_kinds.map((kind) => (
                  <span className="tool-chip" key={kind}>{kind}</span>
                ))}
              </div>
            ) : null}
            <div className="mt-2.5 space-y-1.5">
              {payload.data.findings.map((finding) => (
                <div className="rounded-lg border border-white/[.07] bg-black/20 px-2.5 py-1.5 text-xs" key={`${finding.code}-${finding.message}`}>
                  <span className="font-medium text-slate-100">{finding.kind}</span>
                  <p className="mt-1 text-slate-400">{finding.message}</p>
                </div>
              ))}
            </div>
            {payload.data.open_needs.length > 0 ? (
              <p className="warn-note mt-2.5 text-[11px]">{payload.data.open_needs.join(" · ")}</p>
            ) : null}
          </Card>
        </EnterCard>
      );
    case "patch_diff":
      return (
        <EnterCard>
          <Card className="genui-card">
            <Heading
              icon={FileCode2}
              title={strings.patch}
              right={
                <span className={`status-badge ${payload.data.ready_for_release ? "status-good" : "status-warn"}`}>
                  {payload.data.ready_for_release ? "release-ready" : "gated"}
                </span>
              }
            />
            <p className="text-sm text-slate-200">{payload.data.rationale}</p>
            <pre className="mt-2.5 max-h-36 overflow-auto rounded-lg border border-white/[.07] bg-black/30 p-2.5 font-mono text-[10px] leading-relaxed text-slate-400">
              {payload.data.unified_diff.slice(0, 1200)}
              {payload.data.unified_diff.length > 1200 ? "\n…" : ""}
            </pre>
            {payload.data.files_changed.length > 0 ? (
              <div className="mt-2 flex flex-wrap gap-2">
                {payload.data.files_changed.map((file) => (
                  <span className="evidence-tag" key={file}>{file}</span>
                ))}
              </div>
            ) : null}
          </Card>
        </EnterCard>
      );
    case "monitor_status":
      return (
        <EnterCard>
          <Card className="genui-card">
            <Heading
              icon={Radio}
              title={strings.monitor}
              right={
                <span className={`status-badge ${payload.data.healthy_live ? "status-good" : "status-warn"}`}>
                  {payload.data.last_status}
                </span>
              }
            />
            <p className="font-mono text-xs text-slate-300">{payload.data.target}</p>
            <div className="mt-2.5 grid grid-cols-2 gap-2 text-[11px] text-slate-500">
              <div><span className="detail-label">Enabled</span><p className="mt-1 text-slate-300">{String(payload.data.enabled)}</p></div>
              <div><span className="detail-label">Stale</span><p className="mt-1 text-slate-300">{String(payload.data.stale)}</p></div>
            </div>
            {!payload.data.grants_write_permission ? (
              <p className="warn-note mt-2.5 text-[11px]">{strings.monitorNoWrite}</p>
            ) : null}
          </Card>
        </EnterCard>
      );
    case "incident":
      return (
        <EnterCard>
          <Card className="genui-card border-rose-400/[.12] bg-rose-400/[.03]">
            <Heading
              icon={Siren}
              title={strings.incident}
              right={<span className="status-badge status-warn">{payload.data.status}</span>}
            />
            <p className="text-sm font-medium text-white">{payload.data.title}</p>
            <p className="mt-1 text-[11px] text-slate-500">alerts · {payload.data.alert_count}</p>
            {!payload.data.write_authorized ? (
              <p className="warn-note mt-2.5 text-[11px]">{strings.writeNotAuthorized}</p>
            ) : null}
          </Card>
        </EnterCard>
      );
    case "operation_status":
      return (
        <EnterCard>
          <Card className="genui-card">
            <Heading icon={Activity} title={strings.opStatus} right={<span className="status-badge status-warn">{payload.data.state}</span>} />
            <p className="font-mono text-[10px] text-slate-400">{payload.data.operation_id}</p>
            {payload.data.plan_id ? (
              <p className="mt-2 text-[11px] text-slate-500">plan · {payload.data.plan_id.slice(0, 12)}…</p>
            ) : null}
          </Card>
        </EnterCard>
      );
    case "verification_result":
      return (
        <EnterCard>
          <Card className="result-card genui-card">
            <Heading
              icon={ShieldCheck}
              title={strings.verification}
              right={
                <span className={`status-badge ${payload.data.verified ? "status-good" : "status-warn"}`}>
                  {payload.data.state}
                </span>
              }
            />
            {payload.data.summary ? <p className="text-sm text-slate-200">{payload.data.summary}</p> : null}
            <p className="mt-2 font-mono text-[10px] text-slate-500">{payload.data.operation_id}</p>
          </Card>
        </EnterCard>
      );
    case "operation_result":
      return (
        <EnterCard>
          <Card className="result-card genui-card">
            <Heading icon={ShieldCheck} title="Operation verified" right={<span className="status-badge status-good">Success · {payload.data.mode === "LIVE" ? "LIVE" : "DEMO"}</span>} />
            <p className="text-sm text-slate-200">{payload.data.result}</p>
            <div className="mt-2.5 grid grid-cols-2 gap-3">
              <div><span className="detail-label">Operation</span><p className="mt-1 font-mono text-[10px] text-slate-300">{payload.data.operation_id}</p></div>
              <div><span className="detail-label">Service</span><p className="mt-1 text-xs text-slate-300">{payload.data.service}</p></div>
            </div>
          </Card>
        </EnterCard>
      );
    case "service_health":
      return (
        <EnterCard>
          <Card className="genui-card">
            <Heading icon={Activity} title="Service health" right={<ModeTag mode={payload.data.mode} />} />
            <div className="flex items-center justify-between">
              <span className={payload.data.status === "Healthy" ? "status-badge status-good" : "status-badge status-warn"}>{payload.data.status}</span>
              <span className="text-xs text-slate-500">{payload.data.uptime} uptime</span>
            </div>
          </Card>
        </EnterCard>
      );
    case "unsupported":
      return <UnsupportedCard type={String(payload.data.originalType ?? "unknown")} language={language} />;
    default: {
      const safePayload: unknown = payload;
      const type = typeof safePayload === "object" && safePayload !== null && "type" in safePayload
        ? String(safePayload.type)
        : "unknown";
      return <UnsupportedCard type={type} language={language} />;
    }
  }
}
