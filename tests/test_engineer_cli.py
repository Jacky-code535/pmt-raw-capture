import contextlib
import io
import json
from pathlib import Path
import selectors
import subprocess
import sys
import tarfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import pmt_capture_cli as cli
import pmt_bulk_capture as capture
import test_pmt_bulk_capture as fixtures


class EngineerCliTest(unittest.TestCase):
    setUp = fixtures.PmtBulkCaptureTest.setUp
    tearDown = fixtures.PmtBulkCaptureTest.tearDown
    _args = fixtures.PmtBulkCaptureTest._args
    _add_telem = fixtures.PmtBulkCaptureTest._add_telem

    def start(self, name="cli"):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main([
                "start", "--endpoint", "test-host", "--run-id", name,
                "--sysfs-root", str(self.sysfs), "--output-root", str(self.output),
                "--interval", "0.01", "--samples", "3",
            ]), 0)
        return self.output / name

    def test_status_verify_pack(self):
        run_dir = self.start()
        self.assertEqual(cli.status_report(run_dir)["verification"], "not_checked")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["verify", "--run-dir", str(run_dir)]), 0)
            self.assertEqual(cli.main(["pack", "--run-dir", str(run_dir), "--output", str(self.root / "export")]), 0)
        self.assertEqual(cli.status_report(run_dir)["verification"], "passed")
        archive = next((self.root / "export").glob("*.tar.gz"))
        with tarfile.open(archive) as bundle:
            self.assertIn("cli/collector.log", bundle.getnames())
            self.assertEqual(len([name for name in bundle.getnames() if "/snapshots/" in name]), 3)

    def test_recover_orphan_snapshot(self):
        run_dir = self.start()
        (run_dir / "manifest.ndjson").write_text("broken trailing record")
        state = capture.load_json(run_dir / "run.json")
        state["CompleteFiles"] = 0
        capture.atomic_write_json(run_dir / "run.json", state)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["resume", "--run-dir", str(run_dir)]), 0)
        self.assertEqual(capture.load_json(run_dir / "run.json")["CompleteFiles"], 3)
        self.assertTrue(capture.verify_run(run_dir)["AllObservedFilesValid"])

    def test_busy_run_cannot_resume_or_pack(self):
        run_dir = self.start()
        with capture.run_lock(run_dir), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cli.main(["resume", "--run-dir", str(run_dir)]), 1)
            self.assertEqual(cli.main(["pack", "--run-dir", str(run_dir)]), 1)

    def test_stale_verification(self):
        run_dir = self.start()
        capture.verify_run(run_dir)
        state = capture.load_json(run_dir / "run.json")
        state["UpdatedAt"] = "changed"
        capture.atomic_write_json(run_dir / "run.json", state)
        self.assertEqual(cli.status_report(run_dir)["verification"], "stale")

    def test_missing_sequence_is_not_filled(self):
        run_dir = self.start()
        next((run_dir / "snapshots").glob("bulk-000002-*")).unlink()
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cli.main(["resume", "--run-dir", str(run_dir)]), 1)
        self.assertEqual(len(list((run_dir / "snapshots").glob("*.gz"))), 2)

    def test_start_requires_samples(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            cli.main(["start", "--endpoint", "test"])
        self.assertEqual(raised.exception.code, 2)

    def test_command_help_explains_actions(self):
        parser = cli.build_parser()
        help_text = parser.format_help()
        for description in (
            "show progress", "request a stop", "collect remaining samples",
            "check saved snapshots", "verify and export", "does not decode",
        ):
            self.assertIn(description, help_text)
        for command in ("status", "stop", "resume", "verify", "pack", "dump"):
            with self.subTest(command=command):
                output = io.StringIO()
                with contextlib.redirect_stdout(output), self.assertRaises(SystemExit) as raised:
                    cli.main([command, "--help"])
                self.assertEqual(raised.exception.code, 0)
                self.assertIn("path to one" if command == "dump" else "existing run directory", output.getvalue())

    def test_release_version_consistency(self):
        root = Path(cli.__file__).resolve().parents[1]
        version = (root / "VERSION").read_text().strip()
        self.assertEqual(capture.TOOL_VERSION, version)
        for name in ("README.md", "docs/data-format.md", "docs/development.md",
                 "docs/service.md", "docs/changelog.md"):
            with self.subTest(document=name):
                self.assertIn(version, (root / name).read_text(encoding="utf-8"))

    def test_shell_entrypoint_workflow(self):
        entrypoint = Path(cli.__file__).resolve().parents[1] / "pmt-capture"

        def invoke(*arguments):
            result = subprocess.run(
                [str(entrypoint)] + list(arguments), capture_output=True,
                text=True, timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            return result.stdout

        inventory = json.loads(invoke("inventory", "--sysfs-root", str(self.sysfs)))
        self.assertTrue(inventory)
        invoke("start", "--endpoint", "test-host", "--run-id", "entrypoint",
               "--sysfs-root", str(self.sysfs), "--output-root", str(self.output),
               "--interval", "0.01", "--samples", "3")
        run_dir = self.output / "entrypoint"
        report = json.loads(invoke("status", "--run-dir", str(run_dir), "--json"))
        self.assertEqual(report["completed"], 3)
        self.assertEqual(report["collection"], "completed")
        archive = Path(invoke("pack", "--run-dir", str(run_dir),
                              "--output", str(self.root / "handoff")).strip())
        self.assertTrue(archive.is_file())
        snapshot = next((run_dir / "snapshots").glob("*.json.gz"))
        self.assertEqual(json.loads(invoke("dump", str(snapshot)))["Capture"]["RunId"], "entrypoint")
        self.assertEqual(invoke("--version").strip(), (entrypoint.parent / "VERSION").read_text().strip())

    def test_background_launch_uses_saved_run(self):
        processes = []
        original_spawn = subprocess.Popen

        def spawn_process(*args, **kwargs):
            process = original_spawn(*args, **kwargs)
            processes.append(process)
            return process

        try:
            with mock.patch.object(cli.subprocess, "Popen", side_effect=spawn_process) as spawn:
                args = self._args("background")
                with contextlib.redirect_stdout(io.StringIO()):
                    cli.launch(args, True)
            self.assertIn("resume", spawn.call_args[0][0])
            self.assertTrue(spawn.call_args[1]["start_new_session"])
            self.assertEqual(processes[0].wait(timeout=5), 0)
            run_dir = self.output / "background"
            self.assertEqual(cli.status_report(run_dir)["collection"], "completed")
            self.assertIn('"sequence":1', (run_dir / "console.log").read_text())
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                process.wait()

    def test_process_stop_and_resume_saved_schedule(self):
        command = [sys.executable, str(Path(cli.__file__)), "start",
                   "--endpoint", "test-host", "--run-id", "process",
                   "--sysfs-root", str(self.sysfs), "--output-root", str(self.output),
                   "--interval", "60", "--samples", "2"]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                self.assertTrue(selector.select(timeout=5), "collector did not publish first snapshot")
            self.assertIn('"sequence":1', process.stdout.readline())
            run_dir = self.output / "process"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(cli.stop_run(run_dir), 0)
            stdout, stderr = process.communicate(timeout=5)
            self.assertEqual(process.returncode, 0, stderr)
            self.assertEqual(cli.status_report(run_dir)["collection"], "stopped")
            resumed = subprocess.run(
                [sys.executable, str(Path(cli.__file__)), "resume", "--run-dir", str(run_dir)],
                capture_output=True, text=True, timeout=5,
            )
            self.assertEqual(resumed.returncode, 0, resumed.stderr)
            self.assertEqual(cli.status_report(run_dir)["completed"], 2)
            self.assertEqual(cli.status_report(run_dir)["interval_seconds"], 60)
        finally:
            if process.poll() is None:
                process.kill()
            process.communicate()

    def test_partial_export_with_torn_manifest(self):
        run_dir = self.start()
        (run_dir / "manifest.ndjson").write_text("torn")
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cli.main(["pack", "--run-dir", str(run_dir)]), 1)
            self.assertEqual(cli.main(["pack", "--run-dir", str(run_dir), "--allow-partial",
                                       "--output", str(self.root / "partial")]), 0)
        self.assertTrue(next((self.root / "partial").glob("*-partial.tar.gz")))

    def test_pack_rejects_symbolic_links(self):
        for target in ("snapshot", "snapshots", "run.json", "collector.log", "result.txt"):
            with self.subTest(target=target):
                run_dir = self.start("link-" + target.replace(".", "-"))
                if target == "snapshot":
                    path = next((run_dir / "snapshots").glob("*.json.gz"))
                else:
                    path = run_dir / target
                relocated = self.root / (run_dir.name + "-original")
                if path.exists():
                    path.rename(relocated)
                path.symlink_to(relocated)
                output_dir = self.root / (run_dir.name + "-export")
                for extra_args in ([], ["--allow-partial"]):
                    error = io.StringIO()
                    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(error):
                        result = cli.main(["pack", "--run-dir", str(run_dir),
                                           "--output", str(output_dir)] + extra_args)
                    self.assertEqual(result, 1)
                    self.assertIn("symbolic link", error.getvalue())
                    self.assertFalse(list(output_dir.glob("*.tar.gz")))