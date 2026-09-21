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

const FUND_RETURN_CODE_BY_NAME: Record<string, string> = {
  "밸류알레그로": "KRZ502611211", "밸류프레스토": "KRZ502630622",
  "웰컴하이일드1호": "KRZ502619770", "웰컴공모주2호": "KRZ502593210",
  "이지스드래곤4호": "KRZ502620720", "코람코하이일드45호": "KRZ502628640",
  "보고빌드업": "KRZ502578863", "현대인베1호": "KRZ502627860",
  "DB알파3호": "KRZ502609750", "브이엠하이일드": "KRZ502493854",
  "W1000": "KRZ502327923", "안다블루칩": "KRZ502363413",
  "VIP올인원": "KRZ502274243", "보고VOYAGE": "KRZ502575043",
  "블래쉬2호": "KRZ502671172", "타임폴리오EH": "KRZ502421551",
  "DB하이일드3호": "KRZ502641190", "빌리언폴드LS": "KRZ502501108",
};

const payloadNumber = (payload: Record<string, unknown>, ...keys: string[]) => {
  for (const key of keys) {
    const value = Number(payload[key]);
    if (payload[key] != null && payload[key] !== "" && Number.isFinite(value)) return value;
  }
  return null;
};

async function loadFundReturnSeries(admin: any, fundName: string) {
  const name = String(fundName || "").trim();
  const code = FUND_RETURN_CODE_BY_NAME[name];
  if (!code) throw new Error(`${name}의 기준가 매핑이 없습니다.`);
  const sourceRows: any[] = [];
  for (let offset = 0; ; offset += 1000) {
    const { data, error } = await admin.from("manual_file_rows")
      .select("row_no,payload")
      .eq("domain", "eq.fund")
      .eq("file_key", "eq.fund_nav")
      .filter("payload->>예탁원펀드코드", "eq", code)
      .order("row_no", { ascending: true })
      .range(offset, offset + 999);
    if (error) throw error;
    sourceRows.push(...(data || []));
    if ((data || []).length < 1000) break;
  }
  const manualDates = sourceRows.map((item) => String(item?.payload?.trade_day || item?.payload?.기준일 || ""))
    .filter((value) => /^\d{4}-\d{2}-\d{2}$/.test(value));
  const manualLatest = manualDates.sort().at(-1) || "";
  const { data: snapshots, error: snapshotError } = await admin.from("kfr_source_snapshots")
    .select("id,business_date,downloaded_at")
    .eq("source_key", "eq.fund_prices")
    .eq("source_format", "eq.kfr_partner_api_json")
    .order("business_date", { ascending: true })
    .order("downloaded_at", { ascending: true });
  if (snapshotError) throw snapshotError;
  const snapshotByDate = new Map<string, number>();
  for (const row of snapshots || []) snapshotByDate.set(String(row.business_date || ""), Number(row.id));
  const snapshotIds = [...snapshotByDate.entries()]
    .filter(([businessDate]) => !manualLatest || businessDate > manualLatest)
    .map(([, id]) => id);
  for (let start = 0; start < snapshotIds.length; start += 40) {
    const { data, error } = await admin.from("kfr_source_rows")
      .select("snapshot_id,row_no,payload")
      .in("snapshot_id", snapshotIds.slice(start, start + 40))
      .filter("payload->>fund_ksd_code", "eq", code)
      .order("snapshot_id", { ascending: true })
      .order("row_no", { ascending: true });
    if (error) throw error;
    sourceRows.push(...(data || []));
  }
  const byDate = new Map<string, Record<string, unknown>>();
  for (const item of sourceRows) {
    const payload = item?.payload && typeof item.payload === "object" ? item.payload as Record<string, unknown> : {};
    const tradeDate = String(payload.trade_day || payload["기준일"] || "").slice(0, 10);
    const cumulativeReturn = payloadNumber(payload, "cul_ret", "누적수익률");
    if (!/^\d{4}-\d{2}-\d{2}$/.test(tradeDate) || cumulativeReturn == null) continue;
    byDate.set(tradeDate, {
      date: tradeDate,
      fund: 1000 + cumulativeReturn * 10,
      kospi: payloadNumber(payload, "kospi", "KOSPI"),
      kosdaq: payloadNumber(payload, "kosdaq", "KOSDAQ"),
    });
  }
  const rows = [...byDate.values()].sort((a, b) => String(a.date).localeCompare(String(b.date)));
  if (rows.length < 2) throw new Error(`${name}의 기준가 관측치가 부족합니다.`);
  return { fund: { name, code }, dateMin: rows[0].date, dateMax: rows.at(-1)?.date, rows };
}

