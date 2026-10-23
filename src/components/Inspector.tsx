import { useState } from "react";
import { Activity, ChevronDown, FileText, Gauge, Info, Radio, RefreshCw } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./ui/tabs";
import type { OrchestratorRun } from "../lib/schemas";
import type { Service } from "../lib/api";
import { mapOrchestratorToCards } from "../lib/orchestratorCards";
import { timelineStatusLabel } from "../lib/requestTimeline";
import { GenerativeCard } from "./agent-ui/GenerativeCard";
import { Card } from "./ui/card";

type Props = {
  run: OrchestratorRun | null;
  service: Service | null;
  loading: boolean;
  open: boolean;
  language: "en" | "fa";
};

const copy = {
  en: {
    title: "Inspector",
    subtitle: "Execution context",
    activity: "Activity",
    logs: "Logs",
    metrics: "Metrics",
    details: "Details",
    currentRun: "CURRENT RUN",
    steps: "EXECUTION STEPS",
    audit: "AUDIT TRAIL",
    case: "CASE",
    emptyTitle: "No active execution",
    emptyHint: "Send a chat goal to see the orchestrator timeline here.",
    logsEmpty: "Orchestrator events appear after a case starts.",
    metricsEmpty: "Metrics for live ops arrive in later surfaces.",
    detailsEmpty: "Case and operation details show once a run starts.",
    stage: "Stage",
    caseId: "Case ID",
    planId: "Plan ID",
    operationId: "Operation",
    opState: "Op state",
    goal: "Goal",
    noteLive: "Provider writes require explicit Approve — chat text is never authorization.",
    refresh: "Refresh inspector",
  },
  fa: {
    title: "جزئیات",
    subtitle: "وضعیت اجرای فعلی",
    activity: "فعالیت",
    logs: "گزارش‌ها",
    metrics: "آمار",
    details: "جزئیات",
    currentRun: "اجرای جاری",
    steps: "گام‌های اجرا",
    audit: "سابقه اقدامات",
    case: "پرونده",
    emptyTitle: "اجرای فعالی نیست",
    emptyHint: "یک هدف در گفتگو بفرستید تا روند کار اینجا دیده شود.",
    logsEmpty: "رویدادها پس از شروع پرونده ظاهر می‌شوند.",
    metricsEmpty: "آمار عملیات بعداً اینجا می‌آید.",
    detailsEmpty: "جزئیات پرونده پس از شروع اجرا نمایش داده می‌شود.",
    stage: "مرحله",
    caseId: "شناسه پرونده",
    planId: "شناسه طرح",
    operationId: "عملیات",
    opState: "وضعیت عملیات",
    goal: "هدف",
    noteLive: "تغییرات واقعی فقط با دکمه تأیید؛ نوشتن در چت به‌معنی اجازه نیست.",
    refresh: "بازخوانی پنل",
  },
};

function stageBadgeClass(stage: OrchestratorRun["stage"]): string {
  if (stage === "verified") return "status-good";
  if (stage === "rejected" || stage === "stopped" || stage === "error") return "status-muted";
  if (stage === "awaiting_approval") return "status-warn";
  return "status-warn";
}

