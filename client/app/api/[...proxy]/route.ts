import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function proxy(request: NextRequest, context: { params: { proxy: string[] } }) {
  const path = context.params.proxy.join("/");
  const search = request.nextUrl.search;
  const target = `${API_BASE}/api/${path}${search}`;
  const isFormData = request.headers.get("content-type")?.includes("multipart/form-data");

  const headers = new Headers(request.headers);
  headers.delete("host");
  if (!isFormData) {
    headers.set("content-type", request.headers.get("content-type") || "application/json");
  }

  try {
    const body = ["GET", "HEAD"].includes(request.method) ? undefined : await request.arrayBuffer();
    const response = await fetch(target, {
      method: request.method,
      headers,
      body,
      cache: "no-store",
    });

    const responseHeaders = new Headers(response.headers);
    responseHeaders.delete("content-encoding");

    return new NextResponse(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: responseHeaders,
    });
  } catch (error) {
    return NextResponse.json(
      { error: "Proxy Error", message: error instanceof Error ? error.message : String(error), target },
      { status: 500 }
    );
  }
}

export {
  proxy as DELETE,
  proxy as GET,
  proxy as HEAD,
  proxy as PATCH,
  proxy as POST,
  proxy as PUT,
};
