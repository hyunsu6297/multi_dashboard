import { createClient } from "npm:@supabase/supabase-js@2.95.0";

const MODEL = Deno.env.get("OPENAI_MODEL") || "gpt-5.4-mini";
const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Content-Type": "application/json; charset=utf-8",
};
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: cors });

async function authorized(req: Request) {
  const token = (req.headers.get("Authorization") || "").replace(/^Bearer\s+/i, "");
  if (!token) return null;
  const publishable = JSON.parse(Deno.env.get("SUPABASE_PUBLISHABLE_KEYS") || "{}").default
    || Deno.env.get("SUPABASE_ANON_KEY") || "";
  const client = createClient(Deno.env.get("SUPABASE_URL") || "", publishable);
  return (await client.auth.getUser(token)).data.user || null;
}

const number = (value: unknown) => {
  const result = Number(value ?? 0);
  return Number.isFinite(result) ? result : 0;
};
const rounded = (value: number | null) => value == null || !Number.isFinite(value)
  ? null
  : Number(value.toFixed(3));
const assessment = (value: number | null) => {
  if (value == null) return "비교 불가";
  const size = Math.abs(value) < 0.20 ? "소폭" : Math.abs(value) < 0.50 ? "다소" : "큰 폭";
  return `${size} ${value >= 0 ? "강세" : "약세"}`;
};
const signed = (value: number) => `${value >= 0 ? "+" : ""}${value.toFixed(2)}`;

type Position = {
  name?: string;
  code?: string;
  market?: string;
  sectorLarge?: string;
  sectorMid?: string;
  exp?: number;
  pl?: number;
  changeRatePct?: number | null;
  benchmarkKey?: string;
  benchmarkWeight?: number | null;
};

type Bucket = {
  codes: Set<string>;
  benchmarkKeys?: Set<string>;
  benchmarkWeight?: number;
  hasBenchmark?: boolean;
  exp: number;
  pl: number;
  rows?: Position[];
};

const compactPosition = (row: Position) => ({
  name: String(row.name || "미분류"),
  returnPct: rounded(number(row.changeRatePct)),
  contributionPp: null,
});

