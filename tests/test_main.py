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
                        {"id": "908122", "label": "Alpha, Beta", "level": "katlevel1"},
                        {"id": "908123", "label": "C++ Kurs", "level": "katlevel1"},
                        {"id": "908124", "label": "L'art pour l'art", "level": "katlevel1"},
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

    def test_advanced_cat_label_supports_quoted_values_with_delimiters(self) -> None:
        cfg = main.resolve_profile('DOWNLOAD_CAT_LABEL="Alpha, Beta"+"C++ Kurs"', self.filter_dir)
        self.assertEqual(cfg["series_ids"], ["-1"])
        self.assertEqual(cfg["cat_ids"], ["908122", "908123"])

    def test_split_multi_values_respects_quotes(self) -> None:
        values = main.split_multi_values('"Alpha, Beta"+"C++ Kurs";Bühne Theater')
        self.assertEqual(values, ["Alpha, Beta", "C++ Kurs", "Bühne Theater"])

    def test_split_multi_values_supports_escaped_delimiters(self) -> None:
        values = main.split_multi_values(r"Alpha\, Beta+C\+\+ Kurs")
        self.assertEqual(values, ["Alpha, Beta", "C++ Kurs"])

    def test_split_multi_values_keeps_apostrophes_inside_tokens(self) -> None:
        values = main.split_multi_values("L'art pour l'art")
        self.assertEqual(values, ["L'art pour l'art"])

    def test_split_multi_values_raises_on_unbalanced_quotes(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unbalancierte Anführungszeichen"):
            main.split_multi_values('"Bühne · Theater+Vorträge · Diskussion')

    def test_advanced_cat_label_with_apostrophes_resolves(self) -> None:
        cfg = main.resolve_profile("DOWNLOAD_CAT_LABEL=L'art pour l'art", self.filter_dir)
        self.assertEqual(cfg["series_ids"], ["-1"])
        self.assertEqual(cfg["cat_ids"], ["908124"])

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
        self.assertIn("--backend", cmd)
        self.assertIn("auto", cmd)
        self.assertEqual(cmd.count("--series-id"), 2)
        self.assertEqual(cmd.count("--cat-id"), 2)

    def test_build_fetch_command_allows_custom_backend(self) -> None:
        cmd = main.build_fetch_command(
            {
                "series_ids": ["330100"],
                "anz": "-1",
                "cat_ids": [],
            },
            "structured-data",
            backend="stealth",
        )
        backend_index = cmd.index("--backend")
        self.assertEqual(cmd[backend_index + 1], "stealth")

    def test_update_filters_uses_wrapper_script_and_backend(self) -> None:
        with patch("main.run_python_script", return_value=0) as mocked:
            rc = main.update_filters(self.filter_dir, backend="stealth")
        self.assertEqual(rc, 0)
        script_path, args = mocked.call_args.args
        self.assertEqual(script_path.name, "fetch_filter_options.py")
        self.assertEqual(args, ["--out-dir", str(self.filter_dir), "--backend", "stealth"])

    def test_update_filters_quiet_mode_adds_flag(self) -> None:
        with patch("main.run_python_script", return_value=0) as mocked:
            rc = main.update_filters(self.filter_dir, backend="auto", quiet=True)
        self.assertEqual(rc, 0)
        script_path, args = mocked.call_args.args
        self.assertEqual(script_path.name, "fetch_filter_options.py")
        self.assertEqual(args, ["--out-dir", str(self.filter_dir), "--backend", "auto", "--quiet"])

    def test_run_preprocess_uses_wrapper_script(self) -> None:
        with patch("main.run_python_script", return_value=0) as mocked:
            rc = main.run_preprocess("config/processing_config.json")
        self.assertEqual(rc, 0)
        script_path, args = mocked.call_args.args
        self.assertEqual(script_path.name, "preprocess_data.py")
        self.assertEqual(args, ["--config", "config/processing_config.json"])

    def test_run_preprocess_with_event_filters_uses_wrapper_flags(self) -> None:
        with patch("main.run_python_script", return_value=0) as mocked:
            rc = main.run_preprocess(
                "config/processing_config.json",
                event_ids=["1", "2,3"],
                event_titles=["Titel A"],
                event_urls=["https://example.org/a"],
            )
        self.assertEqual(rc, 0)
        script_path, args = mocked.call_args.args
        self.assertEqual(script_path.name, "preprocess_data.py")
        self.assertEqual(
            args,
            [
                "--config",
                "config/processing_config.json",
                "--event-id",
                "1",
                "--event-id",
                "2,3",
                "--event-title",
                "Titel A",
                "--event-url",
                "https://example.org/a",
            ],
        )

    def test_run_postprocess_uses_wrapper_script(self) -> None:
        with patch("main.run_python_script", return_value=0) as mocked:
            rc = main.run_postprocess("config/processing_config.json")
        self.assertEqual(rc, 0)
        script_path, args = mocked.call_args.args
        self.assertEqual(script_path.name, "postprocess_output.py")
        self.assertEqual(args, ["--config", "config/processing_config.json"])

    def test_run_postprocess_with_event_filters_uses_wrapper_flags(self) -> None:
        with patch("main.run_python_script", return_value=0) as mocked:
            rc = main.run_postprocess(
                "config/processing_config.json",
                from_boilerplate=True,
                event_ids=["1"],
                event_titles=["Titel A,Titel B"],
                event_urls=["https://example.org/a"],
            )
        self.assertEqual(rc, 0)
        script_path, args = mocked.call_args.args
        self.assertEqual(script_path.name, "postprocess_output.py")
        self.assertEqual(
            args,
            [
                "--config",
                "config/processing_config.json",
                "--from-boilerplate",
                "--event-id",
                "1",
                "--event-title",
                "Titel A,Titel B",
                "--event-url",
                "https://example.org/a",
            ],
        )

    def test_run_postprocess_from_boilerplate_uses_wrapper_flag(self) -> None:
        with patch("main.run_python_script", return_value=0) as mocked:
            rc = main.run_postprocess("config/processing_config.json", from_boilerplate=True)
        self.assertEqual(rc, 0)
        script_path, args = mocked.call_args.args
        self.assertEqual(script_path.name, "postprocess_output.py")
        self.assertEqual(args, ["--config", "config/processing_config.json", "--from-boilerplate"])

    def test_run_csv_lint_uses_wrapper_script(self) -> None:
        with patch("main.run_python_script", return_value=0) as mocked:
            rc = main.run_csv_lint(
                config_path="config/processing_config.json",
                output_dir="output",
                csv_files=["output/a.csv", "output/b.csv"],
                recursive=True,
                no_schema_check=True,
                schema_check=True,
                strict_config=True,
            )
        self.assertEqual(rc, 0)
        script_path, args = mocked.call_args.args
        self.assertEqual(script_path.name, "lint_csv.py")
        self.assertEqual(
            args,
            [
                "--config",
                "config/processing_config.json",
                "--output-dir",
                "output",
                "--csv-file",
                "output/a.csv",
                "--csv-file",
                "output/b.csv",
                "--recursive",
                "--no-schema-check",
                "--schema-check",
                "--strict-config",
            ],
        )

    def test_main_preprocess_only_does_not_run_download(self) -> None:
        with (
            patch("sys.argv", ["main.py", "--preprocess"]),
            patch("main.run_preprocess", return_value=0) as mocked_pre,
            patch("main.run_download") as mocked_download,
            patch("main.resolve_profile") as mocked_profile,
        ):
            rc = main.main()

        self.assertEqual(rc, 0)
        mocked_pre.assert_called_once_with(
            "config/processing_config.json",
            event_ids=[],
            event_titles=[],
            event_urls=[],
        )
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
        mocked_post.assert_called_once_with(
            "x.json",
            from_boilerplate=False,
            event_ids=[],
            event_titles=[],
            event_urls=[],
        )

    def test_main_passes_backend_to_download(self) -> None:
        profile_cfg = {"series_ids": ["330100"], "anz": "-1", "cat_ids": []}
        with (
            patch("sys.argv", ["main.py", "--profile", "frauentage", "--backend", "stealth"]),
            patch("main.resolve_profile", return_value=profile_cfg),
            patch("main.run_download", return_value=0) as mocked_download,
        ):
            rc = main.main()

        self.assertEqual(rc, 0)
        mocked_download.assert_called_once_with(profile_cfg, "structured-data", backend="stealth")

    def test_main_postprocess_with_from_boilerplate_passes_flag(self) -> None:
        with (
            patch("sys.argv", ["main.py", "--postprocess", "--from-boilerplate"]),
            patch("main.run_postprocess", return_value=0) as mocked_post,
            patch("main.run_download") as mocked_download,
        ):
            rc = main.main()

        self.assertEqual(rc, 0)
        mocked_download.assert_not_called()
        mocked_post.assert_called_once_with(
            "config/processing_config.json",
            from_boilerplate=True,
            event_ids=[],
            event_titles=[],
            event_urls=[],
        )

    def test_main_postprocess_passes_event_filters(self) -> None:
        with (
            patch(
                "sys.argv",
                [
                    "main.py",
                    "--postprocess",
                    "--event-id",
                    "523253141860,523253151003",
                    "--event-title",
                    "Iftar für Frauen",
                    "--event-url",
                    "https://www.esslingen.de/frauenwochen",
                ],
            ),
            patch("main.run_postprocess", return_value=0) as mocked_post,
            patch("main.run_download") as mocked_download,
        ):
            rc = main.main()

        self.assertEqual(rc, 0)
        mocked_download.assert_not_called()
        mocked_post.assert_called_once_with(
            "config/processing_config.json",
            from_boilerplate=False,
            event_ids=["523253141860,523253151003"],
            event_titles=["Iftar für Frauen"],
            event_urls=["https://www.esslingen.de/frauenwochen"],
        )

    def test_main_lint_only_does_not_run_download(self) -> None:
        with (
            patch("sys.argv", ["main.py", "--lint-csv"]),
            patch("main.run_csv_lint", return_value=0) as mocked_lint,
            patch("main.run_download") as mocked_download,
            patch("main.resolve_profile") as mocked_profile,
        ):
            rc = main.main()

        self.assertEqual(rc, 0)
        mocked_download.assert_not_called()
        mocked_profile.assert_not_called()
        mocked_lint.assert_called_once_with(
            config_path="config/processing_config.json",
            output_dir=None,
            csv_files=[],
            recursive=False,
            no_schema_check=False,
            schema_check=False,
            strict_config=False,
        )

    def test_main_from_boilerplate_without_postprocess_fails(self) -> None:
        with patch("sys.argv", ["main.py", "--from-boilerplate"]):
            rc = main.main()
        self.assertEqual(rc, 1)

    def test_list_filters_uses_cached_files(self) -> None:
        rc = main.list_filters(self.filter_dir, backend="auto")
        self.assertEqual(rc, 0)

    def test_main_list_filters_only_does_not_run_download(self) -> None:
        with (
            patch("sys.argv", ["main.py", "--list-filters"]),
            patch("main.list_filters", return_value=0) as mocked_list_filters,
            patch("main.run_download") as mocked_download,
            patch("main.resolve_profile") as mocked_profile,
        ):
            rc = main.main()

        self.assertEqual(rc, 0)
        mocked_download.assert_not_called()
        mocked_profile.assert_not_called()
        mocked_list_filters.assert_called_once_with(Path("filter"), backend="auto")

    def test_main_doctor_only_does_not_run_download(self) -> None:
        with (
            patch("sys.argv", ["main.py", "--doctor"]),
            patch("main.doctor", return_value=0) as mocked_doctor,
            patch("main.run_download") as mocked_download,
            patch("main.resolve_profile") as mocked_profile,
        ):
            rc = main.main()

        self.assertEqual(rc, 0)
        mocked_download.assert_not_called()
        mocked_profile.assert_not_called()
        mocked_doctor.assert_called_once_with(Path("filter"), "config/processing_config.json")

    def test_main_doctor_failure_stops_execution(self) -> None:
        with (
            patch("sys.argv", ["main.py", "--doctor"]),
            patch("main.doctor", return_value=1) as mocked_doctor,
            patch("main.run_download") as mocked_download,
        ):
            rc = main.main()

        self.assertEqual(rc, 1)
        mocked_doctor.assert_called_once()
        mocked_download.assert_not_called()

    def test_doctor_returns_zero_with_warnings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            filter_dir = Path(tmp_dir) / "filter"
            filter_dir.mkdir(parents=True, exist_ok=True)
            with (
                patch("main.check_dns", return_value=(False, "dns warn")),
                patch("main.check_https", return_value=(False, "https warn")),
                patch("main.has_stealth_requests", return_value=False),
                patch("main.has_frictionless", return_value=False),
                patch("main.shutil.which", return_value=None),
            ):
                rc = main.doctor(filter_dir, "missing_config.json")
            self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
