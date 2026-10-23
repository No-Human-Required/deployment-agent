import { useEffect, useState, type FormEvent } from "react";
import {
  Check,
  FlaskConical,
  Globe2,
  LoaderCircle,
  Menu,
  Save,
  ShieldCheck,
  Sparkles,
  Zap,
} from "lucide-react";
import {
  proveLiaraRead,
  proveLlmConnection,
  saveSettings,
  type SettingsUpdateBody,
} from "../lib/api";
import type { SettingsView } from "../lib/schemas";
import { Button } from "./ui/button";
import { Card } from "./ui/card";

const DEFAULT_LIARA_BASE = "https://api.liara.ir";
const DEFAULT_AI_BASE = "https://api.avalai.ir/v1";
const DEFAULT_AI_MODEL = "gpt-5.6-luna";

type LoadState = "loading" | "ready" | "error";

type SettingsPanelProps = {
  settingsView: SettingsView | null;
  loadState: LoadState;
  loadError?: string;
  onOpenNav?: () => void;
  onViewChange: (view: SettingsView) => void;
  onAfterMutate?: () => void | Promise<void>;
};

const t = {
  title: "تنظیمات",
  live: "حالت زنده",
  setup: "نیاز به پیکربندی",
  liaraEyebrow: "اتصال لیارا",
  liaraHint:
    "یک‌بار ذخیره کافی است (Postgres + SECRETS_MASTER_KEY ثابت). فیلد خالی بعد از ذخیره یعنی توکن از قبل هست — فقط برای تعویض دوباره وارد کنید، نه هر بار استارت.",
  aiEyebrow: "Aval AI",
  aiHint:
    "کلید Aval هم روی سرور می‌ماند و برنمی‌گردد. وضعیت «پیکربندی‌شده» یعنی ذخیره شده؛ فیلد خالی طبیعی است. اگر prove خطای 401 داد کلید را عوض کنید، نه اینکه هر بار از نو بسازید.",
  baseUrl: "آدرس پایه API",
  teamId: "شناسه تیم",
  teamPlaceholder: "اختیاری — به‌صورت teamID ارسال می‌شود",
  liaraToken: "توکن API لیارا",
  tokenReplace: "توکن جدید برای جایگزینی",
  tokenPaste: "توکن API را وارد کنید",
  aiBase: "آدرس پایه Aval AI",
  aiModel: "مدل",
  aiKey: "کلید Aval AI",
  keyReplace: "کلید جدید برای جایگزینی",
  keyPaste: "کلید Aval AI را وارد کنید",
  writesNote:
    "تغییرات واقعی روی لیارا فقط بعد از تأیید شما در گفتگو انجام می‌شود.",
  save: "ذخیره",
  saving: "در حال ذخیره…",
  proveLiara: "بررسی اتصال لیارا",
  proveAval: "بررسی اتصال Aval AI",
  loading: "در حال بارگذاری تنظیمات…",
  loadFailed: "بارگذاری تنظیمات ممکن نشد.",
  retry: "تلاش دوباره",
  saved: "ذخیره شد و ماندگار است. فیلدهای خالی یعنی نیازی به ورود دوباره نیست مگر برای تعویض.",
  connectionStatus: "توکن لیارا",
  tokenSaved: "ذخیره‌شده روی سرور",
  notConfigured: "پیکربندی نشده",
  aiKeyStatus: "کلید Aval AI",
  approvals: "تأیید عملیات حساس",
  alwaysRequired: "همیشه لازم",
  language: "زبان و جهت",
  faDir: "فارسی · راست‌چین",
  labelPrefix: "برچسب",
  proveFailed: "بررسی اتصال ناموفق بود.",
};

function applyViewToDraft(view: SettingsView) {
  return {
    liaraBaseUrl: view.liara.api_base_url || DEFAULT_LIARA_BASE,
    teamId: view.liara.team_id || "",
    token: "",
    aiBaseUrl: view.aval.base_url || DEFAULT_AI_BASE,
    aiModel: view.aval.model || DEFAULT_AI_MODEL,
    aiKey: "",
  };
}

