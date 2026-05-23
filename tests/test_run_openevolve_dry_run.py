import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "openevolve-coding-agent" / "scripts" / "run_openevolve.py"


class RunOpenEvolveDryRunTests(unittest.TestCase):
    def test_opencode_dry_run_command(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    str(project),
                    "--mode",
                    "opencode",
                    "--iterations",
                    "7",
                    "--checkpoint-interval",
                    "2",
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
            self.assertEqual(payload["mode"], "opencode")
            self.assertIn("opencode", payload["command"][0])
            self.assertIn("iterations: 7", payload["prompt"])
            self.assertIn("checkpoint_interval: 2", payload["prompt"])

    def test_prompt_accepts_language_and_extra_parameters(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    str(project),
                    "--mode",
                    "opencode",
                    "--iterations",
                    "7",
                    "--checkpoint-interval",
                    "2",
                    "--language",
                    "zh-CN",
                    "--extra",
                    "num_islands=3",
                    "--extra",
                    "mutation_rate=0.2",
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
            self.assertIn("所有自然语言回复必须使用简体中文", payload["prompt"])
            self.assertIn("num_islands: 3", payload["prompt"])
            self.assertIn("mutation_rate: 0.2", payload["prompt"])

    def test_direct_dry_run_builds_openevolve_run_command(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            (project / "initial_program.py").write_text("", encoding="utf-8")
            (project / "evaluator.py").write_text("", encoding="utf-8")
            (project / "config.yaml").write_text("", encoding="utf-8")
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
