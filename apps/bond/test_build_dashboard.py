import unittest
from datetime import date

import pandas as pd

from apps.bond.build_dashboard import process_holding_frame


class ProcessHoldingFrameTest(unittest.TestCase):
    def setUp(self):
        self.holdings = pd.DataFrame(
            {
                "보유일": ["2026-11-13", None],
                "발행일": ["2025-01-01", "2025-01-01"],
                "만기일": ["2027-01-01", "2027-01-01"],
                "예탁원코드": ["F1", "F1"],
                "평가금": [100, 200],
            }
        )
        self.funds = {"F1": {"펀드명": "Test", "지분율": 0.5, "평가금액": 300}}

    def test_missing_holding_date_does_not_break_base_date(self):
        rows, base_date = process_holding_frame(self.holdings, self.funds, [])

        self.assertEqual(base_date, date(2026, 11, 13))
        self.assertEqual(len(rows), 2)
        self.assertEqual([row["date"] for row in rows], ["2026-11-13", ""])

    def test_all_missing_holding_dates_raise_clear_error(self):
        self.holdings["보유일"] = None

        with self.assertRaisesRegex(ValueError, "유효한 보유일"):
            process_holding_frame(self.holdings, self.funds, [])


if __name__ == "__main__":
    unittest.main()