const fundStats = (rows: any[], key: string) => {
  const series = rows.map((row) => [String(row.date || ""), number(row[key])] as [string, number]).filter((row) => row[1] > 0);
  if (series.length < 2) return {} as Record<string, any>;
  const daily = series.slice(1).map((row, index) => row[1] / series[index][1] - 1);
  const periodReturn = series.at(-1)![1] / series[0][1] - 1;
  const average = daily.reduce((sum, value) => sum + value, 0) / daily.length;
  const variance = daily.reduce((sum, value) => sum + (value - average) ** 2, 0) / Math.max(1, daily.length - 1);
  const volatility = Math.sqrt(variance) * Math.sqrt(252);
  const annualReturn = periodReturn > -1 ? (1 + periodReturn) ** (252 / daily.length) - 1 : -1;
  let peak = series[0][1], mdd = 0;
  for (const [, value] of series) { peak = Math.max(peak, value); mdd = Math.min(mdd, value / peak - 1); }
  return {
    observations: series.length, periodReturnPct: rounded(periodReturn * 100),
    annualReturnPct: rounded(annualReturn * 100), annualVolatilityPct: rounded(volatility * 100),
    sharpe: rounded(volatility ? annualReturn / volatility : null), mddPct: rounded(mdd * 100), dailyReturns: daily,
  };
};

const fundMonths = (rows: any[], key: string) => {
  const grouped = new Map<string, number[]>();
  for (const row of rows) {
    const value = number(row[key]), month = String(row.date || "").slice(0, 7);
    if (value <= 0 || month.length !== 7) continue;
    if (!grouped.has(month)) grouped.set(month, []);
    grouped.get(month)!.push(value);
  }
  return [...grouped.entries()].filter(([, values]) => values.length > 1 && values[0])
    .map(([month, values]) => ({ month, returnPct: rounded((values.at(-1)! / values[0] - 1) * 100) }));
};

const analysisValue = (value: unknown, suffix = "", showSign = false) => {
  const numeric = number(value);
  return `${showSign && numeric > 0 ? "+" : ""}${numeric.toFixed(2)}${suffix}`;
};

