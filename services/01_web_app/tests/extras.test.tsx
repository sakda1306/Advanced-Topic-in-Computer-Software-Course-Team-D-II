import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { KnowledgeBase, Users } from "../components/AdminExtras";
vi.mock("../components/AppProvider", () => ({
  useApp: () => ({ user: { id: "self" } }),
}));
it("disables own role and account controls", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            items: [
              {
                id: "self",
                username: "admin",
                display_name: "Admin",
                role: "admin",
                disabled: false,
                message_count: 0,
              },
            ],
            next_cursor: null,
          }),
        ),
    ),
  );
  render(<Users />);
  expect(
    await screen.findByRole("combobox", { name: "บทบาท admin" }),
  ).toBeDisabled();
  expect(screen.getByRole("button", { name: "ระงับบัญชี" })).toBeDisabled();
});
it("does not delete a document after confirmation is cancelled", async () => {
  const fetcher = vi.fn(
    async () =>
      new Response(
        JSON.stringify({
          documents: 3,
          chunks: 3,
          by_category: {},
          index_version: "test",
        }),
      ),
  );
  vi.stubGlobal("fetch", fetcher);
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
  render(<KnowledgeBase />);
  await screen.findByText("Index version: test");
  await userEvent.type(
    screen.getByRole("textbox", { name: "Document ID" }),
    "trivia-0001",
  );
  await userEvent.click(screen.getByRole("button", { name: "ลบเอกสาร" }));
  expect(confirm).toHaveBeenCalled();
  expect(fetcher).toHaveBeenCalledTimes(1);
});
