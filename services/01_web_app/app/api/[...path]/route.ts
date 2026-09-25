import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

async function proxy(request: NextRequest, context: { params: { path: string[] } }) {
  const base = process.env.API_INTERNAL_URL ?? "http://localhost:8000";
  const target = new URL("/api/" + context.params.path.map(encodeURIComponent).join("/"), base);
  target.search = request.nextUrl.search;

  const headers = new Headers();
  for (const name of ["cookie", "content-type", "x-request-id"]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }

  try {
    const upstream = await fetch(target, {
      method: request.method,
      headers,
      body: ["GET", "HEAD"].includes(request.method) ? undefined : await request.arrayBuffer(),
      cache: "no-store",
      signal: AbortSignal.timeout(60_000),
    });
    const responseHeaders = new Headers();
    for (const name of ["content-type", "set-cookie", "retry-after", "x-request-id"]) {
      const value = upstream.headers.get(name);
      if (value) responseHeaders.set(name, value);
    }
    responseHeaders.set("cache-control", "no-store");
    return new NextResponse(upstream.body, {
      status: upstream.status,
      headers: responseHeaders,
    });
  } catch {
    return NextResponse.json(
      {
        code: "API_UNAVAILABLE",
        detail: "เชื่อมต่อระบบตอบคำถามไม่ได้ชั่วคราว",
      },
      { status: 502 },
    );
  }
}

export { proxy as GET, proxy as POST, proxy as PATCH, proxy as DELETE };
