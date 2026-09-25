import { act, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { AppProvider, useApp } from "../components/AppProvider";
import Home from "../app/page";
const navigation = vi.hoisted(() => ({ replace: vi.fn(), push: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => navigation,
  usePathname: () => "/",
}));
let app: ReturnType<typeof useApp>;
function Probe() {
  app = useApp();
  return <span>{app.user?.id ?? "guest"}</span>;
}
const user = (id: string) => ({
  id,
  display_name: id,
  username: id,
  role: "user",
  favorite_team_id: 66,
  language: "th",
});
const json = (data: unknown, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json" },
  });
async function setup() {
  const fetcher = vi.fn(
    async (path: string, init?: RequestInit): Promise<Response> => {
      if (path === "/api/auth/me") return json({ user: user("A") });
      if (path === "/api/auth/login") return json({ user: user("B") });
      if (path === "/api/sessions") return json({ sessions: [] });
      if (path === "/api/auth/logout") return json({ ok: true });
      if (path === "/api/me/preferences")
        return json({
          user: {
            ...user("A"),
            favorite_team_id: JSON.parse(String(init?.body)).favorite_team_id,
          },
        });
      if (path === "/api/chat")
        return json({
          session_id: "session-A",
          message_id: "answer-A",
          answer: "private answer A",
          sources: [],
          route: "general_ai",
          latency_ms: 10,
        });
      throw new Error("unexpected " + path);
    },
  );
  vi.stubGlobal("fetch", fetcher);
  render(
    <AppProvider>
      <Probe />
      <Home />
    </AppProvider>,
  );
  await waitFor(() => expect(app.user?.id).toBe("A"));
  return fetcher;
}
it("clears every account's conversation and sends a fresh session after logout/login", async () => {
  const fetcher = await setup();
  await act(async () => {
    await app.sendQuestion("private question A");
  });
  expect(app.entries).toHaveLength(2);
  await act(async () => {
    await app.logout();
    await app.login("B", "password");
  });
  expect(app.entries).toEqual([]);
  expect(app.sessionId).toBeNull();
  await act(async () => {
    await app.sendQuestion("new question B");
  });
  const calls = fetcher.mock.calls.filter(([path]) => path === "/api/chat");
  expect(JSON.parse(String(calls[1][1]?.body)).session_id).toBeNull();
  expect(screen.queryByText("private question A")).not.toBeInTheDocument();
});
it("expires the account on 401 and ignores a late answer after switching identity", async () => {
  const fetcher = await setup();
  fetcher.mockResolvedValueOnce(
    json({ detail: "expired", code: "UNAUTHENTICATED" }, 401),
  );
  await act(async () => {
    await app.sendQuestion("expire");
  });
  expect(app.user).toBeNull();
  expect(app.entries).toEqual([]);
  expect(app.sessions).toEqual([]);
  expect(navigation.replace).toHaveBeenCalledWith("/login?expired=1");
});
it("does not append pending account A response after B logs in", async () => {
  const fetcher = await setup();
  let resolve!: (value: Response) => void;
  fetcher.mockImplementationOnce(
    () =>
      new Promise((done) => {
        resolve = done;
      }),
  );
  let pending!: Promise<boolean>;
  act(() => {
    pending = app.sendQuestion("old question");
  });
  await act(async () => {
    await app.login("B", "pw");
  });
  await act(async () => {
    resolve(
      json({
        session_id: "old",
        message_id: "old-answer",
        answer: "secret",
        sources: [],
      }),
    );
    await pending;
  });
  expect(app.user?.id).toBe("B");
  expect(app.entries).toEqual([]);
  expect(app.sessionId).toBeNull();
});
it("retains failed draft and never sends while a team preference is pending", async () => {
  const fetcher = await setup();
  act(() => app.setDraft("retry this"));
  fetcher.mockResolvedValueOnce(
    json({ detail: "offline", code: "API_UNAVAILABLE" }, 502),
  );
  await act(async () => {
    expect(await app.sendQuestion("retry this")).toBe(false);
  });
  expect(app.draft).toBe("retry this");
  expect(app.entries).toEqual([]);
  let resolve!: (value: Response) => void;
  fetcher.mockImplementationOnce(
    () =>
      new Promise((done) => {
        resolve = done;
      }),
  );
  let changing!: Promise<void>;
  act(() => {
    changing = app.changeTeam("chelsea");
  });
  await act(async () => {
    expect(await app.sendQuestion("team question")).toBe(false);
  });
  await act(async () => {
    resolve(json({ user: { ...user("A"), favorite_team_id: 61 } }));
    await changing;
  });
  expect(app.team.key).toBe("chelsea");
  expect(app.sessionId).toBeNull();
});
it("sample prompt fills the composer and focuses it", async () => {
  await setup();
  const { default: userEvent } = await import("@testing-library/user-event");
  await userEvent.click(screen.getByRole("button", { name: /ประวัติทีม/ }));
  expect(screen.getByRole("textbox", { name: "ถามเรื่องฟุตบอล" })).toHaveValue(
    "เล่าประวัติของ Manchester United",
  );
  expect(
    screen.getByRole("textbox", { name: "ถามเรื่องฟุตบอล" }),
  ).toHaveFocus();
});
