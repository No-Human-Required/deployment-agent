import { motion } from "motion/react";
import type { OrchestratorRun } from "../lib/schemas";
import { toIntakeViewPayload } from "../lib/intake";
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
 * In-chat GenUI intake (service / plan / domain) before createPlan.
 * HITL Approve remains a separate gate after the plan is drafted.
 */
export function IntakePanel({
  run,
  language,
  busy,
  onConfirm,
  onOpenSettings,
}: Props) {
  if (!run.intake || run.stage !== "awaiting_intake") return null;

  const payload = toIntakeViewPayload(
    {
      kind: run.intake.kind,
      services: run.intake.services,
      plans: run.intake.plans,
      require_plan: run.intake.require_plan,
      require_domain: run.intake.require_domain,
      load_error: run.intake.load_error,
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
