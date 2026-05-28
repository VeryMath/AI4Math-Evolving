# Example: ADMM Adaptive-Rho OpenEvolve Session

This repository example shows a concrete pattern for guiding an open-ended mathematical optimization goal into an OpenEvolve project and run. It is a condensed, sanitized reconstruction of a real interaction. Do not copy secrets, raw API keys, or local-only credentials from chat into project files.

## Scenario

The user starts in an empty temporary workspace and activates `openevolve-coding-agent`.

User intent:

```text
我想优化 admm 的自适应算法形式
```

The useful interpretation is not "write a generic ADMM essay." It is an agent-led OpenEvolve task:

- choose a measurable ADMM benchmark,
- establish the runnable environment,
- create the smallest valid OpenEvolve project,
- run a probe before spending more API budget,
- inspect best-program artifacts and adapt.

## Included Files

This example includes the main project files created during the session:

| Path | Purpose |
| --- | --- |
| `project/initial_program.py` | Starter evolvable `update_rho(...)` strategy with EVOLVE block markers. |
| `project/evaluator.py` | OpenEvolve `evaluate(program_path)` adapter. |
| `project/admm_benchmark.py` | LASSO instance generation, ADMM solver, baselines, scoring, and safety handling. |
| `project/config.yaml` | Small-run OpenEvolve config using `${LLM_API_KEY}` instead of a plaintext key. |
| `project/tests/test_evaluator_contract.py` | Contract tests for project shape, metrics, and bad-strategy penalties. |
| `project/README.md` | Commands for validating and running this sample project. |

Generated `runs/` artifacts are intentionally not included. The metrics below are copied from the original run summary.

## Good Flow

### 1. Initialize a visible workspace if the current one is empty

If the current directory is an empty auto-created workspace and no project path is supplied, initialize:

```bash
python3 scripts/interactive_session.py --workspace ~/Desktop/AI4Math-Evolving --json init
```

Report the absolute path and continue from there. Do not leave the user's project hidden in a generated temporary folder.

### 2. Establish the environment before deep algorithm design

Before asking benchmark-shaping questions, check:

- Python interpreter and version,
- `openevolve-run`,
- installed `openevolve` package,
- configured or missing API environment variable,
- model and base URL.

Example outcome:

```text
openevolve-run: /opt/anaconda3/bin/openevolve-run
OpenEvolve: 0.2.25 under /opt/anaconda3/bin/python
LLM_API_KEY: missing
```

When the user provides API settings in chat, acknowledge without repeating the secret value. Store or configure the secret outside project files. Project config should use:

```yaml
llm:
  api_base: "https://chat.ecnu.edu.cn/open/api/v1"
  primary_model: "ecnu-plus"
  api_key: "${LLM_API_KEY}"
```

If a real key was exposed in chat, recommend rotation after setup. Never write it into `config.yaml`, README, logs, examples, or summaries.

### 3. Turn the loose ADMM goal into a first experiment

Recommend one crisp first benchmark instead of asking for a broad menu. In this case, the first project used LASSO ADMM:

```text
minimize    0.5 * ||A x - b||_2^2 + lambda * ||z||_1
subject to  x = z
```

OpenEvolve only edits:

```python
def update_rho(rho, primal_residual, dual_residual, iteration, history):
    ...
    return new_rho
```

Keep the ADMM driver, LASSO instance generator, soft-thresholding, baselines, and safety clipping fixed inside the evaluator.

### 4. Define evaluator signals before running search

Use a primary metric such as `combined_score` where higher is better. Include enough supporting metrics to make results interpretable:

- convergence rate,
- mean iterations,
- failure rate,
- rho clipping rate,
- relative objective gap,
- fixed-rho baseline iterations,
- Boyd residual-balancing baseline iterations,
- case count.

Guard against score saturation. If the starter strategy is Boyd residual balancing, matching Boyd should be strong but should not receive a maximum score; leave search headroom for faster schedules.

### 5. Validate locally before using API budget

Before a real OpenEvolve run:

```bash
python3 scripts/validate_project.py --json <project>
python3 scripts/run_openevolve.py --dry-run --json <project>
```

Also run the evaluator directly or through tests. In the example, the contract tests verified:

- `initial_program.py` has EVOLVE block markers,
- `update_rho(...)` returns a finite positive number,
- `evaluator.evaluate(program_path)` returns numeric metrics,
- bad strategies are penalized rather than crashing the evaluator,
- the starter score leaves search headroom.

### 6. Run a probe before a formal run

A probe is a small real run used to check whether the end-to-end loop works and whether metrics have signal. It should answer:

- Can OpenEvolve call the LLM and evaluator?
- Are artifacts written?
- Do candidate programs fail safely?
- Is there any positive improvement before spending more budget?

Example probe:

```bash
openevolve-run initial_program.py evaluator.py \
  --config config.yaml \
  --output runs/probe-001 \
  --iterations 10
```

Observed result:

```text
fixed rho mean iterations: 94.0
Boyd baseline mean iterations: 33.0
probe best mean iterations: 31.8333
probe best combined_score: 88.2590
```

### 7. Run a larger search only after the probe has signal

Resume from the probe checkpoint to avoid throwing away useful candidates:

```bash
openevolve-run initial_program.py evaluator.py \
  --config config.yaml \
  --output runs/formal-001 \
  --iterations 50 \
  --checkpoint runs/probe-001/checkpoints/checkpoint_10
```

Example formal result:

```text
formal best combined_score: 89.1862
formal best mean iterations: 28.6667
candidate_convergence_rate: 1.0
candidate_failure_rate: 0.0
candidate_clip_rate: 0.0
```

The run found the best program around iteration 15 and stopped early after no further improvement.

### 8. Inspect the best program, not just the score

In the example, the best strategy did not invent a completely new ADMM method. It preserved residual balancing and evolved the update factor:

```text
tau = max(3.0 * (0.97 ** iteration), 1.2)
```

It also damped updates when primal and dual residuals were both decreasing. The interpretation was:

- more aggressive rho movement early,
- more conservative updates later,
- stable convergence without clipping.

Per-case comparison showed why aggregate metrics must be inspected:

```text
case                         fixed  Boyd  best
seed11_cond3                 66     20    14
seed17_cond12                52     27    22
seed23_cond45                139    45    47
seed31_cond90                103    28    35
seed43_cond25                24     24    24
seed59_cond120               180    54    30
```

The mean improved, but two cases regressed. A good next recommendation is to add held-out cases or worst-case scoring before promoting the strategy.

## What To Say To The User

Useful concise summaries:

```text
Probe means a small real run to test the full OpenEvolve loop before spending more API budget.
```

```text
The formal run improved mean iterations from Boyd's 33.0 to 28.67, with all six cases converging and no rho clipping. The improvement is real on this evaluator, but not uniform across cases.
```

```text
The best evolved rule kept residual balancing and changed tau into an aggressive-early, conservative-late schedule. I recommend adding held-out LASSO cases before treating it as a robust ADMM rule.
```

## Common Mistakes This Example Prevents

- Asking broad algorithm-choice questions before checking whether the user's OpenEvolve environment can run.
- Treating API setup as permission to write plaintext keys into config files.
- Starting with a long search before a probe validates evaluator signal.
- Reporting only `combined_score` and skipping best-program inspection.
- Ignoring per-case regressions hidden by an improved mean.
- Calling OpenEvolve a local service deployment instead of a Python package and CLI workflow.
