import { createClient } from "npm:@supabase/supabase-js@2.95.0";

const MODEL = Deno.env.get("OPENAI_MODEL") || "gpt-5.4-mini";
const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Content-Type": "application/json; charset=utf-8",
};
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: cors });
const number = (value: unknown) => {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
};
const rounded = (value: number | null, digits = 2) => value == null || !Number.isFinite(value)
  ? null
  : Number(value.toFixed(digits));
const assessment = (value: number | null) => {
  if (value == null) return "비교 불가";
  const size = Math.abs(value) < 0.20 ? "소폭" : Math.abs(value) < 0.50 ? "다소" : "큰 폭";
  return `${size} ${value >= 0 ? "강세" : "약세"}`;
};

type Position = {
  name?: string;
  code?: string;
  market?: string;
  sectorLarge?: string;
  sectorMid?: string;
  exp?: number;
  pl?: number;
  changeRatePct?: number | null;
  delta?: number | null;
  parity?: number | null;
  creditRating?: string;
  creditScore?: number | null;
  issuer?: string;
  lookthrough?: number;
};

async function authorized(req: Request) {
  const token = (req.headers.get("Authorization") || "").replace(/^Bearer\s+/i, "");
  if (!token) return null;
  const publishable = JSON.parse(Deno.env.get("SUPABASE_PUBLISHABLE_KEYS") || "{}").default
    || Deno.env.get("SUPABASE_ANON_KEY") || "";
  const client = createClient(Deno.env.get("SUPABASE_URL") || "", publishable);
  return (await client.auth.getUser(token)).data.user || null;
}

function marketName(value: unknown) {
  const text = String(value || "");
  if (text.includes("코스닥")) return "코스닥";
  if (text.includes("코스피")) return "코스피";
  return "미분류";
}

