import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import process_data_pipeline as pipeline


class TestProcessDataPipeline(unittest.TestCase):
    def test_clean_text_with_all_rules(self) -> None:
        cfg = {
            "remove_html_entities": True,
            "remove_html_tags": True,
            "remove_line_breaks_and_tabs": True,
            "trim_whitespace": True,
        }
        raw = "  Hallo\t<b>Welt</b>\n&amp; Freunde  "
        cleaned = pipeline.clean_text(raw, cfg)
        self.assertEqual(cleaned, "Hallo Welt & Freunde")

    def test_extract_time_from_datetime_keeps_date_only_empty(self) -> None:
        self.assertEqual(pipeline.extract_time_from_datetime("2026-03-08"), "")
        self.assertEqual(pipeline.extract_time_from_datetime("2026-03-08T09:05:00"), "09:05")
        self.assertEqual(pipeline.extract_time_from_datetime("2026-03-08T09:05:00+01:00"), "09:05")

    def test_split_time_range_from_normalized_values(self) -> None:
        self.assertEqual(pipeline.split_time_range("18:00-20:00"), ("18:00", "20:00"))
        self.assertEqual(pipeline.split_time_range("18:00"), ("18:00", ""))
        self.assertEqual(pipeline.split_time_range(""), ("", ""))

    def test_normalize_record_splits_load_data_time_range(self) -> None:
        cfg = pipeline.deep_merge_dict(pipeline.DEFAULT_CONFIG, {})
        record = {
            "id": "x1",
            "titel": "Abendveranstaltung",
            "von": "18.02.2026",
            "zeit": "18:00-20:00",
        }
        normalized = pipeline.normalize_record(record, "loadData_20307012.json", cfg)
        self.assertEqual(normalized["time"], "18:00-20:00")
        self.assertEqual(normalized["start_time"], "18:00")
        self.assertEqual(normalized["end_time"], "20:00")

    def test_normalize_record_splits_jsonld_time_range(self) -> None:
        cfg = pipeline.deep_merge_dict(pipeline.DEFAULT_CONFIG, {})
        record = {
            "@type": "Event",
            "name": "JSONLD",
            "startDate": "2026-03-08T18:00:00+01:00",
            "endDate": "2026-03-08T20:00:00+01:00",
        }
        normalized = pipeline.normalize_record(record, "jsonld_20307012_generated.json", cfg)
        self.assertEqual(normalized["time"], "18:00-20:00")
        self.assertEqual(normalized["start_time"], "18:00")
        self.assertEqual(normalized["end_time"], "20:00")

    def test_env_overrides_for_formats_and_csv_options(self) -> None:
        base = pipeline.deep_merge_dict(pipeline.DEFAULT_CONFIG, {})
        with patch.dict(
            os.environ,
            {
                "PROCESS_EXPORT_FORMATS": "xml,csv",
                "PROCESS_CSV_DELIMITER": r"\t",
                "PROCESS_LINE_ENDING": r"\r\n",
                "PROCESS_ROWS_PER_FILE": "25",
            },
            clear=False,
        ):
            updated = pipeline.apply_env_overrides(base)

        self.assertEqual(updated["export"]["formats"], ["xml", "csv"])
        self.assertEqual(updated["export"]["csv"]["delimiter"], "\t")
        self.assertEqual(updated["export"]["line_ending"], "\r\n")
        self.assertTrue(updated["export"]["rows_per_file"]["enabled"])
        self.assertEqual(updated["export"]["rows_per_file"]["value"], 25)

    def test_env_override_rows_per_file_enabled_false(self) -> None:
        base = pipeline.deep_merge_dict(pipeline.DEFAULT_CONFIG, {})
        with patch.dict(
            os.environ,
            {
                "PROCESS_ROWS_PER_FILE_ENABLED": "false",
                "PROCESS_ROWS_PER_FILE": "1",
            },
            clear=False,
        ):
            updated = pipeline.apply_env_overrides(base)

        self.assertFalse(updated["export"]["rows_per_file"]["enabled"])
        self.assertEqual(updated["export"]["rows_per_file"]["value"], 1)

    def test_env_override_escapechar_doublequote_mode(self) -> None:
        base = pipeline.deep_merge_dict(pipeline.DEFAULT_CONFIG, {})
        with patch.dict(
            os.environ,
            {"PROCESS_CSV_ESCAPECHAR": '""'},
            clear=False,
        ):
            updated = pipeline.apply_env_overrides(base)

        self.assertIsNone(updated["export"]["csv"]["escapechar"])
        self.assertTrue(updated["export"]["csv"]["doublequote"])

    def test_env_overrides_for_boilerplate_input_mode(self) -> None:
        base = pipeline.deep_merge_dict(pipeline.DEFAULT_CONFIG, {})
        with patch.dict(
            os.environ,
            {
                "PROCESS_INPUT_MODE": "boilerplate",
                "PROCESS_BOILERPLATE_DIR": "output/boilerplate/runtime-snapshots",
                "PROCESS_BOILERPLATE_FILES": "a.json,b.json",
                "PROCESS_SCHEMA_SOURCE_BOILERPLATES_ENABLED": "false",
                "PROCESS_SCHEMA_SOURCE_BOILERPLATES_DIR": "output/boilerplate/schema-boilerplates/custom-source",
            },
            clear=False,
        ):
            updated = pipeline.apply_env_overrides(base)

        self.assertEqual(updated["input"]["mode"], "boilerplate")
        self.assertEqual(updated["input"]["boilerplate_dir"], "output/boilerplate/runtime-snapshots")
        self.assertEqual(updated["input"]["boilerplate_files"], ["a.json", "b.json"])
        self.assertFalse(updated["schema"]["source_boilerplates"]["enabled"])
        self.assertEqual(
            updated["schema"]["source_boilerplates"]["dir"],
            "output/boilerplate/schema-boilerplates/custom-source",
        )

    def test_run_pipeline_creates_boilerplate_and_split_exports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            in_dir = root / "in"
            out_dir = root / "out"
            in_dir.mkdir(parents=True, exist_ok=True)

            load_data_path = in_dir / "loadData_20307012.json"
            jsonld_path = in_dir / "jsonld_20307012_generated.json"

            load_data_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "1",
                            "titel": " Test <b>Event</b> ",
                            "von": "18.02.2026",
                            "zeit": "19:30-21:00",
                            "beschreibung": "Line1\nLine2 &amp; More",
                            "location": "Haus A",
                            "location_plz": "73728",
                            "location_ortsname": "Esslingen",
                            "kategorie": [{"id": "908106", "name": "Bühne · Theater"}],
                            "sammel": ["Frauenwochen"],
                            "link_url": "https://example.org/1",
                        },
                        {
                            "id": "2",
                            "titel": "Zweites Event",
                            "von": "19.02.2026",
                            "beschreibung": "Mehr Text",
                            "location": "Haus B",
                            "link_url": "https://example.org/2",
                        },
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            jsonld_path.write_text(
                json.dumps(
                    [
                        {
                            "@type": "Event",
                            "name": "JSONLD Event",
                            "startDate": "2026-02-20",
                            "endDate": "2026-02-21",
                            "description": "Desc &amp; Stuff",
                            "url": "https://example.org/j",
                            "location": {
                                "name": "Ort JSONLD",
                                "address": {"postalCode": "73728", "addressLocality": "Esslingen"},
                            },
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            cfg = pipeline.deep_merge_dict(
                pipeline.DEFAULT_CONFIG,
                {
                    "input": {"files": [str(load_data_path), str(jsonld_path)]},
                    "export": {
                        "output_dir": str(out_dir),
                        "rows_per_file": {"enabled": True, "value": 1},
                        "formats": ["csv", "xml"],
                        "filename_template": "{source}_{format}{_part{part}}.{ext}",
                    },
                },
            )
            pipeline.normalize_csv_options(cfg)
            written = pipeline.run_pipeline(cfg, timestamp="20260218_120000")

            self.assertEqual(len(written["boilerplate"]), 2)
            self.assertEqual(len(written["schema_boilerplate"]), 1)
            self.assertEqual(len(written["source_schema_boilerplate"]), 2)
            self.assertGreaterEqual(len(written["csv"]), 3)
            self.assertGreaterEqual(len(written["xml"]), 3)

            boilerplate_file = out_dir / "boilerplate" / "runtime-snapshots" / "boilerplate_loadData_20307012.json"
            self.assertTrue(boilerplate_file.exists())
            payload = json.loads(boilerplate_file.read_text(encoding="utf-8"))
            self.assertEqual(payload["record_count"], 2)
            self.assertEqual(payload["records"][0]["title"], "Test Event")
            self.assertEqual(payload["records"][0]["description"], "Line1 Line2 & More")
            self.assertEqual(payload["records"][0]["start_date"], "2026-02-18")
            self.assertEqual(payload["records"][0]["time"], "19:30-21:00")
            self.assertEqual(payload["records"][0]["start_time"], "19:30")
            self.assertEqual(payload["records"][0]["end_time"], "21:00")

            csv_file = out_dir / "loadData_20307012_csv_part1.csv"
            self.assertTrue(csv_file.exists())
            csv_text = csv_file.read_text(encoding="utf-8")
            self.assertIn("Titel", csv_text)
            self.assertIn("Test Event", csv_text)
            self.assertIn("Startzeit", csv_text)
            self.assertIn("Endzeit", csv_text)

            xml_file = out_dir / "jsonld_20307012_generated_xml_part1.xml"
            self.assertTrue(xml_file.exists())
            xml_text = xml_file.read_text(encoding="utf-8")
            self.assertIn("<events>", xml_text)
            self.assertIn("<Titel>JSONLD Event</Titel>", xml_text)

            jsonld_boilerplate_file = (
                out_dir / "boilerplate" / "runtime-snapshots" / "boilerplate_jsonld_20307012_generated.json"
            )
            self.assertTrue(jsonld_boilerplate_file.exists())
            jsonld_payload = json.loads(jsonld_boilerplate_file.read_text(encoding="utf-8"))
            self.assertEqual(jsonld_payload["records"][0]["time"], "")
            self.assertEqual(jsonld_payload["records"][0]["start_time"], "")
            self.assertEqual(jsonld_payload["records"][0]["end_time"], "")

            source_schema_file = out_dir / "boilerplate" / "schema-boilerplates" / "source_loadData_20307012.json"
            self.assertTrue(source_schema_file.exists())
            source_schema_payload = json.loads(source_schema_file.read_text(encoding="utf-8"))
            field_names = [item["name"] for item in source_schema_payload["fields"]]
            self.assertIn("id", field_names)
            self.assertIn("titel", field_names)

    def test_run_pipeline_without_split_ignores_rows_value_and_omits_part_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            in_dir = root / "in"
            out_dir = root / "out"
            in_dir.mkdir(parents=True, exist_ok=True)

            load_data_path = in_dir / "loadData_20307012.json"
            load_data_path.write_text(
                json.dumps(
                    [
                        {"id": "1", "titel": "Event 1", "von": "18.02.2026"},
                        {"id": "2", "titel": "Event 2", "von": "19.02.2026"},
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            cfg = pipeline.deep_merge_dict(
                pipeline.DEFAULT_CONFIG,
                {
                    "input": {"files": [str(load_data_path)]},
                    "export": {
                        "output_dir": str(out_dir),
                        "formats": ["csv"],
                        "rows_per_file": {"enabled": False, "value": 1},
                        "filename_template": "{source}_{format}_{timestamp}{_part{part}}.{ext}",
                    },
                },
            )
            pipeline.normalize_csv_options(cfg)
            written = pipeline.run_pipeline(cfg, timestamp="20260218_130000")

            self.assertEqual(len(written["csv"]), 1)
            self.assertEqual(len(written["schema_boilerplate"]), 1)
            self.assertEqual(len(written["source_schema_boilerplate"]), 1)
            expected = out_dir / "loadData_20307012_csv_20260218_130000.csv"
            self.assertTrue(expected.exists())
            self.assertNotIn("_part", expected.name)
            csv_text = expected.read_text(encoding="utf-8")
            self.assertIn("Event 1", csv_text)
            self.assertIn("Event 2", csv_text)

    def test_run_pipeline_from_boilerplate_exports_without_rewriting_boilerplate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            out_dir = root / "out"
            boiler_dir = root / "boilerplate"
            boiler_dir.mkdir(parents=True, exist_ok=True)

            boiler_file = boiler_dir / "boilerplate_loadData_20307012.json"
            boiler_file.write_text(
                json.dumps(
                    {
                        "source": "loadData_20307012",
                        "generated_at": "2026-02-18T12:00:00",
                        "record_count": 1,
                        "records": [
                            {
                                "id": "1",
                                "title": "Bereinigt",
                                "start_date": "2026-02-18",
                                "end_date": "2026-02-18",
                                "time": "19:30",
                                "description": "A & B",
                                "location_name": "Ort A",
                                "location_postal_code": "73728",
                                "location_city": "Esslingen",
                                "category": "Bühne Theater",
                                "series": "Frauenwochen",
                                "url": "https://example.org/1",
                                "source_type": "loadData",
                                "source_file": "loadData_20307012.json",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            cfg = pipeline.deep_merge_dict(
                pipeline.DEFAULT_CONFIG,
                {
                    "input": {
                        "mode": "boilerplate",
                        "boilerplate_dir": str(boiler_dir),
                    },
                    "export": {
                        "output_dir": str(out_dir),
                        "formats": ["csv"],
                        "rows_per_file": {"enabled": False, "value": 1000},
                        "filename_template": "{source}_{format}_{timestamp}{_part{part}}.{ext}",
                    },
                },
            )
            pipeline.normalize_csv_options(cfg)
            written = pipeline.run_pipeline(cfg, timestamp="20260218_140000")

            self.assertEqual(len(written["boilerplate"]), 0)
            self.assertEqual(len(written["schema_boilerplate"]), 1)
            self.assertEqual(len(written["source_schema_boilerplate"]), 0)
            self.assertEqual(len(written["boilerplate_input"]), 1)
            self.assertEqual(written["boilerplate_input"][0], boiler_file)
            self.assertEqual(len(written["csv"]), 1)

            expected = out_dir / "loadData_20307012_csv_20260218_140000.csv"
            self.assertTrue(expected.exists())
            csv_text = expected.read_text(encoding="utf-8")
            self.assertIn("Bereinigt", csv_text)
            self.assertIn("A & B", csv_text)
            self.assertFalse((out_dir / "boilerplate" / "runtime-snapshots").exists())
            self.assertTrue((out_dir / "boilerplate" / "schema-boilerplates" / "canonical_event_v1.json").exists())

    def test_schema_order_is_used_when_export_fields_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            in_dir = root / "in"
            out_dir = root / "out"
            in_dir.mkdir(parents=True, exist_ok=True)

            load_data_path = in_dir / "loadData_20307012.json"
            load_data_path.write_text(
                json.dumps([{"id": "1", "titel": "Event 1", "von": "18.02.2026"}], ensure_ascii=False),
                encoding="utf-8",
            )

            schema_path = out_dir / "boilerplate" / "schema-boilerplates" / "custom.json"
            schema_path.parent.mkdir(parents=True, exist_ok=True)
            schema_path.write_text(
                json.dumps(
                    {
                        "schema_id": "custom",
                        "fields": [
                            {"name": "title", "label": "TitelX"},
                            {"name": "id", "label": "IDX"},
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            cfg = pipeline.deep_merge_dict(
                pipeline.DEFAULT_CONFIG,
                {
                    "input": {"files": [str(load_data_path)]},
                    "schema": {"enabled": True, "file": str(schema_path)},
                    "export": {
                        "output_dir": str(out_dir),
                        "formats": ["csv"],
                        "rows_per_file": {"enabled": False, "value": 1000},
                        "fields": [],
                        "field_mappings": {},
                    },
                },
            )
            pipeline.normalize_csv_options(cfg)
            written = pipeline.run_pipeline(cfg, timestamp="20260218_150000")

            self.assertEqual(len(written["csv"]), 1)
            self.assertEqual(len(written["source_schema_boilerplate"]), 1)
            csv_file = out_dir / "loadData_20307012_csv_20260218_150000.csv"
            self.assertTrue(csv_file.exists())
            csv_lines = csv_file.read_text(encoding="utf-8").splitlines()
            self.assertTrue(csv_lines)
            self.assertEqual(csv_lines[0], "TitelX;IDX")


if __name__ == "__main__":
    unittest.main()
