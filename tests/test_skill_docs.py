from pathlib import Path
import unittest
from urllib.parse import unquote, urlsplit
import zipfile

import frontmatter
from markdown_it import MarkdownIt
import yaml


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "openevolve-experiment-workflow"
EXAMPLE = SKILL_ROOT / "examples" / "admm-adaptive-rho-session"


class SkillDocsTests(unittest.TestCase):
    def test_skill_metadata_and_agent_invocation_are_valid(self):
        for path in (ROOT / "SKILL.md", SKILL_ROOT / "SKILL.md"):
            skill = frontmatter.load(path)
            self.assertRegex(skill["name"], r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
            self.assertIsInstance(skill["description"], str)
            self.assertTrue(0 < len(skill["description"]) <= 1024)
            self.assertTrue(skill.content.strip())
        agent = yaml.safe_load((SKILL_ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8"))
        interface = agent["interface"]
        self.assertIn("$" + frontmatter.load(SKILL_ROOT / "SKILL.md")["name"], interface["default_prompt"])
        self.assertTrue(25 <= len(interface["short_description"]) <= 64)

    def test_public_entrypoint_links_resolve_within_repository(self):
        paths = [ROOT / "README.md", ROOT / "README.zh-CN.md", ROOT / "SKILL.md"]
        paths += [SKILL_ROOT / "README.md", SKILL_ROOT / "README.zh-CN.md", SKILL_ROOT / "SKILL.md"]
        paths += list((SKILL_ROOT / "references").glob("*.md"))
        paths += [SKILL_ROOT / "examples" / "model_candidates" / "README.md"]
        parser = MarkdownIt()
        for path in paths:
            content = frontmatter.load(path).content
            for token in parser.parse(content):
                for child in token.children or []:
                    if child.type not in ("link_open", "image"):
                        continue
                    target = child.attrGet("href" if child.type == "link_open" else "src")
                    parts = urlsplit(target)
                    if parts.scheme or parts.netloc or not parts.path:
                        continue
                    resolved = (path.parent / unquote(parts.path)).resolve()
                    self.assertTrue(resolved.is_relative_to(ROOT), f"{path}: {target}")
                    self.assertTrue(resolved.exists(), f"{path}: {target}")

    def test_examples_keep_credentials_and_local_outputs_out_of_release(self):
        for path in (SKILL_ROOT / "examples").rglob("*"):
            if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            if path.suffix == ".pptx":
                with zipfile.ZipFile(path) as deck:
                    text = "\n".join(deck.read(name).decode("utf-8") for name in deck.namelist()
                                     if name.endswith((".xml", ".rels")))
            else:
                text = path.read_text(encoding="utf-8")
            self.assertNotRegex(text, r"sk-[A-Za-z0-9]{8,}")
            self.assertNotRegex(text, r"/(?:Users|home)/[A-Za-z0-9_.-]+/")
            self.assertNotIn(".verification", path.parts)
        config = yaml.safe_load((EXAMPLE / "project" / "config.yaml").read_text(encoding="utf-8"))
        self.assertEqual(config["llm"]["api_key"], "${LLM_API_KEY}")
        self.assertFalse((EXAMPLE / "project" / "runs").exists())

    def test_existing_example_remains_complete(self):
        for relative in ("project/initial_program.py", "project/evaluator.py", "project/admm_benchmark.py",
                         "project/config.yaml", "project/tests/test_evaluator_contract.py", "project/README.md",
                         "slides/admm-rho-evolve-ppt.pptx"):
            self.assertTrue((EXAMPLE / relative).is_file(), relative)


if __name__ == "__main__":
    unittest.main()
