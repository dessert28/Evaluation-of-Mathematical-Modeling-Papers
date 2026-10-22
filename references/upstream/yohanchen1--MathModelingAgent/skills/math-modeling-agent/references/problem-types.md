# Problem Types and Obligations

| Type | Primary output | Mandatory checks |
|---|---|---|
| Symbolic calculation | exact expression or roots | domain, equivalence, substitution, singular cases |
| Theorem/proposition | proof or counterexample | quantifiers, assumptions, boundary cases, proof completeness |
| Deterministic numerical | approximation | residual, convergence, stability, discretization error |
| Feasibility | satisfying assignment | every constraint, tolerance, certificate |
| Optimization | local/global solution | objective fidelity, constraints, bounds, optimality gap/certificate |
| Statistical estimation | estimate and uncertainty | sampling assumptions, interval, residual diagnostics |
| Prediction/classification | out-of-sample performance | leakage-safe split, baseline, calibration, uncertainty |
| Causal inference | identified effect | estimand, temporal order, confounding, sensitivity |
| Stochastic/risk | distribution or risk measure | distribution assumptions, Monte Carlo error, tail behavior |
| Inverse problem | recovered parameter/structure | identifiability, conditioning, regularization |
| Mechanism/system | dynamic behavior | structural validity, units, calibration, initial/boundary conditions |
| Decision analysis | recommendation | preference/weight source, constraints, sensitivity, regret |
| Exploratory analysis | hypotheses/patterns | no causal upgrade, multiplicity, robustness |
| Literature synthesis | supported method/fact | source verification, applicability, conflicting evidence |

Use multiple labels when necessary, but choose one primary output and one explicit assurance mode.
