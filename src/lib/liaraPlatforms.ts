/**
 * Liara PaaS platforms (cli AVAILABLE_PLATFORMS) + icons from
 * github.com/liara-cloud/platformicons (bundled via Vite).
 */

export type LiaraPlatformOption = {
  id: string;
  label: string;
  hint?: string;
  /** Vite-resolved URL to platform SVG. */
  icon: string;
};

/** Eager URL map: `node.svg` → `/assets/node-xxxxx.svg` */
const iconModules = import.meta.glob("../assets/platform-icons/*.svg", {
  eager: true,
  import: "default",
  query: "?url",
}) as Record<string, string>;

function iconUrl(file: string): string {
  const key = `../assets/platform-icons/${file}`;
  const url = iconModules[key];
  if (!url) {
    // Fallback to public/ copy if glob miss
    return `/platform-icons/${file}`;
  }
  return url;
}

/** Same ids as liara-cli `AVAILABLE_PLATFORMS`. */
export const LIARA_PLATFORMS: LiaraPlatformOption[] = [
  { id: "node", label: "NodeJS", hint: "Express / Nest / plain Node", icon: iconUrl("node.svg") },
  { id: "next", label: "NextJS", hint: "SSR / App Router", icon: iconUrl("next.svg") },
  { id: "laravel", label: "Laravel", icon: iconUrl("laravel.svg") },
  { id: "php", label: "PHP", icon: iconUrl("php.svg") },
  { id: "python", label: "Python", icon: iconUrl("python.svg") },
  { id: "django", label: "Django", icon: iconUrl("django.svg") },
  { id: "flask", label: "Flask", icon: iconUrl("flask.svg") },
  { id: "dotnet", label: ".NET", icon: iconUrl("dotnet.svg") },
  { id: "react", label: "React", hint: "Static export", icon: iconUrl("react.svg") },
  { id: "angular", label: "Angular", icon: iconUrl("angular.svg") },
  { id: "vue", label: "Vue", icon: iconUrl("vue.svg") },
  { id: "static", label: "Static", hint: "HTML / built assets", icon: iconUrl("static.svg") },
  { id: "docker", label: "Docker", icon: iconUrl("docker.svg") },
  { id: "go", label: "Go", icon: iconUrl("go.svg") },
];

const byId = new Map(LIARA_PLATFORMS.map((row) => [row.id, row]));

/** Always attach catalog icon (and label) so GenUI never renders empty tiles. */
export function enrichPlatformOptions(
  rows: Array<{ id: string; label?: string; hint?: string | null; icon?: string | null }> | null | undefined,
): LiaraPlatformOption[] {
  if (!rows || rows.length === 0) {
    return LIARA_PLATFORMS.map((row) => ({ ...row }));
  }
  return rows.map((row) => {
    const catalog = byId.get(row.id);
    return {
      id: row.id,
      label: row.label || catalog?.label || row.id,
      hint: row.hint ?? catalog?.hint,
      icon: row.icon || catalog?.icon || iconUrl(`${row.id}.svg`),
    };
  });
}

export function suggestLiaraPlatform(args: {
  readinessPlatform?: string | null;
}): { id: string; reason: "readiness" | "default" } {
  const raw = (args.readinessPlatform || "").toLowerCase().trim();
  if (raw === "next" || raw === "nextjs") {
    return { id: "next", reason: "readiness" };
  }
  if (raw === "nodejs" || raw === "node") {
    return { id: "node", reason: "readiness" };
  }
  if (raw === "static") {
    return { id: "static", reason: "readiness" };
  }
  if (raw && byId.has(raw)) {
    return { id: raw, reason: "readiness" };
  }
  return { id: "node", reason: "default" };
}

export function suggestServiceNameFromPath(appPath: string | null | undefined): string {
  if (!appPath) return "";
  const base = appPath.split(/[/\\]/).filter(Boolean).pop() || "";
  return sanitizeServiceName(base);
}

export function suggestServiceNameFromPackage(
  packageName: string | null | undefined,
  appPath?: string | null,
): string {
  const fromPkg = sanitizeServiceName((packageName || "").replace(/^@[^/]+\//, ""));
  if (fromPkg) return fromPkg;
  return suggestServiceNameFromPath(appPath);
}

function sanitizeServiceName(raw: string): string {
  return raw
    .toLowerCase()
    .replace(/[^a-z0-9-]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 32);
}
