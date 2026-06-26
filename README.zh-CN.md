<div align="center">

# AI4Math · 演化式工作流

面向迭代数学实验、OpenEvolve 运行、评估循环和技能改进的 agent-led workflow。

[English](README.md) · [技能包](#技能包) · [快速开始](#快速开始) · [安全边界](#安全边界)

![version](https://img.shields.io/badge/version-0.1.0-blue)
![skills](https://img.shields.io/badge/skills-1-2ea44f)
![license](https://img.shields.io/badge/license-MIT-green)

</div>

## 这个仓库是什么

这个仓库是 AI4Math 演化式 agent workflow 的技能入口。目前重点是有边界的 OpenEvolve 实验会话：环境就绪检查、项目检查、短 probe、指标复盘和下一轮迭代建议。

根 README 负责说明地图；真正执行任务时，请进入对应的 `skills/` 子目录。

## 技能包

| 包 | 适用任务 | 入口 |
| --- | --- | --- |
| [`openevolve-experiment-workflow`](skills/openevolve-experiment-workflow/) | 检查或创建 OpenEvolve 项目、验证运行配置、执行有边界 probe、总结指标并指导迭代改进。 | [`README`](skills/openevolve-experiment-workflow/README.md) · [`SKILL`](skills/openevolve-experiment-workflow/SKILL.md) |

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

```text
AI4Math-Evolving/
├── README.md
├── README.zh-CN.md
├── SKILL.md
└── skills/
    └── openevolve-experiment-workflow/
```

实验日志、checkpoint、provider 设置和生成输出应放在任务本地输出目录，不要放在公开根目录。

## 验证

这个仓库没有根级构建步骤。修改技能包后，请检查 `SKILL.md`、README 链接、脚本和 references；如果使用 Codex 本地 skill validator，请对 `skills/openevolve-experiment-workflow/` 运行验证。

## 安全边界

不要提交 provider API key、明文模型凭证、`.env` 文件、含密钥的 OpenEvolve 日志、生成 checkpoint 或私有实验输出。公开示例应脱敏并确认可以再分发。
