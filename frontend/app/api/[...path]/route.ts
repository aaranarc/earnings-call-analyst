// The backend credential is server-only. Never forward incoming authorization headers.
export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 300;
const allowed = new Map([["health", "GET"], ["companies", "GET"], ["eval/latest", "GET"], ["ask", "POST"], ["thesis/check", "POST"]]);
async function proxy(request: Request, context: {params: Promise<{path: string[]}>}) {
  const path = (await context.params).path.join("/");
  if (allowed.get(path) !== request.method) return Response.json({detail:"Not found"}, {status:404});
  const headers: Record<string,string> = {"Content-Type":"application/json"};
  if (request.method === "POST") {
    const origin = request.headers.get("origin");
    const expected = process.env.PUBLIC_ORIGIN || new URL(request.url).origin;
    if (origin && origin !== expected) return Response.json({detail:"Origin rejected"}, {status:403});
    if (process.env.API_ACCESS_TOKEN) headers.Authorization = `Bearer ${process.env.API_ACCESS_TOKEN}`;
  }
  try {
    let body: string | undefined;
    if (request.method === "POST") {
      // Read a bounded body before forwarding; reject unknown JSON input at the API schema.
      const reader = request.body?.getReader();
      const chunks: Uint8Array[] = []; let size=0;
      if (reader) while (true) {const {done,value} = await reader.read(); if (done) break; size+=value.length;
        if (size>16000) {await reader.cancel(); return Response.json({detail:"Request too large"},{status:413});} chunks.push(value);}
      body = Buffer.concat(chunks).toString("utf8");
    }
    const upstream = await fetch(`${process.env.API_ORIGIN || "http://127.0.0.1:8000"}/${path}`, {
      method:request.method, headers, body, cache:"no-store", redirect:"error", signal:AbortSignal.timeout(290000),
    });
    const out = new Headers({"Content-Type":upstream.headers.get("content-type") || "application/json", "Cache-Control":"no-store", "X-Accel-Buffering":"no"});
    if (upstream.headers.has("retry-after")) out.set("Retry-After",upstream.headers.get("retry-after")!);
    return new Response(upstream.body,{status:upstream.status,headers:out});
  } catch {return Response.json({detail:"Analyst API is unavailable. It may be starting up; please retry shortly."},{status:503});}
}
export {proxy as GET, proxy as POST};
