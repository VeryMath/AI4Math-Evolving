# Adapting a mathematical Candidate to OpenEvolve

Keep the mathematical object and the editable Python representation distinct. A proof Candidate might be rational square coefficients, while its program only returns those coefficients. A graph Candidate might be an edge list. Do not allow edits to the evaluator's hypotheses, reference values, or mathematical checks during a comparison.

For an existing code-backed OpenEvolve project, inspect:

- `initial_program.py`: returns or implements the Candidate; use the project's editable regions, commonly `EVOLVE-BLOCK-START` / `EVOLVE-BLOCK-END`.
- `evaluator.py`: `evaluate(program_path)` evaluates that representation and returns numeric metrics. Keep failure details in the installed evaluator's supported feedback format or ordinary result files.
- `config.yaml`: model, endpoint, search settings, evaluator settings, iteration budget, and output location as supported by the installed version.

Use a primary metric such as `combined_score` when the project expects it, with a documented direction. Keep admissibility and mathematical validity separate: an algebraically incorrect proof candidate may receive a useful residual score, but must remain `unproved`. A counterexample is successful only if every assumption holds and the conclusion fails.

Run the installed CLI directly after inspecting its help and the project. One code-backed invocation is:

```bash
openevolve-run initial_program.py evaluator.py --config config.yaml --iterations 10 --output runs/search
```

This is a command example, not evidence of execution. Reuse the user's agreed budget and current project path; do not require extra approval for already authorized edits or runs.

Provider keys belong in environment variables. Config may reference a placeholder such as `${LLM_API_KEY}` when supported by the installed configuration loader. Do not print secret values while checking environment availability.

OpenEvolve's upstream [README](https://github.com/algorithmicsuperintelligence/openevolve#readme) documents both file-based CLI use and library entry points. Installed releases can differ; inspect the actual runtime instead of claiming compatibility from a documentation example. Package setup is not required for the direct standard-library mathematical examples.

## JSON candidates with OpenEvolve 0.4.0

The [model examples](../examples/model_candidates/README.md) use `language="json"`, `file_suffix=".json"`, and `diff_based_evolution=False`. The initial files contain only candidate data. Three thin evaluator modules fix the task independently of model output and reuse the same mathematical calculations as the direct examples. The graph case fixes five vertices to bound exhaustive enumeration.

`EvaluationResult.metrics` contains numeric `combined_score`, `admissible`, and `target_reached`; `artifacts.mathematical_feedback` contains exact errors, failed assumptions, and mathematical status. Malformed data raises an exception. A mathematically inadmissible but well-formed candidate receives score `-1` and a concrete explanation. A partial polynomial identity can have a positive score while remaining unproved.

The runner calls `OpenEvolve.run(iterations=1)` and loads its checkpoint before the next request. It also includes prior evaluated proposals and feedback in the next system prompt. This ensures completed feedback is available before each proposal even when the installed controller normally submits work in advance. No configuration containing an expanded key is written. Provider credentials stay in memory, and raw logs remain in the ignored output directory.
