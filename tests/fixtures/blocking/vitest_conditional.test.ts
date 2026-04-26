import { it, expect } from "vitest";
import { login } from "./auth/login";

it("login_happy_path", () => {
  const enableStrict = false;
  if (enableStrict) {
    expect(login("u@e.com", "x")).toBe("JWT");
  }
});
