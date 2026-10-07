import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from local_dashboard_server import (
    get_or_create_period_analysis,
    get_shared_period_history,
    period_analysis_fingerprint,
    shared_period_history_entry,
)
from period_ai_history import find_matching_history, get_history, list_history, save_history


class PeriodAiHistoryTests(unittest.TestCase):
    def test_history_persists_metadata_and_original_analysis(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.sqlite3"
            saved = save_history(
                "전체 펀드", "2026-07-01", "2026-10-05", "fingerprint-1",
                "2026-10-07T01:23:00+00:00", "test-model", 64,
                "[코스피] 저장된 원문입니다.", path,
            )
            self.assertEqual(saved["analysis"], "[코스피] 저장된 원문입니다.")
            self.assertEqual(saved["fundScope"], "전체 펀드")
            self.assertEqual(saved["snapshotCount"], 64)
            listed = list_history(path)
            self.assertEqual(len(listed), 1)
            self.assertNotIn("analysis", listed[0])
            self.assertEqual(get_history(saved["id"], path), saved)
            self.assertEqual(find_matching_history(
                "전체 펀드", "2026-07-01", "2026-10-05", "fingerprint-1", path
            ), saved)
            self.assertIsNone(find_matching_history(
                "전체 펀드", "2026-07-01", "2026-10-05", "changed-data", path
            ))

    def test_same_input_reuses_analysis_without_llm_call(self):
        summary = {
            "selectedFund": "전체 펀드", "startDate": "2026-07-01",
            "endDate": "2026-10-05", "analysisFingerprint": "same-input",
            "snapshotCount": 64,
        }
        saved = None

        def find(*args):
            return saved

        def save(*args):
            nonlocal saved
            saved = {
                "id": 1, "analysis": args[-1], "generatedAt": args[-4],
                "analysisFingerprint": args[3],
            }
            return saved

        with patch("local_dashboard_server.find_matching_history", side_effect=find), patch(
            "local_dashboard_server.save_history", side_effect=save
        ), patch("local_dashboard_server.analyze_period_performance", return_value={
            "analysis": "원문", "model": "test-model",
            "generatedAt": "2026-10-07T01:23:00+00:00",
        }) as analyze:
            first = get_or_create_period_analysis(summary)
            second = get_or_create_period_analysis(summary)
        self.assertFalse(first["reused"])
        self.assertTrue(second["reused"])
        self.assertEqual(second["analysis"], "원문")
        analyze.assert_called_once()

    def test_fingerprint_changes_with_analysis_input(self):
        summary = {"startDate": "2026-07-01", "endDate": "2026-10-05", "selectedFund": "전체 펀드", "snapshotCount": 64, "marketRows": [
            {"market": "코스피", "relativePp": -1.0},
        ]}
        first = period_analysis_fingerprint(summary)
        summary["marketRows"][0]["relativePp"] = -2.0
        self.assertNotEqual(first, period_analysis_fingerprint(summary))

    def test_web_history_can_open_original_analysis_read_only(self):
        row = {
            "selected_fund": "기간:2026-09-01:2026-09-30:전체 펀드",
            "generated_at": "2026-10-01T00:00:00+00:00",
            "model": "test-model",
            "analysis": "저장된 웹 분석 원문",
        }
        entry = shared_period_history_entry(row)
        self.assertEqual(entry["source"], "web")
        self.assertNotIn("analysis", entry)
        with patch("local_dashboard_server.supabase_get", return_value=[row]) as get:
            detail = get_shared_period_history(entry["id"][4:])
        self.assertEqual(detail["analysis"], row["analysis"])
        self.assertEqual(detail["fundScope"], "전체 펀드")
        get.assert_called_once()

    def test_invalid_web_history_id_is_rejected(self):
        with self.assertRaises(ValueError):
            get_shared_period_history("a")


if __name__ == "__main__":
    unittest.main()
