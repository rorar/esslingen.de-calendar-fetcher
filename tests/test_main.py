import json
import tempfile
import unittest
from pathlib import Path

import main


class TestMainProfiles(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.filter_dir = self.root / "filter"
        self.filter_dir.mkdir(parents=True, exist_ok=True)

        (self.filter_dir / "q.sammelbegrif.id.json").write_text(
            json.dumps(
                {
                    "items": [
                        {"id": "-1", "label": "Alle"},
                        {"id": "330100", "label": "Frauenwochen"},
                        {"id": "11602300", "label": "Welcome Service Region Stuttgart"},
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        (self.filter_dir / "q.kat.id.json").write_text(
            json.dumps(
                {
                    "items": [
                        {"id": "908119", "label": "Politik · Beteiligung", "level": "katlevel1"},
                        {"id": "908120", "label": "Vorträge · Diskussion", "level": "katlevel1"},
                        {"id": "908121", "label": "Bühne · Theater", "level": "katlevel1"},
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_hardcoded_profile_every_date(self) -> None:
        cfg = main.resolve_profile("every_date", self.filter_dir)
        self.assertEqual(cfg["series_ids"], ["-1"])
        self.assertEqual(cfg["anz"], "-1")
        self.assertEqual(cfg["cat_ids"], [])

    def test_dynamic_cat_by_id_simple(self) -> None:
        cfg = main.resolve_profile("DOWNLOAD_CAT_908119", self.filter_dir)
        self.assertEqual(cfg["series_ids"], ["-1"])
        self.assertEqual(cfg["cat_ids"], ["908119"])

    def test_dynamic_cat_by_label_simple_with_underscore_normalization(self) -> None:
        cfg = main.resolve_profile("DOWNLOAD_CAT_BÜHNE_THEATER", self.filter_dir)
        self.assertEqual(cfg["cat_ids"], ["908121"])

    def test_dynamic_sammel_by_label_simple(self) -> None:
        cfg = main.resolve_profile("DOWNLOAD_SAMMEL_Welcome_Service_Region_Stuttgart", self.filter_dir)
        self.assertEqual(cfg["series_ids"], ["11602300"])
        self.assertEqual(cfg["cat_ids"], [])

    def test_advanced_cat_id_multi_with_delimiters(self) -> None:
        cfg = main.resolve_profile("DOWNLOAD_CAT_ID=908119,908120|908121;908119+908120", self.filter_dir)
        self.assertEqual(cfg["series_ids"], ["-1"])
        self.assertEqual(cfg["cat_ids"], ["908119", "908120", "908121"])

    def test_advanced_cat_label_supports_middle_dot_and_plain_space(self) -> None:
        cfg = main.resolve_profile("DOWNLOAD_CAT_LABEL=Bühne · Theater,Bühne Theater", self.filter_dir)
        self.assertEqual(cfg["series_ids"], ["-1"])
        self.assertEqual(cfg["cat_ids"], ["908121"])

    def test_advanced_sammel_id_multi_with_delimiters(self) -> None:
        cfg = main.resolve_profile("DOWNLOAD_SAMMEL_ID=330100|11602300;330100", self.filter_dir)
        self.assertEqual(cfg["series_ids"], ["330100", "11602300"])
        self.assertEqual(cfg["cat_ids"], [])

    def test_advanced_sammel_id_minus_one_collapses_to_all(self) -> None:
        cfg = main.resolve_profile("DOWNLOAD_SAMMEL_ID=330100,-1,11602300", self.filter_dir)
        self.assertEqual(cfg["series_ids"], ["-1"])

    def test_advanced_sammel_label_multi(self) -> None:
        cfg = main.resolve_profile(
            "DOWNLOAD_SAMMEL_LABEL=Frauenwochen,Welcome Service Region Stuttgart",
            self.filter_dir,
        )
        self.assertEqual(cfg["series_ids"], ["330100", "11602300"])

    def test_build_fetch_command_contains_cat_and_series_ids(self) -> None:
        cmd = main.build_fetch_command(
            {
                "series_ids": ["330100", "11602300"],
                "anz": "-1",
                "cat_ids": ["908119", "908120"],
            },
            "structured-data",
        )
        self.assertEqual(cmd.count("--series-id"), 2)
        self.assertEqual(cmd.count("--cat-id"), 2)


if __name__ == "__main__":
    unittest.main()
