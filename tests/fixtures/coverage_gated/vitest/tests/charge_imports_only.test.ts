/**
 * Gamed test: imports chargeCard but never calls it.
 * Pragma tier-2 should emit vitest.target_not_covered for this file
 * (the V8 coverage will show 0 hits on chargeCard's lines).
 */
import { expect, it } from "vitest";
import { chargeCard } from "../src/charge"; // imported but never called

it("always passes without touching chargeCard", () => {
  expect(1 + 1).toBe(2);
});
