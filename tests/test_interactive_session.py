import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "openevolve-experiment-workflow" / "scripts" / "interactive_session.py"


class InteractiveSessionTests(unittest.TestCase):
    def make_project(self, root: Path) -> None:
        root.mkdir(parents=True, exist_ok=True)
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
        (root / "config.yml").write_text(
            "max_iterations: 3\n"
            "checkpoint_interval: 1\n"
            "llm:\n"
            "  api_key: \"${LLM_API_KEY}\"\n",
            encoding="utf-8",
        )

    def run_cli(self, workspace: Path, *args: str, env: Optional[dict[str, str]] = None) -> dict:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--workspace", str(workspace), "--json", *args],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_session_import_validate_configure_and_run_dry_run(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            workspace = root / "workspace"
            source = root / "source_project"
            self.make_project(source)

            imported = self.run_cli(workspace, "import", str(source), "--name", "demo")
            self.assertEqual(imported["projectName"], "demo")
            imported_path = Path(imported["projectPath"])
            self.assertTrue((imported_path / "config.yaml").is_file())

            validation = self.run_cli(workspace, "validate")
            self.assertTrue(validation["ok"])

            configured = self.run_cli(
                workspace,
                "configure",
                "--mode",
                "direct",
                "--iterations",
                "3",
                "--extra",
                "api_base=https://example.invalid/v1",
                "--extra",
                "primary_model=test-model",
            )
            self.assertEqual(configured["config"]["mode"], "direct")

            planned = self.run_cli(workspace, "run", "--dry-run")
            self.assertEqual(planned["status"], "planned")
            self.assertEqual(planned["mode"], "direct")
            self.assertEqual(planned["command"][0], "openevolve-run")
            self.assertIn("--api-base", planned["command"])
            self.assertIn("--primary-model", planned["command"])

            tree = self.run_cli(workspace, "tree")
            self.assertIn("initial_program.py", [entry["path"] for entry in tree["entries"]])

            read = self.run_cli(workspace, "read", "initial_program.py")
            self.assertIn("EVOLVE-BLOCK-START", read["content"])

            status = self.run_cli(workspace, "status")
            self.assertEqual(status["currentProject"], "demo")

            nxt = self.run_cli(workspace, "next")
            self.assertIn("run", nxt["next"])

    def test_session_config_has_no_opencode_agent_backend(self):
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td) / "workspace"
            status = self.run_cli(workspace, "status")
            config = status["config"]
            self.assertEqual(config["mode"], "direct")
            self.assertNotIn("agent", config)

    def test_summarize_explicit_run_dir(self):
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td) / "workspace"
            run = Path(td) / "run"
            best = run / "best"
            best.mkdir(parents=True)
            (best / "best_program_info.json").write_text(
                json.dumps({"metrics": {"combined_score": 9.0}, "id": "best-1"}),
                encoding="utf-8",
            )

            payload = self.run_cli(workspace, "summarize", "--run-dir", str(run))
            self.assertTrue(payload["hasBest"])
            self.assertEqual(payload["bestMetrics"]["combined_score"], 9.0)

    def test_record_run_updates_session_status(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            workspace = root / "workspace"
            source = root / "source_project"
            self.make_project(source)

            self.run_cli(workspace, "init", "--project", str(source), "--name", "demo")
            recorded = self.run_cli(
                workspace,
                "record-run",
                "--run-id",
                "run_1",
                "--project",
                "demo",
                "--output-dir",
                str(root / "out"),
                "--log-path",
                str(root / "out" / "run.log"),
                "--pid",
                str(os.getpid()),
                "--status",
                "running",
                "--mode",
                "direct",
                "--command-json",
                json.dumps(["openevolve-run", "initial_program.py"]),
            )
            self.assertEqual(recorded["runId"], "run_1")

            status = self.run_cli(workspace, "status")
            self.assertEqual(status["currentRun"], "run_1")
            self.assertEqual(status["runStatus"], "running")

    def test_run_tail_and_stop_with_fake_openevolve(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            workspace = root / "workspace"
            source = root / "source_project"
            fake_bin = root / "bin"
            fake_bin.mkdir()
            fake = fake_bin / "openevolve-run"
            fake.write_text(
                "#!/bin/sh\n"
                "echo fake-openevolve-started\n"
                "sleep 30\n",
                encoding="utf-8",
            )
            fake.chmod(0o755)
            env = dict(os.environ)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            self.make_project(source)

            self.run_cli(workspace, "import", str(source), "--name", "demo", env=env)
            self.run_cli(workspace, "configure", "--mode", "direct", "--iterations", "1", env=env)
            started = self.run_cli(workspace, "run", env=env)
            self.assertEqual(started["status"], "running")
            tail = {"lines": []}
            for _ in range(20):
                time.sleep(0.1)
                tail = self.run_cli(workspace, "tail", "--lines", "5", env=env)
                if "fake-openevolve-started" in "\n".join(tail["lines"]):
                    break
            self.assertIn("fake-openevolve-started", "\n".join(tail["lines"]))

            stopped = self.run_cli(workspace, "stop", env=env)
            self.assertEqual(stopped["status"], "stopped")


if __name__ == "__main__":
    unittest.main()
