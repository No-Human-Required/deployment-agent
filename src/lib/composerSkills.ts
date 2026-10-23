export type ComposerSkill = {
  id: string;
  label: string;
  hint: string;
  prompt: string;
};

type Locale = "en" | "fa";

/** Short starter skills shown in the composer «+» popover. */
export function composerSkills(language: Locale): ComposerSkill[] {
  if (language === "fa") {
    return [
      {
        id: "logs-24h",
        label: "لاگ خطاهای ۲۴ ساعت",
        hint: "خواندن لاگ و خطاهای اخیر",
        prompt: "لاگ خطاهای ۲۴ ساعت گذشته را بررسی کن",
      },
      {
        id: "debug",
        label: "دیباگ سرویس",
        hint: "علت‌یابی با شواهد",
        prompt: "سرویس را دیباگ کن و علت مشکل را پیدا کن",
      },
      {
        id: "deploy-check",
        label: "بررسی استقرار",
        hint: "سلامت و آخرین دیپلوی",
        prompt: "وضعیت آخرین استقرار و سلامت سرویس را بررسی کن",
      },
    ];
  }
  return [
    {
      id: "logs-24h",
      label: "Errors (last 24h)",
      hint: "Read recent error logs",
      prompt: "Review error logs from the last 24 hours",
    },
    {
      id: "debug",
      label: "Debug service",
      hint: "Evidence-based diagnosis",
      prompt: "Debug the service and find the root cause",
    },
    {
      id: "deploy-check",
      label: "Check deployment",
      hint: "Health and latest release",
      prompt: "Check the latest deployment and service health",
    },
  ];
}
