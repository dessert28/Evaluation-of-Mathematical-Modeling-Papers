# Run Directory Contract (v2)

The run directory is the ONLY place work artifacts live. It must stay clean at
every moment, not only at the end.
- After intake, calculations read only inputs/raw and inputs/manifest.json. External source paths are provenance only; source changes are diagnostic and do not alter the frozen snapshot.

## Layout

```text
math-modeling-runs/<task-id>/
├── run.json  ledger.json  events.jsonl        # run-state files (only run-state.mjs writes them)
├── problem-brief.md  inputs.json              # frozen restatement + input manifest
├── inputs/raw/  inputs/manifest.json           # immutable source snapshot + hashes
├── attempts/<n>/
│   ├── report.md                              # 13-section contract + 8-section digest
│   ├── code/                                  # final reproducible scripts ONLY (clean)
│   ├── data/                                  # results: json/csv/npy/xlsx
│   ├── plots/                                 # figures
│   └── _drafts/                               # this attempt's exploratory code (kept, isolated)
├── failed/
│   ├── directions/<id>/                       # direction-level failures: wall memo + code + why
│   ├── code-drafts/<attempt>-<name>/          # implementation-level failures: buggy/timed-out/deprecated
│   ├── failures.jsonl                          # structured failure records
│   └── issues.md                              # failure ledger index (see below)
├── research/                                  # literature (only when research happened)
├── walls/                                     # breakthrough memos (legacy path kept)
├── result.xlsx                                # the deliverable (when the problem asks for one)
├── reproducibility.json                       # final command list + env + hashes
└── final-report.md                            # terminal report
```

## Failure classification (failure ledger)

Every problem in ANY stage is recorded in failed/failures.jsonl and indexed in failed/issues.md with:

```text
#<seq> | 环节(DATA/TOOL/IMPLEMENTATION/MODEL/VALIDATION/EVIDENCE/RESEARCH_GAP) | 发现时间/attempt
症状：…
根因：…
处置：修了/绕过/放弃(→wall memo id)
影响：哪些 claim/obligation 被污染，下游如何重验
```

Direction-level failures additionally get `failed/directions/<id>/wall.md`
(target, paths tried, exact wall, wall type, breakthrough condition, restart
checklist) and their code snapshot. Implementation-level failures get
`failed/code-drafts/<attempt>-<name>/` with a README stating the failure.

## Cleanup gate (MUST run before ANY terminal transition)

1. attempts/<n>/code contains only the final reproducible scripts; each starts
   with a header comment: purpose, inputs, outputs, reproduction command.
   Exploratory/buggy versions move to `_drafts/` or `failed/code-drafts/` — never deleted.
2. No debug prints, unused variables, or hardcoded machine-specific paths
   (the data-root constant is the only allowed absolute path).
3. Figures in `plots/`, tables in `data/`; the deliverable at the run root.
4. reproducibility.json is complete and matches the final scripts.
5. `run-state.mjs validate <dir>` passes and every obligation has a terminal status.
6. The cleanup itself is noted in the terminal transition reason.

## Tidiness invariants

- Code is refactored as soon as it stabilizes within an attempt (not only at the end).
- Every script file maps 1:1 to an attempt artifact or a final deliverable.
- Nothing outside the run directory is written by the modeling work.
