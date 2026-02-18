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
        self.assertEqual(updated["export"]["rows_per_file"], 25)

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
                            "zeit": "19:30",
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
                        "rows_per_file": 1,
                        "formats": ["csv", "xml"],
                        "filename_template": "{source}_{format}_part{part}.{ext}",
                    },
                },
            )
            pipeline.normalize_csv_options(cfg)
            written = pipeline.run_pipeline(cfg, timestamp="20260218_120000")

            self.assertEqual(len(written["boilerplate"]), 2)
            self.assertGreaterEqual(len(written["csv"]), 3)
            self.assertGreaterEqual(len(written["xml"]), 3)

            boilerplate_file = out_dir / "boilerplate" / "boilerplate_loadData_20307012.json"
            self.assertTrue(boilerplate_file.exists())
            payload = json.loads(boilerplate_file.read_text(encoding="utf-8"))
            self.assertEqual(payload["record_count"], 2)
            self.assertEqual(payload["records"][0]["title"], "Test Event")
            self.assertEqual(payload["records"][0]["description"], "Line1 Line2 & More")

            csv_file = out_dir / "loadData_20307012_csv_part1.csv"
            self.assertTrue(csv_file.exists())
            csv_text = csv_file.read_text(encoding="utf-8")
            self.assertIn("Titel", csv_text)
            self.assertIn("Test Event", csv_text)

            xml_file = out_dir / "jsonld_20307012_generated_xml_part1.xml"
            self.assertTrue(xml_file.exists())
            xml_text = xml_file.read_text(encoding="utf-8")
            self.assertIn("<events>", xml_text)
            self.assertIn("<Titel>JSONLD Event</Titel>", xml_text)


if __name__ == "__main__":
    unittest.main()