function prepareSummary(source: Record<string, unknown>) {
  const positions = (Array.isArray(source.positions) ? source.positions : [])
    .filter((row): row is Position => !!row && typeof row === "object");
  const indices = source.marketIndexReturns && typeof source.marketIndexReturns === "object"
    ? source.marketIndexReturns as Record<string, unknown>
    : {};
  const benchmark = source.benchmarkSectors && typeof source.benchmarkSectors === "object"
    ? source.benchmarkSectors as Record<string, any>
    : {};

  return {
    asOfDate: String(source.asOfDate || ""),
    selectedFund: String(source.selectedFund || "전체 메자닌 펀드"),
    markets: ["코스닥", "코스피"].map((market) => {
      const rows = positions.filter((row) => marketName(row.market) === market);
      const exp = rows.reduce((sum, row) => sum + number(row.exp), 0);
      const pl = rows.reduce((sum, row) => sum + number(row.pl), 0);
      const actualReturn = exp ? pl / exp * 100 : null;
      const indexReturn = indices[market] == null ? null : number(indices[market]);
      const relative = actualReturn == null || indexReturn == null ? null : actualReturn - indexReturn;
      const sectors = new Map<string, { exp: number; pl: number; stocks: Position[] }>();
      for (const row of rows) {
        const name = String(row.sectorMid || row.sectorLarge || "미분류");
        const item = sectors.get(name) || { exp: 0, pl: 0, stocks: [] };
        item.exp += number(row.exp);
        item.pl += number(row.pl);
        item.stocks.push(row);
        sectors.set(name, item);
      }
      const bm = benchmark[market]?.mid && typeof benchmark[market].mid === "object"
        ? benchmark[market].mid
        : {};
      const sectorSignals = [...new Set([...sectors.keys(), ...Object.keys(bm)])].map((name) => {
        const item = sectors.get(name) || { exp: 0, pl: 0, stocks: [] };
        const portfolioWeight = exp ? item.exp / exp * 100 : 0;
        const benchmarkWeight = number(bm[name]?.weight ?? bm[name]) * 100;
        const sectorReturn = item.exp ? item.pl / item.exp * 100 : null;
        const activeWeight = portfolioWeight - benchmarkWeight;
        return {
          sector: name,
          portfolioWeightPct: rounded(portfolioWeight),
          benchmarkWeightPct: rounded(benchmarkWeight),
          activeWeightPp: rounded(activeWeight),
          sectorReturnPct: rounded(sectorReturn),
          impactSignal: rounded(sectorReturn == null ? null : activeWeight * sectorReturn / 100),
          topStocks: [...item.stocks].sort((a, b) => Math.abs(number(b.pl)) - Math.abs(number(a.pl))).slice(0, 2)
            .map((row) => ({ name: row.name, returnPct: rounded(row.changeRatePct == null ? null : number(row.changeRatePct)), plEok: rounded(number(row.pl) / 100_000_000) })),
        };
      }).filter((row) => row.portfolioWeightPct || row.benchmarkWeightPct);
      const primaryDirection = number(relative) < 0 ? "negative" : "positive";
      const primarySectors = sectorSignals.filter((row) => primaryDirection === "negative" ? number(row.impactSignal) < 0 : number(row.impactSignal) > 0)
        .sort((a, b) => primaryDirection === "negative" ? number(a.impactSignal) - number(b.impactSignal) : number(b.impactSignal) - number(a.impactSignal)).slice(0, 3);
      const offsetSectors = Math.abs(number(relative)) <= 0.50
        ? sectorSignals.filter((row) => primaryDirection === "negative" ? number(row.impactSignal) > 0 : number(row.impactSignal) < 0)
          .sort((a, b) => primaryDirection === "negative" ? number(b.impactSignal) - number(a.impactSignal) : number(a.impactSignal) - number(b.impactSignal)).slice(0, 3)
        : [];
      const ranked = [...rows].sort((a, b) => number(b.pl) - number(a.pl));
      const stockSignal = (row: Position) => ({
        name: row.name,
        sector: String(row.sectorMid || row.sectorLarge || "미분류"),
        returnPct: rounded(row.changeRatePct == null ? null : number(row.changeRatePct)),
        plEok: rounded(number(row.pl) / 100_000_000),
      });
      const stockCandidates = rows.filter((row) => row.name && row.changeRatePct != null && Number.isFinite(Number(row.changeRatePct)));
      const positiveStocks = stockCandidates.filter((row) => number(row.changeRatePct) > 0)
        .sort((a, b) => number(b.pl) - number(a.pl)).slice(0, 4).map(stockSignal);
      const negativeStocks = stockCandidates.filter((row) => number(row.changeRatePct) < 0)
        .sort((a, b) => number(a.pl) - number(b.pl)).slice(0, 4).map(stockSignal);
      const characteristicStocks = [...stockCandidates]
        .sort((a, b) => Math.abs(number(b.pl)) - Math.abs(number(a.pl))).slice(0, 6).map(stockSignal);
      const creditBase = rows.reduce((sum, row) => sum + Math.max(0, number(row.lookthrough)), 0);
      const issuers = new Map<string, number>();
      let creditWeighted = 0, investment = 0, speculative = 0, unrated = 0, deltaWeighted = 0, parityWeighted = 0, parityBase = 0;
      for (const row of rows) {
        const weight = Math.max(0, number(row.lookthrough));
        const rating = String(row.creditRating || "NR").toUpperCase();
        const score = number(row.creditScore);
        creditWeighted += weight * score;
        if (rating === "NR" || !rating) unrated += weight;
        else if (score >= 65) investment += weight;
        else speculative += weight;
        deltaWeighted += weight * number(row.delta);
        if (row.parity != null && Number.isFinite(Number(row.parity))) { parityWeighted += weight * number(row.parity); parityBase += weight; }
        const issuer = String(row.issuer || "미분류");
        issuers.set(issuer, (issuers.get(issuer) || 0) + weight);
      }
      const topIssuer = [...issuers.entries()].sort((a, b) => b[1] - a[1])[0];
      return {
        market,
        performance: {
          actualReturnPct: rounded(actualReturn), indexReturnPct: rounded(indexReturn), relativePp: rounded(relative),
          relativeAssessment: assessment(relative),
          relativeDisplay: relative == null ? "비교 불가" : `${relative >= 0 ? "Over" : "Under"} ${relative >= 0 ? "+" : ""}${relative.toFixed(2)}%p`,
        },
        sectorSignals: {
          primary: primarySectors,
          primaryStocks: primarySectors.flatMap((row) => row.topStocks).slice(0, 3),
          offset: offsetSectors,
          offsetStocks: offsetSectors.flatMap((row) => row.topStocks).slice(0, 3),
        },
        stockSignals: {
          primary: primaryDirection === "negative" ? negativeStocks : positiveStocks,
          offset: primaryDirection === "negative" ? positiveStocks : negativeStocks,
          characteristic: characteristicStocks,
        },
      };
    }),
  };
}

