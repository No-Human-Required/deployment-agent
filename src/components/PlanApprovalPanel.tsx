import { motion } from "motion/react";
import type { OrchestratorRun } from "../lib/schemas";
import {
  approvalResultFromRun,
  mapOrchestratorToChatCards,
} from "../lib/orchestratorCards";
import { GenerativeCard } from "./agent-ui/GenerativeCard";

type Props = {
  run: OrchestratorRun;
  language: "en" | "fa";
  busy?: boolean;
  onApprove: () => void;
  onReject: () => void;
};

/**
 * Chat stack of companion GenUI cards for an orchestrator run.
 * Quiet surface: useful GenUI (evidence/diagnosis/monitor) + plan + HITL;
 * no readiness / tool-id / UUID dump. HITL approve/reject only via buttons.
 */
export function PlanApprovalPanel({ run, language, busy, onApprove, onReject }: Props) {
  const cards = mapOrchestratorToChatCards(run, language);
  const approvalResult = approvalResultFromRun(run);
  const awaiting = run.stage === "awaiting_approval";

  if (cards.length === 0) return null;

  return (
    <motion.div
      className="approval-panel"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, ease: [0.22, 0.75, 0.28, 1] }}
    >
      {cards.map((payload, index) => (
        <motion.div
          key={`${payload.type}-${index}`}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.24, delay: Math.min(index * 0.05, 0.2), ease: [0.22, 0.75, 0.28, 1] }}
        >
          <GenerativeCard
            payload={payload}
            language={language}
            pending={awaiting && payload.type === "approval"}
            busy={busy}
            approvalResult={payload.type === "approval" ? approvalResult : null}
            onApproval={
              payload.type === "approval"
                ? (decision) => (decision === "approve" ? onApprove() : onReject())
                : undefined
            }
          />
        </motion.div>
      ))}
    </motion.div>
  );
}
