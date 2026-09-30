import csv
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pmt.capture.config import arguments
from pmt import cli


class IntegratedWorkflowTest(unittest.TestCase):
    def test_analyze_report_handoff(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            analysis = root / "analysis"
            with patch("pmt_postprocess.analyze_run", return_value={"output": str(analysis), "decoded_rows": 1}) as decode:
                with patch("pmt.report.generate_report", return_value={"output": str(root / "analysis-report")}) as report:
                    with patch("builtins.print") as output:
                        self.assertEqual(cli.main(["analyze", "--run-dir", str(root), "--metadata", str(root / "pmt.xml"),
                                                   "--output", str(analysis), "--report"]), 0)
            self.assertTrue(decode.called)
            report.assert_called_once_with(analysis, root / "analysis-report",
                                           Path(__file__).resolve().parents[1] / "config/metrics-gnr.json", None)
            self.assertEqual(json.loads(output.call_args[0][0])["report"]["core_view"],
                             str(root / "analysis-report/逐Core看板.html"))

    def test_capture_pack_unpack_native_analysis_compare(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            device = root / "sysfs/telem1"
            device.mkdir(parents=True)
            (device / "guid").write_text("0x1234\n")
            (device / "size").write_text("8\n")
            (device / "telem").write_bytes((250 << 8).to_bytes(8, "little"))
            config = root / "capture.json"
            config.write_text(json.dumps({"endpoint": "fixture", "run_id": "complete", "sysfs_root": "sysfs",
                                          "output_root": "runs", "samples": 1, "interval_seconds": 0.001}))

            def run(*args):
                result = subprocess.run([str(ROOT / "pmt-capture")] + list(args), cwd=str(root),
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                return result.stdout

            run("start", "--config", str(config), "--samples", "3")
            run_dir = root / "runs/complete"
            run("pack", "--run-dir", str(run_dir), "--output", str(root / "packed"))
            unpacked = json.loads(run("unpack", str(next((root / "packed").glob("*.tar.gz"))),
                                      "--output", str(root / "unpacked")))
            metadata = ROOT / "tests/fixtures/synthetic_raw/pmt.xml"
            validated = json.loads(run("validate-platform", "--run-dir", unpacked["run_dir"], "--metadata", str(metadata)))
            self.assertTrue(validated["valid"])
            output = root / "analysis"
            run("analyze", "--run-dir", unpacked["run_dir"], "--metadata", str(metadata), "--output", str(output))
            if importlib.util.find_spec("xlsxwriter"):
                metric_config = root / "metrics.json"
                metric_config.write_text(json.dumps({
                    "format": "pmt-metrics/v1", "schema": {"guid": "0x1234", "size": 8},
                    "cores": 1, "max_gap_factor": 1.5, "guards": {},
                    "metrics": [{"id": "elapsed", "title": "Elapsed", "unit": "time", "operation": "gauge",
                                 "spatial": "max", "source": "clock.elapsed", "formula": "decoded elapsed"}],
                    "charts": [{"metric": "elapsed", "title": "Elapsed", "unit": "time", "type": "line"}],
                }))
                report_command = [sys.executable, str(ROOT / "src/pmt/cli.py"), "analyze",
                                  "--run-dir", unpacked["run_dir"], "--metadata", str(metadata),
                                  "--output", str(root / "analysis-with-report"), "--report",
                                  "--report-metrics", str(metric_config)]
                completed = subprocess.run(report_command, cwd=str(root), stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE, text=True)
                self.assertEqual(completed.returncode, 0, completed.stderr)
                report_result = json.loads(completed.stdout)
                report_dir = root / "analysis-with-report-report"
                self.assertEqual(report_result["report"]["core_view"], str(report_dir / "逐Core看板.html"))
                self.assertTrue((report_dir / "逐Core看板.html").is_file())
                self.assertTrue((report_dir / "pmt-report.xlsx").is_file())
                with (report_dir / "core-metrics.csv").open() as source:
                    self.assertEqual(len(list(csv.DictReader(source))), 3)
            provenance = json.loads((output / "analysis.json").read_text())
            self.assertEqual(provenance["decoder_kind"], "builtin-python")
            self.assertEqual(len(provenance["decoder_sha256"]), 64)
            expected = json.loads((ROOT / "tests/fixtures/expected_output/summary.json").read_text())
            with (output / "summary.csv").open() as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 1)
            for name, value in expected.items():
                self.assertEqual(rows[0][name] if isinstance(value, str) else float(rows[0][name]), value)
            run("compare", "--baseline", str(output), "--candidate", str(output), "--output", str(root / "diff.csv"))
            with (root / "diff.csv").open() as stream:
                self.assertEqual(float(next(csv.DictReader(stream))["difference"]), 0)
            run("archive", "--run-dir", unpacked["run_dir"], "--output", str(root / "raw-export"))
            self.assertEqual((root / "raw-export/raw/sample-000001/telem1.bin").read_bytes(), (device / "telem").read_bytes())

    def test_config_rejects_unknown_keys_and_wrong_types(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            for settings in ({"shell": "true"}, {"samples": True}, {"background": "false"}, []):
                path.write_text(json.dumps(settings))
                with self.assertRaises(ValueError):
                    arguments(path)