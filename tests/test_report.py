import math
from datetime import datetime, timedelta, timezone
import re
import csv
import json
import tempfile
import zipfile
import xml.etree.ElementTree as ET
import importlib.util
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pmt.report import evaluate, load_metrics, compute_rows, rollup_rows, summary_rows, load_topology, generate_report
from pmt.core_view import build_data


class MetricTest(unittest.TestCase):
    def test_integer_delta_and_real_time_rate(self):
        self.assertEqual(evaluate({"operation": "delta"}, [2**63 + 3], [2**63], 2), (3, "valid", 3, 1))
        self.assertEqual(evaluate({"operation": "rate"}, [2**63 + 3], [2**63], 2), (1.5, "valid", 3, 2))

    def test_invalid_windows_are_not_zero(self):
        definition = {"operation": "delta", "invalid_values": [3735928559]}
        for current, previous, elapsed, reason in (
            ([3], None, None, "first_sample"),
            ([2], [3], 1, "reset_or_wrap"),
            ([3], [2], 0, "non_increasing_time"),
            ([None], [2], 1, "missing_input"),
            ([math.nan], [2], 1, "missing_input"),
            ([3735928559], [2], 1, "invalid_marker"),
            ([3], [3735928559], 1, "invalid_previous"),
        ):
            result = evaluate(definition, current, previous, elapsed)
            self.assertIsNone(result[0])
            self.assertEqual(result[1], reason)

    def test_histogram_preserves_rollup_terms(self):
        mean = {"operation": "histogram_mean", "selected": [1, 2], "weights": [0, 400, 1050]}
        self.assertEqual(evaluate(mean, [10, 2, 2], [0, 0, 0], 1), (725, "valid", 2900, 4))
        share = {"operation": "histogram_share", "selected": [0]}
        self.assertEqual(evaluate(share, [8, 2], [0, 0], 1), (80, "valid", 800, 10))
        self.assertEqual(evaluate(share, [8, 2], [8, 2], 1)[1], "no_activity")

    def test_temperature_range(self):
        definition = {"operation": "gauge", "minimum": -50, "maximum": 150}
        self.assertEqual(evaluate(definition, [33])[:2], (33, "valid"))
        self.assertEqual(evaluate(definition, [200])[:2], (None, "out_of_range"))

    def test_dashboard_core_metric_families(self):
        path = Path(__file__).resolve().parents[1] / "config/metrics-gnr.json"
        unused_config, definitions = load_metrics(path)
        by_id = {definition["id"]: definition for definition in definitions}
        self.assertEqual(len(definitions), 47)
        self.assertEqual(evaluate(by_id["core_usage_delta"], [5.75], [5.25], 20)[:2], (0.5, "valid"))
        self.assertEqual(evaluate(by_id["frequency_all_mhz"], [5, 5] + [0] * 10,
                                  [0] * 12, 20)[0], 200)
        self.assertEqual(evaluate(by_id["voltage_all_mv"], [1, 1] + [0] * 10,
                                  [0] * 12, 20)[0], 465)
        self.assertEqual(evaluate(by_id["temperature_distribution.r2"], [0, 0, 4] + [0] * 9,
                                  [0] * 12, 20)[0], 100)
        self.assertEqual(by_id["core_usage_lifetime"]["source"], "C{core}_USAGE_METER.C{core}_USAGE_METER")


