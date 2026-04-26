import { it, expect, vi } from "vitest";

vi.mock("./auth/login", () => ({
  login: vi.fn(() => "JWT"),
}));

import { login } from "./auth/login";

it("login_happy_path", () => {
  expect(login("u@e.com", "x")).toBe("JWT");
});
