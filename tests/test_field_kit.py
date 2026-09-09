import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class FieldKitTest(unittest.TestCase):
    def test_existing_config_does_not_change_new_plan(self):
        script = '''
source field-kit/lib/common.sh
source field-kit/lib/schedule.sh
load_active_config() { PMT_INTERVAL_SECONDS=60; PMT_SAMPLES=600; PMT_RUN_ID=old; }
python3() { printf '1 600\n'; }
PMT_INTERVAL_SECONDS=10
PMT_SAMPLES=3
progress="$(active_progress)"
apply_env_plan
[[ "$progress" == "1 600" && "$PMT_PLAN_INTERVAL" == 10 && "$PMT_PLAN_SAMPLES" == 3 ]]
'''
        result = subprocess.run(["bash", "-euc", script], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_hours_conversion_rejects_invalid_values(self):
        for hours, interval, expected in [("0.5", "60", 0), ("nan", "60", 1), ("-1", "60", 1), ("1", "0", 1)]:
            result = subprocess.run(
                ["bash", "-c", 'source field-kit/lib/schedule.sh; samples_for_hours "$1" "$2"',
                 "test", hours, interval], cwd=ROOT, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, expected, result.stderr)
            if expected == 0:
                self.assertEqual(result.stdout.strip(), "30")

    @unittest.skipUnless(os.geteuid() == 0, "menu requires root")
    def test_menu_continues_after_failed_action(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copy(ROOT / "run.sh", root / "run.sh")
            (root / "field-kit").mkdir()
            script = root / "field-kit" / "show-progress.sh"
            script.write_text("#!/bin/sh\nexit 1\n")
            script.chmod(0o755)
            result = subprocess.run(["bash", str(root / "run.sh")], input="2\n7\n",
                                    capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.count("7)"), 2)

    def test_script_help_does_not_require_input(self):
        for script in ("run.sh", "install.sh", "uninstall.sh"):
            for option in ("--help", "-h"):
                with self.subTest(script=script, option=option):
                    result = subprocess.run(
                        ["bash", str(ROOT / script), option], input="",
                        capture_output=True, text=True, timeout=5,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("help", result.stdout.lower())

    def test_uninstall_rejects_unknown_arguments(self):
        with tempfile.TemporaryDirectory() as directory:
            environment = dict(os.environ, PATH=directory)
            for arguments in (["--unknown"], ["--yes", "--unknown"]):
                with self.subTest(arguments=arguments):
                    result = subprocess.run(
                        [shutil.which("bash"), str(ROOT / "uninstall.sh")] + arguments, input="",
                        capture_output=True, text=True, timeout=5, env=environment,
                    )
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertIn("Usage:", result.stderr)

    def test_shell_syntax(self):
        paths = list(ROOT.glob("*.sh")) + list((ROOT / "field-kit").rglob("*.sh")) + [ROOT / "pmt-capture"]
        for path in paths:
            with self.subTest(path=path):
                result = subprocess.run(["bash", "-n", str(path)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)