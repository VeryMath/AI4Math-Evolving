# Mathematical Candidates and executable searches

A Candidate is the mathematical object being improved, together with a representation that can be changed. The evaluator stays fixed during a comparison. An admissible Candidate is not necessarily a valid proof or counterexample: its mathematical status must be reported separately.

| Object | Change | Search signal | Final mathematical check |
| --- | --- | --- | --- |
| Algorithm | Step, update formula, decomposition, stopping rule | Error, iterations, runtime, constraint violation | Assumptions, stability/convergence argument, and evaluation beyond the search inputs |
| Proof candidate | Lemma, decomposition, invariant, coefficient | Unresolved obligations, exact identity residual | Complete argument or proof-assistant acceptance under the stated assumptions |
| Counterexample | Graph edge, matrix entry, discrete assignment | Violation magnitude or number of surviving witnesses | All assumptions hold and the exact claimed conclusion fails |
| Conjecture/construction | Formula, hypothesis, combinatorial structure | Exact small cases, bounds, target property | Separate evidence for the concrete object from any general theorem |

## Direct execution

From the package directory:

```bash
python3 examples/mathematical_evolution.py --case all --rounds 10 --output .verification/mathematical-evolution.json
```

Use `--case algorithm`, `--case proof`, or `--case counterexample` to run one search. The program directly computes each mathematical evaluation, uses its observations and failed proposals to produce the next changes, selects an improved parent, and stops when no proposed legal change strictly improves the objective or the round budget is exhausted. JSON records contain every parent, proposal, mutation, metric, mathematical check, selection, and failure feedback. Each proposal's `feedback_used` identifies the current coefficient mismatch, failed step, or graph observation that it used; ordinary algorithm neighbors are labeled as such. Rational values are stored as readable fractions; JSON is an output format, with no extra dependencies.

The proposal rules are deterministic and read the evaluator's current result and prior failed proposals. These runs establish that the concrete mathematical searches execute; they do not measure model creativity, OpenEvolve performance, or research novelty.

Every case and the top-level result include `target_reached`. The algorithm target requires legal spectral contraction and improvement over the initial error; the proof target requires `exact_sos_identity`; the graph target requires `counterexample_verified`. Exit `0` means every selected target was reached. Exit `1` means a target remains unmet when the round budget or local progress ends; stdout prints the complete partial result, including the proposals, and `--output` also saves it. For example, `--case proof --rounds 1` exits `1` with a nonzero identity residual. No additional flag changes these mathematical success conditions.

## Algorithm: gradient descent on quadratics

For `f(x) = x^T A x / 2`, evolve the fixed step in `x <- x - step*A*x`. The search evaluates 12 actual rational iterations from the all-ones vector for diagonal spectra `(1,2,4)` and `(1,3,9)`. It minimizes the worst mean squared error across those two objectives. The initial step is `1/64`; each round tries doubling it and changing it by `±1/64`. If a previous proposal failed the spectral condition above the current step, propose the midpoint toward the smallest such rejected step. This repair is computed from the failure history rather than from a prescribed round or final value.

The evaluator rejects steps outside `0 < step < 2/9`. For symmetric positive definite `A` with spectrum in `[1,9]`, diagonalizing `I-step*A` gives the error contraction bound `max(|1-step|, |1-9*step|)`. This establishes convergence for that stated quadratic class, while the measured finite-iteration improvement concerns only the two evaluated objectives.

A direct run verified on 2026-11-01 made five improving rounds, selecting `step=25/128`, with contraction bound `103/128`. In round four, `step=1/4` failed the stability condition; round five used that failure and its current `9/64` step to propose the selected midpoint `25/128`. The worst mean squared error decreased from `0.454826833171` to `0.00223996531907`. The sixth round found no improving proposal. This establishes the stated local search result and spectral bound.

## Proof candidate: an exact quartic inequality

The goal is to prove, for all real `x,y`,

```text
x^4 + y^4 - x^3*y - x*y^3 >= 0.
```