function buildFundAnalysis(data: Record<string, any>, seriesPayload: any) {
  const fundName = String(data.fundName || "").trim();
  const startDate = String(data.startDate || ""), endDate = String(data.endDate || "");
  const benchmarkKey = String(data.benchmark || "").toLowerCase() === "kosdaq" ? "kosdaq" : "kospi";
  const benchmarkName = benchmarkKey === "kosdaq" ? "KOSDAQ" : "KOSPI";
  const rows = (seriesPayload.rows || []).filter((row: any) => row.date >= startDate && row.date <= endDate && number(row.fund) > 0 && number(row[benchmarkKey]) > 0);
  if (rows.length < 2) throw new Error("선택 기간의 펀드·BM 기준가 관측치가 부족합니다.");
  const fund = fundStats(rows, "fund"), benchmark = fundStats(rows, benchmarkKey);
  const fundDaily = fund.dailyReturns || [], benchmarkDaily = benchmark.dailyReturns || [];
  const pairCount = Math.min(fundDaily.length, benchmarkDaily.length);
  let beta: number | null = null;
  if (pairCount > 1) {
    const f = fundDaily.slice(-pairCount), b = benchmarkDaily.slice(-pairCount);
    const fm = f.reduce((sum: number, value: number) => sum + value, 0) / pairCount;
    const bm = b.reduce((sum: number, value: number) => sum + value, 0) / pairCount;
    const covariance = f.reduce((sum: number, value: number, index: number) => sum + (value - fm) * (b[index] - bm), 0) / (pairCount - 1);
    const variance = b.reduce((sum: number, value: number) => sum + (value - bm) ** 2, 0) / (pairCount - 1);
    beta = variance ? covariance / variance : null;
  }
  const relative = number(fund.periodReturnPct) - number(benchmark.periodReturnPct);
  const months = fundMonths(rows, "fund");
  const best = [...months].sort((a, b) => number(b.returnPct) - number(a.returnPct)).slice(0, 2);
  const worst = [...months].sort((a, b) => number(a.returnPct) - number(b.returnPct)).slice(0, 2);
  const performanceLines = [
    `펀드 기간수익률은 **${analysisValue(fund.periodReturnPct, "%", true)}**로, ${benchmarkName} 수익률 ${analysisValue(benchmark.periodReturnPct, "%", true)} 대비 **${analysisValue(relative, "%p", true)} ${relative > 0 ? "상회" : relative < 0 ? "하회" : "동일"}**했습니다.`,
  ];
  const monthParts: string[] = [];
  if (best.length) monthParts.push("강세 구간은 " + best.map((row) => `**${row.month}(${analysisValue(row.returnPct, "%", true)})**`).join(", "));
  if (worst.length) monthParts.push("약세 구간은 " + worst.map((row) => `**${row.month}(${analysisValue(row.returnPct, "%", true)})**`).join(", "));
  if (monthParts.length) performanceLines.push(monthParts.join("이며, ") + "입니다.");
  performanceLines.push(`연환산 변동성은 ${analysisValue(fund.annualVolatilityPct, "%")}이고 Sharpe는 ${analysisValue(fund.sharpe)}, 최대낙폭은 ${analysisValue(fund.mddPct, "%")}입니다.`);

  const positions = Array.isArray(data.positions) ? data.positions.slice(0, 3000) : [];
  const gross = positions.reduce((sum: number, row: any) => sum + Math.abs(number(row.exp)), 0);
  const marketValues = new Map<string, number>(), sectorValues = new Map<string, number>();
  const stockValues: Array<[string, number]> = [];
  for (const row of positions) {
    const value = Math.abs(number(row.exp)), market = String(row.market || "미분류");
    const sector = String(row.sectorMid || row.sectorLarge || "미분류");
    marketValues.set(market, (marketValues.get(market) || 0) + value);
    sectorValues.set(sector, (sectorValues.get(sector) || 0) + value);
    stockValues.push([String(row.name || "미분류"), value]);
  }
  const weighted = (source: Map<string, number>) => [...source.entries()].sort((a, b) => b[1] - a[1]).map(([name, value]) => ({ name, weightPct: gross ? value / gross * 100 : 0 }));
  const sortedStocks = [...stockValues].sort((a, b) => b[1] - a[1]);
  const hhi = stockValues.reduce((sum, row) => sum + (gross ? row[1] / gross : 0) ** 2, 0);
  const marketText = weighted(marketValues).slice(0, 2).map((row) => `**${row.name}** ${analysisValue(row.weightPct, "%")}`).join(", ") || "시장 정보 부족";
  const sectorText = weighted(sectorValues).slice(0, 3).map((row) => `**${row.name}** ${analysisValue(row.weightPct, "%")}`).join(", ") || "섹터 정보 부족";
  const investment = Math.abs(number(data.investment));
  const trades = Array.isArray(data.trades) ? data.trades.filter((row: any) => row.date >= startDate && row.date <= endDate).slice(0, 10000) : [];
  const grossTrades = trades.reduce((sum: number, row: any) => sum + Math.abs(number(row.amount)), 0);
  const turnover = investment ? grossTrades / (2 * investment) * Math.min(4, 252 / Math.max(1, rows.length - 1)) * 100 : null;
  const volatilityRatio = number(benchmark.annualVolatilityPct) ? number(fund.annualVolatilityPct) / number(benchmark.annualVolatilityPct) : null;
  const profile = beta != null && volatilityRatio != null ? (beta >= 1.10 || volatilityRatio >= 1.10 ? "공격적" : beta <= 0.90 && volatilityRatio <= 0.90 ? "방어적" : "중립적") : "판단 유보";
  const styleLines = [
    `시장 비중은 ${marketText}이며, 주요 섹터는 ${sectorText}입니다.`,
    `상위 1개 종목 비중은 ${analysisValue(gross && sortedStocks.length ? sortedStocks[0][1] / gross * 100 : 0, "%")}, 상위 5개는 ${analysisValue(gross ? sortedStocks.slice(0, 5).reduce((sum, row) => sum + row[1], 0) / gross * 100 : 0, "%")}이고 실질 분산 종목 수는 ${hhi ? (1 / hhi).toFixed(1) : "0.0"}개입니다.`,
    `연환산 추정 회전율은 ${analysisValue(turnover, "%")}, 베타는 ${analysisValue(beta)}, 변동성비율은 ${analysisValue(volatilityRatio)}으로 **${profile} 성향**입니다.`,
  ];

  const currentNames = new Set(positions.filter((row: any) => Math.abs(number(row.exp)) > 0).map((row: any) => String(row.name || "")));
  const tradeByName = new Map<string, { buy: number; sell: number }>();
  for (const row of trades) {
    const name = String(row.name || "미분류"), item = tradeByName.get(name) || { buy: 0, sell: 0 };
    if (String(row.side || "") === "매도") item.sell += Math.abs(number(row.amount)); else item.buy += Math.abs(number(row.amount));
    tradeByName.set(name, item);
  }
  const changes = [...tradeByName.entries()].map(([name, item]) => ({ name, netEok: (item.buy - item.sell) / 100_000_000, currentlyHeld: currentNames.has(name) }));
  const netBuys = changes.filter((row) => row.netEok > 0).sort((a, b) => b.netEok - a.netEok).slice(0, 5);
  const netSells = changes.filter((row) => row.netEok < 0).sort((a, b) => a.netEok - b.netEok).slice(0, 5);
  const named = (values: any[]) => values.slice(0, 3).map((row) => `**${row.name}** ${analysisValue(row.netEok, "억원", true)}`).join(", ");
  const changeLines: string[] = [];
  if (netBuys.length) changeLines.push(`주요 순매수는 ${named(netBuys)}입니다.`);
  if (netSells.length) changeLines.push(`주요 순매도는 ${named(netSells)}입니다.`);
  const entrants = netBuys.filter((row) => row.currentlyHeld).slice(0, 3);
  const exits = netSells.filter((row) => !row.currentlyHeld).slice(0, 3);
  const candidates: string[] = [];
  if (entrants.length) candidates.push("신규 편입 후보는 " + entrants.map((row) => `**${row.name}**`).join(", "));
  if (exits.length) candidates.push("전량 매도 후보는 " + exits.map((row) => `**${row.name}**`).join(", "));
  if (candidates.length) changeLines.push(candidates.join("이며, ") + "입니다.");
  const tradeStart = String(data.tradeDataStart || ""), tradeEnd = String(data.tradeDataEnd || "");
  if (tradeStart && tradeStart > startDate) changeLines.push(`가용 매매 데이터가 **${tradeStart}~${tradeEnd}**로 제한되어 이전 변화는 포함되지 않았습니다.`);
  if (!changeLines.length) changeLines.push("선택 기간에 확인 가능한 주요 매매 변화가 없습니다.");

  const contributions = positions.map((row: any) => {
    const cost = Math.abs(number(row.cost)), profit = number(row.profit);
    return { name: String(row.name || "미분류"), profitEok: profit / 100_000_000, returnPct: cost ? profit / cost * 100 : 0 };
  });
  const contributors = contributions.filter((row: any) => row.profitEok > 0).sort((a: any, b: any) => b.profitEok - a.profitEok).slice(0, 3);
  const detractors = contributions.filter((row: any) => row.profitEok < 0).sort((a: any, b: any) => a.profitEok - b.profitEok).slice(0, 3);
  const contributionLines: string[] = [];
  for (const [label, values] of [["성과 기여 상위", contributors], ["성과 훼손 상위", detractors]] as const) {
    if (values.length) contributionLines.push(`${label} 종목은 ` + values.map((row: any) => `**${row.name}** ${analysisValue(row.returnPct, "%", true)}, ${analysisValue(row.profitEok, "억원", true)}`).join(", ") + "입니다.");
  }
  contributionLines.push("기여도는 현재 보유 포지션의 누적 평가손익 기준이며 선택 기간의 정밀 성과귀속은 아닙니다.");
  return [
    "[성과 요약]\n" + performanceLines.join(" "),
    "[운용 스타일]\n" + styleLines.join(" "),
    "[포트폴리오 변화]\n" + changeLines.join(" "),
    "[성과 기여]\n" + contributionLines.join(" "),
  ].join("\n\n");
}
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

