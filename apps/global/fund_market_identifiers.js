(function (root) {
  const api = {
    isRepoTrade(row) {
      return [row.asset, row.market, row.name, row.code, row.ticker, row.security]
        .some(value => /repo|레포|환매조건부|(?:^|[^a-z])r\/?p(?:[^a-z]|$)/i.test(String(value || "")));
    },
    isForward(row) {
      if (!row.isFx && !/선물옵션파생/.test(String(row.asset || ""))) return false;
      return /^FWD\b/i.test(String(row.name || "").trim()) ||
        /^FXW/i.test(String(row.code || "").trim()) ||
        /FX\s*SWAP/i.test(String(row.market || ""));
    },
    hedgeExposure(row) {
      if (api.isForward(row)) {
        if (row.rawInvestAmt == null || row.rawInvestAmt === "") return null;
        return Math.abs(Number(row.rawInvestAmt) * Number(row.fundShare ?? 1));
      }
      return Math.abs(Number(row.lookthrough || row.original || 0));
    },
    etfMeta(row, etfs = []) {
      const key = value => String(value || "").trim().toUpperCase();
      const code = key(row.code), name = key(row.name), security = key(row.security || row.ticker);
      return etfs.find(e => (code && key(e.isin) === code) ||
        (name && [key(e.name), key(e.koreanName), key(e.fullName)].includes(name)) ||
        (security && [key(e.ticker), key(e.name)].includes(security))) || null;
    },
    kind(row, reference = {}, etfs = []) {
      const types = `${reference.securityType || row.securityType || ""} ${reference.securityType2 || row.securityType2 || ""}`;
      if (/\b(?:ETP|ETF|ETN)\b|Exchange Traded/i.test(types)) return "etf";
      if (/Common Stock|Preferred Stock|Preference|Depositary|\bADR\b|\bGDR\b|REIT|Ordinary Shares|\bEquity\b/i.test(types)) return "stock";
      if (types.trim()) return "other";
      if (api.etfMeta(row, etfs)) return "etf";
      if (/ETF|ETN/.test(String(row.asset || "") + String(row.name || ""))) return "etf";
      if (/주식/.test(String(row.asset || "") + String(row.market || ""))) return "stock";
      return "other";
    },
    stockTicker(row, reference = {}) {
      const isin = String(reference.isin || row.bloombergIsin || row.code || "").trim().toUpperCase();
      const ticker = String(reference.ticker || row.bloombergTicker || "").trim().toUpperCase();
      const security = String(row.security || "").trim();
      if (/^KR/.test(isin) || /\s(?:KS|KQ)\s+Equity$/i.test(security) || /코스닥|코스피|거래소상장|유가증권/.test(String(row.market || ""))) {
        if (/^\d{1,6}$/.test(ticker)) return ticker.padStart(6, "0");
        if (/^[A-Z0-9]{6}$/.test(ticker)) return ticker;
        if (/^KR7[A-Z0-9]{6}\d{3}$/.test(isin)) return isin.slice(3, 9);
        if (/^[A-Z0-9]{6}$/.test(isin)) return isin;
      }
      if (/^[A-Z][A-Z0-9./-]*$/.test(ticker)) return ticker;
      const match = security.match(/^([A-Z][A-Z0-9./-]*)\s+US\s+Equity$/i);
      return match ? match[1].toUpperCase() : "";
    },
    referenceFor(row, securities = {}, etfs = []) {
      const code = String(row.code || "").trim().toUpperCase();
      const isin = String(row.bloombergIsin || code).trim().toUpperCase();
      const keys = [api.identifier(row, etfs), `/isin/${isin}`, code, row.security, row.ticker,
        row.bloombergTicker && `${row.bloombergTicker} US Equity`].filter(Boolean);
      // Prefer metadata-bearing responses over legacy price-only cache entries.
      return keys.map(key => securities[key]).find(value => value?.securityType || value?.ticker || value?.gicsLevel1)
        || keys.map(key => securities[key]).find(Boolean) || null;
    },
    applyMetadata(row, reference = {}, etfs = []) {
      if (row.isFx || /선물옵션파생/.test(String(row.asset || ""))) return row;
      const kind = api.kind(row, reference, etfs);
      row.instrumentKind = kind;
      if (reference.securityType) row.securityType = reference.securityType;
      if (reference.securityType2) row.securityType2 = reference.securityType2;
      if (reference.ticker) row.bloombergTicker = reference.ticker;
      if (reference.isin) row.bloombergIsin = reference.isin;
      if (kind === "etf") {
        const meta = api.etfMeta(row, etfs) || {};
        row.ticker = meta.name || meta.ticker || "";
        row.displayTicker = String(meta.ticker || meta.name || "ETF DB 미등록").replace(/\s+\w+\s+Equity$/i, "");
        ["large", "mid", "small", "country", "listing"].forEach(key => row[key] = meta[key] || "미분류");
        row.underlyingAsset = meta.underlyingAsset || "";
        row.classificationSource = "ETF DB";
      } else if (kind === "stock") {
        row.displayTicker = api.stockTicker(row, reference) || "티커 미조회";
        row.ticker = row.displayTicker === "티커 미조회" ? "" : row.displayTicker;
        // GICS level 2 is industry GROUP, not the level 3 industry field.
        row.large = reference.gicsLevel1 || row.gicsLevel1 || (row.large && row.large !== "GICS 미조회" ? row.large : "미분류");
        row.small = reference.gicsLevel2 || row.gicsLevel2 || (row.small && row.small !== "GICS 미조회" ? row.small : "미분류");
        if (reference.gicsLevel1) row.gicsLevel1 = reference.gicsLevel1;
        if (reference.gicsLevel2) row.gicsLevel2 = reference.gicsLevel2;
        row.mid = "미분류";
        row.classificationSource = "Bloomberg GICS";
      }
      return row;
    },
    identifier(row, etfs = []) {
      if (row.isFx || /선물옵션파생/.test(String(row.asset || ""))) return "";
      const code = String(row.code || "").trim().toUpperCase();
      const meta = row.instrumentKind === "stock" ? {} : api.etfMeta(row, etfs) || {};
      const market = String(row.market || "");
      if (/현금|예금|증거금|레포/.test(market + String(row.asset || ""))) return "";
      // Identify the raw security first: an ETF DB match must not redirect a stock's quote.
      if (/^[A-Z]{2}[A-Z0-9]{9}\d$/.test(code)) return `/isin/${code}`;
      if (row.instrumentKind === "stock" && /^\d{6}$/.test(code)) {
        if (/코스닥|KOSDAQ/i.test(market)) return `${code} KQ Equity`;
        if (/유가증권|거래소상장|코스피|KOSPI/i.test(market)) return `${code} KS Equity`;
      }
      const security = String(meta.ticker || row.security || row.ticker || "").trim();
      if (/\s(?:Equity|Corp|Govt|Index|Curncy|Comdty)$/i.test(security)) return security;
      const isin = String(meta.isin || code).trim().toUpperCase();
      if (/^[A-Z]{2}[A-Z0-9]{9}\d$/.test(isin)) return `/isin/${isin}`;
      if (/비상장|장외/.test(market + String(row.asset || ""))) return "";
      if (/^\d{6}$/.test(code)) {
        if (/코스닥|KOSDAQ/i.test(market)) return `${code} KQ Equity`;
        if (/유가증권|거래소상장|코스피|KOSPI/i.test(market)) return `${code} KS Equity`;
      }
      return "";
    }
  };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.FundMarketIdentifiers = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
