import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import {
  Activity,
  ArrowUp,
  Bot,
  ChevronDown,
  CircleHelp,
  Code2,
  FolderOpen,
  FolderPlus,
  Menu,
  MessageSquare,
  MoreHorizontal,
  Plus,
  Search,
  Server,
  Settings2,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { IntakePanel } from "./components/IntakePanel";
import { NavigationView, type NavSurface } from "./components/nav/NavigationView";
import { PlanApprovalPanel } from "./components/PlanApprovalPanel";
import { SettingsPanel } from "./components/SettingsPanel";
import type { IntakeConfirmValues } from "./components/agent-ui/GenerativeCard";
import {
  approvePlan,
  assessReadiness,
  collectEvidence,
  createCase,
  createPlan,
  createPlanFromFix,
  diagnoseCase,
  enableMonitor,
  executePlan,
  getLiaraPlans,
  getServices,
  getSettings,
  pickLocalPath,
  proposeFixOptions,
  verifyResult,
  type Service,
} from "./lib/api";
import { resolveChallengeLoopRoute } from "./lib/challengeLoops";
import {
  findConversationInHistory,
  loadAllConversationHistory,
  loadConversationHistory,
  saveConversationHistory,
  type Conversation,
} from "./lib/conversations";
import {
  buildPlanPayloads,
  intakeAssistantPrompt,
  intakeRequirements,
  type IntakeKind,
} from "./lib/intake";
import {
  navigateAppRoute,
  parseAppRoute,
  type AppRoute,
} from "./lib/routes";
import type { OrchestratorRun, SettingsView } from "./lib/schemas";
import {
  planReadyAssistantText,
  verificationAssistantText,
} from "./lib/quietChat";
import { buildRequestTimeline } from "./lib/requestTimeline";
import {
  activateRecentWorkspace,
  folderDisplayName,
  listRecentWorkspaces,
  loadLocalWorkspace,
  normalizeWorkspaceKey,
  saveLocalWorkspace,
  type LocalWorkspace,
} from "./lib/workspace";

type NavItem = NavSurface;
type ChatMessage = { id: string; role: "user" | "assistant"; text: string; kind?: "demo" | "live" };
type CatalogState = "idle" | "loading" | "ready" | "error";

const copy = {
  en: {
    workspace: "Agent workspace",
    start: "Start a conversation",
    subtitle: "Your cloud operations, understood.",
    caption: "A thoughtful teammate for every deployment, incident, and infrastructure question.",
    prompt: "Investigate an issue, inspect a service, or ask a question...",
    first: "Investigate HTTP 500 errors",
    firstHint: "Case → plan → HITL approve → execute",
    second: "Show me service health",
    secondHint: "Get an overview of your services",
    third: "Review latest deployment",
    thirdHint: "See release history and status",
    trust: "Sensitive actions always require your approval.",
    powered: "LiaraOps AI can make mistakes. Review operations before approval.",
    foldersSection: "FOLDERS",
    recentEmpty: "No conversations yet in this folder.",
    recentNeedFolder: "Add a project folder to start chatting.",
    newConversation: "New conversation",
    addFolder: "Add folder",
    settings: "Settings",
    thinking: "Driving orchestrator case…",
    noServices: "No services",
    noFolder: "No project folder",
    pickFolderHint: "Choose a local folder to start project chat",
    pickFolderCta: "Open project folder",
    pickFolderTitle: "Pick a project folder first",
    pickFolderBody: "Like Cursor, chats live inside a local workspace. Select an OS folder to continue — Settings still works without one.",
    pickFolderPrompt: "Select a project folder to send messages…",
    pickFolderBusy: "Opening folder picker…",
    folderGateError: "Select a local project folder before starting a project chat.",
    collapseFolder: "Collapse folder",
    expandFolder: "Expand folder",
  },
  fa: {
    workspace: "فضای کار عامل",
    start: "گفتگو را شروع کنید",
    subtitle: "عملیات ابری، ساده و شفاف.",
    caption: "همراهی دقیق برای استقرار، حادثه و سوال‌های زیرساخت.",
    prompt: "مشکل را بررسی کنید، سرویس را ببینید یا سوالی بپرسید...",
    first: "بررسی خطای HTTP 500",
    firstHint: "پرونده → طرح → تأیید انسانی → اجرا",
    second: "وضعیت سلامت سرویس",
    secondHint: "نمای کلی سرویس‌های شما",
    third: "بررسی آخرین استقرار",
    thirdHint: "تاریخچه انتشار و وضعیت",
    trust: "اقدامات حساس همیشه نیاز به تأیید شما دارند.",
    powered: "عامل ممکن است اشتباه کند. پیش از تأیید، عملیات را بررسی کنید.",
    foldersSection: "پوشه‌ها",
    recentEmpty: "هنوز گفتگویی در این پوشه نیست.",
    recentNeedFolder: "برای شروع گفتگو یک پوشه پروژه اضافه کنید.",
    newConversation: "گفتگوی جدید",
    addFolder: "افزودن پوشه",
    settings: "تنظیمات",
    thinking: "در حال آماده‌سازی پاسخ…",
    noServices: "بدون سرویس",
    noFolder: "بدون پوشه پروژه",
    pickFolderHint: "برای شروع گفتگوی پروژه یک پوشه محلی انتخاب کنید",
    pickFolderCta: "انتخاب پوشه پروژه",
    pickFolderTitle: "ابتدا پوشه پروژه را انتخاب کنید",
    pickFolderBody: "مثل Cursor، گفتگوها داخل فضای کار محلی می‌مانند. یک پوشه از سیستم انتخاب کنید — تنظیمات بدون پوشه هم در دسترس است.",
    pickFolderPrompt: "برای ارسال پیام، ابتدا پوشه پروژه را انتخاب کنید…",
    pickFolderBusy: "در حال باز کردن انتخابگر پوشه…",
    folderGateError: "قبل از شروع گفتگوی پروژه، یک پوشه محلی انتخاب کنید.",
    collapseFolder: "بستن پوشه",
    expandFolder: "باز کردن پوشه",
  },
};

const surfaceMotion = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -6 },
  transition: { duration: 0.22, ease: [0.22, 0.75, 0.28, 1] as const },
};

function id() {
  return Math.random().toString(36).slice(2, 10);
}

