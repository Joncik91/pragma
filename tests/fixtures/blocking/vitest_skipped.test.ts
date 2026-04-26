import { it, expect } from "vitest";

it.skip("login_happy_path", () => {
  expect(login("u@e.com", "x")).toBe("JWT");
});
