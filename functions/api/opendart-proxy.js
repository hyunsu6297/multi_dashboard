const ALLOWED_ENDPOINTS = new Set([
  "corpCode.xml",
  "cvbdIsDecsn.json",
  "exbdIsDecsn.json",
  "bdwtIsDecsn.json",
]);

export async function onRequestPost(context) {
  try {
    const { endpoint, params } = await context.request.json();
    if (!ALLOWED_ENDPOINTS.has(endpoint)) {
      return Response.json({ message: "허용되지 않은 OpenDART 요청입니다." }, { status: 400 });
    }
    const query = new URLSearchParams(params || {});
    const response = await fetch(`https://opendart.fss.or.kr/api/${endpoint}?${query}`, {
      headers: { "User-Agent": "MultiDashboard/3.0" },
    });
    return new Response(response.body, {
      status: response.status,
      headers: {
        "Content-Type": response.headers.get("Content-Type") || "application/octet-stream",
        "Cache-Control": "no-store",
      },
    });
  } catch (error) {
    return Response.json(
      { message: error instanceof Error ? error.message : String(error) },
      { status: 502 },
    );
  }
}

export function onRequest() {
  return Response.json({ message: "POST 요청만 허용됩니다." }, { status: 405 });
}