const validPeriodDate = (value: unknown) => /^\d{4}-\d{2}-\d{2}$/.test(String(value || ""));

async function loadPerformanceSnapshots(admin: any, fundScope: string, startDate: string, endDate: string) {
  if (!fundScope || fundScope.length > 200) throw new Error("조회 대상 펀드가 올바르지 않습니다.");
  if (!validPeriodDate(startDate) || !validPeriodDate(endDate) || startDate > endDate) {
    throw new Error("조회 기간이 올바르지 않습니다.");
  }
  const { data, error } = await admin.from("stock_performance_snapshots")
    .select("performance_date,holdings_snapshot_date,fund_scope,captured_at,calculation_version,payload")
    .eq("environment", "local_test")
    .eq("fund_scope", fundScope)
    .gte("performance_date", startDate)
    .lte("performance_date", endDate)
    .order("performance_date", { ascending: true });
  if (error) throw error;
  return data || [];
}

const compoundedReturn = (rates: number[]) => {
  if (!rates.length) return null;
  return (rates.reduce((factor, rate) => factor * (1 + rate / 100), 1) - 1) * 100;
};

function preparePeriodSummary(rows: any[], startDate: string, endDate: string, fundScope: string) {
  const markets = ["코스피", "코스닥"];
  const marketRates = new Map(markets.map((market) => [market, { actual: [] as number[], benchmark: [] as number[] }]));
  const marketDays = new Map(markets.map((market) => [market, 0]));
  const sectors = new Map<string, { market: string; sector: string; portfolioWeightSum: number; benchmarkWeightSum: number; contributionPp: number }>();
  const stocks = new Map<string, { market: string; code: string; name: string; weightSum: number; contributionPp: number; returns: number[] }>();
  const snapshotDates: string[] = [];
  const dailyAnalyses: any[] = [];

  for (const record of rows) {
    const payload: Record<string, any> = record?.payload && typeof record.payload === "object" ? record.payload : {};
    const positions = Array.isArray(payload.positions) ? payload.positions : [];
    const snapshotDate = String(record.performance_date || payload.asOfDate || "");
    if (snapshotDate) snapshotDates.push(snapshotDate);
    if (payload.dailyAnalysis && typeof payload.dailyAnalysis === "object" && String(payload.dailyAnalysis.analysis || "").trim()) {
      dailyAnalyses.push({
        date: snapshotDate,
        title: String(payload.dailyAnalysis.title || "AI 성과분석"),
        analysis: String(payload.dailyAnalysis.analysis || "").trim(),
        model: String(payload.dailyAnalysis.model || ""),
      });
    }
    const indexReturns: Record<string, any> = payload.marketIndexReturns && typeof payload.marketIndexReturns === "object" ? payload.marketIndexReturns : {};
    const benchmarkSectors: Record<string, any> = payload.benchmarkSectors && typeof payload.benchmarkSectors === "object" ? payload.benchmarkSectors : {};

    for (const market of markets) {
      const marketPositions = positions.filter((item: any) => String(item?.market || "") === market);
      const marketExp = marketPositions.reduce((sum: number, item: any) => sum + number(item?.exp), 0);
      const marketPl = marketPositions.reduce((sum: number, item: any) => sum + number(item?.pl), 0);
      if (!marketExp) continue;
      marketDays.set(market, (marketDays.get(market) || 0) + 1);
      marketRates.get(market)!.actual.push(marketPl / marketExp * 100);
      if (indexReturns[market] != null) marketRates.get(market)!.benchmark.push(number(indexReturns[market]));

      const grouped = new Map<string, any[]>();
      for (const item of marketPositions) {
        const sector = String(item?.sectorMid || item?.sectorLarge || "미분류");
        if (!grouped.has(sector)) grouped.set(sector, []);
        grouped.get(sector)!.push(item);
      }
      const benchmarkMid = benchmarkSectors?.[market]?.mid && typeof benchmarkSectors[market].mid === "object"
        ? benchmarkSectors[market].mid : {};
      const sectorNames = new Set([...grouped.keys(), ...Object.keys(benchmarkMid)]);
      for (const sector of sectorNames) {
        const items = grouped.get(sector) || [];
        const sectorExp = items.reduce((sum, item) => sum + number(item?.exp), 0);
        const sectorPl = items.reduce((sum, item) => sum + number(item?.pl), 0);
        const rawBenchmark = benchmarkMid[sector];
        const benchmarkWeight = number(rawBenchmark && typeof rawBenchmark === "object" ? rawBenchmark.weight : rawBenchmark);
        const key = `${market}\u0000${sector}`;
        const aggregate = sectors.get(key) || { market, sector, portfolioWeightSum: 0, benchmarkWeightSum: 0, contributionPp: 0 };
        aggregate.portfolioWeightSum += sectorExp / marketExp * 100;
        aggregate.benchmarkWeightSum += benchmarkWeight * 100;
        aggregate.contributionPp += sectorPl / marketExp * 100;
        sectors.set(key, aggregate);
      }

      for (const item of marketPositions) {
        const code = String(item?.code || item?.name || "");
        const key = `${market}\u0000${code}`;
        const aggregate = stocks.get(key) || { market, code, name: String(item?.name || code), weightSum: 0, contributionPp: 0, returns: [] as number[] };
        aggregate.weightSum += number(item?.exp) / marketExp * 100;
        aggregate.contributionPp += number(item?.pl) / marketExp * 100;
        if (item?.changeRatePct != null) aggregate.returns.push(number(item.changeRatePct));
        stocks.set(key, aggregate);
      }
    }
  }

  const marketRows = markets.map((market) => {
    const actual = compoundedReturn(marketRates.get(market)!.actual);
    const benchmark = compoundedReturn(marketRates.get(market)!.benchmark);
    return {
      market, days: marketDays.get(market) || 0,
      actualReturnPct: rounded(actual), benchmarkReturnPct: rounded(benchmark),
      relativePp: rounded(actual != null && benchmark != null ? actual - benchmark : null),
    };
  });
  const sectorRows = [...sectors.values()].map((item) => {
    const divisor = marketDays.get(item.market) || 1;
    const portfolioWeightPct = item.portfolioWeightSum / divisor;
    const benchmarkWeightPct = item.benchmarkWeightSum / divisor;
    return {
      market: item.market, sector: item.sector,
      portfolioWeightPct: rounded(portfolioWeightPct), benchmarkWeightPct: rounded(benchmarkWeightPct),
      activeWeightPp: rounded(portfolioWeightPct - benchmarkWeightPct), contributionPp: rounded(item.contributionPp),
    };
  }).sort((a, b) => Math.abs(number(b.contributionPp)) - Math.abs(number(a.contributionPp)));
  const stockRows = [...stocks.values()].map((item) => ({
    market: item.market, code: item.code, name: item.name,
    averageWeightPct: rounded(item.weightSum / (marketDays.get(item.market) || 1)),
    periodReturnPct: rounded(compoundedReturn(item.returns)), contributionPp: rounded(item.contributionPp),
  })).sort((a, b) => Math.abs(number(b.contributionPp)) - Math.abs(number(a.contributionPp)));
  return {
    startDate, endDate, selectedFund: fundScope, environment: "local_test",
    snapshotCount: rows.length, snapshotDates, marketRows, sectorRows, stockRows, dailyAnalyses,
    savedDailyAnalysis: dailyAnalyses.length === 1 ? dailyAnalyses[0] : null,
  };
}

