import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pmt.capture.config import arguments


class IntegratedWorkflowTest(unittest.TestCase):
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