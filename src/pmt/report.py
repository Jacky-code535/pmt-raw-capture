"""Configuration-driven offline metrics and Excel reporting."""

import csv
import itertools
import json
import math
import re
import sqlite3
from collections import Counter
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import shutil
from datetime import timezone

from pmt.process.statistics import summarize


FIELDS = ("level", "endpoint", "scope", "aggregator", "guid", "core", "socket", "die", "physical_core",
          "sequence", "start", "end", "metric", "value", "unit", "quality", "notes",
          "numerator", "denominator", "valid_members", "expected_members", "skew_seconds")
OPERATIONS = {"gauge", "delta", "rate", "histogram_share", "histogram_mean", "histogram_distribution"}


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamps must include a timezone")
    return parsed.timestamp()


def number(value):
    if value == "":
        return None
    return int(value) if re.fullmatch(r"[-+]?\d+", value) else float(value)


def load_metrics(path):
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    if config.get("format") != "pmt-metrics/v1":
        raise ValueError("expected pmt-metrics/v1")
    int(config["schema"]["guid"], 16)
    if config["schema"]["size"] <= 0 or not 1 <= config["cores"] <= 256:
        raise ValueError("invalid schema size or core count")
    gap = config["max_gap_factor"]
    if not math.isfinite(gap) or gap < 1:
        raise ValueError("max_gap_factor must be finite and >= 1")
    definitions = []
    for definition in config["metrics"]:
        operation = definition["operation"]
        if operation not in OPERATIONS:
            raise ValueError("unsupported metric operation: " + operation)
        if definition["spatial"] not in ("max", "sum", "ratio"):
            raise ValueError("unsupported spatial aggregation")
        if operation.startswith("histogram"):
            count = definition["buckets"]
            if not isinstance(count, int) or not 1 <= count <= 64:
                raise ValueError("invalid histogram bucket count")
            if operation != "histogram_distribution":
                selected = definition["selected"]
                if not selected or len(set(selected)) != len(selected) or any(not isinstance(index, int) or not 0 <= index < count for index in selected):
                    raise ValueError("invalid selected buckets")
            if operation == "histogram_mean" and (len(definition["weights"]) != count or any(not math.isfinite(weight) for weight in definition["weights"])):
                raise ValueError("invalid histogram weights")
            if operation == "histogram_distribution":
                if len(definition["labels"]) != count:
                    raise ValueError("histogram labels must match bucket count")
                for index in range(count):
                    expanded = dict(definition, operation="histogram_share", selected=[index],
                                    id=definition["id"] + ".r" + str(index),
                                    title=definition["title"] + ": " + definition["labels"][index])
                    definitions.append(expanded)
                continue
        definitions.append(definition)
    ids = [definition["id"] for definition in definitions]
    if not ids or len(set(ids)) != len(ids):
        raise ValueError("metric IDs must be nonempty and unique")
    for definition in definitions:
        if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_.]*", definition["id"]):
            raise ValueError("invalid metric ID")
        for field in ("title", "unit", "formula", "source"):
            if not isinstance(definition[field], str):
                raise ValueError("metric text field must be a string: " + field)
        if definition["operation"].startswith("histogram") and definition["spatial"] != "ratio":
            raise ValueError("histograms require ratio spatial aggregation")
        source_names(definition, 0)
    return config, definitions


