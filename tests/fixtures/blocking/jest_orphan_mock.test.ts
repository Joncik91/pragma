test("fetchUser_returns_user", async () => {
  const mock = jest.fn().mockResolvedValue({ id: "u1", name: "Alice" });
  const result = await mock("u1");
  expect(result).toEqual({ id: "u1", name: "Alice" });
});
