import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import pmt_analysis as analysis


class AnalysisTest(unittest.TestCase):
    def row(self, value, sequence, second, aggregator="telem1"):
        return {"timestamp": "2026-09-10T00:00:%02dZ" % second,
                "sequence": sequence, "endpoint": "host", "aggregator": aggregator,
                "guid": "0x1", "metric": "ticks", "unit": "count", "value": value}

    def test_statistics(self):
        result = analysis.summarize([1, 2, 3, None, float("nan")])
        self.assertEqual(result["valid_count"], 3)
        self.assertEqual(result["mean"], 2)
        self.assertAlmostEqual(result["p95"], 2.9)
        self.assertAlmostEqual(result["std"], math.sqrt(2 / 3))
        self.assertIsNone(analysis.summarize([0, 0])["cv"])
        self.assertEqual(analysis.summarize([])["valid_count"], 0)

    def test_counter_precision_reset_missing_and_wrap(self):
        processor = analysis.Reconstructor({"ticks": {"kind": "counter", "bits": 64}})
        self.assertEqual(processor.add(self.row(2**63, 1, 1))[1]["validity"], "first_sample")
        self.assertEqual(processor.add(self.row(2**63 + 3, 2, 3))[2]["value"], 1.5)
        self.assertEqual(processor.add(self.row(1, 3, 4))[1]["validity"], "reset_or_wrap")
        self.assertEqual(processor.add(self.row(2, 5, 5))[1]["validity"], "missing_sample")
        self.assertEqual(processor.add(self.row(3, 6, 5))[1]["validity"], "non_increasing_time")
        self.assertEqual(processor.add(self.row(7, 7, 6, "telem2"))[1]["validity"], "first_sample")
        processor = analysis.Reconstructor({"ticks": {"kind": "counter", "bits": 8, "allow_wrap": True}})
        processor.add(self.row(254, 1, 1))
        self.assertEqual(processor.add(self.row(2, 2, 2))[1]["value"], 4)

    def test_invalid_breaks_counter_chain(self):
        invalid = analysis.Reconstructor({}).add(dict(self.row(3735928559, 1, 1), known_invalid=True))[0]
        self.assertEqual(invalid["validity"], "invalid_marker")
        self.assertIsNone(invalid["value"])
        processor = analysis.Reconstructor({"ticks": {"kind": "counter", "bits": 8, "invalid_values": [255]}})
        processor.add(self.row(1, 1, 1))
        self.assertIsNone(processor.add(self.row(255, 2, 2))[0]["value"])
        self.assertEqual(processor.add(self.row(3, 3, 3))[1]["validity"], "first_sample")

    def test_events_use_timezone_and_half_open_windows(self):
        events = analysis.load_events([{"start": "2026-09-10T08:00:01+08:00",
                                       "end": "2026-09-10T08:00:03+08:00",
                                       "phase": "stress", "test_item": "synthetic",
                                       "failure_time": "2026-09-10T00:00:02Z"}])
        self.assertEqual(analysis.align_events(self.row(1, 1, 1), events)[0]["phase"], "stress")
        self.assertEqual(analysis.align_events(self.row(1, 2, 3), events), [])
        self.assertEqual(analysis.failure_windows(self.row(1, 2, 3), events, 1, 1)[0]["relative_seconds"], 1)
        self.assertEqual(analysis.failure_windows(self.row(1, 2, 4), events, 1, 1), [])
        with self.assertRaises(ValueError):
            analysis.timestamp_seconds("2026-09-10T00:00:00")