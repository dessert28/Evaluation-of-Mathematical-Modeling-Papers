# Modeling Methodology

## Mechanism first

Map real objects to variables, mechanism to equations, reality constraints to mathematical constraints, and requested decisions to objective/evaluation criteria. Never choose a named method first and force the problem into it.

## Candidate portfolio

Always begin with a defensible baseline. Add a more complex candidate only when it targets a documented baseline failure. Candidates must differ in mechanism, information, assumptions, or verification route—not wording.

For each candidate record:

- stable ID and parent/fork;
- target subproblem and claims;
- mechanism and equations;
- assumptions and parameter sources;
- input requirements;
- expected information gain;
- verification obligations;
- stop/abandon conditions;
- complexity, interpretability, and compute cost.

## Selection

Prefer the simplest candidate that meets evidence and accuracy requirements. Compare verification coverage, critical issues, empirical performance, robustness, complexity, interpretability, cost, and reproducibility. Do not reward model count, deep learning, metaheuristics, AHP, TOPSIS, entropy weights, or Monte Carlo by name.

## Core checks

- units and dimensions;
- limiting and boundary cases;
- known special cases;
- constraint completeness;
- identifiability and conditioning;
- convergence and numerical stability;
- data leakage and post-hoc parameters;
- baseline and ablation;
- sensitivity of conclusion-changing parameters;
- model-result-conclusion traceability.
