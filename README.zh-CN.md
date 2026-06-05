# AI4Math-Evolving Skill

English guide: [README.md](README.md)

GitHub：<https://github.com/VeryMath/AI4Math-Evolving>

`openevolve-coding-agent` 是一个面向 AI4Math/OpenEvolve 实验的 coding-agent skill。它应该由 coding agent 来安装和操作：agent 负责读取项目、配置可运行环境、只在关键决策处提问、先跑小规模探测再做长搜索，并且不把 API key 写进文件。

## 1. 用 Coding Agent 安装

把 GitHub 链接或当前本地仓库交给你的 coding agent，然后说：

```text
请把 https://github.com/VeryMath/AI4Math-Evolving 里的 `openevolve-coding-agent` skill 安装到我正在使用的 coding agent 环境。

请自动识别目标 agent 和它的 skill/config 位置，保留已有配置，只安装或链接必要内容，不要把 API key 写进文件；安装后验证 `openevolve-coding-agent/SKILL.md` 能被发现，并告诉我是否需要重启目标 agent。
```

安装细节由 coding agent 负责。如果目标是 OpenCode 或其他支持 skill 的 agent，它应该使用目标 agent 原生的 skill 发现路径和验证命令，而不是让你手动编辑配置。

## 2. 开始一次 OpenEvolve 交互会话

安装后，把目标交给 coding agent：

```text
Use $openevolve-coding-agent.

我的目标是：<描述优化问题、算法想法、benchmark 或研究目标>。

请先检查工作区，配置可运行的 OpenEvolve 环境，第一次运行保持小规模；任何长时间或高成本运行前先问我。
```

如果已有 OpenEvolve 项目，同时给出项目路径和你关心的指标或行为。如果还没有项目，只描述目标即可；coding agent 应该自己创建或选择工作区和 starter project。

## Coding Agent 应该做什么

一次会话中，agent 应该：

- 先检查工作区，再问项目问题；
- 检查 Python、`openevolve` package、`openevolve-run`、API 环境变量、model 和 base URL；
- 创建或选择可见工作区，在没有更好路径时默认使用 `~/Desktop/AI4Math-Evolving`；
- 检查或创建 `initial_program.py`、`evaluator.py` 和 `config.yaml`；
- 验证项目，只修复直接相关的问题；
- 在花费 API 预算前先构造 dry-run 命令；
- 先跑 short probe，再决定是否做 longer evolution search；
- 检查日志、metrics、checkpoints 和 best-program artifacts；
- 总结发生了什么变化，并提出下一个具体动作。

## OpenEvolve 项目约定

一个 OpenEvolve 项目通常包含：

- `initial_program.py`，并带有 `EVOLVE-BLOCK-START` 和 `EVOLVE-BLOCK-END`；
- `evaluator.py`，并提供 `evaluate(program_path)`；
- `config.yaml`、`config.yml` 或 `config_default.yaml`，并包含 `max_iterations` 和 `checkpoint_interval`。

如果项目结构不同，skill 应该先检查现有文件，再决定适配、修复或询问用户，而不是强行套用默认结构。

## 仓库结构

- `openevolve-coding-agent/SKILL.md`：goal-driven AI4Math-Evolving 交互协议。
- `openevolve-coding-agent/scripts/`：验证、dry run、运行摘要和会话状态的内部工具。
- `openevolve-coding-agent/references/`：项目格式和故障排查参考。
- `examples/`：仓库级可运行示例，包含理解和复现实验所需的主要项目文件。

## 本地检查

这些脚本主要给 agent 使用，但也可以直接检查仓库：

```bash
python3 openevolve-coding-agent/scripts/interactive_session.py --workspace /tmp/ai4math-evolving --json init
python3 openevolve-coding-agent/scripts/interactive_session.py --workspace /tmp/ai4math-evolving --json next
python3 -m unittest discover -s tests -v
```
