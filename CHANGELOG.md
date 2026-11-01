# 更新日志 / Changelog

## 0.2.0 — 2026-11-01

### 改动 / Changes

- 将 `openevolve-experiment-workflow` 从代码和 Prompt 搜索扩展到算法、证明候选、反例、猜想和构造。明确候选对象（Candidate）、允许的修改、评价目标、数学核查和失败记录。
  Extend the workflow to mathematical candidates, with explicit editable objects, evaluation objectives, mathematical checks, and failure records.
- 新增三个可直接运行的数学案例：二次目标的梯度步长搜索、四次不等式的精确平方和证明、连通图 Hamilton 回路猜想的反例搜索。后续修改实际读取不稳定步长、系数误差和断连反馈。
  Add three executable searches for an algorithm, an exact algebraic proof, and a graph counterexample; later proposals consume evaluator feedback.
- 增加 OpenEvolve 0.4.0 的真实模型 JSON 候选流程，固定数学评估器，每轮保存 checkpoint 并将已评价候选和数学反馈传入后续请求。模型输出作为数据解析。
  Add real OpenEvolve model proposals as JSON data, fixed mathematical evaluators, sequential checkpoints, and feedback in subsequent requests.
- 无向边统一规范化，格式错误直接报错，违反数学条件的候选保留具体反馈。未达到数学目标时保留完整结果并返回非零退出码。
  Normalize undirected edges, reject malformed input immediately, retain mathematical failures, and return a nonzero exit code for unmet targets.
- 增加 SymPy 和 NetworkX 独立验证、真实请求记录核对及本仓库直接执行的 CI。
  Add independent SymPy and NetworkX verification, actual trace checks, and self-contained CI.

### 本地结果 / Local results

- 三个确定性搜索分别完成 5、8、5 轮改进：梯度步长选为 `25/128`，最差平方误差从 `0.454826833171` 降至 `0.00223996531907`；恢复系数 `1/4, 3/4` 的精确平方和恒等式；找到 5 个顶点、5 条边、无 Hamilton 回路的连通图，并用度为 1 的顶点核查反例。
  The three deterministic searches reached their stated targets after 5, 8, and 5 improving rounds; checks cover spectral contraction, an exact polynomial identity, and the explicit graph counterexample.
- `ecnu-max` 实际调用七次，服务返回总用量为 5,740 tokens。选中步长 `1/10`、平方和权重 `(1/4,3/4)` 及五顶点六边的连通图反例，三项数学目标均满足。独立数学工具与原评估器结果一致。
  A seven-call ecnu-max run used 5,740 reported tokens and reached all three mathematical targets, with independently checked results.
- 复现命令和适用范围见[确定性案例](skills/openevolve-experiment-workflow/references/mathematical-candidates.md)与[模型验证](skills/openevolve-experiment-workflow/references/model-validation.md)。结果涉及指定的小型任务和证明表示，未验证研究创新、全局最优或一般证明能力。
  Reproduction commands and scope are documented for both deterministic and model-generated searches; these checks do not establish research novelty, global optimality, or general proof ability.
