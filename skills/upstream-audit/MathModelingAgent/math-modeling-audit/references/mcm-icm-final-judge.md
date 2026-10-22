# MCM/ICM Final Judging Panel

This is a simulated 100-point final-panel framework, not a COMAP official quantitative scorecard. Review as if the paper is competing for Outstanding Winner or Finalist. Do not coach, reward effort, or supply missing evidence. CUMCM use is a paper-quality proxy, not official CUMCM/COMAP scoring.

## v0.5 review modes

PROJECT_INITIAL_REVIEW evaluates the current run and paper-evidence readiness before a complete manuscript exists. PAPER_FINAL_REVIEW evaluates a user-provided frozen manuscript plus a frozen evidence graph. Both modes use the same rubric intent and fourteen-section output. Every score row, cap and ceiling must cite evidenceRefs that resolve to artifact paths and hashes; prose evidence alone is invalid. Findings may open a correction lineage, but a score never mutates the parent run or silently upgrades a claim.

## Non-negotiable principles

- Do not assume the model is correct.
- Complexity, machine learning, optimization, neural networks, Monte Carlo, AHP, TOPSIS, entropy weights, or named algorithms earn no automatic innovation credit.
- Reject formulas without mechanism, results without traceable computation, figures without conclusions, and formalistic sensitivity analysis that misses critical parameters.
- Distinguish plausible from validated and a number from a credible modeling result.
- Cite page, section, equation, table, figure, or exact value whenever possible.
- If evidence is absent, write “论文未提供证据”.

## Stage 1: veto and award caps

Classify each item as 通过, 警告, 严重问题, or 一票否决风险:

1. every subproblem is answered;
2. no omission, off-target answer, or proxy substituted for the requested metric;
3. no critical mathematical formula error;
4. no dimensional, unit, or order-of-magnitude error;
5. no key result violates constraints;
6. summary, body, tables, and figures agree numerically;
7. conclusions follow from model and computation;
8. critical parameters have a source or defensible estimate;
9. critical model and algorithm are reproducible;
10. no data/future leakage or train-test mixing;
11. sources, data, and references are traceable and non-fabricated;
12. external methods, algorithms, images, and data are cited;
13. applicable annual COMAP page, anonymity, submission, citation, and AI/disclosure rules are satisfied;
14. core prediction/optimization/decision results are validated;
15. model structure fits the real mechanism or the mismatch is discussed.

Apply evidence-linked caps:

- missing core subtask: Outstanding and Finalist normally unavailable;
- conclusion-changing main-model math error: cap 69;
- completely unvalidated core prediction/optimization/decision model: cap 84;
- unsupported highly sensitive core parameter: cap 79;
- irreproducible critical result: cap 79;
- clear leakage or answer-information training: cap 69;
- main conclusion conflicts with calculation/figure: cap 74;
- almost no quantitative result: cap 59;
- suspected fabricated data/reference, plagiarism, or serious rule violation: stop ordinary scoring and report Disqualification Risk.

## Stage 2: 100-point scoring

### 1. Problem understanding, decomposition, and summary — 10

#### 1.1 Summary Sheet — 4

Check whether a 60-second reader learns the problem, models, method per subproblem, core quantitative results, recommendation, validation, and numbers consistent with the body. “Good performance” without numbers is weak evidence.

#### 1.2 Understanding and decomposition — 3

Check every explicit task, hidden constraint, practical objective, stakeholder, subproblem relation, and whether the paper solved an easier substitute problem.

#### 1.3 Assumptions, definitions, boundaries — 3

Check completeness, necessity, realism, simplification rationale, applicability, distinction among fact/assumption/setting, and support from data, literature, or sensitivity.

### 2. Data, evidence, and parameters — 12

#### 2.1 Source credibility — 3

For every key dataset record name, source, time, sample size, unit, and consuming model. Check temporal/spatial match, conflicts, update frequency, and traceability.

#### 2.2 Cleaning and preprocessing — 2

Check missing values, outliers, scaling, interpolation, smoothing, trend creation, method explanation, and before-after comparison.

#### 2.3 Representativeness, bias, leakage — 2

Check selection, survivor, temporal, spatial, and entity bias; train/validation/test separation; future and target leakage.

#### 2.4 Parameter determination and calibration — 3

Every key parameter must come from data estimation, literature, theory, calibration, inverse optimization, justified expert input, or an explicitly tested scenario. Unsupported values such as “let alpha=0.5” are penalized.

#### 2.5 Data-parameter-model consistency — 2

Check unit, temporal, and spatial consistency; physical meaning; whether data supports variables; and whether variables were invented only to fit a method.

### 3. Model formulation — 22

#### 3.1 Mechanism-to-mathematics mapping — 5

Check whether variables, equations, probability structure, objective, and constraints correspond to the real mechanism rather than mathematical assembly.