const periodInstructions = `기관투자자용 기간별 BM 상대성과 분석을 자연스러운 한국어 존댓말로 작성하십시오.
입력 수치는 계산 엔진에서 산출됐으므로 재계산하거나 외부 뉴스·전망·펀더멘털을 추가하지 마십시오.
코스피와 코스닥을 분리하여 각각 한 문단으로 작성하고 각 문단은 3~4문장으로 제한하십시오.
첫 문장에는 기간 누적 포트폴리오 수익률, BM 수익률, 상대성과를 명확히 쓰십시오.
이후에는 같은 시장의 sectorRows와 stockRows만 이용해 강세 또는 약세의 핵심 원인을 설명하십시오.
섹터는 평균 포트폴리오 비중, 평균 BM 비중, BM 대비 비중 차이와 기간 기여도를 함께 고려하십시오.
종목은 기간 기여도가 특징적인 경우에만 시장별 최대 3개를 언급하십시오.
숫자는 소수점 둘째 자리까지 표시하고 양수에는 + 부호를 붙이십시오.
snapshotCount가 적으면 분석 첫머리에 데이터 커버리지가 제한적임을 짧게 알리십시오.
출력은 반드시 [코스피] 문단, 빈 줄, [코스닥] 문단 순서로 작성하십시오.
중요한 결론과 핵심 섹터·종목명은 **굵게** 표시하십시오.`;

