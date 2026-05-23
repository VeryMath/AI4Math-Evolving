import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "export_public_ui.py"


class ExportPublicUiTests(unittest.TestCase):
    def make_source(self, root: Path) -> None:
        for rel in [
            "README.md",
            "ATTRIBUTIONS.md",
            "index.html",
            "package.json",
            "package-lock.json",
            "postcss.config.mjs",
            "vite.config.ts",
            ".gitignore",
            ".env.example",
            "opencode.example.json",
            "src/app/App.tsx",
            "backend/server.py",
            "guidelines/Guidelines.md",
            "docs/installation.md",
            "examples/function-minimization/config.yaml",
            "scripts/smoke_ui_repo.sh",
            "start_all.sh",
            "stop_all.sh",
        ]:
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"{rel}\n", encoding="utf-8")
        for rel in [
            ".env",
            "opencode.json",
            "node_modules/pkg/index.js",
            "dist/assets/app.js",
            "server_data/private/config.yaml",
            ".run_logs/backend.log",
            ".archives/archive.tgz",
            "migration_artifact_20260511_210658.tgz",
        ]:
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("private\n", encoding="utf-8")

    def test_export_excludes_private_and_runtime_files(self):
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as parent:
            source = Path(src)
            target = Path(parent) / "public"
            self.make_source(source)
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--source",
                    str(source),
                    "--target",
                    str(target),
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertTrue((target / "README.md").is_file())
            self.assertTrue((target / "src/app/App.tsx").is_file())
            self.assertTrue((target / "opencode.example.json").is_file())
            self.assertFalse((target / ".env").exists())
            self.assertFalse((target / "opencode.json").exists())
            self.assertFalse((target / "node_modules").exists())
            self.assertFalse((target / "dist").exists())
            self.assertFalse((target / "server_data").exists())
            self.assertFalse((target / ".run_logs").exists())
            self.assertFalse((target / ".archives").exists())


if __name__ == "__main__":
    unittest.main()
