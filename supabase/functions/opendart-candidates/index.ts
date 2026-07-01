import { unzipSync } from "npm:fflate@0.8.2";
import { createClient } from "npm:@supabase/supabase-js@2.95.0";

const BASES = ["https://opendart.fss.or.kr/api", "https://engopendart.fss.or.kr/engapi"];
const APIS = [["CB", "cvbdIsDecsn.json"], ["EB", "exbdIsDecsn.json"], ["BW", "bdwtIsDecsn.json"]] as const;
let corpCache: { byStock: Record<string, any>; byCorp: Record<string, any> } | null = null;

const cors = { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type", "Content-Type": "application/json" };
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: cors });
async function authorized(req: Request) {
  const suppliedKey = req.headers.get("apikey") || "";
  const secretKeys = Object.values(JSON.parse(Deno.env.get("SUPABASE_SECRET_KEYS") || "{}"));
  if (secretKeys.includes(suppliedKey)) return true;
  const token = (req.headers.get("Authorization") || "").replace(/^Bearer\s+/i, "");
  if (!token) return false;
  const publishable = JSON.parse(Deno.env.get("SUPABASE_PUBLISHABLE_KEYS") || "{}").default || Deno.env.get("SUPABASE_ANON_KEY") || "";
  const client = createClient(Deno.env.get("SUPABASE_URL") || "", publishable);
  return Boolean((await client.auth.getUser(token)).data.user);
}
const num = (value: unknown) => { const text = String(value ?? "").replace(/[^\d.\-]/g, ""); return text ? Number(text) : null; };
const pct = (value: unknown) => { const n = num(value); return n == null ? null : n / 100; };
const date = (value: unknown) => { const m = String(value ?? "").match(/(\d{4})\D+(\d{1,2})\D+(\d{1,2})/); return m ? `${m[1]}-${m[2].padStart(2,"0")}-${m[3].padStart(2,"0")}` : ""; };
const round = (value: unknown) => String(value ?? "").replace(/[^0-9]/g, "");
const targetName = (value: unknown, issuer: string) => { let text = String(value ?? "").trim(); if (issuer && text.includes(issuer)) return issuer; for (const token of ["회사가 보유한","(자기주식)","자기주식","주식회사","(주)","기명식","보통주식","보통주","발행"]) text = text.replaceAll(token, ""); return text.replace(/[\[\]()“”"]/g, "").replace(/\s+/g, " ").trim() || issuer; };

async function dart(endpoint: string, params: Record<string,string>, binary = false) {
  let lastError: unknown;
  for (const base of BASES) {
    try {
      const url = `${base}/${endpoint}?${new URLSearchParams(params)}`;
      const res = await fetch(url, { headers: { "User-Agent": "MezzanineDashboard/3.0" } });
      if (!res.ok) throw new Error(`OpenDART HTTP ${res.status}`);
      return binary ? new Uint8Array(await res.arrayBuffer()) : await res.json();
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError instanceof Error ? lastError : new Error("OpenDART 연결에 실패했습니다.");
}

async function corpMaps(key: string) {
  if (corpCache) return corpCache;
  const zipped = await dart("corpCode.xml", { crtfc_key: key }, true) as Uint8Array;
  const files = unzipSync(zipped), xml = new TextDecoder().decode(files[Object.keys(files)[0]]);
  const byStock: Record<string,any> = {}, byCorp: Record<string,any> = {};
  for (const block of xml.match(/<list>[\s\S]*?<\/list>/g) ?? []) {
    const get = (tag:string) => (block.match(new RegExp(`<${tag}>([\\s\\S]*?)<\\/${tag}>`))?.[1] ?? "").trim();
    const row = { corp_code:get("corp_code"), corp_name:get("corp_name"), corp_name_eng:get("corp_name_eng"), stock_code:get("stock_code"), modify_date:get("modify_date") };
    if (row.corp_code) byCorp[row.corp_code] = row;
    if (row.stock_code) byStock[row.stock_code] = row;
  }
  corpCache = { byStock, byCorp }; return corpCache;
}

function enrich(raw:any, kind:string, corp:any, maps:any) {
  const target = targetName(raw.cvisstk_knd || raw.extg || raw.nstk_isstk_knd || raw.bd_knd, corp.corp_name);
  const match = Object.values(maps.byCorp).find((x:any) => x.stock_code && x.corp_name === target) as any;
  const cv = num(raw.cv_prc || raw.ex_prc), floor = num(raw.act_mktprcfl_cvprc_lwtrsprc), amount = num(raw.bd_fta), no = round(raw.bd_tm);
  return { rcept_no:raw.rcept_no || "", corp_name:corp.corp_name, stock_code:corp.stock_code, bond_type_code:kind, round:no, issue_name:`${corp.corp_name}${no}${kind}`, target_stock:target, exchange_code:match?.stock_code || (kind !== "EB" ? corp.stock_code : ""), coupon:pct(raw.bd_intr_ex), ytm:pct(raw.bd_intr_sf), issue_amount_million:amount == null ? null : Math.round(amount/1_000_000), issue_date:date(raw.bddd), convert_start:date(raw.cvrqpd_bgd || raw.exrqpd_bgd || raw.expd_bgd), convert_end:date(raw.cvrqpd_edd || raw.exrqpd_edd || raw.expd_edd), convert_price:cv, floor_price:floor, refixing:floor != null && cv ? floor/cv : null };
}

Deno.serve(async req => {
  if (req.method === "OPTIONS") return new Response("ok", { headers:cors });
  try {
    if (!await authorized(req)) return json({ ok:false, message:"로그인 세션이 유효하지 않습니다." }, 401);
    const key = Deno.env.get("OPENDART_API_KEY") || "__DART_KEY__";
    if (!/^[A-Za-z0-9]{40}$/.test(key)) throw new Error("OpenDART 인증키가 설정되지 않았습니다.");
    const { identifier, begin, end } = await req.json();
    if (!/^\d{8}$/.test(begin) || !/^\d{8}$/.test(end)) throw new Error("조회기간은 YYYYMMDD 형식이어야 합니다.");
    const maps = await corpMaps(key), value = String(identifier ?? "").replace(/\.0$/, "").trim();
    let corp:any = /^\d{1,6}$/.test(value) ? maps.byStock[value.padStart(6,"0")] : /^\d{7,8}$/.test(value) ? maps.byCorp[value.padStart(8,"0")] : Object.values(maps.byCorp).find((x:any)=>x.corp_name===value);
    if (!corp) throw new Error(`'${value}'에 해당하는 OpenDART 고유번호를 찾지 못했습니다.`);
    const list:any[] = [], api_results:any[] = [];
    for (const [kind, endpoint] of APIS) {
      const data:any = await dart(endpoint, { crtfc_key:key, corp_code:corp.corp_code, bgn_de:begin, end_de:end });
      if (!["000","013"].includes(data.status)) throw new Error(`${kind} OpenDART 오류(${data.status}): ${data.message}`);
      const found = data.list || []; api_results.push({ type:kind, status:data.status, count:found.length }); list.push(...found.map((x:any)=>enrich(x,kind,corp,maps)));
    }
    list.sort((a,b)=>String(b.rcept_no).localeCompare(String(a.rcept_no)));
    return json({ ok:true, company:corp, api_results, list, begin, end });
  } catch (error) { return json({ ok:false, message:error instanceof Error ? error.message : String(error) }, 400); }
});

