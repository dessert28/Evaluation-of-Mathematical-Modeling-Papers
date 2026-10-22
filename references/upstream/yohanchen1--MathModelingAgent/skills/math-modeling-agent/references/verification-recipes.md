# Verification Recipes (v0.5)

Recipes are selected by claim type before a phase can advance. A verification verdict is local to one recipe; it does not directly set an obligation or claim verdict.

## Status layers

- Verification: PASS, FAIL, INCONCLUSIVE, NOT_RUN.
- Obligation: OPEN, SATISFIED, BLOCKED, WAIVED, STALE.
- Claim: SUPPORTED, CONDITIONAL, INCONCLUSIVE, REFUTED, STALE.
- Run: lifecycle state such as VERIFY, EVALUATE, REVISE, CONDITIONAL or SOLVED.

## Recipes

| Recipe | Required checks | Typical claim |
|---|---|---|
| data | schema, ids, references, hash, independent-parser | attachment/data interpretation |
| numeric | recompute, domain, strict, tolerance, counterexample | numeric value or formula |
| feasibility | all-constraints, actual-output, strict-and-tolerance | optimization/engineering feasibility |
| optimization | objective-scope, coverage, initialization, local-global-label | best-found or optimum claim |
| simulation | baseline, bounds, sampling, independent-implementation | simulation/ratio |
| report | nine-sections, why-how-what-check, coverage, symbols, citations | paper/report completeness |
| reproducibility | snapshot, command, environment, hash, clean-rerun | reproduction |
| branch-coverage | candidate-enumeration, branch-switch | branch stability |

## Independence rule

Two checks count separately only when their calculation path or code provenance differs. Reusing a deterministic result, solver-internal result, branch summary, derived artifact, code path, or reprint does not create a second independent verification. The runner records an independenceKey and rejects duplicate or summary-derived keys.

## Numeric and output rules

A numeric recipe reports strict and tolerance outcomes separately. A display format is not numeric quantization. When an output is rounded, the quantized values are generated first and every original hard constraint is rerun on the quantized artifact.

## Branch rules

If a declared four-branch problem executes only one branch, the recipe returns or raises branch-switch-not-tested; branch_changed=false is not evidence of stability. Branch ranking from an existing solver summary is only a consistency check, not an independent rerun.

## Benchmark rule

An expensive recipe must carry a PASS benchmark artifact before full execution. The benchmark records command, input subset, expected time, environment, stdout/stderr and exit code. Missing or failed benchmark evidence blocks the expensive recipe.

## Scope rule

If a required check was not executed, the recipe is INCONCLUSIVE. If the user explicitly waives the check, the result is WAIVED and may only contribute to a CONDITIONAL run.
