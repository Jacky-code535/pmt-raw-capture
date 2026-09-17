#!/usr/bin/env python3
"""Engineer-oriented commands for local raw PMT collection."""

from __future__ import annotations

import argparse
import fcntl
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
from typing import Optional

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pmt.capture import sampler as capture


def bundled_metadata() -> Optional[Path]:
    candidate = Path(__file__).resolve().parents[2] / "bundled-platform-data" / "xml" / "pmt.xml"
    return candidate if candidate.is_file() else None


def is_busy(run_dir: Path) -> bool:
    path = run_dir / ".capture.lock"
    if not path.exists():
        return False
    with path.open("r") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
    return False


def run_state(run_dir: Path) -> dict:
    state = capture.load_json(run_dir / "run.json")
    if state["RunId"] != run_dir.name:
        raise RuntimeError("run directory name must match RunId")
    return state


def saved_args(run_dir: Path) -> argparse.Namespace:
    state = run_state(run_dir)
    return argparse.Namespace(
        endpoint=state["Endpoint"], run_id=state["RunId"],
        output_root=run_dir.parent, sysfs_root=Path(state["SysfsRoot"]),
        interval_seconds=float(state["IntervalSeconds"]), samples=int(state["RequestedSamples"]),
        expected_aggregators=len(state["Inventory"]), metadata=None,
        cpu=state.get("CollectorCPU"),
        resume=True, align_minute=False,
    )


def launch(args: argparse.Namespace, background: bool) -> int:
    if not background:
        return capture.run_capture(args)
    if not args.run_id:
        args.run_id = args.endpoint.lower() + "-" + capture.filename_time()
    capture.validate_identifier(args.run_id, "run-id")
    run_dir = args.output_root.resolve() / args.run_id
    if not args.resume:
        with capture.run_lock(run_dir):
            capture.prepare_run(args)
    elif is_busy(run_dir):
        raise RuntimeError("run is already collecting")
    command = [sys.executable, str(Path(__file__).resolve()), "resume", "--run-dir", str(run_dir)]
    if args.align_minute:
        command.append("--align-minute")
    with (run_dir / "console.log").open("a", encoding="utf-8") as output:
        process = subprocess.Popen(
            command, stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
            start_new_session=True, close_fds=True,
        )
    deadline = time.monotonic() + 10
    while True:
        returncode = process.poll()
        if returncode is not None:
            if returncode:
                raise RuntimeError("background collector failed; see " + str(run_dir / "console.log"))
            break
        state = run_state(run_dir)
        if state.get("Pid") == process.pid and is_busy(run_dir):
            break
        if time.monotonic() >= deadline:
            process.terminate()
            raise RuntimeError("background collector startup timed out; see " + str(run_dir / "console.log"))
        time.sleep(0.02)
    print(f"Launched PID {process.pid}; run directory: {run_dir}")
    print("Use status to check startup; background mode does not restart after reboot.")
    return 0


def status_report(run_dir: Path, *, locked: bool = False) -> dict:
    state = run_state(run_dir)
    busy = False if locked else is_busy(run_dir)
    status = state["Status"]
    if status == "running" and not busy:
        status = "interrupted"
    verification = "not_checked"
    report_path = run_dir / "verification.json"
    if report_path.exists():
        report = capture.load_json(report_path)
        if busy or report.get("RunUpdatedAt") != state.get("UpdatedAt"):
            verification = "stale"
        else:
            verification = "passed" if (
                report["AllObservedFilesValid"] and report["RequestedSampleCountReached"]
            ) else "failed"
    return {
        "run_id": state["RunId"], "endpoint": state["Endpoint"],
        "collection": status, "busy": busy,
        "completed": state["CompletedFiles"], "requested": state["RequestedSamples"],
        "complete": state["CompleteFiles"], "incomplete": state["IncompleteFiles"],
        "interval_seconds": state["IntervalSeconds"], "verification": verification,
        "last_error": state.get("LastError", ""), "run_dir": str(run_dir),
    }


def stop_run(run_dir: Path, wait_seconds: float = 0) -> int:
    if not math.isfinite(wait_seconds) or wait_seconds < 0:
        raise ValueError("stop wait must be finite and nonnegative")
    state = run_state(run_dir)
    if not is_busy(run_dir):
        print("No active collector for this run.")
        return 0
    pid = int(state.get("Pid", 0))
    if pid <= 1 or state.get("ProcessBootId") != capture.machine_facts()["BootId"]:
        raise RuntimeError("collector process identity unavailable; use its service manager")
    if capture.process_start(pid) != state.get("ProcessStart"):
        raise RuntimeError("collector PID has changed; refusing to signal another process")
    os.kill(pid, signal.SIGTERM)
    if wait_seconds:
        deadline = time.monotonic() + wait_seconds
        while is_busy(run_dir):
            if time.monotonic() >= deadline:
                raise RuntimeError("collector has not stopped before the timeout")
            time.sleep(0.05)
        print("Collector stopped.")
        return 0
    print("Stop requested. Use status to confirm the collector has stopped.")
    return 0


