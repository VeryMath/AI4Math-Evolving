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


if __name__ == "__main__":
    unittest.main()
