import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "openevolve-experiment-workflow" / "scripts" / "summarize_run.py"


class SummarizeRunTests(unittest.TestCase):
    def test_best_program_info_summary(self):
        with tempfile.TemporaryDirectory() as td:
            run = Path(td)
            best = run / "best"
            best.mkdir()
            (best / "best_program_info.json").write_text(
                json.dumps({"metrics": {"combined_score": 2.5}, "id": "abc"}),
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(run), "--json"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["bestMetrics"]["combined_score"], 2.5)
            self.assertEqual(payload["bestProgramInfoPath"], str(best / "best_program_info.json"))


if __name__ == "__main__":
    unittest.main()