Represent a proposed proof by nonnegative rational `(a,b)` in

```text
a*(x-y)^4 + b*(x^2-y^2)^2.
```

Start at `(0,0)`. Compare all five exact polynomial coefficients with the target and minimize their total absolute error. Read the evaluator's coefficient differences to choose a correction: first inspect mixed monomials distinguishing `a`, then the remaining affected terms; for `b`, first inspect the `x^2*y^2` mismatch. Change a weight in the direction that reduces that mismatch, by at most `1/8`. Reject negative square weights and evaluate the full identity before accepting a proposed correction. A nonzero error is a failed proof identity, and its actual residual determines the next refinement.

A direct run verified on 2026-11-01 made eight improving rounds, reducing coefficient error from `4` to `0`; the ninth found no improvement. It recovered

```text
x^4 + y^4 - x^3*y - x*y^3
  = (1/4)*(x-y)^4 + (3/4)*(x^2-y^2)^2 >= 0.
```

Exact rational expansion checks the identity; both right-hand terms are nonnegative squares. This is an algebraic proof for all real inputs. No numerical sampling establishes the proof, and no proof assistant was run. The square basis is supplied to the search, so this example does not show automatic discovery of a proof language or basis.

## Counterexample: a graph conjecture

Refute the claim: every finite connected simple undirected graph on `n >= 3` vertices with at least `n` edges has a Hamiltonian cycle.

Start at the complete graph on five vertices and propose deleting one edge. Normalize each undirected edge to its unordered endpoint pair; reject duplicate edges, self-loops, malformed endpoints, or a vertex count outside the stated conjecture. Reject disconnected graphs or graphs with fewer than `n` edges. Enumerate all cyclic vertex orders, fixing the first vertex and removing reversal duplicates, to count Hamiltonian cycles. Minimize this count, then the number of edges to refine a found counterexample.

Order deletion proposals using the current degrees. If an earlier removal disconnected the graph, preserve that edge on later rounds: deleting additional edges cannot restore connectivity. Stop proposing deletions when the current edge count is `n`, since the evaluator's assumption would be violated. In the recorded run, round four's failed removal of `(0,4)` caused round five to preserve it; that feedback appears explicitly in the next proposals.

A direct run verified on 2026-11-01 made five improving rounds, reducing the edge count from `10` to `5` and the Hamiltonian-cycle count from `12` to `0`. The sixth found no admissible improvement. Its selected edge set was

```text
{(0,4), (1,4), (2,3), (2,4), (3,4)}.
```

Connectivity and the edge count establish the assumptions. Exhaustive enumeration confirms the absence of a Hamiltonian cycle. Independently, vertex `0` has degree one, whereas every vertex on a cycle has two incident cycle edges; this verifies the counterexample without relying on the search score. The result concerns the explicit graph and refutes the displayed conjecture. It does not classify all non-Hamiltonian graphs.

The evaluator directly checks ordinary Hamiltonian cycles as comparison cases. Reversed duplicate edges, self-loops, and out-of-range endpoints raise `ValueError` at input validation. Well-formed graphs that fail the conjecture assumptions return `valid: false` with the failed assumptions.

## Feedback and transfer to model proposals

Use the same mathematical problem and evaluator when replacing the deterministic proposer with an agent or OpenEvolve. For each proposed change, provide the selected parent, permitted editable part, exact failure or obligation, and the target metric. Keep proof failures distinct from invalid inputs and evaluator errors.

Examples of useful feedback are: the step violates its spectral range; a polynomial's `x^2*y^2` coefficient is wrong; a graph has become disconnected; or a Hamiltonian cycle still exists. Record a rejected proposal rather than editing the evaluator until it passes.

The direct program contains one implementation of each mathematical evaluator. The separate [JSON model adapter](../examples/model_candidates/README.md) reuses these evaluators, records actual model proposals and token usage, and passes mathematical feedback into later requests. The [validated model run](model-validation.md) reports its own generated candidates and scope.