function prepareSummary(data: Record<string, unknown>) {
  const positions = Array.isArray(data.positions) ? data.positions as Position[] : [];
  const indexReturns = data.marketIndexReturns && typeof data.marketIndexReturns === "object"
    ? data.marketIndexReturns as Record<string, unknown>
    : {};
  const benchmarkSectors = data.benchmarkSectors && typeof data.benchmarkSectors === "object"
    ? data.benchmarkSectors as Record<string, any>
    : {};
  const hasFullBenchmark = ["코스피", "코스닥"].some((market) =>
    benchmarkSectors[market]?.mid && typeof benchmarkSectors[market].mid === "object"
  );
  const totalExp = positions.reduce((sum, row) => sum + number(row.exp), 0);
  const totalPl = positions.reduce((sum, row) => sum + number(row.pl), 0);
  const markets = new Map<string, Bucket>();
  const sectors = new Map<string, Bucket>();
  const marketBucket = (market: string) => {
    if (!markets.has(market)) markets.set(market, { codes: new Set(), exp: 0, pl: 0 });
    return markets.get(market)!;
  };
  const sectorBucket = (market: string, sector: string) => {
    const key = `${market}\u0000${sector}`;
    if (!sectors.has(key)) sectors.set(key, {
      codes: new Set(), benchmarkKeys: new Set(), benchmarkWeight: 0,
      hasBenchmark: false, exp: 0, pl: 0, rows: [],
    });
    return sectors.get(key)!;
  };

  for (const row of positions) {
    const market = String(row.market || "미분류");
    const sector = String(row.sectorMid || row.sectorLarge || "미분류");
    const code = String(row.code || row.name || "");
    const exp = number(row.exp), pl = number(row.pl);
    const mb = marketBucket(market);
    mb.codes.add(code); mb.exp += exp; mb.pl += pl;
    const sb = sectorBucket(market, sector);
    sb.codes.add(code); sb.exp += exp; sb.pl += pl; sb.rows!.push(row);
    if (!hasFullBenchmark && row.benchmarkWeight != null) {
      const key = String(row.benchmarkKey || `${market}|${code}`);
      if (!sb.benchmarkKeys!.has(key)) {
        sb.benchmarkKeys!.add(key);
        sb.benchmarkWeight! += number(row.benchmarkWeight);
        sb.hasBenchmark = true;
      }
    }
  }

  if (hasFullBenchmark) {
    for (const market of ["코스피", "코스닥"]) {
      const payload = benchmarkSectors[market]?.mid;
      if (!payload || typeof payload !== "object") continue;
      for (const [sector, raw] of Object.entries(payload)) {
        const sb = sectorBucket(market, sector || "미분류");
        sb.benchmarkWeight = number(typeof raw === "object" && raw ? (raw as any).weight : raw);
        sb.hasBenchmark = true;
      }
    }
  }

  const marketRows: Record<string, any>[] = [];
  let expectedTotal = 0, hasExpected = false;
  for (const market of ["코스피", "코스닥", "미분류"]) {
    const item = marketBucket(market);
    const actualReturn = item.exp ? item.pl / item.exp * 100 : null;
    const indexReturn = indexReturns[market] == null ? null : number(indexReturns[market]);
    const expectedPl = indexReturn == null ? null : item.exp * indexReturn / 100;
    if (expectedPl != null) { expectedTotal += expectedPl; hasExpected = true; }
    const relative = actualReturn == null || indexReturn == null ? null : actualReturn - indexReturn;
    marketRows.push({
      market,
      stockCount: item.codes.size,
      weightPct: rounded(totalExp ? item.exp / totalExp * 100 : null),
      actualReturnPct: rounded(actualReturn),
      indexReturnPct: rounded(indexReturn),
      relativePp: rounded(relative),
      relativeAssessment: assessment(relative),
      relativeDisplay: relative == null ? null : `${relative >= 0 ? "Over" : "Under"} ${signed(relative)}%p`,
      isNearBenchmark: relative != null && Math.abs(relative) <= 0.50,
      actualPlEok: rounded(item.pl / 100_000_000),
      expectedPlEok: rounded((expectedPl || 0) / 100_000_000),
    });
  }

  const marketSignals: Record<string, any> = {};
  for (const market of ["코스피", "코스닥"]) {
    const marketExp = marketBucket(market).exp;
    const signals: any[] = [];
    for (const [key, item] of sectors) {
      const [itemMarket, sector] = key.split("\u0000");
      if (itemMarket !== market || !item.hasBenchmark) continue;
      const portfolioWeight = marketExp ? item.exp / marketExp * 100 : 0;
      const benchmarkWeight = number(item.benchmarkWeight) * 100;
      const activeWeight = portfolioWeight - benchmarkWeight;
      const sectorReturn = item.exp ? item.pl / item.exp * 100 : null;
      const allocationSignal = sectorReturn == null ? null : activeWeight * sectorReturn / 100;
      const ranked = [...(item.rows || [])].sort((a, b) => Math.abs(number(b.pl)) - Math.abs(number(a.pl)));
      signals.push({
        sector,
        portfolioWeightPct: rounded(portfolioWeight),
        benchmarkWeightPct: rounded(benchmarkWeight),
        activeWeightPp: rounded(activeWeight),
        sectorReturnPct: rounded(sectorReturn),
        portfolioContributionPp: rounded(marketExp ? item.pl / marketExp * 100 : null),
        allocationSignalPp: rounded(allocationSignal),
        topStocks: ranked.slice(0, 3).map(compactPosition),
      });
    }
    const support = signals.filter((row) => number(row.allocationSignalPp) > 0)
      .sort((a, b) => number(b.allocationSignalPp) - number(a.allocationSignalPp)).slice(0, 3);
    const drag = signals.filter((row) => number(row.allocationSignalPp) < 0)
      .sort((a, b) => number(a.allocationSignalPp) - number(b.allocationSignalPp)).slice(0, 3);
    const notable = positions.filter((row) => String(row.market || "미분류") === market && row.benchmarkWeight != null)
      .map((row) => {
        const stockExp = number(row.exp), stockReturn = number(row.changeRatePct);
        const portfolioWeight = marketExp ? stockExp / marketExp * 100 : 0;
        const benchmarkWeight = number(row.benchmarkWeight) * 100;
        const activeWeight = portfolioWeight - benchmarkWeight;
        const contribution = marketExp ? number(row.pl) / marketExp * 100 : 0;
        return {
          name: String(row.name || "미분류"),
          portfolioWeightPct: rounded(portfolioWeight), benchmarkWeightPct: rounded(benchmarkWeight),
          activeWeightPp: rounded(activeWeight), returnPct: rounded(stockReturn),
          contributionPp: rounded(contribution), impactSignalPp: rounded(activeWeight * stockReturn / 100),
        };
      }).filter((row) => Math.abs(number(row.activeWeightPp)) >= 0.50
        && Math.abs(number(row.returnPct)) >= 1.00 && Math.abs(number(row.contributionPp)) >= 0.01);
    marketSignals[market] = {
      support, drag,
      supportStocks: notable.filter((row) => number(row.impactSignalPp) > 0)
        .sort((a, b) => number(b.impactSignalPp) - number(a.impactSignalPp)).slice(0, 3),
      dragStocks: notable.filter((row) => number(row.impactSignalPp) < 0)
        .sort((a, b) => number(a.impactSignalPp) - number(b.impactSignalPp)).slice(0, 3),
    };
  }

  const marketAnalysis = ["코스피", "코스닥"].map((market) => {
    const performance = marketRows.find((row) => row.market === market)!;
    const under = number(performance.relativePp) < 0;
    const primary = under ? "drag" : "support";
    const offset = under ? "support" : "drag";
    const signals = marketSignals[market] || { support: [], drag: [], supportStocks: [], dragStocks: [] };
    return {
      market,
      performance,
      analysisDirection: under ? "약세 원인" : "강세 원인",
      sectorSignals: {
        primary: signals[primary], primaryStocks: signals[`${primary}Stocks`],
        offset: performance.isNearBenchmark ? signals[offset] : [],
        offsetStocks: performance.isNearBenchmark ? signals[`${offset}Stocks`] : [],
      },
    };
  });
  const expectedReturn = totalExp && hasExpected ? expectedTotal / totalExp * 100 : null;
  const actualReturn = totalExp ? totalPl / totalExp * 100 : null;
  return {
    asOfDate: data.asOfDate,
    selectedFund: data.selectedFund,
    portfolio: {
      stockCount: new Set(positions.map((row) => String(row.code || row.name || ""))).size,
      stockExpEok: rounded(totalExp / 100_000_000), actualPlEok: rounded(totalPl / 100_000_000),
      actualReturnPct: rounded(actualReturn), benchmarkReturnPct: rounded(expectedReturn),
      relativePp: rounded(actualReturn == null || expectedReturn == null ? null : actualReturn - expectedReturn),
    },
    marketAnalysis,
  };
}

