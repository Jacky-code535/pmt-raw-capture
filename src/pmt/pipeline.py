"""Read-only v1 capture archival and XML-backed offline analysis."""

import base64
import contextlib
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pmt.process.aggregate import SummaryStore
from pmt.export.series_csv import writer
from pmt.export.endpoint_csv import topology_map, decoded_rows


import pmt_analysis as analysis
import pmt_bulk_capture as capture


FIELDS = ("timestamp", "endpoint", "metric", "value", "unit", "sequence",
          "aggregator", "guid", "system", "socket", "die", "module", "measure", "validity")
GROUP = analysis.IDENTITY + ("measure",)
STATS = ("mean", "min", "max", "p95", "std", "cv", "valid_count")


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


@contextlib.contextmanager
def destination(output, run_dir):
    output = output.absolute()
    if output.exists() or output.is_symlink():
        raise FileExistsError("output already exists: " + str(output))
    if run_dir == output.resolve() or run_dir in output.resolve().parents:
        raise ValueError("output must be outside the raw run directory")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".pmt-analysis-", dir=str(output.parent)))
    try:
        yield temporary
        if output.exists():
            raise FileExistsError(str(output))
        os.rename(str(temporary), str(output))
    finally:
        if temporary.exists():
            shutil.rmtree(str(temporary))


def checked_run(run_dir, allow_partial):
    paths = [run_dir / "run.json", run_dir / "manifest.ndjson", run_dir / "snapshots"]
    paths.extend((run_dir / "snapshots").glob("bulk-*.json.gz"))
    if any(path.is_symlink() for path in paths):
        raise ValueError("raw inputs must not be symbolic links")
    report = capture.verify_run(run_dir, write_report=False)
    if not report["AllObservedFilesValid"] or not report["ObservedFiles"]:
        raise ValueError("raw verification failed: " + json.dumps(report["Errors"]))
    if not allow_partial and not report["RequestedSampleCountReached"]:
        raise ValueError("sample count incomplete; use --allow-partial for a valid shorter run")
    return capture.load_json(run_dir / "run.json"), report


def archive_run(run_dir, output, allow_partial=False):
    with capture.run_lock(run_dir):
        state, report = checked_run(run_dir, allow_partial)
        with destination(output, run_dir) as target:
            capture_dir = target / "capture" / capture.validate_identifier(state["RunId"], "run-id")
            capture_dir.mkdir(parents=True)
            for name in ("run.json", "manifest.ndjson"):
                shutil.copyfile(str(run_dir / name), str(capture_dir / name))
            (capture_dir / "snapshots").mkdir()
            for source in sorted((run_dir / "snapshots").glob("bulk-*.json.gz")):
                shutil.copyfile(str(source), str(capture_dir / "snapshots" / source.name))
            metadata = target / "metadata"
            metadata.mkdir()
            capture.atomic_write_json(metadata / "platform.json", {
                "observed": state["Machine"], "platform_label": state.get("PlatformLabel", ""),
                "xml_version_label": state.get("XMLVersionLabel", ""),
            })
            capture.atomic_write_json(metadata / "endpoint.json", {
                "endpoint": state["Endpoint"], "aggregators": state["Inventory"],
                "topology": "not inferred from endpoint or AccessId",
            })
            capture.atomic_write_json(metadata / "capture_config.json", state)
            records = []
            for path in sorted((capture_dir / "snapshots").glob("bulk-*.json.gz")):
                document = capture.read_bundle(path)
                sequence = document["Capture"]["Sequence"]
                for item in document["TelemetryData"]:
                    access = capture.validate_identifier(item["attributes"]["AccessId"], "AccessId")
                    relative = Path("raw") / ("sample-%06d" % sequence) / (access + ".bin")
                    binary = target / relative
                    binary.parent.mkdir(parents=True, exist_ok=True)
                    capture.atomic_write_bytes(binary, base64.b64decode(item["Data"], validate=True))
                    records.append({"path": relative.as_posix(), "sequence": sequence,
                                    "endpoint": state["Endpoint"], "aggregator": access,
                                    "guid": item["Guid"], "size": item["Size"],
                                    "timestamp": item["attributes"]["CapturedAt"], "sha256": digest(binary)})
            logs = target / "logs"
            logs.mkdir()
            for name in ("collector.log", "console.log"):
                source = run_dir / name
                if source.is_symlink():
                    raise ValueError("log is a symbolic link")
                if source.is_file():
                    shutil.copyfile(str(source), str(logs / name))
            capture.atomic_write_json(target / "manifest.json", {
                "format": "pmt-offline-archive/v1", "raw_format": capture.FORMAT_VERSION,
                "run_id": state["RunId"], "verification": report, "records": records,
                "capture_start": records[0]["timestamp"], "capture_end": document["Capture"]["FinishedAt"],
                "replay_run_dir": capture_dir.relative_to(target).as_posix(),
                "files": {path.relative_to(target).as_posix(): digest(path)
                          for path in sorted(target.rglob("*")) if path.is_file()},
            })
    return {"output": str(output), "raw_records": len(records)}


