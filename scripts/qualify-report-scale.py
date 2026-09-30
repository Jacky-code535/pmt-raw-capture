"""Generate synthetic decoded CORE observations to exercise full-size reports."""

import argparse
import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pmt.report import generate_report, load_metrics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=600)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    if args.samples < 2:
        parser.error("at least two samples required")
    source = args.output_root / "analysis"
    source.mkdir(parents=True, exist_ok=False)
    (source / "provenance").mkdir()
    metrics_path = ROOT / "config/metrics-gnr.json"
    config, definitions = load_metrics(metrics_path)
    inventory = [dict(AccessId="telem" + str(index), Guid=config["schema"]["guid"],
                      Size=config["schema"]["size"]) for index in range(1, 7)]
    (source / "provenance/run.json").write_text(json.dumps({
        "Endpoint": "synthetic", "IntervalSeconds": 60, "Inventory": inventory,
    }))
    (source / "analysis.json").write_text("{}")
    fields = ("endpoint", "aggregator", "guid", "sequence", "timestamp", "metric", "value")
    with (source / "decoded.csv").open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for sequence in range(1, args.samples + 1):
            end = (datetime(2026, 9, 1, tzinfo=timezone.utc) + timedelta(minutes=sequence)).isoformat()
            for region in inventory:
                common = dict(endpoint="synthetic", aggregator=region["AccessId"],
                              guid=region["Guid"], sequence=sequence, timestamp=end)
                values = {config["guards"]["heartbeat"]: sequence,
                          config["guards"]["loss"]: 0}
                for core in range(config["cores"]):
                    values["C{0}_C{1}_C{2}_C{3}_TEMP.C{4}_TEMP".format(
                        core // 4 * 4, core // 4 * 4 + 1, core // 4 * 4 + 2,
                        core // 4 * 4 + 3, core)] = 40 + core % 10
                    values["C{0}_PVP_THROTTLE_64.C{0}_PVP_THROTTLE_64".format(core)] = sequence * 10 + core
                for metric, value in values.items():
                    writer.writerow(dict(common, metric=metric, value=value))
    report = generate_report(source, args.output_root / "report", metrics_path)
    expected = args.samples * len(inventory) * config["cores"] * len(definitions)
    if report["core_metric_rows"] != expected:
        raise AssertionError("expected {} Core rows, got {}".format(expected, report["core_metric_rows"]))
    print(json.dumps({"samples": args.samples, "expected_core_rows": expected,
                      "report": report}, indent=2))


if __name__ == "__main__":
    main()