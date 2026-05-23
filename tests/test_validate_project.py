import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "openevolve-coding-agent" / "scripts" / "validate_project.py"


class ValidateProjectTests(unittest.TestCase):
    def make_project(self, root: Path) -> None:
        (root / "initial_program.py").write_text(
            "# EVOLVE-BLOCK-START\n"
            "def search():\n"
            "    return 1\n"
            "# EVOLVE-BLOCK-END\n\n"
            "def run_search():\n"
            "    return search()\n",
            encoding="utf-8",
        )
        (root / "evaluator.py").write_text(
            "def evaluate(program_path):\n"
            "    return {'metrics': {'combined_score': 1.0}}\n",
            encoding="utf-8",
        )
        (root / "config.yaml").write_text(
            "max_iterations: 3\n"
            "checkpoint_interval: 1\n"
            "llm:\n"
            "  api_key: \"${LLM_API_KEY}\"\n",
            encoding="utf-8",
        )

    def run_validator(self, project: Path) -> dict:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), str(project), "--json"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_valid_project(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            self.make_project(project)
            payload = self.run_validator(project)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["errors"], [])

    def test_missing_evaluator_fails(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            self.make_project(project)
            (project / "evaluator.py").unlink()
            payload = self.run_validator(project)
            self.assertFalse(payload["ok"])
            self.assertIn("missing evaluator.py", [e["message"] for e in payload["errors"]])

    def test_plaintext_key_fails(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            self.make_project(project)
            (project / "config.yaml").write_text(
                "max_iterations: 3\ncheckpoint_interval: 1\napi_key: \"sk-real-secret-value\"\n",
                encoding="utf-8",
            )
            payload = self.run_validator(project)
            self.assertFalse(payload["ok"])
            self.assertIn(
                "config.yaml contains a plaintext api_key",
                [e["message"] for e in payload["errors"]],
            )


if __name__ == "__main__":
    unittest.main()
