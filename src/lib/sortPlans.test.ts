import { describe, expect, it } from "vitest";
import { sortPlansWeakToStrong } from "./sortPlans";

describe("sortPlansWeakToStrong", () => {
  it("orders free then cheapest RAM/price ascending", () => {
    const sorted = sortPlansWeakToStrong([
      { id: "express-g2", price_monthly: 24_600_000, ram_gb: 64 },
      { id: "small-g2", price_monthly: 475_000, ram_gb: 0.5 },
      { id: "pro-g2", price_monthly: 4_600_000, ram_gb: 8 },
      { id: "free", price_monthly: 0, ram_gb: 0.5 },
      { id: "medium-g2", price_monthly: 825_000, ram_gb: 1 },
    ]);
    expect(sorted.map((p) => p.id)).toEqual([
      "free",
      "small-g2",
      "medium-g2",
      "pro-g2",
      "express-g2",
    ]);
    expect(sorted.map((p) => p.tier)).toEqual([1, 2, 3, 4, 5]);
  });
});
