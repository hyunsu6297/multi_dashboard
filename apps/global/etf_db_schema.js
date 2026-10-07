(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.EtfDbSchema = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  const gics = {
    "Energy": ["Energy"],
    "Materials": ["Materials"],
    "Industrials": ["Capital Goods", "Commercial & Professional Services", "Transportation"],
    "Consumer Discretionary": ["Automobiles & Components", "Consumer Durables & Apparel", "Consumer Services", "Consumer Discretionary Distribution & Retail"],
    "Consumer Staples": ["Consumer Staples Distribution & Retail", "Food, Beverage & Tobacco", "Household & Personal Products"],
    "Health Care": ["Health Care Equipment & Services", "Pharmaceuticals, Biotechnology & Life Sciences"],
    "Financials": ["Banks", "Financial Services", "Insurance"],
    "Information Technology": ["Software & Services", "Technology Hardware & Equipment", "Semiconductors & Semiconductor Equipment"],
    "Communication Services": ["Telecommunication Services", "Media & Entertainment"],
    "Utilities": ["Utilities"],
    "Real Estate": ["Equity Real Estate Investment Trusts (REITs)", "Real Estate Management & Development"],
  };
  // ETFs do not receive company-level GICS assignments. These are editable, name-based estimates.
  const byTicker = {
    GRID: ["Industrials", "Capital Goods"], SHLD: ["Industrials", "Capital Goods"],
    ARKX: ["Industrials", "Capital Goods"], TAN: ["Information Technology", "Semiconductors & Semiconductor Equipment"],
    URNM: ["Energy", "Energy"], NLR: ["Energy", "Energy"], ICLN: ["Utilities", "Utilities"],
    SMH: ["Information Technology", "Semiconductors & Semiconductor Equipment"],
    SOXX: ["Information Technology", "Semiconductors & Semiconductor Equipment"],
    IGV: ["Information Technology", "Software & Services"], XSW: ["Information Technology", "Software & Services"],
    XLK: ["Information Technology", "Technology Hardware & Equipment"], IYW: ["Information Technology", "Technology Hardware & Equipment"],
    ARTY: ["Information Technology", "Software & Services"], DTCR: ["Real Estate", "Equity Real Estate Investment Trusts (REITs)"],
    XLV: ["Health Care", "Health Care Equipment & Services"], VHT: ["Health Care", "Health Care Equipment & Services"],
    IYH: ["Health Care", "Health Care Equipment & Services"], IHI: ["Health Care", "Health Care Equipment & Services"],
    XBI: ["Health Care", "Pharmaceuticals, Biotechnology & Life Sciences"],
    XLE: ["Energy", "Energy"], VDE: ["Energy", "Energy"], IYE: ["Energy", "Energy"],
    XME: ["Materials", "Materials"], XLB: ["Materials", "Materials"], VAW: ["Materials", "Materials"], IYM: ["Materials", "Materials"],
    KBWB: ["Financials", "Banks"], XLF: ["Financials", "Financial Services"],
    VFH: ["Financials", "Financial Services"], IYF: ["Financials", "Financial Services"],
    KWEB: ["Consumer Discretionary", "Consumer Discretionary Distribution & Retail"],
    XLY: ["Consumer Discretionary", "Consumer Discretionary Distribution & Retail"],
    VCR: ["Consumer Discretionary", "Consumer Discretionary Distribution & Retail"],
    IYC: ["Consumer Discretionary", "Consumer Discretionary Distribution & Retail"],
    PEJ: ["Consumer Discretionary", "Consumer Services"],
    XLP: ["Consumer Staples", "Food, Beverage & Tobacco"], VDC: ["Consumer Staples", "Food, Beverage & Tobacco"],
    IYK: ["Consumer Staples", "Food, Beverage & Tobacco"],
    XLI: ["Industrials", "Capital Goods"], VIS: ["Industrials", "Capital Goods"], IYJ: ["Industrials", "Capital Goods"],
    XLC: ["Communication Services", "Media & Entertainment"], VOX: ["Communication Services", "Media & Entertainment"],
    IXP: ["Communication Services", "Media & Entertainment"], IYZ: ["Communication Services", "Telecommunication Services"],
    XLU: ["Utilities", "Utilities"], VPU: ["Utilities", "Utilities"], IDU: ["Utilities", "Utilities"],
    "139260": ["Information Technology", "Technology Hardware & Equipment"],
    "0173Y0": ["Information Technology", "Technology Hardware & Equipment"],
    "487230": ["Industrials", "Capital Goods"], "456600": ["Information Technology", "Software & Services"],
    "0167A0": ["Information Technology", "Semiconductors & Semiconductor Equipment"],
    SKYY: ["Information Technology", "Software & Services"], CIBR: ["Information Technology", "Software & Services"],
    HACK: ["Information Technology", "Software & Services"], EUFN: ["Financials", "Financial Services"],
    IBB: ["Health Care", "Pharmaceuticals, Biotechnology & Life Sciences"],
  };
  const tickerOf = etf => String(etf.ticker || etf.name || "").trim().split(/\s+/)[0].toUpperCase();
  const hasKorean = value => /[가-힣]/.test(String(value || ""));
  const validEnglish = value => value && !hasKorean(value) && !String(value).includes("�");
  const unclassified = value => !value || ["미분류", "GICS 미조회"].includes(String(value).trim());
  function applySuggestedGics(etf) {
    const result = { ...etf };
    const suggestion = result.large === "주식" ? byTicker[tickerOf(result)] : null;
    if (suggestion && unclassified(result.mid) && unclassified(result.small)) {
      [result.mid, result.small] = suggestion;
    }
    return result;
  }
  function normalize(etf, baseline = null) {
    const result = { ...etf };
    result.underlyingAsset = String(result.country || "").trim() === "한국" ? "N" : "Y";
    if (result.large === "대체자산") result.large = "대체";
    if (!["주식", "채권", "대체", "현금"].includes(result.large)) result.large = "대체";
    if (result.listing !== "한국" && result.large !== "현금" && hasKorean(result.koreanName)) {
      const english = baseline?.koreanName || baseline?.fullName || result.fullName;
      if (validEnglish(english)) result.koreanName = english;
    }
    if (result.large === "주식") {
      const classification = byTicker[tickerOf(result)];
      if (classification && (!gics[result.mid] || !gics[result.mid].includes(result.small))) {
        [result.mid, result.small] = classification;
      } else if (!gics[result.mid] || !gics[result.mid].includes(result.small)) {
        result.mid = "미분류";
        result.small = "미분류";
      }
    }
    return result;
  }
  function mergeBloombergAdditions(saved, embedded) {
    const merged = [...saved];
    const keys = new Set(merged.flatMap(etf => [etf.isin, etf.ticker].filter(Boolean).map(value => String(value).toUpperCase())));
    for (const etf of embedded) {
      if (!String(etf.source || "").startsWith("Bloomberg API")) continue;
      if (keys.has(String(etf.isin || "").toUpperCase()) || keys.has(String(etf.ticker || "").toUpperCase())) continue;
      const row = normalize(etf);
      merged.push(row);
      [row.isin, row.ticker].filter(Boolean).forEach(value => keys.add(String(value).toUpperCase()));
    }
    return merged;
  }
  return { gics, normalize, applySuggestedGics, tickerOf, mergeBloombergAdditions };
});
