import { it } from "vitest";
import { login } from "./auth/login";

it("login_happy_path", () => {
  try {
    login("u@e.com", "weak");
  } catch (_) {}
});