async function analyzePeriodSummary(summary: any) {
  const apiKey = Deno.env.get("OPENAI_API_KEY") || "";
  if (!apiKey) throw new Error("OPENAI_API_KEY가 Supabase Edge Function secret에 설정되지 않았습니다.");
  const compact = {
    startDate: summary.startDate, endDate: summary.endDate, selectedFund: summary.selectedFund,
    snapshotCount: summary.snapshotCount, marketRows: summary.marketRows,
    sectorRows: (summary.sectorRows || []).slice(0, 16), stockRows: (summary.stockRows || []).slice(0, 20),
  };
  const response = await fetch("https://api.openai.com/v1/responses", {
    method: "POST",
    headers: { "Authorization": `Bearer ${apiKey}`, "Content-Type": "application/json" },
    body: JSON.stringify({
      model: MODEL, reasoning: { effort: "low" }, store: false, max_output_tokens: 1800,
      instructions: periodInstructions, input: JSON.stringify(compact), text: { verbosity: "low" },
    }),
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload?.error?.message || `OpenAI API HTTP ${response.status}`);
  if (payload.status === "incomplete") throw new Error(`기간 AI 분석 응답이 완성되기 전에 종료되었습니다: ${payload.incomplete_details?.reason || "unknown"}`);
  const analysis = outputText(payload);
  if (!analysis) throw new Error("OpenAI API 응답에 기간 분석 문장이 없습니다.");
  return { analysis, model: payload.model || MODEL, usage: payload.usage || {}, generatedAt: new Date().toISOString() };
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  if (req.method !== "POST") return json({ error: "POST 요청만 지원합니다." }, 405);
  try {
    const user = await authorized(req);
    if (!user) return json({ error: "로그인 세션이 유효하지 않습니다." }, 401);
    const data = await req.json();
    const source = data && typeof data === "object" ? data as Record<string, unknown> : {};
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
    if (source.action === "fund-return-series") {
      return json(await loadFundReturnSeries(admin, String(source.fundName || "")));
    }
    if (source.action === "fund-analysis") {
      const series = await loadFundReturnSeries(admin, String(source.fundName || ""));
      return json({
        analysis: buildFundAnalysis(source, series),
        model: "산출 엔진",
        usage: {},
        generatedAt: new Date().toISOString(),
      });
    }
    if (source.action === "period-summary" || source.action === "period-analysis") {
      const fundScope = String(source.fundScope || "").trim();
      const startDate = String(source.start || "").trim();
      const endDate = String(source.end || "").trim();
      const snapshots = await loadPerformanceSnapshots(admin, fundScope, startDate, endDate);
      const summary = preparePeriodSummary(snapshots, startDate, endDate, fundScope);
      if (source.action === "period-summary") return json(summary);
      if (!snapshots.length) throw new Error("선택한 기간에 저장된 마감 스냅샷이 없습니다.");
      return json({ ...(await analyzePeriodSummary(summary)), summary });
    }
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