#### 3.2 Valuable innovation — 4

Credit mechanism design, justified coupling, structural adaptation, meaningful new indicators, evidence-based correction, or a genuinely useful solver. Do not credit stacking, deep learning by name, jargon, or unnecessary parameters. Ask whether a simpler model gives essentially the same answer.

#### 3.3 Variables, objective, constraints, equations — 4

Check every symbol, objective fidelity, complete real constraints, mathematical correctness, units, initial conditions, and boundary conditions.

#### 3.4 Assumption and internal consistency — 3

Check contradictions among assumptions/equations, changing parameter meanings, reused symbols, and circular logic.

#### 3.5 Complexity and explainability — 3

Check necessary complexity, overfitting, removable modules, interpretability, and fit to a four-day contest.

#### 3.6 Multi-subproblem unity — 3

Check whether earlier results genuinely support later tasks and whether the paper forms problem → core model → extension → verification → decision rather than a model collage.

### 4. Mathematical solution, algorithm, reproducibility — 16

#### 4.1 Derivation correctness — 4

Audit probability, calculus, differential/difference equations, matrices, statistics, normalization, weights, and recurrences. State whether an error changes the conclusion.

#### 4.2 Algorithms and numerical methods — 4

Check method suitability, initial values, stop/convergence conditions, numerical stability, hyperparameters, seeds, and local-versus-global claims.

#### 4.3 Reproducibility — 3

Check inputs, parameters, steps, outputs, code/pseudocode, and figure-to-computation traceability.

#### 4.4 Complexity, convergence, optimality — 3

Check time/space complexity, convergence, grid convergence, optimality proof/gap, baselines for heuristics, and multi-start tests.

#### 4.5 Sanity checks — 2

Check extremes, magnitude, bounds, units, sums/probabilities, resource capacities, nonnegative time, and common-sense violations.

### 5. Results, validation, robustness, credibility — 24

#### 5.1 Task completion — 4

Build requirement → model → output → conclusion mapping. A method without the requested number, ranking, strategy, prediction, or decision is incomplete.

#### 5.2 Numerical correctness and internal consistency — 4

Audit the three to ten most important results: value, unit, page, model, input, computation path, reproducibility, plausibility, validation, and PASS/WARNING/FAIL. Compare summary, body, tables, figures, and repeated values.

#### 5.3 Baseline and controls — 3

Check naive, traditional, historical, official, current, random, or literature baselines. A standalone 91% result has no comparative meaning.

#### 5.4 Sensitivity — 4

Identify truly critical parameters first. Check realistic perturbation, quantitative output change, thresholds, rank reversal, and failure. Ask how far a parameter moves before the conclusion changes.

#### 5.5 Robustness and uncertainty — 4

Check parameter, data, measurement, random, structural, and scenario uncertainty; Monte Carlo, bootstrap, confidence/prediction intervals, worst case, or robust optimization. Distinguish exact-looking numbers from credible intervals.

#### 5.6 Independent/external validation — 3

Prefer holdout, time extrapolation, backtest, real case, independent source, literature result, known theorem, or simulation-to-reality comparison. Training-data self-validation is weak.

#### 5.7 Failure scenarios and counterexamples — 2

Check extreme parameters, missing data, network failure, demand shock, environmental/policy change, and black swans. Outstanding papers know when they fail.

### 6. Conclusions, practical meaning, generalization — 8

#### 6.1 Model-grounded conclusions — 3

Trace data → model → result → conclusion. Penalize correlation written as causation, unlimited extrapolation, or precise policy advice without computation.

#### 6.2 Actionable recommendations — 2

Identify actor, action, timing, cost, risk, resources, and implementation constraints.

#### 6.3 Concrete limitations — 2

Name the most dangerous assumption, missing data, sensitive parameter, failure condition, and bias direction—not “more work is needed”.

#### 6.4 Transferability — 1

Assess extension across region, time, scale, network, and policy scenario.

### 7. Writing, figures, professional presentation — 8

#### 7.1 Structure — 2

Check logical service of sections, repetition, result-before-model reasoning, jumps, and clear section purpose.

#### 7.2 Figures — 2

Check necessity, axes, units, legend, self-contained caption, resolution, font, color, independent readability, and whether the figure supports a conclusion.

#### 7.3 Language — 1

Check concise, professional, accurate language without empty AI-style prose.

#### 7.4 Notation and formulas — 1

Check prior definition, consistency, numbering, units, and absence of decorative equations.

#### 7.5 Citations — 1

Check data, image, algorithm, and literature references and correspondence between text and bibliography.

#### 7.6 Page efficiency — 1

Check wasted space, unnecessary contents pages, code in body, hidden key reasoning, and information density under the page limit.

## Stage 3: model-by-model autopsy

For every M1, M2, ... report:

