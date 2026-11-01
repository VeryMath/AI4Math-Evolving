---
name: openevolve-experiment-workflow
description: Use when evolving AI4Math mathematical Candidates such as algorithms, proof candidates, counterexamples, conjectures, or constructions through mutation/refinement, an evaluator, mathematical verification, and recorded failure feedback; also use for bounded OpenEvolve code or prompt search.
---

# OpenEvolve Experiment Workflow

Turn a mathematical goal into a repeated search over explicit **Candidates**. A Candidate can be an algorithm, proof argument, graph, inequality, conjecture, or other mathematical object; code and prompts are possible representations. Keep the mathematical statement, evaluator, and editable object distinct.

Reply in Chinese by default. Inspect the user's current project and existing results before asking questions. Continue within the agreed scope and budget; ask only for information that changes the work.

## 1. Check whether the object can evolve

Before selecting a search tool, establish:

- **Representation:** write the Candidate in a form that can be inspected and changed, including its mathematical domain and assumptions.
- **Permitted changes:** specify legal mutations and refinements. For example, change an algorithm's step, add a proof lemma, or remove a graph edge while retaining the conjecture's assumptions.
- **Evaluation:** define a meaningful objective and compare against an initial Candidate. A partial proof score may guide search but cannot establish a theorem.
- **Mathematical check:** state what establishes the final claim: exact algebra, a proof, a proof assistant, an exhaustive finite computation, or a verified counterexample. State the scope of numerical evidence.
- **Feedback:** retain failed Candidates and the concrete failed assumption, coefficient, obligation, input, or evaluator error so the next proposal can address it.

If no useful comparison or mathematical check is available, first make that missing piece concrete. Do not force an arbitrary score onto an open research question.

Record the Candidate's object, editable part, objective, constraints, and run budget in the existing project notes. Load [mathematical-candidates.md](references/mathematical-candidates.md) for worked representations and evidence limits.

## 2. Run the mathematical loop

1. Evaluate and mathematically inspect the initial Candidate.
2. Propose a mutation or refinement, naming its parent and the observation it addresses.
3. Evaluate the proposed object under the same assumptions, inputs, and objective. Retain evaluator failures as feedback rather than assigning them a favorable score.
4. Check its mathematical obligations separately from the search score. A syntactically valid proof candidate can still be unproved; a high numerical score can still violate a theorem's hypotheses.
5. Select a legal improvement, or explain why it was rejected. Preserve informative failures in ordinary run notes or result files.
6. Use the observed feedback to propose the next change. Continue until the agreed budget, a verified target, or an explained lack of progress.

For every evaluated proposal, record the round, parent, change, object, metrics, mathematical-check result, and feedback. Records may be corrected normally; no special file identity or execution permission system is needed.

Before reporting success, re-evaluate the selected object and inspect the strongest available mathematical argument. Report improvement and mathematical validity as separate findings. Route a substantive proof obligation to `proof-blueprint-review` or `lean-formalization` when those skills are available.

## 3. Choose and state the search backend

- **Direct mathematical search:** use executable finite search, symbolic computation, or numerical optimization when it suits the Candidate. The bundled examples use deterministic local search and report every evaluated proposal.
- **Model-generated OpenEvolve search:** use OpenEvolve when the model should propose edits to the Candidate representation. Inspect the installed package/CLI, project, model, endpoint, and API environment variable only when needed for that run. Respect the user's agreed iteration and cost budget.
- **Agent-guided refinement:** use explicit edits with feedback when the object is not yet suited to automatic generation. Name who or what produced each proposal.

Never describe deterministic search, a manual rewrite, a command illustration, or an old result as a newly completed OpenEvolve/model run. Report the actual backend, completed rounds, evaluator failures, selected object, and unresolved checks.

## OpenEvolve adapter

For a code-backed project, keep the editable Candidate in `initial_program.py`, supply `evaluator.py` with `evaluate(program_path)`, and use the installed OpenEvolve configuration format. The evaluator must inspect the mathematical object, keep assumptions fixed, and return numeric metrics; use `combined_score` when the project expects it. Keep detailed failure feedback alongside those metrics using the installed evaluator's supported return format.

Load [project-format.md](references/project-format.md) before creating or adapting these files. Run the installed CLI directly. Keep provider keys in environment variables, referenced by placeholders such as `${LLM_API_KEY}`. Do not repeat secrets in chat or tracked files.

For data-shaped Candidates, prefer the [JSON model examples](examples/model_candidates/README.md): they parse generated data without executing generated code. OpenEvolve 0.4.0 accepts `EvaluationResult` with numeric metrics and feedback artifacts. The example fixes the case and graph size in the evaluator, runs one proposal at a time, and passes evaluated proposals and mathematical feedback into the next request. Load [model-validation.md](references/model-validation.md) for actual model results and their scope.

Package installation and API setup are needed for a model run; they are not prerequisites for mathematical reasoning or the dependency-free examples below. The historical session helpers remain available for existing projects; the mathematical workflow does not require them.

## Executable mathematical examples

Run from this package directory:

```bash
python3 examples/mathematical_evolution.py --case all --rounds 10 --output .verification/mathematical-evolution.json
```

This directly executes three multi-round searches:

- **Algorithm:** evolve a gradient step using exact rational iterations on diagonal quadratic objectives and check the spectral contraction condition.
- **Proof candidate:** refine nonnegative rational square coefficients until exact polynomial expansion proves a quartic inequality for all real inputs.
- **Counterexample:** remove edges from a five-vertex graph, retain the conjecture's assumptions, enumerate Hamiltonian cycles, and independently inspect a degree-one witness.

The program uses only Python's standard library. Its next proposals read evaluator feedback: rejected unstable steps guide a midpoint repair, polynomial coefficient mismatches guide proof corrections, and failed graph deletions identify edges to retain. `feedback_used` records the consumed observation. Undirected graph inputs are normalized and invalid simple-graph representations are diagnosed. It computes the trajectory during execution and does not call a model or OpenEvolve. Read [mathematical-candidates.md](references/mathematical-candidates.md) for objectives, verified results, and limits. The older [ADMM session](examples/admm-adaptive-rho-session/README.md) is historical material, not evidence of a new run.

The example reports `target_reached` for each case and overall. It exits `0` only for a legal improving algorithm, an exact proof identity, and a verified graph counterexample, as selected by `--case`. An unmet target exits `1` after writing the full partial result; report that mathematical outcome rather than calling an incomplete search successful.

## Reporting

Give the selected Candidate and its location, baseline comparison, actual search backend and rounds, mathematical verification and scope, and the most useful remaining step. Say when a result is a numerical observation, exact finite check, algebraic proof, or proof-assistant result. Improved metrics alone do not establish correctness or a new research result.

Read [troubleshooting.md](references/troubleshooting.md) when execution, evaluation, or Candidate interpretation fails.
