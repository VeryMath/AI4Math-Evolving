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
        self.assertIn("--dry-run", argv)
        self.assertIn("--json", argv)
        self.assertIn("--language", argv)
        self.assertIn("zh-CN", argv)
        self.assertIn("--extra", argv)
        self.assertIn("num_islands=3", argv)
        self.assertIn("mutation_rate=0.2", argv)

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
