import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { Answer, Markdown } from "../components/Answer";
vi.mock("../components/AppProvider", () => ({
  useApp: () => ({ updateRating: vi.fn() }),
}));
it("renders Markdown and focuses the matching numbered source", async () => {
  render(
    <Answer
      entry={{
        id: "a1",
        role: "assistant",
        content: "**ผลแข่ง** อ้างอิง [2]",
        sources: [
          { ref: 2, title: "Match report", origin: "football-data.org" },
        ],
      }}
    />,
  );
  expect(screen.getByText("ผลแข่ง").tagName).toBe("STRONG");
  const link = screen.getByRole("link", { name: "[2]" });
  expect(link).toHaveAttribute("href", "#main-a1-source-2");
  await userEvent.click(link);
  expect(document.getElementById("main-a1-source-2")).toHaveFocus();
});
it("does not execute HTML or javascript links and does not rewrite code citations", () => {
  const { container } = render(
    <Markdown
      text={
        "<script>alert(1)</script>\n\n[bad](javascript:alert%281%29)\n\n`[1]`"
      }
      sources={[{ ref: 1, title: "Source" }]}
    />,
  );
  expect(container.querySelector("script")).toBeNull();
  expect(container.querySelector('a[href^="javascript:"]')).toBeNull();
  expect(container.querySelector("code")?.textContent).toBe("[1]");
  expect(container.querySelector("code a")).toBeNull();
});
