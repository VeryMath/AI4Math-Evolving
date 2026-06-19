import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "openevolve-experiment-workflow" / "scripts" / "run_openevolve.py"


class RunOpenEvolveDryRunTests(unittest.TestCase):
    def make_project(self, root: Path) -> None:
        (root / "initial_program.py").write_text("", encoding="utf-8")
        (root / "evaluator.py").write_text("", encoding="utf-8")
        (root / "config.yaml").write_text("", encoding="utf-8")

    def test_default_dry_run_uses_direct_openevolve_command(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            self.make_project(project)
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    str(project),
                    "--iterations",
                    "7",
                    "--dry-run",
                    "--json",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["mode"], "direct")
            self.assertEqual(payload["command"][0], "openevolve-run")

    def test_opencode_mode_is_not_supported_in_skill_layer(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            self.make_project(project)
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    str(project),
                    "--mode",
                    "opencode",
                    "--dry-run",
                    "--json",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("invalid choice", result.stderr)

    def test_direct_dry_run_builds_openevolve_run_command(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            self.make_project(project)
            output = project / "out"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    str(project),
                    "--mode",
                    "direct",
                    "--iterations",
                    "7",
                    "--output-dir",
                    str(output),
                    "--extra",
                    "api_base=https://example.invalid/v1",
                    "--extra",
                    "primary_model=test-model",
                    "--dry-run",
                    "--json",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["mode"], "direct")
            command = payload["command"]
            self.assertEqual(command[0], "openevolve-run")
            self.assertIn(str((project / "initial_program.py").resolve()), command)
            self.assertIn(str((project / "evaluator.py").resolve()), command)
            self.assertIn("--config", command)
            self.assertIn(str((project / "config.yaml").resolve()), command)
            self.assertIn("--output", command)
            self.assertIn(str(output.resolve()), command)
            self.assertIn("--api-base", command)
            self.assertIn("https://example.invalid/v1", command)


if __name__ == "__main__":
    unittest.main()
