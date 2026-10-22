# Independent Verification Protocol

## Freeze inputs

Hash the exact artifact set, problem statement, data, code, configuration, and environment evidence. Record anything unavailable.

## Rebuild the claim map

For each material claim record exact text, source location, assumptions, required evidence, supplied evidence, and independent countercheck.

## Attack order

1. task coverage and proxy substitution;
2. units, dimensions, domain, bounds, and constraints;
3. derivation and implementation consistency;
4. data leakage, labels, splits, preprocessing, and post-hoc parameters;
5. baseline, uncertainty, sensitivity, and external validity;
6. reproducibility and citation truth;
7. counterexamples, failure cases, and simpler alternatives.

## Verdicts

- PASS: required obligation is supported by reproducible evidence.
- FAIL: a contradiction, counterexample, invalid method, or failed reproduction defeats the claim.
- INCONCLUSIVE: evidence is insufficient or unavailable.

Never convert INCONCLUSIVE to PASS because the approach looks reasonable.
