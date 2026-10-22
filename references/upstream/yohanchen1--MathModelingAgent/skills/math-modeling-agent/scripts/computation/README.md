# DSH computation tool extension

These entrypoints are adapted from the user-provided
`math-science-computation` toolkit. They are computation-support tools, not
mathematical engines: they discover callable external backends, persist a
local capability snapshot, and validate reproducible computation records.

## Entrypoints

- `probe_backends.py` / `probe_backends.ps1`: read-only discovery of
  Wolfram/Mathematica, primecount, SageMath, Python, and Python library
  availability. External probes are bounded and return structured failures.
- `backend_inventory.py` / `backend_inventory.ps1`: read or refresh a
  capability snapshot. Pass a run-local `--state-file`/`-StateFile`; do not
  use an implicit shared machine-wide path.
- `computation_record.py`: initialize or validate a reproducibility record
  for every probeable backend, including primecount.

The external backend remains responsible for the actual mathematical
calculation. A successful probe or record validation is not a proof.
