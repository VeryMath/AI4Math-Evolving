from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "openevolve-experiment-workflow" / "SKILL.md"
README = ROOT / "README.md"
README_ZH = ROOT / "README.zh-CN.md"
PYPROJECT = ROOT / "pyproject.toml"
AGENT_META = ROOT / "openevolve-experiment-workflow" / "agents" / "openai.yaml"
REFERENCE_DIR = ROOT / "openevolve-experiment-workflow" / "references"
EXAMPLE_DIR = ROOT / "examples" / "admm-adaptive-rho-session"


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

    def test_skill_defaults_to_chinese_responses(self):
        text = self.read(SKILL)
        agent_meta = self.read(AGENT_META)
        self.assertIn("Reply in Chinese by default", text)
        self.assertIn("用中文", agent_meta)

    def test_skill_uses_goal_first_readiness_instead_of_fixed_order(self):
        text = self.read(SKILL)
        agent_meta = self.read(AGENT_META)
        self.assertIn("## Goal-Directed Environment Setup", text)
        self.assertIn("For new-user onboarding, establish a runnable environment before project design", text)
        self.assertIn("Let the user's goal shape defaults", text)
        self.assertIn("Do not turn readiness into a fixed checklist", text)
        self.assertIn("openevolve-run", text)
        self.assertNotIn("2. **Ready API**", text)
        self.assertNotIn("3. **Ready Environment**", text)
        self.assertIn("~/Desktop/AI4Math-Evolving", text)
        self.assertIn("先配好运行环境", agent_meta)
        self.assertIn("以目标为导向", agent_meta)

    def test_skill_describes_openevolve_as_python_cli_not_local_deployment(self):
        text = self.read(SKILL)
        agent_meta = self.read(AGENT_META)
        self.assertIn("OpenEvolve is used as a Python package and CLI", text)
        self.assertIn("Do not describe this as deploying a local service", text)
        self.assertIn("Prefer installing or importing the package and calling the CLI", text)
        self.assertIn("do not clone or deploy OpenEvolve itself unless the user asks", text)
        self.assertIn("直接调包", agent_meta)
        self.assertIn("无需本地部署服务", agent_meta)

    def test_public_docs_use_formal_new_user_onboarding_language(self):
        readme = self.read(README)
        readme_zh = self.read(README_ZH)
        skill = self.read(SKILL)
        agent_meta = self.read(AGENT_META)
        public_text = f"{readme}\n{readme_zh}\n{skill}\n{agent_meta}"
        self.assertIn("What The Coding Agent Should Do", readme)
        self.assertIn("Coding Agent 应该做什么", readme_zh)
        self.assertIn("第一次运行保持小规模", readme_zh)
        self.assertIn("first-run onboarding", skill)
        self.assertIn("新用户首次上手路径", agent_meta)
        self.assertNotIn("小白", public_text)
        self.assertNotIn("first path", public_text.lower())

    def test_empty_workspace_initializes_visible_workspace_first(self):
        readme = self.read(README)
        readme_zh = self.read(README_ZH)
        skill = self.read(SKILL)
        agent_meta = self.read(AGENT_META)
        self.assertIn("empty or temporary workspace", skill)
        self.assertIn("default action is to initialize", skill)
        self.assertIn("~/Desktop/AI4Math-Evolving", skill)
        self.assertIn("Do not force a single workspace path", skill)
        self.assertIn("report its absolute path", skill)
        self.assertIn("--workspace ~/Desktop/AI4Math-Evolving --json init", skill)
        self.assertIn("defaulting to `~/Desktop/AI4Math-Evolving` when no better path is known", readme)
        self.assertIn("默认使用 `~/Desktop/AI4Math-Evolving`", readme_zh)
        self.assertIn("空目录时先初始化", agent_meta)

    def test_onboarding_configures_environment_before_domain_questionnaires(self):
        text = self.read(SKILL)
        agent_meta = self.read(AGENT_META)
        self.assertIn("Before asking domain-shaping questions", text)
        self.assertIn("workspace, Python interpreter, `openevolve` package, `openevolve-run`, provider API variable, model, and base URL", text)
        self.assertIn("Do not start with a multi-option algorithm or benchmark questionnaire", text)
        self.assertIn("If the user provides API settings in chat", text)
        self.assertIn("acknowledge receipt without repeating the secret value", text)
        self.assertIn("先检查工作区、Python/OpenEvolve、API 环境变量和模型配置", agent_meta)

    def test_readme_and_agent_metadata_present_goal_session(self):
        readme = self.read(README)
        readme_zh = self.read(README_ZH)
        agent_meta = self.read(AGENT_META)
        self.assertIn("Chinese guide: [README.zh-CN.md](README.zh-CN.md)", readme)
        self.assertIn("English guide: [README.md](README.md)", readme_zh)
        self.assertIn("https://github.com/VeryMath/AI4Math-Evolving", readme)
        self.assertIn("https://github.com/VeryMath/AI4Math-Evolving", readme_zh)
        self.assertIn("## Installation / Loading", readme)
        self.assertIn("## Quick Start", readme)
        self.assertIn("Please detect the target agent and its skill/config location", readme)
        self.assertNotIn("Install this skill for OpenCode", readme)
        self.assertNotIn("## 1. Install With Your Coding Agent", readme)
        self.assertIn("## 安装 / 加载", readme_zh)
        self.assertIn("## 快速开始", readme_zh)
        self.assertIn("请自动识别目标 agent 和它的 skill/config 位置", readme_zh)
        self.assertNotIn("请把这个 skill 安装到 OpenCode", readme_zh)
        self.assertNotIn("## 1. 用 Coding Agent 安装", readme_zh)
        self.assertNotIn("Runner Contract", readme)
        self.assertNotIn("Runner Contract", readme_zh)
        self.assertIn("goal", agent_meta.lower())
        self.assertIn("feedback", agent_meta.lower())

    def test_public_docs_are_platform_neutral_and_not_process_notes(self):
        readme = self.read(README)
        readme_zh = self.read(README_ZH)
        pyproject = self.read(PYPROJECT)
        public_text = f"{readme}\n{readme_zh}\n{pyproject}"
        self.assertIn("coding-agent", readme)
        self.assertIn("target agent", readme)
        self.assertIn("目标 agent", readme_zh)
        self.assertNotIn("Codex", public_text)
        self.assertNotIn("UI bridge", readme)

    def test_readme_documents_opencode_install_without_skill_layer_surface(self):
        token = "open" + "code"
        readme = self.read(README)
        readme_zh = self.read(README_ZH)
        self.assertIn(token, readme.lower())
        self.assertIn(token, readme_zh.lower())
        self.assertIn("openevolve-experiment-workflow/SKILL.md", readme)
        self.assertIn("openevolve-experiment-workflow/SKILL.md", readme_zh)
        for path in (SKILL, AGENT_META):
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

    def test_examples_are_repository_level_case_packages(self):
        readme = self.read(README)
        readme_zh = self.read(README_ZH)
        self.assertIn("`examples/`: repository-level runnable examples", readme)
        self.assertIn("`examples/`：仓库级可运行示例", readme_zh)
        self.assertTrue((EXAMPLE_DIR / "README.md").is_file())
        self.assertFalse((ROOT / "openevolve-experiment-workflow" / "examples").exists())

        required_project_files = [
            "project/initial_program.py",
            "project/evaluator.py",
            "project/admm_benchmark.py",
            "project/config.yaml",
            "project/tests/test_evaluator_contract.py",
            "project/README.md",
        ]
        for rel_path in required_project_files:
            self.assertTrue((EXAMPLE_DIR / rel_path).is_file(), rel_path)

    def test_examples_do_not_store_secrets_or_local_run_artifacts(self):
        local_workspace_path = "/".join(["", "Users", "conanxu", "Desktop", "AI4Math-Evolving"])
        for path in EXAMPLE_DIR.rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                text = self.read(path)
                self.assertNotRegex(text, r"sk-[A-Za-z0-9]{8,}")
                self.assertNotIn(local_workspace_path, text)
        self.assertIn('${LLM_API_KEY}', self.read(EXAMPLE_DIR / "project" / "config.yaml"))
        self.assertFalse((EXAMPLE_DIR / "project" / "runs").exists())


if __name__ == "__main__":
    unittest.main()
