import {
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  CircleDashed,
  ExternalLink,
  FileDiff,
  GitBranch,
  Globe2,
  LoaderCircle,
  MessageSquare,
  Rocket,
  ShieldAlert,
  Terminal,
  XCircle,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { type AgentEvent, type AgentRunView, isAgentRunLive, toolArgHint, toolLabel } from "../lib/agentRuns";

type Locale = "fa" | "en";

type Props = {
  view: AgentRunView;
  language: Locale;
  busy?: boolean;
  onStart: (projectName: string) => void;
  onCancel: () => void;
  onStop: () => void;
  onApprove: () => void;
  onDecline: () => void;
};

type FeedItem =
  | { kind: "thought"; seq: number; text: string }
  | { kind: "tool"; seq: number; name: string; hint: string; ok?: boolean; preview?: string }
  | { kind: "diff"; seq: number; path: string; diff: string }
  | { kind: "note"; seq: number; icon: ReactNode; text: string; tone?: "ok" | "bad" };

const T = {
  fa: {
    title: "عامل DevOps",
    proposeBody:
      "با تأیید شما، عامل خودش کد پروژه را بررسی و در صورت نیاز ویرایش می‌کند، روی لیارا مستقر می‌کند، لاگ ساخت و اجرا را می‌خواند و تا وقتی آدرس اپ واقعاً بالا بیاید ادامه می‌دهد. تغییرات کد با یک نقطهٔ بازگشت git ثبت و اینجا نشان داده می‌شود. برای کارهای هزینه‌دار، حذف یا دامنه دوباره از شما اجازه می‌گیرد.",
    appName: "نام اپ در لیارا",
    start: "تأیید و شروع",
    cancel: "انصراف",
    stop: "توقف",
    stopping: "پس از مرحلهٔ فعلی متوقف می‌شود…",
    cancelled: "لغو شد.",
    running: "در حال کار…",
    awaiting: "منتظر تأیید شما",
    approvalBody: "عامل می‌خواهد این کار را انجام دهد (ممکن است هزینه داشته باشد):",
    approve: "اجازه می‌دهم",
    decline: "رد",
    success: "استقرار تأیید شد",
    failed: "به نتیجه نرسید",
    error: "خطای عامل",
    open: "باز کردن اپ",
    showAll: (n: number) => `نمایش همهٔ ${n} مرحله`,
    checkpoint: (ref: string) => `نقطهٔ بازگشت git: ${ref}`,
    noCheckpoint: "پوشه git نیست؛ نقطهٔ بازگشت ساخته نشد",
    deployUpload: (app: string, dir: string, mb: number) => `بارگذاری ${dir} روی ${app} (${mb} MB)`,
    deployState: (state: string) => `وضعیت انتشار: ${state}`,
    verifyRejected: "ادعای موفقیت رد شد — هنوز پاسخ سالم از آدرس اپ دریافت نشده",
    envs: (keys: string) => `متغیرها: ${keys}`,
  },
  en: {
    title: "DevOps agent",
    proposeBody:
      "Once you approve, the agent inspects and, if needed, edits the project code, deploys to Liara, reads build and runtime logs, and keeps going until the app URL really serves. Code edits get a git checkpoint and are shown here. Paid, destructive or domain actions ask you again.",
    appName: "Liara app name",
    start: "Approve and start",
    cancel: "Cancel",
    stop: "Stop",
    stopping: "Stopping after the current step…",
    cancelled: "Cancelled.",
    running: "Working…",
    awaiting: "Waiting for your approval",
    approvalBody: "The agent wants to do this (may cost money):",
    approve: "Allow",
    decline: "Decline",
    success: "Deploy verified",
    failed: "Did not reach a working deploy",
    error: "Agent error",
    open: "Open app",
    showAll: (n: number) => `Show all ${n} steps`,
    checkpoint: (ref: string) => `git checkpoint: ${ref}`,
    noCheckpoint: "Not a git repo — no checkpoint",
    deployUpload: (app: string, dir: string, mb: number) => `Uploading ${dir} to ${app} (${mb} MB)`,
    deployState: (state: string) => `Release state: ${state}`,
    verifyRejected: "Success claim rejected — the app URL has not answered healthy yet",
    envs: (keys: string) => `Env vars: ${keys}`,
  },
} as const;

const COLLAPSED_LIMIT = 14;

function buildFeed(events: AgentEvent[], language: Locale): FeedItem[] {
  const t = T[language];
  const items: FeedItem[] = [];
  const toolIndex = new Map<string, number>();
  for (const event of events) {
    const str = (key: string) => (typeof event[key] === "string" ? (event[key] as string) : "");
    switch (event.type) {
      case "thought":
        if (str("text").trim()) items.push({ kind: "thought", seq: event.seq, text: str("text").trim() });
        break;
      case "user_note":
        if (str("text").trim()) {
          items.push({
            kind: "note",
            seq: event.seq,
            icon: <MessageSquare size={14} />,
            text: language === "fa" ? `پیام شما: ${str("text").trim()}` : `Your note: ${str("text").trim()}`,
          });
        }
        break;
      case "tool_call": {
        const name = str("name");
        if (name === "finish") break;
        toolIndex.set(str("id"), items.length);
        items.push({ kind: "tool", seq: event.seq, name, hint: toolArgHint(event.args) });
        break;
      }
      case "tool_result": {
        const at = toolIndex.get(str("id"));
        const item = at === undefined ? undefined : items[at];
        if (item && item.kind === "tool") {
          items[at!] = { ...item, ok: event.ok === true, preview: str("preview") };
        }
        break;
      }
      case "diff":
        items.push({ kind: "diff", seq: event.seq, path: str("path"), diff: str("diff") });
        break;
      case "checkpoint":
        items.push({
          kind: "note",
          seq: event.seq,
          icon: <GitBranch size={13} />,
          text: str("ref") ? t.checkpoint(str("ref")) : t.noCheckpoint,
        });
        break;
      case "deploy": {
        const phase = str("phase");
        if (phase === "upload") {
          items.push({
            kind: "note",
            seq: event.seq,
            icon: <Rocket size={13} />,
            text: t.deployUpload(str("app"), str("app_dir") || ".", Number(event.size_mb ?? 0)),
          });
        } else if (phase === "done") {
          const state = str("state");
          items.push({
            kind: "note",
            seq: event.seq,
            icon: <Rocket size={13} />,
            text: t.deployState(state),
            tone: state === "READY" ? "ok" : "bad",
          });
        }
        break;
      }
      case "http_check":
        items.push({
          kind: "note",
          seq: event.seq,
          icon: <Globe2 size={13} />,
          text: `${str("url")} → ${String(event.status ?? "—")}${str("title") ? ` · ${str("title")}` : ""}`,
          tone: event.ok === true ? "ok" : "bad",
        });
        break;
      case "envs":
        items.push({
          kind: "note",
          seq: event.seq,
          icon: <Terminal size={13} />,
          text: t.envs(Array.isArray(event.changed) ? (event.changed as string[]).join(", ") : ""),
        });
        break;
      case "verify_rejected":
        items.push({ kind: "note", seq: event.seq, icon: <AlertTriangle size={13} />, text: t.verifyRejected, tone: "bad" });
        break;
      default:
        break;
    }
  }
  return items;
}

function ToolIcon({ name }: { name: string }) {
  if (name.includes("docs") || name.includes("skill") || name === "web_fetch") return <BookOpen size={13} />;
  if (name === "run_command") return <Terminal size={13} />;
  if (name === "http_check") return <Globe2 size={13} />;
  if (name.startsWith("liara_")) return <Rocket size={13} />;
  return <CircleDashed size={13} />;
}

function DiffBlock({ diff }: { diff: string }) {
  return (
    <pre className="agent-diff" dir="ltr">
      {diff.split("\n").map((line, index) => (
        <span
          key={index}
          className={
            line.startsWith("+") && !line.startsWith("+++")
              ? "diff-add"
              : line.startsWith("-") && !line.startsWith("---")
                ? "diff-del"
                : line.startsWith("@@")
                  ? "diff-hunk"
                  : undefined
          }
        >
          {line}
          {"\n"}
        </span>
      ))}
    </pre>
  );
}

export function AgentRunCard({ view, language, busy, onStart, onCancel, onStop, onApprove, onDecline }: Props) {
  const t = T[language];
  const [projectName, setProjectName] = useState(view.projectName);
  const [expanded, setExpanded] = useState(false);
  const feedRef = useRef<HTMLOListElement>(null);
  const feed = useMemo(() => buildFeed(view.events, language), [view.events, language]);
  const live = isAgentRunLive(view);
  const visible = expanded || feed.length <= COLLAPSED_LIMIT ? feed : feed.slice(-COLLAPSED_LIMIT);
  const stopping = live && view.events.some((event) => event.type === "cancel_requested");

  useEffect(() => {
    if (live && feedRef.current) feedRef.current.scrollTop = feedRef.current.scrollHeight;
  }, [feed.length, live]);

  const statusLine =
    view.status === "awaiting_approval" ? (
      <span className="agent-status warn"><ShieldAlert size={13} /> {t.awaiting}</span>
    ) : live ? (
      <span className="agent-status"><LoaderCircle size={13} className="spin" /> {t.running}</span>
    ) : view.status === "done" && view.outcome?.success ? (
      <span className="agent-status ok"><CheckCircle2 size={13} /> {t.success}</span>
    ) : view.status === "done" ? (
      <span className="agent-status bad"><XCircle size={13} /> {t.failed}</span>
    ) : view.status === "error" ? (
      <span className="agent-status bad"><XCircle size={13} /> {t.error}</span>
    ) : null;

  return (
    <section className="agent-run-card" aria-label={t.title} aria-busy={live}>
      <header className="agent-run-head">
        <strong>{t.title}</strong>
        <span className="agent-run-app" dir="ltr">{view.projectName}</span>
        {statusLine}
        {live && view.runId ? (
          <button type="button" className="quick-reply quick-reply-danger agent-run-stop" disabled={stopping} onClick={onStop}>
            {stopping ? t.stopping : t.stop}
          </button>
        ) : null}
      </header>

      {view.status === "proposed" ? (
        <div className="agent-run-propose">
          <p>{t.proposeBody}</p>
          <label className="agent-run-field">
            <span>{t.appName}</span>
            <input
              dir="ltr"
              value={projectName}
              onChange={(event) => setProjectName(event.target.value.trim().toLowerCase())}
              placeholder="my-app"
            />
          </label>
          <div className="agent-run-actions">
            <button
              type="button"
              className="quick-reply quick-reply-primary"
              disabled={busy || !projectName}
              onClick={() => onStart(projectName)}
            >
              {t.start}
            </button>
            <button type="button" className="quick-reply" disabled={busy} onClick={onCancel}>
              {t.cancel}
            </button>
          </div>
        </div>
      ) : null}

      {view.status === "cancelled" ? <p className="agent-run-muted">{t.cancelled}</p> : null}

      {feed.length > 0 ? (
        <>
          {feed.length > visible.length ? (
            <button type="button" className="agent-run-more" onClick={() => setExpanded(true)}>
              {t.showAll(feed.length)}
            </button>
          ) : null}
          <ol className="agent-feed" ref={feedRef}>
            {visible.map((item) => {
              if (item.kind === "thought") {
                return (
                  <li key={item.seq} className="agent-feed-thought">
                    {item.text}
                  </li>
                );
              }
              if (item.kind === "diff") {
                return (
                  <li key={item.seq} className="agent-feed-step">
                    <details>
                      <summary>
                        <FileDiff size={13} /> <span dir="ltr">{item.path}</span>
                      </summary>
                      <DiffBlock diff={item.diff} />
                    </details>
                  </li>
                );
              }
              if (item.kind === "note") {
                return (
                  <li key={item.seq} className={`agent-feed-step ${item.tone ?? ""}`}>
                    {item.icon} <span>{item.text}</span>
                  </li>
                );
              }
              const pending = item.ok === undefined;
              return (
                <li key={item.seq} className={`agent-feed-step ${item.ok === false ? "bad" : ""}`}>
                  {pending && live ? <LoaderCircle size={13} className="spin" /> : <ToolIcon name={item.name} />}
                  <span>{toolLabel(item.name, language)}</span>
                  {item.hint ? <code dir="ltr">{item.hint}</code> : null}
                  {item.ok === false && item.preview ? (
                    <details className="agent-feed-error">
                      <summary>…</summary>
                      <pre dir="ltr">{item.preview}</pre>
                    </details>
                  ) : null}
                </li>
              );
            })}
          </ol>
        </>
      ) : null}

      {view.status === "awaiting_approval" && view.pendingApproval?.length ? (
        <div className="agent-run-approval">
          <p>{t.approvalBody}</p>
          <ul>
            {view.pendingApproval.map((call, index) => (
              <li key={`${call.name}-${index}`}>
                <strong>{toolLabel(call.name, language)}</strong>
                <code dir="ltr">{JSON.stringify(call.args ?? {})}</code>
              </li>
            ))}
          </ul>
          <div className="agent-run-actions">
            <button type="button" className="quick-reply quick-reply-primary" disabled={busy} onClick={onApprove}>
              {t.approve}
            </button>
            <button type="button" className="quick-reply quick-reply-danger" disabled={busy} onClick={onDecline}>
              {t.decline}
            </button>
          </div>
        </div>
      ) : null}

      {view.status === "done" && view.outcome ? (
        <div className={`agent-run-outcome ${view.outcome.success ? "ok" : "bad"}`}>
          <p>{view.outcome.summary}</p>
          {view.outcome.success && view.outcome.url ? (
            <a href={view.outcome.url} target="_blank" rel="noreferrer" dir="ltr">
              <ExternalLink size={13} /> {t.open}: {view.outcome.url}
            </a>
          ) : null}
        </div>
      ) : null}
      {view.status === "error" && view.error ? <p className="agent-run-outcome bad" dir="auto">{view.error}</p> : null}
    </section>
  );
}
