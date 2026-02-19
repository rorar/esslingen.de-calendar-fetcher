import json
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from app import lint_csv
from app import process_data_pipeline as pipeline


class DummyError:
    def __init__(self, code: str, message: str, row_number: int | None = None, field_name: str | None = None) -> None:
        self.code = code
        self.message = message
        self.row_number = row_number
        self.field_name = field_name


class DummyTask:
    def __init__(self, errors: list[DummyError]) -> None:
        self.errors = errors


class DummyReport:
    def __init__(self, valid: bool, errors: list[DummyError] | None = None) -> None:
        self.valid = valid
        self.tasks = [DummyTask(errors or [])]


class TestLintCsv(unittest.TestCase):
    def test_to_resource_descriptor_sanitizes_resource_name(self) -> None:
        descriptor = lint_csv.to_resource_descriptor(
            csv_file=Path("output/LoadData 20307012.csv"),
            dialect=None,
            encoding="utf-8",
            expected_headers=None,
        )
        self.assertEqual(descriptor["name"], "loaddata_20307012")
        self.assertNotIn("dialect", descriptor)

    def test_to_resource_descriptor_keeps_strict_dialect(self) -> None:
        descriptor = lint_csv.to_resource_descriptor(
            csv_file=Path("output/data.csv"),
            dialect={"delimiter": ";", "quoteChar": '"', "escapeChar": "\\", "doubleQuote": False},
            encoding="utf-8",
            expected_headers=["ID", "Titel"],
        )
        self.assertIn("dialect", descriptor)
        self.assertEqual(descriptor["dialect"]["delimiter"], ";")
        self.assertEqual(descriptor["dialect"]["quoteChar"], '"')
        self.assertEqual(descriptor["dialect"]["escapeChar"], "\\")
        self.assertFalse(descriptor["dialect"]["doubleQuote"])
        self.assertIn("schema", descriptor)

    def test_collect_csv_files_deduplicates_and_sorts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "b.csv").write_text("a;b\n1;2\n", encoding="utf-8")
            (root / "a.csv").write_text("a;b\n1;2\n", encoding="utf-8")

            files = lint_csv.collect_csv_files(root, ["*.csv", "a.csv"], recursive=False)
            self.assertEqual([path.name for path in files], ["a.csv", "b.csv"])

    def test_resolve_expected_headers_uses_export_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_dir = Path(tmp_dir)
            cfg = pipeline.deep_merge_dict(
                pipeline.DEFAULT_CONFIG,
                {
                    "export": {
                        "output_dir": str(out_dir),
                    }
                },
            )
            headers = lint_csv.resolve_expected_headers(cfg, out_dir)
            self.assertIn("ID", headers)
            self.assertIn("Titel", headers)

    def test_lint_csv_file_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_file = Path(tmp_dir) / "ok.csv"
            csv_file.write_text("Titel;Startdatum\nA;2026-03-01\n", encoding="utf-8")

            def fake_validate(_descriptor: dict[str, object]) -> DummyReport:
                return DummyReport(valid=True)

            valid, errors = lint_csv.lint_csv_file(
                csv_file=csv_file,
                validate_func=fake_validate,
                dialect={"delimiter": ";"},
                encoding="utf-8",
                expected_headers=["Titel", "Startdatum"],
            )
            self.assertTrue(valid)
            self.assertEqual(errors, [])

    def test_lint_csv_file_failure_collects_error_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_file = Path(tmp_dir) / "bad.csv"
            csv_file.write_text("Titel;Startdatum\nA\n", encoding="utf-8")

            def fake_validate(_descriptor: dict[str, object]) -> DummyReport:
                return DummyReport(
                    valid=False,
                    errors=[DummyError(code="extra-cell", message="wrong column count", row_number=2, field_name="Titel")],
                )

            valid, errors = lint_csv.lint_csv_file(
                csv_file=csv_file,
                validate_func=fake_validate,
                dialect={"delimiter": ";"},
                encoding="utf-8",
                expected_headers=["Titel", "Startdatum"],
            )
            self.assertFalse(valid)
            self.assertTrue(any("extra-cell" in line for line in errors))
            self.assertTrue(any("row=2" in line for line in errors))

    def test_lint_csv_file_uses_fallback_dialect(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_file = Path(tmp_dir) / "maybe.csv"
            csv_file.write_text("Titel;Startdatum\nA;2026-03-01\n", encoding="utf-8")

            def fake_validate(descriptor: dict[str, object]) -> DummyReport:
                dialect = descriptor.get("dialect")
                if isinstance(dialect, dict) and dialect.get("delimiter") == ";":
                    return DummyReport(valid=True)
                return DummyReport(
                    valid=False,
                    errors=[DummyError(code="extra-cell", message="autodetect mismatch")],
                )

            valid, errors = lint_csv.lint_csv_file(
                csv_file=csv_file,
                validate_func=fake_validate,
                dialect=None,
                fallback_dialect={"delimiter": ";"},
                encoding="utf-8",
                expected_headers=None,
            )
            self.assertTrue(valid)
            self.assertEqual(errors, [])

    def test_main_returns_2_when_frictionless_missing(self) -> None:
        with patch("app.lint_csv.load_frictionless_validate", side_effect=RuntimeError("missing")):
            with patch("sys.argv", ["lint_csv.py"]):
                rc = lint_csv.main()
        self.assertEqual(rc, 2)

    def test_main_lints_csv_files_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            out_dir = root / "out"
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "events.csv").write_text("ID;Titel\n1;A\n", encoding="utf-8")

            cfg = pipeline.deep_merge_dict(
                pipeline.DEFAULT_CONFIG,
                {
                    "export": {
                        "output_dir": str(out_dir),
                        "csv": {"delimiter": ";"},
                    }
                },
            )
            cfg_path = root / "cfg.json"
            cfg_path.write_text(json.dumps(cfg), encoding="utf-8")

            def fake_validate(_descriptor: dict[str, object]) -> DummyReport:
                return DummyReport(valid=True)

            with (
                patch("app.lint_csv.load_frictionless_validate", return_value=fake_validate),
                patch("sys.argv", ["lint_csv.py", "--config", str(cfg_path)]),
            ):
                rc = lint_csv.main()
            self.assertEqual(rc, 0)

    def test_main_lints_csv_files_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            out_dir = root / "out"
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "events.csv").write_text("ID;Titel\n1\n", encoding="utf-8")

            cfg = pipeline.deep_merge_dict(
                pipeline.DEFAULT_CONFIG,
                {
                    "export": {
                        "output_dir": str(out_dir),
                        "csv": {"delimiter": ";"},
                    }
                },
            )
            cfg_path = root / "cfg.json"
            cfg_path.write_text(json.dumps(cfg), encoding="utf-8")

            def fake_validate(_descriptor: dict[str, object]) -> DummyReport:
                return DummyReport(
                    valid=False,
                    errors=[DummyError(code="missing-cell", message="not enough columns", row_number=2)],
                )

            with (
                patch("app.lint_csv.load_frictionless_validate", return_value=fake_validate),
                patch("sys.argv", ["lint_csv.py", "--config", str(cfg_path)]),
                patch("sys.stdout", new_callable=StringIO) as stdout,
            ):
                rc = lint_csv.main()

            self.assertEqual(rc, 1)
            self.assertIn("FAIL", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
