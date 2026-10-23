import { useEffect, useState } from "react";
import { getAccountBalances, type AccountBalances } from "../lib/api";

function formatIrt(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return `${new Intl.NumberFormat("fa-IR").format(Math.round(value))} تومان`;
}

type SidebarWalletBalancesProps = {
  workspaceId?: string | null;
  /** Re-fetch when credentials change after Settings save. */
  refreshKey?: string;
};

export function SidebarWalletBalances({
  workspaceId,
  refreshKey,
}: SidebarWalletBalancesProps) {
  const [balances, setBalances] = useState<AccountBalances | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!workspaceId) {
      setBalances(null);
      return;
    }
    let cancelled = false;
    setBusy(true);
    void getAccountBalances(workspaceId)
      .then((result) => {
        if (!cancelled) setBalances(result);
      })
      .catch(() => {
        if (!cancelled) setBalances(null);
      })
      .finally(() => {
        if (!cancelled) setBusy(false);
      });
    return () => {
      cancelled = true;
    };
  }, [workspaceId, refreshKey]);

  if (!workspaceId) return null;

  const liaraValue = busy ? "…" : formatIrt(balances?.liara.balance);
  const avalValue = busy ? "…" : formatIrt(balances?.aval.remaining_irt);
  const liaraErr = Boolean(balances?.liara.error);
  const avalErr = Boolean(balances?.aval.error);

  return (
    <div className="sidebar-wallets" aria-live="polite" aria-label="موجودی کیف‌پول‌ها">
      <div className="sidebar-wallet-row">
        <span className="sidebar-wallet-label">لیارا</span>
        <span
          className={`sidebar-wallet-value${liaraErr ? " is-error" : ""}`}
          dir="ltr"
          title={liaraErr ? "خواندن موجودی ممکن نشد" : undefined}
        >
          {liaraErr && !busy ? "—" : liaraValue}
        </span>
      </div>
      <div className="sidebar-wallet-row">
        <span className="sidebar-wallet-label">Aval AI</span>
        <span
          className={`sidebar-wallet-value${avalErr ? " is-error" : ""}`}
          dir="ltr"
          title={avalErr ? "خواندن اعتبار ممکن نشد" : undefined}
        >
          {avalErr && !busy ? "—" : avalValue}
        </span>
      </div>
    </div>
  );
}