def pack_run(run_dir: Path, output_dir: Path, allow_partial: bool) -> int:
    run_state(run_dir)
    output_dir = output_dir.resolve()
    if output_dir == run_dir or run_dir in output_dir.parents:
        raise ValueError("output directory must be outside the run directory")
    with capture.run_lock(run_dir):
        paths = [run_dir / name for name in (
            "run.json", "manifest.ndjson", "verification.json", "result.json",
            "result.txt", "collector.log", "console.log",
        )]
        snapshots_dir = run_dir / "snapshots"
        paths.extend(sorted(snapshots_dir.glob("bulk-*.json.gz")))
        for path in [snapshots_dir] + paths:
            if path.is_symlink():
                raise RuntimeError(f"cannot pack symbolic link: {path}; restore regular files first")
        report = capture.verify_run(run_dir)
        complete = report["AllObservedFilesValid"] and report["RequestedSampleCountReached"]
        if not complete and not allow_partial:
            raise RuntimeError("verification failed; use --allow-partial to export diagnostic data")
        result = {"collection_complete": complete, "verification": report, "status": status_report(run_dir, locked=True)}
        capture.atomic_write_json(run_dir / "result.json", result)
        capture.atomic_write_bytes(run_dir / "result.txt", (
            f"Run: {run_dir.name}\nCollection: {'COMPLETE' if complete else 'INCOMPLETE'}\n"
            f"Snapshots: {report['ObservedFiles']}/{report['RequestedSamples']}\n"
            "This result describes collection, not hardware health.\n"
        ).encode("utf-8"))
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = "" if complete else "-partial"
        archive = output_dir / f"pmt-capture-{run_dir.name}{suffix}.tar.gz"
        if archive.exists():
            raise FileExistsError(f"archive already exists: {archive}; choose another output directory")
        descriptor, temporary_name = tempfile.mkstemp(dir=str(output_dir), suffix=".tmp")
        os.close(descriptor)
        temporary = Path(temporary_name)
        try:
            with tarfile.open(str(temporary), "w:gz") as bundle:
                for path in paths:
                    if path.is_symlink():
                        raise RuntimeError(f"cannot pack symbolic link: {path}")
                    if path.is_file():
                        bundle.add(str(path), arcname=str(Path(run_dir.name) / path.relative_to(run_dir)))
            os.replace(str(temporary), str(archive))
        finally:
            if temporary.exists():
                temporary.unlink()
    print(archive)
    return 0