class ReportDataTest(unittest.TestCase):
    def test_long_metrics_and_csv_only_viewer(self):
        from pmt.metrics import generate_report as compact_report
        from pmt.core_view import build_metrics_data, generate_from_csv
        self.write_samples()
        (self.root / "analysis.json").write_text("{}")
        path = self.root / "config.json"
        path.write_text(json.dumps(dict(self.config, metrics=self.definitions)))
        output = self.root.parent / (self.root.name + "-compact")
        self.addCleanup(__import__("shutil").rmtree, output, True)
        result = compact_report(self.root, output, path)
        self.assertEqual(result["metric_rows"], 6)
        self.assertEqual([entry.name for entry in output.glob("*.csv")], ["metrics.csv"])
        self.assertFalse((output / "pmt-report.xlsx").exists())
        with (output / "metrics.csv").open() as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(rows[0]["value"], "")
        self.assertEqual(rows[2]["value"], "0.5")
        self.assertEqual(rows[2]["metric"], "C0.pvp64_rate")
        self.assertEqual(rows[2]["interval_seconds"], "2.0")
        data = build_metrics_data(output / "metrics.csv")
        self.assertEqual(data["scopes"]["host/telem1/C0"]["aggregate"]["pvp64_rate"], 0.5)
        __import__("shutil").rmtree(output / "provenance")
        generate_from_csv(output / "metrics.csv", output / "standalone.html")
        self.assertTrue((output / "standalone.html").is_file())

    def test_compact_failure_discards_output(self):
        from pmt.metrics import generate_report as compact_report
        self.write_samples((2, 1))
        (self.root / "analysis.json").write_text("{}")
        path = self.root / "config.json"
        path.write_text(json.dumps(dict(self.config, metrics=self.definitions)))
        output = self.root.parent / (self.root.name + "-failed")
        with self.assertRaises(ValueError):
            compact_report(self.root, output, path)
        self.assertFalse(output.exists())

    def test_csv_viewer_preserves_omitted_gap(self):
        from pmt.core_view import build_metrics_data
        path = self.root / "metrics.csv"
        fields = ("timestamp", "endpoint", "aggregator", "core", "sequence", "metric", "value",
                  "unit", "title", "measure", "validity", "numerator", "denominator")
        with path.open("w", newline="") as source:
            writer = csv.DictWriter(source, fields)
            writer.writeheader()
            for sequence in range(1, 606):
                writer.writerow(dict(timestamp=(datetime(2026, 1, 1, tzinfo=timezone.utc) +
                                                timedelta(seconds=sequence)).isoformat(),
                                     endpoint="host", aggregator="telem1", core=0, sequence=sequence,
                                     metric="C0.temperature_c", value="" if sequence == 2 else 40,
                                     unit="C", title="Temperature", measure="gauge",
                                     validity="missing_input" if sequence == 2 else "valid",
                                     numerator="", denominator=""))
        data = build_metrics_data(path)
        samples = data["scopes"]["host/telem1/C0"]["samples"]
        self.assertEqual(samples[1][0], 3)
        self.assertTrue(samples[1][2]["temperature_c"][2])
        self.assertEqual(samples[-1][0], 605)
        self.assertLessEqual(len(samples), 601)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "provenance").mkdir()
        state = {"Endpoint": "host", "IntervalSeconds": 2, "Inventory": [
            {"AccessId": "telem1", "Guid": "0x22473996", "Size": 14496},
            {"AccessId": "telem2", "Guid": "0x22473996", "Size": 14496}]}
        (self.root / "provenance/run.json").write_text(json.dumps(state))
        config_path = Path(__file__).resolve().parents[1] / "config/metrics-gnr.json"
        self.config, definitions = load_metrics(config_path)
        self.config["cores"] = 1
        self.definitions = [definition for definition in definitions if definition["id"] == "pvp64_rate"]

    def write_samples(self, sequences=(1, 2, 3), loss=False):
        with (self.root / "decoded.csv").open("w", newline="") as target:
            fields = ("endpoint", "aggregator", "guid", "sequence", "timestamp", "metric", "value")
            writer = csv.DictWriter(target, fieldnames=fields)
            writer.writeheader()
            for sequence in sequences:
                for aggregator, multiplier in (("telem1", 1), ("telem2", 10)):
                    for metric, value in (("C0_PVP_THROTTLE_64.C0_PVP_THROTTLE_64", 2**63 + multiplier * sequence),
                                          (self.config["guards"]["heartbeat"], sequence),
                                          (self.config["guards"]["loss"], int(loss and sequence == 2))):
                        writer.writerow(dict(endpoint="host", aggregator=aggregator, guid="0x22473996",
                                             sequence=sequence, timestamp="2026-09-18T00:00:%02dZ" % (sequence * 2),
                                             metric=metric, value=value))

    def test_identity_real_rate_and_summary(self):
        self.write_samples()
        rows = compute_rows(self.root, self.config, self.definitions)
        self.assertEqual([row["value"] for row in rows], [None, None, 0.5, 5, 0.5, 5])
        rollups = rollup_rows(rows, self.definitions, {})
        self.assertEqual([row["value"] for row in rollups], [None, 5.5, 5.5])
        summary = summary_rows(rows, self.definitions)
        self.assertEqual([row["aggregate"] for row in summary], [0.5, 5])

    def test_sequence_gap_and_hardware_loss(self):
        self.write_samples((1, 3))
        rows = compute_rows(self.root, self.config, self.definitions)
        self.assertEqual(rows[-1]["quality"], "missing_sample")
        self.assertIsNone(rows[-1]["value"])
        self.write_samples(loss=True)
        rows = compute_rows(self.root, self.config, self.definitions)
        self.assertEqual(rows[2]["quality"], "aggregator_loss_or_reset")
        self.assertIsNone(rows[2]["value"])

    def test_topology_is_explicit_and_not_double_counted(self):
        path = self.root / "topology.csv"
        path.write_text("endpoint,aggregator,core,socket,die,physical_core,enabled\nhost,telem1,0,0,0,0,true\nhost,telem2,0,0,0,0,true\n")
        with self.assertRaises(ValueError):
            load_topology(path)

    def test_rollup_histogram_recomputes_weighted_ratio(self):
        self.write_samples()
        rows = compute_rows(self.root, self.config, self.definitions)[2:4]
        rows[0].update(value=10, numerator=10, denominator=1)
        rows[1].update(value=20, numerator=180, denominator=9)
        definition = dict(self.definitions[0], spatial="ratio")
        result = rollup_rows(rows, [definition], {})
        self.assertEqual(result[0]["value"], 19)

    def test_partial_mapping_and_disabled_core(self):
        self.write_samples()
        path = self.root / "topology.csv"
        header = "endpoint,aggregator,core,socket,die,physical_core,enabled\n"
        path.write_text(header + "host,telem1,0,0,0,7,true\n")
        topology = load_topology(path)
        rows = compute_rows(self.root, self.config, self.definitions, topology)
        self.assertEqual(rows[2]["physical_core"], "7")
        rollups = rollup_rows(rows, self.definitions, topology)
        system = next(row for row in rollups if row["level"] == "system" and row["sequence"] == 2)
        socket = next(row for row in rollups if row["level"] == "socket" and row["sequence"] == 2)
        self.assertEqual(system["value"], 5.5)
        self.assertNotIn("mapped_members_only", system["notes"])
        self.assertEqual(socket["value"], 0.5)
        self.assertEqual(socket["expected_members"], 1)
        path.write_text(header + "host,telem1,0,0,0,7,true\nhost,telem2,0,1,0,8,false\n")
        topology = load_topology(path)
        rows = compute_rows(self.root, self.config, self.definitions, topology)
        self.assertEqual(rows[3]["quality"], "disabled_by_topology")
        system = next(row for row in rollup_rows(rows, self.definitions, topology)
                      if row["level"] == "system" and row["sequence"] == 2)
        self.assertEqual(system["value"], 0.5)
        self.assertEqual(system["expected_members"], 1)

    @unittest.skipUnless(importlib.util.find_spec("xlsxwriter"), "optional Excel dependency not installed")
    def test_workbook_contains_real_charts_and_missing_baselines(self):
        self.write_samples()
        config = dict(self.config, metrics=self.definitions,
                      charts=[{"metric": "pvp64_rate", "title": "PVP", "unit": "count/s", "type": "line"}])
        path = self.root / "metrics.json"
        path.write_text(json.dumps(config))
        (self.root / "analysis.json").write_text("{}")
        output = self.root.parent / (self.root.name + "-report")
        self.addCleanup(__import__("shutil").rmtree, output, True)
        result = generate_report(self.root, output, path)
        self.assertEqual(result["core_metric_rows"], 6)
        with (output / "core-metrics.csv").open() as source:
            rows = list(csv.DictReader(source))
        self.assertEqual(rows[0]["value"], "")
        self.assertEqual(rows[2]["value"], "0.5")
        with (output / "metric-quality.csv").open() as source:
            quality = list(csv.DictReader(source))
        self.assertEqual(sum(int(row["count"]) for row in quality), 9)
        self.assertEqual(sum(int(row["count"]) for row in quality
                             if row["level"] == "core" and row["quality"] == "first_sample"), 2)
        with zipfile.ZipFile(output / "pmt-report.xlsx") as archive:
            charts = [name for name in archive.namelist() if re.fullmatch(r"xl/charts/chart\d+.xml", name)]
            self.assertEqual(len(charts), 2)
            xml = ET.fromstring(archive.read(charts[0]))
            namespace = {"c": "http://schemas.openxmlformats.org/drawingml/2006/chart"}
            values = [entry.text for entry in xml.findall(".//c:val/c:numRef/c:numCache/c:pt/c:v", namespace)]
            self.assertIn("0.5", values)
            self.assertIn("5.0", values)
        page = (output / "逐Core看板.html").read_text()
        self.assertIn("host/telem1/C0", page)
        self.assertIn("host/telem2/C0", page)
        self.assertIn('id="core"', page)
        self.assertIn('core_usage_delta', page)
        self.assertFalse((output / "socket-metrics.csv").exists())
        with self.assertRaises(FileExistsError):
            generate_report(self.root, output, path)

    @unittest.skipUnless(importlib.util.find_spec("xlsxwriter"), "optional Excel dependency not installed")
    def test_report_exceeds_old_core_row_limit(self):
        self.config["cores"] = 64
        unused, definitions = load_metrics(Path(__file__).resolve().parents[1] / "config/metrics-gnr.json")
        config = dict(self.config, charts=[], metrics=unused["metrics"])
        path = self.root / "metrics.json"
        path.write_text(json.dumps(config))
        (self.root / "analysis.json").write_text("{}")
        with (self.root / "decoded.csv").open("w", newline="") as target:
            writer = csv.DictWriter(target, fieldnames=("endpoint", "aggregator", "guid", "sequence", "timestamp", "metric", "value"))
            writer.writeheader()
            for sequence in range(1, 85):
                end = (datetime(2026, 9, 18, tzinfo=timezone.utc) + timedelta(seconds=2 * sequence)).isoformat()
                for aggregator in ("telem1", "telem2"):
                    for metric, value in ((self.config["guards"]["heartbeat"], sequence),
                                          (self.config["guards"]["loss"], 0)):
                        writer.writerow(dict(endpoint="host", aggregator=aggregator, guid="0x22473996",
                                             sequence=sequence, timestamp=end, metric=metric, value=value))
        output = self.root.parent / (self.root.name + "-large-report")
        self.addCleanup(__import__("shutil").rmtree, output, True)
        result = generate_report(self.root, output, path)
        self.assertEqual(result["core_metric_rows"], 84 * 2 * 64 * len(definitions))
        self.assertGreater(result["core_metric_rows"], 500000)
        with (output / "core-metrics.csv").open() as source:
            self.assertEqual(sum(1 for unused in source) - 1, result["core_metric_rows"])
        with zipfile.ZipFile(output / "pmt-report.xlsx") as archive:
            self.assertIn("xl/worksheets/sheet1.xml", archive.namelist())
        self.assertIn("host/telem2/C63", (output / "逐Core看板.html").read_text())

    def test_dashboard_keeps_endpoints_and_only_key_metrics(self):
        config = dict(self.config, metrics=[definition for definition in self.config["metrics"]
                                            if definition["id"] in ("temperature_c", "pvp64_rate", "frequency_distribution")])
        (self.root / "metrics.json").write_text(json.dumps(config))
        fields = ("scope", "sequence", "end", "metric", "value", "quality")
        with (self.root / "core-metrics.csv").open("w", newline="") as target:
            writer = csv.DictWriter(target, fieldnames=fields)
            writer.writeheader()
            for sequence in range(1, 606):
                for metric in ("temperature_c", "pvp64_rate", "frequency_distribution.r0"):
                    writer.writerow(dict(scope="host/telem1/C0", sequence=sequence,
                                         end="2026-09-18T00:00:00Z", metric=metric, value=sequence, quality="valid"))
        with (self.root / "metric-summary.csv").open("w", newline="") as target:
            writer = csv.DictWriter(target, fieldnames=("level", "scope", "metric", "aggregate"))
            writer.writeheader()
            for metric in ("temperature_c", "pvp64_rate"):
                writer.writerow(dict(level="core", scope="host/telem1/C0", metric=metric, aggregate=3))
        data = build_data(self.root)
        samples = data["scopes"]["host/telem1/C0"]["samples"]
        self.assertLessEqual(len(samples), 601)
        self.assertEqual((samples[0][0], samples[-1][0]), (1, 605))
        self.assertNotIn("frequency_distribution.r0", data["definitions"])

    @unittest.skipUnless(importlib.util.find_spec("xlsxwriter"), "optional Excel dependency not installed")
    def test_large_integer_delta_summary_remains_exact(self):
        self.write_samples()
        source = self.root / "decoded.csv"
        with source.open(newline="") as stream:
            rows = list(csv.DictReader(stream))
        step = 2**54 + 1
        for row in rows:
            if row["metric"].endswith("PVP_THROTTLE_64"):
                row["value"] = str((int(row["sequence"]) - 1) * step)
        with source.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        unused_config, definitions = load_metrics(Path(__file__).resolve().parents[1] / "config/metrics-gnr.json")
        delta = next(definition for definition in definitions if definition["id"] == "pvp64_delta")
        config = dict(self.config, metrics=[delta], charts=[])
        path = self.root / "metrics.json"
        path.write_text(json.dumps(config))
        (self.root / "analysis.json").write_text("{}")
        output = self.root.parent / (self.root.name + "-exact-report")
        self.addCleanup(__import__("shutil").rmtree, output, True)
        generate_report(self.root, output, path)
        with (output / "metric-summary.csv").open() as stream:
            summaries = list(csv.DictReader(stream))
        core = next(row for row in summaries if row["level"] == "core")
        self.assertEqual(core["aggregate"], str(2 * step))