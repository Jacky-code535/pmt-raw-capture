from __future__ import annotations

import argparse
import base64
import contextlib
import gzip
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import pmt_bulk_capture as capture


class PmtBulkCaptureTest(unittest.TestCase):
    def setUp(self) -> None:
        capture.STOP_REQUESTED = False
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.sysfs = self.root / "sysfs"
        self.output = self.root / "results"
        self.sysfs.mkdir()
        self._add_telem("telem1", "0x1234", b"\xef\xbe\xad\xde")
        self._add_telem("telem2", "0x5678", bytes(range(16)))

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _add_telem(
        self, name: str, guid: str, payload: bytes
    ) -> None:
        entry = self.sysfs / name
        entry.mkdir()
        (entry / "guid").write_text(guid + "\n", encoding="utf-8")
        (entry / "size").write_text(
            str(len(payload)) + "\n", encoding="utf-8"
        )
        (entry / "telem").write_bytes(payload)

    def _args(
        self, run_id: str, samples: int = 1
    ) -> argparse.Namespace:
        return argparse.Namespace(
            endpoint="test-host",
            run_id=run_id,
            sysfs_root=self.sysfs,
            output_root=self.output,
            metadata=None,
            expected_aggregators=2,
            interval_seconds=0.01,
            samples=samples,
            align_minute=False,
            resume=False,
        )

    def test_inventory_is_numeric_and_normalized(self) -> None:
        inventory = capture.discover_inventory(self.sysfs)
        self.assertEqual(
            [(x["AccessId"], x["Guid"], x["Size"]) for x in inventory],
            [
                ("telem1", "0x00001234", 4),
                ("telem2", "0x00005678", 16),
            ],
        )

    def test_capture_preserves_raw_poison_and_decoder_envelope(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(capture.run_capture(self._args("one")), 0)
        bulk = next((self.output / "one" / "snapshots").glob("*.json.gz"))
        with gzip.open(bulk, "rt", encoding="utf-8") as source:
            document = json.load(source)

        self.assertEqual(document["FormatVersion"], capture.FORMAT_VERSION)
        self.assertEqual(len(document["TelemetryData"]), 2)
        first = document["TelemetryData"][0]
        self.assertEqual(
            set(first),
            {
                "Guid",
                "Size",
                "CollectionTimestamp",
                "attributes",
                "Data",
            },
        )
        self.assertEqual(
            base64.b64decode(first["Data"]), b"\xef\xbe\xad\xde"
        )
        self.assertLessEqual(len(first["CollectionTimestamp"]), 10)
        self.assertEqual(first["attributes"]["AccessId"], "telem1")
        self.assertTrue(document["Capture"]["Complete"])

    def test_three_sample_run_verifies(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                capture.run_capture(self._args("three", samples=3)), 0
            )
        report = capture.verify_run(self.output / "three")
        self.assertTrue(report["AllObservedFilesValid"])
        self.assertTrue(report["RequestedSampleCountReached"])
        self.assertEqual(report["ObservedFiles"], 3)
        self.assertEqual(report["ManifestRecords"], 3)

    def test_size_mismatch_is_saved_as_incomplete(self) -> None:
        args = self._args("broken")
        run_dir, state, inventory, _ = capture.prepare_run(args)
        (self.sysfs / "telem2" / "telem").write_bytes(b"short")
        record = capture.capture_bundle(
            endpoint=args.endpoint,
            run_id=state["RunId"],
            sequence=1,
            sysfs_root=self.sysfs,
            expected_inventory=inventory,
            snapshots_dir=run_dir / "snapshots",
            manifest_path=run_dir / "manifest.ndjson",
        )
        self.assertFalse(record["Complete"])
        report = capture.verify_run(run_dir)
        self.assertFalse(report["AllObservedFilesValid"])
        self.assertEqual(report["InvalidFiles"], 1)

    def test_fatal_capture_error_marks_run_failed(self) -> None:
        args = self._args("failed")
        with mock.patch.object(
            capture, "capture_bundle", side_effect=RuntimeError("read failed")
        ):
            with self.assertRaisesRegex(RuntimeError, "read failed"):
                capture.run_capture(args)

        state = json.loads(
            (self.output / "failed" / "run.json").read_text(encoding="utf-8")
        )
        self.assertEqual(state["Status"], "failed")
        self.assertEqual(state["LastError"], "read failed")

    def test_resume_rejects_changed_interval(self) -> None:
        args = self._args("resume")
        capture.prepare_run(args)
        args.resume = True
        args.interval_seconds = 10
        with self.assertRaisesRegex(RuntimeError, "resume interval"):
            capture.prepare_run(args)

    def test_wait_stops_on_signal(self) -> None:
        with mock.patch.object(capture.time, "sleep") as sleeping:
            sleeping.side_effect = lambda _: capture.request_stop(15, None)
            capture.wait_until(capture.time.monotonic() + 600)
        sleeping.assert_called_once()


if __name__ == "__main__":
    unittest.main()
