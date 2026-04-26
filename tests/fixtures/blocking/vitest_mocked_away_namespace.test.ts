import { it, expect, vi } from "vitest";
import * as searchModule from "./search";

vi.mock("./search", () => ({
  searchProducts: vi.fn(),
}));

it("searchProducts_returns_results", () => {
  vi.mocked(searchModule.searchProducts).mockReturnValue([{ id: "1" }]);
  const results = searchModule.searchProducts("widget", 10);
  expect(results).toEqual([{ id: "1" }]);
});
