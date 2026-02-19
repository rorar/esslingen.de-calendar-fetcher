import json
import tempfile
import unittest
from pathlib import Path

from app import analyze_time_formats as analyzer


class TestAnalyzeTimeFormats(unittest.TestCase):
    def test_collect_load_data_files_from_structured_and_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            structured = root / "structured-data"
            history = structured / "history"
            structured.mkdir(parents=True, exist_ok=True)
            history.mkdir(parents=True, exist_ok=True)

            a = structured / "loadData_20307012.json"
            b = history / "loadData_20307012__2026-02-19_10-00-00.json"
            c = structured / "jsonld_20307012_generated.json"
            a.write_text("[]", encoding="utf-8")
            b.write_text("[]", encoding="utf-8")
            c.write_text("[]", encoding="utf-8")

            files = analyzer.collect_load_data_files(structured, history)
            self.assertEqual(files, [a, b])

    def test_analyze_time_formats_builds_value_and_pattern_stats(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            structured = root / "structured-data"
            history = structured / "history"
            structured.mkdir(parents=True, exist_ok=True)
            history.mkdir(parents=True, exist_ok=True)

            (structured / "loadData_20307012.json").write_text(
                json.dumps(
                    [
                        {"id": "1", "titel": "A", "zeit": "18-20:30 Uhr"},
                        {"id": "2", "titel": "B", "zeit": "16 - 17 Uhr telefonisch"},
                        {"id": "3", "titel": "C", "zeit": "ganztägig außerhalb der Gottesdienstzeiten"},
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (history / "loadData_20307012__2026-02-19_10-00-00.json").write_text(
                json.dumps(
                    [
                        {"id": "4", "titel": "D", "zeit": "18-20:30 Uhr"},
                        {"id": "5", "titel": "E", "zeit": "ab 18 Uhr"},
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            files = analyzer.collect_load_data_files(structured, history)
            report = analyzer.analyze_time_formats(files, max_examples=3)

            self.assertEqual(report["file_count"], 2)
            self.assertEqual(report["record_count"], 5)
            self.assertEqual(report["non_empty_time_record_count"], 5)
            self.assertEqual(report["unique_time_values"], 4)

            values = {item["zeit"]: item for item in report["values"]}
            self.assertEqual(values["18-20:30 Uhr"]["count"], 2)
            self.assertEqual(values["18-20:30 Uhr"]["start_time"], "18:00")
            self.assertEqual(values["18-20:30 Uhr"]["end_time"], "20:30")
            self.assertTrue(values["18-20:30 Uhr"]["recognized"])

            self.assertEqual(values["16 - 17 Uhr telefonisch"]["zeit_kommentar"], "telefonisch")
            self.assertFalse(values["ganztägig außerhalb der Gottesdienstzeiten"]["recognized"])

            patterns = {item["format_key"]: item for item in report["format_patterns"]}
            self.assertIn("<time>-<time> uhr", patterns)


if __name__ == "__main__":
    unittest.main()
