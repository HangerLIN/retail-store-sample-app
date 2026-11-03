"""Run the actual CI shell orchestration against isolated fake external commands."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest


class CiTests(unittest.TestCase):
    def run_build(self, fail):
        source = Path(__file__).resolve().parents[1] / "scripts/ci.sh"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scripts = root / "learning/scripts"
            scripts.mkdir(parents=True)
            shutil.copy(source, scripts / "ci.sh")
            (root / "bin").mkdir()
            (root / "python/bin").mkdir(parents=True)
            (root / "python/bin/python").symlink_to(os.sys.executable)
            (root / "release.kubeconfig").write_text("fake-only")
            (scripts / "environment.sh").write_text('export LAB_HOME="$PWD"\nexport KUBECONFIG="$PWD/release.kubeconfig"\nexport PATH="$PWD/bin:/usr/bin:/bin:/usr/sbin:/sbin"\n')
            (scripts / "test-build.sh").write_text('echo "test:$1" >> calls\n[ "$1" != "$FAIL_SERVICE" ]\n')
            (scripts / "image.sh").write_text('echo "push:$1" >> calls\n')
            commands = {
                "git": "echo test-sha",
                "docker": "exit 0",
                "kubectl": "echo '{\"items\":[]}'",
                "memory_pressure": "exit 0",
                "sysctl": "exit 0",
            }
            for name, body in commands.items():
                p = root / "bin" / name
                p.write_text("#!/bin/sh\n" + body + "\n")
                p.chmod(0o755)
            run = subprocess.run(["/bin/bash", str(scripts / "ci.sh"), "build"], cwd=root,
                                 env=dict(os.environ, FAIL_SERVICE=fail), capture_output=True, text=True, timeout=20)
            return run.returncode, (root / "calls").read_text().splitlines()

    def test_failure_in_any_suite_prevents_all_pushes(self):
        for service in ("orders", "checkout", "carts", "catalog", "ui"):
            with self.subTest(service=service):
                code, calls = self.run_build(service)
                self.assertNotEqual(code, 0)
                self.assertFalse(any(c.startswith("push:") for c in calls))

    def test_all_tests_finish_before_first_push(self):
        code, calls = self.run_build("")
        self.assertEqual(code, 0)
        self.assertEqual(calls, [f"{stage}:{service}" for stage in ("test", "push")
                                for service in ("orders", "checkout", "carts", "catalog", "ui")])


if __name__ == "__main__":
    unittest.main()