def build_parser() -> argparse.ArgumentParser:
    default_metadata = bundled_metadata()
    parser = argparse.ArgumentParser(prog="pmt-capture", description="Capture raw Linux PMT locally; decode after experiments.")
    parser.add_argument("--version", action="version", version=capture.TOOL_VERSION)
    commands = parser.add_subparsers(dest="command")
    inventory = commands.add_parser("inventory", help="discover PMT regions")
    inventory.add_argument("--sysfs-root", type=Path, default=capture.DEFAULT_SYSFS, help="PMT device directory (default: /sys/class/intel_pmt)")
    start = commands.add_parser("start", help="start a foreground capture (no installation)")
    capture.add_capture_arguments(start)
    start.add_argument("--config", type=Path, help="JSON capture settings; explicit CLI values override settings")
    start.set_defaults(samples=None)
    start.add_argument("--interval", dest="interval_seconds", type=float, default=argparse.SUPPRESS, help="alias for --interval-seconds (default: 60)")
    start.add_argument("--background", action="store_true", help="detach; does not survive reboot")
    descriptions = {
        "status": "show progress, running state and last verification result",
        "stop": "request a stop without deleting collected data",
        "resume": "collect remaining samples using the saved settings",
        "verify": "check saved snapshots and the planned sample count",
        "pack": "verify and export a result archive for sharing",
    }
    for name, description in descriptions.items():
        command = commands.add_parser(name, help=description, description=description)
        command.add_argument("--run-dir", required=True, type=Path, help="existing run directory, e.g. ./results/trial-001")
        if name == "status":
            command.add_argument("--json", action="store_true", help="print machine-readable JSON")
        if name == "stop":
            command.add_argument("--wait-seconds", type=float, default=0, help="wait for the collector lock to be released (default: return immediately)")
        if name == "resume":
            command.add_argument("--background", action="store_true", help="detach from the terminal; no automatic reboot recovery")
            command.add_argument("--align-minute", action="store_true", help="wait until the next minute only if no samples have been saved yet")
        if name == "verify":
            command.add_argument("--allow-partial", action="store_true", help="accept fewer samples than planned; all saved samples must still be valid")
        if name == "pack":
            command.add_argument("--output", type=Path, default=Path("output"), help="archive destination outside the run directory (default: ./output)")
            command.add_argument("--allow-partial", action="store_true", help="allow an incomplete or invalid capture to be exported for diagnosis")
    dump = commands.add_parser("dump", help="print a snapshot as JSON; does not decode PMT metrics")
    dump.add_argument("input", type=Path, help="path to one snapshots/bulk-*.json.gz file")
    archive = commands.add_parser("archive", help="export immutable offline raw layout with per-sample binaries")
    archive.add_argument("--run-dir", required=True, type=Path)
    archive.add_argument("--output", required=True, type=Path)
    archive.add_argument("--allow-partial", action="store_true")
    unpack = commands.add_parser("unpack", help="safely decompress and verify a capture archive")
    unpack.add_argument("input", type=Path)
    unpack.add_argument("--output", required=True, type=Path)
    platform = commands.add_parser("validate-platform", help="validate exact XML coverage for a run or entire registry")
    platform.add_argument("--metadata", required=default_metadata is None, type=Path,
                          default=default_metadata, help="PMT XML registry path (default: bundled registry when present)")
    platform.add_argument("--run-dir", type=Path)
    analyze = commands.add_parser("analyze", help="decode saved raw data using exact platform XML")
    analyze.add_argument("--run-dir", required=True, type=Path)
    analyze.add_argument("--output", required=True, type=Path)
    analyze.add_argument("--metadata", required=default_metadata is None, type=Path,
                         default=default_metadata, help="PMT XML registry path (default: bundled registry when present)")
    analyze.add_argument("--decoder", type=Path, help="optional legacy external decoder; default: built-in Python decoder")
    analyze.add_argument("--policies", type=Path, help="JSON metric counter/invalid-value policies")
    analyze.add_argument("--topology", type=Path, help="CSV endpoint,aggregator,metric,system,socket,die,module")
    analyze.add_argument("--events", type=Path, help="CSV start,end,phase,test_item,status,failure_time; ISO timestamps with offsets")
    analyze.add_argument("--event-offset-seconds", type=float, default=0.0)
    analyze.add_argument("--failure-before", type=float, default=5.0)
    analyze.add_argument("--failure-after", type=float, default=5.0)
    analyze.add_argument("--allow-partial", action="store_true")
    compare = commands.add_parser("compare", help="compare matching series in two offline analysis summaries")
    compare.add_argument("--baseline", required=True, type=Path, help="baseline analysis directory")
    compare.add_argument("--candidate", required=True, type=Path, help="candidate analysis directory")
    compare.add_argument("--output", required=True, type=Path, help="new CSV path")
    compare.add_argument("--by-test", action="store_true", help="match phase and test item instead of whole-run statistics")
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "start":
        preliminary = argparse.ArgumentParser(add_help=False)
        preliminary.add_argument("--config", type=Path)
        settings, _ = preliminary.parse_known_args(argv[1:])
        if settings.config:
            from pmt.capture.config import arguments
            try:
                argv = ["start"] + arguments(settings.config) + argv[1:]
            except (OSError, ValueError) as error:
                parser.error(str(error))
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0
    try:
        if args.command == "inventory":
            return capture.command_inventory(args)
        if args.command == "dump":
            return capture.command_dump(args)
        if args.command == "unpack":
            from pmt.export.archive import unpack_archive
            print(json.dumps(unpack_archive(args.input, args.output), indent=2))
            return 0
        if args.command == "validate-platform":
            from pmt.decode.platform_data import validate
            report = validate(args.metadata, args.run_dir)
            print(json.dumps(report, indent=2))
            return 0 if report["valid"] else 1
        if args.command == "start":
            if args.samples is None or args.samples <= 0:
                parser.error("start requires --samples with a positive count")
            if not math.isfinite(args.interval_seconds) or args.interval_seconds <= 0:
                parser.error("--interval must be finite and positive")
            if args.resume:
                parser.error("use resume --run-dir instead of start --resume")
            return launch(args, args.background)
        if args.command in ("archive", "analyze", "compare"):
            import pmt_postprocess as postprocess
            if args.command == "archive":
                result = postprocess.archive_run(args.run_dir.resolve(), args.output, args.allow_partial)
            elif args.command == "analyze":
                result = postprocess.analyze_run(args)
            else:
                result = postprocess.compare_runs(args)
            print(json.dumps(result, indent=2))
            return 0
        run_dir = args.run_dir.resolve()
        run_state(run_dir)
        if args.command == "resume":
            resumed = saved_args(run_dir)
            resumed.align_minute = args.align_minute
            return launch(resumed, args.background)
        if args.command == "status":
            report = status_report(run_dir)
            if args.json:
                print(json.dumps(report, indent=2))
            else:
                for key, value in report.items():
                    print(f"{key}: {value}")
            return 0
        if args.command == "stop":
            return stop_run(run_dir, args.wait_seconds)
        if args.command == "pack":
            return pack_run(run_dir, args.output, args.allow_partial)
        with capture.run_lock(run_dir):
            report = capture.verify_run(run_dir)
        print(json.dumps(report, indent=2))
        return 0 if report["AllObservedFilesValid"] and (
            args.allow_partial or report["RequestedSampleCountReached"]
        ) else 1
    except (OSError, RuntimeError, ValueError, KeyError, EOFError, tarfile.TarError, subprocess.TimeoutExpired) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())