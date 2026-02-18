import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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

    def test_run_preprocess_uses_wrapper_script(self) -> None:
        with patch("main.run_python_script", return_value=0) as mocked:
            rc = main.run_preprocess("config/processing_config.json")
        self.assertEqual(rc, 0)
        script_path, args = mocked.call_args.args
        self.assertEqual(script_path.name, "preprocess_data.py")
        self.assertEqual(args, ["--config", "config/processing_config.json"])

    def test_run_postprocess_uses_wrapper_script(self) -> None:
        with patch("main.run_python_script", return_value=0) as mocked:
            rc = main.run_postprocess("config/processing_config.json")
        self.assertEqual(rc, 0)
        script_path, args = mocked.call_args.args
        self.assertEqual(script_path.name, "postprocess_output.py")
        self.assertEqual(args, ["--config", "config/processing_config.json"])

    def test_main_preprocess_only_does_not_run_download(self) -> None:
        with (
            patch("sys.argv", ["main.py", "--preprocess"]),
            patch("main.run_preprocess", return_value=0) as mocked_pre,
            patch("main.run_download") as mocked_download,
            patch("main.resolve_profile") as mocked_profile,
        ):
            rc = main.main()

        self.assertEqual(rc, 0)
        mocked_pre.assert_called_once_with("config/processing_config.json")
        mocked_download.assert_not_called()
        mocked_profile.assert_not_called()

    def test_main_profile_and_postprocess_runs_both(self) -> None:
        with (
            patch("sys.argv", ["main.py", "--profile", "frauentage", "--postprocess", "--process-config", "x.json"]),
            patch("main.resolve_profile", return_value={"series_ids": ["330100"], "anz": "-1", "cat_ids": []}) as mocked_profile,
            patch("main.run_download", return_value=0) as mocked_download,
            patch("main.run_postprocess", return_value=0) as mocked_post,
        ):
            rc = main.main()

        self.assertEqual(rc, 0)
        mocked_profile.assert_called_once()
        mocked_download.assert_called_once()
        mocked_post.assert_called_once_with("x.json")


if __name__ == "__main__":
    unittest.main()
