export type AppRoute =
  | { kind: "chat"; conversationId: string | null }
  | { kind: "settings" };

const CHAT_RE = /^\/chat(?:\/([^/]+))?\/?$/;
const SETTINGS_RE = /^\/settings\/?$/;

export function parseAppRoute(pathname: string): AppRoute {
  const path = pathname.replace(/\/+$/, "") || "/";
  if (SETTINGS_RE.test(path) || path === "/settings") {
    return { kind: "settings" };
  }
  const chat = path.match(CHAT_RE);
  if (chat) {
    const id = chat[1] && chat[1] !== "new" ? decodeURIComponent(chat[1]) : null;
    return { kind: "chat", conversationId: id };
  }
  if (path === "/" || path === "") {
    return { kind: "chat", conversationId: null };
  }
  return { kind: "chat", conversationId: null };
}

export function appRoutePath(route: AppRoute): string {
  if (route.kind === "settings") return "/settings";
  if (route.conversationId) return `/chat/${encodeURIComponent(route.conversationId)}`;
  return "/";
}

export function navigateAppRoute(route: AppRoute, mode: "push" | "replace" = "push"): void {
  const next = appRoutePath(route);
  if (typeof window === "undefined") return;
  if (window.location.pathname === next) return;
  if (mode === "replace") {
    window.history.replaceState(null, "", next);
  } else {
    window.history.pushState(null, "", next);
  }
}
