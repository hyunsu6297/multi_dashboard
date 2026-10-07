(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.FundAllocationView = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  const indexByTicker = {
    SPY: "S&P 500", IVV: "S&P 500", VOO: "S&P 500", SPYM: "S&P 500",
    "360750": "S&P 500", "379800": "S&P 500", "449180": "S&P 500",
    QQQ: "NASDAQ 100", QQQM: "NASDAQ 100", "448300": "NASDAQ 100", "449190": "NASDAQ 100", "426030": "NASDAQ 100",
    IWM: "Russell 2000", DIA: "Dow Jones 30",
    "102110": "KOSPI 200", "451060": "KOSPI 200", "229200": "KOSDAQ 150",
    EWJ: "일본 지수", BBJP: "일본 지수", EWY: "한국 지수", EWC: "캐나다 지수",
    EWT: "대만 지수", EWP: "스페인 지수", EWZ: "브라질 지수", MCHI: "중국 지수",
    "283580": "중국 CSI 300", "371160": "중국 항셍테크",
    EFA: "선진국 지수", VEA: "선진국 지수", IEFA: "선진국 지수",
    EEM: "신흥국 지수", IEMG: "신흥국 지수", VWO: "신흥국 지수",
    VGK: "유럽 지수", EZU: "유럽 지수", VPL: "태평양 지수", EPP: "태평양 지수",
    AAXJ: "아시아 지수",
    SMH: "반도체", SOXX: "반도체", "0167A0": "반도체", IGV: "소프트웨어",
    XSW: "소프트웨어", XLK: "정보기술", IYW: "정보기술", "139260": "한국 IT",
    XLV: "헬스케어", XBI: "바이오", IHI: "의료기기", VHT: "헬스케어", IYH: "헬스케어",
    XLE: "에너지", VDE: "에너지", IYE: "에너지", XLF: "금융", VFH: "금융", IYF: "금융",
    KBWB: "은행", XLC: "커뮤니케이션", VOX: "커뮤니케이션", IXP: "커뮤니케이션",
    XLY: "경기소비재", XLP: "필수소비재", XLB: "소재", XLI: "산업재", XLU: "유틸리티",
    VCR: "경기소비재", VDC: "필수소비재", VAW: "소재", VIS: "산업재", VPU: "유틸리티",
    IYC: "경기소비재", IYK: "필수소비재", IYM: "소재", IYJ: "산업재", IDU: "유틸리티",
    GRID: "전력인프라", SHLD: "방산", ARKX: "우주·방산", TAN: "태양광",
    ICLN: "청정에너지", URNM: "우라늄", NLR: "원자력", KWEB: "중국 인터넷",
    ARTY: "AI", DTCR: "데이터센터", "0173Y0": "AI 광학", "487230": "AI 전력설비", "456600": "글로벌 AI",
  };
  const tickerOf = value => String(value || "").trim().toUpperCase().split(/\s+/)[0];
  // Bloomberg stock labels and editable ETF classifications can use different languages.
  // Normalize only the displayed grouping key; keep the ETF DB's original values intact.
  const gicsAliases = (entries) => {
    const aliases = new Map();
    for (const [label, variants] of entries) for (const variant of [label, ...variants]) {
      aliases.set(String(variant).toLowerCase().replace(/[\s&·,().-]/g, ""), label);
    }
    return aliases;
  };
  const gicsSectors = gicsAliases([
    ["에너지", ["Energy"]], ["소재", ["Materials"]], ["산업재", ["Industrials"]],
    ["경기소비재", ["Consumer Discretionary", "임의소비재"]],
    ["필수소비재", ["Consumer Staples"]], ["헬스케어", ["Health Care", "건강관리"]],
    ["금융", ["Financials"]], ["IT", ["Information Technology", "정보기술"]],
    ["커뮤니케이션", ["Communication Services", "커뮤니케이션서비스"]],
    ["유틸리티", ["Utilities", "공익사업"]], ["부동산", ["Real Estate"]],
  ]);
  const gicsIndustries = gicsAliases([
    ["에너지", ["Energy"]], ["소재", ["Materials"]],
    ["자본재", ["Capital Goods"]],
    ["상업·전문서비스", ["Commercial & Professional Services", "상업 및 전문 서비스"]],
    ["운송", ["Transportation"]],
    ["자동차·부품", ["Automobiles & Components", "자동차 및 부품"]],
    ["내구소비재·의류", ["Consumer Durables & Apparel", "내구 소비재 및 의류"]],
    ["소비자서비스", ["Consumer Services", "소비자 서비스"]],
    ["경기소비재 유통·소매", ["Consumer Discretionary Distribution & Retail"]],
    ["필수소비재 유통·소매", ["Consumer Staples Distribution & Retail"]],
    ["식품·음료·담배", ["Food, Beverage & Tobacco", "식품 음료 및 담배"]],
    ["가정·개인용품", ["Household & Personal Products", "가정 및 개인용품"]],
    ["헬스케어 장비·서비스", ["Health Care Equipment & Services", "건강관리 장비 및 서비스"]],
    ["제약·바이오·생명과학", ["Pharmaceuticals, Biotechnology & Life Sciences", "제약 바이오 생명과학"]],
    ["은행", ["Banks"]], ["금융서비스", ["Financial Services", "금융 서비스"]],
    ["보험", ["Insurance"]], ["소프트웨어·서비스", ["Software & Services", "소프트웨어 및 서비스"]],
    ["기술 하드웨어·장비", ["Technology Hardware & Equipment", "기술 하드웨어 및 장비"]],
    ["반도체·반도체 장비", ["Semiconductors & Semiconductor Equipment", "반도체 및 반도체 장비"]],
    ["통신서비스", ["Telecommunication Services", "통신 서비스"]],
    ["미디어·엔터테인먼트", ["Media & Entertainment", "미디어 및 엔터테인먼트"]],
    ["유틸리티", ["Utilities"]],
    ["리츠", ["Equity Real Estate Investment Trusts (REITs)"]],
    ["부동산 관리·개발", ["Real Estate Management & Development"]],
  ]);
  function gicsLabel(value, level) {
    const label = String(value || "").trim();
    if (!label || ["GICS 미조회", "미분류", "다중섹터", "해당 없음"].includes(label)) return "미분류";
    return (level === 1 ? gicsSectors : gicsIndustries).get(label.toLowerCase().replace(/[\s&·,().-]/g, "")) || label;
  }
  const regionOf = value => ({ DM: "선진국", EM: "신흥국", "글로벌": "글로벌", "미분류": "지역 미확인" }[String(value || "").trim()] || String(value || "").trim() || "지역 미확인");
  const isinCountryNames = { KR: "한국", US: "미국", JP: "일본", CN: "중국", TW: "대만", HK: "홍콩", GB: "영국", DE: "독일", FR: "프랑스", CA: "캐나다", AU: "호주", IN: "인도", SG: "싱가포르", CH: "스위스", NL: "네덜란드", IE: "아일랜드", LU: "룩셈부르크", KY: "케이맨 제도", BM: "버뮤다" };
  function stockRegionOf(row) {
    const isin = String(row.code || row.bloombergIsin || "").trim().toUpperCase();
    if (!/^[A-Z]{2}[A-Z0-9]{9}\d$/.test(isin)) return regionOf(row.country);
    const prefix = isin.slice(0, 2);
    if (isinCountryNames[prefix]) return isinCountryNames[prefix];
    if (prefix === "XS") return regionOf(row.country);
    const name = typeof Intl !== "undefined" && Intl.DisplayNames
      ? new Intl.DisplayNames(["ko"], { type: "region" }).of(prefix) : "";
    return name && name !== prefix ? name : regionOf(row.country);
  }
  function investmentRegionOf(row, etfs) {
    return row.instrumentKind === "stock" ? stockRegionOf(row) : regionOf(etfMeta(row, etfs)?.country || row.country);
  }
  function benchmarkOf(etf) {
    const explicit = String(etf.benchmark || "").trim();
    if (explicit) return explicit;
    const ticker = tickerOf(etf.ticker || etf.name);
    if (indexByTicker[ticker]) return indexByTicker[ticker];
    const name = `${etf.fullName || ""} ${etf.koreanName || ""} ${etf.name || ""}`.toUpperCase();
    if (/S&P\s*500/.test(name)) return "S&P 500";
    if (/NASDAQ\s*100|NSDQ\s*100|나스닥\s*100/.test(name)) return "NASDAQ 100";
    if (/RUSSELL\s*2000/.test(name)) return "Russell 2000";
    if (/DOW\s*JONES|다우/.test(name)) return "Dow Jones 30";
    if (/KOSDAQ\s*150|코스닥\s*150/.test(name)) return "KOSDAQ 150";
    if (/KOSPI\s*200|TIGER\s*200|KODEX\s*200/.test(name)) return "KOSPI 200";
    if (etf.mid && etf.mid !== "미분류") return "업종·테마";
    return "기타 주식 ETF";
  }
  function etfMeta(row, etfs) {
    const code = String(row.code || "").trim().toUpperCase();
    const ticker = tickerOf(row.security || row.ticker);
    return (etfs || []).find(etf => code && String(etf.isin || "").trim().toUpperCase() === code) ||
      (etfs || []).find(etf => ticker && tickerOf(etf.ticker || etf.name) === ticker) || null;
  }
  function describe(row, etfs) {
    const meta = row.instrumentKind === "stock" ? null : etfMeta(row, etfs);
    const asset = row.instrumentKind === "stock" ? "주식" : String(meta?.large || row.large || "기타");
    const unclassified = value => !value || ["미분류", "GICS 미조회", "다중섹터", "해당 없음"].includes(String(value).trim());
    if (asset !== "주식") return { asset, path: [row.mid || meta?.mid || "미분류", row.small || meta?.small || "미분류"] };
    if (row.instrumentKind === "stock") return { asset, path: [gicsLabel(row.large === "주식" ? "미분류" : row.large, 1), gicsLabel(row.small, 2)] };
    const gics1 = meta?.mid || row.mid;
    const gics2 = meta?.small || row.small;
    const benchmark = meta ? benchmarkOf(meta) : "미분류";
    if (unclassified(gics1)) return { asset, path: ["지수·전략 ETF", benchmark] };
    return { asset, path: [gicsLabel(gics1, 1), gicsLabel(gics2, 2)] };
  }
  function holdingSector(row, etfs, level) {
    const category = level === "large" ? 0 : 1;
    const classification = describe(row, etfs);
    if (classification.asset === "주식") return classification.path[category] || "미분류";
    const key = level === "large" && row.instrumentKind === "etf" ? "mid" : level;
    const value = String(row[key] || "").trim();
    return !value || value === "GICS 미조회" ? "미분류" : value;
  }
  function tree(rows, etfs) {
    const roots = new Map();
    for (const row of rows) {
      const value = Math.max(0, Number(row.lookthrough || 0));
      if (!Number.isFinite(value) || value === 0) continue;
      const parts = describe(row, etfs);
      const root = roots.get(parts.asset) || { label: parts.asset, value: 0, children: new Map() };
      roots.set(parts.asset, root);
      root.value += value;
      let parent = root;
      for (const label of parts.path.filter(Boolean)) {
        const child = parent.children.get(label) || { label, value: 0, children: new Map() };
        parent.children.set(label, child);
        child.value += value;
        parent = child;
      }
    }
    const assetOrder = ["주식", "채권", "대체", "현금"];
    const sort = (map, level = 0) => [...map.values()].sort((a, b) => level === 0
      ? (assetOrder.indexOf(a.label) < 0 ? assetOrder.length : assetOrder.indexOf(a.label)) -
        (assetOrder.indexOf(b.label) < 0 ? assetOrder.length : assetOrder.indexOf(b.label)) || a.label.localeCompare(b.label, "ko-KR")
      : b.value - a.value || a.label.localeCompare(b.label, "ko-KR"))
      .map(item => ({ ...item, children: sort(item.children, level + 1) }));
    const groups = sort(roots);
    return { total: groups.reduce((sum, group) => sum + group.value, 0), groups };
  }
  return { benchmarkOf, regionOf, investmentRegionOf, gicsLabel, describe, holdingSector, tree };
});
