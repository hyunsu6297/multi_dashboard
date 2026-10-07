(function (root) {
  const isinPattern = /^[A-Z]{2}[A-Z0-9]{9}\d$/;
  const clean = value => String(value || "").trim();
  const upper = value => clean(value).toUpperCase();
  const hasKorean = value => /[가-힣]/.test(clean(value));

  function candidates(rows, etfs) {
    const known = new Set(etfs.map(etf => upper(etf.isin)).filter(Boolean));
    const knownTickers = new Set(etfs.flatMap(etf => [etf.ticker, etf.name])
      .map(value => upper(value).split(/\s+/)[0]).filter(Boolean));
    const found = new Map();
    for (const row of rows) {
      if (row.isFx) continue;
      const isin = upper(row.code || row.bloombergIsin);
      const ticker = upper(row.bloombergTicker || row.ticker || row.security).split(/\s+/)[0];
      if (!isinPattern.test(isin) || known.has(isin) || found.has(isin) ||
          (ticker && knownTickers.has(ticker))) continue;
      found.set(isin, { isin, security: `/isin/${isin}`, rawName: clean(row.name),
        market: clean(row.market), asset: clean(row.asset) });
    }
    return [...found.values()];
  }

  function isEtf(reference) {
    const type = `${reference?.securityType || ""} ${reference?.securityType2 || ""}`;
    return /\b(?:ETF|ETP|ETN)\b|Exchange Traded/i.test(type);
  }

  function assetClass(reference, candidate) {
    const focus = upper(reference.assetClassFocus);
    if (/EQUITY|STOCK|주식/.test(focus)) return "주식";
    if (/FIXED INCOME|BOND|DEBT|채권/.test(focus)) return "채권";
    if (/MONEY MARKET|CASH|현금/.test(focus)) return "현금";
    if (/COMMODITY|ALTERNATIVE|REAL ESTATE|대체/.test(focus)) return "대체";
    const source = `${candidate.asset} ${candidate.market}`;
    if (/주식/.test(source)) return "주식";
    if (/채권/.test(source)) return "채권";
    return "대체";
  }

  function rowFor(candidate, reference) {
    if (!isEtf(reference)) return null;
    const isin = upper(reference.isin || candidate.isin);
    if (isin !== candidate.isin || !isinPattern.test(isin)) return null;
    const ticker = upper(reference.ticker);
    if (!ticker) return null;
    const exchange = upper(reference.exchangeCode);
    const listing = ["US", "KS", "KQ", "KR"].includes(exchange)
      ? exchange === "US" ? "미국" : "한국" : exchange || "미분류";
    const englishName = [reference.name, reference.longName, candidate.rawName]
      .map(clean).find(value => value && !hasKorean(value)) || clean(reference.name || reference.longName || candidate.rawName);
    const country = clean(reference.geoFocus) || (listing === "미국" || listing === "한국" ? listing : "미분류");
    return { isin, ticker: `${ticker}${exchange ? ` ${exchange} Equity` : ""}`,
      name: ticker, fullName: clean(reference.longName || reference.name) || englishName,
      koreanName: englishName, listing, country, benchmark: clean(reference.benchmark),
      underlyingAsset: country === "한국" ? "N" : "Y", large: assetClass(reference, candidate),
      mid: "미분류", small: "미분류", source: "Bloomberg API · 미등록 ETF 등록" };
  }

  const api = { candidates, isEtf, rowFor };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.FundEtfDiscovery = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
