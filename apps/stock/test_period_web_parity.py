"""Read-only integration check for local and web period calculations."""

import json
import subprocess
import sys
from pathlib import Path

from local_dashboard_server import (
    load_period_benchmark_snapshots,
    load_performance_snapshots,
    prepare_period_summary,
)


NODE_CHECK = r"""
const Module = require('module');
const originalLoad = Module._load;
Module._load = function(name, parent, main) {
  if (name.startsWith('npm:')) return {createClient() { throw Error('network access disabled'); }};
  return originalLoad.call(this, name, parent, main);
};
global.Deno = {env:{get() { return ''; }}, serve() {}};
const {preparePeriodSummaryV2, periodAnalysisInput} = require(process.argv[1]);
let input = '';
process.stdin.on('data', chunk => input += chunk);
process.stdin.on('end', () => {
  const data = JSON.parse(input);
  const summary = preparePeriodSummaryV2(data.rows, data.start, data.end, data.scope, data.benchmarks);
  process.stdout.write(JSON.stringify({summary, analysisInput:periodAnalysisInput(summary)}));
});
"""


def main() -> None:
    start, end = sys.argv[1:3]
    scope = sys.argv[3] if len(sys.argv) > 3 else "전체 펀드"
    rows = load_performance_snapshots(scope, start, end)
    benchmarks = load_period_benchmark_snapshots(start, end)
    local = prepare_period_summary(rows, start, end, scope, benchmarks)
    bundle = Path(__file__).parents[2] / "tmp" / "stock-edge-check.cjs"
    completed = subprocess.run(
        ["node", "-e", NODE_CHECK, str(bundle)],
        input=json.dumps({"rows": rows, "benchmarks": benchmarks, "start": start, "end": end, "scope": scope}, ensure_ascii=False),
        text=True, encoding="utf-8", capture_output=True, check=True,
    )
    web = json.loads(completed.stdout)["summary"]
    assert local["snapshotCount"] == web["snapshotCount"] == len(rows)
    assert local["snapshotDates"] == web["snapshotDates"]
    for market in ("코스피", "코스닥"):
        local_market = next(row for row in local["marketRows"] if row["market"] == market)
        web_market = next(row for row in web["marketRows"] if row["market"] == market)
        for key in ("actualReturnPct", "benchmarkReturnPct", "relativePp", "heldStockEffectPp", "benchmarkResidualPp"):
            assert abs(local_market[key] - web_market[key]) <= 0.006, (market, key, local_market[key], web_market[key])
        for level in ("large", "mid"):
            local_sectors = {row["sector"]: row for row in local["sectorRowsByLevel"][level] if row["market"] == market}
            web_sectors = {row["sector"]: row for row in web["sectorRowsByLevel"][level] if row["market"] == market}
            assert local_sectors.keys() == web_sectors.keys()
            for sector in local_sectors:
                for key in ("portfolioWeightPct", "benchmarkWeightPct", "excessContributionPp", "excessProfitLoss"):
                    assert abs(local_sectors[sector][key] - web_sectors[sector][key]) <= 0.006, (market, level, sector, key, local_sectors[sector][key], web_sectors[sector][key])
        local_stocks = {row["code"]: row for row in local["stockRowsByMarket"][market]}
        web_stocks = {row["code"]: row for row in web["stockRowsByMarket"][market]}
        assert local_stocks.keys() == web_stocks.keys()
        for code in local_stocks:
            for key in ("averageWeightPct", "averageBenchmarkWeightPct", "excessContributionPp", "excessProfitLoss"):
                assert abs(local_stocks[code][key] - web_stocks[code][key]) <= 0.006, (market, code, key, local_stocks[code][key], web_stocks[code][key])
    assert [item["month"] for item in local.get("monthlyAnalysis", [])] == [item["month"] for item in web.get("monthlyAnalysis", [])]
    print(f"period parity passed: {start}..{end}, {len(rows)} snapshots, {len(web.get('monthlyAnalysis', []))} monthly sections")


if __name__ == "__main__":
    main()