const instructions = `기관투자자용 메자닌 포트폴리오 성과분석을 자연스러운 한국어 존댓말로 작성하십시오.
모든 계산과 선별은 서버에서 끝났습니다. 입력 숫자만 해석하고 재계산, 외부 추정, 뉴스, 전망, 종목 펀더멘털을 추가하지 마십시오. 섹터는 모두 중분류 기준입니다.
코스닥 문단은 market='코스닥' 객체 안의 performance, sectorSignals, stockSignals만 사용하고, 코스피 문단은 market='코스피' 객체 안의 값만 사용하십시오. 다른 시장의 섹터·종목·비중을 가져오거나 두 시장을 합산하지 마십시오. sectorSignals.primary는 상대성과와 같은 방향의 핵심 섹터 요인이며, offset은 BM과 성과가 가까울 때 제공되는 반대 방향의 상쇄 요인입니다. stockSignals.primary는 같은 방향으로 손익 영향이 컸던 종목, offset은 반대 방향 종목, characteristic은 절대 손익 영향이 큰 종목 순서입니다.

출력 형식은 반드시 다음 순서와 표식을 지키십시오.
[코스닥]
코스닥 분석 문단

[코스피]
코스피 분석 문단

각 시장 문단은 정확히 세 문장으로 작성하십시오.
1. 첫 문장은 반드시 '포트폴리오는 코스닥보다 [relativeAssessment]입니다([relativeDisplay]).' 또는 코스피 형식으로 짧게 작성하고 입력값을 그대로 쓰십시오.
2. 이어지는 문장은 primary의 가장 중요한 중분류 섹터 하나를 먼저 설명한 뒤 stockSignals.primary의 특징적인 종목을 반드시 연결하십시오. 예: 'BM 대비 비중이 +3.20%p 높은 IT-하드웨어 섹터가 -1.10%로 약세를 보였고, 특히 A종목(-2.30%)과 B종목(-1.40%)이 부진했습니다.' 섹터만 설명하고 종목을 생략하지 마십시오.
3. stockSignals.offset이 있으면 대표 종목을 우선 언급하고, sectorSignals.offset이 있으면 해당 섹터도 함께 연결해 '다만 C종목(+1.20%)과 D종목(+0.80%), 생활소비재 섹터의 강세가 약세를 일부 만회했습니다.'처럼 설명하십시오. offset 종목이 없으면 stockSignals.primary 또는 characteristic에서 아직 쓰지 않은 다음 중요 종목을 골라 같은 방향의 영향을 설명하십시오. 확인되지 않은 상쇄 요인은 만들지 마십시오.
종목 데이터가 2개 이상이면 각 시장 문단에 서로 다른 특징 종목을 최소 2개, 최대 3개 반드시 포함하십시오. 단순 나열하지 말고 어떤 종목의 강세·약세가 주된 흐름을 만들거나 반대 흐름을 일부 상쇄했는지 자연스럽게 설명하십시오. 문장 구조와 접속사는 숫자의 방향에 맞게 바꾸십시오. 양수인 수익률·상대성과·비중 차이에는 + 부호를 붙이고 모든 숫자는 소수점 둘째 자리까지 표시하십시오. 비중·수익률은 %, 상대성과와 BM 대비 비중 차이는 %p입니다. 종목은 같은 시장의 제공된 목록에서 '종목명(+3.66%)' 형식으로 쓰십시오. 핵심 결론과 중요한 섹터명·종목명은 **굵게** 표시하되 문장 전체는 굵게 쓰지 마십시오. 델타, 패리티, 신용등급, 발행사 집중도, 기여도 수치, 내부 필드명, 계산법, 방법론, JSON, 제목, 기준일은 본문에서 언급하지 마십시오.`;

