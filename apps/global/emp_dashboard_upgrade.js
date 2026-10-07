(function () {
  const style = document.createElement("style");
  style.textContent = `
    :root{--deep:#00483a;--teal:#006b5b;--mint:#edf5f1;--line:#dfe8e4;--ink:#16251f;--muted:#697872;--red:#e7663f;--bg:#f5f7f4}
    body{background:var(--bg);color:var(--ink);font-family:"Segoe UI","Malgun Gothic",Arial,sans-serif}
    .app{grid-template-columns:176px minmax(0,1fr);grid-template-rows:62px 1fr}
    .top{background:linear-gradient(90deg,#f8fbf9 0%,#fff 44%,#edf7f3 100%);border-bottom:1px solid var(--line);gap:18px;padding:0 18px}
    .brand{font-size:23px;color:var(--deep);border:0;padding:0;white-space:nowrap;letter-spacing:-.3px}
    .tab{background:#fff;color:var(--deep);border:1px solid var(--deep);border-radius:7px;padding:7px 11px}
    .tab:hover,.actionBtn:hover,.chip:hover{background:#e8f6f1}.tab.active{background:var(--deep);color:#fff}
    .side{border-right:1px solid var(--line);padding:7px 6px}.filter{background:#fff;border:1px solid var(--line);border-radius:8px}
    #filters .chips{grid-template-columns:minmax(0,1fr);gap:5px}
    #filters .chip{width:100%;background:#fff;color:var(--ink);border:1px solid transparent;border-radius:7px;padding:6px 7px;text-align:left;font-size:10px;font-weight:700}
    #filters .chip:hover{border-color:#b8dedd;background:#f3fbfa}
    #filters .chip.active{background:#e8f6f1;color:var(--deep);border-color:var(--deep);box-shadow:inset 3px 0 0 var(--deep)}
    .panel{border:1px solid var(--line);border-radius:7px;box-shadow:0 2px 8px rgba(18,55,45,.04);padding:12px}
    .metricCard{border:1px solid var(--line);border-radius:6px;box-shadow:0 1px 0 rgba(0,72,58,.04)}
    table th{background:#eef5f1;color:#40515d;border-bottom:1px solid var(--line)}table td{border-bottom:1px solid var(--line)}
    .actionBtn{border-color:var(--deep);background:#fff;color:var(--deep);border-radius:7px}.actionBtn.primary{background:var(--deep);color:#fff}
    .topRefresh{background:var(--deep);border-color:var(--deep)}
    #master .tablewrap{max-height:none;overflow:visible}#master .masterGrid>.panel{min-height:calc(100vh - 120px)}
    #dashboard .notice,#dashboard .kpis{display:none!important}#dashboard .grid{margin-top:0}
    #emp .panel{border-radius:8px}#emp .empTableWrap{max-height:calc(100vh - 185px)!important}#empTable{font-size:10.5px;table-layout:fixed;white-space:normal}#empTable th{padding:5px 4px;line-height:1.2;text-align:center}#empTable td{padding:4px 4px;line-height:1.2;overflow:hidden;text-overflow:ellipsis}#empTable th:nth-child(n+4),#empTable td:nth-child(n+4){text-align:center!important}#empTable .manualCell{background:#fff!important}.manualInput{width:56px;border:1px solid #b8cbc6;border-radius:3px;padding:2px 3px;text-align:right;background:#fff}.manualInput:focus{outline:2px solid #e0b323;background:#fff8d8}.manualChanged{background:#fff3b0!important}.manualChanged .manualInput{background:#fff8d8!important;border-color:#d09b00!important;font-weight:800}.rowCheck,.etfCheck{width:14px;height:14px;accent-color:#064e43}.empActions{flex-wrap:wrap}.empStatus.dirty{color:#b7791f;font-weight:800}.changeBarCell{padding:3px 4px!important}.changeBar{position:relative;height:15px;background:#e4efec;border-radius:3px;overflow:hidden}.changeBar:before{content:"";position:absolute;left:50%;top:0;bottom:0;width:1px;background:rgba(6,78,67,.28);z-index:2}.changeFill{position:absolute;top:0;bottom:0;left:50%;background:linear-gradient(90deg,#6fa99e,#064e43)}.changeFill.neg{left:auto;right:50%;background:linear-gradient(90deg,#c2413a,#f0a09b)}.changeBarText{position:absolute;inset:0;display:grid;place-items:center;font-weight:900;font-size:9px;color:#173a34;text-shadow:0 1px 2px rgba(255,255,255,.9);z-index:3}
    #empTable .changeFill{background:#e86969}#empTable .changeFill.neg{background:#72a8e8}
    .subtotalRow{background:#dfeeea!important;font-weight:900;color:#064e43}.subtotalRow td{border-top:2px solid #609d91;border-bottom:1px solid #609d91}.totalRow{background:#064e43!important;color:white;font-weight:900}.totalRow td{border-top:2px solid #033b32}
    .picker{position:fixed;inset:0;background:rgba(3,31,27,.46);display:none;place-items:center;z-index:100}.picker.active{display:grid}.pickerBox{width:min(1100px,94vw);max-height:84vh;background:white;border-radius:12px;padding:14px;box-shadow:0 22px 70px rgba(0,0,0,.25)}.pickerHead{display:flex;gap:8px;align-items:center;margin-bottom:10px}.pickerHead h2{margin:0;min-width:170px}.pickerTable{max-height:64vh;overflow:auto}.pickBtn{border:0;background:#064e43;color:white;border-radius:3px;padding:4px 8px;cursor:pointer}.pickBtn.added{background:#8aa9a1;cursor:default}.pickerCheck{width:15px;height:15px;accent-color:#064e43}.pickerBulk{border:1px solid #064e43;background:#064e43;color:#fff;border-radius:4px;padding:6px 10px;font-weight:800;cursor:pointer;white-space:nowrap}.pickerTray{display:flex;gap:5px;flex-wrap:wrap;margin:0 0 8px}.pickerChip{border:1px solid #b6d1ca;background:#e9f2ef;color:#173a34;border-radius:12px;padding:3px 8px;font-size:11px}.pickerChip button{border:0;background:transparent;color:#b42318;font-weight:900;cursor:pointer;margin-left:4px}
    .etfManageTools,.empInfoTools,.fundManageTools{display:flex;gap:8px;align-items:center;margin-bottom:8px}.etfManageTools .search{max-width:420px}.etfInput,.empInfoInput,.fundInput{width:100%;min-width:80px;border:1px solid #b8cbc6;border-radius:3px;padding:4px}.etfInput.wide,.fundInput.wide{min-width:190px}.empPrincipalInput,.fundNumericInput{text-align:right}.etfStatus,.empInfoStatus,.fundStatus{font-size:11px;color:#6c7f7b;font-weight:800;margin-left:auto}.etfStatus.dirty,.empInfoStatus.dirty,.fundStatus.dirty{color:#b7791f}
    #dashboard .empIntegratedPanel .compactChart,#dashboard .fundIntegratedPanel .shareRows{height:300px}.assetPanel.expanded .compactChart,.assetPanel.expanded .shareRows{height:calc(100vh - 145px)!important;min-height:690px}.assetPanel h2{justify-content:flex-start;align-items:center;gap:8px}.assetPanel h2:before{display:none}.assetTitle{display:flex;align-items:baseline;gap:8px;min-width:0;flex:0 1 auto}.assetTitleText{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.assetMeta{font-size:11px;color:#6c7f7b;font-weight:800}.panelToggle{border:1px solid #b6d1ca;background:#e9f2ef;color:#173a34;border-radius:4px;padding:3px 7px;font-size:11px;font-weight:800;cursor:pointer;flex:0 0 auto;margin-left:auto}
    .shareRow{grid-template-columns:minmax(36px,var(--share-label-width,64px)) 46px minmax(120px,1fr)!important;gap:5px!important}.shareText{display:contents}.shareRow .shareLabel{grid-column:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.shareRow .shareValue{grid-column:2;text-align:right}.shareRow .track{grid-column:3}.empMenu>h3{display:none}.empPortfolioFilter{margin:8px 0;background:#fcfffe;border:1.5px solid var(--line);border-radius:5px;padding:6px}.empPortfolioFilter .filterHead{display:flex;align-items:center;gap:4px;margin-bottom:6px}.empPortfolioFilter h3{margin:0;color:var(--ink);font-size:12px;flex:1}.empPortfolioFilter .multiBtn,.empPortfolioFilter .miniAll{border:1px solid #b6d1ca;background:var(--mint);color:var(--ink);border-radius:3px;padding:2px 6px;font-size:10px;line-height:1.2;height:auto;cursor:pointer}.empPortfolioFilter .multiBtn.active{background:var(--deep);color:#fff}.empPortfolioFilter .chips{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:4px}.empPortfolioFilter .chip{border:0;background:var(--teal);color:#fff;border-radius:3px;padding:5px 6px;text-align:left;font-size:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;cursor:pointer}.empPortfolioFilter .chip.active{background:#092f2a;box-shadow:inset 0 0 0 2px #9ad0c1}
    #emp .empSummary{margin-bottom:8px}.topRefresh{border:1.5px solid var(--line);background:var(--deep);color:#fff;font-weight:900;border-radius:5px;padding:9px 14px;cursor:pointer;white-space:nowrap}
    .dashboardMetricStrip{display:grid;grid-template-columns:repeat(9,minmax(0,1fr));gap:7px;margin-bottom:8px}.metricCard{background:#fff;border:1.5px solid var(--line);border-radius:7px;padding:7px 9px;min-width:0}.metricCard span{display:block;min-height:22px;color:#6c7f7b;font-size:10px;font-weight:900;line-height:1.1;overflow-wrap:anywhere}.metricCard b{display:block;margin-top:3px;text-align:right;color:#064e43;font-size:14px}.metricCard b.neg{color:#c2413a}.metricCard b.pos{color:#087f5b}
    .bloombergUpdatedAt{align-self:center;color:var(--muted);font-size:10px;font-weight:800;white-space:nowrap}
    .fundPerfPanel{margin:0 0 8px;padding:9px 11px}.fundPerfPanel h2{margin-bottom:3px}.fundPerfNote{font-size:10px;color:var(--muted);margin-bottom:6px}.fundPerfPanel .tablewrap{max-height:190px}.fundPerfTable{table-layout:fixed;min-width:850px;font-size:10.5px}.fundPerfTable th,.fundPerfTable td{text-align:center;padding:6px 4px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.fundPerfTable th:first-child,.fundPerfTable td:first-child{width:15%}.fundPerfTable th:nth-child(2),.fundPerfTable td:nth-child(2){width:12%}.fundPerfTable th:nth-child(3),.fundPerfTable td:nth-child(3){width:10%}.fundPerfTable th:nth-child(4),.fundPerfTable td:nth-child(4){width:10%}.fundPerfTable th:nth-child(5),.fundPerfTable td:nth-child(5){width:10%}.fundPerfTable th:nth-child(6),.fundPerfTable td:nth-child(6){width:10%}.fundPerfTable th:nth-child(7),.fundPerfTable td:nth-child(7){width:10%}.fundPerfTable th:nth-child(8),.fundPerfTable td:nth-child(8){width:11%}.fundPerfTable th:nth-child(9),.fundPerfTable td:nth-child(9){width:12%}.fundPerfTable .pos{color:#c2413a}.fundPerfTable .neg{color:#2563eb}
    #dashboard .grid.dashboardOverview{display:grid;grid-template-columns:minmax(0,.98fr) minmax(0,.82fr) minmax(0,1.3fr);gap:10px;align-items:stretch;height:calc(100vh - 158px);min-height:590px}
    #dashboard .chosenAssetPanel,#dashboard .tradeLongPanel{height:100%;display:flex;flex-direction:column;min-height:0}
    #dashboard .chosenAssetPanel .shareRows{height:auto!important;flex:1;min-height:0;max-height:none;padding-right:2px}
    #dashboard .chosenAssetPanel .panelToggle{display:none}
    .dashboardBreakdownColumn{display:grid;grid-template-rows:minmax(0,.82fr) minmax(0,1.18fr);gap:10px;min-height:0}.breakdownPanel{display:flex;flex-direction:column;min-height:0;padding:13px 14px}.breakdownPanel h2{margin:0;font-size:13px}.breakdownPanel h2:before{display:none}.breakdownIntro{display:flex;justify-content:space-between;align-items:baseline;gap:8px;margin:3px 0 9px;color:var(--muted);font-size:10px}.breakdownIntro strong{color:var(--deep);font-size:14px;white-space:nowrap}.breakdownList{flex:1;min-height:0;overflow:auto;padding-right:4px}.breakdownRow{padding:6px 0 7px;border-bottom:1px solid #edf1ee}.breakdownRow:last-child{border-bottom:0}.breakdownMain{display:grid;grid-template-columns:minmax(0,1fr) 78px 52px;gap:7px;align-items:center;font-size:11px}.breakdownName{font-weight:750;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.breakdownAmount,.breakdownPercent{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}.breakdownAmount{color:#42564f}.breakdownPercent{font-weight:850;color:var(--deep)}.breakdownTrack{height:5px;margin-top:5px;border-radius:8px;background:#edf3f0;overflow:hidden}.breakdownFill{height:100%;min-width:2px;border-radius:8px;background:var(--bar,#0b7b69)}.breakdownEmpty{padding:20px 6px;color:var(--muted);font-size:11px;text-align:center}
    .allocationHead,.allocationRow{display:grid;grid-template-columns:minmax(0,250px) 78px 60px;gap:7px;align-items:center}.allocationHead{position:sticky;top:0;z-index:2;padding:5px 8px;background:#f3f7f5;color:var(--muted);font-size:10px;font-weight:800}.allocationHead span:nth-child(n+2),.allocationRow span:nth-child(n+2){text-align:right}.allocationHead span:nth-child(2):after{content:" · 억원"}.allocationRow{min-height:32px;padding:6px 8px;border-bottom:1px solid #edf1ee;font-size:11px;font-variant-numeric:tabular-nums;cursor:pointer}.allocationRow:hover{background:#eaf4ef}.allocationRow:focus-visible{outline:2px solid var(--teal);outline-offset:-2px}.allocationNode>summary{list-style:none}.allocationNode>summary::-webkit-details-marker{display:none}.allocationNode.level0>summary{background:#eaf4ef;color:var(--deep);font-weight:900}.allocationNode.level1>summary{background:#f7faf8;font-weight:800}.allocationNode.level1>summary .allocationLabel,.allocationLeaf.level1 .allocationLabel{padding-left:12px}.allocationNode.level2>summary .allocationLabel,.allocationLeaf.level2 .allocationLabel{padding-left:24px}.allocationLeaf.level3 .allocationLabel{padding-left:36px}.allocationLeaf{color:#45564e}.allocationLabel{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.allocationChevron{display:inline-block;width:14px;color:#78958a;font-weight:900}.allocationNode[open]>summary .allocationChevron{transform:rotate(90deg)}.allocationValue,.allocationShare{white-space:nowrap}.allocationValue{font-weight:750}.allocationShare{font-weight:850;color:var(--deep)}.allocationFoot{margin:8px 4px 0;color:var(--muted);font-size:10px}
    .allocationNode.level1>summary{background:#f1f8f4;color:var(--deep);font-weight:800}.allocationNode.level1>summary:hover{background:#e6f2ec}.allocationLeaf.level2 .allocationLabel{padding-left:36px}.allocationLeaf.level2 .allocationLabel::before{content:"-";display:inline-block;width:12px;color:#78958a;font-weight:900}
    #dashboard .tradeLongPanel .tablewrap{height:auto!important;max-height:none!important;flex:1;min-height:0;overflow-x:hidden}#dashboard .tradeLongPanel table{font-size:10px;table-layout:fixed;width:100%}#tradeTable th,#tradeTable td{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;padding-left:3px;padding-right:3px;text-align:center!important}#tradeTable th:nth-child(1),#tradeTable td:nth-child(1){width:11%}#tradeTable th:nth-child(2),#tradeTable td:nth-child(2){width:11%}#tradeTable th:nth-child(3),#tradeTable td:nth-child(3){width:7%}#tradeTable th:nth-child(4),#tradeTable td:nth-child(4){width:25%}#tradeTable th:nth-child(5),#tradeTable td:nth-child(5){width:8%}#tradeTable th:nth-child(6),#tradeTable td:nth-child(6){width:10%}#tradeTable th:nth-child(7),#tradeTable td:nth-child(7){width:11%}#tradeTable th:nth-child(8),#tradeTable td:nth-child(8){width:9%}#tradeTable th:nth-child(9),#tradeTable td:nth-child(9){width:8%}#tradeTable span[title]{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;text-align:center}.tradeSide{display:inline-block;min-width:32px;padding:3px 5px;border-radius:4px;color:#fff;font-size:10px;font-weight:900;line-height:1.2}.tradeSide.buy{background:#c2413a}.tradeSide.sell{background:#2563eb}.tradeEmpty{height:100%;min-height:360px;display:grid;place-items:center;color:#6c7f7b;font-weight:900;border:1px dashed #b8d2cc;border-radius:10px;background:#f8fcfb}.sortHeader{width:100%;border:0;background:transparent;color:inherit;font:inherit;font-weight:900;cursor:pointer;text-align:center;padding:0}.sortHeader:hover{text-decoration:underline}th[aria-sort="ascending"] .sortHeader::after{content:" ▲"}th[aria-sort="descending"] .sortHeader::after{content:" ▼"}
    @media(max-width:1250px){#dashboard .grid.dashboardOverview{grid-template-columns:1fr;height:auto}#dashboard .chosenAssetPanel,#dashboard .tradeLongPanel{min-height:520px}}
    #dashboard .grid.securitiesMain{grid-template-columns:minmax(0,1fr) minmax(0,1fr);height:calc(100vh - 240px);min-height:360px;align-items:stretch;gap:10px}
    #dashboard .securitiesMain>.panel{display:flex;flex-direction:column;height:100%;min-height:0}
    #dashboard .securitiesMain .tablewrap{flex:1;min-height:0;max-height:none;height:auto;overflow:auto}
    #dashboard .securitiesMain table{table-layout:fixed;width:100%;min-width:0;font-size:10px}
    #dashboard .securitiesMain th,#dashboard .securitiesMain td{padding:5px 4px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;text-align:center!important}
    #dashboard .securitiesMain th{white-space:normal;line-height:1.25;text-overflow:clip;font-size:9px}
    #dashboard .sectorToolbar .search{flex:1;min-width:0;width:auto}.sectorChoice{display:flex;align-items:center;gap:4px;margin-left:auto;white-space:nowrap;color:var(--muted);font-size:10px;font-weight:800}.sectorChoice select{max-width:125px;border:1px solid var(--line);border-radius:5px;background:#fff;color:var(--ink);padding:5px 3px;font-size:10px;cursor:pointer}
    #holdingTable th:nth-child(1){width:7%}#holdingTable th:nth-child(2){width:25%}#holdingTable th:nth-child(3){width:9%}#holdingTable th:nth-child(4){width:16%}#holdingTable th:nth-child(5){width:10%}#holdingTable th:nth-child(6){width:10%}#holdingTable th:nth-child(7){width:10%}#holdingTable th:nth-child(8){width:13%}#holdingTable span[title]{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;text-align:center}
    #holdingTable td:nth-child(2),#tradeTable td:nth-child(4){text-align:left!important}#holdingTable td:nth-child(2) span[title],#tradeTable td:nth-child(4) span[title]{text-align:left!important}
    .fundRateBar{position:relative;height:18px;width:100%;min-width:58px;max-width:94px;margin:auto;background:#f1f5f9;border-radius:4px;overflow:hidden}.fundRateBar span{position:absolute;top:0;bottom:0;opacity:.72}.fundRateBar .barZero{left:50%;width:1px;background:#667085;opacity:.8}.fundRateBar .barPos{background:#f59e9e}.fundRateBar .barNeg{background:#93c5fd}.fundRateBar em{position:relative;z-index:2;display:block;text-align:center;font-style:normal;font-weight:800;color:#172033;line-height:18px;font-size:10px}
    #emp .empAllocationView[hidden],#emp .empHoldingsContent[hidden]{display:none!important}
    #emp .empAllocationView{margin-top:8px}#emp .empAllocationView .fundAllocationGrid{height:calc(100vh - 245px);min-height:560px}#emp .empAllocationView .chosenAssetPanel{display:flex;flex-direction:column;min-height:0}#emp .empAllocationView .shareRows{height:auto!important;flex:1;min-height:0;max-height:none;overflow:auto}#emp .empAllocationView .panelToggle{display:none}#emp .empAllocationView .breakdownRow[role="button"]{cursor:pointer}#emp .empAllocationView .breakdownRow[role="button"]:hover,#emp .empAllocationView .breakdownRow[role="button"]:focus-visible{background:#eaf4ef;outline:0}
    .fundAllocationGrid{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:10px;padding:0;height:calc(100vh - 250px);min-height:560px}.fundAllocationGrid .chosenAssetPanel{min-height:0!important}.fundAllocation .breakdownRow[role="button"]{cursor:pointer}.fundAllocation .breakdownRow[role="button"]:hover,.fundAllocation .breakdownRow[role="button"]:focus-visible{background:#eaf4ef;outline:0}
    @media(max-width:1100px){#dashboard .grid.securitiesMain{grid-template-columns:1fr;height:auto}#dashboard .securitiesMain>.panel{height:460px}.fundAllocationGrid{grid-template-columns:1fr;height:auto}.fundAllocationGrid .chosenAssetPanel{height:460px!important}.dashboardBreakdownColumn{grid-template-columns:1fr 1fr;grid-template-rows:330px}.breakdownPanel{height:330px}}
    @media(max-width:650px){.dashboardBreakdownColumn{grid-template-columns:1fr;grid-template-rows:300px 300px}.breakdownPanel{height:300px}}
    @media(max-width:1100px){.app{grid-template-columns:1fr;grid-template-rows:auto auto auto}.side{border-right:0;border-bottom:1px solid var(--line)}}
    .tabs{flex:1;min-width:0;align-items:center}.navGroup{display:flex;align-items:center;gap:7px}.databaseTabs{margin-left:auto;padding-left:18px;border-left:1px solid var(--line)}
    .securitiesSubtabs{display:flex;gap:5px;margin:0 0 8px;border-bottom:1px solid var(--line);padding-bottom:6px}.securitiesSubtab{border:1px solid var(--line);border-radius:6px;background:#fff;color:var(--deep);padding:7px 14px;font-size:12px;font-weight:900;cursor:pointer}.securitiesSubtab.active{background:var(--deep);border-color:var(--deep);color:#fff}
    #emp .empViewTabs{display:flex;gap:5px;margin-left:4px}#emp .empViewTabs .securitiesSubtab{padding:6px 11px;font-size:11px}
    #dashboard .fundSection[hidden]{display:none!important}#dashboard .grid.securitiesMain.fundHoldingsView{grid-template-columns:minmax(0,2fr) minmax(0,3fr)}#dashboard .grid.securitiesMain.fundTradesView{display:block}#dashboard .fundTradesView>.panel{width:100%}
    #dashboard .fundHoldingsView .fundPerfPanel{margin:0;overflow:hidden}#dashboard .fundHoldingsView .fundPerfPanel .tablewrap{max-height:none}#dashboard .fundHoldingsView .fundPerfTable{min-width:850px}
    @media(max-width:1100px){#dashboard .grid.securitiesMain.fundHoldingsView{grid-template-columns:1fr}#dashboard .fundHoldingsView>.panel{height:460px}}
    @media(max-width:760px){.top{flex-wrap:wrap;height:auto;padding:10px}.tabs{flex-basis:100%;flex-wrap:wrap}.databaseTabs{margin-left:0;padding-left:0;border-left:0}.navGroup{flex-wrap:wrap}}
    table tbody tr:nth-child(even):not(.subtotalRow):not(.totalRow):not(.selectedFundRow){background:#fff}
    #fundPerfTable tbody tr.selectedFundRow td{background:#e8f5ed}
    #holdingTable th:nth-child(1){width:13%}#holdingTable th:nth-child(2){width:10%}#holdingTable th:nth-child(3){width:24%}#holdingTable th:nth-child(4){width:12%}#holdingTable th:nth-child(5){width:10%}#holdingTable th:nth-child(6){width:10%}#holdingTable th:nth-child(7){width:10%}#holdingTable th:nth-child(8){width:11%}
    #holdingTable td:nth-child(2),#holdingTable td:nth-child(2) span[title]{text-align:center!important}#holdingTable td:nth-child(3),#holdingTable td:nth-child(3) span[title]{text-align:left!important}
    #dashboard .fundHoldingsView .fundPerfTable{min-width:690px}
    #fundPerfTable th:nth-child(1),#fundPerfTable td:nth-child(1){width:24%}#fundPerfTable th:nth-child(2),#fundPerfTable td:nth-child(2){width:12%}#fundPerfTable th:nth-child(3),#fundPerfTable td:nth-child(3){width:11%}#fundPerfTable th:nth-child(4),#fundPerfTable td:nth-child(4){width:10%}#fundPerfTable th:nth-child(5),#fundPerfTable td:nth-child(5){width:13%}#fundPerfTable th:nth-child(6),#fundPerfTable td:nth-child(6){width:13%}#fundPerfTable th:nth-child(7),#fundPerfTable td:nth-child(7){width:17%}#fundPerfTable th:nth-child(5),#fundPerfTable th:nth-child(6){white-space:normal}
    #dashboard .grid.securitiesMain.fundHoldingsView{grid-template-columns:minmax(0,2.3fr) minmax(0,2.7fr)}
    #dashboard .fundHoldingsView .fundPerfPanel .tablewrap{overflow-x:hidden}
    #dashboard .fundHoldingsView .fundPerfTable{width:100%;min-width:0;font-size:11.3px}
    #dashboard .fundHoldingsView .fundPerfTable th,#dashboard .fundHoldingsView .fundPerfTable td{padding:6px 2px}
    #filters .fundTypeGroup{margin-top:8px;padding-top:7px;border-top:1px solid var(--line)}#filters .filterHead+.fundTypeGroup{margin-top:2px;border-top:0;padding-top:0}#filters .fundTypeTitle{padding:0 7px 4px;color:var(--teal);font-size:10px;font-weight:900}
    #fundPerfTable .fundSelect{display:block;width:100%;border:0;background:transparent;color:inherit;font:inherit;text-align:center;cursor:pointer;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}#fundPerfTable .fundSelect:hover{text-decoration:underline;color:var(--teal)}#fundPerfTable .subtotalRow td,#fundPerfTable .totalRow td{text-align:center}#fundPerfTable .fundRateBar{min-width:0;max-width:none}#fundPerfTable .totalRow .pos,#fundPerfTable .totalRow .neg{color:#fff;font-weight:900}
    .panel h2 .tableUnit{margin-left:auto;color:var(--muted);font-size:10px;font-weight:800;white-space:nowrap}
    #dashboard .securitiesMain table{font-size:11.3px;min-width:0}#dashboard .securitiesMain th{font-size:10.5px}#dashboard .securitiesMain th,#dashboard .securitiesMain td{padding-left:2px;padding-right:2px}#dashboard .securitiesMain .tablewrap{overflow-x:hidden}
    #holdingTable th:nth-child(1){width:7%}#holdingTable th:nth-child(2){width:10%}#holdingTable th:nth-child(3){width:27%}#holdingTable th:nth-child(4){width:16%}#holdingTable th:nth-child(5){width:11%}#holdingTable th:nth-child(6){width:11%}#holdingTable th:nth-child(7){width:8%}#holdingTable th:nth-child(8){width:10%}
    #holdingTable td:nth-child(3) span[title]{cursor:help}#holdingTable .fundRateBar{min-width:0;max-width:none}
    #holdingTable thead th{z-index:5;background:#f3f7f5;background-clip:padding-box}
    .fundHoldingPanel .holdingPanelHeader{display:flex;align-items:center;gap:8px;min-width:0;margin-bottom:7px}
    .fundHoldingPanel .holdingPanelHeader h2{margin:0;min-width:0;white-space:nowrap}
    .fundHoldingPanel .holdingPanelHeader .toolbar{display:flex;align-items:center;justify-content:flex-end;gap:6px;min-width:0;margin:0 0 0 auto;flex:1}
    #dashboard .fundHoldingPanel .holdingPanelHeader .search{width:min(270px,100%);flex:0 1 270px;min-width:90px}
    .fundHoldingCount{border:0;background:transparent;color:var(--teal);font:inherit;font-weight:800;cursor:pointer;text-decoration:underline;text-underline-offset:2px;white-space:nowrap}
    .fundHoldingCount:hover,.fundHoldingCount:focus-visible{color:var(--deep);background:#e8f5ed;outline:2px solid transparent;border-radius:3px}
    .fundHoldingModal{position:fixed;inset:0;z-index:140;display:none;place-items:center;background:rgba(3,31,27,.52);padding:18px}
    .fundHoldingModal.active{display:grid}.fundHoldingModalBox{width:min(1040px,96vw);max-height:88vh;overflow:auto;background:#fff;border-radius:10px;box-shadow:0 20px 70px rgba(0,0,0,.25);padding:16px}
    .fundHoldingModalHead{display:flex;align-items:center;gap:12px;margin-bottom:6px}.fundHoldingModalHead h2{margin:0;flex:1;color:var(--deep);font-size:17px}
    .fundHoldingModalClose{border:1px solid var(--line);border-radius:5px;background:#fff;color:var(--ink);font-size:22px;line-height:1;cursor:pointer;padding:3px 8px}
    .fundHoldingModalNote{font-size:11px;color:var(--muted);margin:0 0 10px}.fundHoldingModalTableWrap{overflow-x:auto}
    .fundHoldingModalTable{width:100%;min-width:750px;border-collapse:collapse;font-size:11px}.fundHoldingModalTable th,.fundHoldingModalTable td{padding:8px 5px;text-align:center;border-bottom:1px solid var(--line);white-space:nowrap}
    .fundHoldingModalTable th:first-child,.fundHoldingModalTable td:first-child{text-align:left}.fundHoldingModalTable .totalRow td,.fundHoldingModalTable .totalRow .pos,.fundHoldingModalTable .totalRow .neg{color:#fff}
    @media(max-width:1180px){#dashboard .grid.securitiesMain.fundHoldingsView{grid-template-columns:minmax(0,1fr);height:auto}#dashboard .fundHoldingsView>.panel{height:460px}}
  `;
  document.head.appendChild(style);
  document.title = "수익증권 대시보드";
  const brand = document.querySelector(".brand");
  if (brand) brand.textContent = "수익증권 대시보드";

  const tabs = document.querySelector(".tabs");
  const empTab = tabs.querySelector('[data-tab="emp"]');
  if (empTab) empTab.textContent = "EMP";
  const securitiesTab = tabs.querySelector('[data-tab="dashboard"]');
  securitiesTab.textContent = "수익증권";
  tabs.insertBefore(empTab, securitiesTab);
  const masterTab = tabs.querySelector('[data-tab="master"]');
  masterTab.textContent = "펀드DB";
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
  const primaryTabs = document.createElement("div");
  primaryTabs.className = "navGroup primaryTabs";
  primaryTabs.append(empTab, securitiesTab);
  const databaseTabs = document.createElement("div");
  databaseTabs.className = "navGroup databaseTabs";
  databaseTabs.append(etfTab, masterTab, empInfoTab);
  tabs.append(primaryTabs, databaseTabs);

  const etfPane = document.createElement("section");
  etfPane.className = "pane";
  etfPane.id = "etfManager";
  etfPane.innerHTML = `<div class="panel"><div class="etfManageTools"><input class="search" id="etfManagerSearch" placeholder="티커·종목명·분류 검색"><button class="actionBtn" id="addEtfMaster">ETF 추가</button><button class="actionBtn" id="deleteSelectedEtfs">삭제</button><button class="actionBtn primary" id="saveEtfChanges">변경저장</button><span class="etfStatus" id="etfStatus"></span></div><h2>ETF DB</h2><div class="tablewrap" style="max-height:calc(100vh - 190px)"><table id="etfManagerTable"></table></div></div>`;
  document.getElementById("master").after(etfPane);
  const empInfoPane = document.createElement("section");
  empInfoPane.className = "pane";
  empInfoPane.id = "empInfoManager";
  empInfoPane.innerHTML = `<div class="panel"><div class="empInfoTools"><button class="actionBtn" id="addEmpInfo">EMP 추가</button><button class="actionBtn" id="deleteSelectedEmpInfo">삭제</button><button class="actionBtn primary" id="saveEmpInfoChanges">변경저장</button><span class="empInfoStatus" id="empInfoStatus"></span></div><h2>EMP정보</h2><div class="tablewrap" style="max-height:calc(100vh - 190px)"><table id="empInfoTable"></table></div></div>`;
  document.getElementById("master").after(empInfoPane);
  const oldEtfPanel = document.getElementById("etfTable")?.closest(".panel");
  if (oldEtfPanel) oldEtfPanel.style.display = "none";
  const fundPanel = document.getElementById("fundTable")?.closest(".panel");
  if (fundPanel) fundPanel.querySelector("h2").textContent = "펀드DB";
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
  empPanel.classList.add("assetPanel", "chosenAssetPanel", "empIntegratedPanel");
  document.getElementById("empAssetChart").className = "shareRows";
  document.querySelector("#emp .empCharts")?.remove();
  function panelTitle(panel, text, meta, toggleId) {
    const heading = panel.querySelector("h2");
    heading.innerHTML = `<span class="assetTitle"><span class="assetTitleText">${esc(text)}</span><span class="assetMeta">${esc(meta)}</span></span><button class="panelToggle" id="${toggleId}" type="button">펼치기</button>`;
  }
  function bindPanelToggle(panel, buttonId) {
    const button = document.getElementById(buttonId);
    button.onclick = () => {
      const shouldExpand = !panel.classList.contains("expanded");
      panel.classList.toggle("expanded", shouldExpand);
      button.textContent = shouldExpand ? "접기" : "펼치기";
    };
  }
  panelTitle(empPanel, "EMP 자산 구성", "", "toggleEmpAssetPanel");
  panelTitle(currentFundPanel, "수익증권 자산 비중", "", "toggleFundAssetPanel");
  bindPanelToggle(currentFundPanel, "toggleFundAssetPanel");
  const holdingPanel = document.getElementById("holdingTable")?.closest(".panel");
  const tradePanel = document.getElementById("tradeTable")?.closest(".panel");
  const sectorLevels = { holding: "small" };
  function installSectorChoice(panel, key, label, renderTable) {
    const toolbar = panel?.querySelector(".toolbar");
    if (!toolbar) return;
    toolbar.classList.add("sectorToolbar");
    const choice = document.createElement("label");
    choice.className = "sectorChoice";
    choice.innerHTML = `<span>섹터</span><select aria-label="${label} 섹터 분류"><option value="large">대분류(GICS1)</option><option value="small" selected>소분류(GICS2)</option></select>`;
    toolbar.append(choice);
    choice.querySelector("select").onchange = event => {
      sectorLevels[key] = event.target.value;
      renderTable();
    };
  }
  installSectorChoice(holdingPanel, "holding", "보유현황", renderFundHoldings);
  holdingPanel?.classList.add("fundHoldingPanel");
  if (holdingPanel) {
    const heading = holdingPanel.querySelector("h2");
    const toolbar = holdingPanel.querySelector(".toolbar");
    const header = document.createElement("div");
    header.className = "holdingPanelHeader";
    heading.before(header);
    header.append(heading, toolbar);
  }
  const empHoldingsPanel = document.querySelector("#emp .empActions").closest(".panel");
  const empHoldingsContent = document.createElement("div");
  empHoldingsContent.className = "empHoldingsContent";
  empHoldingsContent.append(document.getElementById("empTitle"), document.querySelector("#emp .empTableWrap"));
  empHoldingsPanel.append(empHoldingsContent);
  const empBreakdownColumn = document.createElement("div");
  empBreakdownColumn.className = "dashboardBreakdownColumn";
  empBreakdownColumn.innerHTML = `<div class="panel breakdownPanel"><h2>자산군 구성</h2><div class="breakdownIntro"><span>선택 EMP · 보유 익스포저</span><strong id="empAssetMixTotal"></strong></div><div class="breakdownList" id="empAssetMixList"></div></div><div class="panel breakdownPanel"><h2>주식 투자지역</h2><div class="breakdownIntro"><span>ETF 투자국가 · 개별주식 ISIN 등록국 기준</span><strong id="empRegionMixTotal"></strong></div><div class="breakdownList" id="empRegionMixList"></div></div>`;
  const empAllocationView = document.createElement("div");
  empAllocationView.className = "empAllocationView";
  empAllocationView.hidden = true;
  const empAllocationGrid = document.createElement("div");
  empAllocationGrid.className = "fundAllocationGrid";
  empAllocationGrid.append(empPanel, empBreakdownColumn);
  empAllocationView.append(empAllocationGrid);
  empHoldingsPanel.append(empAllocationView);
  currentFundPanel.classList.add("chosenAssetPanel");
  tradePanel?.classList.add("tradeLongPanel");
  const breakdownColumn = document.createElement("div");
  breakdownColumn.className = "dashboardBreakdownColumn";
  breakdownColumn.innerHTML = `<div class="panel breakdownPanel"><h2>자산군 구성</h2><div class="breakdownIntro"><span>선택 펀드 · 보유 익스포저</span><strong id="assetMixTotal"></strong></div><div class="breakdownList" id="assetMixList"></div></div><div class="panel breakdownPanel"><h2>주식 투자지역</h2><div class="breakdownIntro"><span>ETF 투자국가 · 개별주식 ISIN 등록국 기준</span><strong id="regionMixTotal"></strong></div><div class="breakdownList" id="regionMixList"></div></div>`;
  dashboardGrid.className = "securitiesViewHost";
  dashboardGrid.innerHTML = "";
  const securitiesSubtabs = document.createElement("div");
  securitiesSubtabs.className = "securitiesSubtabs";
  securitiesSubtabs.setAttribute("role", "tablist");
  securitiesSubtabs.setAttribute("aria-label", "수익증권 현황");
  securitiesSubtabs.innerHTML = `<button type="button" class="securitiesSubtab active" role="tab" aria-selected="true" data-fund-view="holdings">보유현황</button><button type="button" class="securitiesSubtab" role="tab" aria-selected="false" data-fund-view="trades">매매현황</button><button type="button" class="securitiesSubtab" role="tab" aria-selected="false" data-fund-view="allocation">자산구성</button>`;
  const holdingView = document.createElement("div");
  holdingView.className = "grid securitiesMain fundHoldingsView fundSection";
  const tradeView = document.createElement("div");
  tradeView.className = "grid securitiesMain fundTradesView fundSection";
  tradeView.hidden = true;
  if (holdingPanel) holdingView.append(holdingPanel);
  if (tradePanel) tradeView.append(tradePanel);
  const fundAllocation = document.createElement("div");
  fundAllocation.className = "fundAllocation fundSection";
  fundAllocation.hidden = true;
  const fundAllocationGrid = document.createElement("div");
  fundAllocationGrid.className = "fundAllocationGrid";
  fundAllocationGrid.append(currentFundPanel, breakdownColumn);
  fundAllocation.append(fundAllocationGrid);
  dashboardGrid.append(securitiesSubtabs, holdingView, tradeView, fundAllocation);
  securitiesSubtabs.querySelectorAll("[data-fund-view]").forEach(button => button.onclick = () => {
    const selected = button.dataset.fundView;
    holdingView.hidden = selected !== "holdings";
    tradeView.hidden = selected !== "trades";
    fundAllocation.hidden = selected !== "allocation";
    securitiesSubtabs.querySelectorAll("[data-fund-view]").forEach(tab => {
      const active = tab === button;
      tab.classList.toggle("active", active);
      tab.setAttribute("aria-selected", String(active));
    });
  });

  const picker = document.createElement("div");
  picker.className = "picker";
  picker.id = "etfPicker";
  picker.innerHTML = `<div class="pickerBox"><div class="pickerHead"><h2 id="pickerTitle"></h2><input class="search" id="pickerSearch" placeholder="티커·종목명·분류 검색"><button class="pickerBulk" id="pickSelectedEtfs">선택 적용</button><button class="actionBtn" id="closePicker">닫기</button></div><div class="pickerTray" id="pickerTray"></div><div class="pickerTable"><table id="pickerTable"></table></div></div>`;
  document.body.appendChild(picker);
  const holdingModal = document.createElement("div");
  holdingModal.className = "fundHoldingModal";
  holdingModal.id = "fundHoldingModal";
  holdingModal.setAttribute("role", "dialog");
  holdingModal.setAttribute("aria-modal", "true");
  holdingModal.setAttribute("aria-labelledby", "fundHoldingModalTitle");
  holdingModal.innerHTML = `<div class="fundHoldingModalBox"><div class="fundHoldingModalHead"><h2 id="fundHoldingModalTitle"></h2><button type="button" class="fundHoldingModalClose" aria-label="상세 닫기">×</button></div><p class="fundHoldingModalNote">매수 평단가와 누적 평가손익은 보유 원천데이터에 취득원가가 없어 표시하지 않습니다. PL은 당일 추정치입니다.</p><div class="fundHoldingModalTableWrap"><table class="fundHoldingModalTable"></table></div></div>`;
  document.body.appendChild(holdingModal);
  const allocationModal = document.createElement("div");
  allocationModal.className = "fundHoldingModal";
  allocationModal.setAttribute("role", "dialog");
  allocationModal.setAttribute("aria-modal", "true");
  allocationModal.setAttribute("aria-labelledby", "allocationModalTitle");
  allocationModal.innerHTML = `<div class="fundHoldingModalBox"><div class="fundHoldingModalHead"><h2 id="allocationModalTitle"></h2><button type="button" class="fundHoldingModalClose" aria-label="상세 닫기">×</button></div><p class="fundHoldingModalNote"></p><div class="fundHoldingModalTableWrap"><table class="fundHoldingModalTable"></table></div></div>`;
  document.body.appendChild(allocationModal);

  const isLocalDashboard = location.protocol === "file:" || ["localhost", "127.0.0.1", "[::1]"].includes(location.hostname);
  const webBridge = isLocalDashboard ? null : window.GlobalWebBridge;
  const embeddedEtfs = DATA.etfs;
  const savedEtfs = webBridge ? null : JSON.parse(localStorage.getItem("globalDashboard.etfs") || "null");
  if (Array.isArray(savedEtfs)) {
    const savedEtfSchema = localStorage.getItem("globalDashboard.etfsSchema");
    if (savedEtfSchema !== "4" && savedEtfSchema !== "5") {
      const baseline = new Map(embeddedEtfs.map(etf => [String(etf.isin || etf.ticker).toUpperCase(), etf]));
      DATA.etfs = savedEtfSchema === "3" ? savedEtfs.map(etf => ({ ...etf })) : savedEtfs.map(etf => {
        const source = baseline.get(String(etf.isin || etf.ticker).toUpperCase());
        const normalized = EtfDbSchema.normalize(etf, source);
        normalized.benchmark = String(etf.benchmark || source?.benchmark || FundAllocationView.benchmarkOf(normalized));
        return normalized;
      });
      DATA.etfs = EtfDbSchema.mergeBloombergAdditions(DATA.etfs, embeddedEtfs);
    } else DATA.etfs = savedEtfs;
    if (savedEtfSchema !== "5") {
      DATA.etfs = DATA.etfs.map(EtfDbSchema.applySuggestedGics);
      localStorage.setItem("globalDashboard.etfs", JSON.stringify(DATA.etfs));
      localStorage.setItem("globalDashboard.etfsSchema", "5");
    }
  } else DATA.etfs = embeddedEtfs.map(etf => {
    const normalized = EtfDbSchema.normalize(etf);
    normalized.benchmark ||= FundAllocationView.benchmarkOf(normalized);
    return normalized;
  });
  const restoredFunds = webBridge ? { funds: DATA.funds, imported: false } : FundMasterStorage.restore(DATA.funds, localStorage, location, history);
  DATA.funds = restoredFunds.funds;
  const backupFundsButton = document.createElement("button");
  backupFundsButton.className = "actionBtn";
  backupFundsButton.textContent = "펀드 백업";
  backupFundsButton.onclick = () => FundMasterStorage.download(DATA.funds);
  document.getElementById("fundManageTools").append(backupFundsButton);
  if (location.protocol === "file:") {
    const transferFundsButton = document.createElement("button");
    transferFundsButton.className = "actionBtn primary";
    transferFundsButton.textContent = "로컬웹으로 이전";
    transferFundsButton.onclick = () => FundMasterStorage.transfer(DATA.funds);
    document.getElementById("fundManageTools").append(transferFundsButton);
  }
  const savedSnapshot = webBridge ? null : FundSnapshotStorage.restore(localStorage);
  if (savedSnapshot) {
    DATA.asOf = savedSnapshot.asOf || DATA.asOf;
    DATA.sources = savedSnapshot.sources || DATA.sources;
  }
  const rawFundHoldings = (savedSnapshot?.holdings || DATA.holdings).map(row => ({ ...row }));
  const rawFundTrades = (savedSnapshot?.trades || DATA.trades).map(row => ({ ...row }));
  let fundCoverage = savedSnapshot?.coverage || [];
  let snapshotSavedAt = savedSnapshot?.savedAt || "";
  let snapshotSaveError = "";
  let rawRequestVersion = 0;
  const fundDataTools = document.createElement("div");
  fundDataTools.className = "fundDataTools";
  fundDataTools.style.cssText = "display:flex;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:8px;font-size:11px;overflow-wrap:anywhere";
  fundDataTools.innerHTML = `<span id="fundRawStatus" role="status"></span><span id="fundMarketStatus" role="status"></span>`;
  metricStrip.before(fundDataTools);
  const performancePanel = document.createElement("div");
  performancePanel.className = "panel fundPerfPanel";
  performancePanel.innerHTML = `<h2>펀드별 PL<span class="tableUnit">단위:억원</span></h2><div class="tablewrap"><table class="fundPerfTable" id="fundPerfTable"></table></div>`;
  holdingView.prepend(performancePanel);
  const apiUrl = path => location.protocol === "file:" ? `http://127.0.0.1:8766${path}` : `${location.origin}${path}`;
  const fundMarketIdentifier = row => FundMarketIdentifiers.identifier(row, DATA.etfs);
  function applyFundMaster() {
    const byCode = new Map(DATA.funds.filter(fund => fund.assocCode).map(fund => [String(fund.assocCode).trim(), fund]));
    const updateRows = rows => rows.filter(row => byCode.has(row.fundCode)).map(row => FundMarketIdentifiers.applyMetadata({ ...row, fund: byCode.get(row.fundCode).fund }, {}, DATA.etfs));
    DATA.holdings = updateRows(rawFundHoldings);
    DATA.trades = updateRows(rawFundTrades);
  }
  applyFundMaster();
  const applyMarketData = market => {
    if (!market) return;
    if (market.fx) state.fx = Number(market.fx || 1);
    const map = market.securities || {};
    [...DATA.holdings, ...rawFundHoldings, ...DATA.trades, ...rawFundTrades].forEach(row => {
      const updated = FundMarketIdentifiers.referenceFor(row, map, DATA.etfs);
      FundMarketIdentifiers.applyMetadata(row, updated || {}, DATA.etfs);
      if (!updated) return;
      if (updated.change != null) row.change = Number(updated.change);
      if (updated.price != null) row.marketPrice = Number(updated.price);
      if (updated.prevClose != null) row.prevClose = Number(updated.prevClose);
    });
  };
  let savedMarket = webBridge ? null : JSON.parse(localStorage.getItem("globalDashboard.market") || "null");
  function saveFundSnapshot() {
    if (webBridge) return; // Hosted raw holdings/trades come from the daily Supabase build.
    const result = FundSnapshotStorage.save(localStorage, {
      holdings: rawFundHoldings, trades: rawFundTrades, coverage: fundCoverage,
      asOf: DATA.asOf, sources: DATA.sources
    });
    snapshotSaveError = result.ok ? "" : ` · 직전 데이터 저장 실패: ${result.error}`;
    if (result.ok) snapshotSavedAt = result.savedAt;
  }
  function showRawCoverage() {
    const status = document.getElementById("fundRawStatus");
    const selected = f => !state.fund.length || state.fund.includes(f.fund);
    const missingCode = DATA.funds.filter(f => selected(f) && !String(f.assocCode || "").trim()).map(f => f.fund || "이름 없는 펀드");
    const absent = fundCoverage.filter(f => selected(f) && !f.holdings).map(f => f.fund);
    const noTrades = fundCoverage.filter(f => selected(f) && !f.trades).map(f => f.fund);
    const details = [];
    if (absent.length) details.push(`최신 보유 없음: ${absent.join(", ")}`);
    if (noTrades.length) details.push(`매매 원천 없음: ${noTrades.join(", ")}`);
    if (missingCode.length) details.push(`펀드코드 미입력: ${missingCode.join(", ")}`);
    if (rawFundTrades.some(row => !Object.prototype.hasOwnProperty.call(row, "tradeNav"))) details.push("매매일 NAV 반영 전 저장 데이터: 서버 재시작 후 블룸버그 업데이트 필요");
    const missingForward = selectedFundFxRows().filter(row => FundMarketIdentifiers.isForward(row) && FundMarketIdentifiers.hedgeExposure(row) == null);
    if (missingForward.length) details.push(`선도 invest_amt ${missingForward.length}건 누락: 업데이트 필요`);
    status.textContent = `직전 저장 데이터 · ${DATA.asOf} · 보유 ${fundBase(DATA.holdings).length.toLocaleString()}건 / 매매 ${fundBase(DATA.trades).length.toLocaleString()}건${details.length ? " · " + details.join(" · ") : ""}${snapshotSaveError}`;
    status.title = status.textContent + (snapshotSavedAt ? ` · 저장 시각: ${new Date(snapshotSavedAt).toLocaleString("ko-KR")}` : "");
    document.getElementById("asOf").textContent = DATA.asOf;
    document.getElementById("generated").textContent = `보유현황 기준일 ${DATA.asOf}`;
    document.getElementById("meta").textContent = `Supabase API · 보유 ${DATA.asOf} / ${DATA.holdings.length.toLocaleString()}건 · 매매 ${DATA.trades.length.toLocaleString()}건 · ETF ${DATA.etfs.length.toLocaleString()}건`;
  }
  async function refreshFundRaw() {
    const version = ++rawRequestVersion;
    const status = document.getElementById("fundRawStatus");
    const button = document.getElementById("refreshMarket");
    const funds = DATA.funds.map(f => ({ fund: f.fund, assocCode: f.assocCode, type: f.type }));
    const signature = JSON.stringify(funds);
    status.textContent = "전체 유형 보유·매매 조회 중…";
    button.disabled = true;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 120000);
    try {
      const res = await fetch(apiUrl("/api/fund-raw"), {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ funds, etfs: DATA.etfs }), signal: controller.signal
      });
      const payload = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(res.status === 404 ? "서버 창을 닫고 실행파일을 다시 실행하세요 (조회 API 업데이트 필요)" : payload.error || "원천데이터 조회 실패");
      if (version !== rawRequestVersion) return false;
      if (signature !== JSON.stringify(DATA.funds.map(f => ({ fund: f.fund, assocCode: f.assocCode, type: f.type })))) {
        status.textContent = "펀드 목록이 변경되었습니다. 변경저장 후 블룸버그 업데이트를 눌러주세요.";
        return false;
      }
      if (!Array.isArray(payload.holdings) || !Array.isArray(payload.trades)) throw new Error("원천데이터 응답 형식 오류");
      if (payload.trades.some(row => !Object.prototype.hasOwnProperty.call(row, "tradeNav"))) throw new Error("실행 중인 서버가 매매일 NAV를 제공하지 않습니다. 서버 창을 닫고 실행파일을 다시 켜주세요.");
      rawFundHoldings.length = 0;
      rawFundTrades.length = 0;
      payload.holdings.forEach(row => rawFundHoldings.push(row));
      payload.trades.forEach(row => rawFundTrades.push(row));
      fundCoverage = payload.coverage || [];
      DATA.asOf = payload.asOf || DATA.asOf;
      DATA.sources = payload.sources;
      applyFundMaster();
      applyMarketData(savedMarket);
      saveFundSnapshot();
      render();
      showRawCoverage();
      return true;
    } catch (error) {
      if (version === rawRequestVersion) status.textContent = `보유·매매 조회 실패 (기존 데이터 유지): ${error.name === "AbortError" ? "조회 시간 초과" : error.message === "Failed to fetch" ? "대시보드 서버를 실행하세요" : error.message}`;
      return false;
    } finally {
      clearTimeout(timeout);
      if (version === rawRequestVersion) button.disabled = false;
    }
  }
  // Local Bloomberg refresh still refreshes raw positions first; ETF registration is separate.
  const savedEmpState = JSON.parse(localStorage.getItem("globalDashboard.emp") || "null");
  if (savedEmpState?.principals) DATA.emp.principals = savedEmpState.principals;
  applyMarketData(savedMarket);
  saveEmp = function () {
    localStorage.setItem("globalDashboard.emp", JSON.stringify({ portfolios: DATA.emp.portfolios, principals: DATA.emp.principals, fx: state.fx }));
  };
  const refreshButton = document.getElementById("refreshMarket");
  const missingEtfButton = document.createElement("button");
  missingEtfButton.type = "button";
  missingEtfButton.className = "actionBtn";
  missingEtfButton.id = "registerMissingEtfs";
  missingEtfButton.textContent = "미등록 ETF 등록";
  const addRowButton = document.getElementById("addEmpRow");
  refreshButton.textContent = "블룸버그 업데이트";
  refreshButton.classList.remove("actionBtn", "primary", "summaryRefresh");
  refreshButton.classList.add("topRefresh");
  empInfoTab.after(refreshButton);
  const bloombergUpdatedAt = document.createElement("span");
  bloombergUpdatedAt.className = "bloombergUpdatedAt";
  bloombergUpdatedAt.id = "bloombergUpdatedAt";
  bloombergUpdatedAt.setAttribute("role", "status");
  refreshButton.after(missingEtfButton, bloombergUpdatedAt);
  function showBloombergUpdatedAt() {
    const updated = savedMarket?.updatedAt && new Date(savedMarket.updatedAt);
    if (updated && !Number.isNaN(updated.getTime())) {
      const stamp = new Intl.DateTimeFormat("ko-KR", {
        timeZone: "Asia/Seoul", year: "numeric", month: "2-digit", day: "2-digit",
        hour: "2-digit", minute: "2-digit", hour12: false
      }).format(updated);
      bloombergUpdatedAt.textContent = `Bloomberg 최종 업데이트 ${stamp} KST`;
    } else {
      bloombergUpdatedAt.textContent = savedMarket?.asOf
        ? `Bloomberg 기존 캐시 ${savedMarket.asOf}` : "Bloomberg 업데이트 기록 없음";
    }
  }
  showBloombergUpdatedAt();
  fundDataTools.style.display = "none";
  addRowButton.textContent = "행 추가";
  const deleteRowsButton = document.createElement("button");
  deleteRowsButton.className = "actionBtn";
  deleteRowsButton.id = "deleteSelectedEmpRows";
  deleteRowsButton.textContent = "행 삭제";
  const saveChangesButton = document.createElement("button");
  saveChangesButton.className = "actionBtn primary";
  saveChangesButton.id = "saveEmpChanges";
  saveChangesButton.textContent = "변경저장";
  addRowButton.before(deleteRowsButton);
  addRowButton.after(saveChangesButton);
  const empViewTabs = document.createElement("div");
  empViewTabs.className = "empViewTabs";
  empViewTabs.setAttribute("role", "tablist");
  empViewTabs.setAttribute("aria-label", "EMP 현황");
  empViewTabs.innerHTML = `<button type="button" class="securitiesSubtab active" role="tab" aria-selected="true" data-emp-view="holdings">보유현황</button><button type="button" class="securitiesSubtab" role="tab" aria-selected="false" data-emp-view="allocation">자산구성</button>`;
  saveChangesButton.after(empViewTabs);
  empViewTabs.querySelectorAll("[data-emp-view]").forEach(button => button.onclick = () => {
    const showAllocation = button.dataset.empView === "allocation";
    empAllocationView.hidden = !showAllocation;
    empHoldingsContent.hidden = showAllocation;
    empViewTabs.querySelectorAll("[data-emp-view]").forEach(tab => {
      const active = tab === button;
      tab.classList.toggle("active", active);
      tab.setAttribute("aria-selected", String(active));
    });
  });
  const saveEtfs = () => {
    localStorage.setItem("globalDashboard.etfs", JSON.stringify(DATA.etfs));
    localStorage.setItem("globalDashboard.etfsSchema", "5");
    return webBridge ? webBridge.replace("etf_db", DATA.etfs) : Promise.resolve();
  };
  const saveFunds = () => {
    FundMasterStorage.save(DATA.funds);
    return webBridge ? webBridge.replace("fund_info", DATA.funds) : Promise.resolve();
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
  state.multiDimension = false;
  state.dashboardSource = "fund";
  state.multiEmp = false;
  state.empSelection = [];
  const selectedRows = new Set();
  const pickerSelected = new Set();
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
    const reference = savedMarket?.securities?.[security] || {};
    if (FundMarketIdentifiers.kind({ security }, reference, []) === "stock") {
      return FundMarketIdentifiers.applyMetadata({ security, code: reference.isin || "", name: ticker }, reference, []);
    }
    return DATA.etfs.find(e => String(e.name || e.ticker || "").split(" ")[0].toUpperCase() === ticker && String(e.emp || "").toUpperCase() === empName)
      || DATA.etfs.find(e => String(e.name || e.ticker || "").split(" ")[0].toUpperCase() === ticker) || {};
  };
  const usdMillion = (value, security) => {
    const usd = isUsd(security) ? Number(value || 0) : Number(value || 0) / Number(state.fx || 1);
    return usd / 1_000_000;
  };
  const usdBillion = (value, security) => usdMillion(value, security) / 1_000;
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
  const emptyEmpRow = ticker => ({ security: ticker, marketCap: 0, avgTurnover3m: 0, quantity: 0, price: 0, prevClose: 0, change: 0 });
  const insertEmpRows = rowsToInsert => {
    if (!rowsToInsert.length) return;
    const rows = empRows();
    const selected = [...selectedRows].sort((a, b) => b - a);
    const insertAt = selected.length ? selected[0] + 1 : rows.length;
    rows.splice(insertAt, 0, ...rowsToInsert);
    selectedRows.clear();
    rowsToInsert.forEach((_, offset) => selectedRows.add(insertAt + offset));
    markEmpDirty(`${rowsToInsert.length}개 행 추가됨 · 변경저장을 눌러 확정`);
    renderEmp();
  };
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
  const fundTypeRank = type => (["EMP", "Pre-IPO", "주식"].indexOf(type) + 1) || (type === "미지정" ? 99 : 50);
  const fundType = (name, code) => {
    const fund = DATA.funds.find(item => code && String(item.assocCode || "").trim() === String(code).trim()) ||
      DATA.funds.find(item => item.fund === name);
    return String(fund?.type || "").trim() || "미지정";
  };
  const orderedFundTypes = types => [...types].sort((a, b) => fundTypeRank(a) - fundTypeRank(b) ||
    a.localeCompare(b, "ko-KR", { numeric: true }));
  renderFilters = function () {
    const box = document.getElementById("filters");
    const groups = new Map();
    DATA.funds.forEach(fund => {
      const type = fundType(fund.fund, fund.assocCode);
      if (!groups.has(type)) groups.set(type, []);
      groups.get(type).push(fund.fund);
    });
    const list = orderedFundTypes(groups.keys()).map(type => `<div class="fundTypeGroup"><div class="fundTypeTitle">${esc(type)}</div><div class="chips">${groups.get(type).map(name => `<button title="${esc(name)}" class="chip ${state.fund.includes(name) ? "active" : ""}" data-key="fund" data-value="${esc(name)}">${esc(name)}</button>`).join("")}</div></div>`).join("");
    box.innerHTML = `<div class="filter"><div class="filterHead"><h3>수익증권</h3><button class="multiBtn ${state.multiFund ? "active" : ""}" data-action="multi">중복</button><button class="miniAll" data-key="fund" data-action="clear">전체</button></div>${list}</div>`;
    box.querySelectorAll("button").forEach(button => button.onclick = () => {
      if (button.dataset.action === "multi") {
        state.multiFund = !state.multiFund;
        if (!state.multiFund && state.fund.length > 1) state.fund = state.fund.slice(0, 1);
      } else if (button.dataset.action === "clear") {
        state.fund = [];
        state.multiFund = false;
      } else {
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
    return { value, krw, pnl, current };
  };

  editEmp = function (index, key, value) {
    if (key !== "quantity") return;
    const row = empRows()[index];
    row.quantity = parseNumber(value);
    row.quantityTouched = true;
    markEmpDirty();
    renderEmp();
  };
  function updatePanelHeader(panel, text, meta, toggleId) {
    const wasExpanded = panel.classList.contains("expanded");
    panelTitle(panel, text, meta, toggleId);
    if (wasExpanded) panel.classList.add("expanded");
    const button = document.getElementById(toggleId);
    button.textContent = wasExpanded ? "접기" : "펼치기";
    bindPanelToggle(panel, toggleId);
  }
  const breakdownColors = ["#087f68", "#397f9a", "#bd8b37", "#8879b6", "#86a49b", "#c27567"];
  function selectedEmpExposureRows() {
    const exposure = [];
    selectedEmpNames().forEach(name => {
      (DATA.emp.portfolios[name] || []).forEach(row => {
        const meta = securityEtf(row.security, name);
        exposure.push({
          source: "emp",
          emp: name,
          code: meta.isin || meta.code || "",
          name: row.security,
          ticker: row.security,
          security: row.security,
          instrumentKind: meta.instrumentKind || "etf",
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
    return fundBase(DATA.holdings).filter(row => !row.isFx && !FundPerformance.isReturnOnlyFund(row.fund));
  }
  function selectedFundFxRows() {
    return fundBase(DATA.holdings).filter(row => row.isFx && !FundPerformance.isReturnOnlyFund(row.fund));
  }
  function currentDashboardRows() {
    return selectedFundRows();
  }
  const isEquityAsset = row => row.instrumentKind === "stock" || String(row.large || "") === "\uC8FC\uC2DD";
  const isBondAsset = row => String(row.large || "") === "\uCC44\uAD8C";
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
    return selectedFundRows();
  }
  function hedgeRatioForFunds() {
    const fxRows = selectedFundFxRows();
    const fxValues = fxRows.map(row => FundMarketIdentifiers.hedgeExposure(row));
    if (fxValues.some(value => value == null)) return null;
    const fxShort = fxValues.reduce((sum, value) => sum + value, 0);
    const usListedValue = selectedFundRows()
      .filter(row => FundPerformance.isHedgeExposure(row, DATA.etfs))
      .reduce((sum, row) => sum + Math.abs(Number(row.lookthrough || 0)), 0);
    return usListedValue ? fxShort / usListedValue : null;
  }
  function groupShares(rows, key) {
    const total = rows.reduce((sum, row) => sum + Math.max(0, Number(row.lookthrough || 0)), 0);
    return Object.entries(rows.reduce((acc, row) => {
      const label = (typeof key === "function" ? key(row) : row[key]) || "미분류";
      acc[label] = (acc[label] || 0) + Math.max(0, Number(row.lookthrough || 0));
      return acc;
    }, {})).map(([label, value]) => ({ label, value, share: total ? value / total : 0 })).sort((a, b) => b.value - a.value);
  }
  function renderBreakdown(listId, totalId, rows, key, sourceRows = null) {
    const entries = groupShares(rows, key).filter(entry => entry.value > 0);
    const total = entries.reduce((sum, entry) => sum + entry.value, 0);
    document.getElementById(totalId).textContent = total ? `${krwEokAmount(total)}억원` : "-";
    const list = document.getElementById(listId);
    list.innerHTML = entries.length ? entries.map((entry, index) => `
      <div class="breakdownRow" tabindex="0" role="button" title="클릭하여 상세 종목 보기" data-breakdown-label="${encodeURIComponent(entry.label)}" style="--bar:${breakdownColors[index % breakdownColors.length]}">
        <div class="breakdownMain"><span class="breakdownName" title="${esc(entry.label)}">${esc(entry.label)}</span><span class="breakdownAmount">${krwEokAmount(entry.value)}</span><span class="breakdownPercent">${pct(entry.share)}</span></div>
        <div class="breakdownTrack" aria-label="${esc(entry.label)} ${pct(entry.share)}"><div class="breakdownFill" style="width:${Math.max(1, entry.share * 100).toFixed(1)}%"></div></div>
      </div>`).join("") : `<div class="breakdownEmpty">표시할 보유 자산이 없습니다.</div>`;
    list.onclick = event => {
      const item = event.target.closest("[data-breakdown-label]");
      if (!item) return;
      const label = decodeURIComponent(item.dataset.breakdownLabel);
      openAllocationDetail(label, row => listId === "regionMixList" || listId === "empRegionMixList"
        ? isEquityAsset(row) && FundAllocationView.investmentRegionOf(row, DATA.etfs) === label
        : (isEquityAsset(row) ? "주식" : row.large || "미분류") === label, item, sourceRows);
    };
    list.onkeydown = event => {
      if ((event.key === "Enter" || event.key === " ") && event.target.matches("[data-breakdown-label]")) {
        event.preventDefault();
        event.target.click();
      }
    };
  }
  function tickerKey(value) {
    return String(value || "").trim().toUpperCase().replace(/\s+/g, " ");
  }
  function tradeTicker(row) {
    if (row.displayTicker) return row.displayTicker;
    const code = tickerKey(row.code);
    const name = tickerKey(row.name || row.ticker);
    const meta = DATA.etfs.find(etf => (code && tickerKey(etf.isin) === code) || (name && (tickerKey(etf.name) === name || tickerKey(etf.koreanName) === name))) || {};
    return meta.ticker || row.security || row.ticker || row.code || "";
  }
  function displayTicker(value) {
    return String(value || "").replace(/\s+(US|KS)\s+EQUITY$/i, "");
  }
  function titled(value, className = "") {
    const text = String(value ?? "");
    return `<span class="${className}" title="${esc(text)}">${esc(text)}</span>`;
  }
  function displayedSector(row, level) {
    return FundAllocationView.holdingSector(row, DATA.etfs, level);
  }
  function fundRateBar(value) {
    if (value == null || !Number.isFinite(Number(value))) return "-";
    const change = Number(value);
    const width = Math.abs(Math.max(-0.05, Math.min(0.05, change))) / 0.05 * 50;
    const fill = change < 0
      ? `<span class="barNeg" style="left:${(50 - width).toFixed(1)}%;width:${width.toFixed(1)}%"></span>`
      : `<span class="barPos" style="left:50%;width:${width.toFixed(1)}%"></span>`;
    return `<div class="fundRateBar" title="${esc(pct2(change))}"><span class="barZero"></span>${fill}<em>${esc(pct2(change))}</em></div>`;
  }
  let currentHoldingGroups = [];
  let holdingModalReturnFocus = null;
  function closeHoldingDetail() {
    holdingModal.classList.remove("active");
    holdingModalReturnFocus?.focus();
    holdingModalReturnFocus = null;
  }
  function openHoldingDetail(index, trigger) {
    const asset = currentHoldingGroups[index];
    if (!asset) return;
    holdingModalReturnFocus = trigger;
    holdingModal.querySelector("#fundHoldingModalTitle").textContent = `${asset.name || asset.code || "자산"} · 보유펀드 ${asset.fundCount}개`;
    const formatQty = value => Number(value || 0).toLocaleString("ko-KR", { maximumFractionDigits: 2 });
    const formatPrice = value => value == null || !Number.isFinite(Number(value)) ? "-" :
      Number(value).toLocaleString("ko-KR", { maximumFractionDigits: 4 });
    const signedPnl = value => value == null ? "-" :
      `<span class="${value < 0 ? "neg" : value > 0 ? "pos" : ""}">${krwEokAmount(value)}</span>`;
    const members = asset.members.map(member => `<tr>
      <td title="${esc(member.fund)}">${esc(member.fund)}</td>
      <td>${formatQty(member.qty)}</td>
      <td>${member.returnOnly ? "-" : krwEokAmount(member.lookthrough)}</td>
      <td>${member.returnOnly || !member.investment ? "-" : pct(member.lookthrough / member.investment)}</td>
      <td>${formatPrice(member.price)}</td><td>-</td><td>-</td>
      <td>${signedPnl(member.pnl)}</td></tr>`).join("");
    const total = `<tr class="totalRow"><td>합계</td><td>-</td><td>${asset.lookthrough == null ? "-" : krwEokAmount(asset.lookthrough)}</td><td>-</td><td>-</td><td>-</td><td>-</td><td>${signedPnl(asset.pnl)}</td></tr>`;
    holdingModal.querySelector(".fundHoldingModalTable").innerHTML = `<thead><tr><th>펀드</th><th>펀드 보유수량</th><th>실보유</th><th>펀드내 비중</th><th>현재 평가가격</th><th>매수 평단가</th><th>누적 평가손익</th><th>당일 PL</th></tr></thead><tbody>${members}${total}</tbody>`;
    holdingModal.classList.add("active");
    holdingModal.querySelector(".fundHoldingModalClose").focus();
  }
  holdingModal.querySelector(".fundHoldingModalClose").onclick = closeHoldingDetail;
  holdingModal.onclick = event => { if (event.target === holdingModal) closeHoldingDetail(); };
  document.addEventListener("keydown", event => {
    if (event.key === "Escape" && holdingModal.classList.contains("active")) closeHoldingDetail();
  });
  let allocationModalReturnFocus = null;
  function closeAllocationDetail() {
    allocationModal.classList.remove("active");
    allocationModalReturnFocus?.focus();
    allocationModalReturnFocus = null;
  }
  function openAllocationDetail(title, predicate, trigger, sourceRows = null) {
    const isEmp = sourceRows !== null;
    const members = (sourceRows || currentDashboardRows()).filter(row => Number(row.lookthrough || 0) > 0 && predicate(row))
      .sort((a, b) => Number(b.lookthrough || 0) - Number(a.lookthrough || 0));
    const total = members.reduce((sum, row) => sum + Number(row.lookthrough || 0), 0);
    allocationModalReturnFocus = trigger;
    allocationModal.querySelector("#allocationModalTitle").textContent = `${title} · 상세 종목`;
    allocationModal.querySelector(".fundHoldingModalNote").textContent = `${members.length}개 보유내역 · 평가금액 합계 ${krwEokAmount(total)}억원 · 선택한 ${isEmp ? "EMP" : "펀드"} 기준`;
    allocationModal.querySelector(".fundHoldingModalTable").innerHTML = `<thead><tr><th>${isEmp ? "EMP" : "펀드"}</th><th>티커</th><th>종목</th><th>자산군</th><th>투자지역</th><th>세부분류</th><th>${isEmp ? "평가금액" : "실보유"}(억원)</th><th>구성 내 비중</th></tr></thead><tbody>${members.map(row => {
      const parts = FundAllocationView.describe(row, DATA.etfs);
      const classification = parts.path.at(-1) || "-";
      return `<tr><td title="${esc(isEmp ? row.emp || "" : row.fund || "")}">${esc(isEmp ? row.emp || "-" : row.fund || "-")}</td><td>${esc(displayTicker(row.displayTicker || row.ticker || row.security || "-"))}</td><td title="${esc(row.name || "")}">${esc(row.name || "-")}</td><td>${esc(parts.asset)}</td><td>${esc(FundAllocationView.investmentRegionOf(row, DATA.etfs))}</td><td title="${esc(classification)}">${esc(classification)}</td><td>${krwEokAmount(row.lookthrough)}</td><td>${pct(total ? Number(row.lookthrough) / total : 0)}</td></tr>`;
    }).join("")}</tbody>`;
    allocationModal.classList.add("active");
    allocationModal.querySelector(".fundHoldingModalClose").focus();
  }
  allocationModal.querySelector(".fundHoldingModalClose").onclick = closeAllocationDetail;
  allocationModal.onclick = event => { if (event.target === allocationModal) closeAllocationDetail(); };
  document.addEventListener("keydown", event => {
    if (event.key === "Escape" && allocationModal.classList.contains("active")) closeAllocationDetail();
  });
  function fundPerformanceRows() {
    const market = savedMarket?.securities || {};
    return DATA.holdings.map(row => {
      const reference = FundMarketIdentifiers.referenceFor(row, market, DATA.etfs);
      return { ...row, marketChange: reference?.change ?? null,
        marketCurrency: reference?.currency || null };
    });
  }
  function calculateFundPerformance(rows) {
    const fxChange = savedMarket?.fxChangeBasis === "KST_1530" ? savedMarket.fxChange : null;
    return FundPerformance.calculate(rows, DATA.etfs, fxChange,
      row => FundMarketIdentifiers.hedgeExposure(row));
  }
  function renderFundHoldings() {
    const heading = holdingPanel?.querySelector("h2");
    if (heading) heading.innerHTML = '수익증권 보유현황<span class="tableUnit">단위:억원</span>';
    const performanceRows = fundPerformanceRows();
    const allRows = fundBase(performanceRows);
    const performanceByFund = new Map(calculateFundPerformance(performanceRows)
      .map(result => [result.fundCode || result.fund, result]));
    const denom = allRows.filter(row => !FundPerformance.isReturnOnlyFund(row.fund))
      .reduce((sum, row) => sum + Number(row.investment || 0), 0);
    const q = (state.holdingSearch || "").toLowerCase();
    currentHoldingGroups = FundHoldingGroups.group(allRows, FundPerformance.isReturnOnlyFund, row =>
      FundPerformance.holdingPnl(row, performanceByFund.get(row.fundCode || row.fund), DATA.etfs)?.adjustedPnl ?? null);
    const rows = currentHoldingGroups.filter(row => !q ||
      [row.name, row.ticker, row.code, row.security, ...row.members.map(member => member.fund)]
        .join(" ").toLowerCase().includes(q))
      .sort((a, b) => (a.lookthrough == null) - (b.lookthrough == null) ||
        (b.lookthrough ?? 0) - (a.lookthrough ?? 0) || String(a.name).localeCompare(String(b.name), "ko-KR"));
    currentHoldingGroups = rows;
    rows.forEach((row, index) => { row.detailIndex = index; });
    table(document.getElementById("holdingTable"), [
      ["펀드", row => `<button type="button" class="fundHoldingCount" data-holding-detail="${row.detailIndex}" aria-label="${esc(row.name || row.code)} 보유펀드 ${row.fundCount}개 상세">${row.fundCount}</button>`], ["티커", row => titled(displayTicker(tradeTicker(row)))],
      ["종목", row => titled(row.name)],
      ["섹터", row => titled(displayedSector(row, sectorLevels.holding))],
      ["등락율", row => {
        return fundRateBar(row.marketChange);
      }],
      ["실보유", row => row.lookthrough == null ? "-" : krwEokAmount(row.lookthrough), "num"],
      ["비중", row => row.lookthrough == null ? "-" : pct(denom ? row.lookthrough / denom : 0), "num"],
      ["PL", row => {
        if (row.pnl == null) return "-";
        return `<span class="${row.pnl < 0 ? "neg" : row.pnl > 0 ? "pos" : ""}">${krwEokAmount(row.pnl)}</span>`;
      }, "num"]
    ], rows);
    document.getElementById("holdingTable").onclick = event => {
      const button = event.target.closest("[data-holding-detail]");
      if (button) openHoldingDetail(Number(button.dataset.holdingDetail), button);
    };
  }
  function renderDashboardTrades() {
    const panel = tradePanel;
    if (!panel) return;
    const heading = panel.querySelector("h2");
    if (heading) heading.innerHTML = '수익증권 매매현황<span class="tableUnit">단위:억원 · NAV대비:%p</span>';
    const wrap = panel.querySelector(".tablewrap");
    if (!wrap) return;
    if (!document.getElementById("tradeTable")) wrap.innerHTML = `<table id="tradeTable"></table>`;
    const excludedTradeAsset = row => {
      const asset = String(row.asset || "");
      const large = String(row.large || "");
      const market = String(row.market || "");
      const name = String(row.name || "");
      const ticker = String(row.ticker || "");
      const raw = [asset, large, market, name, ticker].join(" ");
      return raw.includes("\uD604\uAE08\uC131\uC790\uC0B0") || raw.includes("\uC120\uBB3C\uC635\uC158\uD30C\uC0DD") || large === "\uD604\uAE08" || ticker === "\uD604\uAE08" || name.includes("CASHACC") || FundMarketIdentifiers.isRepoTrade(row);
    };
    let rows = fundBase(DATA.trades).filter(row => !excludedTradeAsset(row));
    const q = (state.tradeSearch || "").toLowerCase();
    rows = rows.filter(x => !q || [x.fund, x.name, x.ticker, x.code].join(" ").toLowerCase().includes(q));
    const grouped = FundTradeNetting.netTrades(rows);
    table(document.getElementById("tradeTable"), [
      ["\uAE30\uC900\uC77C", x => x.date], ["\uD380\uB4DC", x => titled(x.fund)], ["\uAC70\uB798", x => `<span class="tradeSide ${x.side === "매수" ? "buy" : "sell"}">${esc(x.side)}</span>`],
      ["\uC885\uBAA9", x => titled(x.name)], ["\uD2F0\uCEE4", x => titled(displayTicker(tradeTicker(x)))],
      ["GICS1", x => titled(displayedSector(x, "large"))],
      ["GICS2", x => titled(displayedSector(x, "small"))],
      ["순거래금액", x => FundPerformance.isReturnOnlyFund(x.fund) ? "-" : `<span class="${x.lookthrough < 0 ? "neg" : ""}">${krwEokAmount(x.lookthrough)}</span>`, "num"],
      ["NAV대비", x => FundPerformance.isReturnOnlyFund(x.fund) || x.navPp == null ? "-" : `<span class="${x.navPp < 0 ? "neg" : ""}">${x.navPp.toFixed(2)}%p</span>`, "num"]
    ], grouped.sort((a, b) => String(b.date || "").localeCompare(String(a.date || "")) || Math.abs(b.lookthrough) - Math.abs(a.lookthrough)));
  }
  function renderDashboardFundInfo() {
    if (document.getElementById("fundTable")) {
      const fields = [
        ["fund", "펀드명"], ["assocCode", "펀드코드"], ["type", "유형"]
      ];
      document.getElementById("fundTable").innerHTML = `<thead><tr><th><input class="etfCheck" type="checkbox" id="checkAllFunds"></th>${fields.map(([, label]) => `<th>${label}</th>`).join("")}</tr></thead><tbody>${DATA.funds.map((fund, i) => `<tr><td><input class="etfCheck" type="checkbox" data-fund-check="${i}" ${selectedFundInfoRows.has(i) ? "checked" : ""}></td>${fields.map(([key]) => {
        const value = esc(fund[key] || "");
        if (key === "type") {
          const types = ["EMP", "Pre-IPO", "주식"];
          const legacy = fund.type && !types.includes(fund.type);
          return `<td><select class="fundInput" aria-label="${esc(fund.fund || "새 펀드")} 유형" data-fund-i="${i}" data-fund-key="type"><option value="" disabled ${!fund.type ? "selected" : ""}>유형 선택</option>${legacy ? `<option value="${value}" disabled selected>기존: ${value} (재선택)</option>` : ""}${types.map(type => `<option value="${type}" ${fund.type === type ? "selected" : ""}>${type}</option>`).join("")}</select></td>`;
        }
        const inputClass = key === "fund" ? "fundInput wide" : "fundInput";
        return `<td><input class="${inputClass}" data-fund-i="${i}" data-fund-key="${key}" value="${value}"></td>`;
      }).join("")}</tr>`).join("")}</tbody>`;
      document.querySelectorAll("#fundTable [data-fund-key]").forEach(input => input.onchange = () => {
        const row = DATA.funds[Number(input.dataset.fundI)];
        const key = input.dataset.fundKey;
        const previousName = row.fund;
        row[key] = input.value.trim();
        if (key === "fund") state.fund = state.fund.map(name => name === previousName ? row.fund : name);
        applyFundMaster();
        markFundDirty();
        render();
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
      table(document.getElementById("etfTable"), [["ISIN", x => esc(x.isin)], ["티커", x => esc(x.name)], ["종목명", x => esc(x.koreanName)], ["상장", x => esc(x.listing)], ["투자국가", x => esc(x.country)], ["해외투자여부", x => esc(x.underlyingAsset)], ["자산군", x => esc(x.large)], ["대분류", x => esc(x.mid)], ["소분류", x => esc(x.small)]], rows);
    }
  }  function metricAmount(value) {
    const n = Number(value || 0);
    return `${Math.round(n / 100_000_000).toLocaleString("ko-KR")}\uC5B5\uC6D0`;
  }
  function plAmount(value) {
    const n = Number(value || 0) / 100_000_000;
    return `${n.toLocaleString("ko-KR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}\uC5B5\uC6D0`;
  }
  function krwEokAmount(value) {
    return (Number(value || 0) / 100_000_000).toLocaleString("ko-KR", {
      minimumFractionDigits: 2, maximumFractionDigits: 2
    });
  }
  function krwMillionAmount(value) {
    const n = Math.round(Number(value || 0) / 1_000_000);
    return n.toLocaleString("ko-KR");
  }
  function renderFundPerformance() {
    const results = calculateFundPerformance(fundPerformanceRows());
    const ratio = value => value == null ? "-" : pct2(value);
    const signed = value => value == null ? "-" : `<span class="${value < 0 ? "neg" : value > 0 ? "pos" : ""}">${krwEokAmount(value)}</span>`;
    const selectedFund = state.fund.length === 1 ? state.fund[0] : "";
    const byType = new Map();
    results.forEach(result => {
      const type = fundType(result.fund, result.fundCode);
      if (!byType.has(type)) byType.set(type, []);
      byType.get(type).push(result);
    });
    const summaryRow = (label, items, rowClass) => {
      const counted = items.filter(item => !item.returnOnly);
      const sum = key => counted.reduce((total, item) => total + Number(item[key] || 0), 0);
      const held = sum("heldAmount");
      const adjustedMissing = counted.some(item => item.adjustedPnl == null);
      const adjustedPnl = !counted.length || adjustedMissing ? null : sum("adjustedPnl");
      if (rowClass === "totalRow") {
        return `<tr class="totalRow"><td>${esc(label)}</td><td>${counted.length ? krwEokAmount(held) : "-"}</td><td></td><td></td><td></td><td></td><td>${signed(adjustedPnl)}</td></tr>`;
      }
      const denominator = sum("hedgeDenominator");
      const fxItems = counted.filter(item => item.estimateFx);
      const fxMissing = fxItems.some(item => item.fxPnl == null);
      const hedge = denominator && !counted.some(item => item.hedgeMissing) ? sum("hedgeAmount") / denominator : null;
      return `<tr class="${rowClass}"><td>${esc(label)}</td><td>${counted.length ? krwEokAmount(held) : "-"}</td><td>${ratio(hedge)}</td><td>${ratio(fxItems.length && !fxMissing && held ? sum("fxPnl") / held : null)}</td><td>${fundRateBar(held ? sum("basePnl") / held : null)}</td><td>${fundRateBar(held && adjustedPnl != null ? adjustedPnl / held : null)}</td><td>${signed(adjustedPnl)}</td></tr>`;
    };
    const fundRow = result => `<tr class="${selectedFund === result.fund ? "selectedFundRow" : ""}"><td><button class="fundSelect" type="button" data-select-fund="${esc(result.fund)}" title="${esc(result.fund)}${result.returnOnly ? " · 재간접 피투자 펀드: 등락율만 표시" : ""}">${esc(result.fund)}</button></td><td>${result.returnOnly ? "-" : krwEokAmount(result.heldAmount)}</td><td title="${result.returnOnly ? "재간접 피투자 펀드" : `환헷지 분모 ${krwEokAmount(result.hedgeDenominator)}억원 · 헤지금액 ${krwEokAmount(result.hedgeAmount)}억원 · 미헤지 익스포저 ${krwEokAmount(result.unhedgedExposure)}억원`}">${result.returnOnly ? "-" : ratio(result.hedgeRatio)}</td><td>${result.returnOnly ? "-" : result.estimateFx && result.fxPnl != null && result.heldAmount ? ratio(result.fxPnl / result.heldAmount) : "-"}</td><td>${fundRateBar(result.baseReturn)}</td><td>${fundRateBar(result.adjustedReturn)}</td><td>${result.returnOnly ? "-" : signed(result.adjustedPnl)}</td></tr>`;
    const body = orderedFundTypes(byType.keys()).map(type => {
      const items = byType.get(type).sort((a, b) => a.fund.localeCompare(b.fund, "ko-KR", { numeric: true }));
      return `${items.map(fundRow).join("")}${summaryRow(`${type} 소계`, items, "subtotalRow")}`;
    }).join("");
    const tableElement = document.getElementById("fundPerfTable");
    tableElement.innerHTML = `<thead><tr><th>펀드</th><th>실보유</th><th>환헷지 비율</th><th>환율효과</th><th>등락율<br>(환율반영전)</th><th>등락율<br>(환율반영후)</th><th>PL</th></tr></thead><tbody>${results.length ? body + summaryRow("총합계", results, "totalRow") : `<tr><td colspan="7">보유현황이 없습니다.</td></tr>`}</tbody>`;
    tableElement.onclick = event => {
      const button = event.target.closest("[data-select-fund]");
      if (!button) return;
      state.fund = [button.dataset.selectFund];
      state.multiFund = false;
      render();
    };
  }
  function renderDashboardMetrics(rows) {
    const strip = document.getElementById("dashboardMetricStrip");
    if (!strip) return;
    const metricRows = dashboardMetricRows();
    const total = metricRows.reduce((sum, row) => sum + Number(row.lookthrough || 0), 0);
    const equity = metricRows.filter(isEquityAsset).reduce((sum, row) => sum + Number(row.lookthrough || 0), 0);
    const bond = metricRows.filter(isBondAsset).reduce((sum, row) => sum + Number(row.lookthrough || 0), 0);
    const other = metricRows.filter(row => !isEquityAsset(row) && !isBondAsset(row)).reduce((sum, row) => sum + Number(row.lookthrough || 0), 0);
    const performanceResults = calculateFundPerformance(fundBase(fundPerformanceRows()))
      .filter(result => !result.returnOnly);
    const fundPnl = performanceResults.length && performanceResults.every(result => result.adjustedPnl != null)
      ? performanceResults.reduce((sum, result) => sum + result.adjustedPnl, 0) : null;
    const fxBasisReady = savedMarket?.fxChangeBasis === "KST_1530";
    const fxRate = fxBasisReady && savedMarket.fxAt1530 != null && Number.isFinite(Number(savedMarket.fxAt1530))
      ? Number(savedMarket.fxAt1530) : null;
    const fxChange = fxBasisReady && savedMarket.fxChange != null && Number.isFinite(Number(savedMarket.fxChange))
      ? Number(savedMarket.fxChange) : null;
    const hedge = hedgeRatioForFunds();
    const cards = [
      ["수익증권 투자금", metricAmount(fundBase(DATA.holdings).filter(row => !FundPerformance.isReturnOnlyFund(row.fund))
        .reduce((sum, row) => sum + Number(row.investment || 0), 0))],
      ["\uC804\uCCB4\uC775\uC2A4\uD3EC\uC838", metricAmount(total)],
      ["\uC8FC\uC2DD\uC775\uC2A4\uD3EC\uC838", metricAmount(equity)],
      ["\uCC44\uAD8C\uC775\uC2A4\uD3EC\uC838", metricAmount(bond)],
      ["\uAE30\uD0C0\uC775\uC2A4\uD3EC\uC838", metricAmount(other)],
      ["\uC218\uC775\uC99D\uAD8C \uD658\uD5F7\uC9C0 \uBE44\uC728", hedge == null ? "-" : pct(hedge)],
      ["USD/KRW (15:30)", fxRate == null ? "-" : fxRate.toLocaleString("ko-KR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })],
      ["원·달러 등락율", fxChange == null ? "-" : pct2(fxChange), fxChange],
      ["수익증권 PL (환율 반영)", fundPnl == null ? "-" : plAmount(fundPnl), fundPnl]
    ];
    strip.innerHTML = cards.map(([label, value, signed]) => `<div class="metricCard"><span>${label}</span><b class="${Number(signed || 0) < 0 ? "neg" : Number(signed || 0) > 0 ? "pos" : ""}">${value}</b></div>`).join("");
  }
  function renderFundAllocationTree(rows, targetId = "assetChart", sourceRows = null) {
    const target = document.getElementById(targetId);
    const allocation = FundAllocationView.tree(rows, DATA.etfs);
    if (!allocation.groups.length) {
      target.innerHTML = `<div class="empty">표시할 보유 자산이 없습니다.</div>`;
      return;
    }
    const cell = (item, expandable) => `<span class="allocationLabel" title="${esc(item.label)}">${expandable ? `<span class="allocationChevron" data-allocation-toggle title="펼치기·접기">▸</span>` : ""}${esc(item.label)}</span><span class="allocationValue">${krwEokAmount(item.value)}</span><span class="allocationShare">${pct(item.value / allocation.total)}</span>`;
    const node = (item, level, path = []) => {
      const nextPath = [...path, item.label];
      const encoded = encodeURIComponent(JSON.stringify(nextPath));
      return item.children.length
        ? `<details class="allocationNode level${level}" ${level === 0 && item.label !== "주식" ? "" : "open"}><summary class="allocationRow" tabindex="0" data-allocation-path="${encoded}" title="클릭하여 상세 종목 보기">${cell(item, true)}</summary>${item.children.map(child => node(child, level + 1, nextPath)).join("")}</details>`
        : `<div class="allocationRow allocationLeaf level${level}" tabindex="0" role="button" data-allocation-path="${encoded}" title="클릭하여 상세 종목 보기">${cell(item, false)}</div>`;
    };
    target.innerHTML = `<div class="allocationHead"><span>구성</span><span>금액</span><span>비중</span></div>${allocation.groups.map(group => node(group, 0)).join("")}<div class="allocationFoot">개별주식·섹터 ETF는 GICS1 → GICS2 통합 · 광역·팩터 ETF는 추종지수·전략 기준 · 항목 클릭: 상세 종목</div>`;
    target.onclick = event => {
      const row = event.target.closest("[data-allocation-path]");
      if (!row) return;
      event.preventDefault();
      if (event.target.closest("[data-allocation-toggle]")) {
        const details = row.closest("details");
        if (details) details.open = !details.open;
        return;
      }
      const path = JSON.parse(decodeURIComponent(row.dataset.allocationPath));
      openAllocationDetail(path.join(" › "), asset => {
        const parts = FundAllocationView.describe(asset, DATA.etfs);
        return [parts.asset, ...parts.path].slice(0, path.length).every((part, index) => part === path[index]);
      }, row, sourceRows);
    };
    target.onkeydown = event => {
      if ((event.key === "Enter" || event.key === " ") && event.target.matches("[data-allocation-path]")) {
        event.preventDefault();
        event.target.click();
      }
    };
  }
  function renderDashboardAssetCharts() {
    const rows = currentDashboardRows();
    const label = selectionLabel(state.fund, "전체 수익증권");
    const title = "수익증권 자산 구성";
    updatePanelHeader(currentFundPanel, title, `${label} · GICS 기준 · 단위:억원`, "toggleFundAssetPanel");
    renderDashboardMetrics(rows);
    renderFundPerformance();
    renderFundAllocationTree(rows);
    renderBreakdown("assetMixList", "assetMixTotal", rows, row => isEquityAsset(row) ? "주식" : row.large || "미분류");
    renderBreakdown("regionMixList", "regionMixTotal", rows.filter(isEquityAsset), row => FundAllocationView.investmentRegionOf(row, DATA.etfs));
    renderDashboardTrades();
    renderFundHoldings();
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
  function empClassification(row, meta) {
    const parts = FundAllocationView.describe({
      ...meta, code: meta.isin || meta.code || "", security: row.security, ticker: row.security,
      instrumentKind: meta.instrumentKind || "etf"
    }, DATA.etfs);
    return [parts.asset, parts.path[0] || "미분류", parts.path[1] || "미분류"];
  }

  renderEmp = function () {
    const rows = empRows();
    const principal = Number(DATA.emp.principals[state.emp] || 0);
    const metrics = rows.map(empMetrics);
    const total = metrics.reduce((s, x) => s + x.value, 0);
    const totalKrw = metrics.reduce((s, x) => s + x.krw, 0);
    const pnl = metrics.reduce((s, x) => s + x.pnl, 0);
    const summary = summarizeEmpPortfolios();
    document.getElementById("empTitle").textContent = `${state.emp}호 보유현황 · 분석`;
    document.getElementById("ePrincipal").textContent = amount(summary.principal);
    document.getElementById("eValue").textContent = won(summary.krw);
    document.getElementById("eWeight").textContent = pct(summary.principal ? summary.value / summary.principal : 0);
    document.getElementById("ePnl").textContent = won(summary.pnl);
    document.getElementById("ePnl").className = summary.pnl < 0 ? "neg" : "pos";
    document.getElementById("eFx").textContent = state.fx === 1 ? "조회 전" : amount(state.fx);

    const empExposure = selectedEmpExposureRows();
    const empLabel = !state.empSelection?.length ? "전체 EMP" : state.empSelection.length === 1 ? `${state.empSelection[0]}호` : `${state.empSelection[0]}호 외 ${state.empSelection.length - 1}개 EMP`;
    updatePanelHeader(empPanel, "EMP 자산 구성", `${empLabel} · GICS 기준 · 단위:억원`, "toggleEmpAssetPanel");
    renderFundAllocationTree(empExposure, "empAssetChart", empExposure);
    renderBreakdown("empAssetMixList", "empAssetMixTotal", empExposure, row => isEquityAsset(row) ? "주식" : row.large || "미분류", empExposure);
    renderBreakdown("empRegionMixList", "empRegionMixTotal", empExposure.filter(isEquityAsset), row => FundAllocationView.investmentRegionOf(row, DATA.etfs), empExposure);

    const headers = ["선택", "종목", "종목명", "자산군", "대분류", "소분류", "시총($bn)", "3M Avg($mn)", "보유수량", "종가", "평가금액", "등락율(전일)", "손익(원화)", "현재비중"];
    const groups = {};
    rows.forEach((row, index) => {
      const meta = securityEtf(row.security);
      const [large] = empClassification(row, meta);
      (groups[large] ||= []).push({ row, index, meta, metric: metrics[index] });
    });
    let body = "";
    Object.entries(groups).forEach(([large, list]) => {
      const groupMetrics = list.map(x => x.metric);
      const groupValue = groupMetrics.reduce((s, m) => s + m.value, 0);
      const groupQty = list.reduce((s, item) => s + Number(item.row.quantity || 0), 0);
      const groupPnl = groupMetrics.reduce((s, m) => s + m.pnl, 0);
      list.forEach(({ row, index: i, meta, metric: m }) => {
        const [asset, category, detail] = empClassification(row, meta);
        const name = meta.koreanName || meta.fullName || meta.name || "";
        body += `<tr><td><input class="rowCheck" type="checkbox" data-row-check="${i}" ${selectedRows.has(i) ? "checked" : ""}></td><td title="${esc(row.security)}">${esc(row.security)}</td><td title="${esc(name)}">${esc(name)}</td><td>${esc(asset)}</td><td title="${esc(category)}">${esc(category)}</td><td title="${esc(detail)}">${esc(detail)}</td><td class="num">${amount(usdBillion(row.marketCap, row.security))}</td><td class="num">${amount(usdMillion(row.avgTurnover3m, row.security))}</td><td class="manualCell"><input class="manualInput" data-i="${i}" data-key="quantity" inputmode="numeric" value="${Number(row.quantity || 0).toLocaleString("ko-KR")}"></td><td class="num">${amount(row.price)}</td><td class="num">${amount(m.value)}</td><td class="changeBarCell">${changeBar(row.change)}</td><td class="num ${m.pnl < 0 ? "neg" : "pos"}">${krwMillionAmount(m.pnl)}</td><td class="num">${pct2(m.current)}</td></tr>`;
      });
      body += `<tr class="subtotalRow"><td></td><td colspan="7">${esc(large)} 소계</td><td class="num">${groupQty.toLocaleString("ko-KR")}</td><td></td><td class="num">${amount(groupValue)}</td><td></td><td class="num ${groupPnl < 0 ? "neg" : "pos"}">${krwMillionAmount(groupPnl)}</td><td class="num">${pct2(principal ? groupValue / principal : 0)}</td></tr>`;
    });
    const totalQty = rows.reduce((sum, row) => sum + Number(row.quantity || 0), 0);
    body += `<tr class="totalRow"><td></td><td colspan="7">총계</td><td class="num">${totalQty.toLocaleString("ko-KR")}</td><td></td><td class="num">${amount(total)}</td><td></td><td class="num ${pnl < 0 ? "neg" : "pos"}">${krwMillionAmount(pnl)}</td><td class="num">${pct2(principal ? total / principal : 0)}</td></tr>`;
    const colWidths = [3, 8, 15, 6, 8, 10, 6, 7, 8, 5, 7, 7, 5, 5];
    document.getElementById("empTable").innerHTML = `<colgroup>${colWidths.map(width => `<col style="width:${width}%">`).join("")}</colgroup><thead><tr>${headers.map(x => `<th>${x}</th>`).join("")}</tr></thead><tbody>${body}</tbody>`;
    document.querySelectorAll("#empTable input[data-i][data-key]").forEach(input => input.onblur = () => {
      const index = Number(input.dataset.i);
      if (parseNumber(input.value) !== Number(empRows()[index]?.quantity || 0)) editEmp(index, input.dataset.key, input.value);
      else input.value = Number(empRows()[index]?.quantity || 0).toLocaleString("ko-KR");
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
    document.getElementById("pickerTable").innerHTML = `<thead><tr><th><input class="pickerCheck" type="checkbox" id="pickerCheckAll"></th><th>추가</th><th>티커</th><th>종목명</th><th>자산군</th><th>대분류</th><th>소분류</th></tr></thead><tbody>${rows.map((e, i) => { const ticker = String(e.ticker || ""); const [asset, category, detail] = empClassification({ security: ticker }, e); return `<tr><td><input class="pickerCheck" type="checkbox" data-pick-check="${i}" ${pickerSelected.has(ticker) ? "checked" : ""}></td><td><button class="pickBtn ${pickerSelected.has(ticker) ? "added" : ""}" data-pick="${i}">${pickerSelected.has(ticker) ? "추가됨" : "추가"}</button></td><td>${esc(e.ticker)}</td><td>${esc(e.koreanName || e.fullName || "")}</td><td>${esc(asset)}</td><td>${esc(category)}</td><td>${esc(detail)}</td></tr>`; }).join("")}</tbody>`;
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
  document.getElementById("pickSelectedEtfs").onclick = () => {
    const existing = new Set(empRows().map(row => String(row.security || "").toUpperCase()));
    const selected = [...pickerSelected].filter(ticker => !existing.has(String(ticker).toUpperCase()));
    if (!selected.length) {
      document.getElementById("pickerTitle").textContent = `${state.emp} 라벨 ETF 선택 · 선택된 종목 없음`;
      return;
    }
    insertEmpRows(selected.map(emptyEmpRow));
    pickerSelected.clear();
    picker.classList.remove("active");
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
  document.getElementById("saveEmpChanges").onclick = () => {
    saveEmp();
    clearEmpDirty();
  };
  document.getElementById("closePicker").onclick = () => picker.classList.remove("active");
  document.getElementById("pickerSearch").oninput = renderPicker;

  function renderEtfManager() {
    const q = document.getElementById("etfManagerSearch").value.trim().toLowerCase();
    const fields = [["ticker", "Bloomberg 티커"], ["koreanName", "종목명"], ["listing", "상장"], ["country", "투자국가"], ["benchmark", "추종지수·전략"], ["underlyingAsset", "해외투자여부"], ["large", "자산군"], ["mid", "대분류"], ["small", "소분류"]];
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
    const options = (values, selected) => values.map(value => `<option value="${esc(value)}" ${value === selected ? "selected" : ""}>${esc(value)}</option>`).join("");
    const editor = (e, i, key) => {
      if (key === "underlyingAsset") return `<input class="etfInput" value="${e.country === "한국" ? "N" : "Y"}" title="투자국가에 따라 자동 설정" readonly>`;
      if (key === "large") return `<select class="etfInput" data-etf-i="${i}" data-etf-key="large">${options(["주식", "채권", "대체", "현금"], e.large)}</select>`;
      if (e.large === "주식" && key === "mid") return `<select class="etfInput" data-etf-i="${i}" data-etf-key="mid">${options(["미분류", ...Object.keys(EtfDbSchema.gics)], e.mid)}</select>`;
      if (e.large === "주식" && key === "small") return `<select class="etfInput" data-etf-i="${i}" data-etf-key="small">${options(["미분류", ...(EtfDbSchema.gics[e.mid] || [])], e.small)}</select>`;
      return `<input class="etfInput ${["koreanName", "benchmark"].includes(key) ? "wide" : ""}" data-etf-i="${i}" data-etf-key="${key}" value="${esc(e[key] || "")}">`;
    };
    document.getElementById("etfManagerTable").innerHTML = `<thead><tr><th><input class="etfCheck" type="checkbox" id="checkAllEtfs"></th>${header}</tr></thead><tbody>${sortedIndices.map(({ e, i }) => `<tr><td><input class="etfCheck" type="checkbox" data-etf-check="${i}" ${selectedEtfRows.has(i) ? "checked" : ""}></td>${fields.map(([key]) => `<td>${editor(e, i, key)}</td>`).join("")}</tr>`).join("")}</tbody>`;
    document.querySelectorAll("#etfManagerTable [data-etf-sort]").forEach(button => button.onclick = () => {
      const key = button.dataset.etfSort;
      etfSort = etfSort.key === key ? { key, direction: etfSort.direction * -1 } : { key, direction: -1 };
      renderEtfManager();
    });
    document.querySelectorAll("#etfManagerTable [data-etf-key]").forEach(input => input.onchange = () => {
      const etf = DATA.etfs[Number(input.dataset.etfI)];
      const key = input.dataset.etfKey;
      etf[key] = input.value.trim();
      if (key === "country") etf.underlyingAsset = etf.country === "한국" ? "N" : "Y";
      if (key === "large") { etf.mid = "미분류"; etf.small = "미분류"; }
      if (key === "mid") etf.small = "미분류";
      markEtfDirty();
      if (["country", "large", "mid"].includes(key)) renderEtfManager();
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
    try {
      await saveEtfs();
      applyFundMaster();
      applyMarketData(savedMarket);
      render();
      clearEtfDirty();
    } catch (error) {
      markEtfDirty(`DB 저장 실패: ${error.message}`);
    }
  };
  document.getElementById("addFundInfo").onclick = () => {
    DATA.funds.push({ fund: "", assocCode: "", type: "" });
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
    applyFundMaster();
    selectedFundInfoRows.clear();
    state.fund = state.fund.filter(name => DATA.funds.some(fund => fund.fund === name));
    markFundDirty("선택 펀드 삭제됨 · 변경저장을 눌러 확정");
    renderDashboardFundInfo();
    renderFilters();
    renderDashboardAssetCharts();
  };
  document.getElementById("saveFundChanges").onclick = async () => {
    try {
      await saveFunds();
      clearFundDirty();
      renderFilters();
      applyFundMaster();
      applyMarketData(savedMarket);
      render();
      showRawCoverage();
    } catch (error) {
      markFundDirty(`DB 저장 실패: ${error.message}`);
    }
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
  document.getElementById("saveEmpInfoChanges").onclick = () => {
    saveEmp();
    clearEmpInfoDirty();
  };
  document.getElementById("empTable").addEventListener("input", event => {
    const input = event.target.closest("input[data-i][data-key]");
    if (!input) return;
    input.closest("td")?.classList.add("manualChanged");
    const status = document.getElementById("empStatus");
    status.textContent = "입력 중 · 변경저장을 눌러 확정";
    status.classList.add("dirty");
  });  document.getElementById("addEtfMaster").onclick = () => { DATA.etfs.unshift({ ticker: "", name: "", koreanName: "", listing: "", country: "", benchmark: "", underlyingAsset: "Y", large: "주식", mid: "미분류", small: "미분류" }); selectedEtfRows.clear(); markEtfDirty("ETF 추가됨 · 변경저장을 눌러 확정"); renderEtfManager(); };
  missingEtfButton.onclick = async () => {
    if (missingEtfButton.disabled) return;
    if (etfDirty) {
      missingEtfButton.title = "ETF DB에서 편집 중인 변경사항을 먼저 저장하세요.";
      missingEtfButton.textContent = "먼저 변경저장";
      setTimeout(() => { if (!missingEtfButton.disabled) missingEtfButton.textContent = "미등록 ETF 등록"; }, 5000);
      return;
    }
    const candidates = FundEtfDiscovery.candidates(rawFundHoldings, DATA.etfs);
    if (!candidates.length) {
      missingEtfButton.textContent = "미등록 ETF 없음";
      setTimeout(() => { if (!missingEtfButton.disabled) missingEtfButton.textContent = "미등록 ETF 등록"; }, 5000);
      return;
    }
    const label = "미등록 ETF 등록";
    missingEtfButton.disabled = true;
    missingEtfButton.textContent = `${candidates.length}종목 확인 중...`;
    try {
      let payload;
      if (webBridge) {
        payload = await webBridge.request("etf_discovery", candidates.map(candidate => candidate.security),
          state => { missingEtfButton.textContent = state.status === "processing" ? "Bloomberg 확인 중..." : "PC 수신기 대기 중..."; });
      } else {
        const response = await fetch(apiUrl("/api/etf-discovery"), {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ securities: candidates.map(candidate => candidate.security) })
        });
        payload = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(response.status === 404
          ? "대시보드 서버를 종료한 뒤 실행파일을 다시 켜주세요." : payload.error || "ETF 조회 실패");
      }
      const existing = new Set(DATA.etfs.map(etf => String(etf.isin || "").toUpperCase()));
      const additions = candidates.map(candidate =>
        FundEtfDiscovery.rowFor(candidate, payload.securities?.[candidate.security]))
        .filter(row => row && !existing.has(row.isin))
        .map(row => {
          existing.add(row.isin);
          row.benchmark ||= FundAllocationView.benchmarkOf(row);
          return EtfDbSchema.applySuggestedGics(row);
        });
      if (additions.length) {
        DATA.etfs.push(...additions);
        await saveEtfs();
        applyFundMaster();
        applyMarketData(savedMarket);
        render();
        renderEtfManager();
      }
      const skipped = candidates.length - additions.length;
      const summary = `${additions.length}개 ETF 등록${skipped ? ` · ${skipped}개 미확인` : ""}`;
      missingEtfButton.textContent = summary;
      clearEtfDirty(`${summary} · 분류는 ETF DB에서 확인·수정하세요`);
      missingEtfButton.title = `Bloomberg가 ETF로 확인한 종목만 등록했습니다. ${skipped ? "미확인 종목은 등록하지 않았습니다." : ""}`;
    } catch (error) {
      missingEtfButton.textContent = "ETF 등록 실패";
      missingEtfButton.title = error.message === "Failed to fetch" ? "대시보드 서버에 연결할 수 없습니다." : error.message;
      document.getElementById("etfStatus").textContent = missingEtfButton.title;
    } finally {
      missingEtfButton.disabled = false;
      setTimeout(() => { if (!missingEtfButton.disabled) missingEtfButton.textContent = label; }, 5000);
    }
  };
  const marketApiUrl = () => apiUrl("/api/emp-market");
  refreshMarket = async function () {
    const button = document.getElementById("refreshMarket");
    if (button.disabled) return;
    const originalText = button.textContent;
    button.disabled = true;
    button.textContent = isLocalDashboard ? "보유·매매 조회 중..." : "Bloomberg 조회 준비 중...";
    if (isLocalDashboard) await refreshFundRaw();
    const fundRows = DATA.holdings.filter(row => !row.isFx);
    const fundSecurities = [...fundRows, ...DATA.trades].map(fundMarketIdentifier).filter(Boolean);
    const marketStatus = document.getElementById("fundMarketStatus");
    marketStatus.textContent = "Bloomberg 조회 중…";
    button.textContent = "업데이트 중...";
    button.disabled = true;
    try {
      let payload;
      if (webBridge) {
        const securities = [...new Set(fundSecurities)];
        if (!securities.length) throw new Error("조회할 종목이 없습니다.");
        await webBridge.request("full", securities, state => {
          marketStatus.textContent = state.status === "processing"
            ? "PC Bloomberg 수신기가 조회 중…" : "PC Bloomberg 수신기 대기 중…";
        });
        payload = await webBridge.market();
        if (!payload) throw new Error("공용 Bloomberg 시세가 저장되지 않았습니다.");
      } else {
        const res = await fetch(marketApiUrl(), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ securities: [...new Set(fundSecurities)] })
        });
        payload = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(payload.error || "Bloomberg 조회 실패");
      }
      if (Number(payload.fx) > 0) state.fx = Number(payload.fx);
      const map = payload.securities || {};
      savedMarket = { ...payload, fx: state.fx, fxChange: payload.fxChange, fxPrevClose: payload.fxPrevClose,
        fxChangeBasis: payload.fxChangeBasis, fxAt1530: payload.fxAt1530,
        fxPreviousAt1530: payload.fxPreviousAt1530, fxAt1530Date: payload.fxAt1530Date,
        fxPreviousAt1530Date: payload.fxPreviousAt1530Date,
        securities: map, errors: payload.errors || {}, asOf: payload.asOf || "",
        updatedAt: payload.updatedAt || new Date().toISOString() };
      applyMarketData(savedMarket);
      localStorage.setItem("globalDashboard.market", JSON.stringify(savedMarket));
      showBloombergUpdatedAt();
      saveFundSnapshot();
      const priced = Object.values(map).filter(row => row.price != null).length;
      const unavailable = fundRows.filter(row => !fundMarketIdentifier(row) || map[fundMarketIdentifier(row)]?.price == null).length;
      marketStatus.textContent = `Bloomberg ${priced}종목 가격 갱신 · 가격 미제공 ${unavailable}건${payload.fx ? "" : " · 환율 조회 실패 (기존값 유지)"}`;
      if (payload.fxChangeBasis !== "KST_1530") marketStatus.textContent += " · 15:30 환율 계산을 위해 서버 재시작 필요";
      else if (payload.fxChange == null) marketStatus.textContent += ` · USD/KRW 15:30 미조회${payload.errors?.["USDKRW 15:30"] ? ": " + payload.errors["USDKRW 15:30"] : ""}`;
      else marketStatus.textContent += ` · USD/KRW ${payload.fxPreviousAt1530Date}→${payload.fxAt1530Date} 15:30 기준`;
      if (!Object.values(map).some(row => row.securityType)) marketStatus.textContent += " · 티커/GICS 조회를 위해 서버를 종료 후 재실행해주세요";
      render();
      button.textContent = `${Object.keys(map).length.toLocaleString("ko-KR")}종목 갱신`;
    } catch (error) {
      button.textContent = "업데이트 실패";
      marketStatus.textContent = `오류: ${error.message === "Failed to fetch" ? "대시보드 서버를 실행한 뒤 다시 시도하세요" : error.message}`;
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
    if (state.activeTab === "dashboard") render();
    if (state.activeTab === "etfManager") renderEtfManager();
  });
  document.getElementById("reset").onclick = () => {
    state.dashboardSource = "fund";
    state.fund = [];
    state.multiFund = false;
    state.dimensions = ["large"];
    render();
  };
  render = function () {
    renderFilters();
    renderDashboardAssetCharts();
    renderDashboardFundInfo();
    if (!document.getElementById("refreshMarket").disabled) showRawCoverage();
  };
  const tradeSearch = document.getElementById("tradeSearch");
  if (tradeSearch) tradeSearch.oninput = () => { state.tradeSearch = tradeSearch.value; renderDashboardTrades(); };
  const holdingSearch = document.getElementById("holdingSearch");
  if (holdingSearch) holdingSearch.oninput = () => { state.holdingSearch = holdingSearch.value; renderFundHoldings(); };
  const etfSearch = document.getElementById("etfSearch");
  if (etfSearch) etfSearch.oninput = () => { state.etfSearch = etfSearch.value; renderDashboardFundInfo(); };
  render(); renderEtfManager();
  // Keep each table's selected sort when its renderer replaces the table contents.
  const tableSorts = new Map([["fundPerfTable", { column: 0, direction: 1 }],
    ["holdingTable", { column: 5, direction: -1 }]]);
  const sortCollator = new Intl.Collator("ko-KR", { numeric: true, sensitivity: "base" });
  const sortValue = cell => {
    const field = cell?.querySelector('input:not([type="checkbox"]), select');
    return String(field ? field.value : cell?.textContent || "").trim();
  };
  const compareSortValues = (left, right) => {
    const numeric = value => /^[+\-−]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?\s*(?:%p|%|억원|원)?$/.test(value);
    if (numeric(left) && numeric(right)) {
      return Number(left.replace(/[,\s%p억원]/g, "").replace("−", "-")) -
        Number(right.replace(/[,\s%p억원]/g, "").replace("−", "-"));
    }
    return sortCollator.compare(left, right);
  };
  function applyTableSort(tableElement) {
    const sort = tableSorts.get(tableElement.id);
    const headers = [...tableElement.querySelectorAll("thead th")];
    headers.forEach((header, column) => {
      if (header.querySelector('input[type="checkbox"]') || header.hasAttribute("colspan")) return;
      if (!header.querySelector("button[data-sort-column]")) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "sortHeader";
        button.dataset.sortColumn = String(column);
        while (header.firstChild) button.appendChild(header.firstChild);
        header.appendChild(button);
      }
      if (sort?.column === column) header.setAttribute("aria-sort", sort.direction > 0 ? "ascending" : "descending");
      else header.removeAttribute("aria-sort");
    });
    const tbody = tableElement.tBodies[0];
    if (!sort || !tbody) return;
    const rows = [...tbody.rows];
    const ordered = [];
    let group = [];
    const flush = () => {
      group.sort((a, b) => {
        const left = sortValue(a.cells[sort.column]);
        const right = sortValue(b.cells[sort.column]);
        const missing = value => !value || value === "-" || value === "—";
        if (missing(left) !== missing(right)) return missing(left) ? 1 : -1;
        return compareSortValues(left, right) * sort.direction;
      });
      ordered.push(...group);
      group = [];
    };
    rows.forEach(row => {
      if (row.classList.contains("subtotalRow") || row.classList.contains("totalRow")) {
        flush();
        ordered.push(row);
      } else if (row.cells.length === 1 && row.cells[0].colSpan > 1) {
        flush();
        ordered.push(row);
      } else group.push(row);
    });
    flush();
    tbody.replaceChildren(...ordered);
  }
  document.querySelectorAll("table[id]").forEach(tableElement => {
    if (tableElement.id === "etfManagerTable") return; // It already sorts its underlying ETF records.
    tableElement.addEventListener("click", event => {
      const button = event.target.closest("button[data-sort-column]");
      if (!button || !tableElement.contains(button)) return;
      const column = Number(button.dataset.sortColumn);
      const previous = tableSorts.get(tableElement.id);
      tableSorts.set(tableElement.id, { column, direction: previous?.column === column ? -previous.direction : -1 });
      applyTableSort(tableElement);
    });
    new MutationObserver(() => applyTableSort(tableElement)).observe(tableElement, { childList: true });
    applyTableSort(tableElement);
  });
  if (restoredFunds.imported) clearFundDirty("기존 index.html 펀드 목록 이전 완료 · 펀드 백업 권장");
  const rawProvider = DATA.sources?.provider === "supabase" ? "Supabase API" : "Excel";
  document.getElementById("meta").textContent = `${rawProvider} · 보유 ${DATA.asOf} / ${DATA.holdings.length.toLocaleString()}건 · 매매 ${DATA.trades.length.toLocaleString()}건 · ETF ${DATA.etfs.length.toLocaleString()}건`;
  document.getElementById("empMenu").classList.remove("active");
  if (!savedSnapshot) saveFundSnapshot();
  showRawCoverage();
  const marketCacheStatus = document.getElementById("fundMarketStatus");
  const incompleteStocks = DATA.holdings.filter(row => row.instrumentKind === "stock" &&
    (!row.bloombergTicker || !row.gicsLevel1 || !row.gicsLevel2));
  marketCacheStatus.textContent = savedMarket && savedMarket.fxChangeBasis !== "KST_1530"
    ? "15:30 환율 기준 적용 전 저장 데이터 · 서버 재시작 후 블룸버그 업데이트 필요"
    : incompleteStocks.length
      ? `직전 Bloomberg 캐시에 개별주식 티커·GICS ${incompleteStocks.length}건 누락 · 업데이트 버튼으로 복구`
      : savedMarket?.asOf ? `Bloomberg 직전 조회: ${savedMarket.asOf} · 환율 ${savedMarket.fxPreviousAt1530Date}→${savedMarket.fxAt1530Date} 15:30 기준`
        : "Bloomberg 저장 정보 없음 · 업데이트 버튼으로 조회";
  // The direct-investment EMP screens are retired. Keep their saved local data untouched.
  renderEmp = () => {};
  renderEmpMenu = () => {};
  empTab.remove();
  empInfoTab.remove();
  document.getElementById("emp")?.remove();
  document.getElementById("empMenu")?.remove();
  empInfoPane.remove();
  if (webBridge) {
    (async () => {
      try {
        const [etfs, funds, market] = await Promise.all([
          webBridge.read("etf_db"), webBridge.read("fund_info"), webBridge.market()
        ]);
        if (etfs.length) DATA.etfs = etfs.map(etf => EtfDbSchema.normalize(etf));
        if (funds.length) DATA.funds = funds;
        if (market) {
          savedMarket = market;
          applyMarketData(market);
          showBloombergUpdatedAt();
        }
        applyFundMaster();
        applyMarketData(savedMarket);
        render();
        renderEtfManager();
        showRawCoverage();
        let lastUpdatedAt = market?.updatedAt || "";
        setInterval(async () => {
          try {
            const current = await webBridge.market();
            if (!current || current.updatedAt === lastUpdatedAt) return;
            lastUpdatedAt = current.updatedAt;
            savedMarket = current;
            applyMarketData(current);
            showBloombergUpdatedAt();
            if (!document.activeElement?.matches?.("input,textarea,select,[contenteditable=true]")) render();
          } catch (error) { console.warn("Global market sync failed", error); }
        }, 20000);
      } catch (error) {
        document.getElementById("fundMarketStatus").textContent = `공용 DB 조회 실패: ${error.message}`;
      } finally {
        document.documentElement.classList.remove("dashboardBooting", "dashboardBootError");
      }
    })();
  } else {
    document.documentElement.classList.remove("dashboardBooting", "dashboardBootError");
  }
})();
