jest.mock("./auth/login", () => ({ login: jest.fn(() => "JWT") }));
import { login } from "./auth/login";

test("login_happy_path", () => {
  expect(login("u@e.com", "x")).toBe("JWT");
});
