/* Supabase bridge for the hosted global dashboard; never exposes the service key. */
(function () {
  "use strict";
  const projectUrl = "https://esqakvzvchcunhzjlyry.supabase.co";
  const publishableKey = "sb_publishable_T0q_8mB9yzcitTL7HH0SuA_W4DUcVtP";
  let clientPromise;
  async function client() {
    if (!clientPromise) clientPromise = (async () => {
      if (window.parent !== window && window.parent.dashboardSupabase) return window.parent.dashboardSupabase;
      const { createClient } = await import("https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/+esm");
      return createClient(projectUrl, publishableKey);
    })();
    return clientPromise;
  }
  async function user() {
    const db = await client();
    const { data, error } = await db.auth.getSession();
    if (error) throw error;
    if (!data?.session?.user) throw new Error("로그인이 필요합니다.");
    return data.session.user;
  }
  async function rows(fileKey) {
    const db = await client();
    const output = [];
    for (let start = 0; ; start += 1000) {
      const { data, error } = await db.from("manual_file_rows")
        .select("payload,row_no,updated_at").eq("domain", "global").eq("file_key", fileKey)
        .order("row_no").range(start, start + 999);
      if (error) throw error;
      output.push(...data);
      if (data.length < 1000) return output;
    }
  }
  async function read(fileKey) { return (await rows(fileKey)).map(row => row.payload); }
  async function replace(fileKey, values) {
    const actor = await user();
    const db = await client();
    const records = values.map((payload, index) => ({
      domain: "global", file_key: fileKey, file_label: fileKey,
      sheet_name: "Data", row_no: index + 1, payload,
      created_by: actor.id, updated_at: new Date().toISOString()
    }));
    for (let start = 0; start < records.length; start += 500) {
      const { error } = await db.from("manual_file_rows")
        .upsert(records.slice(start, start + 500), { onConflict: "domain,file_key,sheet_name,row_no" });
      if (error) throw error;
    }
    const { error } = await db.from("manual_file_rows").delete()
      .eq("domain", "global").eq("file_key", fileKey).eq("sheet_name", "Data")
      .gt("row_no", records.length);
    if (error) throw error;
  }
  async function market() { return (await read("market_data"))[0] || null; }
  async function request(requestType, securities, onProgress, timeoutMs = 300000) {
    const actor = await user();
    const db = await client();
    const { data, error } = await db.from("global_market_refresh_requests")
      .insert({ request_type: requestType === "etf_discovery" ? "batch" : requestType,
        securities: [...new Set(securities)],
        requested_by: actor.id, priority: requestType === "etf_discovery" ? 40 : 30 })
      .select("id").single();
    if (error) throw error;
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
      const { data: state, error: pollError } = await db.from("global_market_refresh_requests")
        .select("status,error,result,started_at").eq("id", data.id).single();
      if (pollError) throw pollError;
      onProgress?.(state);
      if (state.status === "done") return state.result || {};
      if (state.status === "failed") throw new Error(state.error || "블룸버그 수신기 처리 실패");
      await new Promise(resolve => setTimeout(resolve, 1800));
    }
    throw new Error("수신기 응답 시간 초과. 이 PC에서 블룸버그 수신기를 실행했는지 확인하세요.");
  }
  window.GlobalWebBridge = { client, read, replace, market, request };
})();
