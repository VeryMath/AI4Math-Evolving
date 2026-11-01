<div align="center">

# AI4Math · 演化式工作流

面向迭代数学实验、OpenEvolve 运行、评估循环和技能改进的 agent-led workflow。

[English](README.md) · [贡献者](CONTRIBUTORS.md) · [技能包](#技能包) · [安装](#安装) · [快速开始](#快速开始) · [安全边界](#安全边界)

![version](https://img.shields.io/badge/version-0.2.0-blue)
![skills](https://img.shields.io/badge/skills-1-2ea44f)
![license](https://img.shields.io/badge/license-MIT-green)

</div>

<p align="center">
  如果这个项目对你有帮助，欢迎为仓库点 Star ⭐
  <a href="https://github.com/VeryMath/AI4Math-Evolving"><img alt="GitHub Stars" src="https://img.shields.io/github/stars/VeryMath/AI4Math-Evolving?style=social"></a>
</p>

## 这个仓库是什么

这个仓库是 AI4Math 演化式 agent workflow 的技能入口。目前重点是有边界的 OpenEvolve 实验会话：对算法、证明候选和反例逐轮修改、评估、数学核查，并记录失败反馈。

根 README 负责说明地图；真正执行任务时，请进入对应的 `skills/` 子目录。

## 技能包

| 包 | 适用任务 | 入口 |
| --- | --- | --- |
| [`openevolve-experiment-workflow`](skills/openevolve-experiment-workflow/) | 演化算法、证明候选和反例，逐轮评估修改，记录数学核查与失败反馈。 | [`README`](skills/openevolve-experiment-workflow/README.md) · [`SKILL`](skills/openevolve-experiment-workflow/SKILL.md) |

## 安装

推荐方式是 AI 自动安装：让你的 coding agent 自己 clone 或更新仓库、读取 Skill 说明、安装入口并验证 discovery。

```text
请帮我安装这些 AI4Math Skills。

仓库：https://github.com/VeryMath/AI4Math-Evolving.git
分支：main
Skill 路径：
- skills/openevolve-experiment-workflow

请执行：
1. 本地 clone 或更新仓库。
2. 读取 README.md、SKILL.md、AGENTS.md（如果存在）以及每个目标 Skill 入口。
3. 如果当前环境支持本地 Skill discovery，把每个包含 SKILL.md 的目录链接到本地 skills 目录。
4. 如果某个 Skill 依赖相邻的共享支持目录，请保留这些 sibling 目录。
5. 验证安装后的 Skills 是否可被发现。
6. 告诉我安装路径、是否需要重启 agent，并给我一个测试 prompt。
```

Codex 风格本地 discovery 的手工 fallback：

```bash
git clone https://github.com/VeryMath/AI4Math-Evolving.git
cd AI4Math-Evolving
mkdir -p ~/.codex/skills
ln -s "$PWD/skills/openevolve-experiment-workflow" ~/.codex/skills/openevolve-experiment-workflow
```

如果你的 agent 使用别的本地 Skill 目录，把 `~/.codex/skills` 替换成对应配置路径。

## 快速开始

克隆仓库并打开技能包：

```bash
git clone https://github.com/VeryMath/AI4Math-Evolving.git
cd AI4Math-Evolving
```

从这里开始：

```text
skills/openevolve-experiment-workflow/SKILL.md
```

## 仓库结构

- `README.md` 与 `README.zh-CN.md`：仓库说明与安装入口。
- `SKILL.md`：引导任务使用对应技能包。
- `skills/openevolve-experiment-workflow/`：工作流程、示例与参考资料。
- `tests/`：脚本行为、元信息、链接与数学验证。

实验日志、checkpoint、provider 设置和生成输出应放在任务本地输出目录，不要放在公开根目录。

## 验证

从仓库根目录安装验证依赖并运行检查：

```bash
python -m pip install '.[test]'
mkdir -p .verification/temporary
TMPDIR="$PWD/.verification/temporary" python -m pytest -q
python skills/openevolve-experiment-workflow/examples/mathematical_evolution.py --case all --rounds 10 --output .verification/mathematical-evolution.json
```

[真实模型案例](skills/openevolve-experiment-workflow/examples/model_candidates/README.md)使用 JSON 候选和固定评估器。已完成的 `ecnu-max` 运行见[验证记录](skills/openevolve-experiment-workflow/references/model-validation.md)。CI 无需服务密钥即可执行本地数学检查。

## 安全边界

不要提交 provider API key、明文模型凭证、`.env` 文件、含密钥的 OpenEvolve 日志、生成 checkpoint 或私有实验输出。公开示例应脱敏并确认可以再分发。
