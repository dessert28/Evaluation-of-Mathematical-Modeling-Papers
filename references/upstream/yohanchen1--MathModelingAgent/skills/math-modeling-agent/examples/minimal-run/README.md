# Minimal Run Example (v2)

Problem: solve 2x + 3 = 11.

Mode: Fast.

Claim C-001: x = 4.

Evidence E-001: algebraic derivation.
Evidence E-002: substitution 2(4) + 3 = 11.

Status: SOLVED.

v2 interaction records (ledger.scope.interactions): D0 restatement (auto), D1 routing
(algebra / Fast), D2 assumptions (none beyond the equation), D3 direction
(direct inverse), D4 verdict (user accepted). scope.robustnessExempt = true —
a pure algebraic equation has no perturbable parameters, so the robustness
gate is exempted with that reason. decisionStack holds the D3 entry.

No Python, Lean, Wolfram, research directory, or empty artifact directory is required.
