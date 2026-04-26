import { it, expect, vi } from "vitest";

it("fetchUser_returns_user", async () => {
  const mock = vi.fn().mockResolvedValue({ id: "u1", name: "Alice" });
  const result = await mock("u1");
  expect(result).toEqual({ id: "u1", name: "Alice" });
});
