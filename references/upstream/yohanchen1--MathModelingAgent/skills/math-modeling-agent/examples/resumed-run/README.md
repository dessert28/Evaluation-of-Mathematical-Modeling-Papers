# Resumed Run Example

A Standard optimization run reached VERIFY with candidate C-003 and evidence E-008 before interruption. `run.json` was corrupted after the journal append.

Resume sequence:

1. run `node scripts/run-state.mjs validate <run-root>`;
2. run `node scripts/run-state.mjs recover <run-root>`;
3. confirm C-003 remains the best candidate;
4. run `node scripts/run-state.mjs gate <run-root> --to REVISE --reason "回退到 D3-SP1：..."` (the reason must reference the decisionStack entry);
5. rerun only the incomplete verifier;
6. append a new evidence-linked transition (the CLI enforces the gate).

Previously hash-stable Python outputs are not recomputed. Interaction records,
the decision stack, and the failure ledger survive the crash unchanged.
