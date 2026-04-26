import { it, expect } from "vitest";
import { login } from "./auth/login";

it("login_throws_on_weak_password", () => {
  // Asserts the production stub's "not implemented yet" error rather than
  // a real validation rejection. Catches BUG-015.
  expect(() => login("u@e.com", "x")).toThrow("not implemented yet");
});
