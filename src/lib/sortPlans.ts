/** Weak → strong ordering for Liara PaaS plans (price, then RAM). */

export type SortablePlan = {
  id: string;
  price_monthly?: number | null;
  ram_gb?: number | null;
  tier?: number;
};

export function sortPlansWeakToStrong<T extends SortablePlan>(plans: T[]): T[] {
  return [...plans].sort((a, b) => {
    const aFree = a.id === "free" ? 0 : 1;
    const bFree = b.id === "free" ? 0 : 1;
    if (aFree !== bFree) return aFree - bFree;

    const aPrice = Number(a.price_monthly);
    const bPrice = Number(b.price_monthly);
    const aHasPrice = Number.isFinite(aPrice);
    const bHasPrice = Number.isFinite(bPrice);
    if (aHasPrice && bHasPrice && aPrice !== bPrice) return aPrice - bPrice;
    if (aHasPrice !== bHasPrice) return aHasPrice ? -1 : 1;

    const aRam = Number(a.ram_gb);
    const bRam = Number(b.ram_gb);
    const aHasRam = Number.isFinite(aRam);
    const bHasRam = Number.isFinite(bRam);
    if (aHasRam && bHasRam && aRam !== bRam) return aRam - bRam;
    if (aHasRam !== bHasRam) return aHasRam ? -1 : 1;

    return a.id.localeCompare(b.id);
  }).map((plan, index) => ({ ...plan, tier: index + 1 }));
}