def source_names(definition, core):
    names = []
    for bucket in range(definition.get("buckets", 1)):
        labels = {"core": core, "bucket": bucket, "pair": bucket // 2 * 2,
                  "pair_next": bucket // 2 * 2 + 1}
        labels.update({"quad" + str(index): core // 4 * 4 + index for index in range(4)})
        names.append(definition["source"].format(**labels))
    return names


def load_topology(path):
    mapping = {}
    physical = set()
    if path is None:
        return mapping
    with Path(path).open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        required = {"endpoint", "aggregator", "core", "socket", "die", "physical_core", "enabled"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("core topology requires: " + ", ".join(sorted(required)))
        for row in reader:
            key = (row["endpoint"], row["aggregator"], int(row["core"]))
            if key in mapping or row["enabled"] not in ("true", "false"):
                raise ValueError("duplicate topology identity or invalid enabled flag")
            if any(not row[name] for name in ("endpoint", "aggregator", "socket", "die", "physical_core")):
                raise ValueError("topology must contain confirmed physical identities")
            identity = tuple(row[name] for name in ("endpoint", "socket", "die", "physical_core"))
            if row["enabled"] == "true" and identity in physical:
                raise ValueError("multiple PMT cores map to the same physical core")
            if row["enabled"] == "true":
                physical.add(identity)
            mapping[key] = row
    return mapping


def compute_rows(analysis_dir, config, definitions, topology=None):
    return list(iter_core_rows(analysis_dir, config, definitions, topology))


def iter_core_rows(analysis_dir, config, definitions, topology=None):
    analysis_dir = Path(analysis_dir)
    topology = topology or {}
    state = json.loads((analysis_dir / "provenance/run.json").read_text(encoding="utf-8"))
    guid = config["schema"]["guid"].lower()
    matching = {entry["AccessId"] for entry in state["Inventory"]
                if int(entry["Guid"], 16) == int(guid, 16) and entry["Size"] == config["schema"]["size"]}
    if not matching:
        raise ValueError("no exact GUID/Size match for metrics configuration")
    endpoint = state["Endpoint"]
    interval = float(state["IntervalSeconds"])
    if not math.isfinite(interval) or interval <= 0:
        raise ValueError("run interval must be positive and finite")
    names = {(core, definition["id"]): source_names(definition, core)
             for core in range(config["cores"]) for definition in definitions}
    required = set(itertools.chain.from_iterable(names.values())) | set(config["guards"].values())
    for key in topology:
        if key[0] != endpoint or key[1] not in matching or not 0 <= key[2] < config["cores"]:
            raise ValueError("topology references a core outside the selected schema")
    previous = {}
    last_sequence = 0
    with (analysis_dir / "decoded.csv").open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        columns = {"endpoint", "aggregator", "guid", "sequence", "timestamp", "metric", "value"}
        if not columns.issubset(reader.fieldnames or []):
            raise ValueError("decoded CSV is missing required columns")
        def selected():
            for row in reader:
                if row["aggregator"] in matching and int(row["guid"], 16) == int(guid, 16):
                    if row["endpoint"] != endpoint:
                        raise ValueError("decoded endpoint differs from run provenance")
                    yield row

        for sequence, sequence_rows in itertools.groupby(selected(), lambda row: int(row["sequence"])):
            if sequence <= last_sequence:
                raise ValueError("decoded snapshots must be ordered by increasing sequence")
            last_sequence = sequence
            frames = {}
            for row in sequence_rows:
                aggregator = row["aggregator"]
                frame = frames.setdefault(aggregator, {"timestamp": row["timestamp"], "values": {}})
                if frame["timestamp"] != row["timestamp"]:
                    raise ValueError("inconsistent timestamp within aggregator snapshot")
                if row["metric"] in required:
                    if row["metric"] in frame["values"]:
                        raise ValueError("duplicate metric in decoded snapshot")
                    frame["values"][row["metric"]] = number(row["value"])
            yield from core_sequence_rows(sequence, frames, previous, matching, endpoint, guid,
                                          interval, config, definitions, names, topology)
    if not last_sequence:
        raise ValueError("no matching decoded snapshots")


def core_sequence_rows(sequence, frames, previous, matching, endpoint, guid,
                       interval, config, definitions, names, topology):
    earliest = min((frame["timestamp"] for frame in frames.values()), key=timestamp)
    for aggregator in sorted(matching):
            frame = frames.get(aggregator)
            before = previous.get(aggregator)
            end = frame["timestamp"] if frame else earliest
            values = frame["values"] if frame else {}
            start = before["timestamp"] if before else end
            elapsed = timestamp(end) - timestamp(start)
            continuity = ""
            if frame is None:
                continuity = "missing_snapshot"
            elif before:
                if sequence != before["sequence"] + 1:
                    continuity = "missing_sample"
                elif elapsed <= 0:
                    continuity = "non_increasing_time"
                elif elapsed > interval * config["max_gap_factor"]:
                    continuity = "long_gap"
                else:
                    for guard, field in config["guards"].items():
                        current_guard = values.get(field)
                        previous_guard = before["values"].get(field)
                        if current_guard is None or previous_guard is None or not math.isfinite(current_guard) or not math.isfinite(previous_guard):
                            continuity = "missing_guard"
                            break
                        if guard == "heartbeat" and current_guard <= previous_guard:
                            continuity = "stale_or_reset"
                            break
                        if guard == "loss" and current_guard != previous_guard:
                            continuity = "aggregator_loss_or_reset"
                            break
            for core in range(config["cores"]):
                location = topology.get((endpoint, aggregator, core), {})
                notes = [] if location else ["physical_topology_unmapped", "enabled_state_unknown"]
                for definition in definitions:
                    fields = names[(core, definition["id"])]
                    current = [values.get(name) for name in fields]
                    prior = [before["values"].get(name) for name in fields] if before else None
                    value, quality, numerator, denominator = evaluate(definition, current, prior, elapsed)
                    if continuity:
                        value, quality, numerator, denominator = None, continuity, None, None
                    if location.get("enabled") == "false":
                        value, quality, numerator, denominator = None, "disabled_by_topology", None, None
                    if definition.get("provisional") and value is not None:
                        quality = "provisional"
                    metric_notes = list(notes)
                    if definition.get("provisional"):
                        metric_notes.append(definition["provisional"])
                    if definition["operation"] == "gauge" and not before:
                        metric_notes.append("freshness_unchecked_first_sample")
                    yield dict(level="core", endpoint=endpoint,
                                     scope=endpoint + "/" + aggregator + "/C" + str(core),
                                     aggregator=aggregator, guid=guid, core=core,
                                     socket=location.get("socket", ""), die=location.get("die", ""),
                                     physical_core=location.get("physical_core", ""),
                                     sequence=sequence, start=end if definition["operation"] == "gauge" else start,
                                     end=end, metric=definition["id"], value=value, unit=definition["unit"],
                                     quality=quality, notes=";".join(metric_notes), numerator=numerator,
                                     denominator=denominator, valid_members=int(value is not None), expected_members=1,
                                     skew_seconds=0)
            if frame:
                previous[aggregator] = dict(frame, sequence=sequence)
            else:
                previous.pop(aggregator, None)


def rollup_rows(core_rows, definitions, topology):
    definitions = {definition["id"]: definition for definition in definitions}
    groups = defaultdict(list)
    for row in core_rows:
        if row["quality"] == "disabled_by_topology":
            continue
        groups[("system", row["endpoint"], row["sequence"], row["metric"])].append(row)
        if row["socket"] != "":
            groups[("socket", row["endpoint"] + "/socket" + row["socket"], row["sequence"], row["metric"])].append(row)
    rows = []
    for (level, scope, sequence, metric), members in sorted(groups.items()):
        available = [row for row in members if row["value"] is not None]
        definition = definitions[metric]
        numerator = denominator = value = None
        quality = "no_valid_members"
        if available:
            if definition["spatial"] == "ratio":
                numerator = sum(row["numerator"] for row in available)
                denominator = sum(row["denominator"] for row in available)
                value = numerator / denominator
            elif definition["spatial"] == "max":
                value = max(row["value"] for row in available)
                numerator, denominator = value, 1
            else:
                value = sum(row["value"] for row in available)
                numerator, denominator = value, 1
            quality = "partial_coverage" if len(available) != len(members) else "valid"
            if definition.get("provisional") and quality == "valid":
                quality = "provisional"
        starts = [timestamp(row["start"]) for row in members]
        ends = [timestamp(row["end"]) for row in members]
        notes = {note for row in members for note in row["notes"].split(";") if note}
        notes.add("sequential_region_observations")
        notes.add("mapped_members_only" if all(member["socket"] != "" for member in members)
              else "observed_xml_slots_not_confirmed_physical_cores")
        row = dict(members[0], level=level, scope=scope, aggregator="", core="", die="", physical_core="",
                   socket=members[0]["socket"] if level == "socket" else "",
                   start=min((member["start"] for member in members), key=timestamp),
                   end=max((member["end"] for member in members), key=timestamp),
                   value=value, numerator=numerator, denominator=denominator, quality=quality,
                   notes=";".join(sorted(notes)), valid_members=len(available), expected_members=len(members),
                   skew_seconds=max(max(starts) - min(starts), max(ends) - min(ends)))
        rows.append(row)
    return rows


def summary_rows(rows, definitions):
    definitions = {definition["id"]: definition for definition in definitions}
    groups = defaultdict(list)
    for row in rows:
        groups[(row["level"], row["scope"], row["metric"])].append(row)
    result = []
    for (level, scope, metric), members in sorted(groups.items()):
        valid = [row for row in members if row["value"] is not None]
        definition = definitions[metric]
        aggregate = None
        if valid:
            if definition["operation"].startswith("histogram"):
                aggregate = sum(row["numerator"] for row in valid) / sum(row["denominator"] for row in valid)
            elif definition["operation"] == "delta":
                aggregate = sum(row["value"] for row in valid)
            elif definition["operation"] == "rate":
                durations = [timestamp(row["end"]) - timestamp(row["start"]) for row in valid]
                aggregate = sum(row["value"] * duration for row, duration in zip(valid, durations)) / sum(durations)
            else:
                aggregate = sum(row["value"] for row in valid) / len(valid)
        result.append(dict(level=level, scope=scope, metric=metric, unit=definition["unit"],
                           aggregate=aggregate, **summarize(row["value"] for row in members),
                           excluded_count=len(members) - len(valid),
                           notes=";".join(sorted({note for row in members for note in row["notes"].split(";") if note}))))
    return result


def write_csv(path, fields, rows):
    with path.open("x", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def csv_rows(path):
    with path.open(newline="", encoding="utf-8") as source:
        yield from csv.DictReader(source)


def stored_summaries(connection, definitions, exact_deltas=None):
    by_id = {definition["id"]: definition for definition in definitions}
    connection.execute("CREATE INDEX series_values ON samples(level, scope, metric, value)")
    connection.commit()
    keys = connection.execute("SELECT level, scope, metric, COUNT(*), COUNT(value), "
                              "SUM(value), SUM(numerator), SUM(denominator), SUM(weighted), SUM(duration) "
                              "FROM samples GROUP BY level, scope, metric ORDER BY level, scope, metric")
    for level, scope, metric, count, valid_count, total, numerator, denominator, weighted, duration in keys:
        definition = by_id[metric]
        values = (row[0] for row in connection.execute(
            "SELECT value FROM samples WHERE level=? AND scope=? AND metric=? AND value IS NOT NULL ORDER BY value",
            (level, scope, metric)))
        statistics = summarize(values)
        if not valid_count:
            aggregate = None
        elif definition["operation"].startswith("histogram"):
            aggregate = numerator / denominator
        elif definition["operation"] == "delta":
            aggregate = exact_deltas.get((level, scope, metric), total) if exact_deltas is not None else total
        elif definition["operation"] == "rate":
            aggregate = weighted / duration
        else:
            aggregate = total / valid_count
        notes = {note for (text,) in connection.execute(
            "SELECT DISTINCT notes FROM samples WHERE level=? AND scope=? AND metric=?",
            (level, scope, metric)) for note in text.split(";") if note}
        yield dict(level=level, scope=scope, metric=metric, unit=definition["unit"],
                   aggregate=aggregate, **statistics, excluded_count=count - valid_count,
                   notes=";".join(sorted(notes)))


def store_row(connection, row):
    value = row["value"]
    duration = timestamp(row["end"]) - timestamp(row["start"]) if value is not None else None
    connection.execute("INSERT INTO samples VALUES (?,?,?,?,?,?,?,?,?,?)", (
        row["level"], row["scope"], row["metric"], float(value) if value is not None else None,
        float(row["numerator"]) if value is not None else None,
        float(row["denominator"]) if value is not None else None,
        value * duration if value is not None else None, duration,
        row["notes"], row["quality"]))


def excel_report(path, rows, summaries, definitions, config, provenance):
    try:
        import xlsxwriter
    except ImportError as error:
        raise RuntimeError("Excel reporting requires XlsxWriter; install requirements-report.txt on the analysis host") from error
    workbook = xlsxwriter.Workbook(str(path), {
        "constant_memory": True, "strings_to_formulas": False, "strings_to_urls": False,
        "default_date_format": "yyyy-mm-dd hh:mm:ss.000",
    })
    workbook.set_properties({"title": "GNR PMT Metrics", "comments": "Offline derived metrics; see Quality and Definitions."})
    heading = workbook.add_format({"bold": True, "font_color": "#FFFFFF", "bg_color": "#254B45", "text_wrap": True})
    title = workbook.add_format({"bold": True, "font_size": 18, "font_color": "#254B45"})
    body = workbook.add_format({"text_wrap": True, "valign": "top"})
    numeric = workbook.add_format({"num_format": "0.000"})
    colors = ["#177E89", "#D1495B", "#427A40", "#D18C25", "#665191", "#555555"]

    def write_value(sheet, row, column, value):
        if value is None:
            return
        if isinstance(value, int) and abs(value) > 2**53:
            sheet.write_string(row, column, str(value))
        elif isinstance(value, (int, float)):
            sheet.write_number(row, column, value, numeric)
        else:
            sheet.write_string(row, column, str(value))

    def table(name, fields, records):
        sheet = workbook.add_worksheet(name)
        sheet.freeze_panes(1, 2)
        sheet.set_row(0, 32)
        sheet.set_column(0, len(fields) - 1, 19)
        for column, field in enumerate(fields):
            sheet.write_string(0, column, field, heading)
            if field in ("scope", "metric", "quality", "notes", "formula", "source"):
                sheet.set_column(column, column, 42)
        count = 0
        for count, record in enumerate(records, 1):
            if count >= 1048576:
                raise ValueError("Excel worksheet row limit exceeded")
            for column, field in enumerate(fields):
                write_value(sheet, count, column, record.get(field))
        sheet.autofilter(0, 0, count, len(fields) - 1)
        return sheet

    try:
        overview = workbook.add_worksheet("Overview")
        overview.set_column(0, 0, 32)
        overview.set_column(1, 1, 110)
        overview.write(0, 0, "GNR PMT Metrics", title)
        overview.set_row(0, 30)
        entries = [
            ("Source", provenance["analysis_dir"]),
            ("Time range (UTC)", provenance["first_timestamp"] + " to " + provenance["last_timestamp"]),
            ("Metric configuration SHA256", provenance["metrics_sha256"]),
            ("Core identity", "PMT aggregator + XML-local core. Physical mapping is explicit, never inferred from telem ID."),
            ("Scope coverage", "System aggregates observed enabled/unknown XML slots; see valid_members and expected_members. Socket views require --topology."),
            ("Histogram status", "PROVISIONAL: histogram time scale is unverified. Frequency is a bucket-midpoint estimate, not an instantaneous clock reading."),
            ("Voltage", "r0 means below 602 mV, not C6. Distribution percentages do not establish instantaneous voltage."),
            ("Counters", "Delta=current-previous; rate=delta/actual seconds. First samples, gaps, declines and hardware loss are blank, not zero."),
            ("Quality", "Finite values are not a hardware-health certification. Partial rollups state contributing member counts."),
            ("Statistics", "Summary aggregate uses count sums or denominator-weighted ratios/rates; mean/p95 are statistics of valid per-window values."),
            ("Timing", "PMT regions are read sequentially; grouped sequences are not simultaneous. See skew_seconds."),
            ("Chart selection", "Core charts use up to six representative local cores, one per aggregator when possible. Core Data and Summary contain all slots."),
        ]
        for index, (label, text) in enumerate(entries, 2):
            overview.write_string(index, 0, label, heading)
            overview.write_string(index, 1, text, body)
            overview.set_row(index, 42)
        core_chart_sheet = workbook.add_worksheet("Core Charts")
        socket_chart_sheet = workbook.add_worksheet("Socket Charts")
        system_chart_sheet = workbook.add_worksheet("System Charts")
        for sheet in (core_chart_sheet, socket_chart_sheet, system_chart_sheet):
            sheet.hide_gridlines(2)
            sheet.set_column(0, 18, 12)
            sheet.write(0, 0, sheet.name + " | estimates and coverage: see Overview", title)
        metric_ids = [definition["id"] for definition in definitions]
        metric_titles = {definition["id"]: definition["title"].split(": ")[-1] for definition in definitions}
        by_level = defaultdict(list)
        for row in rows:
            by_level[row["level"]].append(row)
        for level in ("core", "socket", "system"):
            if not by_level[level]:
                continue
            grouped = defaultdict(dict)
            for row in by_level[level]:
                grouped[(row["scope"], row["sequence"])][row["metric"]] = row
            data = []
            for (scope, sequence), metrics in sorted(grouped.items()):
                first = next(iter(metrics.values()))
                record = {"scope": scope, "sequence": sequence, "timestamp": first["end"]}
                record.update({metric: metrics.get(metric, {}).get("value") for metric in metric_ids})
                record["quality"] = ";".join(sorted({row["quality"] for row in metrics.values()}))
                record["coverage"] = ";".join(sorted({str(row["valid_members"]) + "/" + str(row["expected_members"]) for row in metrics.values()}))
                data.append(record)
            table(level.title() + " Data", ["scope", "sequence", "timestamp"] + metric_ids + ["quality", "coverage"], data)
        table("Summary", list(summaries[0]) if summaries else ["scope", "metric"], summaries)
        table("Quality", FIELDS, (row for row in rows if row["quality"] != "valid" or row["notes"]))
        table("Definitions", ["id", "title", "unit", "operation", "formula", "source", "spatial", "provisional"], definitions)
        chart_data = workbook.add_worksheet("Chart Data")
        chart_data.set_column(0, 13, 21)
        chart_cursor = 0
        lookup = {(row["level"], row["scope"], row["sequence"], row["metric"]): row for row in rows}
        selected_scopes = {}
        for level in ("core", "socket", "system"):
            scopes = sorted({row["scope"] for row in by_level[level] if row["value"] is not None})
            if level == "core":
                representative = {}
                for row in by_level[level]:
                    if row["value"] is not None and row["metric"] == "frequency_non_c6_mhz":
                        representative.setdefault(row["aggregator"], row["scope"])
                scopes = list(representative.values()) or scopes
            selected_scopes[level] = scopes[:6]
        for level, sheet in (("core", core_chart_sheet), ("socket", socket_chart_sheet), ("system", system_chart_sheet)):
            scopes = selected_scopes[level]
            if not scopes:
                sheet.write_string(3, 0, "No confirmed socket topology supplied." if level == "socket" else "No valid metric observations.")
                continue
            sheet.write_string(2, 0, "Selected: " + ", ".join(scopes))
            chart_index = 0
            for chart_spec in config.get("charts", []):
                requested = [metric for metric in metric_ids if metric == chart_spec["metric"] or metric.startswith(chart_spec["metric"] + ".r")]
                if not requested:
                    raise ValueError("chart refers to unknown metric: " + chart_spec["metric"])
                series_keys = [(scopes[0], metric) for metric in requested] if len(requested) > 1 else [(scope, requested[0]) for scope in scopes]
                sequences = sorted({row["sequence"] for row in by_level[level]})
                block = chart_cursor
                chart_data.write_string(block, 0, level + ": " + chart_spec["title"], heading)
                for column, (scope, metric) in enumerate(series_keys, 1):
                    chart_data.write_string(block, column, scope + " | " + metric, heading)
                values_cache = [[] for unused in series_keys]
                categories = []
                for offset, sequence in enumerate(sequences, 1):
                    observed = next((lookup[(level, scope, sequence, metric)] for scope, metric in series_keys
                                     if (level, scope, sequence, metric) in lookup), None)
                    time_value = datetime.fromisoformat(observed["end"].replace("Z", "+00:00")).astimezone(timezone.utc).replace(tzinfo=None)
                    chart_data.write_datetime(block + offset, 0, time_value)
                    categories.append((time_value - datetime(1899, 12, 30)).total_seconds() / 86400)
                    for column, (scope, metric) in enumerate(series_keys, 1):
                        value = lookup.get((level, scope, sequence, metric), {}).get("value")
                        write_value(chart_data, block + offset, column, value)
                        values_cache[column - 1].append(value)
                kind = chart_spec.get("type", "line")
                if kind not in ("line", "stacked_column"):
                    raise ValueError("unsupported chart type")
                chart = workbook.add_chart({"type": "column", "subtype": "stacked"} if kind == "stacked_column" else {"type": "line"})
                for index, ((scope, metric), cached) in enumerate(zip(series_keys, values_cache), 1):
                    options = {"name": metric_titles[metric] if len(requested) > 1 else scope,
                               "categories": ["Chart Data", block + 1, 0, block + len(sequences), 0],
                               "values": ["Chart Data", block + 1, index, block + len(sequences), index],
                               "categories_data": categories, "values_data": cached}
                    if kind == "line":
                        options["line"] = {"color": colors[(index - 1) % len(colors)], "width": 1.5}
                    chart.add_series(options)
                chart.set_title({"name": chart_spec["title"] + (" | " + scopes[0] if len(requested) > 1 else "")})
                chart.set_x_axis({"name": "UTC", "num_format": "hh:mm:ss"})
                chart.set_y_axis({"name": chart_spec["unit"], "major_gridlines": {"visible": True}})
                chart.set_legend({"position": "bottom"})
                chart.show_blanks_as("gap")
                chart.set_size({"width": 760, "height": 380})
                sheet.insert_chart(4 + chart_index * 21, 0, chart)
                chart_index += 1
                chart_cursor += len(sequences) + 3
        overview.activate()
    finally:
        workbook.close()


def excel_report_stream(root, definitions, config, provenance, quality_counts, sequences):
    try:
        import xlsxwriter
    except ImportError as error:
        raise RuntimeError("Excel reporting requires XlsxWriter; install requirements-report.txt on the analysis host") from error
    workbook = xlsxwriter.Workbook(str(root / "pmt-report.xlsx"),
                                   {"constant_memory": True, "strings_to_formulas": False, "strings_to_urls": False})
    heading = workbook.add_format({"bold": True, "font_color": "#FFFFFF", "bg_color": "#254B45"})
    numeric = workbook.add_format({"num_format": "0.000"})
    metric_ids = [definition["id"] for definition in definitions]
    stride = max(1, math.ceil(len(sequences) / 1200))
    chart_sequences = set(sequences[::stride]) | {sequences[-1]}

    def cell(sheet, row_index, column, value):
        if value is None or value == "":
            return
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if isinstance(value, int) and abs(value) > 2**53:
                sheet.write_string(row_index, column, str(value))
            else:
                sheet.write_number(row_index, column, value, numeric)
        else:
            sheet.write_string(row_index, column, str(value))

    def rows_table(name, fields, records, split=False):
        sheet = None
        row_index = 0
        part = 0
        for record in itertools.chain((None,), records):
            if sheet is None or (split and row_index == 1048576):
                part += 1
                sheet = workbook.add_worksheet(name if part == 1 else name + " " + str(part))
                sheet.freeze_panes(1, 2)
                sheet.set_column(0, len(fields) - 1, 19)
                for column, field in enumerate(fields):
                    cell(sheet, 0, column, field)
                row_index = 1
            if record is not None:
                if row_index == 1048576:
                    raise ValueError("Excel worksheet row limit exceeded")
                for column, field in enumerate(fields):
                    value = record.get(field)
                    if field in metric_ids or field in ("aggregate", "mean", "min", "max", "p95", "std", "cv"):
                        value = number(value) if isinstance(value, str) and value else value
                    cell(sheet, row_index, column, value)
                row_index += 1
        sheet.autofilter(0, 0, row_index - 1, len(fields) - 1)

    try:
        overview = workbook.add_worksheet("Overview")
        for index, (label, value) in enumerate((
            ("Source", provenance["analysis_dir"]), ("Time range (UTC)", provenance["first_timestamp"] + " to " + provenance["last_timestamp"]),
            ("Metric configuration SHA256", provenance["metrics_sha256"]),
            ("Core identity", "PMT aggregator + XML-local slot; physical mapping is never inferred."),
            ("Quality", "Detailed rows: metric-quality.csv. Quality worksheet counts reasons per scope and metric."),
            ("Estimates", "Histogram scale is unverified; frequencies/voltage use bucket midpoints."),
            ("Missing data", "First counters, discontinuities and unavailable intervals are blank, not zero."),
        )):
            cell(overview, index, 0, label)
            cell(overview, index, 1, value)
        overview.set_column(0, 0, 34)
        overview.set_column(1, 1, 105)
        fields = ["scope", "sequence", "timestamp"] + metric_ids + ["quality", "coverage"]
        charts = {}
        chart_sheets = {}
        for level in ("core", "socket", "system"):
            chart_sheet = workbook.add_worksheet(level.title() + " Charts")
            chart_sheets[level] = chart_sheet
            chart_sheet.hide_gridlines(2)
            chart_sheet.set_column(0, 18, 12)
            chart_sheet.write_string(0, 0, level.title() + " | estimates and coverage: see Overview")
            path = root / (level + "-metrics.csv")
            if not path.exists():
                continue

            def wide_rows():
                for (scope, sequence), group in itertools.groupby(csv_rows(path),
                                                                   lambda row: (row["scope"], row["sequence"])):
                    metrics = {row["metric"]: row for row in group}
                    first = next(iter(metrics.values()))
                    record = {"scope": scope, "sequence": int(sequence), "timestamp": first["end"]}
                    record.update({metric: metrics.get(metric, {}).get("value") for metric in metric_ids})
                    record["quality"] = ";".join(sorted({row["quality"] for row in metrics.values()}))
                    record["coverage"] = ";".join(sorted({row["valid_members"] + "/" + row["expected_members"] for row in metrics.values()}))
                    if record["sequence"] in chart_sequences and any(record.get(metric) for metric in metric_ids):
                        selected = charts.setdefault(level, {})
                        aggregator = scope.split("/")[1] if level == "core" else scope
                        if scope in selected or (len(selected) < 6 and (
                                level != "core" or aggregator not in {name.split("/")[1] for name in selected})):
                            selected.setdefault(scope, {})[record["sequence"]] = record
                    yield record

            rows_table(level.title() + " Data", fields, wide_rows(), split=True)
        summary_path = root / "metric-summary.csv"
        rows_table("Summary", list(next(csv_rows(summary_path))), csv_rows(summary_path), split=True)
        rows_table("Quality", ["level", "scope", "metric", "quality", "count"],
                   (dict(zip(("level", "scope", "metric", "quality"), key), count=count)
                    for key, count in sorted(quality_counts.items())), split=True)
        rows_table("Definitions", ["id", "title", "unit", "operation", "formula", "source", "spatial", "provisional"], definitions)
        chart_data = workbook.add_worksheet("Chart Data")
        chart_cursor = 0
        for level, sheet in chart_sheets.items():
            selected = charts.get(level, {})
            if not selected:
                sheet.write_string(3, 0, "No valid metric observations or confirmed topology.")
                continue
            scopes = list(selected)
            sheet.write_string(2, 0, "Selected: " + ", ".join(scopes))
            sequences = sorted({sequence for scope in scopes for sequence in selected[scope]})
            for chart_index, spec in enumerate(config.get("charts", [])):
                requested = [metric for metric in metric_ids if metric == spec["metric"] or metric.startswith(spec["metric"] + ".r")]
                if not requested:
                    raise ValueError("chart refers to unknown metric: " + spec["metric"])
                series = [(scopes[0], metric) for metric in requested] if len(requested) > 1 else [(scope, requested[0]) for scope in scopes]
                block = chart_cursor
                for column, (scope, metric) in enumerate(series, 1):
                    cell(chart_data, block, column, scope + " | " + metric)
                cached = [[] for unused in series]
                categories = []
                for offset, sequence in enumerate(sequences, 1):
                    observed = next((selected[scope][sequence] for scope, metric in series if sequence in selected[scope]), None)
                    when = datetime.fromisoformat(observed["timestamp"].replace("Z", "+00:00")).astimezone(timezone.utc).replace(tzinfo=None)
                    chart_data.write_datetime(block + offset, 0, when)
                    categories.append((when - datetime(1899, 12, 30)).total_seconds() / 86400)
                    for column, (scope, metric) in enumerate(series, 1):
                        raw = selected[scope].get(sequence, {}).get(metric)
                        value = number(raw) if raw else None
                        cell(chart_data, block + offset, column, value)
                        cached[column - 1].append(value)
                kind = spec.get("type", "line")
                if kind not in ("line", "stacked_column"):
                    raise ValueError("unsupported chart type")
                chart = workbook.add_chart({"type": "column", "subtype": "stacked"} if kind == "stacked_column" else {"type": "line"})
                for column, ((scope, metric), values) in enumerate(zip(series, cached), 1):
                    chart.add_series({"name": scope if len(requested) == 1 else metric,
                                      "categories": ["Chart Data", block + 1, 0, block + len(sequences), 0],
                                      "values": ["Chart Data", block + 1, column, block + len(sequences), column],
                                      "categories_data": categories, "values_data": values})
                chart.set_title({"name": spec["title"]})
                chart.set_x_axis({"name": "UTC", "num_format": "hh:mm:ss"})
                chart.set_y_axis({"name": spec["unit"]})
                chart.set_legend({"position": "bottom"})
                chart.show_blanks_as("gap")
                chart.set_size({"width": 760, "height": 380})
                sheet.insert_chart(4 + chart_index * 21, 0, chart)
                chart_cursor += len(sequences) + 3
        overview.activate()
    finally:
        workbook.close()


def generate_report(analysis_dir, output, metrics_path, topology_path=None):
    from pmt.pipeline import destination, digest
    analysis_dir = Path(analysis_dir).resolve()
    output = Path(output)
    if output.resolve() == analysis_dir or analysis_dir in output.resolve().parents:
        raise ValueError("report output must be outside the original analysis directory")
    config, definitions = load_metrics(metrics_path)
    topology = load_topology(topology_path)
    inputs = [analysis_dir / "decoded.csv", analysis_dir / "analysis.json", analysis_dir / "provenance/run.json", Path(metrics_path)]
    if topology_path:
        inputs.append(Path(topology_path))
    before = {str(path): digest(path) for path in inputs}
    with destination(output, analysis_dir) as target:
        database = sqlite3.connect(str(target / "report.sqlite"))
        database.execute("CREATE TABLE samples (level TEXT, scope TEXT, metric TEXT, value REAL, "
                         "numerator REAL, denominator REAL, weighted REAL, duration REAL, notes TEXT, quality TEXT)")
        counts = Counter()
        sequences = []
        quality_counts = Counter()
        exact_deltas = Counter()
        delta_metrics = {definition["id"] for definition in definitions if definition["operation"] == "delta"}
        first = last = None
        try:
            with (target / "core-metrics.csv").open("x", newline="", encoding="utf-8") as core_file, \
                 (target / "system-metrics.csv").open("x", newline="", encoding="utf-8") as system_file:
                writers = {"core": csv.DictWriter(core_file, FIELDS),
                          "system": csv.DictWriter(system_file, FIELDS)}
                for writer in writers.values():
                    writer.writeheader()
                socket_file = None
                try:
                    for sequence, group in itertools.groupby(iter_core_rows(analysis_dir, config, definitions, topology),
                                                              lambda row: row["sequence"]):
                        sequences.append(sequence)
                        core_rows = list(group)
                        derived = rollup_rows(core_rows, definitions, topology)
                        for row in itertools.chain(core_rows, derived):
                            level = row["level"]
                            if level == "socket" and socket_file is None:
                                socket_file = (target / "socket-metrics.csv").open("x", newline="", encoding="utf-8")
                                writers["socket"] = csv.DictWriter(socket_file, FIELDS)
                                writers["socket"].writeheader()
                            writers[level].writerow(row)
                            counts[level] += 1
                            first = row["end"] if first is None or timestamp(row["end"]) < timestamp(first) else first
                            last = row["end"] if last is None or timestamp(row["end"]) > timestamp(last) else last
                            quality_counts[(level, row["scope"], row["metric"], row["quality"])] += 1
                            if row["metric"] in delta_metrics and isinstance(row["value"], int):
                                exact_deltas[(level, row["scope"], row["metric"])] += row["value"]
                            store_row(database, row)
                        database.commit()
                finally:
                    if socket_file is not None:
                        socket_file.close()
            summary_fields = ("level", "scope", "metric", "unit", "aggregate", "mean", "min", "max",
                              "p95", "std", "cv", "valid_count", "excluded_count", "notes")
            write_csv(target / "metric-summary.csv", summary_fields, stored_summaries(database, definitions, exact_deltas))
            write_csv(target / "metric-quality.csv", ("level", "scope", "metric", "quality", "count"),
                      (dict(zip(("level", "scope", "metric", "quality"), key), count=count)
                       for key, count in sorted(quality_counts.items())))
        finally:
            database.close()
            (target / "report.sqlite").unlink()
        provenance = {
            "format": "pmt-report/v1", "analysis_dir": str(analysis_dir),
            "inputs_sha256": before, "metrics_sha256": before[str(Path(metrics_path))],
            "core_metric_rows": counts["core"], "total_metric_rows": sum(counts.values()),
            "first_timestamp": first, "last_timestamp": last,
            "physical_topology": "explicit" if topology else "unmapped",
            "implementation_sha256": digest(Path(__file__)),
            "core_view_sha256": digest(Path(__file__).with_name("core_view.py")),
            "caveats": ["histogram scale unverified", "no inferred physical topology", "sequential region snapshots"],
        }
        shutil.copyfile(str(metrics_path), str(target / "metrics.json"))
        if topology_path:
            shutil.copyfile(str(topology_path), str(target / "topology.csv"))
        excel_report_stream(target, definitions, config, provenance, quality_counts, sequences)
        from pmt.core_view import generate as generate_core_view
        generate_core_view(target)
        after = {str(path): digest(path) for path in inputs}
        if before != after:
            raise ValueError("report inputs changed during generation")
        provenance["output_sha256"] = {path.name: digest(path) for path in sorted(target.iterdir()) if path.is_file()}
        (target / "report.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    return {"output": str(output), "workbook": str(output / "pmt-report.xlsx"), "core_metric_rows": counts["core"],
            "physical_topology": provenance["physical_topology"]}


def evaluate(definition, current, previous=None, elapsed=None):
    operation = definition["operation"]
    if any(value is None or not math.isfinite(value) for value in current):
        return None, "missing_input", None, None
    invalid = definition.get("invalid_values", [])
    if any(value in invalid for value in current):
        return None, "invalid_marker", None, None
    if operation == "gauge":
        value = current[0]
        if not definition.get("minimum", -math.inf) <= value <= definition.get("maximum", math.inf):
            return None, "out_of_range", None, None
        return value, "valid", value, 1
    if previous is None:
        return None, "first_sample", None, None
    if len(previous) != len(current) or any(value is None or not math.isfinite(value) for value in previous):
        return None, "missing_previous_input", None, None
    if any(value in invalid for value in previous):
        return None, "invalid_previous", None, None
    if elapsed is None or elapsed <= 0:
        return None, "non_increasing_time", None, None
    differences = [after - before for after, before in zip(current, previous)]
    if any(value < 0 for value in differences):
        return None, "reset_or_wrap", None, None
    if operation == "delta":
        return differences[0], "valid", differences[0], 1
    if operation == "rate":
        return differences[0] / elapsed, "valid", differences[0], elapsed
    if operation == "histogram_share":
        numerator = sum(differences[index] for index in definition["selected"])
        denominator = sum(differences)
        factor = 100
    elif operation == "histogram_mean":
        included = definition["selected"]
        numerator = sum(differences[index] * definition["weights"][index] for index in included)
        denominator = sum(differences[index] for index in included)
        factor = 1
    else:
        raise ValueError("unsupported metric operation: " + operation)
    if denominator == 0:
        return None, "no_activity", None, None
    return factor * numerator / denominator, "valid", factor * numerator, denominator