def freeze_xml(metadata, inventory, target):
    metadata = metadata.resolve()
    content = metadata.read_bytes()
    if b"<!DOCTYPE" in content or b"<!ENTITY" in content:
        raise ValueError("XML entities and DTDs are not supported")
    try:
        registry = ET.fromstring(content)
    except ET.ParseError as error:
        raise ValueError("invalid XML registry: " + str(error)) from error
    required = {(capture.normalize_guid(item["Guid"]), int(item["Size"])) for item in inventory}
    matched = set()
    sources = {metadata.resolve()}
    root = metadata.resolve().parent
    for mapping in registry.findall("./mappings/mapping"):
        key = (capture.normalize_guid(mapping.attrib["guid"]), int(mapping.attrib["size"]))
        if key not in required:
            continue
        if key in matched:
            raise ValueError("duplicate GUID+Size XML mapping")
        matched.add(key)
        xmlset = mapping.find("xmlset")
        for tag in ("common", "aggregator", "aggregatorinterface"):
            relative = Path(xmlset.findtext("basedir")) / xmlset.findtext(tag)
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("XML paths must stay within the registry directory")
            source = root / relative
            if root not in source.resolve().parents:
                raise ValueError("XML reference escapes registry directory")
            sources.add(source)
    if matched != required:
        raise ValueError("no exact XML mapping for " + repr(sorted(required - matched)))
    hashes = {}
    for source in sorted(sources):
        relative = source.relative_to(root)
        copied = target / relative
        copied.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(str(source), str(copied))
        hashes[relative.as_posix()] = digest(copied)
    return target / metadata.name, hashes










def analyze_run(args):
    run_dir = args.run_dir.resolve()
    if any(not math.isfinite(value) or value < 0 for value in (args.failure_before, args.failure_after)):
        raise ValueError("failure window durations must be finite and nonnegative")
    with capture.run_lock(run_dir), destination(args.output, run_dir) as target:
        state, verification = checked_run(run_dir, args.allow_partial)
        provenance = target / "provenance"
        provenance.mkdir()
        shutil.copyfile(str(run_dir / "run.json"), str(provenance / "run.json"))
        policies = {}
        inputs = {}
        copies = {}
        for name in ("policies", "topology", "events"):
            source = getattr(args, name, None)
            if source is not None:
                copied = provenance / (name + source.suffix)
                shutil.copyfile(str(source), str(copied))
                inputs[name] = digest(copied)
                copies[name] = copied
        if args.policies:
            policies = capture.load_json(copies["policies"])
        topology = topology_map(copies.get("topology"))
        events = []
        if args.events:
            with copies["events"].open(newline="", encoding="utf-8-sig") as source:
                events = analysis.load_events(csv.DictReader(source), args.event_offset_seconds)
        processor = analysis.Reconstructor(policies)
        metadata, hashes = freeze_xml(args.metadata, state["Inventory"], provenance / "xml")
        from pmt.decode.payload_decoder import PayloadDecoder
        native_decoder = PayloadDecoder(metadata) if args.decoder is None else None
        native_sources = {path.name: digest(path) for path in sorted((Path(__file__).parent / "decode").glob("*.py"))}
        decoder_hash = digest(args.decoder) if args.decoder else hashlib.sha256(
            json.dumps(native_sources, sort_keys=True).encode("utf-8")).hexdigest()
        platform_commit = None
        if native_decoder is not None:
            from pmt.decode.platform_data import revision
            try:
                platform_commit = revision(args.metadata)
            except OSError:
                pass
        raw_hashes = {}
        count = 0
        summary = SummaryStore(target / ".summary.sqlite")
        phases = SummaryStore(target / ".phases.sqlite")
        try:
            with contextlib.ExitStack() as stack:
                decoded = writer(stack, target / "decoded.csv", FIELDS)
                series = writer(stack, target / "series.csv", FIELDS)
                aligned = writer(stack, target / "aligned.csv", FIELDS + ("phase", "test_item", "status"))
                failures = writer(stack, target / "failure-windows.csv", FIELDS + ("phase", "test_item", "failure_time", "relative_seconds"))
                views = {level: writer(stack, target / ("view-" + level + ".csv"), ("scope",) + FIELDS)
                         for level in analysis.TOPOLOGY + ("endpoint", "aggregator")}
                for path in sorted((run_dir / "snapshots").glob("bulk-*.json.gz")):
                    before = digest(path)
                    document = capture.read_bundle(path)
                    if digest(path) != before:
                        raise ValueError("raw snapshot changed during read")
                    raw_hashes[path.name] = before
                    if native_decoder is not None:
                        results = native_decoder.decode(document)
                    else:
                        process = subprocess.run([str(args.decoder.resolve()), "-metadata", str(metadata)],
                                                 input=json.dumps(document), stdout=subprocess.PIPE,
                                                 stderr=subprocess.PIPE, text=True, timeout=120)
                        if process.returncode:
                            raise RuntimeError("XML decoder failed: " + process.stderr[-4000:])
                        results = json.loads(process.stdout)
                    for row in decoded_rows(document, results, topology):
                        decoded.writerow(dict(row, measure="value", validity="invalid_marker" if row["known_invalid"] else "decoded_unfiltered"))
                        count += 1
                        for sample in processor.add(row):
                            series.writerow(sample)
                            summary.add(sample)
                            for level, view in views.items():
                                scope = sample.get(level, "")
                                if level == "aggregator":
                                    scope = sample["endpoint"] + "/" + sample["aggregator"]
                                elif level in analysis.TOPOLOGY:
                                    ancestors = analysis.TOPOLOGY[:analysis.TOPOLOGY.index(level) + 1]
                                    scope = "/".join(sample[name] for name in ancestors) if all(sample[name] for name in ancestors) else ""
                                view.writerow(dict(sample, scope=scope or "unknown"))
                            for match in analysis.align_events(sample, events):
                                aligned.writerow(match)
                                phases.add(match, GROUP + ("phase", "test_item", "status"))
                            failures.writerows(analysis.failure_windows(sample, events, args.failure_before, args.failure_after))
                writer(stack, target / "summary.csv", GROUP + STATS).writerows(summary.rows())
                writer(stack, target / "phase-summary.csv", GROUP + ("phase", "test_item", "status") + STATS).writerows(
                    phases.rows(GROUP + ("phase", "test_item", "status")))
            if args.decoder and digest(args.decoder) != decoder_hash:
                raise ValueError("decoder changed during analysis")
            capture.atomic_write_json(target / "analysis.json", {
                "format": "pmt-analysis/v1", "generated_at": capture.utc_now(), "run_id": state["RunId"],
                "verification": verification, "decoded_rows": count, "raw_snapshots": raw_hashes,
                "decoder_sha256": decoder_hash, "xml_files": hashes, "inputs": inputs,
                "decoder_kind": "builtin-python" if native_decoder is not None else "external",
                "platform_source": {"metadata": str(args.metadata.resolve()), "git_commit": platform_commit},
                "event_offset_seconds": args.event_offset_seconds,
                "failure_before_seconds": args.failure_before, "failure_after_seconds": args.failure_after,
                "analyzer_sources": {path.relative_to(Path(__file__).parent).as_posix(): digest(path)
                                     for path in sorted(Path(__file__).parent.rglob("*.py"))},
                "statistics": {"mean": "arithmetic sample mean", "std": "population (ddof=0)",
                               "p95": "linear interpolation at (n-1)*0.95", "cv": "std/abs(mean); blank when mean=0",
                               "valid_count": "finite non-null values", "precision": "float64 statistics; integer counter differences"},
                "topology": "scope views retain series identity; no implicit spatial sum",
                "validity": "XML-decoded numeric values are not hardware-health qualification; invalid markers require policy",
            })
        finally:
            summary.close()
            phases.close()
        (target / ".summary.sqlite").unlink()
        (target / ".phases.sqlite").unlink()
    return {"output": str(args.output), "decoded_rows": count}


