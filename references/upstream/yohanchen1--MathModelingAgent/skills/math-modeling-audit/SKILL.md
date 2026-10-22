---
name: math-modeling-audit
description: This skill should be used when the user asks to "独立核验数学模型", "检查推导", "寻找反例", "审计建模报告", "按 MCM/ICM 终审框架打分", "verify this model", or needs an artifact-only adversarial audit of mathematical claims, data, code, results, citations, or a competition paper.
whenToUse: Use for existing artifacts and papers; do not take over open-ended model construction or silently rewrite the audited work.
user-invocable: true
---

# Math Modeling Audit

## Goal

Independently decide which claims in an existing artifact pass, fail, or remain inconclusive, and why.

## Interface

Accept a paper, model, derivation, code/result artifact, or MathModelingAgent run. Optionally accept the original problem, competition year/code, target claims, and assurance level.

Return per-claim verdicts, evidence levels, counterexamples, reproducibility findings, residual risk, and—only for MCM/ICM judging intent—the fixed final-panel report.

## Workflow

1. Freeze the artifact set and record review coverage.
2. Reconstruct claims, assumptions, obligations, and evidence without trusting the author’s summary.
3. Apply `references/verification-protocol.md` and `references/evidence-levels.md`.
4. Audit data, parameters, leakage, citations, and reproducibility with `references/data-citation-audit.md`.
5. Recompute applicable formulas and results through independent tools.
6. Seek boundary cases, counterexamples, alternative explanations, and simpler models.
7. Output PASS, FAIL, or INCONCLUSIVE per claim; do not silently repair the source.
8. For project initial review, evaluate the current run and paper-evidence readiness. For complete-paper final review, freeze the manuscript and evidence graph, load references/mcm-icm-final-judge.md, validate arithmetic with scripts/mcm-score.mjs, and preserve its fourteen-section output. Findings can request a correction lineage but never mutate the audited parent.

## Invariants

- Paper prose and solver success are not verification artifacts.
- Missing evidence is reported, never supplied on the author’s behalf.
- Lean verifies the formal statement, not its natural-language fidelity or data pipeline.
- A score never feeds back into the solver’s SOLVED gate.
- Disqualification risk stops ordinary award scoring.

## Boundaries

Do not edit the audited artifact. Do not reward complexity or presentation without evidence. Do not load the large MCM/ICM rubric for generic audits.
