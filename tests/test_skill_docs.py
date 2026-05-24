from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "openevolve-coding-agent" / "SKILL.md"
README = ROOT / "README.md"
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
        self.assertIn("## Tool Primitives", text)
        self.assertNotIn("## Workflow", text)

    def test_readme_and_agent_metadata_present_goal_session(self):
        readme = self.read(README)
        agent_meta = self.read(AGENT_META)
        self.assertIn("Goal-Driven Usage", readme)
        self.assertNotIn("Runner Contract", readme)
        self.assertIn("goal", agent_meta.lower())
        self.assertIn("feedback", agent_meta.lower())

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


if __name__ == "__main__":
    unittest.main()