export function SettingsPanel({
  settingsView,
  loadState,
  loadError,
  onOpenNav,
  onViewChange,
  onAfterMutate,
}: SettingsPanelProps) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [messageTone, setMessageTone] = useState<"ok" | "err">("ok");
  const [liaraBaseUrl, setLiaraBaseUrl] = useState(DEFAULT_LIARA_BASE);
  const [teamId, setTeamId] = useState("");
  const [token, setToken] = useState("");
  const [aiBaseUrl, setAiBaseUrl] = useState(DEFAULT_AI_BASE);
  const [aiModel, setAiModel] = useState(DEFAULT_AI_MODEL);
  const [aiKey, setAiKey] = useState("");

  useEffect(() => {
    if (!settingsView) return;
    const draft = applyViewToDraft(settingsView);
    setLiaraBaseUrl(draft.liaraBaseUrl);
    setTeamId(draft.teamId);
    setToken(draft.token);
    setAiBaseUrl(draft.aiBaseUrl);
    setAiModel(draft.aiModel);
    setAiKey(draft.aiKey);
  }, [settingsView]);

  async function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    try {
      const body: SettingsUpdateBody = {
        liara_api_base_url: liaraBaseUrl.trim() || DEFAULT_LIARA_BASE,
        liara_team_id: teamId.trim() ? teamId.trim() : "",
        llm_base_url: aiBaseUrl.trim() || DEFAULT_AI_BASE,
        llm_model: aiModel.trim() || DEFAULT_AI_MODEL,
      };
      if (token.trim()) body.liara_api_token = token.trim();
      if (aiKey.trim()) body.llm_api_key = aiKey.trim();

      const saved = await saveSettings(body);
      onViewChange(saved);
      setToken("");
      setAiKey("");
      setMessageTone("ok");
      setMessage(t.saved);
      await onAfterMutate?.();
    } catch (cause) {
      setMessageTone("err");
      setMessage(cause instanceof Error ? cause.message : t.loadFailed);
    } finally {
      setBusy(false);
    }
  }

  async function handleProveLiara() {
    setBusy(true);
    setMessage("");
    try {
      const result = await proveLiaraRead();
      setMessageTone("ok");
      setMessage(`اتصال لیارا برقرار است — ${result.project_count} پروژه دیده شد.`);
      await onAfterMutate?.();
    } catch (cause) {
      setMessageTone("err");
      setMessage(cause instanceof Error ? cause.message : t.proveFailed);
    } finally {
      setBusy(false);
    }
  }

  async function handleProveAval() {
    setBusy(true);
    setMessage("");
    try {
      const result = await proveLlmConnection(settingsView?.workspace_id);
      setMessageTone("ok");
      setMessage(result.message || "اتصال Aval AI برقرار است.");
    } catch (cause) {
      setMessageTone("err");
      setMessage(cause instanceof Error ? cause.message : t.proveFailed);
    } finally {
      setBusy(false);
    }
  }

  const configured = Boolean(settingsView?.liara.token_configured);

  return (
    <div className="settings-shell">
      <header className="chat-topbar">
        {onOpenNav ? (
          <button className="mobile-menu icon-button" onClick={onOpenNav} aria-label="باز کردن منو">
            <Menu size={18} />
          </button>
        ) : null}
        <div className="flex min-w-0 items-center gap-2">
          <span className="topbar-spark">
            <Sparkles size={14} />
          </span>
          <span className="truncate text-sm font-medium text-slate-200">{t.title}</span>
        </div>
        <span className={`logical-end topbar-mode ${configured ? "topbar-mode-live" : ""}`}>
          <span /> {configured ? t.live : t.setup}
        </span>
      </header>

      <div className="settings-body">
        {loadState === "loading" ? (
          <Card className="nav-detail-card nav-state-card nav-state-loading settings-card" aria-busy="true">
            <div className="ui-loading-row" role="status">
              <span className="mini-spinner" />
              <span>{t.loading}</span>
            </div>
          </Card>
        ) : null}

        {loadState === "error" ? (
          <Card className="nav-detail-card nav-state-card nav-state-error settings-card" role="alert">
            <h3>{t.loadFailed}</h3>
            <p>{loadError || t.loadFailed}</p>
            <Button className="mt-3" type="button" size="sm" onClick={() => void onAfterMutate?.()}>
              {t.retry}
            </Button>
          </Card>
        ) : null}

        {loadState === "ready" && settingsView ? (
          <Card className="nav-detail-card settings-card">
            <form className="settings-form" onSubmit={(event) => void handleSave(event)}>
              <section className="settings-section" aria-labelledby="settings-liara-heading">
                <div className="section-eyebrow" id="settings-liara-heading">
                  {t.liaraEyebrow}
                </div>
                <p className="mb-3 text-xs leading-relaxed text-slate-500">{t.liaraHint}</p>
                <label className="settings-field">
                  <span>{t.baseUrl}</span>
                  <input
                    value={liaraBaseUrl}
                    onChange={(event) => setLiaraBaseUrl(event.target.value)}
                    autoComplete="off"
                    placeholder={DEFAULT_LIARA_BASE}
                    dir="ltr"
                  />
                </label>
                <label className="settings-field">
                  <span>{t.teamId}</span>
                  <input
                    value={teamId}
                    onChange={(event) => setTeamId(event.target.value)}
                    autoComplete="off"
                    placeholder={t.teamPlaceholder}
                    dir="ltr"
                  />
                </label>
                <label className="settings-field">
                  <span>{t.liaraToken}</span>
                  <input
                    type="password"
                    value={token}
                    onChange={(event) => setToken(event.target.value)}
                    autoComplete="new-password"
                    placeholder={
                      settingsView.liara.token_configured ? t.tokenReplace : t.tokenPaste
                    }
                    dir="ltr"
                  />
                </label>
                {settingsView.liara.token_configured && settingsView.liara.token_label ? (
                  <p className="settings-label-hint">
                    {t.labelPrefix}: {settingsView.liara.token_label}
                  </p>
                ) : null}
              </section>

              <section className="settings-section" aria-labelledby="settings-ai-heading">
                <div className="section-eyebrow" id="settings-ai-heading">
                  {t.aiEyebrow}
                </div>
                <p className="mb-3 text-xs leading-relaxed text-slate-500">{t.aiHint}</p>
                <label className="settings-field">
                  <span>{t.aiBase}</span>
                  <input
                    value={aiBaseUrl}
                    onChange={(event) => setAiBaseUrl(event.target.value)}
                    autoComplete="off"
                    placeholder={DEFAULT_AI_BASE}
                    dir="ltr"
                  />
                </label>
                <label className="settings-field">
                  <span>{t.aiModel}</span>
                  <input
                    value={aiModel}
                    onChange={(event) => setAiModel(event.target.value)}
                    autoComplete="off"
                    placeholder={DEFAULT_AI_MODEL}
                    dir="ltr"
                  />
                </label>
                <label className="settings-field">
                  <span>{t.aiKey}</span>
                  <input
                    type="password"
                    value={aiKey}
                    onChange={(event) => setAiKey(event.target.value)}
                    autoComplete="new-password"
                    placeholder={
                      settingsView.aval.api_key_configured ? t.keyReplace : t.keyPaste
                    }
                    dir="ltr"
                  />
                </label>
                {settingsView.aval.api_key_configured && settingsView.aval.api_key_label ? (
                  <p className="settings-label-hint">
                    {t.labelPrefix}: {settingsView.aval.api_key_label}
                  </p>
                ) : null}
              </section>

              <p className="mb-1 text-[11px] leading-relaxed text-slate-500">{t.writesNote}</p>

              <div className="settings-actions">
                <Button type="submit" size="sm" disabled={busy}>
                  {busy ? <LoaderCircle size={14} className="animate-spin" /> : <Save size={14} />}
                  {busy ? t.saving : t.save}
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  disabled={busy || !settingsView.liara.token_configured}
                  onClick={() => void handleProveLiara()}
                >
                  <FlaskConical size={14} />
                  {t.proveLiara}
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  disabled={busy || !settingsView.aval.api_key_configured}
                  onClick={() => void handleProveAval()}
                >
                  <Sparkles size={14} />
                  {t.proveAval}
                </Button>
              </div>
            </form>

            {message ? (
              <p
                className={`settings-feedback ${messageTone === "err" ? "settings-feedback-err" : "settings-feedback-ok"}`}
                role="status"
              >
                {messageTone === "ok" ? <Check size={14} /> : null}
                <span>{message}</span>
              </p>
            ) : null}

            <div className="mt-5 domain-row">
              <Zap size={16} />
              <span className="flex-1 text-sm text-slate-200">{t.connectionStatus}</span>
              <span
                className={`status-badge ${
                  settingsView.liara.token_configured ? "status-good" : "status-warn"
                }`}
              >
                {settingsView.liara.token_configured ? t.tokenSaved : t.notConfigured}
              </span>
            </div>
            <div className="domain-row">
              <Sparkles size={16} />
              <span className="flex-1 text-sm text-slate-200">{t.aiKeyStatus}</span>
              <span
                className={`status-badge ${
                  settingsView.aval.api_key_configured ? "status-good" : "status-warn"
                }`}
              >
                {settingsView.aval.api_key_configured ? t.tokenSaved : t.notConfigured}
              </span>
            </div>
            <div className="domain-row">
              <ShieldCheck size={16} />
              <span className="flex-1 text-sm text-slate-200">{t.approvals}</span>
              <span className="status-badge status-good">{t.alwaysRequired}</span>
            </div>
            <div className="domain-row">
              <Globe2 size={16} />
              <span className="flex-1 text-sm text-slate-200">{t.language}</span>
              <span className="status-badge status-muted">{t.faDir}</span>
            </div>
          </Card>
        ) : null}
      </div>
    </div>
  );
}