const instructions = `기관투자자용 BM 대비 상대성과 분석을 자연스러운 한국어 존댓말로 작성하십시오.
모든 계산과 선별은 서버에서 끝났습니다. 제공된 숫자만 해석하고 재계산, 외부 추정, 뉴스, 전망, 종목 펀더멘털을 추가하지 마십시오. 섹터는 모두 중분류 기준입니다.

입력의 marketAnalysis는 시장별로 완전히 분리되어 있습니다. 코스피 문단은 market='코스피' 객체 안의 performance와 sectorSignals만 사용하고, 코스닥 문단은 market='코스닥' 객체 안의 값만 사용하십시오. 다른 시장이나 전체 portfolio의 섹터·종목·비중을 가져오거나 두 시장을 합산하지 마십시오.
sectorSignals.primary는 Under이면 약세 원인, Over이면 강세 원인입니다. 두 번째 문장은 반드시 primary만 사용하십시오. sectorSignals.offset은 상대성과 절대값이 0.50%p 이하인 강보합·약보합권에서만 제공됩니다. offset이 비어 있으면 반대 방향 요인을 언급하지 마십시오.

출력 형식:
[코스피]
코스피 분석 문단

[코스닥]
코스닥 분석 문단

시장별 문단 규칙:
1. 첫 문장은 반드시 '포트폴리오는 코스피보다 [relativeAssessment]입니다([relativeDisplay]).' 또는 코스닥 형식으로 끝내고 입력값을 그대로 쓰십시오.
2. 두 번째 문장은 primary의 가장 중요한 중분류 섹터 하나를 골라 비중 차이와 섹터 수익률을 설명하십시오. 반드시 '필수-식음료 비중이 BM 대비 +8.66%p 높았으나'처럼 'BM 대비'와 activeWeightPp를 함께 쓰십시오.
3. offset이 비어 있으면 primary와 primaryStocks만 사용해 같은 방향 원인을 보강하십시오. offset이 있으면 반드시 offset과 offsetStocks만 사용해 반대 방향 요인이 일부 만회하거나 제한했다고 설명하십시오. 이때도 'BM 대비 비중이 +1.93%p 높은 IT-하드웨어'처럼 'BM 대비'와 activeWeightPp를 포함하십시오.
4. 각 시장은 정확히 세 문장만 쓰십시오. 한 문장에는 하나의 핵심만 담고 가능하면 70자를 넘기지 마십시오.
5. 양수에는 + 부호를 붙이고 모든 숫자는 소수점 둘째 자리까지 표시하십시오. 비중·수익률은 %, 상대성과와 비중 차이는 %p입니다.
6. 특징적인 종목은 같은 시장의 primaryStocks 또는 offsetStocks에서만 최대 3개를 '종목명(+3.66%)' 형식으로 쓰십시오.
7. 핵심 결론과 중요한 섹터명·종목명은 **굵게** 표시하되 문장 전체는 굵게 하지 마십시오.
8. 기여도 수치, 내부 필드명, 방법론, 제목, 기준일은 쓰지 마십시오.`;

