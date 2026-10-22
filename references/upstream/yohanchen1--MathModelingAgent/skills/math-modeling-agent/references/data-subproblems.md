# Inputs, Data, and Subproblems

## Input manifest

For each accessible artifact record stable ID, cryptographic hash, source, path, type, size, encoding, readability, and extraction provenance. For tables record sheets, rows, columns, inferred types, units, missingness, duplicates, ranges, anomalies, label source, time structure, group structure, and leakage risk.

Do not silently ignore unsupported files. Mark them unreadable and state the minimum representation needed.

## Leakage audit

Before model selection, identify target labels, future information, repeated entities, grouped observations, temporal ordering, and preprocessing fit scope. Fit imputation, scaling, feature selection, dimensionality reduction, and thresholds only inside training folds. Use time or group splits when ordinary random splits leak information.

## Subproblem DAG

Each subproblem records ID, exact task, required inputs, produced claims/artifacts, dependencies, acceptance criteria, and status. Downstream work references upstream IDs rather than copied prose.

When an upstream artifact changes, mark every dependent output stale. If an upstream node is blocked, downstream work must choose exactly one state: blocked, provisional with explicit condition, or alternative independent path.