function App() {
  const [initialWorkspace] = useState(() => {
    try {
      return loadLocalWorkspace(window.localStorage);
    } catch {
      return {
        workspace: null as LocalWorkspace | null,
        recent: [] as LocalWorkspace[],
        error: "فضای کار محلی در این مرورگر در دسترس نیست.",
      };
    }
  });
  const [localWorkspace, setLocalWorkspace] = useState<LocalWorkspace | null>(initialWorkspace.workspace);
  const [recentWorkspaces, setRecentWorkspaces] = useState<LocalWorkspace[]>(initialWorkspace.recent ?? []);
  const workspaceKey = localWorkspace ? normalizeWorkspaceKey(localWorkspace.path) : null;
  const hasLocalWorkspace = Boolean(workspaceKey);
  const [expandedFolders, setExpandedFolders] = useState<Record<string, boolean>>(() => {
    const key = initialWorkspace.workspace
      ? normalizeWorkspaceKey(initialWorkspace.workspace.path)
      : "";
    return key ? { [key]: true } : {};
  });

  const [initialHistory] = useState(() => {
    try {
      return loadConversationHistory(window.localStorage, workspaceKey);
    } catch {
      return {
        conversations: [] as Conversation[],
        error: "تاریخچه گفتگو در این مرورگر در دسترس نیست. جلسه فعلی همچنان کار می‌کند.",
      };
    }
  });
  const historyCanBeSaved = initialHistory.error === null;
  const [services, setServices] = useState<Service[]>([]);
  const [servicesState, setServicesState] = useState<CatalogState>("idle");
  const [servicesError, setServicesError] = useState("");
  const [selectedServiceId, setSelectedServiceId] = useState("");
  const [activeNav, setActiveNav] = useState<NavItem>(() => {
    const route = parseAppRoute(window.location.pathname);
    return route.kind === "settings" ? "Settings" : "New Chat";
  });
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [orchestratorRun, setOrchestratorRun] = useState<OrchestratorRun | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>(initialHistory.conversations);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(false);
  const [approvalBusy, setApprovalBusy] = useState(false);
  const [pickingFolder, setPickingFolder] = useState(false);
  const [error, setError] = useState("");
  const [historyNotice, setHistoryNotice] = useState(
    initialWorkspace.error ?? initialHistory.error,
  );
  const language = "fa" as const;
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [settingsView, setSettingsView] = useState<SettingsView | null>(null);
  const [settingsLoadState, setSettingsLoadState] = useState<"loading" | "ready" | "error">("loading");
  const [settingsLoadError, setSettingsLoadError] = useState("");
  const chatEndRef = useRef<HTMLDivElement>(null);
  const [activeConversationId, setActiveConversationId] = useState(() => id());
  const conversationIdRef = useRef(activeConversationId);
  conversationIdRef.current = activeConversationId;
  const skipInitialHistorySave = useRef(true);
  const settingsReadyRef = useRef(false);
  const routeHydratedRef = useRef(false);
  const localWorkspaceRef = useRef(localWorkspace);
  localWorkspaceRef.current = localWorkspace;
  const strings = copy[language];
  const currentTitle = messages.find((message) => message.role === "user")?.text;
  const recentConversations = hasLocalWorkspace
    ? [
        ...(currentTitle
          ? [{
              id: activeConversationId,
              title: currentTitle,
              serviceId: selectedServiceId || "workspace",
              messages,
              updatedAt: new Date().toISOString(),
              orchestratorRun,
            }]
          : []),
        ...conversations.filter((conversation) => conversation.id !== activeConversationId),
      ].slice(0, 8)
    : [];
  const conversationsByFolder = useMemo(() => {
    let stored: Record<string, Conversation[]> = {};
    try {
      stored = loadAllConversationHistory(window.localStorage).byWorkspace;
    } catch {
      stored = {};
    }
    const map: Record<string, Conversation[]> = { ...stored };
    if (workspaceKey) {
      map[workspaceKey] = recentConversations;
    }
    return map;
  }, [recentConversations, workspaceKey, recentWorkspaces]);

  function setConversationId(nextId: string) {
    conversationIdRef.current = nextId;
    setActiveConversationId(nextId);
  }

  function syncRoute(route: AppRoute, mode: "push" | "replace" = "push") {
    navigateAppRoute(route, mode);
  }

  function toggleFolderExpanded(folderKey: string) {
    setExpandedFolders((current) => ({
      ...current,
      [folderKey]: !current[folderKey],
    }));
  }

  function ensureFolderExpanded(folderKey: string) {
    setExpandedFolders((current) =>
      current[folderKey] ? current : { ...current, [folderKey]: true },
    );
  }

  async function refreshCatalog() {
    if (!settingsReadyRef.current) setSettingsLoadState("loading");
    setServicesState("loading");
    setServicesError("");
    try {
      const view = await getSettings();
      setSettingsView(view);
      settingsReadyRef.current = true;
      setSettingsLoadState("ready");
      setSettingsLoadError("");
      if (!view.liara.token_configured) {
        setServices([]);
        setSelectedServiceId("");
        setServicesState("ready");
        setError(
          language === "fa"
            ? "توکن لیارا را در تنظیمات ذخیره کنید تا سرویس‌های واقعی بارگذاری شوند."
            : "توکن لیارا را در تنظیمات ذخیره کنید تا سرویس‌ها بارگذاری شوند.",
        );
        return;
      }
      const catalog = await getServices(view.workspace_id);
      setServices(catalog);
      setSelectedServiceId((current) =>
        catalog.some((service) => service.id === current) ? current : (catalog[0]?.id ?? ""),
      );
      setServicesState("ready");
      setError("");
    } catch (cause: unknown) {
      setServices([]);
      const message = cause instanceof Error ? cause.message : "Could not connect to the API.";
      setServicesState("error");
      setServicesError(message);
      setError(message);
      if (!settingsReadyRef.current) {
        setSettingsLoadState("error");
        setSettingsLoadError(message);
      }
    }
  }

  useEffect(() => {
    void refreshCatalog();
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, orchestratorRun]);

  useEffect(() => {
    if (!hasLocalWorkspace) return;
    const title = messages.find((message) => message.role === "user")?.text;
    if (!title) return;

    const currentConversation: Conversation = {
      id: conversationIdRef.current,
      title,
      serviceId: selectedServiceId || "workspace",
      messages,
      updatedAt: new Date().toISOString(),
      orchestratorRun,
    };
    setConversations((current) => [
      currentConversation,
      ...current.filter((conversation) => conversation.id !== currentConversation.id),
    ].slice(0, 8));
    if (activeNav === "New Chat") {
      syncRoute({ kind: "chat", conversationId: currentConversation.id }, "replace");
    }
  }, [messages, orchestratorRun, selectedServiceId, hasLocalWorkspace, activeNav]);

  useEffect(() => {
    function restoreConversationFromRoute(conversationId: string): boolean {
      const found = findConversationInHistory(window.localStorage, conversationId);
      if (!found) return false;

      const activeKey = localWorkspaceRef.current
        ? normalizeWorkspaceKey(localWorkspaceRef.current.path)
        : null;
      if (found.workspaceKey !== activeKey) {
        const activated = activateRecentWorkspace(window.localStorage, found.workspaceKey);
        if (!activated.workspace) return false;
        localWorkspaceRef.current = activated.workspace;
        setLocalWorkspace(activated.workspace);
        setRecentWorkspaces(listRecentWorkspaces(window.localStorage));
        skipInitialHistorySave.current = true;
        const loaded = loadConversationHistory(window.localStorage, found.workspaceKey);
        setConversations(loaded.conversations);
      }
      ensureFolderExpanded(found.workspaceKey);
      setConversationId(found.conversation.id);
      setSelectedServiceId(
        found.conversation.serviceId === "workspace" ? "" : found.conversation.serviceId,
      );
      setMessages(found.conversation.messages);
      setOrchestratorRun(found.conversation.orchestratorRun);
      setError("");
      return true;
    }

    function applyRoute(route: AppRoute) {
      if (route.kind === "settings") {
        setActiveNav("Settings");
        setMobileNavOpen(false);
        return;
      }

      setActiveNav("New Chat");
      setMobileNavOpen(false);

      if (!route.conversationId) {
        setConversationId(id());
        setMessages([]);
        setOrchestratorRun(null);
        setDraft("");
        setError("");
        return;
      }

      if (route.conversationId === conversationIdRef.current) return;

      if (!restoreConversationFromRoute(route.conversationId)) {
        navigateAppRoute({ kind: "chat", conversationId: null }, "replace");
        setConversationId(id());
        setMessages([]);
        setOrchestratorRun(null);
      }
    }

    if (!routeHydratedRef.current) {
      routeHydratedRef.current = true;
      applyRoute(parseAppRoute(window.location.pathname));
    }

    function onPopState() {
      applyRoute(parseAppRoute(window.location.pathname));
    }
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
    // Mount-only: restore URL once and listen for browser back/forward.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!historyCanBeSaved || !workspaceKey) return;
    if (skipInitialHistorySave.current) {
      skipInitialHistorySave.current = false;
      return;
    }

    try {
      setHistoryNotice(saveConversationHistory(window.localStorage, workspaceKey, conversations));
    } catch {
      setHistoryNotice("ذخیره تاریخچه در این مرورگر ممکن نشد. فضای ذخیره‌سازی را بررسی کنید.");
    }
  }, [conversations, historyCanBeSaved, workspaceKey]);

  function resetActiveThread(options?: { syncUrl?: boolean; mode?: "push" | "replace" }) {
    setConversationId(id());
    setMessages([]);
    setOrchestratorRun(null);
    setDraft("");
    setError("");
    if (options?.syncUrl !== false) {
      syncRoute({ kind: "chat", conversationId: null }, options?.mode ?? "push");
    }
  }

  function flushConversationsForKey(
    key: string | null,
    list: Conversation[],
    includeCurrent: boolean,
  ): Conversation[] {
    let next = list;
    if (includeCurrent) {
      const title = messages.find((message) => message.role === "user")?.text;
      if (title) {
        const currentConversation: Conversation = {
          id: conversationIdRef.current,
          title,
          serviceId: selectedServiceId || "workspace",
          messages: [...messages],
          updatedAt: new Date().toISOString(),
          orchestratorRun,
        };
        next = [
          currentConversation,
          ...list.filter((item) => item.id !== currentConversation.id),
        ].slice(0, 8);
      }
    }
    if (key && historyCanBeSaved) {
      try {
        const saveError = saveConversationHistory(window.localStorage, key, next);
        if (saveError) setHistoryNotice(saveError);
      } catch {
        setHistoryNotice("ذخیره تاریخچه در این مرورگر ممکن نشد. فضای ذخیره‌سازی را بررسی کنید.");
      }
    }
    return next;
  }

  function applyLocalWorkspace(next: LocalWorkspace) {
    const previous = localWorkspaceRef.current;
    const previousKey = previous ? normalizeWorkspaceKey(previous.path) : null;
    const nextKey = normalizeWorkspaceKey(next.path);
    if (!nextKey) {
      setError(strings.folderGateError);
      return;
    }

    try {
      if (previousKey && previousKey !== nextKey) {
        flushConversationsForKey(previousKey, conversations, true);
      }

      const saveError = saveLocalWorkspace(window.localStorage, next);
      if (saveError) {
        setHistoryNotice(saveError);
        return;
      }

      setLocalWorkspace(next);
      localWorkspaceRef.current = next;
      setRecentWorkspaces(listRecentWorkspaces(window.localStorage));
      ensureFolderExpanded(nextKey);

      if (!previousKey || previousKey !== nextKey) {
        skipInitialHistorySave.current = true;
        const loaded = loadConversationHistory(window.localStorage, nextKey);
        setConversations(loaded.conversations);
        if (loaded.error) setHistoryNotice(loaded.error);
        resetActiveThread({ mode: "replace" });
        setActiveNav("New Chat");
        setMobileNavOpen(false);
      }
    } catch (cause: unknown) {
      const message =
        cause instanceof Error
          ? cause.message
          : language === "fa"
            ? "اعمال پوشه پروژه ممکن نشد."
            : "Could not apply the project folder.";
      setError(message);
    }
  }

  function switchToRecentWorkspace(path: string) {
    setError("");
    const activated = activateRecentWorkspace(window.localStorage, path);
    if (activated.error || !activated.workspace) {
      setHistoryNotice(activated.error ?? strings.folderGateError);
      return;
    }
    applyLocalWorkspace(activated.workspace);
  }

  async function pickWorkspaceFolder() {
    if (pickingFolder) return;
    setPickingFolder(true);
    setError("");
    try {
      const result = await pickLocalPath("directory");
      if (result.cancelled || !result.path) return;
      const path = normalizeWorkspaceKey(result.path);
      if (!path) return;
      // Defer apply so the native dialog can fully dismiss before React re-renders.
      window.setTimeout(() => {
        applyLocalWorkspace({
          version: 1,
          path,
          displayName: folderDisplayName(path),
        });
      }, 0);
    } catch (cause: unknown) {
      const message =
        cause instanceof Error
          ? cause.message
          : language === "fa"
            ? "انتخاب پوشه ممکن نشد. مطمئن شوید عامل محلی در حال اجراست."
            : "Could not open the folder picker. Ensure the local agent is running.";
      setError(message);
    } finally {
      setPickingFolder(false);
    }
  }

  function configGateMessage(): string | null {
    if (!settingsView?.workspace_id) {
      return language === "fa"
        ? "فضای کار بارگذاری نشده. تنظیمات را باز کنید و اتصال را بررسی کنید."
        : "Workspace settings are not loaded. Open Settings and check the companion connection.";
    }
    if (!settingsView.liara.token_configured) {
      return language === "fa"
        ? "توکن لیارا تنظیم نشده. برای ادامه به تنظیمات بروید."
        : "Liara API token is not configured. Open Settings to continue.";
    }
    return null;
  }

  function stamp(event: string, actor = "orchestrator") {
    return { time: new Date().toISOString(), event, actor };
  }

  async function startOrchestratorGoal(prompt: string, options?: { prependUser?: boolean }) {
    if (!hasLocalWorkspace) {
      setError(strings.folderGateError);
      setActiveNav("New Chat");
      return;
    }

    const gate = configGateMessage();
    if (gate) {
      setError(gate);
      setActiveNav("Settings");
      setMessages((current) => [
        ...current,
        ...(options?.prependUser === false ? [] : [{ id: id(), role: "user" as const, text: prompt }]),
        { id: id(), role: "assistant", text: gate },
      ]);
      return;
    }

    const workspaceId = settingsView!.workspace_id;
    setActiveNav("New Chat");
    setError("");
    setLoading(true);
    setOrchestratorRun(null);
    if (options?.prependUser !== false) {
      setMessages((current) => [...current, { id: id(), role: "user", text: prompt }]);
    }

    try {
      const appPath = localWorkspaceRef.current?.path ?? null;
      const created = await createCase(workspaceId, prompt);
      let run: OrchestratorRun = {
        case_id: created.id,
        workspace_id: workspaceId,
        goal: prompt,
        stage: "assessing",
        // Inspector timeline is request-derived; chat bubbles stay quiet (02).
        summary: language === "fa" ? "در حال آماده‌سازی پاسخ…" : "Preparing a reply…",
        timeline: buildRequestTimeline({
          language,
          goal: prompt,
          stage: "assessing",
        }),
        events: [stamp("create_case")],
      };
      setOrchestratorRun(run);

      const readiness = await assessReadiness(workspaceId, created.id, appPath);
      run = {
        ...run,
        stage: "planning",
        readiness,
        summary: language === "fa" ? "در حال آماده‌سازی طرح…" : "Drafting a plan…",
        timeline: buildRequestTimeline({
          language,
          goal: prompt,
          stage: "planning",
          readiness,
        }),
        events: [...run.events, stamp("assess_readiness")],
      };
      setOrchestratorRun(run);

      const route = resolveChallengeLoopRoute(prompt, {
        selectedServiceId: selectedServiceId || null,
      });

      if (route.mode === "troubleshoot") {
        await runTroubleshootLoop({
          workspaceId,
          caseId: created.id,
          goal: prompt,
          projectName: route.projectName,
          readiness,
          priorEvents: run.events,
          priorRun: run,
        });
        return;
      }

      if (route.mode === "maintain_monitor") {
        await runMaintainMonitorLoop({
          workspaceId,
          caseId: created.id,
          goal: prompt,
          target: route.target,
          readiness,
          priorEvents: run.events,
          priorRun: run,
        });
        return;
      }

      if (route.mode === "conversation") {
        const reply =
          language === "fa"
            ? "سلام! من همراه لیارا هستم. بگویید می‌خواهید چه کاری انجام دهید — مثلاً دیپلوی، اتصال دامنه، پایش، یا عیب‌یابی یک سرویس. تا وقتی درخواست مشخص نشود طرح اجرایی نمی‌سازم."
            : "Hi! I’m your Liara companion. Tell me what you need — deploy, attach a domain, monitor, or troubleshoot a service. I won’t draft an execution plan until the request is clear.";
        const next: OrchestratorRun = {
          ...run,
          stage: "verified",
          summary: reply,
          timeline: buildRequestTimeline({
            language,
            goal: prompt,
            stage: "verified",
            readiness,
            operationState: "conversation",
          }),
          events: [...run.events, stamp("conversation_reply")],
        };
        setOrchestratorRun(next);
        setMessages((current) => [
          ...current,
          { id: id(), role: "assistant", text: reply, kind: "live" },
        ]);
        return;
      }

      if (route.mode === "intake") {
        await pauseForIntake({
          workspaceId,
          goal: prompt,
          intakeKind: route.intakeKind,
          readiness,
          priorRun: run,
        });
        return;
      }

      await finalizePlanFromIntake({
        workspaceId,
        caseId: created.id,
        goal: prompt,
        readiness,
        priorEvents: run.events,
        priorRun: run,
      });
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : "The orchestrator could not start.";
      setError(message);
      setOrchestratorRun((current) =>
        current
          ? {
              ...current,
              stage: "error",
              error: message,
              summary: message,
              timeline: buildRequestTimeline({
                language,
                goal: current.goal,
                stage: "error",
                planBody: current.plan_body,
                readiness: current.readiness,
                error: message,
              }),
            }
          : current,
      );
      setMessages((current) => [
        ...current,
        { id: id(), role: "assistant", text: language === "fa" ? `اجرا ناموفق بود: ${message}` : `I couldn’t complete the run: ${message}` },
      ]);
      if (/token|Settings|configure|workspace|Liara|Aval/i.test(message)) setActiveNav("Settings");
    } finally {
      setLoading(false);
    }
  }

  async function pauseForIntake(args: {
    workspaceId: string;
    goal: string;
    intakeKind: IntakeKind;
    readiness: OrchestratorRun["readiness"];
    priorRun: OrchestratorRun;
  }) {
    const req = intakeRequirements(args.intakeKind);
    let intakeServices: { id: string; name: string; status?: string }[] = [];
    let intakePlans: { id: string; label: string; hint?: string | null }[] = [];
    let loadError: string | null = null;
    try {
      const liveServices = await getServices(args.workspaceId);
      intakeServices = liveServices.map((row) => ({
        id: row.id,
        name: row.name,
        status: row.status,
      }));
      if (req.require_plan) {
        const plans = await getLiaraPlans(args.workspaceId);
        intakePlans = plans.map((plan) => ({
          id: plan.id,
          label: plan.label,
          hint: plan.hint,
        }));
      }
    } catch (cause) {
      loadError =
        cause instanceof Error
          ? cause.message
          : language === "fa"
            ? "بارگذاری سرویس‌ها یا پلن‌ها ناموفق بود."
            : "Could not load services or plans.";
    }

    const intakeText = intakeAssistantPrompt(args.intakeKind, language);
    const next: OrchestratorRun = {
      ...args.priorRun,
      stage: "awaiting_intake",
      intake: {
        kind: args.intakeKind,
        services: intakeServices,
        plans: intakePlans,
        require_plan: req.require_plan,
        require_domain: req.require_domain,
        load_error: loadError,
      },
      summary: intakeText,
      timeline: buildRequestTimeline({
        language,
        goal: args.goal,
        stage: "awaiting_intake",
        readiness: args.readiness,
      }),
      events: [...args.priorRun.events, stamp("await_intake")],
    };
    setOrchestratorRun(next);
    setMessages((current) => [
      ...current,
      { id: id(), role: "assistant", text: intakeText, kind: "live" },
    ]);
  }

  async function runTroubleshootLoop(args: {
    workspaceId: string;
    caseId: string;
    goal: string;
    projectName: string;
    readiness: OrchestratorRun["readiness"];
    priorEvents: OrchestratorRun["events"];
    priorRun: OrchestratorRun;
  }) {
    const projectName = args.projectName.trim();
    let run: OrchestratorRun = {
      ...args.priorRun,
      stage: "planning",
      intake: null,
      summary:
        language === "fa"
          ? `در حال جمع‌آوری شواهد برای ${projectName}…`
          : `Gathering evidence for ${projectName}…`,
      timeline: buildRequestTimeline({
        language,
        goal: args.goal,
        stage: "planning",
        readiness: args.readiness,
      }),
      events: [...args.priorEvents, stamp("collect_evidence")],
    };
    setOrchestratorRun(run);

    const evidence = await collectEvidence({
      workspaceId: args.workspaceId,
      caseId: args.caseId,
      projectName,
      symptom: args.goal.slice(0, 200),
    });
    const diagnosis = await diagnoseCase({
      workspaceId: args.workspaceId,
      caseId: args.caseId,
      evidenceVersion: evidence.version,
    });
    const fixOptions = await proposeFixOptions({
      workspaceId: args.workspaceId,
      caseId: args.caseId,
      diagnosisVersion: diagnosis.version,
      projectName,
    });

    run = {
      ...run,
      evidence,
      diagnosis,
      fix_options: fixOptions,
      events: [
        ...run.events,
        stamp("diagnose"),
        stamp("propose_fix_options"),
      ],
    };

    const enabled = fixOptions.options.find((option) => option.enabled);
    if (enabled) {
      const plan = await createPlanFromFix({
        workspaceId: args.workspaceId,
        caseId: args.caseId,
        optionId: enabled.id,
      });
      const assistantText = planReadyAssistantText(
        language,
        diagnosis.summary ?? plan.body.summary,
      );
      const next: OrchestratorRun = {
        ...run,
        stage: "awaiting_approval",
        plan_id: plan.plan_id,
        plan_version: plan.version,
        content_hash: plan.content_hash,
        plan_body: plan.body,
        summary: assistantText,
        timeline: buildRequestTimeline({
          language,
          goal: args.goal,
          stage: "awaiting_approval",
          planBody: plan.body,
          readiness: args.readiness,
        }),
        events: [...run.events, stamp("create_plan_from_fix")],
      };
      setOrchestratorRun(next);
      setMessages((current) => [
        ...current,
        { id: id(), role: "assistant", text: assistantText, kind: "live" },
      ]);
      return;
    }

    const gapsNote =
      diagnosis.insufficient_evidence || evidence.gaps.length > 0
        ? language === "fa"
          ? "شواهد ناقص است؛ بدون حدس ریشهٔ علت."
          : "Evidence is incomplete — no invented root cause."
        : language === "fa"
          ? "گزینهٔ اصلاح فعالی برای اجرا نیست (محدودیت API یا رجیستری)."
          : "No enabled fix option is available (API/registry limit).";
    const summary =
      (diagnosis.summary?.trim() ||
        (language === "fa" ? "تشخیص آماده است." : "Diagnosis ready.")) +
      ` ${gapsNote}`;
    const next: OrchestratorRun = {
      ...run,
      stage: "verified",
      summary,
      timeline: buildRequestTimeline({
        language,
        goal: args.goal,
        stage: "verified",
        readiness: args.readiness,
        operationState: "diagnosis_only",
      }),
      events: [...run.events, stamp("troubleshoot_complete")],
    };
    setOrchestratorRun(next);
    setMessages((current) => [
      ...current,
      { id: id(), role: "assistant", text: summary, kind: "live" },
    ]);
  }

  async function runMaintainMonitorLoop(args: {
    workspaceId: string;
    caseId: string;
    goal: string;
    target: string;
    readiness: OrchestratorRun["readiness"];
    priorEvents: OrchestratorRun["events"];
    priorRun: OrchestratorRun;
  }) {
    const target = args.target.trim();
    const monitor = await enableMonitor({
      workspaceId: args.workspaceId,
      target,
      caseId: args.caseId,
    });
    const summary = language === "fa"
      ? `مانیتور برای «${target}» فعال شد. این کار اجازهٔ نوشتن حساس نمی‌دهد؛ بازیابی جداگانه تأیید می‌خواهد.`
      : `Monitor enabled for “${target}”. This does not grant write permission — recovery still needs Approve.`;
    const next: OrchestratorRun = {
      ...args.priorRun,
      stage: "verified",
      intake: null,
      monitor,
      summary,
      timeline: buildRequestTimeline({
        language,
        goal: args.goal,
        stage: "verified",
        readiness: args.readiness,
        operationState: "monitor_enabled",
      }),
      events: [...args.priorEvents, stamp("enable_monitor")],
    };
    setOrchestratorRun(next);
    setMessages((current) => [
      ...current,
      { id: id(), role: "assistant", text: summary, kind: "live" },
    ]);
  }

  async function finalizePlanFromIntake(args: {
    workspaceId: string;
    caseId: string;
    goal: string;
    readiness: OrchestratorRun["readiness"];
    priorEvents: OrchestratorRun["events"];
    priorRun: OrchestratorRun;
    deploy?: Record<string, unknown>;
    ops?: Record<string, unknown>;
    deps?: Record<string, unknown>;
  }) {
    const plan = await createPlan({
      workspaceId: args.workspaceId,
      caseId: args.caseId,
      goal: args.goal,
      useLlm: Boolean(settingsView?.aval.api_key_configured),
      ...(args.deploy ? { deploy: args.deploy } : {}),
      ...(args.ops ? { ops: args.ops } : {}),
      ...(args.deps ? { deps: args.deps } : {}),
    });

    const assistantText = planReadyAssistantText(language, plan.body.summary);
    const next: OrchestratorRun = {
      ...args.priorRun,
      stage: "awaiting_approval",
      intake: null,
      plan_id: plan.plan_id,
      plan_version: plan.version,
      content_hash: plan.content_hash,
      plan_body: plan.body,
      summary: assistantText,
      timeline: buildRequestTimeline({
        language,
        goal: args.goal,
        stage: "awaiting_approval",
        planBody: plan.body,
        readiness: args.readiness,
      }),
      events: [...args.priorEvents, stamp("create_plan")],
    };
    setOrchestratorRun(next);
    setMessages((current) => [
      ...current,
      {
        id: id(),
        role: "assistant",
        text: assistantText,
        kind: "live",
      },
    ]);
  }

  async function confirmIntake(values: IntakeConfirmValues) {
    if (!orchestratorRun || orchestratorRun.stage !== "awaiting_intake" || loading || approvalBusy) {
      return;
    }
    if (!orchestratorRun.intake) return;

    setLoading(true);
    setError("");
    setActiveNav("New Chat");

    try {
      const appPath = localWorkspaceRef.current?.path ?? null;
      const kind = orchestratorRun.intake.kind;
      const planning: OrchestratorRun = {
        ...orchestratorRun,
        stage: "planning",
        summary: language === "fa" ? "در حال آماده‌سازی طرح…" : "Drafting a plan…",
        timeline: buildRequestTimeline({
          language,
          goal: orchestratorRun.goal,
          stage: "planning",
          readiness: orchestratorRun.readiness,
        }),
        events: [...orchestratorRun.events, stamp("intake_confirmed", "user")],
      };
      setOrchestratorRun(planning);

      if (kind === "troubleshoot") {
        await runTroubleshootLoop({
          workspaceId: orchestratorRun.workspace_id,
          caseId: orchestratorRun.case_id,
          goal: orchestratorRun.goal,
          projectName: values.project_name,
          readiness: orchestratorRun.readiness,
          priorEvents: planning.events,
          priorRun: planning,
        });
        return;
      }

      if (kind === "maintain_monitor") {
        await runMaintainMonitorLoop({
          workspaceId: orchestratorRun.workspace_id,
          caseId: orchestratorRun.case_id,
          goal: orchestratorRun.goal,
          target: values.project_name,
          readiness: orchestratorRun.readiness,
          priorEvents: planning.events,
          priorRun: planning,
        });
        return;
      }

      const payloads = buildPlanPayloads({
        kind,
        project_name: values.project_name,
        plan_id: values.plan_id,
        domain_name: values.domain_name,
        app_path: appPath,
      });

      await finalizePlanFromIntake({
        workspaceId: orchestratorRun.workspace_id,
        caseId: orchestratorRun.case_id,
        goal: orchestratorRun.goal,
        readiness: orchestratorRun.readiness,
        priorEvents: planning.events,
        priorRun: planning,
        deploy: payloads.deploy,
        ops: payloads.ops,
        deps: payloads.deps,
      });
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : "The orchestrator could not draft a plan.";
      setError(message);
      setOrchestratorRun((current) =>
        current
          ? {
              ...current,
              stage: "awaiting_intake",
              error: message,
              summary: message,
              timeline: buildRequestTimeline({
                language,
                goal: current.goal,
                stage: "awaiting_intake",
                readiness: current.readiness,
                error: message,
              }),
            }
          : current,
      );
      setMessages((current) => [
        ...current,
        {
          id: id(),
          role: "assistant",
          text:
            language === "fa"
              ? `آماده‌سازی طرح ناموفق بود: ${message}`
              : `Could not draft the plan: ${message}`,
        },
      ]);
      if (/token|Settings|configure|workspace|Liara|Aval/i.test(message)) setActiveNav("Settings");
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const prompt = draft.trim();
    if (!prompt || loading || approvalBusy) return;
    if (!hasLocalWorkspace) {
      setError(strings.folderGateError);
      return;
    }
    setDraft("");
    // Free-text "approve" is never authorization — only the Approve control executes.
    if (
      /^(approve|reject|stop|تأیید|رد)\b/i.test(prompt) &&
      (orchestratorRun?.stage === "awaiting_approval" || orchestratorRun?.stage === "awaiting_intake")
    ) {
      setActiveNav("New Chat");
      setMessages((current) => [
        ...current,
        { id: id(), role: "user", text: prompt },
        {
          id: id(),
          role: "assistant",
          text:
            language === "fa"
              ? orchestratorRun.stage === "awaiting_intake"
                ? "انتخاب سرویس از متن گفتگو انجام نمی‌شود. از کارت انتخاب در چت استفاده کنید."
                : "تأیید از متن گفتگو پذیرفته نمی‌شود. از دکمه‌های تأیید یا رد روی کارت طرح استفاده کنید."
              : orchestratorRun.stage === "awaiting_intake"
                ? "Chat text cannot submit intake. Use the selection card in the thread."
                : "Chat text cannot authorize writes. Use the Approve or Reject controls on the plan card.",
        },
      ]);
      return;
    }
    await startOrchestratorGoal(prompt);
  }

  async function decideApproval(decision: "approve" | "reject") {
    if (!orchestratorRun || orchestratorRun.stage !== "awaiting_approval" || approvalBusy) return;
    if (!orchestratorRun.plan_id) return;

    setApprovalBusy(true);
    setError("");

    if (decision === "reject") {
      const rejected: OrchestratorRun = {
        ...orchestratorRun,
        stage: "rejected",
        summary:
          language === "fa"
            ? "طرح رد شد. هیچ اجرایی انجام نشد."
            : "Plan rejected. No execute was performed.",
        timeline: buildRequestTimeline({
          language,
          goal: orchestratorRun.goal,
          stage: "rejected",
          planBody: orchestratorRun.plan_body,
          readiness: orchestratorRun.readiness,
        }),
        events: [...orchestratorRun.events, stamp("reject_plan", "user")],
      };
      setOrchestratorRun(rejected);
      setMessages((current) => [...current, { id: id(), role: "assistant", text: rejected.summary, kind: "live" }]);
      setApprovalBusy(false);
      return;
    }

    try {
      setOrchestratorRun((current) =>
        current
          ? {
              ...current,
              stage: "approving",
              summary: language === "fa" ? "در حال ثبت تأیید…" : "Recording approval…",
              timeline: buildRequestTimeline({
                language,
                goal: current.goal,
                stage: "approving",
                planBody: current.plan_body,
                readiness: current.readiness,
              }),
            }
          : current,
      );
      const approval = await approvePlan(orchestratorRun.workspace_id, orchestratorRun.plan_id);
      setOrchestratorRun((current) =>
        current
          ? {
              ...current,
              stage: "executing",
              approval,
              summary: language === "fa" ? "تأیید شد؛ در حال اجرا…" : "Approved; executing plan…",
              timeline: buildRequestTimeline({
                language,
                goal: current.goal,
                stage: "executing",
                planBody: current.plan_body,
                readiness: current.readiness,
              }),
              events: [...current.events, stamp("approve_plan", "user")],
            }
          : current,
      );

      const clientRequestId =
        typeof crypto !== "undefined" && "randomUUID" in crypto
          ? crypto.randomUUID()
          : `req-${Date.now()}`;
      const operation = await executePlan({
        workspaceId: orchestratorRun.workspace_id,
        planId: orchestratorRun.plan_id,
        clientRequestId,
      });

      setOrchestratorRun((current) =>
        current
          ? {
              ...current,
              stage: "verifying",
              operation,
              summary: language === "fa" ? "اجرا شد؛ در حال راستی‌آزمایی…" : "Executed; verifying result…",
              timeline: buildRequestTimeline({
                language,
                goal: current.goal,
                stage: "verifying",
                planBody: current.plan_body,
                readiness: current.readiness,
                operationState: operation.state,
              }),
              events: [...current.events, stamp("execute_plan")],
            }
          : current,
      );

      const verified = await verifyResult(orchestratorRun.workspace_id, operation.id);
      const doneSummary = verificationAssistantText(language, verified.state);
      setOrchestratorRun((current) =>
        current
          ? {
              ...current,
              stage: "verified",
              operation: verified,
              summary: doneSummary,
              timeline: buildRequestTimeline({
                language,
                goal: current.goal,
                stage: "verified",
                planBody: current.plan_body,
                readiness: current.readiness,
                operationState: verified.state,
              }),
              events: [...current.events, stamp("verify_result")],
            }
          : current,
      );
      setMessages((current) => [...current, { id: id(), role: "assistant", text: doneSummary, kind: "live" }]);
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : "The approval request failed.";
      setError(message);
      setOrchestratorRun((current) =>
        current
          ? {
              ...current,
              stage: "error",
              error: message,
              summary: message,
              timeline: buildRequestTimeline({
                language,
                goal: current.goal,
                stage: "error",
                planBody: current.plan_body,
                readiness: current.readiness,
                operationState: current.operation?.state,
                error: message,
              }),
            }
          : current,
      );
      setMessages((current) => [
        ...current,
        { id: id(), role: "assistant", text: language === "fa" ? `تأیید/اجرا ناموفق: ${message}` : `Approve/execute failed: ${message}` },
      ]);
    } finally {
      setApprovalBusy(false);
    }
  }

  function archiveCurrentConversation() {
    if (!hasLocalWorkspace) return;
    const title = messages.find((message) => message.role === "user")?.text;
    if (!title) return;
    const conversation: Conversation = {
      id: conversationIdRef.current,
      title,
      serviceId: selectedServiceId || "workspace",
      messages: [...messages],
      updatedAt: new Date().toISOString(),
      orchestratorRun,
    };
    setConversations((current) => [
      conversation,
      ...current.filter((item) => item.id !== conversation.id),
    ].slice(0, 8));
  }

  function openConversation(conversation: Conversation, folderKey?: string) {
    if (folderKey && folderKey !== workspaceKey) {
      const folder = recentWorkspaces.find(
        (item) => normalizeWorkspaceKey(item.path) === folderKey,
      );
      if (folder) {
        const previous = localWorkspaceRef.current;
        const previousKey = previous ? normalizeWorkspaceKey(previous.path) : null;
        if (previousKey && previousKey !== folderKey) {
          flushConversationsForKey(previousKey, conversations, true);
        }
        const activated = activateRecentWorkspace(window.localStorage, folder.path);
        if (activated.workspace) {
          localWorkspaceRef.current = activated.workspace;
          setLocalWorkspace(activated.workspace);
          setRecentWorkspaces(listRecentWorkspaces(window.localStorage));
          skipInitialHistorySave.current = true;
          const loaded = loadConversationHistory(window.localStorage, folderKey);
          setConversations(loaded.conversations);
        }
      }
      ensureFolderExpanded(folderKey);
    }

    if (conversation.id === conversationIdRef.current) {
      setActiveNav("New Chat");
      setMobileNavOpen(false);
      syncRoute({ kind: "chat", conversationId: conversation.id });
      return;
    }
    archiveCurrentConversation();
    setConversationId(conversation.id);
    setSelectedServiceId(conversation.serviceId === "workspace" ? "" : conversation.serviceId);
    setMessages(conversation.messages);
    setOrchestratorRun(conversation.orchestratorRun);
    setActiveNav("New Chat");
    setMobileNavOpen(false);
    setError("");
    syncRoute({ kind: "chat", conversationId: conversation.id });
  }

  function navigate(item: NavItem) {
    setActiveNav(item);
    setMobileNavOpen(false);
    setError("");
    if (item === "Settings") {
      syncRoute({ kind: "settings" });
      return;
    }
    if (item === "New Chat") {
      if (!hasLocalWorkspace) {
        resetActiveThread();
        return;
      }
      archiveCurrentConversation();
      resetActiveThread();
    } else {
      syncRoute({ kind: "chat", conversationId: conversationIdRef.current || null });
    }
  }

  function requestNewChat(folderKey?: string) {
    if (folderKey && folderKey !== workspaceKey) {
      const folder = recentWorkspaces.find(
        (item) => normalizeWorkspaceKey(item.path) === folderKey,
      );
      if (folder) {
        switchToRecentWorkspace(folder.path);
        setActiveNav("New Chat");
        setMobileNavOpen(false);
        return;
      }
    }
    if (!hasLocalWorkspace) {
      setActiveNav("New Chat");
      setMobileNavOpen(false);
      setError("");
      void pickWorkspaceFolder();
      return;
    }
    navigate("New Chat");
  }

  function activateFolder(folder: LocalWorkspace) {
    const key = normalizeWorkspaceKey(folder.path);
    ensureFolderExpanded(key);
    if (key === workspaceKey) return;
    switchToRecentWorkspace(folder.path);
  }

  function renderWorkspace() {
    if (activeNav === "New Chat") {
      return (
        <>
          <header className="chat-topbar">
            <button className="mobile-menu icon-button" onClick={() => setMobileNavOpen(true)} aria-label="باز کردن منو"><Menu size={18} /></button>
            <div className="flex min-w-0 items-center gap-2">
              <span className="topbar-spark"><Sparkles size={14} /></span>
              <span className="truncate text-sm font-medium text-slate-200">
                {orchestratorRun
                  ? (orchestratorRun.goal.slice(0, 48) || strings.workspace)
                  : (localWorkspace?.displayName ?? strings.workspace)}
              </span>
              <span className="topbar-separator" />
              <span className={`topbar-mode ${settingsView?.liara.token_configured ? "topbar-mode-live" : ""}`}>
                <span /> {settingsView?.liara.token_configured ? "حالت زنده" : "نیاز به پیکربندی"}
              </span>
            </div>
            <div className="logical-end flex items-center gap-2">
              <label className="service-picker">
                <span className="service-health-dot" />
                <select
                  aria-label="انتخاب سرویس"
                  value={selectedServiceId}
                  onChange={(event) => setSelectedServiceId(event.target.value)}
                  disabled={services.length === 0}
                >
                  {services.length === 0 ? <option value="">{strings.noServices}</option> : null}
                  {services.map((service) => <option key={service.id} value={service.id}>{service.name}</option>)}
                </select>
                <ChevronDown size={13} />
              </label>

              <button className="icon-button desktop-menu" aria-label="گزینه‌های بیشتر"><MoreHorizontal size={18} /></button>
            </div>
          </header>

          <section className={`chat-scroll ${messages.length === 0 || !hasLocalWorkspace ? "chat-scroll-empty" : ""}`}>
            {!hasLocalWorkspace ? (
              <div className="welcome-wrap workspace-gate">
                <div className="welcome-orb"><div><FolderOpen size={26} /></div></div>
                <div className="welcome-eyebrow"><span /> همراه لیارا · فضای کار محلی</div>
                <h1>{strings.pickFolderTitle}</h1>
                <p className="welcome-caption">{strings.pickFolderBody}</p>
                <button
                  type="button"
                  className="workspace-gate-cta"
                  onClick={() => void pickWorkspaceFolder()}
                  disabled={pickingFolder}
                >
                  <FolderOpen size={16} />
                  {pickingFolder ? strings.pickFolderBusy : strings.pickFolderCta}
                </button>
                <div className="trust-note"><ShieldCheck size={14} /> {strings.trust}</div>
                {error && <div className="inline-error mt-4"><CircleHelp size={15} />{error}</div>}
              </div>
            ) : messages.length === 0 ? (
              <div className="welcome-wrap">
                <div className="welcome-orb"><div><Bot size={26} /></div></div>
                <div className="welcome-eyebrow"><span /> همراه لیارا · هم‌پایلوت ابری شما</div>
                <h1>{strings.start}<br /><span>{strings.subtitle}</span></h1>
                <p className="welcome-caption">{strings.caption}</p>
                <div className="suggestion-grid">
                  <button className="suggestion-card" onClick={() => void startOrchestratorGoal(strings.first)}>
                    <span className="suggestion-icon icon-blue"><Activity size={16} /></span>
                    <span><strong>{strings.first}</strong><small>{strings.firstHint}</small></span>
                    <ArrowUp size={14} className="suggestion-arrow" />
                  </button>
                  <button className="suggestion-card" onClick={() => void startOrchestratorGoal(strings.second)}>
                    <span className="suggestion-icon icon-violet"><Server size={16} /></span>
                    <span><strong>{strings.second}</strong><small>{strings.secondHint}</small></span>
                    <ArrowUp size={14} className="suggestion-arrow" />
                  </button>
                  <button className="suggestion-card" onClick={() => void startOrchestratorGoal(strings.third)}>
                    <span className="suggestion-icon icon-cyan"><Code2 size={16} /></span>
                    <span><strong>{strings.third}</strong><small>{strings.thirdHint}</small></span>
                    <ArrowUp size={14} className="suggestion-arrow" />
                  </button>
                </div>
                <div className="trust-note"><ShieldCheck size={14} /> {strings.trust}</div>
              </div>
            ) : (
              <div className="message-list">
                {messages.map((message) => (
                  <div className={`message-row ${message.role}`} key={message.id}>
                    <div className={message.role === "assistant" ? "assistant-avatar" : "user-avatar"}>
                      {message.role === "assistant" ? <Sparkles size={14} /> : "ش"}
                    </div>
                    <div className="message-stack">
                      <div className="message-meta">
                        <span>{message.role === "assistant" ? "همراه لیارا" : "شما"}</span>
                        {message.kind === "demo" && <span className="message-demo">SIMULATED</span>}
                        {message.kind === "live" && <span className="message-demo message-live">زنده</span>}
                      </div>
                      <div className="message-bubble">
                        <p className="message-text">{message.text}</p>
                      </div>
                    </div>
                  </div>
                ))}
                {loading && (
                  <div className="message-row assistant">
                    <div className="assistant-avatar"><Sparkles size={14} /></div>
                    <div className="message-stack">
                      <div className="message-meta">
                        <span>همراه لیارا</span>
                        <span className="message-demo message-live">زنده</span>
                      </div>
                      <div className="message-bubble">
                        <div className="thinking-indicator"><span /><span /><span /> {strings.thinking}</div>
                      </div>
                    </div>
                  </div>
                )}
                {orchestratorRun?.stage === "awaiting_intake" && orchestratorRun.intake && (
                  <div className="message-row assistant agent-block">
                    <div className="assistant-avatar"><Sparkles size={14} /></div>
                    <div className="message-stack">
                      <IntakePanel
                        run={orchestratorRun}
                        language={language}
                        busy={loading}
                        onConfirm={(values) => void confirmIntake(values)}
                        onOpenSettings={() => navigate("Settings")}
                      />
                    </div>
                  </div>
                )}
                {(orchestratorRun?.plan_body ||
                  orchestratorRun?.evidence ||
                  orchestratorRun?.diagnosis ||
                  orchestratorRun?.monitor) && (
                  <div className="message-row assistant agent-block">
                    <div className="assistant-avatar"><Sparkles size={14} /></div>
                    <div className="message-stack">
                      <PlanApprovalPanel
                        run={orchestratorRun}
                        language={language}
                        busy={approvalBusy}
                        onApprove={() => void decideApproval("approve")}
                        onReject={() => void decideApproval("reject")}
                      />
                    </div>
                  </div>
                )}
                {error && (
                  <div className="message-row assistant">
                    <div className="assistant-avatar"><CircleHelp size={14} /></div>
                    <div className="message-stack">
                      <div className="inline-error inline-error-inline"><CircleHelp size={15} />{error}</div>
                    </div>
                  </div>
                )}
                <div ref={chatEndRef} />
              </div>
            )}
          </section>

          {error && messages.length === 0 && hasLocalWorkspace && (
            <div className="inline-error mx-auto max-w-3xl"><CircleHelp size={15} />{error}</div>
          )}
          <div className="composer-wrap">
            <form className="composer" onSubmit={handleSubmit}>
              <button className="composer-plus" type="button" aria-label="افزودن زمینه" disabled={!hasLocalWorkspace}>
                <Plus size={17} />
              </button>
              <input
                aria-label="پیام به همراه لیارا"
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                placeholder={hasLocalWorkspace ? strings.prompt : strings.pickFolderPrompt}
                disabled={loading || !hasLocalWorkspace}
              />
              <div className="composer-actions">
                <button className="composer-tool" type="button" aria-label="جستجوی زمینه" disabled={!hasLocalWorkspace}>
                  <Search size={15} />
                </button>
                <span className="composer-divider" />
                <button
                  className="composer-send"
                  type="submit"
                  aria-label="ارسال پیام"
                  disabled={!hasLocalWorkspace || !draft.trim() || loading}
                >
                  {loading ? <div className="mini-spinner" /> : <ArrowUp size={16} />}
                </button>
              </div>
            </form>
            <p className="composer-footnote">{strings.powered}</p>
          </div>
        </>
      );
    }

    if (activeNav === "Settings") {
      return (
        <SettingsPanel
          settingsView={settingsView}
          loadState={settingsLoadState}
          loadError={settingsLoadError}
          onOpenNav={() => setMobileNavOpen(true)}
          onViewChange={setSettingsView}
          onAfterMutate={() => void refreshCatalog()}
        />
      );
    }

    return (
      <NavigationView
        activeNav={activeNav}
        language={language}
        settingsView={settingsView}
        services={services}
        servicesState={servicesState}
        servicesError={servicesError}
        history={recentConversations}
        onOpenConversation={openConversation}
        onStart={() => navigate("New Chat")}
        onOpenNav={() => setMobileNavOpen(true)}
        onOpenSettings={() => navigate("Settings")}
        onRefreshServices={() => void refreshCatalog()}
        onInvestigate={(service) => {
          setSelectedServiceId(service.id);
          void startOrchestratorGoal(
            language === "fa"
              ? `بررسی وضعیت سرویس ${service.name}`
              : `Investigate service ${service.name}`,
          );
        }}
        onStartMonitorGoal={() =>
          void startOrchestratorGoal(
            language === "fa"
              ? "یک مانیتور پایش برای فضای کار فعال کن"
              : "Enable a maintain monitor for this workspace",
          )
        }
        onStartDomainGoal={(projectName) =>
          void startOrchestratorGoal(
            language === "fa"
              ? projectName
                ? `دامنه سفارشی را به سرویس ${projectName} وصل کن`
                : "دامنه سفارشی را به سرویس وصل کن"
              : projectName
                ? `Attach a custom domain to service ${projectName}`
                : "Attach a custom domain to my service",
          )
        }
      />
    );
  }

  return (
    <div className={`app-shell ${language === "fa" ? "rtl-mode" : ""}`} dir={language === "fa" ? "rtl" : "ltr"}>
      <AnimatePresence>
        {mobileNavOpen && <motion.button className="mobile-scrim" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setMobileNavOpen(false)} aria-label="بستن منو" />}
      </AnimatePresence>
      <aside className={`sidebar ${mobileNavOpen ? "sidebar-open" : ""}`}>
        <div className="brand-row">
          <div className="brand-mark"><span /><span /><span /></div>
          <div className="brand-type"><strong>همراه <span>لیارا</span></strong><small>فضای کار عامل</small></div>
          <button className="mobile-menu logical-end icon-button" onClick={() => setMobileNavOpen(false)} aria-label="بستن منو"><X size={17} /></button>
        </div>

        <button
          className="new-chat-button"
          onClick={() => requestNewChat(workspaceKey ?? undefined)}
          type="button"
          disabled={pickingFolder}
        >
          <Plus size={15} /> {strings.newConversation}
        </button>

        <button
          type="button"
          className="add-folder-button"
          onClick={() => void pickWorkspaceFolder()}
          disabled={pickingFolder}
        >
          <FolderPlus size={15} />
          {pickingFolder ? strings.pickFolderBusy : strings.addFolder}
        </button>

        <div className="sidebar-section-label">{strings.foldersSection}</div>
        <div className="folder-accordion" role="tree" aria-label={strings.foldersSection}>
          {recentWorkspaces.length === 0 && (
            <p className="recent-empty">{strings.recentNeedFolder}</p>
          )}
          {recentWorkspaces.map((folder) => {
            const folderKey = normalizeWorkspaceKey(folder.path);
            const isActiveFolder = folderKey === workspaceKey;
            const isExpanded = Boolean(expandedFolders[folderKey] ?? isActiveFolder);
            const folderChats = conversationsByFolder[folderKey] ?? [];
            return (
              <div
                key={folder.path}
                className={`folder-group ${isActiveFolder ? "active" : ""}`}
                role="treeitem"
                aria-expanded={isExpanded}
              >
                <div className="folder-header">
                  <button
                    type="button"
                    className="folder-toggle"
                    aria-label={isExpanded ? strings.collapseFolder : strings.expandFolder}
                    onClick={() => toggleFolderExpanded(folderKey)}
                  >
                    <ChevronDown
                      size={14}
                      className={`folder-chevron ${isExpanded ? "open" : ""}`}
                    />
                  </button>
                  <button
                    type="button"
                    className="folder-title"
                    title={folder.path}
                    onClick={() => activateFolder(folder)}
                  >
                    <FolderOpen size={14} />
                    <span>{folder.displayName}</span>
                  </button>
                  <button
                    type="button"
                    className="folder-new-chat"
                    aria-label={strings.newConversation}
                    onClick={() => requestNewChat(folderKey)}
                  >
                    <Plus size={13} />
                  </button>
                </div>
                {isExpanded && (
                  <div className="folder-chats" role="group">
                    {folderChats.length === 0 ? (
                      <p className="recent-empty">{strings.recentEmpty}</p>
                    ) : (
                      folderChats.map((conversation) => {
                        const isActiveChat =
                          isActiveFolder &&
                          activeNav === "New Chat" &&
                          conversation.id === activeConversationId;
                        return (
                          <button
                            key={conversation.id}
                            type="button"
                            className={`recent-item ${isActiveChat ? "active" : ""}`}
                            onClick={() => openConversation(conversation, folderKey)}
                          >
                            <MessageSquare size={13} />
                            <span>{conversation.title}</span>
                          </button>
                        );
                      })
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        <div className="sidebar-bottom">
          <button
            type="button"
            className={`nav-item settings-nav ${activeNav === "Settings" ? "active" : ""}`}
            onClick={() => navigate("Settings")}
          >
            <Settings2 size={16} strokeWidth={1.8} />
            <span>{strings.settings}</span>
          </button>
        </div>
      </aside>
      <main className="main-workspace">
        {historyNotice && (
          <div className="history-notice" role="status">
            <CircleHelp size={14} />
            <span>{historyNotice}</span>
            <button onClick={() => setHistoryNotice("")} aria-label="بستن اعلان تاریخچه"><X size={13} /></button>
          </div>
        )}
        <div className="center-panel center-wide">
          <AnimatePresence mode="wait">
            <motion.div
              key={activeNav}
              className="workspace-surface"
              initial={surfaceMotion.initial}
              animate={surfaceMotion.animate}
              exit={surfaceMotion.exit}
              transition={surfaceMotion.transition}
            >
              {renderWorkspace()}
            </motion.div>
          </AnimatePresence>
        </div>
      </main>
    </div>
  );
}

export default App;