- problem solved, inputs, outputs, core equations, parameters, assumptions;
- why chosen and mechanism fit;
- mathematical correctness and parameter interpretability;
- solver and result;
- validation, sensitivity, robustness;
- strengths, most serious defect, simpler alternative, marginal value;
- score /10 and retain/simplify/restructure/untrustworthy.

Conclude unified system or model collage.

## Stage 4: key-result audit

Use:

| ID | Result | Source | Unit | Model | Reproducible | Magnitude | Validated | Importance | Verdict |
|---|---|---|---|---|---|---|---|---|---|

Then answer:

1. most credible result;
2. most fragile result;
3. result most dependent on manual parameters;
4. result most exposed to data failure;
5. result whose failure collapses the paper;
6. precision illusion;
7. all constraints satisfied;
8. better solution possibly missed;
9. stability under ±5%, ±10%, ±20% input perturbations;
10. reason to trust for real decisions.

## Stage 5: type-specific module

- MCM A: ODE/PDE/difference equations, initial/boundary conditions, dimensions, discretization, grid convergence, stability, parameter estimation, physical meaning.
- MCM B: graph/combinatorial structure, dynamic/integer programming, correctness, complexity, optimality, scalability.
- MCM C: quality, leakage, splits, feature engineering, variable selection, multicollinearity, overfitting, baselines, metrics, calibration, uncertainty, interpretation.
- ICM D: network construction, node/edge meaning, weights, metrics, objective, constraints, optimization, scale, perturbation stability.
- ICM E: boundary, time scale, lifecycle, environmental-economic-social tradeoff, weights, scenarios, uncertainty, long-run and unintended consequences.
- ICM F: correlation/causality, behavior, stakeholders, fairness, cost, incentives, execution, scenarios, unintended and heterogeneous effects.

## Stage 6: award judgment

Reference bands:

- 93–100 Outstanding Candidate;
- 87–92 Finalist;
- 78–86 Meritorious;
- 68–77 Honorable Mention;
- 55–67 Successful Participant;
- below 55 Unsuccessful Risk.

Outstanding additionally requires complete tasks, no major math/logic error, credible core validation, meaningful sensitivity/robustness, sourced key parameters, strong Summary Sheet, non-template modeling, closed model-result-conclusion loop, reproducibility, and one memorable contribution. High score without gates is Finalist or below.

## Required final output

Use exactly these top-level sections and fields.

### 一、60 秒终审印象

Paper objective; core methods; core results; strongest point; most serious first-impression problem; continue reading: 是/勉强/否.

### 二、一票否决与奖项封顶检查

For each risk: risk; evidence; severity; cap triggered; cap level.

### 三、总体评价与最终得分

Composite score /100; raw score; capped score; predicted award; Outstanding probability; Finalist-or-higher probability; core advantages; fatal weaknesses.

### 四、100 分分项评分

| 一级指标 | 二级指标 | 得分 | 满分 | 评委意见 |
|---|---|---:|---:|---|

Every row needs evidence.

### 五、题目要求覆盖矩阵

| 题目要求 | 是否完成 | 使用模型 | 最终结果 | 验证情况 | 判定 |
|---|---|---|---|---|---|

Find omissions and proxy answers.

### 六、模型逐个尸检

Review M1, M2, M3 separately using the autopsy template.

### 七、建模结果专项审计

Provide R1, R2, ... table and judge correctness, credibility, robustness, reproducibility, and practical meaning.

### 八、数据与参数审计

| 参数 | 数值 | 来源 | 是否有依据 | 敏感性 | 风险 |
|---|---:|---|---|---|---|

Name Achilles’ heel parameters.

### 九、灵敏度、稳健性与验证专项评价

State what authors did, omitted, whether existing analysis is effective or formalistic, and validation needed for Finalist/Outstanding.

### 十、数学与计算正确性抽查

Check at least three formulas, three numbers, one algorithm, one figure, and one final conclusion when available; recompute when possible.

### 十一、图表与写作评审

Name best/worst/delete/add figures, hardest and most wasteful sections, and whether Summary Sheet is final-round quality.

### 十二、Outstanding Winner 差距分析

Explain why another paper wins; missing decisive evidence; current award level; three blockers to Finalist; three blockers to Outstanding; genuine innovation; removable model.

### 十三、修改优先级

P0 no high award without fix; P1 Meritorious vs Finalist; P2 Finalist vs Outstanding; P3 polish. Every item states problem, severity, fix, expected gain, and low/medium/high cost.

### 十四、评委最终裁决

One-sentence summary; most likely award; recommend Final Round yes/no; Head Judge defense yes/no; reason; final verdict.

Do not inflate for encouragement. Use “技术复杂度高于证据强度” or “presentation quality exceeds modeling quality” when supported. The final question is how credible the conclusions are and why they belong among the best papers.
