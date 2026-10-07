(function (root) {
  const normalized = value => String(value || "").trim().toUpperCase();

  function assetKey(row) {
    const code = normalized(row.code || row.bloombergIsin);
    if (code) return `code:${code}`;
    const security = normalized(row.security || row.ticker);
    if (security) return `security:${security}`;
    return `name:${normalized(row.name)}|${normalized(row.market)}|${normalized(row.asset)}`;
  }

  function group(rows, isReturnOnlyFund, pnlForRow) {
    const assets = new Map();
    for (const row of rows) {
      const key = assetKey(row);
      if (!assets.has(key)) assets.set(key, { key, row, funds: new Map() });
      const asset = assets.get(key);
      const fundKey = row.fundCode || row.fund;
      if (!asset.funds.has(fundKey)) asset.funds.set(fundKey, {
        fund: row.fund, fundCode: row.fundCode, returnOnly: isReturnOnlyFund(row.fund),
        qty: 0, lookthrough: 0, investment: Number(row.investment || 0),
        priceAmount: 0, priceQty: 0, pnl: 0, pnlMissing: false
      });
      const fund = asset.funds.get(fundKey);
      fund.qty += Number(row.qty || 0);
      fund.investment = Math.max(fund.investment, Number(row.investment || 0));
      const qty = Number(row.qty || 0);
      if (Number.isFinite(Number(row.price)) && Number(row.price) > 0 && qty > 0) {
        fund.priceAmount += qty * Number(row.price);
        fund.priceQty += qty;
      }
      if (fund.returnOnly) continue;
      fund.lookthrough += Number(row.lookthrough || 0);
      const pnl = pnlForRow(row);
      if (pnl == null || !Number.isFinite(Number(pnl))) fund.pnlMissing = true;
      else fund.pnl += Number(pnl);
    }
    return [...assets.values()].map(asset => {
      const members = [...asset.funds.values()].map(fund => ({
        ...fund, price: fund.priceQty ? fund.priceAmount / fund.priceQty : null,
        pnl: fund.returnOnly || fund.pnlMissing ? null : fund.pnl
      })).sort((a, b) => a.fund.localeCompare(b.fund, "ko-KR", { numeric: true }));
      const counted = members.filter(fund => !fund.returnOnly);
      const lookthrough = counted.length ? counted.reduce((sum, fund) => sum + fund.lookthrough, 0) : null;
      const pnl = counted.length && counted.every(fund => fund.pnl != null)
        ? counted.reduce((sum, fund) => sum + fund.pnl, 0) : null;
      return { ...asset.row, assetKey: asset.key, members,
        fundCount: members.length, lookthrough, pnl };
    });
  }

  const api = { assetKey, group };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.FundHoldingGroups = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
