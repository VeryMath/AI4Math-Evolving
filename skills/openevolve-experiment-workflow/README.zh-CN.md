# OpenEvolve Experiment Workflow

English guide: [README.md](README.md)

`openevolve-experiment-workflow` 帮助 coding agent 运行受控的 OpenEvolve 代码或 prompt 搜索实验。

## 适合什么任务

当你有这些输入或需求时使用：

- 可以用 metric 打分的代码或 prompt；
- 需要检查、修复或有边界运行的已有 OpenEvolve project；
- 可以被整理成 starter project 和 evaluator 的研究目标；
- 在昂贵搜索前需要先检查 API、runtime 和预算风险。

## 会产出什么

Agent 应产出 workspace state、dry-run plans、short-probe logs、metrics、checkpoints、best-program artifacts 和 next-step recommendations。

## 安装

把下面这句话发给你的 coding agent：

```text
请帮我安装 `openevolve-experiment-workflow` skill，链接是：https://github.com/VeryMath/AI4Math-Evolving.git。请读取包内 `SKILL.md`，安装其中声明的 Skill entrypoint，验证 `$openevolve-experiment-workflow` 可用，并告诉我是否需要重启 agent。
```

如果你已经有这个 skill 仓库的本地文件夹，把链接换成本地路径即可。clone、link、配置、reload/restart 检查和验证都交给 coding agent 处理。

## 快速开始

把目标交给 coding agent：

```text
Use this repository's OpenEvolve experiment workflow.

我的目标是：<描述优化问题、算法想法、benchmark 或研究目标>。

请先检查工作区，配置可运行的 OpenEvolve 环境，第一次运行保持小规模；任何长时间或高成本运行前先问我。
```

如果已有 OpenEvolve 项目，同时给出项目路径和你关心的指标或行为。如果还没有项目，只描述目标即可；coding agent 应该自己创建或选择工作区和 starter project。

## 如何交互使用

推荐使用 checkpoint 循环：

```text
目标 -> 工作区检查 -> dry-run 计划 -> approve / revise / reject / skip
     -> 获批 probe -> 证据总结 -> 下一轮 checkpoint
```

`approve` 表示执行下一步，`revise` 表示先改计划，`reject` 表示停止当前路线，
`skip` 表示跳过当前阶段。长时间运行、API 预算、依赖变化、源码修改和最终结论前都应先问用户。

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

- `skills/openevolve-experiment-workflow/SKILL.md`：goal-driven AI4Math-Evolving 交互协议。
- `skills/openevolve-experiment-workflow/scripts/`：验证、dry run、运行摘要和会话状态的内部工具。
- `skills/openevolve-experiment-workflow/references/`：项目格式和故障排查参考。
- `examples/`：包内可运行示例，包含理解和复现实验所需的主要项目文件。

## 本地检查

这些脚本主要给 agent 使用，但也可以直接检查仓库：

```bash
python3 skills/openevolve-experiment-workflow/scripts/interactive_session.py --workspace /tmp/ai4math-evolving --json init
python3 skills/openevolve-experiment-workflow/scripts/interactive_session.py --workspace /tmp/ai4math-evolving --json next
python3 -m unittest discover -s tests -v
```
