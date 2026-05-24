from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "openevolve-coding-agent" / "SKILL.md"
README = ROOT / "README.md"
PYPROJECT = ROOT / "pyproject.toml"
AGENT_META = ROOT / "openevolve-coding-agent" / "agents" / "openai.yaml"
REFERENCE_DIR = ROOT / "openevolve-coding-agent" / "references"


class SkillDocsTests(unittest.TestCase):
    def read(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def frontmatter_description(self) -> str:
        text = self.read(SKILL)
        match = re.search(r"^description:\s*(.+)$", text, flags=re.MULTILINE)
        self.assertIsNotNone(match)
        return match.group(1)

    def test_skill_description_triggers_goal_driven_interaction(self):
        description = self.frontmatter_description().lower()
        self.assertIn("goal", description)
        self.assertIn("interactive", description)
        self.assertNotIn("workflow", description)

    def test_skill_body_prioritizes_agent_decision_contract(self):
        text = self.read(SKILL)
        self.assertIn("## Interaction Contract", text)
        self.assertIn("## Agent Decision Loop", text)
        self.assertIn("## Capabilities", text)
        self.assertIn("## User Guidance", text)
        self.assertIn("## Runtime/API Configuration", text)
        self.assertIn("## Tool Primitives", text)
        self.assertNotIn("## Workflow", text)

    def test_skill_guides_user_instead_of_exposing_command_menu(self):
        text = self.read(SKILL)
        self.assertIn("Guide the user through one decision at a time", text)
        self.assertIn("Do not ask the user to choose from a command list", text)
        self.assertIn("choose the next useful action yourself", text)

    def test_readme_and_agent_metadata_present_goal_session(self):
        readme = self.read(README)
        agent_meta = self.read(AGENT_META)
        self.assertIn("Goal-Driven Usage", readme)
        self.assertNotIn("Runner Contract", readme)
        self.assertIn("goal", agent_meta.lower())
        self.assertIn("feedback", agent_meta.lower())

    def test_public_docs_are_platform_neutral_and_not_process_notes(self):
        readme = self.read(README)
        pyproject = self.read(PYPROJECT)
        public_text = f"{readme}\n{pyproject}"
        self.assertIn("coding-agent", readme)
        self.assertNotIn("Codex", public_text)
        self.assertNotIn("UI bridge", readme)

    def test_skill_layer_has_no_opencode_surface(self):
        token = "open" + "code"
        for path in (SKILL, README, AGENT_META):
            self.assertNotIn(token, self.read(path).lower(), str(path))
        self.assertFalse((REFERENCE_DIR / f"{token}-adapter.md").exists())

    def test_skill_stays_lightweight_without_mcp_surface(self):
        text = self.read(SKILL).lower()
        self.assertNotIn("mcp", text)
        self.assertIn("short probe", text)
        self.assertIn("visualization data", text)
        self.assertIn("baseline", text)

    def test_skill_guides_api_configuration_without_storing_keys(self):
        text = self.read(SKILL)
        self.assertIn("`${LLM_API_KEY}`", text)
        self.assertIn("Do not write plaintext API keys", text)
        self.assertIn("If config already has", text)


if __name__ == "__main__":
    unittest.main()
