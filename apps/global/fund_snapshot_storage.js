(function (root) {
  const key = "globalDashboard.fundSnapshot";
  const valid = value => value && value.version === 1 &&
    Array.isArray(value.holdings) && Array.isArray(value.trades) &&
    [...value.holdings, ...value.trades].every(row => row && typeof row === "object" && !Array.isArray(row));
  const api = {
    restore(storage) {
      try {
        const value = JSON.parse(storage.getItem(key) || "null");
        return valid(value) ? value : null;
      } catch { return null; }
    },
    save(storage, snapshot) {
      try {
        const value = { ...snapshot, version: 1, savedAt: new Date().toISOString() };
        if (!valid(value)) throw new Error("보유·매매 저장 형식 오류");
        storage.setItem(key, JSON.stringify(value));
        return { ok: true, savedAt: value.savedAt };
      } catch (error) { return { ok: false, error: error.message }; }
    }
  };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.FundSnapshotStorage = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
