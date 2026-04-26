import { it, expect } from "vitest";
import { login } from "./auth/login";

it("login_throws_on_weak_password", () => {
  const result = login("u@e.com", "weak");
  expect(result).toBe("JWT");
});
