(function () {
  const style = document.createElement("style");
  style.textContent = `
    #dashboard .notice,#dashboard .kpis{display:none!important}#dashboard .grid{margin-top:0}
    #emp .panel{border-radius:8px}#emp .empTableWrap{max-height:calc(100vh - 185px)!important}#empTable{font-size:10.5px;table-layout:fixed;white-space:normal}#empTable th{padding:5px 4px;line-height:1.2;text-align:center}#empTable td{padding:4px 4px;line-height:1.2;overflow:hidden;text-overflow:ellipsis}#empTable th:nth-child(n+4),#empTable td:nth-child(n+4){text-align:center!important}#empTable .manualCell{background:#fff!important}.manualInput{width:56px;border:1px solid #b8cbc6;border-radius:3px;padding:2px 3px;text-align:right;background:#fff}.targetWeightInput{width:72px}.manualInput:focus{outline:2px solid #e0b323;background:#fff8d8}.manualChanged{background:#fff3b0!important}.manualChanged .manualInput{background:#fff8d8!important;border-color:#d09b00!important;font-weight:800}.rowCheck,.etfCheck{width:14px;height:14px;accent-color:#064e43}.empActions{flex-wrap:wrap}.empStatus.dirty{color:#b7791f;font-weight:800}.empTableMeta{caption-side:top;text-align:right;color:#6c7f7b;font-size:11px;font-weight:900;padding:0 2px 4px}.changeBarCell{padding:3px 4px!important}.changeBar{position:relative;height:15px;background:#e4efec;border-radius:3px;overflow:hidden}.changeBar:before{content:"";position:absolute;left:50%;top:0;bottom:0;width:1px;background:rgba(6,78,67,.28);z-index:2}.changeFill{position:absolute;top:0;bottom:0;left:50%;background:linear-gradient(90deg,#6fa99e,#064e43)}.changeFill.neg{left:auto;right:50%;background:linear-gradient(90deg,#c2413a,#f0a09b)}.changeBarText{position:absolute;inset:0;display:grid;place-items:center;font-weight:900;font-size:9px;color:#173a34;text-shadow:0 1px 2px rgba(255,255,255,.9);z-index:3}
    .subtotalRow{background:#dfeeea!important;font-weight:900;color:#064e43}.subtotalRow td{border-top:2px solid #609d91;border-bottom:1px solid #609d91}.totalRow{background:#064e43!important;color:white;font-weight:900}.totalRow td{border-top:2px solid #033b32}
    .picker{position:fixed;inset:0;background:rgba(3,31,27,.46);display:none;place-items:center;z-index:100}.picker.active{display:grid}.pickerBox{width:min(1100px,94vw);max-height:84vh;background:white;border-radius:12px;padding:14px;box-shadow:0 22px 70px rgba(0,0,0,.25)}.pickerHead{display:flex;gap:8px;align-items:center;margin-bottom:10px}.pickerHead h2{margin:0;min-width:170px}.pickerTable{max-height:64vh;overflow:auto}.pickBtn{border:0;background:#064e43;color:white;border-radius:3px;padding:4px 8px;cursor:pointer}.pickBtn.added{background:#8aa9a1;cursor:default}.pickerCheck{width:15px;height:15px;accent-color:#064e43}.pickerBulk{border:1px solid #064e43;background:#064e43;color:#fff;border-radius:4px;padding:6px 10px;font-weight:800;cursor:pointer;white-space:nowrap}.pickerTray{display:flex;gap:5px;flex-wrap:wrap;margin:0 0 8px}.pickerChip{border:1px solid #b6d1ca;background:#e9f2ef;color:#173a34;border-radius:12px;padding:3px 8px;font-size:11px}.pickerChip button{border:0;background:transparent;color:#b42318;font-weight:900;cursor:pointer;margin-left:4px}
    .etfManageTools,.empInfoTools,.fundManageTools{display:flex;gap:8px;align-items:center;margin-bottom:8px}.etfManageTools .search{max-width:420px}.etfInput,.empInfoInput,.fundInput{width:100%;min-width:80px;border:1px solid #b8cbc6;border-radius:3px;padding:4px}.etfInput.wide,.fundInput.wide{min-width:190px}.empPrincipalInput,.fundNumericInput{text-align:right}.etfStatus,.empInfoStatus,.fundStatus{font-size:11px;color:#6c7f7b;font-weight:800;margin-left:auto}.etfStatus.dirty,.empInfoStatus.dirty,.fundStatus.dirty{color:#b7791f}
    #dashboard .empIntegratedPanel .compactChart,#dashboard .fundIntegratedPanel .shareRows{height:300px}.assetPanel.expanded .compactChart,.assetPanel.expanded .shareRows{height:calc(100vh - 145px)!important;min-height:690px}.assetPanel h2{justify-content:flex-start;align-items:center;gap:8px}.assetPanel h2:before{display:none}.assetTitle{display:flex;align-items:baseline;gap:8px;min-width:0;flex:0 1 auto}.assetTitleText{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.assetMeta{font-size:11px;color:#6c7f7b;font-weight:800}.panelToggle{border:1px solid #b6d1ca;background:#e9f2ef;color:#173a34;border-radius:4px;padding:3px 7px;font-size:11px;font-weight:800;cursor:pointer;flex:0 0 auto;margin-left:auto}
    .shareRow{grid-template-columns:minmax(36px,var(--share-label-width,64px)) 46px minmax(120px,1fr)!important;gap:5px!important}.shareText{display:contents}.shareRow .shareLabel{grid-column:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.shareRow .shareValue{grid-column:2;text-align:right}.shareRow .track{grid-column:3}.empMenu>h3{display:none}.empPortfolioFilter{margin:8px 0;background:#fcfffe;border:1.5px solid var(--line);border-radius:5px;padding:6px}.empPortfolioFilter .filterHead{display:flex;align-items:center;gap:4px;margin-bottom:6px}.empPortfolioFilter h3{margin:0;color:var(--ink);font-size:12px;flex:1}.empPortfolioFilter .multiBtn,.empPortfolioFilter .miniAll{border:1px solid #b6d1ca;background:var(--mint);color:var(--ink);border-radius:3px;padding:2px 6px;font-size:10px;line-height:1.2;height:auto;cursor:pointer}.empPortfolioFilter .multiBtn.active{background:var(--deep);color:#fff}.empPortfolioFilter .chips{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:4px}.empPortfolioFilter .chip{border:0;background:var(--teal);color:#fff;border-radius:3px;padding:5px 6px;text-align:left;font-size:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;cursor:pointer}.empPortfolioFilter .chip.active{background:#092f2a;box-shadow:inset 0 0 0 2px #9ad0c1}
    #emp .empSummary{margin-bottom:8px}.topRefresh{border:1.5px solid var(--line);background:var(--deep);color:#fff;font-weight:900;border-radius:5px;padding:9px 14px;cursor:pointer;white-space:nowrap}
    .dashboardMetricStrip{display:grid;grid-template-columns:repeat(8,minmax(0,1fr));gap:7px;margin-bottom:8px}.metricCard{background:#fff;border:1.5px solid var(--line);border-radius:7px;padding:7px 9px;min-width:0}.metricCard span{display:block;color:#6c7f7b;font-size:10px;font-weight:900;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.metricCard b{display:block;margin-top:5px;text-align:right;color:#064e43;font-size:14px}.metricCard b.neg{color:#c2413a}.metricCard b.pos{color:#087f5b}
    #dashboard .grid.dashboardOverview{display:grid;grid-template-columns:minmax(0,.92fr) minmax(0,.68fr) minmax(0,1.5fr);gap:10px;align-items:stretch;height:calc(100vh - 158px);min-height:590px}
    #dashboard .chosenAssetPanel,#dashboard .tradeLongPanel{height:100%;display:flex;flex-direction:column;min-height:0}
    #dashboard .chosenAssetPanel .shareRows{height:auto!important;flex:1;min-height:0;max-height:none;padding-right:2px}
    #dashboard .chosenAssetPanel .panelToggle{display:none}
    .assetModeTools{display:flex;gap:6px;margin-left:auto;align-items:center}.assetModeBtn{border:1px solid #b6d1ca;background:#e9f2ef;color:#173a34;border-radius:4px;padding:4px 8px;font-size:11px;font-weight:900;cursor:pointer}.assetModeBtn.active{background:#064e43;color:#fff;border-color:#064e43}
    .dashboardPieColumn{display:grid;grid-template-rows:1fr 1fr;gap:10px;min-height:0}.piePanel{height:100%;min-height:0;display:flex;flex-direction:column}.pieBox{position:relative;flex:1;min-height:0;display:grid;place-items:center;overflow:hidden}.pieChart{position:relative;width:min(270px,calc(100% - 24px));max-height:calc(100% - 20px);aspect-ratio:1;border-radius:50%;margin:auto;background:#e4efec;box-shadow:0 0 0 1px #d4e5e1}.pieLabel{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);max-width:74px;text-align:center;color:#fff;font-size:9px;font-weight:900;line-height:1.15;text-shadow:0 1px 3px rgba(0,0,0,.55);pointer-events:none}.pieCallout{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);z-index:2;min-width:48px;max-width:78px;text-align:center;color:#173a34;background:rgba(255,255,255,.92);border:1px solid rgba(96,157,145,.55);border-radius:8px;padding:3px 5px;font-size:9px;font-weight:900;line-height:1.15;box-shadow:0 2px 7px rgba(0,0,0,.08);pointer-events:none}.pieLeaders{position:absolute;inset:0;overflow:hidden;pointer-events:none}.pieLeaders line{stroke:#6c7f7b;stroke-width:1.2;stroke-dasharray:2 2}.pieLegend{display:none}.unclassifiedBtn{border:1.5px solid #d4a72c;background:#fff7d7;color:#7c5510;font-weight:900;border-radius:5px;padding:9px 12px;cursor:pointer;white-space:nowrap}
    #dashboard .tradeLongPanel .tablewrap{height:auto!important;max-height:none!important;flex:1;min-height:0;overflow-x:hidden}#dashboard .tradeLongPanel table{font-size:10px;table-layout:fixed;width:100%}#tradeTable th,#tradeTable td{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;padding-left:3px;padding-right:3px}#tradeTable th:nth-child(1),#tradeTable td:nth-child(1){width:13.5%;text-overflow:clip}#tradeTable th:nth-child(2),#tradeTable td:nth-child(2){width:16%;text-overflow:clip}#tradeTable th:nth-child(3),#tradeTable td:nth-child(3){width:5.5%}#tradeTable th:nth-child(4),#tradeTable td:nth-child(4){width:16%;max-width:0}#tradeTable th:nth-child(5),#tradeTable td:nth-child(5){width:8%}#tradeTable th:nth-child(6),#tradeTable td:nth-child(6){width:7.5%}#tradeTable th:nth-child(7),#tradeTable td:nth-child(7){width:12%}#tradeTable th:nth-child(8),#tradeTable td:nth-child(8){width:8%}#tradeTable th:nth-child(9),#tradeTable td:nth-child(9){width:13.5%}#tradeTable span[title]{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.tradeEmpty{height:100%;min-height:360px;display:grid;place-items:center;color:#6c7f7b;font-weight:900;border:1px dashed #b8d2cc;border-radius:10px;background:#f8fcfb}.sortHeader{width:100%;border:0;background:transparent;color:inherit;font:inherit;font-weight:900;cursor:pointer;text-align:center;padding:0}.sortHeader:hover{text-decoration:underline}
    @media(max-width:1250px){#dashboard .grid.dashboardOverview{grid-template-columns:1fr;height:auto}.dashboardPieColumn{grid-template-rows:auto}.piePanel{min-height:310px}#dashboard .chosenAssetPanel,#dashboard .tradeLongPanel{min-height:520px}}
  `;
  document.head.appendChild(style);
  document.title = "글로벌전략 대시보드";
  const brand = document.querySelector(".brand");
  if (brand) brand.textContent = "글로벌전략 대시보드";

  const tabs = document.querySelector(".tabs");
  const empTab = tabs.querySelector('[data-tab="emp"]');
  if (empTab) empTab.textContent = "EMP상세";
  const masterTab = tabs.querySelector('[data-tab="master"]');
  masterTab.textContent = "펀드정보";
  const etfTab = document.createElement("button");
  etfTab.className = "tab";
  etfTab.dataset.tab = "etfManager";
  etfTab.textContent = "ETF DB";
  tabs.insertBefore(etfTab, masterTab);
  const empInfoTab = document.createElement("button");
  empInfoTab.className = "tab";
  empInfoTab.dataset.tab = "empInfoManager";
  empInfoTab.textContent = "EMP정보";
  masterTab.after(empInfoTab);
  const unclassifiedButton = document.createElement("button");
  unclassifiedButton.className = "unclassifiedBtn";
  unclassifiedButton.id = "addUnclassifiedEtfs";
  unclassifiedButton.type = "button";
  unclassifiedButton.textContent = "미분류추가";
  etfTab.after(unclassifiedButton);

  const etfPane = document.createElement("section");
  etfPane.className = "pane";
  etfPane.id = "etfManager";
  etfPane.innerHTML = `<div class="panel"><div class="etfManageTools"><input class="search" id="etfManagerSearch" placeholder="티커·종목명·분류·EMP 검색"><button class="actionBtn" id="addEtfMaster">ETF 추가</button></div><h2>ETF DB</h2><div class="tablewrap" style="max-height:calc(100vh - 190px)"><table id="etfManagerTable"></table></div></div>`;
  etfPane.innerHTML = `<div class="panel"><div class="etfManageTools"><input class="search" id="etfManagerSearch" placeholder="티커·종목명·분류·EMP 검색"><button class="actionBtn" id="addEtfMaster">ETF 추가</button><button class="actionBtn" id="deleteSelectedEtfs">삭제</button><button class="actionBtn primary" id="saveEtfChanges">변경저장</button><span class="etfStatus" id="etfStatus"></span></div><h2>ETF DB</h2><div class="tablewrap" style="max-height:calc(100vh - 190px)"><table id="etfManagerTable"></table></div></div>`;
  document.getElementById("master").after(etfPane);
  const empInfoPane = document.createElement("section");
  empInfoPane.className = "pane";
  empInfoPane.id = "empInfoManager";
  empInfoPane.innerHTML = `<div class="panel"><div class="empInfoTools"><button class="actionBtn" id="addEmpInfo">EMP 추가</button><button class="actionBtn" id="deleteSelectedEmpInfo">삭제</button><button class="actionBtn primary" id="saveEmpInfoChanges">변경저장</button><span class="empInfoStatus" id="empInfoStatus"></span></div><h2>EMP정보</h2><div class="tablewrap" style="max-height:calc(100vh - 190px)"><table id="empInfoTable"></table></div></div>`;
  document.getElementById("master").after(empInfoPane);
  const oldEtfPanel = document.getElementById("etfTable")?.closest(".panel");
  if (oldEtfPanel) oldEtfPanel.style.display = "none";
  const fundPanel = document.getElementById("fundTable")?.closest(".panel");
  if (fundPanel && !document.getElementById("fundManageTools")) {
    fundPanel.insertAdjacentHTML("afterbegin", `<div class="fundManageTools" id="fundManageTools"><button class="actionBtn" id="addFundInfo">행 추가</button><button class="actionBtn" id="deleteSelectedFunds">행 삭제</button><button class="actionBtn primary" id="saveFundChanges">변경저장</button><span class="fundStatus" id="fundStatus"></span></div>`);
  }

  const dashboardGrid = document.querySelector("#dashboard .grid");
  const metricStrip = document.createElement("div");
  metricStrip.className = "dashboardMetricStrip";
  metricStrip.id = "dashboardMetricStrip";
  dashboardGrid.before(metricStrip);
  const currentFundPanel = dashboardGrid.querySelector(".panel.wide");
  currentFundPanel.classList.remove("wide");
  currentFundPanel.classList.add("assetPanel", "fundIntegratedPanel");
  const empPanel = document.querySelector("#empAssetChart").closest(".panel");
  empPanel.classList.add("assetPanel", "empIntegratedPanel");
  dashboardGrid.insertBefore(empPanel, currentFundPanel);
  document.querySelector("#emp .empCharts")?.remove();
  function panelTitle(panel, text, meta, toggleId) {
    const heading = panel.querySelector("h2");
    heading.innerHTML = `<span class="assetTitle"><span class="assetTitleText">${esc(text)}</span><span class="assetMeta">${esc(meta)}</span></span><button class="panelToggle" id="${toggleId}" type="button">펼치기</button>`;
  }
  function bindPanelToggle(panel, buttonId) {
    const button = document.getElementById(buttonId);
    button.onclick = () => {
      const shouldExpand = !panel.classList.contains("expanded");
      [empPanel, currentFundPanel].forEach(target => target.classList.toggle("expanded", shouldExpand));
      ["toggleEmpAssetPanel", "toggleFundAssetPanel"].forEach(id => {
        const toggle = document.getElementById(id);
        if (toggle) toggle.textContent = shouldExpand ? "접기" : "펼치기";
      });
    };
  }
  panelTitle(empPanel, "EMP 자산 비중", "", "toggleEmpAssetPanel");
  panelTitle(currentFundPanel, "수익증권 자산 비중", "", "toggleFundAssetPanel");
  bindPanelToggle(empPanel, "toggleEmpAssetPanel");
  bindPanelToggle(currentFundPanel, "toggleFundAssetPanel");
  const holdingPanel = document.getElementById("holdingTable")?.closest(".panel");
  const tradePanel = document.getElementById("tradeTable")?.closest(".panel");
  holdingPanel?.remove();
  empPanel.style.display = "none";
  currentFundPanel.classList.add("chosenAssetPanel");
  tradePanel?.classList.add("tradeLongPanel");
  const pieColumn = document.createElement("div");
  pieColumn.className = "dashboardPieColumn";
  pieColumn.innerHTML = `<div class="panel piePanel"><h2>대분류 비중</h2><div class="pieBox"><div class="pieChart" id="largePieChart"></div><div class="pieLegend" id="largePieLegend"></div></div></div><div class="panel piePanel"><h2>투자국가 비중</h2><div class="pieBox"><div class="pieChart" id="countryPieChart"></div><div class="pieLegend" id="countryPieLegend"></div></div></div>`;
  dashboardGrid.classList.add("dashboardOverview");
  dashboardGrid.innerHTML = "";
  dashboardGrid.append(currentFundPanel, pieColumn);
  if (tradePanel) dashboardGrid.append(tradePanel);

  const picker = document.createElement("div");
  picker.className = "picker";
  picker.id = "etfPicker";
  picker.innerHTML = `<div class="pickerBox"><div class="pickerHead"><h2 id="pickerTitle"></h2><input class="search" id="pickerSearch" placeholder="티커·종목명·분류 검색"><button class="pickerBulk" id="pickSelectedEtfs">선택 적용</button><button class="actionBtn" id="closePicker">닫기</button></div><div class="pickerTray" id="pickerTray"></div><div class="pickerTable"><table id="pickerTable"></table></div></div>`;
  document.body.appendChild(picker);

  const savedEtfs = JSON.parse(localStorage.getItem("globalDashboard.etfs") || "null");
  if (Array.isArray(savedEtfs)) DATA.etfs = savedEtfs;
  const savedFunds = JSON.parse(localStorage.getItem("globalDashboard.funds") || "null");
  if (Array.isArray(savedFunds)) DATA.funds = savedFunds;
  const applyMarketData = market => {
    if (!market) return;
    if (market.fx) state.fx = Number(market.fx || 1);
    const map = market.securities || {};
    const keyOf = value => String(value || "").trim().replace(/\s+/g, " ").toUpperCase();
    Object.values(DATA.emp.portfolios || {}).flat().forEach(row => {
      const key = keyOf(row.security);
      const found = Object.keys(map).find(item => keyOf(item) === key);
      const updated = map[row.security] || (found ? map[found] : null);
      if (!updated) return;
      ["marketCap", "avgTurnover3m", "price", "prevClose", "change"].forEach(field => {
        if (updated[field] !== undefined && updated[field] !== null && updated[field] !== "") row[field] = Number(updated[field] || 0);
      });
    });
    DATA.holdings.forEach(row => {
      const updated = map[row.security] || map[tradeTicker(row)];
      if (!updated) return;
      if (updated.change !== undefined) row.change = Number(updated.change || 0);
      if (updated.price !== undefined) row.marketPrice = Number(updated.price || 0);
      if (updated.prevClose !== undefined) row.prevClose = Number(updated.prevClose || 0);
    });
  };
  const savedMarket = JSON.parse(localStorage.getItem("globalDashboard.market") || "null") || DATA.market || null;
  const savedEmpState = JSON.parse(localStorage.getItem("globalDashboard.emp") || "null");
  if (savedEmpState?.principals) DATA.emp.principals = savedEmpState.principals;
  applyMarketData(savedMarket);
  DATA.emp.portfolios && Object.values(DATA.emp.portfolios).flat().forEach(row => { row.targetTouched = Boolean(row.targetTouched); });
  const GLOBAL_DOMAIN = "global";
  const GLOBAL_FILE_LABELS = {
    etf_db: "ETF DB",
    fund_info: "펀드정보",
    emp_info: "EMP정보",
    emp_portfolios: "EMP상세",
    market_data: "블룸버그 데이터"
  };
  let globalSupabase = null;
  let globalCurrentUser = null;
  let globalDbReady = false;
  let globalDbLoadPromise = null;
  async function getGlobalSupabase() {
    if (globalSupabase) return globalSupabase;
    if (window.parent !== window && window.parent.dashboardSupabase) {
      globalSupabase = window.parent.dashboardSupabase;
      return globalSupabase;
    }
    const { createClient } = await import("https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/+esm");
    globalSupabase = createClient("https://esqakvzvchcunhzjlyry.supabase.co", "sb_publishable_T0q_8mB9yzcitTL7HH0SuA_W4DUcVtP", {
      auth: { persistSession: true, autoRefreshToken: true }
    });
    return globalSupabase;
  }
  async function getGlobalUser() {
    const client = await getGlobalSupabase();
    const { data } = await client.auth.getSession();
    globalCurrentUser = data?.session?.user || null;
    return globalCurrentUser;
  }
  async function loadGlobalManualRows(fileKey) {
    const client = await getGlobalSupabase();
    const loaded = [];
    for (let start = 0; ; start += 1000) {
      const { data, error } = await client.from("manual_file_rows")
        .select("sheet_name,row_no,payload")
        .eq("domain", GLOBAL_DOMAIN)
        .eq("file_key", fileKey)
        .order("sheet_name")
        .order("row_no")
        .range(start, start + 999);
      if (error) throw error;
      loaded.push(...data);
      if (data.length < 1000) return loaded;
    }
  }
  async function replaceGlobalManualRows(fileKey, rows, sheetName = "Data") {
    const user = await getGlobalUser();
    if (!user) throw new Error("Supabase 로그인이 필요합니다");
    const client = await getGlobalSupabase();
    const records = rows.map((payload, index) => ({
      domain: GLOBAL_DOMAIN,
      file_key: fileKey,
      file_label: GLOBAL_FILE_LABELS[fileKey] || fileKey,
      sheet_name: sheetName,
      row_no: index + 1,
      payload,
      created_by: user.id,
      updated_at: new Date().toISOString()
    }));
    for (let start = 0; start < records.length; start += 500) {
      const { error } = await client.from("manual_file_rows")
        .upsert(records.slice(start, start + 500), { onConflict: "domain,file_key,sheet_name,row_no" });
      if (error) throw error;
    }
    const { error } = await client.from("manual_file_rows").delete()
      .eq("domain", GLOBAL_DOMAIN)
      .eq("file_key", fileKey)
      .eq("sheet_name", sheetName)
      .gt("row_no", records.length);
    if (error) throw error;
  }
  async function loadGlobalDbState() {
    try {
      if (!await getGlobalUser()) return false;
      const [etfRows, fundRows, empInfoRows, empRows, marketRows] = await Promise.all([
        loadGlobalManualRows("etf_db"),
        loadGlobalManualRows("fund_info"),
        loadGlobalManualRows("emp_info"),
        loadGlobalManualRows("emp_portfolios"),
        loadGlobalManualRows("market_data")
      ]);
      if (etfRows.length) DATA.etfs = etfRows.map(row => ({ ...row.payload }));
      if (fundRows.length) DATA.funds = fundRows.map(row => ({ ...row.payload }));
      if (empInfoRows.length || empRows.length) {
        DATA.emp.principals = {};
        DATA.emp.portfolios = {};
        empInfoRows.forEach(row => {
          const name = String(row.payload.name || row.payload.emp || "").trim();
          if (!name) return;
          DATA.emp.principals[name] = Number(row.payload.principal || 0);
          DATA.emp.portfolios[name] = DATA.emp.portfolios[name] || [];
        });
        empRows.forEach(row => {
          const payload = { ...row.payload };
          const name = String(payload.emp || "").trim();
          if (!name) return;
          delete payload.emp;
          payload.targetTouched = Boolean(payload.targetTouched);
          DATA.emp.portfolios[name] = DATA.emp.portfolios[name] || [];
          DATA.emp.portfolios[name].push(payload);
          DATA.emp.principals[name] = Number(DATA.emp.principals[name] || 0);
        });
      }
      if (marketRows[0]?.payload) applyMarketData(marketRows[0].payload);
      globalDbReady = true;
      return true;
    } catch (error) {
      console.warn("global dashboard DB load failed", error);
      return false;
    }
  }
  async function saveGlobalEmpState() {
    const empInfo = Object.keys(DATA.emp.portfolios || {}).map(name => ({
      name,
      principal: Number(DATA.emp.principals[name] || 0)
    }));
    const portfolios = Object.entries(DATA.emp.portfolios || {}).flatMap(([emp, rows]) =>
      rows.map(row => ({ emp, ...row }))
    );
    await replaceGlobalManualRows("emp_info", empInfo, "Data");
    await replaceGlobalManualRows("emp_portfolios", portfolios, "Data");
    globalDbReady = true;
  }
  async function saveGlobalEtfs() {
    await replaceGlobalManualRows("etf_db", DATA.etfs.map(row => ({ ...row })), "Data");
    globalDbReady = true;
  }
  async function saveGlobalFunds() {
    await replaceGlobalManualRows("fund_info", DATA.funds.map(row => ({ ...row })), "Data");
    globalDbReady = true;
  }
  async function saveGlobalMarketData(market) {
    await replaceGlobalManualRows("market_data", [market], "Data");
    globalDbReady = true;
  }
  saveEmp = function () {
    localStorage.setItem("globalDashboard.emp", JSON.stringify({ portfolios: DATA.emp.portfolios, principals: DATA.emp.principals, fx: state.fx }));
    return saveGlobalEmpState().catch(error => {
      console.warn("global dashboard EMP DB save failed", error);
      const status = document.getElementById("empStatus");
      if (status) status.textContent = `로컬 저장 완료 · DB 저장 실패: ${error.message}`;
    });
  };
  const refreshButton = document.getElementById("refreshMarket");
  const addRowButton = document.getElementById("addEmpRow");
  refreshButton.textContent = "블룸버그 업데이트";
  refreshButton.classList.remove("actionBtn", "primary", "summaryRefresh");
  refreshButton.classList.add("topRefresh");
  empInfoTab.after(refreshButton);
  addRowButton.textContent = "행 추가";
  const deleteRowsButton = document.createElement("button");
  deleteRowsButton.className = "actionBtn";
  deleteRowsButton.id = "deleteSelectedEmpRows";
  deleteRowsButton.textContent = "행 삭제";
  const saveChangesButton = document.createElement("button");
  saveChangesButton.className = "actionBtn primary";
  saveChangesButton.id = "saveEmpChanges";
  saveChangesButton.textContent = "변경저장";
  const exportTradesButton = document.createElement("button");
  exportTradesButton.className = "actionBtn";
  exportTradesButton.id = "exportEmpTrades";
  exportTradesButton.textContent = "거래정보추출";
  const resetTargetsButton = document.createElement("button");
  resetTargetsButton.className = "actionBtn";
  resetTargetsButton.id = "resetEmpTargets";
  resetTargetsButton.textContent = "목표비중초기화";
  addRowButton.before(deleteRowsButton);
  addRowButton.after(resetTargetsButton);
  resetTargetsButton.after(saveChangesButton);
  saveChangesButton.after(exportTradesButton);
  const saveEtfs = () => {
    localStorage.setItem("globalDashboard.etfs", JSON.stringify(DATA.etfs));
    return saveGlobalEtfs().catch(error => {
      console.warn("global dashboard ETF DB save failed", error);
      const status = document.getElementById("etfStatus");
      if (status) status.textContent = `로컬 저장 완료 · DB 저장 실패: ${error.message}`;
    });
  };
  const saveFunds = () => {
    localStorage.setItem("globalDashboard.funds", JSON.stringify(DATA.funds));
    return saveGlobalFunds().catch(error => {
      console.warn("global dashboard fund DB save failed", error);
      const status = document.getElementById("fundStatus");
      if (status) status.textContent = `로컬 저장 완료 · DB 저장 실패: ${error.message}`;
    });
  };
  const selectedEtfRows = new Set();
  const selectedEmpInfoRows = new Set();
  const selectedFundInfoRows = new Set();
  let etfDirty = false;
  let etfSort = { key: "ticker", direction: 1 };
  let empInfoDirty = false;
  let fundDirty = false;
  const markEtfDirty = (message = "저장되지 않은 변경사항") => {
    etfDirty = true;
    const status = document.getElementById("etfStatus");
    if (!status) return;
    status.textContent = message;
    status.classList.add("dirty");
  };
  const clearEtfDirty = (message = "변경사항 저장 완료") => {
    etfDirty = false;
    const status = document.getElementById("etfStatus");
    if (!status) return;
    status.textContent = message;
    status.classList.remove("dirty");
  };
  const markEmpInfoDirty = (message = "저장되지 않은 변경사항") => {
    empInfoDirty = true;
    const status = document.getElementById("empInfoStatus");
    if (!status) return;
    status.textContent = message;
    status.classList.add("dirty");
  };
  const clearEmpInfoDirty = (message = "변경사항 저장 완료") => {
    empInfoDirty = false;
    const status = document.getElementById("empInfoStatus");
    if (!status) return;
    status.textContent = message;
    status.classList.remove("dirty");
  };
  const markFundDirty = (message = "저장되지 않은 변경사항") => {
    fundDirty = true;
    const status = document.getElementById("fundStatus");
    if (!status) return;
    status.textContent = message;
    status.classList.add("dirty");
  };
  const clearFundDirty = (message = "변경사항 저장 완료") => {
    fundDirty = false;
    const status = document.getElementById("fundStatus");
    if (!status) return;
    status.textContent = message;
    status.classList.remove("dirty");
  };  const parseNumber = value => Number(String(value ?? "0").replaceAll(",", "")) || 0;
  const normalizeSecurity = value => String(value || "").trim().replace(/\s+/g, " ")
    .replace(/\s+US\s+EQUITY$/i, " US Equity")
    .replace(/\s+KS\s+EQUITY$/i, " KS Equity");
  const securityKey = value => normalizeSecurity(value).toUpperCase();
  const securityRequests = value => {
    const security = normalizeSecurity(value);
    if (!security) return [];
    const original = String(value || "").trim().replace(/\s+/g, " ");
    return [...new Set([original, security].filter(Boolean))];
  };
  const marketMatch = (map, security) => {
    const normalized = normalizeSecurity(security);
    if (map[security]) return map[security];
    if (map[normalized]) return map[normalized];
    const key = securityKey(normalized);
    const found = Object.keys(map).find(item => securityKey(item) === key);
    return found ? map[found] : null;
  };
  const applyEmpMarketRow = (row, map) => {
    const updated = marketMatch(map, row.security);
    if (!updated) return false;
    ["marketCap", "avgTurnover3m", "price", "prevClose", "change"].forEach(key => {
      if (updated[key] !== undefined && updated[key] !== null && updated[key] !== "") row[key] = Number(updated[key] || 0);
    });
    row.security = normalizeSecurity(row.security);
    return true;
  };
  const formatPercentInput = value => {
    const n = Number(value || 0);
    if (!Number.isFinite(n)) return "";
    return n.toFixed(2);
  };
  state.multiDimension = false;
  state.dashboardSource = "all";
  state.showMidDimension = false;
  state.multiEmp = false;
  state.empSelection = [];
  const selectedRows = new Set();
  const pickerSelected = new Set();
  let empInputTimer = null;
  let empDirty = false;
  const markEmpDirty = (message = "저장되지 않은 변경사항") => {
    empDirty = true;
    const status = document.getElementById("empStatus");
    status.textContent = message;
    status.classList.add("dirty");
  };
  const clearEmpDirty = (message = "변경사항 저장 완료") => {
    empDirty = false;
    const status = document.getElementById("empStatus");
    status.textContent = message;
    status.classList.remove("dirty");
  };
  const empNumber = () => state.emp.replace("EMP", "");
  const empEtfs = () => DATA.etfs.filter(e => String(e.emp || "").toUpperCase() === state.emp);
  const securityEtf = (security, empName = state.emp) => {
    const ticker = String(security || "").split(" ")[0].toUpperCase();
    return DATA.etfs.find(e => String(e.name || e.ticker || "").split(" ")[0].toUpperCase() === ticker && String(e.emp || "").toUpperCase() === empName)
      || DATA.etfs.find(e => String(e.name || e.ticker || "").split(" ")[0].toUpperCase() === ticker) || {};
  };
  const usdMillion = (value, security) => {
    const usd = isUsd(security) ? Number(value || 0) : Number(value || 0) / Number(state.fx || 1);
    return usd / 1_000_000;
  };
  const marketDisplayAmount = (value, security) => {
    const amountValue = Number(value || 0);
    return isUsd(security) ? amountValue / 1_000_000 : amountValue / 1_000_000;
  };
  const integerAmount = value => Math.round(Number(value || 0)).toLocaleString("ko-KR");
  const localToUsd = (value, security) => {
    const amount = Number(value || 0);
    return isUsd(security) ? amount : amount / Number(state.fx || 1);
  };
  const empExposureRows = (rows, metrics) => rows.map((row, index) => {
    const meta = securityEtf(row.security);
    return {
      large: meta.large || "미분류",
      country: meta.country || "미분류",
      mid: meta.mid || "미분류",
      small: meta.small || "미분류",
      lookthrough: metrics[index].value
    };
  });
  const insertEmpRow = row => {
    const rows = empRows();
    const selected = [...selectedRows].sort((a, b) => b - a);
    const insertAt = selected.length ? selected[0] + 1 : rows.length;
    rows.splice(insertAt, 0, row);
    selectedRows.clear();
    selectedRows.add(insertAt);
    markEmpDirty("행 추가됨 · 변경저장을 눌러 확정");
    renderEmp();
  };
  const emptyEmpRow = ticker => ({ security: ticker, marketCap: 0, avgTurnover3m: 0, quantity: 0, price: 0, prevClose: 0, change: 0, targetTouched: false });
  const insertEmpRows = rowsToInsert => {
    if (!rowsToInsert.length) return [];
    const rows = empRows();
    const selected = [...selectedRows].sort((a, b) => b - a);
    const insertAt = selected.length ? selected[0] + 1 : rows.length;
    rows.splice(insertAt, 0, ...rowsToInsert);
    selectedRows.clear();
    rowsToInsert.forEach((_, offset) => selectedRows.add(insertAt + offset));
    markEmpDirty(`${rowsToInsert.length}개 행 추가됨 · 변경저장을 눌러 확정`);
    renderEmp();
    return rows.slice(insertAt, insertAt + rowsToInsert.length);
  };
  const activeDimensions = () => state.showMidDimension ? ["large", "mid", "small"] : ["large", "small"];
  const dimensionLabel = () => activeDimensions().map(key => dimensionDefs.find(def => def[0] === key)?.[1] || key).join(" → ");
  const selectedEmpNames = () => state.empSelection?.length ? state.empSelection : Object.keys(DATA.emp.portfolios);
  const selectionLabel = (items, emptyLabel) => {
    if (!items.length) return emptyLabel;
    if (items.length === 1) return items[0];
    return `${items[0]} 등 ${items.length}종목`;
  };
  shares = function (el, entries) {
    const max = Math.max(...entries.map(x => x.share), .0001);
    el.innerHTML = entries.length ? entries.map(x => `<div class="shareRow ${x.subtotal ? "subtotal" : ""}"><span class="shareText"><span class="shareLabel" style="padding-left:${x.depth * 18}px" title="${esc(x.label)}">${x.depth ? "└ " : ""}${esc(x.label)}</span><span class="shareValue">${pct(x.share)}</span></span><div class="track"><div class="fill" style="width:${Math.max(1, x.share / max * 100)}%"></div></div></div>`).join("") : `<div class="empty">표시할 데이터가 없습니다.</div>`;
    if (entries.length) {
      requestAnimationFrame(() => {
        const widths = [...el.querySelectorAll(".shareLabel")].map(node => node.scrollWidth);
        const target = Math.min(Math.max(...widths, 110), Math.max(150, Math.floor(el.clientWidth * 0.28)));
        el.style.setProperty("--share-label-width", `${target}px`);
      });
    } else {
      el.style.removeProperty("--share-label-width");
    }
  };
  hierarchical = function (rows, keys, denom) {
    const out = [];
    function groupBy(part, key) {
      const groups = {};
      part.forEach(row => {
        const value = row[key] || "미분류";
        (groups[value] ||= []).push(row);
      });
      return groups;
    }
    function walk(part, depth) {
      const key = keys[depth];
      Object.entries(groupBy(part, key))
        .map(([label, list]) => [label, list, list.reduce((sum, row) => sum + Number(row.lookthrough || 0), 0)])
        .sort((a, b) => b[2] - a[2])
        .forEach(([label, list, value]) => {
          const last = depth === keys.length - 1;
          out.push({ label: last && keys.length === 1 ? label : `${label}${last ? "" : " 소계"}`, share: denom ? value / denom : 0, depth, subtotal: !last });
          if (!last) {
            const childGroupCount = Object.keys(groupBy(list, keys[depth + 1])).length;
            if (childGroupCount > 1) walk(list, depth + 1);
          }
        });
    }
    if (rows.length) walk(rows, 0);
    return out;
  };
  renderFilters = function () {
    const box = document.getElementById("filters");
    const funds = DATA.funds.map(x => x.fund);
    const names = Object.keys(DATA.emp.portfolios);
    box.innerHTML = `<div class="filter empPortfolioFilter"><div class="filterHead"><h3>EMP</h3><button class="multiBtn ${state.multiEmp ? "active" : ""}" data-emp-action="multi">중복</button><button class="miniAll" data-emp-action="clear">해제</button></div><div class="chips">${names.map(name => `<button title="${name}호 · 원금 ${amount(DATA.emp.principals[name])}" class="chip ${state.dashboardSource === "emp" && (state.empSelection || []).includes(name) ? "active" : ""}" data-emp="${name}">${name}호</button>`).join("")}</div></div><div class="filter"><div class="filterHead"><h3>펀드</h3><button class="multiBtn ${state.multiFund ? "active" : ""}" data-action="multi">중복</button><button class="miniAll" data-key="fund" data-action="clear">해제</button></div><div class="chips">${funds.map(v => `<button title="${esc(v)}" class="chip ${state.dashboardSource === "fund" && state.fund.includes(v) ? "active" : ""}" data-key="fund" data-value="${esc(v)}">${esc(v)}</button>`).join("")}</div></div>`;
    box.querySelectorAll("button").forEach(button => button.onclick = () => {
      if (button.dataset.empAction === "multi") {
        state.dashboardSource = "emp";
        state.multiEmp = !state.multiEmp;
        if (!state.multiEmp && state.empSelection.length > 1) state.empSelection = state.empSelection.slice(0, 1);
      } else if (button.dataset.empAction === "clear") {
        if (!(state.empSelection || []).length) return;
        state.empSelection = [];
        state.multiEmp = false;
        state.dashboardSource = state.fund.length ? "fund" : "all";
      } else if (button.dataset.emp) {
        state.dashboardSource = "emp";
        const name = button.dataset.emp;
        state.emp = name;
        if (state.multiEmp) {
          const index = state.empSelection.indexOf(name);
          if (index >= 0) state.empSelection.splice(index, 1);
          else state.empSelection.push(name);
        } else {
          state.empSelection = [name];
        }
      } else if (button.dataset.action === "multi") {
        state.dashboardSource = "fund";
        state.multiFund = !state.multiFund;
        if (!state.multiFund && state.fund.length > 1) state.fund = state.fund.slice(0, 1);
      } else if (button.dataset.action === "clear") {
        if (!state.fund.length) return;
        state.fund = [];
        state.multiFund = false;
        state.dashboardSource = state.empSelection?.length ? "emp" : "all";
      } else {
        state.dashboardSource = "fund";
        toggleFilter("fund", button.dataset.value);
      }
      render();
    });
  };

  empMetrics = function (row) {
    const localValue = Number(row.quantity || 0) * Number(row.price || 0);
    const value = localToUsd(localValue, row.security);
    const krw = value * Number(state.fx || 1);
    const change = Number(row.change || 0);
    const pnl = krw * change;
    const principal = Number(DATA.emp.principals[state.emp] || 0);
    const current = principal ? value / principal : 0;
    const target = row.targetTouched ? Number(row.targetWeight || 0) : current;
    const prev = localToUsd(Number(row.prevClose || row.price || 0), row.security);
    const gap = target - current;
    if (!row.targetTouched || Math.abs(gap) < 0.00005) return { value, krw, pnl, current, target: current, gap: 0, prev, signedTradeQty: 0, tradeQty: 0, tradeAmount: 0 };
    const targetQty = prev ? (target * principal) / prev : Number(row.quantity || 0);
    const signedTradeQty = Math.round((targetQty - Number(row.quantity || 0)) / 10) * 10;
    return { value, krw, pnl, current, target, gap, prev, signedTradeQty, tradeQty: Math.abs(signedTradeQty), tradeAmount: Math.abs(signedTradeQty * prev) };
  };

  editEmp = function (index, key, value, renderAfterEdit = true) {
    const row = empRows()[index];
    if (!row) return;
    if (key === "security") row[key] = normalizeSecurity(value);
    else if (key === "quantity") {
      row.quantity = parseNumber(value);
      row.quantityTouched = true;
    }
    else if (key === "targetWeight") {
      const raw = String(value).trim();
      row.targetWeightDraft = raw;
      if (raw === "") { row.targetTouched = false; delete row.targetWeight; }
      else { row.targetTouched = true; row.targetWeight = parseNumber(raw) / 100; }
    } else row[key] = parseNumber(value);
    markEmpDirty(renderAfterEdit ? "저장되지 않은 변경사항" : "목표비중 입력 중");
    if (renderAfterEdit) {
      delete row.targetWeightDraft;
      renderEmp();
    }
  };
  function updatePanelHeader(panel, text, meta, toggleId) {
    const wasExpanded = panel.classList.contains("expanded");
    panelTitle(panel, text, meta, toggleId);
    if (wasExpanded) panel.classList.add("expanded");
    const button = document.getElementById(toggleId);
    button.textContent = wasExpanded ? "접기" : "펼치기";
    bindPanelToggle(panel, toggleId);
  }
  const pieColors = ["#064e43", "#2a7569", "#74a99e", "#c49a2c", "#7c6bb0", "#d46a6a", "#4f8fc0", "#8aa9a1", "#b9dbd4", "#d9c27a"];
  function selectedEmpExposureRows() {
    const exposure = [];
    selectedEmpNames().forEach(name => {
      (DATA.emp.portfolios[name] || []).forEach(row => {
        const meta = securityEtf(row.security, name);
        exposure.push({
          source: "emp",
          emp: name,
          code: "",
          name: row.security,
          ticker: row.security,
          large: meta.large || "미분류",
          country: meta.country || "미분류",
          mid: meta.mid || "미분류",
          small: meta.small || "미분류",
          lookthrough: localToUsd(Number(row.quantity || 0) * Number(row.price || 0), row.security) * Number(state.fx || 1),
          change: Number(row.change || 0)
        });
      });
    });
    return exposure;
  }
  function selectedFundRows() {
    return fundBase(DATA.holdings).filter(row => !row.isFx);
  }
  function selectedFundFxRows() {
    return fundBase(DATA.holdings).filter(row => row.isFx);
  }
  function currentDashboardRows() {
    if (state.dashboardSource === "fund" && state.fund.length) return selectedFundRows();
    if (state.dashboardSource === "emp" && state.empSelection?.length) return selectedEmpExposureRows();
    return [...selectedFundRows(), ...selectedEmpExposureRows()];
  }
  const isEquityAsset = row => String(row.large || "") === "\uC8FC\uC2DD";
  const isBondAsset = row => String(row.large || "") === "\uCC44\uAD8C";
  const isUsListedEtf = row => {
    const key = String(row.ticker || row.security || row.name || "").split(" ")[0].toUpperCase();
    const meta = DATA.etfs.find(etf => [etf.name, etf.ticker].some(value => String(value || "").split(" ")[0].toUpperCase() === key)) || {};
    return String(meta.listing || row.listing || "").includes("\uBBF8\uAD6D");
  };
  function empMetricRowsKrw(names = Object.keys(DATA.emp.portfolios || {})) {
    return names.flatMap(name => (DATA.emp.portfolios[name] || []).map(row => {
      const meta = securityEtf(row.security, name);
      const usdValue = localToUsd(Number(row.quantity || 0) * Number(row.price || 0), row.security);
      return {
        source: "emp",
        emp: name,
        large: meta.large || "\uBBF8\uBD84\uB958",
        country: meta.country || "\uBBF8\uBD84\uB958",
        lookthrough: usdValue * Number(state.fx || 1),
        change: Number(row.change || 0)
      };
    }));
  }
  function dashboardMetricRows() {
    if (state.dashboardSource === "fund" && state.fund.length) return selectedFundRows();
    if (state.dashboardSource === "emp" && state.empSelection?.length) return empMetricRowsKrw(state.empSelection);
    return [...selectedFundRows(), ...empMetricRowsKrw()];
  }
  function hedgeRatioForFunds() {
    if (state.dashboardSource === "emp" && state.empSelection?.length) return null;
    const fxShort = selectedFundFxRows()
      .reduce((sum, row) => sum + Math.abs(Number(row.lookthrough || row.original || 0)), 0);
    const usListedValue = selectedFundRows()
      .filter(row => isUsListedEtf(row) || String(row.country || "").includes("\uBBF8\uAD6D"))
      .reduce((sum, row) => sum + Math.abs(Number(row.lookthrough || 0)), 0);
    return usListedValue ? fxShort / usListedValue : null;
  }
  function groupShares(rows, key) {
    const total = rows.reduce((sum, row) => sum + Math.max(0, Number(row.lookthrough || 0)), 0);
    return Object.entries(rows.reduce((acc, row) => {
      const label = row[key] || "미분류";
      acc[label] = (acc[label] || 0) + Math.max(0, Number(row.lookthrough || 0));
      return acc;
    }, {})).map(([label, value]) => ({ label, value, share: total ? value / total : 0 })).sort((a, b) => b.value - a.value);
  }
  function renderPie(chartId, legendId, rows, key) {
    const chart = document.getElementById(chartId);
    const legend = document.getElementById(legendId);
    const box = chart?.closest(".pieBox");
    const entries = groupShares(rows, key).filter(x => x.value > 0);
    if (!entries.length) {
      chart.style.background = "#e4efec";
      chart.innerHTML = "";
      if (box) box.querySelector(".pieLeaders")?.remove();
      legend.innerHTML = `<div class="empty">표시할 데이터가 없습니다.</div>`;
      return;
    }
    let cursor = 0;
    const stops = entries.map((entry, index) => {
      const start = cursor;
      cursor += entry.share * 100;
      entry.midAngle = (start + cursor) / 2 * 3.6;
      return `${pieColors[index % pieColors.length]} ${start.toFixed(3)}% ${cursor.toFixed(3)}%`;
    });
    chart.style.background = `conic-gradient(${stops.join(",")})`;
    chart.innerHTML = entries.filter(entry => entry.share >= .085).slice(0, 6).map(entry => {
      const angle = (entry.midAngle - 90) * Math.PI / 180;
      const radius = entry.share >= .18 ? 31 : 39;
      const x = 50 + Math.cos(angle) * radius;
      const y = 50 + Math.sin(angle) * radius;
      return `<span class="pieLabel" style="left:${x.toFixed(1)}%;top:${y.toFixed(1)}%">${esc(entry.label)}<br>${pct(entry.share)}</span>`;
    }).join("");
    legend.innerHTML = "";
    if (box) {
      box.querySelector(".pieLeaders")?.remove();
      box.querySelectorAll(".pieCallout").forEach(node => node.remove());
      const boxRect = box.getBoundingClientRect();
      const chartRect = chart.getBoundingClientRect();
      const cx = chartRect.left - boxRect.left + chartRect.width / 2;
      const cy = chartRect.top - boxRect.top + chartRect.height / 2;
      const r = chartRect.width / 2;
      const outside = entries.filter(entry => entry.share < .085).slice(0, 8);
      const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      svg.setAttribute("class", "pieLeaders");
      outside.forEach(entry => {
        const angle = (entry.midAngle - 90) * Math.PI / 180;
        const sx = cx + Math.cos(angle) * r * .88;
        const sy = cy + Math.sin(angle) * r * .88;
        const ex = cx + Math.cos(angle) * r * 1.14;
        const ey = cy + Math.sin(angle) * r * 1.14;
        const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
        line.setAttribute("x1", sx.toFixed(1)); line.setAttribute("y1", sy.toFixed(1));
        line.setAttribute("x2", ex.toFixed(1)); line.setAttribute("y2", ey.toFixed(1));
        svg.appendChild(line);
        const callout = document.createElement("span");
        callout.className = "pieCallout";
        callout.style.left = `${ex.toFixed(1)}px`;
        callout.style.top = `${ey.toFixed(1)}px`;
        callout.innerHTML = `${esc(entry.label)}<br>${pct(entry.share)}`;
        box.appendChild(callout);
      });
      box.prepend(svg);
    }
  }
  function isUnclassified(row) {
    return ["large", "country", "mid", "small"].some(key => !String(row[key] || "").trim() || String(row[key]).trim() === "미분류");
  }
  function isExcludedUnclassifiedAsset(row) {
    const asset = String(row.asset || "");
    return row.isFx || asset.includes("\uC120\uBB3C\uC635\uC158\uD30C\uC0DD") || asset.includes("\uD604\uAE08\uC131\uC790\uC0B0");
  }
  function tickerKey(value) {
    return String(value || "").trim().toUpperCase().replace(/\s+/g, " ");
  }
  function unclassifiedCandidates() {
    const rows = [...DATA.holdings.map(row => ({ ...row, source: "fund" })), ...selectedEmpExposureRows()];
    const existing = new Set(DATA.etfs.flatMap(etf => [etf.ticker, etf.name, etf.isin].map(tickerKey)).filter(Boolean));
    const seen = new Set();
    return rows.filter(row => isUnclassified(row) && !isExcludedUnclassifiedAsset(row)).map(row => {
      const rawTicker = row.code || row.ticker || row.name || "";
      const ticker = String(rawTicker || "").trim();
      const key = tickerKey(ticker || row.code || row.name);
      if (!key || seen.has(key) || existing.has(key)) return null;
      seen.add(key);
      return {
        isin: row.code || "",
        ticker,
        name: ticker,
        koreanName: row.name || "",
        listing: "",
        country: "",
        large: "",
        mid: "",
        small: "",
        emp: row.emp || ""
      };
    }).filter(Boolean);
  }
  function activateEtfManager() {
    state.activeTab = "etfManager";
    document.querySelectorAll(".tab,.pane").forEach(x => x.classList.remove("active"));
    etfTab.classList.add("active");
    document.getElementById("etfManager").classList.add("active");
    document.getElementById("filters").style.display = "none";
    document.getElementById("empMenu").classList.remove("active");
    renderEtfManager();
  }
  function tradeTicker(row) {
    const code = tickerKey(row.code);
    const name = tickerKey(row.name || row.ticker);
    const meta = DATA.etfs.find(etf => tickerKey(etf.isin) === code || tickerKey(etf.name) === name || tickerKey(etf.koreanName) === name) || {};
    return meta.ticker || row.security || row.ticker || row.code || "";
  }
  function displayTicker(value) {
    return String(value || "").replace(/\s+(US|KS)\s+EQUITY$/i, "");
  }
  function titled(value, className = "") {
    const text = String(value ?? "");
    return `<span class="${className}" title="${esc(text)}">${esc(text)}</span>`;
  }
  function renderDashboardTrades() {
    const panel = tradePanel;
    if (!panel) return;
    const heading = panel.querySelector("h2");
    const empOnly = state.dashboardSource === "emp" && state.empSelection?.length;
    if (heading) heading.textContent = empOnly ? "EMP \uB9E4\uB9E4\uB0B4\uC5ED" : "\uC218\uC775\uC99D\uAD8C \uB9E4\uB9E4\uB0B4\uC5ED (\uB2E8\uC704: \uBC31\uB9CC\uC6D0)";
    const wrap = panel.querySelector(".tablewrap");
    if (!wrap) return;
    if (empOnly) {
      wrap.innerHTML = `<div class="tradeEmpty">\uB9E4\uB9E4\uB0B4\uC5ED\uC774 \uC5C6\uC2B5\uB2C8\uB2E4.</div>`;
      return;
    }
    if (!document.getElementById("tradeTable")) wrap.innerHTML = `<table id="tradeTable"></table>`;
    const excludedTradeAsset = row => {
      const asset = String(row.asset || "");
      const large = String(row.large || "");
      const market = String(row.market || "");
      const name = String(row.name || "");
      const ticker = String(row.ticker || "");
      const raw = [asset, large, market, name, ticker].join(" ");
      return raw.includes("\uD604\uAE08\uC131\uC790\uC0B0") || raw.includes("\uC120\uBB3C\uC635\uC158\uD30C\uC0DD") || large === "\uD604\uAE08" || ticker === "\uD604\uAE08" || name.includes("CASHACC");
    };
    let rows = fundBase(DATA.trades).filter(row => !excludedTradeAsset(row));
    const q = (state.tradeSearch || "").toLowerCase();
    rows = rows.filter(x => !q || [x.fund, x.name, x.ticker, x.code].join(" ").toLowerCase().includes(q));
    const denom = selectedFundRows().reduce((sum, row) => sum + Number(row.lookthrough || 0), 0);
    const grouped = Object.values(rows.reduce((acc, row) => {
      const key = [row.fund, row.date, row.code || row.ticker || row.name].join("|");
      if (!acc[key]) acc[key] = { ...row, qty: 0, original: 0, lookthrough: 0, sides: new Set() };
      acc[key].qty += Number(row.qty || 0);
      acc[key].original += Number(row.original || 0);
      acc[key].lookthrough += Number(row.lookthrough || 0);
      acc[key].sides.add(row.side || "");
      acc[key].side = [...acc[key].sides].filter(Boolean).join("/");
      return acc;
    }, {}));
    table(document.getElementById("tradeTable"), [
      ["\uAE30\uC900\uC77C", x => x.date], ["\uD380\uB4DC", x => titled(x.fund)], ["\uAC70\uB798", x => esc(x.side)],
      ["\uC885\uBAA9", x => titled(x.name)], ["\uD2F0\uCEE4", x => titled(displayTicker(tradeTicker(x)))],
      ["\uB300\uBD84\uB958", x => titled(x.large)], ["\uC18C\uBD84\uB958", x => titled(x.small)],
      ["\uC2E4\uBCF4\uC720", x => `<span class="${x.lookthrough < 0 ? "neg" : ""}">${tradeMillionAmount(x.lookthrough)}</span>`, "num"],
      ["NAV \uB300\uBE44", x => `<span class="${x.lookthrough < 0 ? "neg" : ""}">${pct(denom ? x.lookthrough / denom : 0)}</span>`, "num"]
    ], grouped.sort((a, b) => String(b.date || "").localeCompare(String(a.date || "")) || Math.abs(b.lookthrough) - Math.abs(a.lookthrough)).slice(0, 1000));
  }
  function renderDashboardFundInfo() {
    if (document.getElementById("fundTable")) {
      const fields = [
        ["manager", "\uC6B4\uC6A9\uC0AC"], ["fund", "\uD380\uB4DC\uBA85"], ["depositCode", "\uC608\uD0C1\uC6D0\uCF54\uB4DC"],
        ["assocCode", "\uD611\uD68C\uCF54\uB4DC"], ["joinDate", "\uAC00\uC785\uC77C"], ["eval", "\uD3C9\uAC00\uAE08\uC561"], ["share", "\uC9C0\uBD84\uC728"]
      ];
      document.getElementById("fundTable").innerHTML = `<thead><tr><th><input class="etfCheck" type="checkbox" id="checkAllFunds"></th>${fields.map(([, label]) => `<th>${label}</th>`).join("")}</tr></thead><tbody>${DATA.funds.map((fund, i) => `<tr><td><input class="etfCheck" type="checkbox" data-fund-check="${i}" ${selectedFundInfoRows.has(i) ? "checked" : ""}></td>${fields.map(([key]) => {
        const value = key === "share" ? (Number(fund[key] || 0) * 100).toLocaleString("ko-KR", { maximumFractionDigits: 4 }) : key === "eval" ? Number(fund[key] || 0).toLocaleString("ko-KR") : esc(fund[key] || "");
        const inputClass = key === "fund" ? "fundInput wide" : ["eval", "share"].includes(key) ? "fundInput fundNumericInput" : "fundInput";
        return `<td><input class="${inputClass}" data-fund-i="${i}" data-fund-key="${key}" value="${value}"></td>`;
      }).join("")}</tr>`).join("")}</tbody>`;
      document.querySelectorAll("#fundTable input[data-fund-key]").forEach(input => input.onchange = () => {
        const row = DATA.funds[Number(input.dataset.fundI)];
        const key = input.dataset.fundKey;
        if (key === "eval") row[key] = parseNumber(input.value);
        else if (key === "share") row[key] = parseNumber(input.value) / 100;
        else row[key] = input.value.trim();
        markFundDirty();
        renderFilters();
      });
      document.querySelectorAll("#fundTable [data-fund-check]").forEach(input => input.onchange = () => {
        const index = Number(input.dataset.fundCheck);
        if (input.checked) selectedFundInfoRows.add(index);
        else selectedFundInfoRows.delete(index);
        renderDashboardFundInfo();
      });
      const checkAll = document.getElementById("checkAllFunds");
      checkAll.checked = DATA.funds.length > 0 && DATA.funds.every((_, i) => selectedFundInfoRows.has(i));
      checkAll.onchange = () => {
        DATA.funds.forEach((_, i) => {
          if (checkAll.checked) selectedFundInfoRows.add(i);
          else selectedFundInfoRows.delete(i);
        });
        renderDashboardFundInfo();
      };
    }
    if (document.getElementById("etfTable")) {
      const q = (state.etfSearch || "").toLowerCase();
      const rows = DATA.etfs.filter(x => !q || [x.koreanName, x.fullName, x.name, x.ticker, x.isin].join(" ").toLowerCase().includes(q));
      table(document.getElementById("etfTable"), [["ISIN", x => esc(x.isin)], ["티커", x => esc(x.name)], ["종목명", x => esc(x.koreanName)], ["상장", x => esc(x.listing)], ["투자국가", x => esc(x.country)], ["대분류", x => esc(x.large)], ["중분류", x => esc(x.mid)], ["소분류", x => esc(x.small)], ["EMP", x => esc(x.emp)]], rows);
    }
  }  function metricAmount(value) {
    const n = Number(value || 0);
    return `${Math.round(n / 100_000_000).toLocaleString("ko-KR")}\uC5B5\uC6D0`;
  }
  function plAmount(value) {
    const n = Number(value || 0) / 100_000_000;
    return `${n.toLocaleString("ko-KR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}\uC5B5\uC6D0`;
  }
  function tradeMillionAmount(value) {
    const n = Math.round(Number(value || 0) / 1_000_000);
    return n.toLocaleString("ko-KR");
  }
  function krwMillionAmount(value) {
    const n = Math.round(Number(value || 0) / 1_000_000);
    return n.toLocaleString("ko-KR");
  }
  function renderDashboardMetrics(rows) {
    const strip = document.getElementById("dashboardMetricStrip");
    if (!strip) return;
    const metricRows = dashboardMetricRows();
    const total = metricRows.reduce((sum, row) => sum + Number(row.lookthrough || 0), 0);
    const equity = metricRows.filter(isEquityAsset).reduce((sum, row) => sum + Number(row.lookthrough || 0), 0);
    const bond = metricRows.filter(isBondAsset).reduce((sum, row) => sum + Number(row.lookthrough || 0), 0);
    const other = metricRows.filter(row => !isEquityAsset(row) && !isBondAsset(row)).reduce((sum, row) => sum + Number(row.lookthrough || 0), 0);
    const empPnl = metricRows.filter(row => row.source === "emp").reduce((sum, row) => sum + Number(row.lookthrough || 0) * Number(row.change || 0), 0);
    const bondPnl = metricRows.filter(isBondAsset).reduce((sum, row) => sum + Number(row.lookthrough || 0) * Number(row.change || 0), 0);
    const fundPnl = metricRows.filter(row => row.source !== "emp").reduce((sum, row) => sum + Number(row.lookthrough || 0) * Number(row.change || 0), 0);
    const hedge = hedgeRatioForFunds();
    const cards = [
      ["\uC804\uCCB4\uC775\uC2A4\uD3EC\uC838", metricAmount(total)],
      ["\uC8FC\uC2DD\uC775\uC2A4\uD3EC\uC838", metricAmount(equity)],
      ["\uCC44\uAD8C\uC775\uC2A4\uD3EC\uC838", metricAmount(bond)],
      ["\uAE30\uD0C0\uC775\uC2A4\uD3EC\uC838", metricAmount(other)],
      ["\uC218\uC775\uC99D\uAD8C \uD658\uD5F7\uC9C0 \uBE44\uC728", hedge == null ? "-" : pct(hedge)],
      ["EMP PL", plAmount(empPnl), empPnl],
      ["\uCC44\uAD8C\uD615 PL", plAmount(bondPnl), bondPnl],
      ["\uC218\uC775\uC99D\uAD8C PL", plAmount(fundPnl), fundPnl]
    ];
    strip.innerHTML = cards.map(([label, value, signed]) => `<div class="metricCard"><span>${label}</span><b class="${Number(signed || 0) < 0 ? "neg" : Number(signed || 0) > 0 ? "pos" : ""}">${value}</b></div>`).join("");
  }  function renderDashboardAssetCharts() {
    const rows = currentDashboardRows();
    const total = rows.reduce((sum, row) => sum + Number(row.lookthrough || 0), 0);
    const fundOnly = state.dashboardSource === "fund" && state.fund.length;
    const empOnly = state.dashboardSource === "emp" && state.empSelection?.length;
    const label = fundOnly ? selectionLabel(state.fund, "전체 수익증권") : empOnly ? selectionLabel(state.empSelection, "전체 EMP") : "전체 포지션";
    const title = fundOnly ? "수익증권 자산 비중" : empOnly ? "EMP 자산 비중" : "전체 포지션 자산 비중";
    updatePanelHeader(currentFundPanel, title, `${label} · ${dimensionLabel()}`, "toggleFundAssetPanel");
    const heading = currentFundPanel.querySelector("h2");
    if (heading && !heading.querySelector(".assetModeTools")) {
      heading.insertAdjacentHTML("beforeend", `<span class="assetModeTools"><button class="assetModeBtn ${state.showMidDimension ? "active" : ""}" id="toggleMidDimension" type="button">중분류</button></span>`);
      document.getElementById("toggleMidDimension").onclick = () => {
        state.showMidDimension = !state.showMidDimension;
        render();
      };
    }
    const midButton = document.getElementById("toggleMidDimension");
    if (midButton) midButton.classList.toggle("active", state.showMidDimension);
    renderDashboardMetrics(rows);
    shares(document.getElementById("assetChart"), hierarchical(rows, activeDimensions(), total));
    renderPie("largePieChart", "largePieLegend", rows, "large");
    renderPie("countryPieChart", "countryPieLegend", rows, "country");
    renderDashboardTrades();
  }
  function summaryEmpNames() {
    return state.empSelection?.length ? state.empSelection : Object.keys(DATA.emp.portfolios);
  }
  function summarizeEmpPortfolios() {
    const names = summaryEmpNames();
    return names.reduce((summary, name) => {
      const principal = Number(DATA.emp.principals[name] || 0);
      const rows = DATA.emp.portfolios[name] || [];
      rows.forEach(row => {
        const value = localToUsd(Number(row.quantity || 0) * Number(row.price || 0), row.security);
        const krw = value * Number(state.fx || 1);
        const pnl = krw * Number(row.change || 0);
        summary.value += value;
        summary.krw += krw;
        summary.pnl += pnl;
      });
      summary.principal += principal;
      return summary;
    }, { principal: 0, value: 0, krw: 0, pnl: 0 });
  }

  function changeBar(value) {
    const change = Number(value || 0);
    const capped = Math.max(-0.05, Math.min(0.05, change));
    const width = Math.abs(capped) / 0.05 * 50;
    const cls = capped < 0 ? "changeFill neg" : "changeFill";
    return `<div class="changeBar" title="${pct(change)}"><span class="${cls}" style="width:${width.toFixed(1)}%"></span><span class="changeBarText">${pct(change)}</span></div>`;
  }

  function pct2(value) {
    return `${(Number(value || 0) * 100).toFixed(2)}%`;
  }

  renderEmp = function () {
    const rows = empRows();
    const principal = Number(DATA.emp.principals[state.emp] || 0);
    const metrics = rows.map(empMetrics);
    const total = metrics.reduce((s, x) => s + x.value, 0);
    const totalKrw = metrics.reduce((s, x) => s + x.krw, 0);
    const pnl = metrics.reduce((s, x) => s + x.pnl, 0);
    const summary = summarizeEmpPortfolios();
    document.getElementById("empTitle").textContent = `${state.emp}호 EMP상세`;
    document.getElementById("ePrincipal").textContent = amount(summary.principal);
    document.getElementById("eValue").textContent = won(summary.krw);
    document.getElementById("eWeight").textContent = pct(summary.principal ? summary.value / summary.principal : 0);
    document.getElementById("ePnl").textContent = won(summary.pnl);
    document.getElementById("ePnl").className = summary.pnl < 0 ? "neg" : "pos";
    document.getElementById("eFx").textContent = state.fx === 1 ? "조회 전" : amount(state.fx);

    renderDashboardAssetCharts();

    const headers = ["선택", "종목", "종목명", "상장", "투자국가", "대분류", "중분류", "소분류", "시총", "3M Avg", "보유수량", "종가", "평가금액", "등락율(전일)", "손익(원화)", "현재비중", "목표비중", "차이", "거래방향", "거래수량", "거래금액(전일종가)"];
    const groups = {};
    rows.forEach((row, index) => {
      const meta = securityEtf(row.security);
      const large = meta.large || "미분류";
      (groups[large] ||= []).push({ row, index, meta, metric: metrics[index] });
    });
    let body = "";
    Object.entries(groups).forEach(([large, list]) => {
      const groupMetrics = list.map(x => x.metric);
      const groupValue = groupMetrics.reduce((s, m) => s + m.value, 0);
      const groupQty = list.reduce((s, item) => s + Number(item.row.quantity || 0), 0);
      const groupPnl = groupMetrics.reduce((s, m) => s + m.pnl, 0);
      const groupTarget = groupMetrics.reduce((s, m) => s + m.target, 0);
      const groupTradeQty = groupMetrics.reduce((s, m) => s + m.tradeQty, 0);
      const groupTradeAmount = groupMetrics.reduce((s, m) => s + m.tradeAmount, 0);
      list.forEach(({ row, index: i, meta, metric: m }) => {
        const side = m.signedTradeQty > 0 ? "매수" : m.signedTradeQty < 0 ? "매도" : "유지";
        const targetValue = row.targetWeightDraft ?? formatPercentInput(m.target * 100);
        body += `<tr><td><input class="rowCheck" type="checkbox" data-row-check="${i}" ${selectedRows.has(i) ? "checked" : ""}></td><td>${esc(row.security)}</td><td>${esc(meta.koreanName || meta.fullName || "")}</td><td>${esc(meta.listing || "")}</td><td>${esc(meta.country || "")}</td><td>${esc(meta.large || "미분류")}</td><td>${esc(meta.mid || "")}</td><td>${esc(meta.small || "")}</td><td class="num">${integerAmount(marketDisplayAmount(row.marketCap, row.security))}</td><td class="num">${integerAmount(marketDisplayAmount(row.avgTurnover3m, row.security))}</td><td class="manualCell"><input class="manualInput" data-i="${i}" data-key="quantity" inputmode="numeric" value="${Number(row.quantity || 0).toLocaleString("ko-KR")}"></td><td class="num">${amount(row.price)}</td><td class="num">${amount(m.value)}</td><td class="changeBarCell">${changeBar(row.change)}</td><td class="num ${m.pnl < 0 ? "neg" : "pos"}">${krwMillionAmount(m.pnl)}</td><td class="num">${pct2(m.current)}</td><td class="manualCell ${row.targetTouched && Math.abs(m.gap) >= 0.00005 ? "manualChanged" : ""}"><input class="manualInput targetWeightInput" data-i="${i}" data-key="targetWeight" inputmode="decimal" value="${esc(targetValue)}"></td><td class="num ${m.gap < 0 ? "neg" : "pos"}">${pct(m.gap)}</td><td>${side}</td><td class="num">${m.tradeQty.toLocaleString("ko-KR")}</td><td class="num">${amount(m.tradeAmount)}</td></tr>`;
      });
      body += `<tr class="subtotalRow"><td></td><td colspan="9">${esc(large)} 소계</td><td class="num">${groupQty.toLocaleString("ko-KR")}</td><td></td><td class="num">${amount(groupValue)}</td><td></td><td class="num ${groupPnl < 0 ? "neg" : "pos"}">${krwMillionAmount(groupPnl)}</td><td class="num">${pct2(principal ? groupValue / principal : 0)}</td><td class="num">${pct(groupTarget)}</td><td></td><td></td><td class="num">${groupTradeQty.toLocaleString("ko-KR")}</td><td class="num">${amount(groupTradeAmount)}</td></tr>`;
    });
    const totalQty = rows.reduce((sum, row) => sum + Number(row.quantity || 0), 0);
    const totalTarget = metrics.reduce((sum, metric) => sum + metric.target, 0);
    const totalTradeQty = metrics.reduce((sum, metric) => sum + metric.tradeQty, 0);
    const totalTradeAmount = metrics.reduce((sum, metric) => sum + metric.tradeAmount, 0);
    body += `<tr class="totalRow"><td></td><td colspan="9">총계</td><td class="num">${totalQty.toLocaleString("ko-KR")}</td><td></td><td class="num">${amount(total)}</td><td></td><td class="num ${pnl < 0 ? "neg" : "pos"}">${krwMillionAmount(pnl)}</td><td class="num">${pct2(principal ? total / principal : 0)}</td><td class="num">${pct(totalTarget)}</td><td></td><td></td><td class="num">${totalTradeQty.toLocaleString("ko-KR")}</td><td class="num">${amount(totalTradeAmount)}</td></tr>`;
    const colWidths = [2, 5.5, 6, 3, 3.5, 3.5, 3.5, 3.5, 4.5, 4.5, 4.5, 3.5, 5, 3.8, 5.2, 4, 4, 3.5, 3.2, 4.2, 5.2];
    document.getElementById("empTable").innerHTML = `<caption class="empTableMeta">시총·3M Avg 단위: 미국 상장 ETF 백만불 / 한국 상장 ETF 백만원</caption><colgroup>${colWidths.map(width => `<col style="width:${width}%">`).join("")}</colgroup><thead><tr>${headers.map(x => `<th>${x}</th>`).join("")}</tr></thead><tbody>${body}</tbody>`;
    document.querySelectorAll("#empTable input[data-i][data-key]").forEach(input => {
      if (input.dataset.key === "targetWeight") {
        input.oninput = () => editEmp(Number(input.dataset.i), input.dataset.key, input.value, false);
        input.onchange = () => editEmp(Number(input.dataset.i), input.dataset.key, input.value, true);
        input.onkeydown = event => {
          if (event.key === "Enter") {
            event.preventDefault();
            input.blur();
          }
        };
      } else {
        input.onchange = () => editEmp(Number(input.dataset.i), input.dataset.key, input.value);
      }
    });
    document.querySelectorAll("#empTable [data-row-check]").forEach(input => input.onchange = () => {
      const index = Number(input.dataset.rowCheck);
      if (input.checked) selectedRows.add(index);
      else selectedRows.delete(index);
    });
  };

  function renderPicker() {
    const q = document.getElementById("pickerSearch").value.trim().toLowerCase();
    const existing = new Set(empRows().map(r => r.security.toUpperCase()));
    const rows = empEtfs().filter(e => !existing.has(String(e.ticker || "").toUpperCase())).filter(e => !q || [e.ticker, e.koreanName, e.country, e.large, e.mid, e.small].join(" ").toLowerCase().includes(q));
    document.getElementById("pickerTitle").textContent = `${state.emp} 라벨 ETF 선택 · ${pickerSelected.size}개 추가됨`;
    document.getElementById("pickerTray").innerHTML = [...pickerSelected].map(ticker => `<span class="pickerChip">${esc(ticker)}<button type="button" data-tray-remove="${esc(ticker)}">×</button></span>`).join("");
    document.querySelectorAll("#pickerTray [data-tray-remove]").forEach(button => button.onclick = () => { pickerSelected.delete(button.dataset.trayRemove); renderPicker(); });
    document.getElementById("pickerTable").innerHTML = `<thead><tr><th><input class="pickerCheck" type="checkbox" id="pickerCheckAll"></th><th>추가</th><th>티커</th><th>종목명</th><th>상장</th><th>투자국가</th><th>대분류</th><th>중분류</th><th>소분류</th></tr></thead><tbody>${rows.map((e, i) => { const ticker = String(e.ticker || ""); return `<tr><td><input class="pickerCheck" type="checkbox" data-pick-check="${i}" ${pickerSelected.has(ticker) ? "checked" : ""}></td><td><button class="pickBtn ${pickerSelected.has(ticker) ? "added" : ""}" data-pick="${i}">${pickerSelected.has(ticker) ? "추가됨" : "추가"}</button></td><td>${esc(e.ticker)}</td><td>${esc(e.koreanName)}</td><td>${esc(e.listing)}</td><td>${esc(e.country)}</td><td>${esc(e.large)}</td><td>${esc(e.mid)}</td><td>${esc(e.small)}</td></tr>`; }).join("")}</tbody>`;
    document.querySelectorAll("#pickerTable [data-pick-check]").forEach(input => input.onchange = () => {
      const ticker = String(rows[Number(input.dataset.pickCheck)]?.ticker || "");
      if (!ticker) return;
      if (input.checked) pickerSelected.add(ticker);
      else pickerSelected.delete(ticker);
    });
    const checkAll = document.getElementById("pickerCheckAll");
    checkAll.checked = rows.length > 0 && rows.every(e => pickerSelected.has(String(e.ticker || "")));
    checkAll.onchange = () => {
      rows.forEach(e => {
        const ticker = String(e.ticker || "");
        if (!ticker) return;
        if (checkAll.checked) pickerSelected.add(ticker);
        else pickerSelected.delete(ticker);
      });
      renderPicker();
    };
    document.querySelectorAll("#pickerTable [data-pick]").forEach(button => button.onclick = () => {
      const e = rows[Number(button.dataset.pick)];
      const ticker = String(e?.ticker || "");
      if (!ticker) return;
      pickerSelected.add(ticker);
      renderPicker();
    });
  }

  document.getElementById("addEmpRow").onclick = () => { document.getElementById("pickerSearch").value = ""; pickerSelected.clear(); picker.classList.add("active"); renderPicker(); };
  document.getElementById("pickSelectedEtfs").onclick = async () => {
    const applyButton = document.getElementById("pickSelectedEtfs");
    const status = document.getElementById("empStatus");
    const existing = new Set(empRows().map(row => String(row.security || "").toUpperCase()));
    const selected = [...pickerSelected].filter(ticker => !existing.has(String(ticker).toUpperCase()));
    if (!selected.length) {
      document.getElementById("pickerTitle").textContent = `${state.emp} 라벨 ETF 선택 · 선택된 종목 없음`;
      return;
    }
    const insertedRows = insertEmpRows(selected.map(emptyEmpRow));
    pickerSelected.clear();
    picker.classList.remove("active");
    applyButton.disabled = true;
    if (status) {
      status.classList.remove("dirty");
      status.textContent = `${selected.length}개 신규 종목 Bloomberg 조회 중...`;
    }
    try {
      const result = await refreshInsertedEmpRows(insertedRows);
      renderEmp();
      render();
      if (status) {
        status.textContent = result.failed.length
          ? `${result.count}개 신규 종목 조회 완료 · 실패: ${result.failed.join(", ")}`
          : `${result.count}개 신규 종목 Bloomberg 조회 완료`;
        status.classList.toggle("dirty", result.failed.length > 0);
      }
    } catch (error) {
      if (status) {
        status.textContent = `신규 종목 Bloomberg 조회 실패: ${error.message}`;
        status.classList.add("dirty");
      }
    } finally {
      applyButton.disabled = false;
    }
  };
  document.getElementById("deleteSelectedEmpRows").onclick = () => {
    if (!selectedRows.size) {
      document.getElementById("empStatus").textContent = "삭제할 행을 체크하세요";
      return;
    }
    const rows = empRows();
    [...selectedRows].sort((a, b) => b - a).forEach(index => rows.splice(index, 1));
    selectedRows.clear();
    markEmpDirty("행 삭제됨 · 변경저장을 눌러 확정");
    renderEmp();
  };
  document.getElementById("saveEmpChanges").onclick = async () => {
    await saveEmp();
    clearEmpDirty();
  };
  document.getElementById("resetEmpTargets").onclick = () => {
    empRows().forEach(row => {
      row.targetTouched = false;
      delete row.targetWeight;
    });
    selectedRows.clear();
    markEmpDirty("목표비중 초기화됨 · 변경저장을 눌러 확정");
    renderEmp();
  };
  function exportEmpTrades() {
    const rows = empRows().map(row => ({ row, metric: empMetrics(row) }));
    const headers = ["종목", "보유수량", "거래방향", "거래수량", "거래금액(전일종가)"];
    const body = rows.map(({ row, metric }) => {
      const side = metric.signedTradeQty > 0 ? "매수" : metric.signedTradeQty < 0 ? "매도" : "유지";
      return [row.security, Number(row.quantity || 0), side, metric.tradeQty, metric.tradeAmount];
    });
    const cell = value => `<td>${esc(value)}</td>`;
    const html = `<!doctype html><html><head><meta charset="utf-8"></head><body><table><thead><tr>${headers.map(h => `<th>${esc(h)}</th>`).join("")}</tr></thead><tbody>${body.map(row => `<tr>${row.map(cell).join("")}</tr>`).join("")}</tbody></table></body></html>`;
    const link = document.createElement("a");
    link.href = `data:application/vnd.ms-excel;charset=utf-8,${encodeURIComponent(html)}`;
    link.download = `${state.emp}_거래정보_${new Date().toISOString().slice(0, 10)}.xls`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    const status = document.getElementById("empStatus");
    if (status) status.textContent = "거래정보 엑셀 추출 완료";
  }  document.getElementById("exportEmpTrades").addEventListener("click", exportEmpTrades);
  document.getElementById("closePicker").onclick = () => picker.classList.remove("active");
  document.getElementById("pickerSearch").oninput = renderPicker;

  function renderEtfManager() {
    const q = document.getElementById("etfManagerSearch").value.trim().toLowerCase();
    const fields = [["ticker", "Bloomberg 티커"], ["koreanName", "종목명"], ["listing", "상장"], ["country", "투자국가"], ["large", "대분류"], ["mid", "중분류"], ["small", "소분류"], ["emp", "EMP 일괄"]];
    const collator = new Intl.Collator("ko-KR", { numeric: true, sensitivity: "base" });
    const sortedIndices = DATA.etfs.map((e, i) => ({ e, i }))
      .filter(({ e }) => !q || fields.map(([key]) => e[key] || "").join(" ").toLowerCase().includes(q))
      .sort((a, b) => {
        const av = a.e[etfSort.key] ?? "";
        const bv = b.e[etfSort.key] ?? "";
        return collator.compare(String(av), String(bv)) * etfSort.direction;
      });
    const header = fields.map(([key, label]) => {
      const mark = etfSort.key === key ? (etfSort.direction > 0 ? " ▲" : " ▼") : "";
      return `<th><button class="sortHeader" type="button" data-etf-sort="${key}">${label}${mark}</button></th>`;
    }).join("");
    document.getElementById("etfManagerTable").innerHTML = `<thead><tr><th><input class="etfCheck" type="checkbox" id="checkAllEtfs"></th>${header}</tr></thead><tbody>${sortedIndices.map(({ e, i }) => `<tr><td><input class="etfCheck" type="checkbox" data-etf-check="${i}" ${selectedEtfRows.has(i) ? "checked" : ""}></td>${fields.map(([key]) => `<td><input class="etfInput ${key === "koreanName" ? "wide" : ""}" data-etf-i="${i}" data-etf-key="${key}" value="${esc(e[key] || "")}"></td>`).join("")}</tr>`).join("")}</tbody>`;
    document.querySelectorAll("#etfManagerTable [data-etf-sort]").forEach(button => button.onclick = () => {
      const key = button.dataset.etfSort;
      etfSort = etfSort.key === key ? { key, direction: etfSort.direction * -1 } : { key, direction: 1 };
      renderEtfManager();
    });
    document.querySelectorAll("#etfManagerTable input[data-etf-key]").forEach(input => input.onchange = () => {
      DATA.etfs[Number(input.dataset.etfI)][input.dataset.etfKey] = input.value.trim();
      markEtfDirty();
    });
    document.querySelectorAll("#etfManagerTable [data-etf-check]").forEach(input => input.onchange = () => {
      const index = Number(input.dataset.etfCheck);
      if (input.checked) selectedEtfRows.add(index);
      else selectedEtfRows.delete(index);
      renderEtfManager();
    });
    const checkAll = document.getElementById("checkAllEtfs");
    checkAll.checked = sortedIndices.length > 0 && sortedIndices.every(({ i }) => selectedEtfRows.has(i));
    checkAll.onchange = () => {
      sortedIndices.forEach(({ i }) => {
        if (checkAll.checked) selectedEtfRows.add(i);
        else selectedEtfRows.delete(i);
      });
      renderEtfManager();
    };
  }  document.getElementById("etfManagerSearch").oninput = renderEtfManager;
  document.getElementById("deleteSelectedEtfs").onclick = () => {
    if (!selectedEtfRows.size) {
      const status = document.getElementById("etfStatus");
      status.textContent = "삭제할 ETF를 선택하세요";
      return;
    }
    [...selectedEtfRows].sort((a, b) => b - a).forEach(index => DATA.etfs.splice(index, 1));
    selectedEtfRows.clear();
    markEtfDirty("선택 ETF 삭제됨 · 변경저장을 눌러 확정");
    renderEtfManager();
  };
  document.getElementById("saveEtfChanges").onclick = async () => {
    await saveEtfs();
    clearEtfDirty();
  };
  document.getElementById("addFundInfo").onclick = () => {
    DATA.funds.push({ manager: "", fund: "", depositCode: "", assocCode: "", joinDate: "", eval: 0, share: 0 });
    selectedFundInfoRows.clear();
    selectedFundInfoRows.add(DATA.funds.length - 1);
    markFundDirty("펀드 행 추가됨 · 변경저장을 눌러 확정");
    renderDashboardFundInfo();
    renderFilters();
  };
  document.getElementById("deleteSelectedFunds").onclick = () => {
    if (!selectedFundInfoRows.size) {
      const status = document.getElementById("fundStatus");
      if (status) status.textContent = "삭제할 펀드를 선택하세요";
      return;
    }
    [...selectedFundInfoRows].sort((a, b) => b - a).forEach(index => DATA.funds.splice(index, 1));
    selectedFundInfoRows.clear();
    state.fund = state.fund.filter(name => DATA.funds.some(fund => fund.fund === name));
    markFundDirty("선택 펀드 삭제됨 · 변경저장을 눌러 확정");
    renderDashboardFundInfo();
    renderFilters();
    renderDashboardAssetCharts();
  };
  document.getElementById("saveFundChanges").onclick = async () => {
    await saveFunds();
    clearFundDirty();
    renderFilters();
    renderDashboardAssetCharts();
  };
  function renderEmpInfoManager() {
    const names = Object.keys(DATA.emp.portfolios || {});
    document.getElementById("empInfoTable").innerHTML = `<thead><tr><th><input class="etfCheck" type="checkbox" id="checkAllEmpInfo"></th><th>EMP</th><th>원금</th><th>보유종목</th></tr></thead><tbody>${names.map(name => `<tr><td><input class="etfCheck" type="checkbox" data-emp-info-check="${esc(name)}" ${selectedEmpInfoRows.has(name) ? "checked" : ""}></td><td><input class="empInfoInput" data-emp-info-name="${esc(name)}" value="${esc(name)}"></td><td><input class="empInfoInput empPrincipalInput" data-emp-info-principal="${esc(name)}" inputmode="numeric" value="${Number(DATA.emp.principals[name] || 0).toLocaleString("ko-KR")}"></td><td class="num">${(DATA.emp.portfolios[name] || []).length.toLocaleString("ko-KR")}</td></tr>`).join("")}</tbody>`;
    document.querySelectorAll("#empInfoTable [data-emp-info-check]").forEach(input => input.onchange = () => {
      const name = input.dataset.empInfoCheck;
      if (input.checked) selectedEmpInfoRows.add(name);
      else selectedEmpInfoRows.delete(name);
      renderEmpInfoManager();
    });
    const checkAll = document.getElementById("checkAllEmpInfo");
    checkAll.checked = names.length > 0 && names.every(name => selectedEmpInfoRows.has(name));
    checkAll.onchange = () => {
      names.forEach(name => {
        if (checkAll.checked) selectedEmpInfoRows.add(name);
        else selectedEmpInfoRows.delete(name);
      });
      renderEmpInfoManager();
    };
    document.querySelectorAll("#empInfoTable [data-emp-info-name]").forEach(input => input.onchange = () => {
      const oldName = input.dataset.empInfoName;
      const newName = input.value.trim();
      if (!newName || oldName === newName || DATA.emp.portfolios[newName]) {
        input.value = oldName;
        return;
      }
      DATA.emp.portfolios[newName] = DATA.emp.portfolios[oldName] || [];
      DATA.emp.principals[newName] = Number(DATA.emp.principals[oldName] || 0);
      delete DATA.emp.portfolios[oldName];
      delete DATA.emp.principals[oldName];
      if (state.emp === oldName) state.emp = newName;
      state.empSelection = (state.empSelection || []).map(name => name === oldName ? newName : name);
      if (selectedEmpInfoRows.delete(oldName)) selectedEmpInfoRows.add(newName);
      markEmpInfoDirty();
      renderEmpInfoManager();
      renderEmpMenu();
      render();
    });
    document.querySelectorAll("#empInfoTable [data-emp-info-principal]").forEach(input => input.onchange = () => {
      DATA.emp.principals[input.dataset.empInfoPrincipal] = parseNumber(input.value);
      markEmpInfoDirty();
      renderEmpInfoManager();
      renderEmpMenu();
      render();
    });
  }
  document.getElementById("addEmpInfo").onclick = () => {
    let index = Object.keys(DATA.emp.portfolios || {}).length + 1;
    let name = `EMP${index}`;
    while (DATA.emp.portfolios[name]) {
      index += 1;
      name = `EMP${index}`;
    }
    DATA.emp.portfolios[name] = [];
    DATA.emp.principals[name] = 0;
    state.emp = name;
    state.empSelection = [name];
    selectedEmpInfoRows.clear();
    selectedEmpInfoRows.add(name);
    markEmpInfoDirty("EMP 추가됨 · 변경저장을 눌러 확정");
    renderEmpInfoManager();
    renderEmpMenu();
    render();
  };
  document.getElementById("deleteSelectedEmpInfo").onclick = () => {
    if (!selectedEmpInfoRows.size) {
      const status = document.getElementById("empInfoStatus");
      status.textContent = "삭제할 EMP를 선택하세요";
      return;
    }
    [...selectedEmpInfoRows].forEach(name => {
      delete DATA.emp.portfolios[name];
      delete DATA.emp.principals[name];
    });
    selectedEmpInfoRows.clear();
    const names = Object.keys(DATA.emp.portfolios || {});
    if (!names.includes(state.emp)) state.emp = names[0] || "";
    state.empSelection = (state.empSelection || []).filter(name => names.includes(name));
    markEmpInfoDirty("선택 EMP 삭제됨 · 변경저장을 눌러 확정");
    renderEmpInfoManager();
    renderEmpMenu();
    render();
  };
  document.getElementById("saveEmpInfoChanges").onclick = async () => {
    await saveEmp();
    clearEmpInfoDirty();
  };
  document.getElementById("empTable").addEventListener("input", event => {
    const input = event.target.closest("input[data-i][data-key]");
    if (!input) return;
    input.closest("td")?.classList.add("manualChanged");
    const status = document.getElementById("empStatus");
    status.textContent = "입력 중 · 변경저장을 눌러 확정";
    status.classList.add("dirty");
  });  document.getElementById("addEtfMaster").onclick = () => { DATA.etfs.unshift({ ticker: "", name: "", koreanName: "", listing: "", country: "", large: "", mid: "", small: "", emp: state.emp }); selectedEtfRows.clear(); markEtfDirty("ETF 추가됨 · 변경저장을 눌러 확정"); renderEtfManager(); };
  unclassifiedButton.onclick = () => {
    const rows = unclassifiedCandidates();
    const search = document.getElementById("etfManagerSearch");
    if (search) search.value = "";
    activateEtfManager();
    if (!rows.length) {
      const status = document.getElementById("etfStatus");
      if (status) {
        status.textContent = "추가할 미분류 종목이 없습니다";
        status.classList.remove("dirty");
      }
      return;
    }
    DATA.etfs.unshift(...rows);
    selectedEtfRows.clear();
    rows.forEach((_, index) => selectedEtfRows.add(index));
    markEtfDirty(`${rows.length}개 미분류 종목 추가됨 · 정보를 입력한 뒤 변경저장`);
    renderEtfManager();
  };

  const marketApiUrl = () => {
    return window.GLOBAL_BLOOMBERG_API_URL || "http://127.0.0.1:8766/api/emp-market";
  };
  const parseFxValue = value => {
    const n = Number(String(value ?? "").replaceAll(",", ""));
    return Number.isFinite(n) && n > 100 ? n : 0;
  };
  async function fetchFxOnly() {
    const res = await fetch(marketApiUrl(), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ securities: [] })
    });
    const payload = await res.json().catch(() => ({}));
    return res.ok ? parseFxValue(payload.fx) : 0;
  }
  function bestKnownFx() {
    const candidates = [
      state.fx,
      JSON.parse(localStorage.getItem("globalDashboard.market") || "null")?.fx,
      JSON.parse(localStorage.getItem("globalDashboard.emp") || "null")?.fx,
      DATA.market?.fx
    ];
    return candidates.map(parseFxValue).find(Boolean) || 0;
  }
  async function refreshInsertedEmpRows(rows) {
    const targets = rows.filter(row => row?.security);
    if (!targets.length) return { count: 0, failed: [] };
    const securities = [...new Set(targets.flatMap(row => securityRequests(row.security)))];
    const res = await fetch(marketApiUrl(), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ securities })
    });
    const payload = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(payload.error || "Bloomberg 신규종목 조회 실패");
    const nextFx = parseFxValue(payload.fx) || bestKnownFx();
    if (nextFx) state.fx = nextFx;
    const map = payload.securities || {};
    let count = 0;
    const failed = [];
    targets.forEach(row => {
      if (applyEmpMarketRow(row, map)) count += 1;
      else failed.push(row.security);
    });
    const previousMarket = JSON.parse(localStorage.getItem("globalDashboard.market") || "null") || {};
    const market = {
      fx: state.fx,
      securities: { ...(previousMarket.securities || {}), ...map },
      asOf: payload.asOf || previousMarket.asOf || ""
    };
    localStorage.setItem("globalDashboard.market", JSON.stringify(market));
    await Promise.allSettled([saveGlobalMarketData(market), saveEmp()]);
    return { count, failed, asOf: payload.asOf || "" };
  }
  refreshMarket = async function () {
    const status = document.getElementById("empStatus");
    const button = document.getElementById("refreshMarket");
    const originalText = button.textContent;
    status.classList.remove("dirty");
    status.textContent = "Supabase DB 상태 확인 중...";
    button.textContent = "업데이트 중...";
    button.disabled = true;
    try {
      if (globalDbLoadPromise) await globalDbLoadPromise.catch(() => false);
      const allRows = Object.values(DATA.emp.portfolios).flat();
      const fundRows = DATA.holdings.filter(row => !row.isFx && row.security);
      const fundSecurities = fundRows.flatMap(row => [row.security, tradeTicker(row)]).filter(Boolean);
      const empSecurities = allRows.flatMap(row => securityRequests(row.security));
      status.textContent = "Bloomberg 데이터 업데이트 중...";
      const res = await fetch(marketApiUrl(), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ securities: [...new Set([...empSecurities, ...fundSecurities.flatMap(securityRequests)])] })
      });
      const payload = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(payload.error || "Bloomberg 조회 실패");
      const nextFx = parseFxValue(payload.fx) || await fetchFxOnly().catch(() => 0) || bestKnownFx();
      if (nextFx) state.fx = nextFx;
      const fxNode = document.getElementById("eFx");
      if (fxNode) fxNode.textContent = state.fx === 1 ? "조회 전" : amount(state.fx);
      const map = payload.securities || {};
      allRows.forEach(row => applyEmpMarketRow(row, map));
      const missingEmpSecurities = [...new Set(allRows
        .filter(row => row.security && !marketMatch(map, row.security))
        .flatMap(row => securityRequests(row.security)))];
      if (missingEmpSecurities.length) {
        const retryRes = await fetch(marketApiUrl(), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ securities: missingEmpSecurities })
        });
        const retryPayload = await retryRes.json().catch(() => ({}));
        if (retryRes.ok && retryPayload.securities) {
          Object.assign(map, retryPayload.securities);
          allRows.forEach(row => applyEmpMarketRow(row, retryPayload.securities));
        }
      }
      fundRows.forEach(row => {
        const updated = marketMatch(map, row.security) || marketMatch(map, tradeTicker(row));
        if (updated && updated.change !== undefined) row.change = Number(updated.change || 0);
        if (updated && updated.price !== undefined) row.marketPrice = Number(updated.price || 0);
        if (updated && updated.prevClose !== undefined) row.prevClose = Number(updated.prevClose || 0);
      });
      const market = { fx: state.fx, securities: map, asOf: payload.asOf || "" };
      localStorage.setItem("globalDashboard.market", JSON.stringify(market));
      const dbResults = await Promise.allSettled([saveGlobalMarketData(market), saveEmp()]);
      renderEmp();
      render();
      button.textContent = `${Object.keys(map).length.toLocaleString("ko-KR")}종목 갱신`;
      const failedDbSave = dbResults.find(result => result.status === "rejected");
      const fxLabel = state.fx === 1 ? "조회 전" : amount(state.fx);
      clearEmpDirty(failedDbSave
        ? `${payload.asOf || ""} · 업데이트 완료 · 환율 ${fxLabel} · DB 저장 실패: ${failedDbSave.reason?.message || failedDbSave.reason}`
        : `${payload.asOf || ""} · ${Object.keys(map).length}종목 업데이트 · 환율 ${fxLabel}`);
    } catch (error) {
      button.textContent = "업데이트 실패";
      status.textContent = `오류: ${error.message === "Failed to fetch" ? "대시보드 서버를 실행한 뒤 다시 시도하세요" : error.message}`;
      status.classList.remove("dirty");
    } finally {
      button.disabled = false;
      setTimeout(() => {
        if (!button.disabled) button.textContent = originalText;
      }, 2200);
    }
  };  document.getElementById("refreshMarket").onclick = refreshMarket;

  renderEmpMenu = function () {
    const nav = document.getElementById("empNav");
    const names = Object.keys(DATA.emp.portfolios);
    nav.innerHTML = `<div class="filter empPortfolioFilter"><div class="filterHead"><h3>EMP</h3><button class="multiBtn ${state.multiEmp ? "active" : ""}" data-emp-action="multi">중복</button><button class="miniAll" data-emp-action="clear">해제</button></div><div class="chips">${names.map(name => `<button title="${name}호 · 원금 ${amount(DATA.emp.principals[name])}" class="chip ${(state.empSelection || []).includes(name) ? "active" : ""}" data-emp="${name}">${name}호</button>`).join("")}</div></div>`;
    nav.querySelectorAll("button").forEach(button => button.onclick = () => {
      if (button.dataset.empAction === "multi") {
        state.multiEmp = !state.multiEmp;
        if (!state.multiEmp && state.empSelection.length > 1) state.empSelection = state.empSelection.slice(0, 1);
      } else if (button.dataset.empAction === "clear") {
        if (!(state.empSelection || []).length) return;
        state.empSelection = [];
        state.multiEmp = false;
      } else if (button.dataset.emp) {
        const name = button.dataset.emp;
        state.emp = name;
        if (state.multiEmp) {
          const index = state.empSelection.indexOf(name);
          if (index >= 0) state.empSelection.splice(index, 1);
          else state.empSelection.push(name);
        } else {
          state.empSelection = [name];
        }
        selectedRows.clear();
      }
      renderEmpMenu();
      renderEmp();
    });
  };
  document.querySelectorAll(".tab").forEach(button => button.onclick = () => {
    state.activeTab = button.dataset.tab;
    document.querySelectorAll(".tab,.pane").forEach(x => x.classList.remove("active"));
    button.classList.add("active"); document.getElementById(button.dataset.tab).classList.add("active");
    document.getElementById("filters").style.display = state.activeTab === "dashboard" ? "block" : "none";
    document.getElementById("empMenu").classList.toggle("active", state.activeTab === "emp");
    if (["dashboard", "emp"].includes(state.activeTab)) renderEmp();
    if (state.activeTab === "etfManager") renderEtfManager();
    if (state.activeTab === "empInfoManager") renderEmpInfoManager();
  });
  document.getElementById("reset").onclick = () => {
    state.dashboardSource = "all";
    state.fund = [];
    state.multiFund = false;
    state.empSelection = [];
    state.multiEmp = false;
    state.showMidDimension = false;
    state.dimensions = ["large"];
    selectedRows.clear();
    renderEmpMenu();
    render();
  };
  render = function () {
    renderFilters();
    renderDashboardAssetCharts();
    renderDashboardFundInfo();
    renderEmp();
    if (state.activeTab === "empInfoManager") renderEmpInfoManager();
  };
  const tradeSearch = document.getElementById("tradeSearch");
  if (tradeSearch) tradeSearch.oninput = () => { state.tradeSearch = tradeSearch.value; renderDashboardTrades(); };
  const etfSearch = document.getElementById("etfSearch");
  if (etfSearch) etfSearch.oninput = () => { state.etfSearch = etfSearch.value; renderDashboardFundInfo(); };
  renderEmpMenu(); render(); renderEtfManager(); renderEmpInfoManager();
  document.getElementById("empMenu").classList.remove("active");
  globalDbLoadPromise = loadGlobalDbState().then(loaded => {
    if (!loaded) return;
    renderEmpMenu();
    render();
    renderEtfManager();
    renderEmpInfoManager();
    clearEtfDirty("Supabase DB 데이터 불러옴");
    clearEmpInfoDirty("Supabase DB 데이터 불러옴");
    const empStatus = document.getElementById("empStatus");
    if (empStatus) {
      empStatus.textContent = "Supabase DB 데이터 불러옴";
      empStatus.classList.remove("dirty");
    }
  });
})();
