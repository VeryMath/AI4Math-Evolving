# Troubleshooting mathematical evolution

- **No meaningful comparison:** identify the mathematical objective and baseline before running search. If a theorem has no trustworthy partial score, refine proof obligations directly instead of inventing a success metric.
- **Invalid Candidate:** report the exact failed assumption or representation error. Retain the failed proposal so the next mutation can address it.
- **High score but failed proof:** preserve the useful numerical observation and state the remaining obligation. Do not present sampling or an incomplete identity as proof.
- **Evaluator exception:** record the exception and affected Candidate; repair an evaluator defect separately from Candidate changes and rerun affected comparisons.
- **No progress:** inspect rejected proposals and objective saturation. Explain whether the legal neighborhood, representation, or mathematical approach needs to change; do not silently change the goal.
- **No model runtime:** check the selected interpreter and the actual CLI. An executable left on `PATH` may still fail because its package is missing. Continue mathematical work that does not require that runtime and report that no model run occurred.
- **API errors:** confirm only whether the configured environment variable is set. Keep key values out of config, logs, and messages.
- **Missing OpenEvolve result:** inspect the run's actual logs and best-object outputs. Do not replace a failed run with the historical ADMM result or the deterministic examples.
