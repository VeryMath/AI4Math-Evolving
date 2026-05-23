import json
import os
import sys
import tempfile
from pathlib import Path
from unittest import mock
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend import skill_runner  # noqa: E402


class SkillRunnerTests(unittest.TestCase):
    def make_fake_skill_repo(self, root: Path) -> None:
        scripts = root / "openevolve-coding-agent" / "scripts"
        scripts.mkdir(parents=True)
        (scripts / "run_openevolve.py").write_text(
            "import json\n"
            "import sys\n"
            "print(json.dumps({\n"
            "  'argv': sys.argv[1:],\n"
            "  'command': ['opencode', 'run', '--format', 'json'],\n"
            "  'prompt': 'fake prompt'\n"
            "}))\n",
            encoding="utf-8",
        )
        (scripts / "interactive_session.py").write_text(
            "import json\n"
            "import sys\n"
            "args = sys.argv[1:]\n"
            "command = args[args.index('--json') + 1]\n"
            "if command == 'run':\n"
            "    print(json.dumps({\n"
            "      'status': 'planned',\n"
            "      'command': ['openevolve-run', 'initial_program.py', 'evaluator.py'],\n"
            "      'argv': args\n"
            "    }))\n"
            "else:\n"
            "    print(json.dumps({'status': command, 'argv': args}))\n",
            encoding="utf-8",
        )

    def test_build_run_payload_invokes_skill_repo_runner(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            self.make_fake_skill_repo(repo)
            project = repo / "project"
            output = repo / "output"
            with mock.patch.dict(os.environ, {"OPENEVOLVE_SKILL_REPO": str(repo)}, clear=False):
                payload = skill_runner.build_run_payload(
                    project,
                    iterations=8,
                    checkpoint_interval=2,
                    output_dir=output,
                    agent="openevolve-unified-primary",
                    extras={"num_islands": 3, "mutation_rate": 0.2},
                )

        argv = payload["argv"]
        self.assertEqual(payload["command"][0], "openevolve-run")
        self.assertIn("run", argv)
        self.assertIn("--project", argv)
        self.assertIn("--run-id", argv)
        self.assertIn("--output-dir", argv)
        self.assertIn("--dry-run", argv)
        self.assertIn("--json", argv)
        self.assertIn("--mode", payload["configureArgv"])
        self.assertIn("direct", payload["configureArgv"])
        self.assertIn("--extra", payload["configureArgv"])
        self.assertIn("num_islands=3", payload["configureArgv"])
        self.assertIn("mutation_rate=0.2", payload["configureArgv"])

    def test_build_run_payload_can_request_opencode_mode(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            self.make_fake_skill_repo(repo)
            project = repo / "project"
            output = repo / "output"
            with mock.patch.dict(os.environ, {"OPENEVOLVE_SKILL_REPO": str(repo)}, clear=False):
                payload = skill_runner.build_run_payload(
                    project,
                    iterations=8,
                    checkpoint_interval=2,
                    output_dir=output,
                    mode="opencode",
                    agent="openevolve-unified-primary",
                )

        self.assertIn("--mode", payload["configureArgv"])
        self.assertIn("opencode", payload["configureArgv"])

    def test_provider_extras_prefer_llm_environment(self):
        env = {
            "LLM_BASE_URL": "https://chat.example/v1",
            "LLM_MODEL_ID": "ecnu-plus",
            "DEEPSEEK_BASE_URL": "https://deepseek.example",
            "DEEPSEEK_MODEL": "deepseek-chat",
        }
        extras = skill_runner.provider_extras_from_env(env)
        self.assertEqual(extras["api_base"], "https://chat.example/v1")
        self.assertEqual(extras["primary_model"], "ecnu-plus")
        self.assertEqual(extras["secondary_model"], "ecnu-plus")

    def test_record_external_run_invokes_interactive_session(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            self.make_fake_skill_repo(repo)
            project = repo / "project"
            output = repo / "output"
            log = output / "logs" / "monitor.jsonl"
            with mock.patch.dict(os.environ, {"OPENEVOLVE_SKILL_REPO": str(repo)}, clear=False):
                payload = skill_runner.record_external_run(
                    project,
                    run_id="run_1",
                    output_dir=output,
                    log_path=log,
                    pid=123,
                    mode="direct",
                    command=["openevolve-run", "initial_program.py"],
                )

        self.assertEqual(payload["status"], "record-run")
        self.assertIn("--command-json", payload["argv"])
        self.assertIn('["openevolve-run", "initial_program.py"]', payload["argv"])

    def test_missing_skill_repo_script_reports_actionable_error(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            with mock.patch.dict(os.environ, {"OPENEVOLVE_SKILL_REPO": str(repo)}, clear=False):
                with self.assertRaises(skill_runner.SkillRunnerError) as ctx:
                    skill_runner.build_run_payload(
                        repo / "project",
                        iterations=1,
                        checkpoint_interval=1,
                        output_dir=repo / "output",
                    )

        self.assertIn("OPENEVOLVE_SKILL_REPO", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
