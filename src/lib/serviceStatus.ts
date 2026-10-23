/** Sidebar / catalog status → visual tone (account-scoped services). */

export type ServiceStatusTone = "online" | "error" | "stopped" | "unknown";

const ONLINE_RE = /\b(RUNNING|STARTED|READY|ACTIVE)\b/i;
const ERROR_RE = /\b(FAILED|ERROR|CRASH(?:ED)?)\b/i;
const STOPPED_RE = /\bSTOPPED\b/i;

/**
 * Map Liara project `status` (and optional `isDeployed`) to a sidebar tone.
 * Explicit status wins; `isDeployed` only leans online when status is absent.
 * Catalog prove-read may encode isDeployed-only as status `"deployed"`.
 */
export function serviceStatusTone(
  status: string | null | undefined,
  isDeployed?: boolean | null,
): ServiceStatusTone {
  const raw = typeof status === "string" ? status.trim() : "";
  if (raw) {
    if (ONLINE_RE.test(raw)) return "online";
    if (ERROR_RE.test(raw)) return "error";
    if (STOPPED_RE.test(raw)) return "stopped";
    // Prove-read fallback when Liara only returns isDeployed (see projectsToServices).
    if (/^deployed$/i.test(raw)) return "online";
    return "unknown";
  }
  if (isDeployed === true) return "online";
  return "unknown";
}

/** Short EN/FA labels for aria / title (status not color-only). */
export function serviceStatusToneLabel(
  tone: ServiceStatusTone,
  language: "en" | "fa" = "en",
): string {
  const labels: Record<ServiceStatusTone, { en: string; fa: string }> = {
    online: { en: "Online", fa: "آنلاین" },
    error: { en: "Error", fa: "خطا" },
    stopped: { en: "Stopped", fa: "متوقف" },
    unknown: { en: "Unknown", fa: "نامشخص" },
  };
  return labels[tone][language];
}
