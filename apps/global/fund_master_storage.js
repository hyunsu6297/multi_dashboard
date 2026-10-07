(function (root) {
  "use strict";
  const key = "globalDashboard.funds";
  const backupKey = "globalDashboard.fundBackups";
  function normalize(rows) {
    if (!Array.isArray(rows) || rows.length > 1000) throw new Error("잘못된 펀드 목록입니다.");
    return rows.map(row => {
      if (!row || typeof row !== "object") throw new Error("잘못된 펀드 정보입니다.");
      return {fund: String(row.fund || "").trim(), assocCode: String(row.assocCode || "").trim(), type: String(row.type || "").trim()};
    });
  }
  function backup(storage, funds, reason) {
    let backups;
    try { backups = JSON.parse(storage.getItem(backupKey) || "[]"); } catch { backups = []; }
    if (!Array.isArray(backups)) backups = [];
    backups.push({date: new Date().toISOString(), reason, funds: normalize(funds)});
    storage.setItem(backupKey, JSON.stringify(backups.slice(-20)));
  }
  function merge(existing, incoming) {
    const result = normalize(existing);
    normalize(incoming).filter(row => row.fund || row.assocCode).forEach(row => {
      const index = result.findIndex(old => row.assocCode ? old.assocCode === row.assocCode : old.fund === row.fund);
      if (index < 0) result.push(row);
      else result[index] = {...row, type: row.type || result[index].type};
    });
    return result;
  }
  function restore(defaults, storage, location, history) {
    const saved = storage.getItem(key);
    let funds = saved ? normalize(JSON.parse(saved)) : normalize(defaults);
    const params = new URLSearchParams(location.hash.slice(1));
    const payload = params.get("fundTransfer");
    let imported = false;
    if (payload) {
      const transfer = JSON.parse(payload);
      if (transfer.version !== 1) throw new Error("지원하지 않는 펀드 이전 형식입니다.");
      const incoming = normalize(transfer.funds);
      backup(storage, funds, "before-transfer");
      funds = merge(funds, incoming);
      storage.setItem(key, JSON.stringify(funds));
      backup(storage, incoming, "imported-file-funds");
      history.replaceState(null, "", location.pathname + location.search);
      imported = true;
    }
    return {funds, imported};
  }
  function save(funds) {
    const previous = root.localStorage.getItem(key);
    if (previous) backup(root.localStorage, JSON.parse(previous), "before-save");
    root.localStorage.setItem(key, JSON.stringify(normalize(funds)));
  }
  function transfer(funds) {
    const rows = normalize(funds);
    backup(root.localStorage, rows, "before-export");
    const payload = JSON.stringify({version: 1, funds: rows});
    const url = new URL("http://127.0.0.1:8766/");
    url.hash = new URLSearchParams({fundTransfer: payload}).toString();
    root.location.assign(url.href);
  }
  function download(funds) {
    const rows = normalize(funds);
    backup(root.localStorage, rows, "download");
    const blob = new Blob([JSON.stringify({version: 1, funds: rows}, null, 2)], {type: "application/json"});
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "fund_master_backup_" + new Date().toISOString().slice(0, 10) + ".json";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  root.FundMasterStorage = {normalize, merge, backup, restore, save, transfer, download};
})(typeof window === "undefined" ? globalThis : window);
