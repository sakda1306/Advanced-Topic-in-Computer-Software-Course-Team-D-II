import { expect, it, vi } from "vitest";
import { api, invalidateAccount, submitFeedback } from "../lib/api";
it("retries feedback once only for MESSAGE_NOT_READY", async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce(
      new Response(
        JSON.stringify({ code: "MESSAGE_NOT_READY", detail: "pending" }),
        { status: 409 },
      ),
    )
    .mockResolvedValueOnce(new Response('{"ok":true}'));
  vi.stubGlobal("fetch", fetcher);
  expect(await submitFeedback("answer", 1)).toEqual({ ok: true });
  expect(fetcher).toHaveBeenCalledTimes(2);
  expect(JSON.parse(fetcher.mock.calls[1][1].body)).toEqual({
    message_id: "answer",
    rating: 1,
  });
});
it("does not endlessly retry feedback", async () => {
  const fetcher = vi.fn().mockImplementation(() =>
    Promise.resolve(
      new Response(JSON.stringify({ code: "MESSAGE_NOT_READY" }), {
        status: 409,
      }),
    ),
  );
  vi.stubGlobal("fetch", fetcher);
  await expect(submitFeedback("answer", -1)).rejects.toMatchObject({
    status: 409,
  });
  expect(fetcher).toHaveBeenCalledTimes(2);
});
it("ignores a late response from an earlier account", async () => {
  let resolve!: (response: Response) => void;
  vi.stubGlobal(
    "fetch",
    vi.fn(
      () =>
        new Promise<Response>((done) => {
          resolve = done;
        }),
    ),
  );
  const request = api("/history/old");
  invalidateAccount();
  resolve(new Response('{"messages":["secret"]}'));
  await expect(request).rejects.toMatchObject({ name: "AbortError" });
});
