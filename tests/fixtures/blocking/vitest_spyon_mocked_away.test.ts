import { it, expect, vi } from "vitest";
import * as chargeModule from "./charge";

it("chargeCard_happy_path", () => {
  vi.spyOn(chargeModule, "chargeCard").mockReturnValue({ id: "ch_1" });
  const result = chargeModule.chargeCard("tok", 1000);
  expect(result).toEqual({ id: "ch_1" });
});
