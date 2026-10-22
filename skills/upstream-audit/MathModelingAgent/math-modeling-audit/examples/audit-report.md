# Audit Example

## Claim C-004

Claim: “The returned point is the global optimum.”

Evidence supplied: one successful SLSQP run.

Verdict: INCONCLUSIVE.

Reason: solver success supports a stationary/best-found point only. The artifact contains no convexity proof, certified bound, multi-start/global search, or optimality gap.

Required upgrade: weaken the claim to “best found local solution” or add an appropriate global-optimality certificate.