def compare_runs(args):
    fields = GROUP + (("phase", "test_item") if args.by_test else ())
    filename = "phase-summary.csv" if args.by_test else "summary.csv"
    provenance = [capture.load_json(path / "analysis.json") for path in (args.baseline, args.candidate)]
    for key in ("format", "decoder_sha256", "xml_files", "statistics", "analyzer_sources"):
        if provenance[0].get(key) != provenance[1].get(key):
            raise ValueError("analyses use different " + key + "; reanalyze with matching settings")
    for key in ("policies", "topology"):
        if provenance[0]["inputs"].get(key) != provenance[1]["inputs"].get(key):
            raise ValueError("analyses use different " + key)
    tables = []
    for directory in (args.baseline, args.candidate):
        table = {}
        with (directory / filename).open(newline="", encoding="utf-8") as source:
            for row in csv.DictReader(source):
                key = tuple(row[name] for name in fields)
                if key in table:
                    raise ValueError("ambiguous comparison key; phase/test has multiple statuses")
                table[key] = row
        tables.append(table)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", newline="", encoding="utf-8") as output:
        result = csv.DictWriter(output, fieldnames=fields + ("baseline_mean", "candidate_mean", "difference",
                                                            "relative_change", "baseline_count", "candidate_count", "match"))
        result.writeheader()
        for key in sorted(set(tables[0]) | set(tables[1])):
            baseline = tables[0].get(key, {})
            candidate = tables[1].get(key, {})
            before = float(baseline["mean"]) if baseline.get("mean") else None
            after = float(candidate["mean"]) if candidate.get("mean") else None
            difference = after - before if after is not None and before is not None else None
            result.writerow(dict(zip(fields, key), baseline_mean=before, candidate_mean=after,
                                 difference=difference, relative_change=difference / abs(before) if before and difference is not None else None,
                                 baseline_count=baseline.get("valid_count", 0), candidate_count=candidate.get("valid_count", 0),
                                 match="both" if baseline and candidate else "baseline_only" if baseline else "candidate_only"))
    return {"output": str(args.output), "comparison": "by_test" if args.by_test else "whole_run"}