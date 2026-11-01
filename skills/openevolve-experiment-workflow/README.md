# Mathematical Candidate Evolution with OpenEvolve

中文说明：[README.zh-CN.md](README.zh-CN.md)

Evolve mathematical **Candidates** through changes, evaluation, mathematical checks, and failure feedback. Candidates include algorithms, proof arguments, counterexamples, conjectures, and constructions; code and prompts are possible representations.

The skill first checks whether the object can be represented, legally changed, meaningfully compared, and mathematically verified. Each round records its parent, proposed change, object, metrics, mathematical status, and feedback. An improved search score and a valid mathematical conclusion are reported separately.

## Start a task

```text
Use $openevolve-experiment-workflow.
My goal is: <algorithm / proof / counterexample / construction>.
Inspect the existing project, define the Candidate and legal changes, evaluate
its initial form, and perform repeated refinements within <budget>.
Record failed proposals and verify the selected mathematical object.
```

Use direct mathematical search, agent-guided refinement, or an actual OpenEvolve model run as appropriate. State which backend generated the proposals. Configure OpenEvolve and provider access when a model run needs them; continue already authorized work within the agreed budget. Keys belong in environment variables.

## Run three mathematical examples

From this package directory, with Python 3.9 or later:

```bash
python3 examples/mathematical_evolution.py --case all --rounds 10 --output .verification/mathematical-evolution.json
```

Only Python's standard library is needed. Use `--case algorithm`, `proof`, or `counterexample` to run one example. The output file contains every computed proposal and its evaluation, selection, failure feedback, and `feedback_used` describing which observation produced the change.

Each case and the overall output include `target_reached`. The algorithm must improve over its baseline with a valid spectral check; the proof must establish the exact identity; the graph must verify a counterexample. The command exits `0` only when all selected targets are reached. If the budget ends or progress stops before that, it prints the full partial results, also saves them when `--output` is given, and exits `1`; for example, `--case proof --rounds 1` leaves an unproved candidate. CI therefore checks the actual mathematical targets.

| Example | Actual multi-round result, verified on 2026-11-01 | Mathematical evidence |
| --- | --- | --- |
| Gradient step on two quadratic objectives | Five improving rounds: step `1/64` → `25/128` | Exact rational iterations; spectral contraction bound `103/128` for the stated quadratic class |
| Quartic inequality proof candidate | Eight improving rounds: identity error `4` → `0`, square weights `(1/4,3/4)` | Exact polynomial identity and nonnegative squares for all real inputs |
| Graph counterexample | Five improving rounds: `10` → `5` edges, Hamiltonian cycles `12` → `0` | Connected graph with `m=n=5`; exhaustive cycle enumeration plus a degree-one witness |

The next proposals consume evaluator observations: an unstable step triggers a smaller refinement, unmatched polynomial coefficients determine a coefficient's direction, and a disconnected graph proposal prevents repeating that edge removal. Undirected edges are normalized; duplicate edges, self-loops, and invalid endpoints are rejected with a reason.

The program generates and evaluates its proposals during execution. These are deterministic mathematical searches, with no model or OpenEvolve invocation. The square basis and feedback rules are supplied; the examples do not establish model ability, global optimality, or new research results. See [worked cases and limits](references/mathematical-candidates.md).

## OpenEvolve projects

The [model example](examples/model_candidates/README.md) uses OpenEvolve 0.4.0 to generate JSON Candidates and fixed evaluators to inspect their mathematics without executing generated code. It processes one proposal at a time and includes evaluated proposals and mathematical feedback in later prompts. A real `ecnu-max` run on 2026-11-01 made seven calls and reached all three mathematical targets: step `1/10`, exact weights `(1/4,3/4)`, and a connected five-vertex, six-edge counterexample. SymPy and NetworkX independently checked these results. See [model validation and limits](references/model-validation.md).

Existing code-backed projects can retain `initial_program.py`, `evaluator.py`, and their installed configuration format. Keep hypotheses and mathematical checks fixed during comparisons. Read [project format](references/project-format.md) and [troubleshooting](references/troubleshooting.md).

The primary workflow is [SKILL.md](SKILL.md); the agent entry point is [agents/openai.yaml](agents/openai.yaml). Existing helper scripts and the [historical ADMM session](examples/admm-adaptive-rho-session/README.md) remain available for earlier projects. Historical metrics do not establish a new run.

## Install

```text
Install the openevolve-experiment-workflow skill from
https://github.com/VeryMath/AI4Math-Evolving.git.
Read its SKILL.md and install the complete package with its references and examples.
Verify that $openevolve-experiment-workflow is discoverable.
```
