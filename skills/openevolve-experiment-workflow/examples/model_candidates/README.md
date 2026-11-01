# 通过真实模型生成数学候选

本例使用 OpenEvolve 0.4.0 和 OpenAI-compatible 服务生成 JSON 候选，由固定评估器进行数学计算。运行需要 Python 3.10 或更新版本。

从仓库根目录安装依赖：

```bash
python -m pip install '.[model]'
```

设置 `LLM_MODEL_ID` 和 `LLM_BASE_URL`，通过已有的 `LLM_API_KEY` 环境变量提供密钥。未设置密钥环境变量时，运行器会在终端隐藏输入。运行器仅在内存中使用密钥，请勿将密钥写入项目文件。

```bash
python skills/openevolve-experiment-workflow/examples/model_candidates/run.py \
  --case all --iterations 3 --output .verification/model-candidates
```

可以通过 `--model` 和 `--base-url` 指定模型及服务地址。输出目录必须为空，以保留已有运行证据。`--iterations` 限制每个案例的模型生成次数；每次完成计算、保存 checkpoint 和反馈后，才开始下一次生成。达到目标分数会提前结束该案例。模型请求不进行自动重试。

| 案例 | 允许修改的数据 | 固定数学检查 |
| --- | --- | --- |
| `algorithm` | 一个有理步长字符串 | 两个指定对角二次目标的 12 次精确有理迭代；谱区间 `[1,9]` 上的收缩条件 |
| `proof` | 两个非负有理权重字符串 | 指定四次多项式的全部系数；仅误差为零且权重非负时确认平方和证明 |
| `counterexample` | 五个固定顶点上的边列表 | 简单无向图、连通、边数至少为 5，以及全部 Hamiltonian 环路枚举 |

模型输出只会通过 `orjson` 解析为数据，评估器不会执行生成的 Python。评估文件固定候选类别和图的顶点数，格式错误立即报错。违反数学条件的候选会收到 `admissible=0`、`combined_score=-1` 和具体原因。

`combined_score` 越大越好：算法为 `1/(1+最大均方误差)`，证明为 `1/(1+系数误差)`，图为 `1/(1+Hamiltonian 环路数+边数/100)`。图分数在本例固定的五顶点范围内优先减少环路数，再减少边数。分数仅用于搜索；数学结论由固定检查决定。

每轮输出包括 checkpoint、实际模型请求与响应、候选、父候选标识、token 用量和数学反馈。`verification.json` 汇总实际评估次数和重新计算后的最佳结果。所有选定案例达到数学目标时返回 `0`，预算结束后仍有目标未完成时返回 `1`。模型服务、生成格式或评估器错误会直接中止运行。日志和原始请求留在忽略的输出目录内。

`target_reached` 的算法条件是合法步长且优于初始误差，证明条件是精确平方和恒等式，图条件是符合全部前提的反例。模型搜索可以在算法达到更高搜索分数前用完预算，最终状态仍按这些数学条件计算。

运行结果和适用范围参见[验证记录](../../references/model-validation.md)。这些小型案例验证运行方式，未测量研究创新能力或一般证明能力。
