import contextlib
import csv
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import pmt_bulk_capture as capture
import pmt_capture_cli as cli
import pmt_postprocess as postprocess
import test_pmt_bulk_capture as fixtures


class PostprocessTest(unittest.TestCase):
    setUp = fixtures.PmtBulkCaptureTest.setUp
    tearDown = fixtures.PmtBulkCaptureTest.tearDown
    _args = fixtures.PmtBulkCaptureTest._args
    _add_telem = fixtures.PmtBulkCaptureTest._add_telem

    def test_archive_preserves_samples_and_legacy_replay(self):
        with contextlib.redirect_stdout(io.StringIO()):
            capture.run_capture(self._args("archive", samples=3))
        run_dir = self.output / "archive"
        before = {str(path): postprocess.digest(path) for path in run_dir.rglob("*") if path.is_file()}
        target = self.root / "archive-output"
        result = postprocess.archive_run(run_dir, target)
        self.assertEqual(result["raw_records"], 6)
        self.assertEqual((target / "raw/sample-000003/telem1.bin").read_bytes(), b"\xef\xbe\xad\xde")
        self.assertTrue(capture.verify_run(target / "capture/archive", False)["AllObservedFilesValid"])
        self.assertEqual(before, {str(path): postprocess.digest(path) for path in run_dir.rglob("*") if path.is_file()})
        with self.assertRaises(FileExistsError):
            postprocess.archive_run(run_dir, target)

    def test_summary_store_does_not_merge_aggregators(self):
        store = postprocess.SummaryStore(self.root / "summary.sqlite")
        try:
            for aggregator, value in (("telem1", 1), ("telem1", 3), ("telem2", 10)):
                store.add({"endpoint": "host", "aggregator": aggregator, "metric": "temp", "value": value})
            rows = list(store.rows())
            self.assertEqual([row["mean"] for row in rows], [2, 10])
            self.assertEqual([row["valid_count"] for row in rows], [2, 1])
        finally:
            store.close()

    def test_topology_does_not_infer_cores(self):
        document = {"Capture": {"Endpoint": "host", "Sequence": 1}, "TelemetryData": [
            {"Guid": "0x1234", "Size": 4, "attributes": {"AccessId": "telem1", "CapturedAt": "2026-09-10T00:00:00Z"}}]}
        decoded = [{"index": 0, "result": {"exact_guid_size_match": True, "reported_size_bytes": 4,
                    "guid": "0x1234", "metrics": [{"name": "metric0", "value": 7}]}}]
        row = list(postprocess.decoded_rows(document, decoded, {}))[0]
        self.assertEqual(row["system"], "host")
        self.assertEqual(row["socket"], "")
        self.assertNotIn("core", row)
        decoded[0]["result"]["exact_guid_size_match"] = False
        with self.assertRaises(ValueError):
            list(postprocess.decoded_rows(document, decoded, {}))

    def test_analysis_cli_events_comparison_and_provenance(self):
        with contextlib.redirect_stdout(io.StringIO()):
            capture.run_capture(self._args("analysis", samples=3))
        run_dir = self.output / "analysis"
        registry = self.root / "pmt.xml"
        mappings = []
        for guid, size in (("0x1234", 4), ("0x5678", 16)):
            mappings.append('<mapping guid="%s" size="%s"><xmlset><basedir>schema</basedir>'
                            '<common>test.xml</common><aggregator>test.xml</aggregator>'
                            '<aggregatorinterface>test.xml</aggregatorinterface></xmlset></mapping>' % (guid, size))
        registry.write_text("<pmt><mappings>" + "".join(mappings) + "</mappings></pmt>")
        (self.root / "schema").mkdir()
        (self.root / "schema/test.xml").write_text("<synthetic/>")
        policies = self.root / "policies.json"
        policies.write_text(json.dumps({"ticks": {"kind": "counter", "bits": 64}}))
        first = capture.read_bundle(next((run_dir / "snapshots").glob("bulk-000001-*")))
        events = self.root / "events.csv"
        events.write_text("start,end,phase,test_item,status,failure_time\n"
                          "2000-01-01T00:00:00Z,2100-01-01T00:00:00Z,stress,fixture,failed," +
                          first["TelemetryData"][0]["attributes"]["CapturedAt"] + "\n")

        def decode(command, **kwargs):
            document = json.loads(kwargs["input"])
            sequence = document["Capture"]["Sequence"]
            records = [{"index": index, "result": {
                "exact_guid_size_match": True, "reported_size_bytes": item["Size"], "guid": item["Guid"],
                "metrics": [{"name": "ticks", "value": 2**63 + sequence, "unit": "count",
                             "known_invalid": index == 1 and sequence == 1}],
            }} for index, item in enumerate(document["TelemetryData"])]
            return subprocess.CompletedProcess(command, 0, json.dumps(records), "")

        output = self.root / "analysis-output"
        command = ["analyze", "--run-dir", str(run_dir), "--metadata", str(registry),
                   "--decoder", sys.executable, "--output", str(output),
                   "--events", str(events), "--policies", str(policies)]
        with mock.patch.object(postprocess.subprocess, "run", side_effect=decode), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(command), 0)
        with (output / "summary.csv").open() as source:
            rows = list(csv.DictReader(source))
        values = [row for row in rows if row["measure"] == "value"]
        self.assertEqual([row["valid_count"] for row in values], ["3", "2"])
        with (output / "failure-windows.csv").open() as source:
            self.assertEqual(len(list(csv.DictReader(source))), 18)
        for name in ("decoded.csv", "series.csv", "aligned.csv", "phase-summary.csv", "view-die.csv"):
            self.assertTrue((output / name).is_file())
        self.assertTrue((output / "provenance/xml/schema/test.xml").is_file())
        comparison = self.root / "comparison.csv"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["compare", "--baseline", str(output), "--candidate", str(output),
                                      "--output", str(comparison), "--by-test"]), 0)
        with comparison.open() as source:
            self.assertTrue(all(float(row["difference"]) == 0 for row in csv.DictReader(source)))
        registry.write_text("<pmt><mappings/></pmt>")
        output_index = command.index("--output") + 1
        command[output_index] = str(self.root / "failed-output")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cli.main(command), 1)
        self.assertFalse((self.root / "failed-output").exists())