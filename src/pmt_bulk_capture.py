#!/usr/bin/env python3
"""Capture local Intel PMT sysfs telemetry as decode-later bulk files.

The output envelope intentionally uses the Redfish-compatible ``TelemetryData``
shape accepted by Intel-PMT's offline debug decoder. Capture metadata is kept in
an additional top-level object that older decoders safely ignore.
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import datetime as dt
import fcntl
import gzip
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import sys
import tempfile
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple


FORMAT_VERSION = "intel-pmt-local-bulk/v1"
TOOL_VERSION = "0.4.3"
DEFAULT_SYSFS = Path("/sys/class/intel_pmt")
DEFAULT_OUTPUT_ROOT = Path("./results")
PMT_ENTRY = re.compile(r"^telem([0-9]+)$")
SAFE_ID = re.compile(r"^[A-Za-z0-9_.-]+$")
STOP_REQUESTED = False


def utc_now() -> str:
    return (
        dt.datetime.now(dt.timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def filename_time() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")


def fsync_directory(path: Path) -> None:
    descriptor = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def atomic_write_bytes(path: Path, data: bytes, mode: int = 0o640) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(str(temporary), str(path))
        fsync_directory(path.parent)
    except BaseException:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise


def atomic_write_json(path: Path, document: Dict[str, Any]) -> None:
    data = json.dumps(
        document, ensure_ascii=False, indent=2, sort_keys=True
    ).encode("utf-8") + b"\n"
    atomic_write_bytes(path, data)


def append_manifest(path: Path, record: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(
        record, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8") + b"\n"
    descriptor = os.open(
        str(path), os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o640
    )
    try:
        os.write(descriptor, line)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


@contextlib.contextmanager
def run_lock(run_dir: Path):
    run_dir.mkdir(parents=True, exist_ok=True, mode=0o750)
    with (run_dir / ".capture.lock").open("a+") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError("run is busy: " + str(run_dir)) from error
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def process_start(pid: int) -> str:
    return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]


def log_event(run_dir: Path, event: str, **fields: Any) -> None:
    append_manifest(run_dir / "collector.log", {"Time": utc_now(), "Event": event, **fields})


def normalize_guid(raw: str) -> str:
    value = int(raw, 0)
    if value < 0 or value > 0xFFFFFFFFFFFFFFFF:
        raise ValueError(f"GUID is outside uint64 range: {raw!r}")
    return f"0x{value:08x}"


def telemetry_sort_key(path: Path) -> int:
    match = PMT_ENTRY.fullmatch(path.name)
    if match is None:
        raise ValueError(f"invalid telemetry entry: {path}")
    return int(match.group(1))


def validate_identifier(value: str, label: str) -> str:
    if value in (".", "..") or not SAFE_ID.fullmatch(value):
        raise ValueError(
            f"{label} must contain only letters, numbers, '.', '_' or '-'"
        )
    return value


def discover_inventory(sysfs_root: Path) -> List[Dict[str, Any]]:
    if not sysfs_root.is_dir():
        raise RuntimeError(f"PMT sysfs directory is unavailable: {sysfs_root}")
    entries = sorted(
        (
            entry
            for entry in sysfs_root.iterdir()
            if entry.is_dir() and PMT_ENTRY.fullmatch(entry.name)
        ),
        key=telemetry_sort_key,
    )
    if not entries:
        raise RuntimeError(f"no telem* entries found under {sysfs_root}")

    inventory: List[Dict[str, Any]] = []
    for entry in entries:
        guid = normalize_guid(read_text(entry / "guid"))
        size = int(read_text(entry / "size"), 0)
        if size <= 0:
            raise RuntimeError(f"{entry.name} reports invalid size {size}")
        if not (entry / "telem").is_file():
            raise RuntimeError(f"{entry.name} has no readable telem file")
        inventory.append(
            {
                "AccessId": entry.name,
                "Guid": guid,
                "Size": size,
                "Path": str(entry / "telem"),
            }
        )
    return inventory


def machine_facts() -> Dict[str, Any]:
    boot_id_path = Path("/proc/sys/kernel/random/boot_id")
    boot_id = read_text(boot_id_path) if boot_id_path.is_file() else "unknown"
    uname = os.uname()
    return {
        "Hostname": uname.nodename,
        "Kernel": {
            "Sysname": uname.sysname,
            "Release": uname.release,
            "Version": uname.version,
            "Machine": uname.machine,
        },
        "BootId": boot_id,
        "Python": sys.version.split()[0],
    }


def metadata_facts(metadata: Optional[Path]) -> Optional[Dict[str, str]]:
    if metadata is None:
        return None
    if not metadata.is_file():
        raise RuntimeError(f"metadata entry does not exist: {metadata}")
    return {"Path": str(metadata.resolve())}


def inventory_identity(
    inventory: Iterable[Dict[str, Any]]
) -> List[Tuple[str, str, int]]:
    return [
        (str(item["AccessId"]), str(item["Guid"]), int(item["Size"]))
        for item in inventory
    ]


def write_compressed_bundle(path: Path, document: Dict[str, Any]) -> None:
    encoded = json.dumps(
        document, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o640)
        with os.fdopen(descriptor, "wb") as raw_output:
            with gzip.GzipFile(
                filename="", mode="wb", compresslevel=6, fileobj=raw_output
            ) as compressed:
                compressed.write(encoded)
            raw_output.flush()
            os.fsync(raw_output.fileno())
        os.replace(str(temporary), str(path))
        fsync_directory(path.parent)
    except BaseException:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise


def capture_bundle(
    *,
    endpoint: str,
    run_id: str,
    sequence: int,
    sysfs_root: Path,
    expected_inventory: List[Dict[str, Any]],
    snapshots_dir: Path,
    manifest_path: Path,
) -> Dict[str, Any]:
    started_wall = utc_now()
    started_monotonic = time.monotonic_ns()
    telemetry: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []

    try:
        current_inventory = discover_inventory(sysfs_root)
    except Exception as error:
        current_inventory = []
        errors.append({"Stage": "inventory", "Error": str(error)})

    if inventory_identity(current_inventory) != inventory_identity(
        expected_inventory
    ):
        errors.append(
            {
                "Stage": "inventory",
                "Error": "current telem/GUID/Size inventory differs from run baseline",
            }
        )

    for expected in expected_inventory:
        access_id = str(expected["AccessId"])
        entry = sysfs_root / access_id
        captured_at = utc_now()
        try:
            guid = normalize_guid(read_text(entry / "guid"))
            size = int(read_text(entry / "size"), 0)
            binary = (entry / "telem").read_bytes()
            if guid != expected["Guid"]:
                raise RuntimeError(
                    f"GUID changed from {expected['Guid']} to {guid}"
                )
            if size != expected["Size"]:
                raise RuntimeError(
                    f"size changed from {expected['Size']} to {size}"
                )
            if len(binary) != size:
                raise RuntimeError(
                    f"read {len(binary)} bytes but sysfs reports {size}"
                )
            telemetry.append(
                {
                    "Guid": guid,
                    # Keep the same Unix-seconds contract used by the existing
                    # local and Redfish receiver types. CapturedAt retains the
                    # higher-resolution wall-clock timestamp for diagnostics.
                    "CollectionTimestamp": str(int(time.time())),
                    "Size": size,
                    "attributes": {
                        "AccessId": access_id,
                        "CapturedAt": captured_at,
                        "Source": "local-sysfs",
                    },
                    "Data": base64.b64encode(binary).decode("ascii"),
                }
            )
        except Exception as error:
            errors.append(
                {
                    "Stage": "read",
                    "AccessId": access_id,
                    "Error": str(error),
                }
            )

    finished_wall = utc_now()
    duration_ms = (time.monotonic_ns() - started_monotonic) / 1_000_000
    complete = not errors and len(telemetry) == len(expected_inventory)
    document: Dict[str, Any] = {
        "FormatVersion": FORMAT_VERSION,
        "Capture": {
            "ToolVersion": TOOL_VERSION,
            "RunId": run_id,
            "Endpoint": endpoint,
            "Sequence": sequence,
            "StartedAt": started_wall,
            "FinishedAt": finished_wall,
            "DurationMilliseconds": round(duration_ms, 3),
            "ExpectedAggregators": len(expected_inventory),
            "CapturedAggregators": len(telemetry),
            "Complete": complete,
            "Errors": errors,
        },
        "TelemetryData": telemetry,
    }
    filename = f"bulk-{sequence:06d}-{filename_time()}.json.gz"
    output_path = snapshots_dir / filename
    write_compressed_bundle(output_path, document)
    record = {
        "Sequence": sequence,
        "Filename": filename,
        "CompressedBytes": output_path.stat().st_size,
        "StartedAt": started_wall,
        "FinishedAt": finished_wall,
        "DurationMilliseconds": round(duration_ms, 3),
        "ExpectedAggregators": len(expected_inventory),
        "CapturedAggregators": len(telemetry),
        "Complete": complete,
        "ErrorCount": len(errors),
    }
    append_manifest(manifest_path, record)
    return record


def estimate_required_bytes(
    inventory: List[Dict[str, Any]], samples: int
) -> int:
    # Base64 expands by 4/3. The 2x factor leaves room for JSON, manifests,
    # temporary files and data that does not compress.
    raw_per_sample = sum(int(item["Size"]) for item in inventory)
    return raw_per_sample * samples * 2 + 64 * 1024 * 1024


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as source:
        result = json.load(source)
    if not isinstance(result, dict):
        raise RuntimeError(f"expected JSON object in {path}")
    return result


def update_run_state(
    run_path: Path,
    state: Dict[str, Any],
    *,
    status: str,
    completed_files: int,
    complete_files: int,
    incomplete_files: int,
) -> None:
    state["Status"] = status
    state["UpdatedAt"] = utc_now()
    state["CompletedFiles"] = completed_files
    state["CompleteFiles"] = complete_files
    state["IncompleteFiles"] = incomplete_files
    atomic_write_json(run_path, state)


def request_stop(_signal_number: int, _frame: Any) -> None:
    global STOP_REQUESTED
    STOP_REQUESTED = True


def next_aligned_minute_delay() -> float:
    now = time.time()
    return max(0.0, 60.0 - (now % 60.0))


def wait_until(deadline: float) -> None:
    while not STOP_REQUESTED:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        time.sleep(min(remaining, 0.1))


def prepare_run(
    args: argparse.Namespace,
) -> Tuple[Path, Dict[str, Any], List[Dict[str, Any]], int]:
    endpoint = validate_identifier(args.endpoint, "endpoint")
    run_id = args.run_id or (
        endpoint.lower() + "-" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    )
    validate_identifier(run_id, "run-id")
    run_dir = args.output_root.resolve() / run_id
    run_path = run_dir / "run.json"
    snapshots_dir = run_dir / "snapshots"

    if run_path.exists():
        if not args.resume:
            raise RuntimeError(
                f"run already exists: {run_dir}; pass --resume to continue it"
            )
        state = load_json(run_path)
        if state.get("Endpoint") != endpoint:
            raise RuntimeError("resume endpoint does not match run.json")
        if args.interval_seconds != float(state["IntervalSeconds"]):
            raise RuntimeError("resume interval does not match run.json")
        if args.samples != int(state["RequestedSamples"]):
            raise RuntimeError("resume sample count does not match run.json")
        if args.sysfs_root.resolve() != Path(state["SysfsRoot"]).resolve():
            raise RuntimeError("resume sysfs root does not match run.json")
        inventory = list(state["Inventory"])
        next_sequence = reconcile_run(run_dir, state)
        return run_dir, state, inventory, next_sequence

    inventory = discover_inventory(args.sysfs_root)
    if args.expected_aggregators is not None and len(inventory) != args.expected_aggregators:
        raise RuntimeError(
            f"discovered {len(inventory)} aggregators; "
            f"expected {args.expected_aggregators}"
        )
    run_dir.mkdir(parents=True, exist_ok=True, mode=0o750)
    snapshots_dir.mkdir(exist_ok=True, mode=0o750)
    if any(snapshots_dir.iterdir()):
        raise RuntimeError("snapshot directory is not empty but run.json is missing")
    required = estimate_required_bytes(inventory, args.samples)
    free = shutil.disk_usage(run_dir).free
    if free < required:
        raise RuntimeError(
            f"insufficient free space: need safety estimate {required} bytes, "
            f"have {free}"
        )
    state = {
        "FormatVersion": FORMAT_VERSION,
        "ToolVersion": TOOL_VERSION,
        "RunId": run_id,
        "Endpoint": endpoint,
        "Status": "prepared",
        "CreatedAt": utc_now(),
        "UpdatedAt": utc_now(),
        "SysfsRoot": str(args.sysfs_root.resolve()),
        "IntervalSeconds": args.interval_seconds,
        "RequestedSamples": args.samples,
        "ExpectedDurationSeconds": args.interval_seconds * args.samples,
        "ExpectedRawBytesPerSample": sum(
            int(item["Size"]) for item in inventory
        ),
        "FreeBytesAtStart": free,
        "Experiment": getattr(args, "experiment", ""),
        "Workload": getattr(args, "workload", ""),
        "Note": getattr(args, "note", ""),
        "Metadata": metadata_facts(args.metadata),
        "Machine": machine_facts(),
        "Inventory": inventory,
        "CompletedFiles": 0,
        "CompleteFiles": 0,
        "IncompleteFiles": 0,
    }
    atomic_write_json(run_path, state)
    return run_dir, state, inventory, 1


def run_capture(args: argparse.Namespace) -> int:
    global STOP_REQUESTED
    STOP_REQUESTED = False
    if not math.isfinite(args.interval_seconds) or args.interval_seconds <= 0:
        raise ValueError("interval-seconds must be positive")
    if args.samples <= 0:
        raise ValueError("samples must be positive")

    if not args.run_id:
        args.run_id = args.endpoint.lower() + "-" + filename_time()
    validate_identifier(args.run_id, "run-id")
    run_dir = args.output_root.resolve() / args.run_id
    with run_lock(run_dir):
        return capture_locked(args)


def capture_locked(args: argparse.Namespace) -> int:
    run_dir, state, inventory, next_sequence = prepare_run(args)
    state["Pid"] = os.getpid()
    state["ProcessStart"] = process_start(os.getpid())
    state["ProcessBootId"] = machine_facts()["BootId"]
    state.pop("LastError", None)
    verification = run_dir / "verification.json"
    if verification.exists():
        verification.unlink()
    try:
        log_event(run_dir, "start", NextSequence=next_sequence)
        return continue_capture(
            args, run_dir, state, inventory, next_sequence
        )
    except Exception as error:
        state["LastError"] = str(error)
        try:
            update_run_state(
                run_dir / "run.json", state, status="failed",
                completed_files=int(state.get("CompletedFiles", 0)),
                complete_files=int(state.get("CompleteFiles", 0)),
                incomplete_files=int(state.get("IncompleteFiles", 0)),
            )
            log_event(run_dir, "failed", Error=str(error))
        except OSError:
            pass
        raise


def continue_capture(
    args: argparse.Namespace,
    run_dir: Path,
    state: Dict[str, Any],
    inventory: List[Dict[str, Any]],
    next_sequence: int,
) -> int:
    requested_samples = int(state["RequestedSamples"])
    if next_sequence > requested_samples:
        state["Status"] = "completed"
        atomic_write_json(run_dir / "run.json", state)
        print(str(run_dir))
        return 1 if state.get("IncompleteFiles", 0) else 0

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    manifest_path = run_dir / "manifest.ndjson"
    snapshots_dir = run_dir / "snapshots"
    complete_files = int(state.get("CompleteFiles", 0))
    incomplete_files = int(state.get("IncompleteFiles", 0))
    completed_files = next_sequence - 1
    update_run_state(
        run_dir / "run.json",
        state,
        status="running",
        completed_files=completed_files,
        complete_files=complete_files,
        incomplete_files=incomplete_files,
    )

    if args.align_minute and next_sequence == 1:
        wait_until(time.monotonic() + next_aligned_minute_delay())

    schedule_start = time.monotonic()
    first_sequence = next_sequence
    for sequence in range(next_sequence, requested_samples + 1):
        if STOP_REQUESTED:
            break
        due = schedule_start + (sequence - first_sequence) * args.interval_seconds
        wait_until(due)
        if STOP_REQUESTED:
            break
        record = capture_bundle(
            endpoint=args.endpoint,
            run_id=str(state["RunId"]),
            sequence=sequence,
            sysfs_root=args.sysfs_root,
            expected_inventory=inventory,
            snapshots_dir=snapshots_dir,
            manifest_path=manifest_path,
        )
        completed_files = sequence
        log_event(run_dir, "snapshot", **record)
        if record["Complete"]:
            complete_files += 1
        else:
            incomplete_files += 1
        update_run_state(
            run_dir / "run.json",
            state,
            status="running",
            completed_files=completed_files,
            complete_files=complete_files,
            incomplete_files=incomplete_files,
        )
        print(
            json.dumps(
                {
                    "sequence": sequence,
                    "file": record["Filename"],
                    "complete": record["Complete"],
                    "duration_ms": record["DurationMilliseconds"],
                },
                separators=(",", ":"),
            ),
            flush=True,
        )

    status = "completed" if completed_files >= requested_samples else "stopped"
    update_run_state(
        run_dir / "run.json",
        state,
        status=status,
        completed_files=completed_files,
        complete_files=complete_files,
        incomplete_files=incomplete_files,
    )
    print(str(run_dir))
    log_event(run_dir, status, CompletedFiles=completed_files)
    return 1 if incomplete_files else 0


def read_manifest(path: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    if not path.is_file():
        return records
    with path.open("r", encoding="utf-8") as source:
        for line_number, line in enumerate(source, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise RuntimeError(
                    f"invalid manifest line {line_number}: {error}"
                ) from error
            records.append(record)
    return records


def read_bundle(path: Path) -> Dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as source:
        result = json.load(source)
    if not isinstance(result, dict):
        raise RuntimeError(f"bundle is not a JSON object: {path}")
    return result


def verify_run(run_dir: Path, write_report: bool = True) -> Dict[str, Any]:
    run_dir = run_dir.resolve()
    state = load_json(run_dir / "run.json")
    baseline = {
        str(item["AccessId"]): (str(item["Guid"]), int(item["Size"]))
        for item in state["Inventory"]
    }
    errors: List[Dict[str, Any]] = []
    try:
        manifest_records = read_manifest(run_dir / "manifest.ndjson")
    except (OSError, RuntimeError) as error:
        errors.append({"Filename": "manifest.ndjson", "Error": str(error)})
        manifest_records = []
    manifest = {
        str(record["Filename"]): record for record in manifest_records
    }
    files = sorted((run_dir / "snapshots").glob("bulk-*.json.gz"))
    if len(manifest) != len(manifest_records):
        errors.append({"Filename": "manifest.ndjson", "Error": "duplicate filenames"})
    complete_files = 0
    sequences: List[int] = []

    for path in files:
        try:
            if path.name not in manifest:
                raise RuntimeError("file is absent from manifest")
            document = read_bundle(path)
            capture = document["Capture"]
            telemetry = document["TelemetryData"]
            sequence = int(capture["Sequence"])
            sequences.append(sequence)
            if document.get("FormatVersion") != FORMAT_VERSION:
                raise RuntimeError("unexpected FormatVersion")
            if capture.get("Endpoint") != state.get("Endpoint"):
                raise RuntimeError("endpoint differs from run.json")
            if capture.get("RunId") != state.get("RunId"):
                raise RuntimeError("run ID differs from run.json")
            observed: Dict[str, Tuple[str, int]] = {}
            for item in telemetry:
                access_id = str(item["attributes"]["AccessId"])
                if access_id in observed:
                    raise RuntimeError("duplicate AccessId: " + access_id)
                guid = normalize_guid(str(item["Guid"]))
                size = int(item["Size"])
                binary = base64.b64decode(item["Data"], validate=True)
                if len(binary) != size:
                    raise RuntimeError(
                        f"{access_id}: decoded length {len(binary)} != {size}"
                    )
                observed[access_id] = (guid, size)
            if observed != baseline:
                raise RuntimeError("bundle inventory differs from baseline")
            if not capture.get("Complete"):
                raise RuntimeError("capture marked incomplete")
            complete_files += 1
        except Exception as error:
            errors.append({"Filename": path.name, "Error": str(error)})

    expected_sequences = list(range(1, len(files) + 1))
    if sorted(sequences) != expected_sequences:
        errors.append(
            {
                "Filename": "run",
                "Error": (
                    f"sequence set {sorted(sequences)} does not equal "
                    f"{expected_sequences}"
                ),
            }
        )
    orphan_manifest = sorted(set(manifest) - {path.name for path in files})
    if orphan_manifest:
        errors.append(
            {
                "Filename": "manifest.ndjson",
                "Error": f"manifest entries without files: {orphan_manifest}",
            }
        )
    report = {
        "FormatVersion": FORMAT_VERSION,
        "VerifiedAt": utc_now(),
        "RunId": state.get("RunId"),
        "Endpoint": state.get("Endpoint"),
        "RequestedSamples": state.get("RequestedSamples"),
        "ObservedFiles": len(files),
        "CompleteFiles": complete_files,
        "InvalidFiles": len(files) - complete_files,
        "ManifestRecords": len(manifest_records),
        "AllObservedFilesValid": not errors,
        "RequestedSampleCountReached": (
            len(files) == int(state.get("RequestedSamples", 0))
        ),
        "Errors": errors,
        "RunUpdatedAt": state.get("UpdatedAt"),
    }
    if write_report:
        atomic_write_json(run_dir / "verification.json", report)
    return report


def command_inventory(args: argparse.Namespace) -> int:
    print(json.dumps(discover_inventory(args.sysfs_root), indent=2))
    return 0


def reconcile_run(run_dir: Path, state: Dict[str, Any]) -> int:
    records = []
    baseline = {item["AccessId"]: (item["Guid"], item["Size"]) for item in state["Inventory"]}
    for path in sorted((run_dir / "snapshots").glob("bulk-*.json.gz")):
        document = read_bundle(path)
        capture = document["Capture"]
        if (document.get("FormatVersion") != FORMAT_VERSION
                or capture["RunId"] != state["RunId"]
                or capture["Endpoint"] != state["Endpoint"]):
            raise RuntimeError(f"cannot resume foreign snapshot: {path.name}")
        if capture["Sequence"] != len(records) + 1:
            raise RuntimeError(f"cannot resume missing or duplicate sequence: {path.name}")
        observed = {}
        for item in document["TelemetryData"]:
            access_id = item["attributes"]["AccessId"]
            identity = (normalize_guid(item["Guid"]), int(item["Size"]))
            if access_id in observed or baseline.get(access_id) != identity:
                raise RuntimeError(f"cannot resume invalid inventory: {path.name}")
            if len(base64.b64decode(item["Data"], validate=True)) != identity[1]:
                raise RuntimeError(f"cannot resume invalid payload: {path.name}")
            observed[access_id] = identity
        if capture["Complete"] and observed != baseline:
            raise RuntimeError(f"cannot resume incomplete inventory: {path.name}")
        records.append({
            "Sequence": capture["Sequence"], "Filename": path.name,
            "CompressedBytes": path.stat().st_size,
            "StartedAt": capture["StartedAt"], "FinishedAt": capture["FinishedAt"],
            "DurationMilliseconds": capture["DurationMilliseconds"],
            "ExpectedAggregators": len(baseline), "CapturedAggregators": len(observed),
            "Complete": capture["Complete"], "ErrorCount": len(capture["Errors"]),
        })
    if len(records) > int(state["RequestedSamples"]):
        raise RuntimeError("more snapshots than requested")
    encoded = "".join(json.dumps(record) + "\n" for record in records).encode("utf-8")
    atomic_write_bytes(run_dir / "manifest.ndjson", encoded)
    state["CompletedFiles"] = len(records)
    state["CompleteFiles"] = sum(bool(record["Complete"]) for record in records)
    state["IncompleteFiles"] = len(records) - state["CompleteFiles"]
    return len(records) + 1


def command_verify(args: argparse.Namespace) -> int:
    load_json(args.run_dir / "run.json")
    with run_lock(args.run_dir):
        report = verify_run(args.run_dir)
    print(json.dumps(report, indent=2))
    if not report["AllObservedFilesValid"]:
        return 1
    if args.require_complete and not report["RequestedSampleCountReached"]:
        return 1
    return 0


def command_dump(args: argparse.Namespace) -> int:
    with gzip.open(args.input, "rb") as source:
        shutil.copyfileobj(source, sys.stdout.buffer)
    return 0


def add_capture_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--endpoint", required=True, help="machine label, not a network address (required)")
    parser.add_argument("--run-id", help="unique experiment name (default: endpoint plus UTC timestamp)")
    parser.add_argument(
        "--sysfs-root", type=Path, default=DEFAULT_SYSFS,
        help="PMT device directory (default: /sys/class/intel_pmt)",
    )
    parser.add_argument(
        "--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT,
        help="parent directory for results (default: ./results)",
    )
    parser.add_argument("--metadata", type=Path, help="optional metadata path to record; not needed for raw capture")
    parser.add_argument("--expected-aggregators", type=int, help="require this many PMT regions (default: discover automatically)")
    parser.add_argument("--interval-seconds", type=float, default=60.0, help="seconds between sample starts (default: 60; positive decimals allowed)")
    parser.add_argument("--samples", type=int, default=600, help="planned number of samples; pmt-capture start requires an explicit positive count")
    parser.add_argument("--align-minute", action="store_true", help="delay the first sample until the next minute (default: immediate)")
    parser.add_argument("--resume", action="store_true", help="legacy run command only; with pmt-capture use resume --run-dir")
    parser.add_argument("--experiment", default="", help="optional experiment label saved with the run")
    parser.add_argument("--workload", default="", help="optional workload label; does not launch a workload")
    parser.add_argument("--note", default="", help="optional free-text note saved with the run")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Capture and verify decode-later local Intel PMT bulk files"
    )
    parser.add_argument("--version", action="version", version=TOOL_VERSION)
    commands = parser.add_subparsers(dest="command", required=True)

    inventory = commands.add_parser(
        "inventory", help="print current telem/GUID/Size inventory"
    )
    inventory.add_argument(
        "--sysfs-root", type=Path, default=DEFAULT_SYSFS
    )
    inventory.set_defaults(handler=command_inventory)

    run = commands.add_parser(
        "run", help="capture a fixed number of aligned interval samples"
    )
    add_capture_arguments(run)
    run.set_defaults(handler=run_capture)

    verify = commands.add_parser(
        "verify", help="verify files, sizes and baseline inventory"
    )
    verify.add_argument("run_dir", type=Path)
    verify.add_argument("--require-complete", action="store_true")
    verify.set_defaults(handler=command_verify)

    dump = commands.add_parser(
        "dump", help="decompress one bulk JSON to stdout for offline decoding"
    )
    dump.add_argument("input", type=Path)
    dump.set_defaults(handler=command_dump)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.handler(args))
    except (OSError, RuntimeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
