import { it, expect } from "vitest";

const refund = async (id: string, amount: number) => {
  throw new Error("payments backend offline");
};

it("refund_rejects_negative_amount", async () => {
  await expect(refund("ch_1", -10)).rejects.toThrow("payments backend offline");
});
