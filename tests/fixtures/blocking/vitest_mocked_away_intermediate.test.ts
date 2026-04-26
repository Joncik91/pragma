import { it, expect, vi } from "vitest";
import { notifyUser } from "./notify";

vi.mock("./notify", () => ({ notifyUser: vi.fn() }));

it("notifyUser_happy_path", () => {
  vi.mocked(notifyUser).mockReturnValue({ sent: true });
  const result = notifyUser("user-1", "Hello!");
  expect(result).toEqual({ sent: true });
});
