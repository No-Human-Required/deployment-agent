import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import {
  Activity,
  ArrowUp,
  Bot,
  Bug,
  ChevronDown,
  CircleHelp,
  ClipboardList,
  Code2,
  ExternalLink,
  FilePlus2,
  FolderOpen,
  FolderPlus,
  Menu,
  MessageSquare,
  MoreHorizontal,
  Pencil,
  Plus,
  Rocket,
  Server,
  Settings2,
  ShieldCheck,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { IntakePanel } from "./components/IntakePanel";
import { NavigationView, type NavSurface } from "./components/nav/NavigationView";
import { PlanApprovalPanel } from "./components/PlanApprovalPanel";
import { SettingsPanel } from "./components/SettingsPanel";
import { SidebarWalletBalances } from "./components/SidebarWalletBalances";
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
import { composerSkills } from "./lib/composerSkills";
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
import { liaraServiceConsoleUrl } from "./lib/liaraLinks";
import {
  enrichPlatformOptions,
  LIARA_PLATFORMS,
  suggestLiaraPlatform,
  suggestServiceNameFromPackage,
} from "./lib/liaraPlatforms";
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
import {
  diagnosisFollowUpReplies,
  fixOptionReplies,
  generativeAwaitingUser,
  intakeServiceReplies,
  settingsReply,
  verifiedFollowUpReplies,
  whatNextReplies,
  type QuickReply,
} from "./lib/quickReplies";
import { buildRequestTimeline } from "./lib/requestTimeline";
import {
  loadUiPreferences,
  patchUiPreferences,
  type UiPreferences,
} from "./lib/uiPreferences";
import {
  activateRecentWorkspace,
  folderDisplayName,
  loadLocalWorkspace,
  normalizeWorkspaceKey,
  saveLocalWorkspace,
  type LocalWorkspace,
} from "./lib/workspace";

type NavItem = NavSurface;
type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  kind?: "demo" | "live";
  quickReplies?: QuickReply[];
};
type CatalogState = "idle" | "loading" | "ready" | "error";
type ContextService = { id: string; name: string };
type AttachPanel = "menu" | "services";

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
    noContextService: "No service in context",
    attachMenu: "Add context",
    attachSkills: "Skills",
    attachFile: "Attach file",
    attachService: "Liara service",
    attachBack: "Back",
    pickingFile: "Opening file picker…",
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
    chatOptions: "Conversation options",
    renameChat: "Rename title",
    deleteChat: "Delete conversation",
    renameTitleHeading: "Rename conversation",
    renameTitleBody: "Choose a short title that stays visible in the sidebar.",
    renameTitleSave: "Save title",
    deleteConfirmHeading: "Delete this conversation?",
    deleteConfirmBody: "This permanently removes the chat and its history from the workspace database. This cannot be undone.",
    deleteConfirmAction: "Delete conversation",
    cancel: "Cancel",
    titlePlaceholder: "Conversation title",
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
    noContextService: "سرویسی در زمینه نیست",
    attachMenu: "افزودن زمینه",
    attachSkills: "مهارت‌ها",
    attachFile: "انتخاب فایل",
    attachService: "سرویس لیارا",
    attachBack: "بازگشت",
    pickingFile: "در حال انتخاب فایل…",
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
    chatOptions: "گزینه‌های گفتگو",
    renameChat: "تغییر عنوان",
    deleteChat: "پاک کردن گفتگو",
    renameTitleHeading: "تغییر عنوان گفتگو",
    renameTitleBody: "عنوان کوتاهی انتخاب کنید که در سایدبار دیده شود.",
    renameTitleSave: "ذخیره عنوان",
    deleteConfirmHeading: "این گفتگو پاک شود؟",
    deleteConfirmBody: "گفتگو و تاریخچه‌اش برای همیشه از پایگاه‌داده فضای کار حذف می‌شود و قابل بازگشت نیست.",
    deleteConfirmAction: "پاک کردن گفتگو",
    cancel: "انصراف",
    titlePlaceholder: "عنوان گفتگو",
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
  const [localWorkspace, setLocalWorkspace] = useState<LocalWorkspace | null>(null);
  const [recentWorkspaces, setRecentWorkspaces] = useState<LocalWorkspace[]>([]);
  const workspaceKey = localWorkspace ? normalizeWorkspaceKey(localWorkspace.path) : null;
  const hasLocalWorkspace = Boolean(workspaceKey);
  const [expandedFolders, setExpandedFolders] = useState<Record<string, boolean>>({});
  const [historyCanBeSaved, setHistoryCanBeSaved] = useState(false);
  const [folderHistoryByKey, setFolderHistoryByKey] = useState<Record<string, Conversation[]>>({});
  const [services, setServices] = useState<Service[]>([]);
  const [servicesState, setServicesState] = useState<CatalogState>("idle");
  const [servicesError, setServicesError] = useState("");
  const [contextServices, setContextServices] = useState<ContextService[]>([]);
  const [contextFiles, setContextFiles] = useState<string[]>([]);
  const [attachOpen, setAttachOpen] = useState(false);
  const [attachPanel, setAttachPanel] = useState<AttachPanel>("menu");
  const [pickingFile, setPickingFile] = useState(false);
  const attachWrapRef = useRef<HTMLDivElement>(null);
  const primaryContextService =
    contextServices[0]?.name ?? contextServices[0]?.id ?? null;
  const [activeNav, setActiveNav] = useState<NavItem>(() => {
    const route = parseAppRoute(window.location.pathname);
    return route.kind === "settings" ? "Settings" : "New Chat";
  });
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [orchestratorRun, setOrchestratorRun] = useState<OrchestratorRun | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(false);
  const [approvalBusy, setApprovalBusy] = useState(false);
  const [pickingFolder, setPickingFolder] = useState(false);
  const [error, setError] = useState("");
  const [historyNotice, setHistoryNotice] = useState<string | null>(null);
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
  const persistHydratedRef = useRef(false);
  const routeHydratedRef = useRef(false);
  const localWorkspaceRef = useRef(localWorkspace);
  localWorkspaceRef.current = localWorkspace;
  const companionWorkspaceId = settingsView?.workspace_id ?? null;
  const companionWorkspaceIdRef = useRef(companionWorkspaceId);
  companionWorkspaceIdRef.current = companionWorkspaceId;
  const [chatMenuOpen, setChatMenuOpen] = useState(false);
  const [renameDialogOpen, setRenameDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");
  const [threadTitle, setThreadTitle] = useState<string | null>(null);
  const [uiPreferences, setUiPreferences] = useState<UiPreferences>(() => loadUiPreferences());
  const uiPreferencesRef = useRef(uiPreferences);
  uiPreferencesRef.current = uiPreferences;
  const chatMenuRef = useRef<HTMLDivElement>(null);
  const strings = copy[language];

  function rememberConversationForResume(conversationId: string | null) {
    const next = patchUiPreferences({ lastConversationId: conversationId });
    setUiPreferences(next);
  }

  function withQuickReplies(replies: QuickReply[] | undefined): { quickReplies?: QuickReply[] } {
    if (!uiPreferencesRef.current.quickRepliesEnabled) return {};
    if (!replies?.length) return {};
    return { quickReplies: replies };
  }
  const inferredTitle =
    messages.length >= 3
      ? messages.find((message) => message.role === "user")?.text
      : undefined;
  const currentTitle = (threadTitle?.trim() || inferredTitle || "").trim() || undefined;
  const canManageThread = Boolean(currentTitle || conversations.some((item) => item.id === activeConversationId));
  const recentConversations = hasLocalWorkspace
    ? [
        ...(currentTitle
          ? [{
              id: activeConversationId,
              title: currentTitle,
              serviceId: primaryContextService ?? "workspace",
              contextServices,
              messages,
              updatedAt: new Date().toISOString(),
              orchestratorRun,
            }]
          : []),
        ...conversations.filter((conversation) => conversation.id !== activeConversationId),
      ].slice(0, 8)
    : [];
  const conversationsByFolder = useMemo(() => {
    const map: Record<string, Conversation[]> = { ...folderHistoryByKey };
    if (workspaceKey) {
      map[workspaceKey] = recentConversations;
    }
    return map;
  }, [folderHistoryByKey, recentConversations, workspaceKey]);
  const lastAssistantMessageIndex = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      if (messages[i]?.role === "assistant") return i;
    }
    return -1;
  }, [messages]);

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

  async function hydratePersistence(workspaceId: string) {
    if (persistHydratedRef.current) return;
    const folders = await loadLocalWorkspace(workspaceId);
    const all = await loadAllConversationHistory(workspaceId);
    setLocalWorkspace(folders.workspace);
    localWorkspaceRef.current = folders.workspace;
    setRecentWorkspaces(folders.recent);
    setFolderHistoryByKey(all.byWorkspace);
    const activeKey = folders.workspace
      ? normalizeWorkspaceKey(folders.workspace.path)
      : null;
    if (activeKey) {
      setExpandedFolders((current) =>
        current[activeKey] ? current : { ...current, [activeKey]: true },
      );
      const loaded = await loadConversationHistory(workspaceId, activeKey);
      setConversations(loaded.conversations);
      if (loaded.error) setHistoryNotice(loaded.error);
    } else {
      setConversations([]);
    }
    const persistOk = folders.error === null && all.error === null;
    setHistoryCanBeSaved(persistOk);
    if (folders.error) setHistoryNotice(folders.error);
    else if (all.error) setHistoryNotice(all.error);
    skipInitialHistorySave.current = true;
    persistHydratedRef.current = true;
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
      await hydratePersistence(view.workspace_id);
      if (!view.liara.token_configured) {
        setServices([]);
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
      setContextServices((current) =>
        current.filter((item) => catalog.some((service) => service.id === item.id)),
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
    if (!attachOpen) return;
    function onPointerDown(event: MouseEvent) {
      const root = attachWrapRef.current;
      if (root && !root.contains(event.target as Node)) {
        setAttachOpen(false);
        setAttachPanel("menu");
      }
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setAttachOpen(false);
        setAttachPanel("menu");
      }
    }
    window.addEventListener("mousedown", onPointerDown);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("mousedown", onPointerDown);
      window.removeEventListener("keydown", onKey);
    };
  }, [attachOpen]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, orchestratorRun]);

  useEffect(() => {
    if (!hasLocalWorkspace) return;
    // Title locks in after the first 3 messages (user/assistant mix), then sticks.
    const autoTitle =
      messages.length >= 3
        ? (messages.find((message) => message.role === "user")?.text || "").trim().slice(0, 56)
        : "";
    if (autoTitle && !threadTitle?.trim()) setThreadTitle(autoTitle);
    const title =
      (threadTitle?.trim() ||
        autoTitle ||
        (messages.some((message) => message.role === "user")
          ? (messages.find((message) => message.role === "user")?.text || "").trim().slice(0, 56)
          : "") ||
        "").trim();
    if (!title) return;

    const currentConversation: Conversation = {
      id: conversationIdRef.current,
      title,
      serviceId: primaryContextService ?? "workspace",
      contextServices,
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
      rememberConversationForResume(currentConversation.id);
    }
  }, [messages, orchestratorRun, contextServices, primaryContextService, hasLocalWorkspace, activeNav, threadTitle]);

  useEffect(() => {
    if (!chatMenuOpen && !renameDialogOpen && !deleteDialogOpen) return;
    function onPointerDown(event: MouseEvent) {
      if (!chatMenuOpen) return;
      const root = chatMenuRef.current;
      if (root && !root.contains(event.target as Node)) setChatMenuOpen(false);
    }
    function onKey(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      if (renameDialogOpen) setRenameDialogOpen(false);
      else if (deleteDialogOpen) setDeleteDialogOpen(false);
      else setChatMenuOpen(false);
    }
    window.addEventListener("mousedown", onPointerDown);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("mousedown", onPointerDown);
      window.removeEventListener("keydown", onKey);
    };
  }, [chatMenuOpen, renameDialogOpen, deleteDialogOpen]);

  useEffect(() => {
    async function restoreConversationFromRoute(conversationId: string): Promise<boolean> {
      const workspaceId = companionWorkspaceIdRef.current;
      if (!workspaceId) return false;
      const found = await findConversationInHistory(workspaceId, conversationId);
      if (!found) return false;

      const activeKey = localWorkspaceRef.current
        ? normalizeWorkspaceKey(localWorkspaceRef.current.path)
        : null;
      if (found.workspaceKey !== activeKey) {
        const activated = await activateRecentWorkspace(workspaceId, found.workspaceKey);
        if (!activated.workspace) return false;
        localWorkspaceRef.current = activated.workspace;
        setLocalWorkspace(activated.workspace);
        setRecentWorkspaces(activated.recent);
        skipInitialHistorySave.current = true;
        const loaded = await loadConversationHistory(workspaceId, found.workspaceKey);
        setConversations(loaded.conversations);
        setFolderHistoryByKey((current) => ({
          ...current,
          [found.workspaceKey]: loaded.conversations,
        }));
      }
      ensureFolderExpanded(found.workspaceKey);
      setConversationId(found.conversation.id);
      setThreadTitle(found.conversation.title);
      setContextServices(
        found.conversation.contextServices?.length
          ? found.conversation.contextServices
          : found.conversation.serviceId !== "workspace"
            ? [{ id: found.conversation.serviceId, name: found.conversation.serviceId }]
            : [],
      );
      setContextFiles([]);
      setMessages(found.conversation.messages);
      setOrchestratorRun(found.conversation.orchestratorRun);
      setError("");
      setChatMenuOpen(false);
      rememberConversationForResume(found.conversation.id);
      return true;
    }

    async function applyRoute(route: AppRoute, options?: { allowResume?: boolean }) {
      if (route.kind === "settings") {
        setActiveNav("Settings");
        setMobileNavOpen(false);
        return;
      }

      setActiveNav("New Chat");
      setMobileNavOpen(false);

      if (!route.conversationId) {
        const prefs = uiPreferencesRef.current;
        const resumeId =
          options?.allowResume && prefs.resumeConversationOnRefresh
            ? prefs.lastConversationId
            : null;
        if (resumeId && (await restoreConversationFromRoute(resumeId))) {
          syncRoute({ kind: "chat", conversationId: resumeId }, "replace");
          return;
        }
        setConversationId(id());
        setMessages([]);
        setOrchestratorRun(null);
        setDraft("");
        setError("");
        return;
      }

      if (route.conversationId === conversationIdRef.current) return;

      if (!(await restoreConversationFromRoute(route.conversationId))) {
        navigateAppRoute({ kind: "chat", conversationId: null }, "replace");
        setConversationId(id());
        setMessages([]);
        setOrchestratorRun(null);
      }
    }

    if (!persistHydratedRef.current || !companionWorkspaceId) return;

    if (!routeHydratedRef.current) {
      routeHydratedRef.current = true;
      void applyRoute(parseAppRoute(window.location.pathname), { allowResume: true });
    }

    function onPopState() {
      void applyRoute(parseAppRoute(window.location.pathname));
    }
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, [companionWorkspaceId]);

  useEffect(() => {
    if (!historyCanBeSaved || !workspaceKey || !companionWorkspaceId) return;
    if (skipInitialHistorySave.current) {
      skipInitialHistorySave.current = false;
      return;
    }

    const workspaceId = companionWorkspaceId;
    const key = workspaceKey;
    let cancelled = false;
    void (async () => {
      const saveError = await saveConversationHistory(workspaceId, key, conversations);
      if (cancelled) return;
      setHistoryNotice(saveError);
      if (!saveError) {
        setFolderHistoryByKey((current) => ({
          ...current,
          [key]: conversations,
        }));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [conversations, historyCanBeSaved, workspaceKey, companionWorkspaceId]);

  function resetActiveThread(options?: { syncUrl?: boolean; mode?: "push" | "replace" }) {
    setConversationId(id());
    setMessages([]);
    setOrchestratorRun(null);
    setDraft("");
    setError("");
    setContextServices([]);
    setContextFiles([]);
    setAttachOpen(false);
    setAttachPanel("menu");
    setThreadTitle(null);
    setChatMenuOpen(false);
    setRenameDialogOpen(false);
    setDeleteDialogOpen(false);
    rememberConversationForResume(null);
    if (options?.syncUrl !== false) {
      syncRoute({ kind: "chat", conversationId: null }, options?.mode ?? "push");
    }
  }

  function openRenameDialog() {
    setChatMenuOpen(false);
    setTitleDraft(currentTitle ?? "");
    setRenameDialogOpen(true);
  }

  function openDeleteDialog() {
    setChatMenuOpen(false);
    setDeleteDialogOpen(true);
  }

  async function applyRenameTitle() {
    const nextTitle = titleDraft.trim();
    if (!nextTitle) return;
    setThreadTitle(nextTitle);
    setConversations((current) => {
      const existing = current.find((item) => item.id === activeConversationId);
      if (!existing) {
        if (!messages.some((message) => message.role === "user")) return current;
        return [
          {
            id: activeConversationId,
            title: nextTitle,
            serviceId: primaryContextService ?? "workspace",
            contextServices,
            messages: [...messages],
            updatedAt: new Date().toISOString(),
            orchestratorRun,
          },
          ...current,
        ].slice(0, 8);
      }
      return current.map((item) =>
        item.id === activeConversationId
          ? { ...item, title: nextTitle, updatedAt: new Date().toISOString() }
          : item,
      );
    });
    setRenameDialogOpen(false);
  }

  async function confirmDeleteConversation() {
    const workspaceId = companionWorkspaceIdRef.current;
    const key = workspaceKey;
    const targetId = activeConversationId;
    const next = conversations.filter((item) => item.id !== targetId);
    setConversations(next);
    if (key) {
      setFolderHistoryByKey((current) => ({ ...current, [key]: next }));
      if (historyCanBeSaved && workspaceId) {
        const saveError = await saveConversationHistory(workspaceId, key, next);
        if (saveError) setHistoryNotice(saveError);
      }
    }
    setDeleteDialogOpen(false);
    resetActiveThread({ mode: "replace" });
  }

  function addContextService(service: ContextService) {
    setContextServices((current) => {
      if (current.some((item) => item.id === service.id)) return current;
      return [...current, service].slice(0, 8);
    });
  }

  function removeContextService(serviceId: string) {
    setContextServices((current) => current.filter((item) => item.id !== serviceId));
  }

  function removeContextFile(path: string) {
    setContextFiles((current) => current.filter((item) => item !== path));
  }

  async function pickContextFile() {
    if (pickingFile) return;
    setPickingFile(true);
    setAttachOpen(false);
    setAttachPanel("menu");
    try {
      const result = await pickLocalPath("file");
      if (result.cancelled || !result.path) return;
      setContextFiles((current) =>
        current.includes(result.path!) ? current : [...current, result.path!].slice(0, 6),
      );
    } catch (cause: unknown) {
      const message =
        cause instanceof Error
          ? cause.message
          : language === "fa"
            ? "انتخاب فایل ممکن نشد."
            : "Could not open the file picker.";
      setError(message);
    } finally {
      setPickingFile(false);
    }
  }

  function buildGoalWithContext(prompt: string): string {
    if (contextFiles.length === 0) return prompt;
    const files =
      language === "fa"
        ? `فایل‌های زمینه: ${contextFiles.join("، ")}`
        : `Context files: ${contextFiles.join(", ")}`;
    return `${prompt}\n\n${files}`;
  }

  async function flushConversationsForKey(
    key: string | null,
    list: Conversation[],
    includeCurrent: boolean,
  ): Promise<Conversation[]> {
    let next = list;
    if (includeCurrent) {
      const auto =
        messages.length >= 3
          ? (messages.find((message) => message.role === "user")?.text || "").trim().slice(0, 56)
          : "";
      const title = (threadTitle?.trim() || auto || "").trim();
      if (title) {
        const currentConversation: Conversation = {
          id: conversationIdRef.current,
          title,
          serviceId: primaryContextService ?? "workspace",
          contextServices,
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
    const workspaceId = companionWorkspaceIdRef.current;
    if (key && historyCanBeSaved && workspaceId) {
      const saveError = await saveConversationHistory(workspaceId, key, next);
      if (saveError) setHistoryNotice(saveError);
      else {
        setFolderHistoryByKey((current) => ({ ...current, [key]: next }));
      }
    }
    return next;
  }

  async function applyLocalWorkspace(next: LocalWorkspace) {
    const workspaceId = companionWorkspaceIdRef.current;
    if (!workspaceId) {
      setError(
        language === "fa"
          ? "فضای کار همراه هنوز آماده نیست. چند لحظه صبر کنید."
          : "Companion workspace is not ready yet.",
      );
      return;
    }

    const previous = localWorkspaceRef.current;
    const previousKey = previous ? normalizeWorkspaceKey(previous.path) : null;
    const nextKey = normalizeWorkspaceKey(next.path);
    if (!nextKey) {
      setError(strings.folderGateError);
      return;
    }

    try {
      if (previousKey && previousKey !== nextKey) {
        await flushConversationsForKey(previousKey, conversations, true);
      }

      const saved = await saveLocalWorkspace(workspaceId, next);
      if (saved.error || !saved.workspace) {
        setHistoryNotice(saved.error ?? strings.folderGateError);
        return;
      }

      setLocalWorkspace(saved.workspace);
      localWorkspaceRef.current = saved.workspace;
      setRecentWorkspaces(saved.recent);
      ensureFolderExpanded(nextKey);

      if (!previousKey || previousKey !== nextKey) {
        skipInitialHistorySave.current = true;
        const loaded = await loadConversationHistory(workspaceId, nextKey);
        setConversations(loaded.conversations);
        setFolderHistoryByKey((current) => ({
          ...current,
          [nextKey]: loaded.conversations,
        }));
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
    const workspaceId = companionWorkspaceIdRef.current;
    if (!workspaceId) {
      setHistoryNotice(strings.folderGateError);
      return;
    }
    void (async () => {
      const activated = await activateRecentWorkspace(workspaceId, path);
      if (activated.error || !activated.workspace) {
        setHistoryNotice(activated.error ?? strings.folderGateError);
        return;
      }
      await applyLocalWorkspace(activated.workspace);
    })();
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
        void applyLocalWorkspace({
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
    const goal = buildGoalWithContext(prompt);
    setActiveNav("New Chat");
    setError("");
    setLoading(true);
    setOrchestratorRun(null);
    setAttachOpen(false);
    if (options?.prependUser !== false) {
      setMessages((current) => [...current, { id: id(), role: "user", text: prompt }]);
    }

    try {
      const appPath = localWorkspaceRef.current?.path ?? null;
      const created = await createCase(workspaceId, goal);
      let run: OrchestratorRun = {
        case_id: created.id,
        workspace_id: workspaceId,
        goal,
        stage: "assessing",
        // Inspector timeline is request-derived; chat bubbles stay quiet (02).
        summary: language === "fa" ? "در حال آماده‌سازی پاسخ…" : "Preparing a reply…",
        timeline: buildRequestTimeline({
          language,
          goal,
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
          goal,
          stage: "planning",
          readiness,
        }),
        events: [...run.events, stamp("assess_readiness")],
      };
      setOrchestratorRun(run);

      // Context service skips intake when present; otherwise GenUI asks for it.
      const route = resolveChallengeLoopRoute(goal, {
        selectedServiceId: primaryContextService,
      });

      if (route.mode === "troubleshoot") {
        await runTroubleshootLoop({
          workspaceId,
          caseId: created.id,
          goal,
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
          goal,
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
            goal,
            stage: "verified",
            readiness,
            operationState: "conversation",
          }),
          events: [...run.events, stamp("conversation_reply")],
        };
        setOrchestratorRun(next);
        setMessages((current) => [
          ...current,
          {
            id: id(),
            role: "assistant",
            text: reply,
            ...withQuickReplies(whatNextReplies(language)),
          },
        ]);
        return;
      }

      if (route.mode === "intake") {
        await pauseForIntake({
          workspaceId,
          goal,
          intakeKind: route.intakeKind,
          readiness,
          priorRun: run,
        });
        return;
      }

      await finalizePlanFromIntake({
        workspaceId,
        caseId: created.id,
        goal,
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
          price_monthly: plan.price_monthly ?? null,
          ram_gb: plan.ram_gb ?? null,
          tier: plan.tier,
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

    const suggestedPlatform = req.require_platform
      ? suggestLiaraPlatform({
          readinessPlatform: args.readiness?.platform,
        }).id
      : null;
    const suggestedServiceName = req.prefer_new_service
      ? suggestServiceNameFromPackage(
          args.readiness?.package_name,
          localWorkspaceRef.current?.path,
        )
      : null;

    const intakeText = intakeAssistantPrompt(args.intakeKind, language);
    const next: OrchestratorRun = {
      ...args.priorRun,
      stage: "awaiting_intake",
      intake: {
        kind: args.intakeKind,
        services: intakeServices,
        plans: intakePlans,
        platforms: req.require_platform ? enrichPlatformOptions(LIARA_PLATFORMS) : [],
        require_plan: req.require_plan,
        require_domain: req.require_domain,
        require_platform: req.require_platform,
        suggested_platform: suggestedPlatform,
        suggested_service_name: suggestedServiceName,
        prefer_new_service: req.prefer_new_service,
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
    // Only one-tap service chips when GenUI needs no plan/domain fields.
    const serviceOnly = !req.require_plan && !req.require_domain;
    const quickReplies = loadError
      ? [settingsReply(language)]
      : serviceOnly && intakeServices.length > 0
        ? intakeServiceReplies(intakeServices, language)
        : undefined;
    setMessages((current) => [
      ...current,
      {
        id: id(),
        role: "assistant",
        text: intakeText,
        // Service chips are intake shortcuts; no “what next” while GenUI waits.
        ...withQuickReplies(quickReplies),
      },
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

    const fixChips = fixOptionReplies(fixOptions.options);
    if (fixChips.length > 0) {
      const assistantText =
        language === "fa"
          ? `${diagnosis.summary?.trim() || "تشخیص آماده است."} یکی از گزینه‌های زیر را انتخاب کنید تا طرح پیشنهادی ساخته شود — اجرا فقط بعد از تأیید.`
          : `${diagnosis.summary?.trim() || "Diagnosis ready."} Pick an option below to draft a plan — nothing runs until you Approve.`;
      const next: OrchestratorRun = {
        ...run,
        stage: "planning",
        summary: assistantText,
        timeline: buildRequestTimeline({
          language,
          goal: args.goal,
          stage: "planning",
          readiness: args.readiness,
        }),
        events: [...run.events, stamp("await_fix_choice")],
      };
      setOrchestratorRun(next);
      setMessages((current) => [
        ...current,
        {
          id: id(),
          role: "assistant",
          text: assistantText,
          ...withQuickReplies(fixChips),
        },
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
      {
        id: id(),
        role: "assistant",
        text: summary,
        ...withQuickReplies(
          diagnosisFollowUpReplies(language, diagnosis.next_read_or_question),
        ),
      },
    ]);
  }

  async function selectFixOption(optionId: string) {
    if (!orchestratorRun || loading || approvalBusy) return;
    if (!orchestratorRun.fix_options?.options.some((option) => option.id === optionId && option.enabled)) {
      return;
    }
    setLoading(true);
    setError("");
    clearLatestQuickReplies();
    try {
      const plan = await createPlanFromFix({
        workspaceId: orchestratorRun.workspace_id,
        caseId: orchestratorRun.case_id,
        optionId,
      });
      const assistantText = planReadyAssistantText(
        language,
        orchestratorRun.diagnosis?.summary ?? plan.body.summary,
      );
      const next: OrchestratorRun = {
        ...orchestratorRun,
        stage: "awaiting_approval",
        plan_id: plan.plan_id,
        plan_version: plan.version,
        content_hash: plan.content_hash,
        plan_body: plan.body,
        summary: assistantText,
        timeline: buildRequestTimeline({
          language,
          goal: orchestratorRun.goal,
          stage: "awaiting_approval",
          planBody: plan.body,
          readiness: orchestratorRun.readiness,
        }),
        events: [...orchestratorRun.events, stamp("create_plan_from_fix")],
      };
      setOrchestratorRun(next);
      // HITL lives on the generative approval card — no duplicate chips / “what next”.
      setMessages((current) => [
        ...current,
        {
          id: id(),
          role: "assistant",
          text: assistantText,
        },
      ]);
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : "Could not draft a fix plan.";
      setError(message);
      setMessages((current) => [
        ...current,
        {
          id: id(),
          role: "assistant",
          text:
            language === "fa"
              ? `ساخت طرح اصلاح ناموفق بود: ${message}`
              : `Could not draft the fix plan: ${message}`,
        },
      ]);
    } finally {
      setLoading(false);
    }
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
      {
        id: id(),
        role: "assistant",
        text: summary,
        ...withQuickReplies(verifiedFollowUpReplies(language)),
      },
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
    // Plan + Approve/Reject are on the GenUI card; plain text only here.
    setMessages((current) => [
      ...current,
      {
        id: id(),
        role: "assistant",
        text: assistantText,
      },
    ]);
  }

  function clearLatestQuickReplies() {
    setMessages((current) => {
      for (let index = current.length - 1; index >= 0; index -= 1) {
        const message = current[index];
        if (message?.role === "assistant" && message.quickReplies?.length) {
          const next = [...current];
          next[index] = { ...message, quickReplies: undefined };
          return next;
        }
      }
      return current;
    });
  }

  async function handleQuickReply(reply: QuickReply) {
    if (loading || approvalBusy) return;
    clearLatestQuickReplies();
    if (reply.kind === "prompt" && reply.prompt) {
      await startOrchestratorGoal(reply.prompt);
      return;
    }
    if (reply.kind === "approve") {
      await decideApproval("approve");
      return;
    }
    if (reply.kind === "reject") {
      await decideApproval("reject");
      return;
    }
    if (reply.kind === "settings") {
      navigate("Settings");
      return;
    }
    if (reply.kind === "fix" && reply.value) {
      await selectFixOption(reply.value);
      return;
    }
    if (reply.kind === "intake_service" && reply.value) {
      await confirmIntake({ project_name: reply.value });
    }
  }

  async function confirmIntake(values: IntakeConfirmValues) {
    if (!orchestratorRun || orchestratorRun.stage !== "awaiting_intake" || loading || approvalBusy) {
      return;
    }
    if (!orchestratorRun.intake) return;

    setLoading(true);
    setError("");
    setActiveNav("New Chat");
    clearLatestQuickReplies();
    if (values.project_name.trim()) {
      addContextService({
        id: values.project_name.trim(),
        name: values.project_name.trim(),
      });
    }

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
        platform: values.platform,
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
      clearLatestQuickReplies();
      setMessages((current) => [
        ...current,
        {
          id: id(),
          role: "assistant",
          text: rejected.summary,
          ...withQuickReplies(whatNextReplies(language)),
        },
      ]);
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
      clearLatestQuickReplies();
      setMessages((current) => [
        ...current,
        {
          id: id(),
          role: "assistant",
          text: doneSummary,
          ...withQuickReplies(verifiedFollowUpReplies(language)),
        },
      ]);
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
      const needsSettings = /token|Settings|configure|workspace|Liara|Aval/i.test(message);
      setMessages((current) => [
        ...current,
        {
          id: id(),
          role: "assistant",
          text: language === "fa" ? `تأیید/اجرا ناموفق: ${message}` : `Approve/execute failed: ${message}`,
          ...(needsSettings ? withQuickReplies([settingsReply(language)]) : {}),
        },
      ]);
    } finally {
      setApprovalBusy(false);
    }
  }

  function archiveCurrentConversation() {
    if (!hasLocalWorkspace) return;
    const auto =
      messages.length >= 3
        ? (messages.find((message) => message.role === "user")?.text || "").trim().slice(0, 56)
        : "";
    const title = (threadTitle?.trim() || auto || "").trim();
    if (!title) return;
    const conversation: Conversation = {
      id: conversationIdRef.current,
      title,
      serviceId: primaryContextService ?? "workspace",
      contextServices,
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
    void (async () => {
      const workspaceId = companionWorkspaceIdRef.current;
      if (folderKey && folderKey !== workspaceKey && workspaceId) {
        const folder = recentWorkspaces.find(
          (item) => normalizeWorkspaceKey(item.path) === folderKey,
        );
        if (folder) {
          const previous = localWorkspaceRef.current;
          const previousKey = previous ? normalizeWorkspaceKey(previous.path) : null;
          if (previousKey && previousKey !== folderKey) {
            await flushConversationsForKey(previousKey, conversations, true);
          }
          const activated = await activateRecentWorkspace(workspaceId, folder.path);
          if (activated.workspace) {
            localWorkspaceRef.current = activated.workspace;
            setLocalWorkspace(activated.workspace);
            setRecentWorkspaces(activated.recent);
            skipInitialHistorySave.current = true;
            const loaded = await loadConversationHistory(workspaceId, folderKey);
            setConversations(loaded.conversations);
            setFolderHistoryByKey((current) => ({
              ...current,
              [folderKey]: loaded.conversations,
            }));
          }
        }
        ensureFolderExpanded(folderKey);
      }

      if (conversation.id === conversationIdRef.current) {
        setActiveNav("New Chat");
        setMobileNavOpen(false);
        syncRoute({ kind: "chat", conversationId: conversation.id });
        rememberConversationForResume(conversation.id);
        return;
      }
      archiveCurrentConversation();
      setConversationId(conversation.id);
      setThreadTitle(conversation.title);
      setChatMenuOpen(false);
      setContextServices(
        conversation.contextServices?.length
          ? conversation.contextServices
          : conversation.serviceId !== "workspace"
            ? [{ id: conversation.serviceId, name: conversation.serviceId }]
            : [],
      );
      setContextFiles([]);
      setMessages(conversation.messages);
      setOrchestratorRun(conversation.orchestratorRun);
      setActiveNav("New Chat");
      setMobileNavOpen(false);
      setError("");
      syncRoute({ kind: "chat", conversationId: conversation.id });
      rememberConversationForResume(conversation.id);
    })();
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
            <div className="flex min-w-0 flex-1 items-center gap-2">
              <span className="topbar-spark"><Sparkles size={14} /></span>
              <span className="truncate text-sm font-medium text-slate-200">
                {orchestratorRun
                  ? (orchestratorRun.goal.split("\n")[0]?.slice(0, 48) || strings.workspace)
                  : (localWorkspace?.displayName ?? strings.workspace)}
              </span>
              <span className="topbar-separator" />
              {contextServices.length > 0 ? (
                <div className="topbar-services" aria-label="سرویس‌های زمینه">
                  {contextServices.map((service) => (
                    <a
                      key={service.id}
                      className="topbar-service-chip"
                      href={liaraServiceConsoleUrl(service.name)}
                      target="_blank"
                      rel="noreferrer"
                      title={service.name}
                    >
                      <Server size={11} />
                      <span>{service.name}</span>
                      <ExternalLink size={10} />
                    </a>
                  ))}
                </div>
              ) : (
                <span className="topbar-context-empty">{strings.noContextService}</span>
              )}
            </div>
            <div className="logical-end flex items-center gap-2">
              <div className="chat-menu-wrap" ref={chatMenuRef}>
                <button
                  type="button"
                  className="icon-button"
                  aria-label={strings.chatOptions}
                  aria-expanded={chatMenuOpen}
                  aria-haspopup="menu"
                  disabled={!hasLocalWorkspace}
                  onClick={() => setChatMenuOpen((open) => !open)}
                >
                  <MoreHorizontal size={18} />
                </button>
                {chatMenuOpen && (
                  <div className="chat-menu-popover" role="menu" aria-label={strings.chatOptions}>
                    <button
                      type="button"
                      className="chat-menu-item"
                      role="menuitem"
                      disabled={!canManageThread}
                      onClick={openRenameDialog}
                    >
                      <Pencil size={14} />
                      <span>{strings.renameChat}</span>
                    </button>
                    <button
                      type="button"
                      className="chat-menu-item danger"
                      role="menuitem"
                      disabled={!canManageThread}
                      onClick={openDeleteDialog}
                    >
                      <Trash2 size={14} />
                      <span>{strings.deleteChat}</span>
                    </button>
                  </div>
                )}
              </div>
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
                {messages.map((message, messageIndex) => {
                  const awaitingGen = generativeAwaitingUser(orchestratorRun?.stage);
                  const visibleReplies = (message.quickReplies ?? []).filter((reply) => {
                    // While GenUI owns the turn, keep only chips that drive that surface
                    // (service / fix). Hide “what next” prompts until the final plain message.
                    if (!awaitingGen) return true;
                    return (
                      reply.kind === "fix" ||
                      reply.kind === "intake_service" ||
                      reply.kind === "settings"
                    );
                  });
                  const showQuickReplies =
                    uiPreferences.quickRepliesEnabled &&
                    message.role === "assistant" &&
                    messageIndex === lastAssistantMessageIndex &&
                    visibleReplies.length > 0 &&
                    !loading &&
                    !approvalBusy;
                  return (
                    <div className={`message-row ${message.role}`} key={message.id}>
                      <div className={message.role === "assistant" ? "assistant-avatar" : "user-avatar"}>
                        {message.role === "assistant" ? <Sparkles size={14} /> : "ش"}
                      </div>
                      <div className="message-stack">
                        <div className="message-meta">
                          <span>{message.role === "assistant" ? "همراه لیارا" : "شما"}</span>
                          {message.kind === "demo" && <span className="message-demo">SIMULATED</span>}
                        </div>
                        <div className="message-bubble">
                          <p className="message-text">{message.text}</p>
                        </div>
                        {showQuickReplies ? (
                          <div className="quick-replies" role="group" aria-label="پاسخ سریع">
                            {visibleReplies.map((reply) => (
                              <button
                                key={reply.id}
                                type="button"
                                className={`quick-reply ${
                                  reply.kind === "approve"
                                    ? "quick-reply-primary"
                                    : reply.kind === "reject"
                                      ? "quick-reply-danger"
                                      : ""
                                }`}
                                onClick={() => void handleQuickReply(reply)}
                              >
                                {reply.label}
                              </button>
                            ))}
                          </div>
                        ) : null}
                      </div>
                    </div>
                  );
                })}
                {loading && (
                  <div className="message-row assistant">
                    <div className="assistant-avatar"><Sparkles size={14} /></div>
                    <div className="message-stack">
                      <div className="message-meta">
                        <span>همراه لیارا</span>
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
            {(contextFiles.length > 0 || contextServices.length > 0) && (
              <div className="composer-context-chips">
                {contextServices.map((service) => (
                  <span className="composer-chip" key={`svc-${service.id}`}>
                    <Server size={12} />
                    <span>{service.name}</span>
                    <button
                      type="button"
                      aria-label={`حذف ${service.name}`}
                      onClick={() => removeContextService(service.id)}
                    >
                      <X size={11} />
                    </button>
                  </span>
                ))}
                {contextFiles.map((path) => (
                  <span className="composer-chip" key={path} title={path}>
                    <FilePlus2 size={12} />
                    <span>{path.split(/[/\\]/).filter(Boolean).pop() || path}</span>
                    <button
                      type="button"
                      aria-label="حذف فایل"
                      onClick={() => removeContextFile(path)}
                    >
                      <X size={11} />
                    </button>
                  </span>
                ))}
              </div>
            )}
            <form className="composer" onSubmit={handleSubmit}>
              <div className="composer-attach-wrap" ref={attachWrapRef}>
                <button
                  className={`composer-plus ${attachOpen ? "active" : ""}`}
                  type="button"
                  aria-label={strings.attachMenu}
                  aria-expanded={attachOpen}
                  aria-haspopup="menu"
                  disabled={!hasLocalWorkspace || pickingFile}
                  onClick={() => {
                    setAttachOpen((open) => !open);
                    setAttachPanel("menu");
                  }}
                >
                  <Plus size={17} />
                </button>
                {attachOpen && (
                  <div className="composer-attach-popover" role="menu" aria-label={strings.attachMenu}>
                    {attachPanel === "menu" ? (
                      <>
                        <div className="composer-attach-label">{strings.attachSkills}</div>
                        {composerSkills(language).map((skill) => {
                          const SkillIcon =
                            skill.id === "logs-24h"
                              ? ClipboardList
                              : skill.id === "debug"
                                ? Bug
                                : Rocket;
                          return (
                            <button
                              key={skill.id}
                              type="button"
                              className="composer-attach-item"
                              role="menuitem"
                              onClick={() => {
                                setAttachOpen(false);
                                void startOrchestratorGoal(skill.prompt);
                              }}
                            >
                              <SkillIcon size={14} />
                              <span>
                                <strong>{skill.label}</strong>
                                <small>{skill.hint}</small>
                              </span>
                            </button>
                          );
                        })}
                        <div className="composer-attach-divider" />
                        <button
                          type="button"
                          className="composer-attach-item"
                          role="menuitem"
                          disabled={pickingFile}
                          onClick={() => void pickContextFile()}
                        >
                          <FilePlus2 size={14} />
                          <span>
                            <strong>{pickingFile ? strings.pickingFile : strings.attachFile}</strong>
                            <small>{language === "fa" ? "افزودن مسیر فایل به زمینه" : "Add a local file path"}</small>
                          </span>
                        </button>
                        <button
                          type="button"
                          className="composer-attach-item"
                          role="menuitem"
                          onClick={() => setAttachPanel("services")}
                        >
                          <Server size={14} />
                          <span>
                            <strong>{strings.attachService}</strong>
                            <small>
                              {language === "fa"
                                ? "برای زمینه این گفتگو"
                                : "Attach to this chat context"}
                            </small>
                          </span>
                        </button>
                      </>
                    ) : (
                      <>
                        <button
                          type="button"
                          className="composer-attach-back"
                          onClick={() => setAttachPanel("menu")}
                        >
                          {strings.attachBack}
                        </button>
                        <div className="composer-attach-label">{strings.attachService}</div>
                        {services.length === 0 ? (
                          <p className="composer-attach-empty">{strings.noServices}</p>
                        ) : (
                          services.map((service) => {
                            const active = contextServices.some((item) => item.id === service.id);
                            return (
                              <button
                                key={service.id}
                                type="button"
                                className={`composer-attach-item ${active ? "active" : ""}`}
                                role="menuitem"
                                onClick={() => {
                                  addContextService({ id: service.id, name: service.name });
                                  setAttachOpen(false);
                                  setAttachPanel("menu");
                                }}
                              >
                                <Server size={14} />
                                <span>
                                  <strong>{service.name}</strong>
                                  <small>{service.status}</small>
                                </span>
                              </button>
                            );
                          })
                        )}
                      </>
                    )}
                  </div>
                )}
              </div>
              <input
                aria-label="پیام به همراه لیارا"
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                placeholder={hasLocalWorkspace ? strings.prompt : strings.pickFolderPrompt}
                disabled={loading || !hasLocalWorkspace}
              />
              <div className="composer-actions">
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
          uiPreferences={uiPreferences}
          onUiPreferencesChange={setUiPreferences}
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
          addContextService({ id: service.id, name: service.name });
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
      <AnimatePresence>
        {renameDialogOpen && (
          <motion.div
            className="confirm-scrim"
            role="presentation"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setRenameDialogOpen(false)}
          >
            <motion.div
              className="confirm-dialog rename"
              role="dialog"
              aria-modal="true"
              aria-labelledby="rename-dialog-title"
              initial={{ opacity: 0, y: 12, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 8, scale: 0.98 }}
              transition={{ duration: 0.2, ease: [0.22, 0.75, 0.28, 1] }}
              onClick={(event) => event.stopPropagation()}
            >
              <div className="confirm-dialog-icon" aria-hidden><Pencil size={18} /></div>
              <h2 id="rename-dialog-title">{strings.renameTitleHeading}</h2>
              <p>{strings.renameTitleBody}</p>
              <input
                autoFocus
                value={titleDraft}
                onChange={(event) => setTitleDraft(event.target.value)}
                placeholder={strings.titlePlaceholder}
                aria-label={strings.titlePlaceholder}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    void applyRenameTitle();
                  }
                }}
              />
              <div className="confirm-actions">
                <button type="button" className="confirm-btn ghost" onClick={() => setRenameDialogOpen(false)}>
                  {strings.cancel}
                </button>
                <button
                  type="button"
                  className="confirm-btn primary"
                  disabled={!titleDraft.trim()}
                  onClick={() => void applyRenameTitle()}
                >
                  {strings.renameTitleSave}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
      <AnimatePresence>
        {deleteDialogOpen && (
          <motion.div
            className="confirm-scrim"
            role="presentation"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setDeleteDialogOpen(false)}
          >
            <motion.div
              className="confirm-dialog"
              role="dialog"
              aria-modal="true"
              aria-labelledby="delete-dialog-title"
              initial={{ opacity: 0, y: 12, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 8, scale: 0.98 }}
              transition={{ duration: 0.2, ease: [0.22, 0.75, 0.28, 1] }}
              onClick={(event) => event.stopPropagation()}
            >
              <div className="confirm-dialog-icon" aria-hidden><Trash2 size={18} /></div>
              <h2 id="delete-dialog-title">{strings.deleteConfirmHeading}</h2>
              <p>
                {strings.deleteConfirmBody}
                {currentTitle ? ` «${currentTitle}»` : ""}
              </p>
              <div className="confirm-actions">
                <button type="button" className="confirm-btn ghost" onClick={() => setDeleteDialogOpen(false)}>
                  {strings.cancel}
                </button>
                <button
                  type="button"
                  className="confirm-btn danger"
                  onClick={() => void confirmDeleteConversation()}
                >
                  {strings.deleteConfirmAction}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
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
          <SidebarWalletBalances
            workspaceId={companionWorkspaceId}
            refreshKey={[
              settingsView?.liara.token_configured ? "1" : "0",
              settingsView?.aval.api_key_configured ? "1" : "0",
              settingsView?.liara.team_id ?? "",
            ].join(":")}
          />
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