export function Inspector({ run, service, loading, open, language }: Props) {
  const [activeTab, setActiveTab] = useState("activity");
  const strings = copy[language];
  const inspectorCards = run
    ? mapOrchestratorToCards(run, language).filter((card) =>
        card.type === "readiness_findings"
        || card.type === "operation_status"
        || card.type === "verification_result",
      )
    : [];

  return (
    <aside className={`inspector-panel ${open ? "mobile-inspector-open" : ""}`}>
      <div className="inspector-top">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold text-slate-100">{strings.title}</h2>
            <span className="inspector-live"><span /> {language === "fa" ? "زنده" : "LIVE"}</span>
          </div>
          <p className="mt-1 text-[11px] text-slate-500">{strings.subtitle}</p>
        </div>
        <button className="icon-button" aria-label={strings.refresh} title={strings.refresh}><RefreshCw size={15} /></button>
      </div>
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="inspector-tabs">
          <TabsTrigger value="activity"><Activity size={13} /> {strings.activity}</TabsTrigger>
          <TabsTrigger value="logs"><FileText size={13} /> {strings.logs}</TabsTrigger>
          <TabsTrigger value="metrics"><Gauge size={13} /> {strings.metrics}</TabsTrigger>
          <TabsTrigger value="details"><Info size={13} /> {strings.details}</TabsTrigger>
        </TabsList>
        <TabsContent value="activity" className="inspector-content">
          {run ? (
            <>
              <div className="section-eyebrow">{strings.currentRun} <span>{run.stage.toUpperCase()}</span></div>
              <Card className="p-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-xs font-medium text-slate-200 truncate">{run.goal}</p>
                    <p className="mt-1 font-mono text-[10px] text-slate-600">{run.case_id.slice(0, 18)}…</p>
                  </div>
                  <span className={`status-badge shrink-0 ${stageBadgeClass(run.stage)}`}>
                    {run.stage.replaceAll("_", " ")}
                  </span>
                </div>
              </Card>
              {inspectorCards.length > 0 ? (
                <>
                  <div className="mt-5 section-eyebrow">CARDS</div>
                  <div className="mt-3 flex flex-col gap-3">
                    {inspectorCards.map((payload, index) => (
                      <GenerativeCard
                        key={`inspector-${payload.type}-${index}`}
                        payload={payload}
                        language={language}
                      />
                    ))}
                  </div>
                </>
              ) : null}
              <div className="mt-5 section-eyebrow">{strings.steps}</div>
              <div className="inspector-steps">
                {run.timeline.map((step, index) => (
                  <div className="inspector-step" key={`${step.tool}-${index}`}>
                    <span className={step.status === "pending" || step.status === "waiting" ? "inspector-pending" : step.status === "error" || step.status === "rejected" ? "inspector-pending" : "inspector-check"}>
                      <span />
                    </span>
                    <div className="min-w-0">
                      <p className="text-xs text-slate-300">{step.title}</p>
                      {step.detail ? (
                        <p className="mt-1 truncate text-[10px] text-slate-500">{step.detail}</p>
                      ) : null}
                    </div>
                    <span className={`logical-end text-[10px] ${step.status === "done" || step.status === "verified" ? "text-emerald-400" : step.status === "waiting" || step.status === "pending" ? "text-amber-300" : step.status === "error" || step.status === "rejected" ? "text-rose-400" : "text-slate-500"}`}>
                      {timelineStatusLabel(step.status, language)}
                    </span>
                  </div>
                ))}
              </div>
              {run.events.length > 0 && (
                <>
                  <div className="mt-4 section-eyebrow">{strings.audit}</div>
                  <div className="mt-3 space-y-2">
                    {run.events.map((event, index) => (
                      <div className="flex items-start gap-2 text-[9px] text-slate-500" key={`${event.event}-${index}`}>
                        <span className="mt-1 size-1 rounded-full bg-blue-400/70" />
                        <span>{event.event.replaceAll("_", " ")}</span>
                        <span className="logical-end font-mono text-[8px] text-slate-700">{event.actor}</span>
                      </div>
                    ))}
                  </div>
                </>
              )}
              <div className="mt-5 section-eyebrow">{strings.case}</div>
              <div className="inspector-detail"><span>{strings.stage}</span><span>{run.stage}</span></div>
              {run.operation ? (
                <div className="inspector-detail"><span>{strings.opState}</span><span className="font-mono text-[10px]">{run.operation.state}</span></div>
              ) : null}
              {service ? (
                <>
                  <div className="inspector-detail"><span>Runtime</span><span>{service.app_type}</span></div>
                  <div className="inspector-detail"><span>Region</span><span>{service.region}</span></div>
                </>
              ) : null}
            </>
          ) : (
            <div className="inspector-empty">
              <div className="empty-orbit"><Radio size={18} /></div>
              <p className="mt-3 text-xs text-slate-300">{strings.emptyTitle}</p>
              <p className="mt-1 max-w-[190px] text-center text-[11px] leading-relaxed text-slate-600">{strings.emptyHint}</p>
            </div>
          )}
          <div className="inspector-note"><Info size={13} /><span>{strings.noteLive}</span></div>
        </TabsContent>
        <TabsContent value="logs" className="inspector-content">
          <div className="flex items-center justify-between">
            <div className="section-eyebrow">EVENTS</div>
            <button className="tiny-select">{service?.name ?? "workspace"} <ChevronDown size={12} /></button>
          </div>
          {loading ? (
            <div className="mt-6 ui-loading-row" aria-busy="true">
              <span className="mini-spinner" />
              <span>…</span>
            </div>
          ) : run && run.events.length > 0 ? (
            <div className="mt-4 space-y-3">
              {run.events.map((event, index) => (
                <div className="inspector-log" key={`${event.time}-${index}`}>
                  <div className="flex items-center gap-2">
                    <span className="log-level-warn">INFO</span>
                    <time>{event.time}</time>
                  </div>
                  <p className="mt-2 font-mono text-[10px] leading-relaxed text-slate-400">{event.event}</p>
                  <p className="mt-1 truncate font-mono text-[9px] text-slate-700">{event.actor}</p>
                </div>
              ))}
            </div>
          ) : <div className="inspector-empty compact"><FileText size={17} /><p>{strings.logsEmpty}</p></div>}
        </TabsContent>
        <TabsContent value="metrics" className="inspector-content">
          <div className="section-eyebrow">RESOURCE SNAPSHOT</div>
          <div className="inspector-empty compact"><Gauge size={17} /><p>{strings.metricsEmpty}</p></div>
          <div className="inspector-note"><Info size={13} /><span>{strings.noteLive}</span></div>
        </TabsContent>
        <TabsContent value="details" className="inspector-content">
          <div className="section-eyebrow">RUN DETAILS</div>
          {run ? (
            <>
              <Card className="mt-4 p-3">
                <p className="text-xs font-medium text-slate-200">{run.goal}</p>
                <p className="mt-2 text-[11px] text-slate-500">{run.summary}</p>
              </Card>
              <div className="mt-5 section-eyebrow">IDENTIFIERS</div>
              <div className="inspector-detail"><span>{strings.caseId}</span><span className="font-mono text-[9px]">{run.case_id.slice(0, 12)}…</span></div>
              {run.plan_id ? <div className="inspector-detail"><span>{strings.planId}</span><span className="font-mono text-[9px]">{run.plan_id.slice(0, 12)}…</span></div> : null}
              {run.operation ? <div className="inspector-detail"><span>{strings.operationId}</span><span className="font-mono text-[9px]">{run.operation.id.slice(0, 12)}…</span></div> : null}
              <div className="inspector-detail"><span>{strings.stage}</span><span>{run.stage}</span></div>
              <div className="inspector-note"><Info size={13} /><span>{strings.noteLive}</span></div>
            </>
          ) : <div className="inspector-empty compact"><Info size={17} /><p>{strings.detailsEmpty}</p></div>}
        </TabsContent>
      </Tabs>
    </aside>
  );
}
