import { useEffect, useMemo, useState } from "react";
import { motion } from "motion/react";
import { getLiaraPlans } from "../lib/api";
import { toIntakeViewPayload, type IntakePlanOption, type IntakePlatformOption } from "../lib/intake";
import { enrichPlatformOptions, LIARA_PLATFORMS } from "../lib/liaraPlatforms";
import type { OrchestratorRun } from "../lib/schemas";
import { sortPlansWeakToStrong } from "../lib/sortPlans";
import {
  GenerativeCard,
  type IntakeConfirmValues,
} from "./agent-ui/GenerativeCard";

type Props = {
  run: OrchestratorRun;
  language: "en" | "fa";
  busy?: boolean;
  onConfirm: (values: IntakeConfirmValues) => void;
  onOpenSettings: () => void;
};

/**
 * In-chat GenUI intake (service / plan / platform / domain) before createPlan.
 * HITL Approve remains a separate gate after the plan is drafted.
 */
export function IntakePanel({
  run,
  language,
  busy,
  onConfirm,
  onOpenSettings,
}: Props) {
  const intake = run.intake;
  const [livePlans, setLivePlans] = useState<IntakePlanOption[] | null>(null);

  useEffect(() => {
    if (!intake || run.stage !== "awaiting_intake") return;
    if (!intake.require_plan) return;
    const missingPrice = (intake.plans ?? []).some(
      (plan) => plan.price_monthly == null || Number.isNaN(Number(plan.price_monthly)),
    );
    if (!missingPrice && (intake.plans?.length ?? 0) > 0) {
      setLivePlans(null);
      return;
    }
    let cancelled = false;
    void getLiaraPlans(run.workspace_id)
      .then((plans) => {
        if (cancelled) return;
        setLivePlans(
          plans.map((plan) => ({
            id: plan.id,
            label: plan.label,
            hint: plan.hint,
            price_monthly: plan.price_monthly ?? null,
            ram_gb: plan.ram_gb ?? null,
            tier: plan.tier,
          })),
        );
      })
      .catch(() => {
        if (!cancelled) setLivePlans(null);
      });
    return () => {
      cancelled = true;
    };
  }, [
    intake,
    run.stage,
    run.workspace_id,
    intake?.require_plan,
    intake?.plans,
  ]);

  const platforms: IntakePlatformOption[] = useMemo(() => {
    if (!intake) return [];
    if (!intake.require_platform) return [];
    return enrichPlatformOptions(
      intake.platforms?.length ? intake.platforms : LIARA_PLATFORMS,
    );
  }, [intake]);

  const plans: IntakePlanOption[] = useMemo(() => {
    if (!intake) return [];
    const source = livePlans && livePlans.length > 0 ? livePlans : intake.plans ?? [];
    return sortPlansWeakToStrong(source);
  }, [intake, livePlans]);

  if (!intake || run.stage !== "awaiting_intake") return null;

  const payload = toIntakeViewPayload(
    {
      kind: intake.kind,
      services: intake.services,
      plans,
      platforms,
      require_plan: intake.require_plan,
      require_domain: intake.require_domain,
      require_platform: intake.require_platform,
      suggested_platform: intake.suggested_platform,
      suggested_service_name: intake.suggested_service_name,
      prefer_new_service: intake.prefer_new_service,
      load_error: intake.load_error,
    },
    language,
  );

  return (
    <motion.div
      className="approval-panel"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, ease: [0.22, 0.75, 0.28, 1] }}
    >
      <GenerativeCard
        payload={payload}
        language={language}
        pending
        busy={busy}
        onIntakeConfirm={onConfirm}
        onOpenSettings={onOpenSettings}
      />
    </motion.div>
  );
}
