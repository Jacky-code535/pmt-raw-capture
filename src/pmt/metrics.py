"""Long-form offline metrics and a CSV-backed standalone Core viewer."""

import csv
import json
from pathlib import Path
import shutil

from pmt.report import iter_core_rows, load_metrics, load_topology, timestamp


def write_metrics(analysis_dir, target, metrics_path, topology_path=None):
    from pmt.pipeline import FIELDS, digest
    from pmt.core_view import generate_from_csv
    config, definitions = load_metrics(metrics_path)
    by_id = {definition["id"]: definition for definition in definitions}
    topology = load_topology(topology_path)
    inputs = [analysis_dir / "decoded.csv", analysis_dir / "analysis.json",
              analysis_dir / "provenance/run.json", Path(metrics_path)]
    if topology_path:
        inputs.append(Path(topology_path))
    before = {str(path): digest(path) for path in inputs}
    columns = FIELDS + ("core", "physical_core", "interval_start", "interval_seconds",
                        "title", "notes", "numerator", "denominator")
    count = 0
    with (target / "metrics.csv").open("x", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=columns)
        writer.writeheader()
        for row in iter_core_rows(analysis_dir, config, definitions, topology):
            definition = by_id[row["metric"]]
            writer.writerow(dict(timestamp=row["end"], endpoint=row["endpoint"],
                                 metric="C{}.{}".format(row["core"], row["metric"]),
                                 value=row["value"], unit=row["unit"], sequence=row["sequence"],
                                 aggregator=row["aggregator"], guid=row["guid"], system=row["endpoint"],
                                 socket=row["socket"], die=row["die"], module="",
                                 measure=definition["operation"], validity=row["quality"],
                                 core=row["core"], physical_core=row["physical_core"],
                                 interval_start=row["start"],
                                 interval_seconds=timestamp(row["end"]) - timestamp(row["start"]),
                                 title=definition["title"], notes=row["notes"],
                                 numerator=row["numerator"], denominator=row["denominator"]))
            count += 1
    generate_from_csv(target / "metrics.csv", target / "dashboard.html")
    provenance = target / "provenance"
    provenance.mkdir(exist_ok=True)
    shutil.copyfile(str(metrics_path), str(provenance / "metrics.json"))
    if topology_path:
        shutil.copyfile(str(topology_path), str(provenance / "core-topology.csv"))
    if before != {str(path): digest(path) for path in inputs}:
        raise ValueError("metrics inputs changed during processing")
    (provenance / "metrics-report.json").write_text(json.dumps({
        "format": "pmt-long-metrics/v1", "rows": count,
        "input_hashes": {path.name: before[str(path)] for path in inputs},
        "outputs": {name: digest(target / name) for name in ("metrics.csv", "dashboard.html")},
        "coverage": {"schema": config["schema"], "metrics_per_core": len(definitions)},
        "window": "adjacent captured samples; not Prometheus rolling extrapolation",
    }, indent=2) + "\n", encoding="utf-8")
    return count


def generate_report(analysis_dir, output, metrics_path, topology_path=None):
    from pmt.pipeline import destination
    analysis_dir, output = Path(analysis_dir).resolve(), Path(output)
    with destination(output, analysis_dir) as target:
        count = write_metrics(analysis_dir, target, metrics_path, topology_path)
    return {"output": str(output), "metric_rows": count,
            "metrics": str(output / "metrics.csv"), "core_view": str(output / "dashboard.html")}