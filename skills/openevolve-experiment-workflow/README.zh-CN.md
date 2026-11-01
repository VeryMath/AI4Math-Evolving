# 用 OpenEvolve 演化数学候选对象

English guide: [README.md](README.md)

围绕数学**候选对象（Candidate）**，反复执行修改、评价、数学检查和失败反馈。候选对象可以是算法、证明思路、反例、猜想或构造；代码和 prompt 是表达这些对象的方式。

Skill 先检查对象能否明确表示、合法修改、有意义地比较，以及能否验证数学结论。每轮记录父候选、修改、具体对象、指标、数学状态和反馈。搜索指标变好与数学结论成立分别报告。

## 开始一个任务

```text
使用 $openevolve-experiment-workflow。
我的目标是：<算法 / 证明 / 反例 / 构造>。
先检查现有项目，明确候选对象和合法修改，评价初始对象，
在 <预算> 内进行多轮改进。记录失败候选，并验证选中的数学对象。
```

按任务选择直接数学搜索、Agent 引导修改或真实 OpenEvolve 模型运行，并明确候选由谁生成。需要模型运行时再配置 OpenEvolve 和 API；在已约定的范围与预算内继续执行。密钥保存在环境变量中。

## 运行三个数学案例

在本包目录运行，要求 Python 3.9 或更新版本：

```bash
python3 examples/mathematical_evolution.py --case all --rounds 10 --output .verification/mathematical-evolution.json
```

只依赖 Python 标准库。用 `--case algorithm`、`proof` 或 `counterexample` 单独运行一个案例。输出文件包含实际计算的每个候选及其评价、选择结果、失败反馈，以及说明本次修改使用了哪项观察的 `feedback_used`。

每个案例和总体输出都有 `target_reached`：算法必须在谱检查合法的同时优于基线；证明必须得到精确恒等式；图必须验证反例。只有全部选定目标达成才退出 `0`。预算耗尽或停止改进时若仍未达标，程序打印完整的部分结果，指定 `--output` 时也保存到文件，然后退出 `1`；例如 `--case proof --rounds 1` 会保留未证明的候选。因此 CI 检查的是实际数学目标。

| 案例 | 2026-11-01 复核的多轮运行结果 | 数学依据 |
| --- | --- | --- |
| 两个二次目标上的梯度步长 | 5 轮改进：步长 `1/64` → `25/128` | 精确有理数迭代；在声明的二次函数范围内，谱收缩界为 `103/128` |
| 四次不等式的证明候选 | 8 轮改进：恒等式误差 `4` → `0`，平方项权重为 `(1/4,3/4)` | 精确多项式恒等式与非负平方项，对所有实数输入成立 |
| 图论反例 | 5 轮改进：边数 `10` → `5`，Hamilton 回路数 `12` → `0` | 连通图且 `m=n=5`；穷举回路，并由度为 1 的顶点独立说明反例成立 |

后续修改实际读取评价反馈：不稳定步长会触发更小的改进，未匹配的多项式系数决定修改方向，断连失败会阻止再次删除相同边。程序统一无向边的端点顺序，并明确拒绝重复边、自环和非法端点。

程序在运行时生成并评价候选。这些是确定性数学搜索，没有调用模型或 OpenEvolve。平方项基底与反馈规则由案例提供；结果不能说明模型能力、全局最优性或研究创新。详见[案例与边界](references/mathematical-candidates.md)。

## OpenEvolve 项目

[模型案例](examples/model_candidates/README.md)使用 OpenEvolve 0.4.0 生成 JSON 候选，由固定评估器检查数学内容，评估过程不执行生成的代码。每次完成一个候选的评估后，将已评价候选及其数学反馈传入后续 prompt。2026-11-01 的真实 `ecnu-max` 运行共调用七次，三个数学目标均满足：步长 `1/10`、精确权重 `(1/4,3/4)`，以及五个顶点、六条边的连通图反例。SymPy 和 NetworkX 独立复核了结果。参阅[模型验证及范围](references/model-validation.md)。

已有代码项目可以继续使用 `initial_program.py`、`evaluator.py` 和当前配置格式。比较候选时保持假设和数学检查不变。参阅[项目格式](references/project-format.md)与[故障处理](references/troubleshooting.md)。

主要工作流在 [SKILL.md](SKILL.md)，Agent 入口在 [agents/openai.yaml](agents/openai.yaml)。既有辅助脚本与[历史 ADMM 会话](examples/admm-adaptive-rho-session/README.md)供原有项目继续使用。历史指标不能作为新运行的证据。

## 安装

```text
请从 https://github.com/VeryMath/AI4Math-Evolving.git 安装
openevolve-experiment-workflow Skill。
读取 SKILL.md，安装包含 references 和 examples 的完整包，
确认 $openevolve-experiment-workflow 可以被发现。
```
