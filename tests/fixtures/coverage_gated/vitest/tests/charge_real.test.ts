/**
 * Honest test: imports chargeCard and actually calls it.
 * Pragma tier-2 should keep this as vitest.verified.
 */
import { expect, it } from "vitest";
import { chargeCard } from "../src/charge";

it("charges a valid token", () => {
  expect(chargeCard("tok_valid", 100)).toBe(true);
});

it("rejects zero amount", () => {
  expect(chargeCard("tok_valid", 0)).toBe(false);
});
