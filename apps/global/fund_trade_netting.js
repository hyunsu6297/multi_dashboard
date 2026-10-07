(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.FundTradeNetting = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  const fundKey = row => String(row.fundCode || row.fund || "").trim();
  const securityKey = row => String(row.code || row.bloombergIsin || row.ticker || row.security || row.name || "").trim().toUpperCase();
  const sideSign = row => {
    const side = String(row.side || "").trim();
    if (side === "매도") return -1;
    if (side === "매수") return 1;
    return Math.sign(Number(row.lookthrough ?? row.original ?? 0)) || 1;
  };

  function netTrades(trades) {
    const grouped = new Map();
    for (const row of trades || []) {
      const key = JSON.stringify([fundKey(row), row.date || "", securityKey(row)]);
      if (!grouped.has(key)) grouped.set(key, { ...row, qty: 0, original: 0, lookthrough: 0 });
      const net = grouped.get(key);
      net.qty += Math.abs(Number(row.qty || 0)) * sideSign(row);
      net.original += Math.abs(Number(row.original || 0)) * sideSign(row);
      net.lookthrough += (Number.isFinite(Number(row.lookthrough))
        ? Math.abs(Number(row.lookthrough)) : Math.abs(Number(row.original || 0)) * Number(row.fundShare ?? 1)) * sideSign(row);
    }
    return [...grouped.values()].filter(row => Math.abs(row.lookthrough) >= 0.5).map(row => {
      const nav = Number(row.tradeNav || 0);
      return { ...row, side: row.lookthrough > 0 ? "매수" : "매도", navPp: nav ? row.lookthrough / nav * 100 : null };
    });
  }
  return { netTrades };
});
