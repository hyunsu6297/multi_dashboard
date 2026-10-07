(function (root) {
  const finite = value => value != null && value !== "" && Number.isFinite(Number(value));
  const tickerKey = value => String(value || "").split(" ")[0].trim().toUpperCase();

  function isUsdExposure(row, etfs) {
    if (row.instrumentKind === "stock" && row.marketCurrency) {
      return String(row.marketCurrency).trim().toUpperCase() === "USD";
    }
    const key = tickerKey(row.ticker || row.security || row.name);
    const meta = row.instrumentKind === "stock" ? {} :
      etfs.find(etf => [etf.name, etf.ticker].some(value => tickerKey(value) === key)) || {};
    return String(meta.listing || row.listing || "").includes("미국") ||
      String(row.country || "").includes("미국") ||
      (row.instrumentKind === "stock" &&
        (/^US[A-Z0-9]{9}\d$/i.test(String(row.bloombergIsin || row.code || "")) ||
          /\sUS\s+Equity$/i.test(String(row.security || ""))));
  }

  function isForeignStock(row) {
    if (row.instrumentKind !== "stock") return false;
    const country = String(row.country || "").trim();
    if (/^(?:한국|대한민국|KR|KOREA)$/i.test(country)) return false;
    if (country && !/^(?:미분류|unknown|N\/A|-)$/i.test(country)) return true;
    const isin = String(row.bloombergIsin || row.code || "").trim().toUpperCase();
    if (/^[A-Z]{2}[A-Z0-9]{9}\d$/.test(isin)) return !isin.startsWith("KR");
    return /해외주식|외국주식|해외상장|외국상장/.test(String(row.market || ""));
  }

  function isForeignInvestmentCountry(value) {
    const country = String(value || "").trim();
    return !!country && !/^(?:한국|대한민국|국내|KR|KOREA|미분류|unknown|N\/A|-)$/i.test(country);
  }

  function isCurrencyHedgedEtf(row, meta) {
    return [meta.fullName, meta.koreanName, meta.name, row.name, row.security]
      .some(value => /(?:\(H\)|환헤지|환헷지)/i.test(String(value || "")));
  }

  function isHedgeExposure(row, etfs) {
    if (row.isFx) return false;
    if (/short|매도/i.test(String(row.position || "")) || Number(row.lookthrough) < 0) return false;
    const rawOverseas = /해외상품/.test(String(row.asset || ""));
    if (row.instrumentKind === "stock") return rawOverseas || isForeignStock(row);
    if (row.instrumentKind !== "etf") return rawOverseas;
    const code = String(row.code || "").trim().toUpperCase();
    const key = tickerKey(row.ticker || row.security);
    const name = String(row.name || "").trim().toUpperCase();
    const meta = (etfs || []).find(etf => code && String(etf.isin || "").trim().toUpperCase() === code) ||
      (etfs || []).find(etf =>
        (key && tickerKey(etf.ticker) === key) ||
        (name && String(etf.name || "").trim().toUpperCase() === name)) || {};
    const domestic = code.startsWith("KR") || /\s(?:KS|KQ)\s+Equity$/i.test(String(row.security || "")) ||
      /^(?:한국|국내|KR)$/i.test(String(meta.listing || row.listing || "").trim());
    if (domestic) {
      const underlyingAsset = String(meta.underlyingAsset || row.underlyingAsset || "").trim();
      if (underlyingAsset === "N" || underlyingAsset === "국내자산" || isCurrencyHedgedEtf(row, meta)) return false;
      return underlyingAsset === "Y" || underlyingAsset === "해외자산" ||
        isForeignInvestmentCountry(meta.country || row.country);
    }
    // Raw overseas products and foreign listings count even without ETF DB metadata.
    if (rawOverseas) return true;
    if (/^[A-Z]{2}[A-Z0-9]{9}\d$/.test(code)) return !code.startsWith("KR");
    return /해외상장|외국상장/.test(String(row.market || "")) ||
      /\s(?!KS\b|KQ\b)[A-Z]{2}\s+(?:Equity|ETF)$/i.test(String(row.security || ""));
  }

  function usesFxEstimate(item) {
    return /^하나\s*TDF/i.test(String(item.fund || "")) ||
      /마이다스\s*EMP/i.test(String(item.fund || "")) ||
      /머스트\s*(?:8|10)\s*호/i.test(String(item.fund || "")) ||
      String(item.fundCode || "") === "K55303EY6676";
  }

  function isReturnOnlyFund(fund) {
    return /^\s*머스트\s*(?:8|9|10|11)\s*호/.test(String(fund || ""));
  }

  function calculate(holdings, etfs, fxChange, hedgeExposure) {
    const byFund = new Map();
    for (const row of holdings) {
      const key = row.fundCode || row.fund;
      if (!byFund.has(key)) byFund.set(key, {
        fund: row.fund, fundCode: row.fundCode, returnOnly: isReturnOnlyFund(row.fund),
        heldAmount: 0, pricedAmount: 0,
        basePnl: 0, usdExposure: 0, hedgeDenominator: 0,
        hedgeAmount: 0, hedgeMissing: false
      });
      const item = byFund.get(key);
      if (row.isFx) {
        const hedge = hedgeExposure(row);
        if (!finite(hedge)) item.hedgeMissing = true;
        else item.hedgeAmount += Number(hedge);
        continue;
      }
      const amount = Number(row.lookthrough || 0);
      item.heldAmount += amount;
      if (finite(row.marketChange)) {
        item.pricedAmount += Math.abs(amount);
        item.basePnl += amount * Number(row.marketChange);
      }
      if (isUsdExposure(row, etfs)) item.usdExposure += Math.abs(amount);
      if (isHedgeExposure(row, etfs)) item.hedgeDenominator += Math.abs(amount);
    }
    return [...byFund.values()].map(item => {
      const hedgeRatio = item.hedgeDenominator && !item.hedgeMissing
        ? item.hedgeAmount / item.hedgeDenominator : null;
      const estimateFx = usesFxEstimate(item);
      const unhedgedExposure = Math.max(0, item.hedgeDenominator - item.hedgeAmount);
      const fxPnl = !estimateFx ? 0 : item.hedgeMissing ? null : unhedgedExposure === 0 ? 0
        : finite(fxChange) ? unhedgedExposure * Number(fxChange) : null;
      const adjustedPnl = fxPnl == null ? null : item.basePnl + fxPnl;
      return {
        ...item, hedgeRatio, estimateFx, unhedgedExposure,
        unhedgedWeight: item.heldAmount ? unhedgedExposure / item.heldAmount : null,
        fxChange: estimateFx && finite(fxChange) ? Number(fxChange) : null, fxPnl, adjustedPnl,
        baseReturn: item.heldAmount ? item.basePnl / item.heldAmount : null,
        adjustedReturn: adjustedPnl != null && item.heldAmount ? adjustedPnl / item.heldAmount : null,
        quoteCoverage: item.heldAmount ? item.pricedAmount / Math.abs(item.heldAmount) : null
      };
    });
  }

  function holdingPnl(row, fundResult, etfs) {
    if (!fundResult || fundResult.returnOnly || row.isFx) return null;
    const amount = Number(row.lookthrough || 0);
    const fxEligible = fundResult.estimateFx && isHedgeExposure(row, etfs);
    if (!finite(row.marketChange) && !fxEligible) return null;
    const basePnl = finite(row.marketChange) ? amount * Number(row.marketChange) : 0;
    let fxPnl = 0;
    if (fxEligible) {
      if (fundResult.fxPnl == null) return null;
      fxPnl = fundResult.hedgeDenominator
        ? fundResult.fxPnl * Math.abs(amount) / fundResult.hedgeDenominator : 0;
    }
    return { basePnl, fxPnl, adjustedPnl: basePnl + fxPnl };
  }

  const api = { calculate, holdingPnl, isUsdExposure, isForeignStock, isHedgeExposure, isReturnOnlyFund };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.FundPerformance = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