function outputText(payload: any) {
  if (typeof payload.output_text === "string") return payload.output_text.trim();
  const parts: string[] = [];
  for (const item of payload.output || []) for (const content of item.content || []) {
    if (content.type === "output_text" && content.text) parts.push(content.text);
  }
  return parts.join("\n").trim();
}

const resultKey = (data: Record<string, unknown>) => {
  const asOfDate = String(data.asOfDate || "").trim();
  const selectedFund = String(data.selectedFund || "").trim();
  if (!/^\d{4}-\d{2}-\d{2}$/.test(asOfDate)) throw new Error("성과분석 기준일이 올바르지 않습니다.");
  if (!selectedFund || selectedFund.length > 200) throw new Error("성과분석 대상 범위가 올바르지 않습니다.");
  return { asOfDate, selectedFund };
};

const sharedResult = (row: any) => ({
  analysis: row.analysis,
  model: row.model,
  usage: row.usage || {},
  generatedAt: row.generated_at,
  asOfDate: row.as_of_date,
  selectedFund: row.selected_fund,
  cached: true,
});

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  if (req.method !== "POST") return json({ error: "POST 요청만 지원합니다." }, 405);
  try {
    const user = await authorized(req);
    if (!user) return json({ error: "로그인 세션이 유효하지 않습니다." }, 401);
    const admin = createClient(Deno.env.get("SUPABASE_URL") || "", Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "", { auth: { persistSession: false, autoRefreshToken: false } });
    const { data: profile, error: profileError } = await admin.from("user_profiles").select("status,must_change_password").eq("user_id", user.id).maybeSingle();
    if (profileError) throw profileError;
    if (profile?.status !== "approved" || profile?.must_change_password) return json({ error: "승인된 사용자만 AI 성과분석을 이용할 수 있습니다." }, 403);
    const body = await req.json();
    const source = body && typeof body === "object" ? body as Record<string, unknown> : {};
    const { asOfDate, selectedFund } = resultKey(source);
    if (source.action === "latest") {
      const { data: cached, error } = await admin
        .from("stock_performance_ai_results")
        .select("as_of_date,selected_fund,analysis,model,usage,generated_at")
        .eq("as_of_date", asOfDate)
        .eq("selected_fund", selectedFund)
        .maybeSingle();
      if (error) throw error;
      return cached ? json(sharedResult(cached)) : json({ cached: false, analysis: null });
    }
    const apiKey = Deno.env.get("OPENAI_API_KEY") || "";
    if (!apiKey) throw new Error("OPENAI_API_KEY가 Edge Function secret에 설정되지 않았습니다.");
    const summary = prepareSummary(source);
    const response = await fetch("https://api.openai.com/v1/responses", {
      method: "POST",
      headers: { "Authorization": `Bearer ${apiKey}`, "Content-Type": "application/json" },
      body: JSON.stringify({ model: MODEL, reasoning: { effort: "low" }, store: false, max_output_tokens: 1400, instructions, input: JSON.stringify(summary), text: { verbosity: "low" } }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result?.error?.message || `OpenAI API HTTP ${response.status}`);
    const analysis = outputText(result);
    if (!analysis) throw new Error("OpenAI API 응답에 분석 문장이 없습니다.");
    const generatedAt = new Date().toISOString();
    const model = result.model || MODEL;
    const usage = result.usage || {};
    const { data: saved, error: saveError } = await admin
      .from("stock_performance_ai_results")
      .upsert({
        as_of_date: asOfDate,
        selected_fund: selectedFund,
        holdings_snapshot_date: source.holdingsSnapshotDate || null,
        analysis,
        model,
        usage,
        generated_at: generatedAt,
        generated_by: user.id,
      }, { onConflict: "as_of_date,selected_fund" })
      .select("as_of_date,selected_fund,analysis,model,usage,generated_at")
      .single();
    if (saveError) throw saveError;
    return json(sharedResult(saved));
  } catch (error) {
    return json({ error: error instanceof Error ? error.message : String(error) }, 400);
  }
});
