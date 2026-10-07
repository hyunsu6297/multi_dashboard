import unittest
from io import BytesIO
from json import dumps, loads
from unittest.mock import patch

from local_dashboard_server import analyze_period_performance, benchmark_weights_for_day, prepare_period_summary


class PeriodAttributionTests(unittest.TestCase):
    def test_reconciliation_and_unheld_day_benchmark_weight(self):
        def position(code, exp, pl, change, sector):
            return {
                "code": code,
                "name": code,
                "market": "코스피",
                "sectorLarge": sector,
                "sectorMid": sector,
                "benchmarkCode": code,
                "exp": exp,
                "pl": pl,
                "changeRatePct": change,
                "priceAvailable": True,
            }

        rows = [
            {
                "performance_date": "2026-07-01",
                "environment": "production",
                "payload": {
                    "positions": [
                        position("A", 60, 6, 10, "IT"),
                        position("B", 40, 0, 0, "소비재"),
                    ],
                    "marketIndexReturns": {"코스피": 8},
                },
            },
            {
                "performance_date": "2026-07-02",
                "environment": "production",
                "payload": {
                    "positions": [position("B", 100, 5, 5, "소비재")],
                    "marketIndexReturns": {"코스피": 7},
                },
            },
        ]
        benchmarks = [
            {
                "market": "코스피",
                "business_date": day,
                "weights": {"A": 0.8, "B": 0.2},
            }
            for day in ("2026-06-30", "2026-07-01")
        ]
        summary = prepare_period_summary(
            rows, "2026-07-01", "2026-07-02", "전체 펀드", benchmarks
        )
        market = summary["marketRows"][0]
        self.assertEqual(market["actualReturnPct"], 11)
        self.assertEqual(market["benchmarkReturnPct"], 15.56)
        self.assertEqual(market["relativePp"], -4.56)
        self.assertEqual(market["heldStockEffectPp"], 2)
        self.assertEqual(market["benchmarkResidualPp"], -6)
        self.assertEqual(market["compoundingAdjustmentPp"], -0.56)
        self.assertAlmostEqual(
            sum(market[key] for key in (
                "heldStockEffectPp", "benchmarkResidualPp", "compoundingAdjustmentPp"
            )), market["relativePp"]
        )
        stocks = {item["code"]: item for item in summary["stockRowsByMarket"]["코스피"]}
        self.assertEqual(stocks["A"]["averageWeightPct"], 30)
        self.assertEqual(stocks["A"]["averageBenchmarkWeightPct"], 80)
        self.assertEqual(stocks["A"]["activeWeightPp"], -50)
        self.assertEqual(stocks["A"]["excessContributionPp"], -2)
        self.assertEqual(stocks["B"]["excessContributionPp"], 4)
        sectors = summary["sectorRowsByLevel"]["mid"]
        self.assertEqual(sum(item["excessContributionPp"] for item in sectors if item["market"] == "코스피"), 2)

    def test_benchmark_weight_never_uses_future_date(self):
        rows = [{"market": "코스피", "business_date": "2026-07-02", "weights": {"A": 0.8}}]
        self.assertEqual(benchmark_weights_for_day(rows, "코스피", "2026-07-02"), {})

    def test_long_period_uses_independent_monthly_market_data(self):
        rows = []
        for day, pl, benchmark in (
            ("2026-07-01", 10, 5),
            ("2026-07-31", -5, -2),
            ("2026-08-03", 2, 3),
        ):
            rows.append({
                "performance_date": day,
                "payload": {
                    "positions": [{
                        "code": "A", "name": "A", "market": "코스피",
                        "sectorLarge": "IT", "sectorMid": "IT", "benchmarkCode": "A",
                        "exp": 100, "pl": pl, "priceAvailable": True,
                        "changeRatePct": pl,
                    }],
                    "marketIndexReturns": {"코스피": benchmark},
                },
            })
        benchmarks = [
            {"market": "코스피", "business_date": day, "weights": {"A": 0.5}}
            for day in ("2026-06-30", "2026-07-30", "2026-07-31")
        ]
        summary = prepare_period_summary(
            rows, "2026-07-01", "2026-08-03", "전체 펀드", benchmarks
        )
        monthly = summary["monthlyAnalysis"]
        self.assertEqual([item["month"] for item in monthly], ["2026-07", "2026-08"])
        self.assertEqual([item["days"] for item in monthly], [2, 1])
        july = monthly[0]["marketAnalysis"][0]
        august = monthly[1]["marketAnalysis"][0]
        self.assertEqual(july["performance"]["actualReturnPct"], 5)
        self.assertEqual(july["performance"]["benchmarkReturnPct"], 2.9)
        self.assertEqual(august["performance"]["actualReturnPct"], 2)
        self.assertEqual(august["performance"]["benchmarkReturnPct"], 3)
        self.assertEqual(july["sectors"][0]["sector"], "IT")
        self.assertEqual(august["sectors"][0]["sector"], "IT")
        self.assertNotIn("monthlyAnalysis", prepare_period_summary(
            rows[:2], "2026-07-01", "2026-07-31", "전체 펀드", benchmarks
        ))

        captured = {}

        def fake_urlopen(request, timeout):
            captured.update(loads(request.data))
            return BytesIO(dumps({"output_text": "[코스피] 확인했습니다.", "status": "completed"}).encode())

        with patch("local_dashboard_server.api_key", return_value="test-key"), patch(
            "local_dashboard_server.urllib.request.urlopen", side_effect=fake_urlopen
        ):
            result = analyze_period_performance(summary)
        self.assertEqual(
            [item["month"] for item in loads(captured["input"])["monthlyAnalysis"]],
            ["2026-07", "2026-08"],
        )
        self.assertIn("월별 글머리표", captured["instructions"])
        self.assertTrue(result["generatedAt"])


if __name__ == "__main__":
    unittest.main()
