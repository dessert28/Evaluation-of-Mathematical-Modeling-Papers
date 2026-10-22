# Claims and Evidence

## Claim record

Store claim ID, exact wording, type, scope/quantifiers, assumptions, risk, verification obligations, evidence IDs, countercheck, status, and limitations.

## Assumption record (v2)

Store id, statement, scope ('global' for whole-problem assumptions, or a subproblem id list), source category, risk, sensitivity plan, validation status, affected claims, status (active/revised/superseded), and revisionHistory [{at, reason, changedTo}]. Allowed source categories are problem, data, theory, verified literature, domain instruction, and modeling simplification.

Two classes: G-class (global, confirmed once in the panorama layer via D2-G) and S-class (per subproblem, confirmed via D2-SPi). Claims carry an `assumptions` field listing the assumption ids they depend on; when an assumption is revised, dependent claims are marked stale and must carry post-revision evidence before a terminal state (validate warns otherwise).

Every assumption additionally carries a `basis` field — the evidence chain behind it: `problem-quote` (exact original wording), `data` (evidence id + statistic), `literature` (source id + excerpt location), or `llm-judgment` (explicitly flagged as the LLM's own inference, challengeable in D2).

Revisions are hard operations: when an assumption is revised, every claim/obligation that depended on it is marked `stale: true` with the revising assumption id, and the affected verification reruns (or the conclusion is explicitly downgraded) before any terminal state.

## Robustness obligation (v2, terminal gate)

Every subproblem that produces numerical conclusions registers a robustness obligation automatically. Execution standard: perturbation targets (problem parameters, data-fitted values, objective/weighting choice, aperture/boundary rules, discretization) × per-parameter magnitudes (±0.1%/±1%/±10% by parameter nature) × judgment (does the conclusion direction flip? what is the magnitude of change?), reported as a table (参数/扰动/结果变化/对结论影响). The run-state gate refuses terminal states without a PASSED robustness obligation unless scope.robustnessExempt is set with a reason (pure proofs only).

## Evidence record

Store evidence ID, method, tool, timestamp, covered claim IDs, input/output hashes, command/workdir/environment, exit code, output artifacts, tolerance, limitations, and level:
DERIVED, EXECUTED, VERIFIED, INDEPENDENTLY_VERIFIED, EXTERNALLY_VALIDATED, or NOT_CHECKED.

INDEPENDENTLY_VERIFIED (v2) means a blind verifier subagent confirmed it (claim + data + problem text only — never the solver's private reasoning); record the verifier label and brief hash (subagent-dispatch.md).

## Obligation patterns

- Numeric value: independent recomputation, residual/error bound, domain, and boundary check.
- Feasibility: all constraints and justified tolerance on original scale.
- Global optimum: convexity/KKT/duality, exact search, or certified bound; otherwise say local or best found.
- Uniqueness: proof or explicit non-uniqueness disclaimer.
- Prediction: untouched test/external validation, leakage-safe split, baseline, uncertainty, and calibration.
- Causal effect: estimand, identification, temporal order, confounding, and sensitivity.
- Robustness: parameter, data, seed, specification, and scenario perturbation.
- Theorem: readable or kernel-checked proof plus formalization-fidelity audit.
- Literature support: resolvable source, exact location, excerpt, retrieval date, and mapped claim.
- Reproducibility: data/code/config versions, lock, seed, tolerance, commands, and clean rerun.

Evidence strength may not be weaker than claim strength. Weaken unsupported claims; never weaken the verification rule.

## v0.5 status and artifact rules

Verification verdicts are PASS, FAIL, INCONCLUSIVE or NOT_RUN. Obligation statuses are OPEN, SATISFIED, BLOCKED, WAIVED or STALE. Claim verdicts are SUPPORTED, CONDITIONAL, INCONCLUSIVE, REFUTED or STALE. A verification PASS never directly sets a claim or run status.

Evidence is a first-class artifact with coveredClaimIds, coveredObligationIds, artifactPath, inputHashes, outputHashes, command, workdir, environment, exitCode, methodFamily, codeHash, level and limitations. Reusing the same deterministic result, solver summary, derived artifact, code path or reprint is not independent evidence.

When evidence or an upstream assumption changes, dependent claims, obligations and reports carry staleReason and staleSourceIds and must be reverified or explicitly downgraded.

## Failure insight contract

MODEL, ASSUMPTION, ANALYSIS, VALIDATION and EVIDENCE failures must preserve whatWasRuledOut, scientificInsight, affected claims/obligations, minimal reproduction, recovery route and evidence IDs. A failed direction is reusable scientific evidence only when its boundary and exclusion are explicit; private chain-of-thought is never stored.
