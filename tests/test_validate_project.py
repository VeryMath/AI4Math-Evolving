import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "openevolve-experiment-workflow" / "scripts" / "validate_project.py"


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

    def run_validator(self, project: Path, env: Optional[dict[str, str]] = None) -> dict:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), str(project), "--json"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            env=env,
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
                "max_iterations: 3\ncheckpoint_interval: 1\napi_key: \"plain-text-test-key\"\n",
                encoding="utf-8",
            )
            payload = self.run_validator(project)
            self.assertFalse(payload["ok"])
            self.assertIn(
                "config.yaml contains a plaintext api_key",
                [e["message"] for e in payload["errors"]],
            )

    def test_config_yml_is_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            self.make_project(project)
            (project / "config.yml").write_text((project / "config.yaml").read_text(encoding="utf-8"), encoding="utf-8")
            (project / "config.yaml").unlink()
            payload = self.run_validator(project)
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["configPath"].endswith("config.yml"))

    def test_missing_api_key_config_warns_before_real_run(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            self.make_project(project)
            (project / "config.yaml").write_text(
                "max_iterations: 3\n"
                "checkpoint_interval: 1\n"
                "llm:\n"
                "  primary_model: ecnu-plus\n"
                "  api_base: https://chat.ecnu.edu.cn/open/api/v1\n",
                encoding="utf-8",
            )
            payload = self.run_validator(project)
            self.assertTrue(payload["ok"])
            self.assertIn("missing_llm_api_key_config", [w["code"] for w in payload["warnings"]])

    def test_unset_api_key_env_placeholder_warns(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            self.make_project(project)
            env = dict(os.environ)
            env.pop("AI4MATH_TEST_KEY", None)
            (project / "config.yaml").write_text(
                "max_iterations: 3\n"
                "checkpoint_interval: 1\n"
                "llm:\n"
                "  api_key: \"${AI4MATH_TEST_KEY}\"\n",
                encoding="utf-8",
            )
            payload = self.run_validator(project, env=env)
            self.assertTrue(payload["ok"])
            self.assertIn("missing_api_key_env", [w["code"] for w in payload["warnings"]])

    def test_set_api_key_env_placeholder_does_not_warn(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            self.make_project(project)
            env = dict(os.environ)
            env["AI4MATH_TEST_KEY"] = "present-but-not-printed"
            (project / "config.yaml").write_text(
                "max_iterations: 3\n"
                "checkpoint_interval: 1\n"
                "llm:\n"
                "  api_key: \"${AI4MATH_TEST_KEY}\"\n",
                encoding="utf-8",
            )
            payload = self.run_validator(project, env=env)
            self.assertTrue(payload["ok"])
            self.assertNotIn("missing_api_key_env", [w["code"] for w in payload["warnings"]])


if __name__ == "__main__":
    unittest.main()