function outputText(payload: any) {
  if (typeof payload.output_text === "string") return payload.output_text.trim();
  const parts: string[] = [];
  for (const item of payload.output || []) {
    for (const content of item.content || []) if (content.type === "output_text" && content.text) parts.push(content.text);
  }
  return parts.join("\n").trim();
}

const resultKey = (data: Record<string, unknown>) => {
  const asOfDate = String(data.asOfDate || "").trim();
  const selectedFund = String(data.selectedFund || "").trim();
  if (!/^\d{4}-\d{2}-\d{2}$/.test(asOfDate)) throw new Error("성과분석 기준일이 올바르지 않습니다.");
  if (!selectedFund || selectedFund.length > 200) throw new Error("성과분석 대상 펀드가 올바르지 않습니다.");
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
    const data = await req.json();
    const source = data && typeof data === "object" ? data as Record<string, unknown> : {};
    const { asOfDate, selectedFund } = resultKey(source);
    const supabaseUrl = Deno.env.get("SUPABASE_URL") || "";
    const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
    if (!serviceKey) throw new Error("Supabase service role key가 설정되지 않았습니다.");
    const admin = createClient(supabaseUrl, serviceKey, {
      auth: { persistSession: false, autoRefreshToken: false },
    });
    const { data: profile, error: profileError } = await admin
      .from("user_profiles")
      .select("status,must_change_password")
      .eq("user_id", user.id)
      .maybeSingle();
    if (profileError) throw profileError;
    if (profile?.status !== "approved" || profile?.must_change_password) {
      return json({ error: "승인된 사용자만 AI 성과분석을 이용할 수 있습니다." }, 403);
    }
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
    if (!apiKey) throw new Error("OPENAI_API_KEY가 Supabase Edge Function secret에 설정되지 않았습니다.");
    const summary = prepareSummary(source);
    const response = await fetch("https://api.openai.com/v1/responses", {
      method: "POST",
      headers: { "Authorization": `Bearer ${apiKey}`, "Content-Type": "application/json" },
      body: JSON.stringify({
        model: MODEL, reasoning: { effort: "low" }, store: false, max_output_tokens: 1600,
        instructions, input: JSON.stringify(summary), text: { verbosity: "low" },
      }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload?.error?.message || `OpenAI API HTTP ${response.status}`);
    if (payload.status === "incomplete") throw new Error(`AI 분석 응답이 완성되기 전에 종료되었습니다: ${payload.incomplete_details?.reason || "unknown"}`);
    const analysis = outputText(payload);
    if (!analysis) throw new Error("OpenAI API 응답에 분석 문장이 없습니다.");
    const generatedAt = new Date().toISOString();
    const model = payload.model || MODEL;
    const usage = payload.usage || {};
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
