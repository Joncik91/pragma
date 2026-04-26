/**
 * Minimal production module for Pragma tier-2 vitest gate fixture.
 * Used by tests/charge_real.test.ts and tests/charge_imports_only.test.ts.
 */

export function chargeCard(token: string, amount: number): boolean {
  if (!token || amount <= 0) {
    return false;
  }
  return true;
}
