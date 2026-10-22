# Original GitHub workflow parity

The DSH bundle is a faithful workflow migration of the original
MathModelingAgent project, not a replacement of its useful behavior.

| Original GitHub behavior | DSH realization |
|---|---|
| PDF/problem extraction in `code/agent.py` | intake D0 and the subproblem DAG |
| Excel attachment profiling in `code/data_analyzer.py` | INPUT_PROFILED and the run input manifest |
| sequential subproblem solving | dependency-ordered SPi loop |
| Modeler → Analyzer → Correction loop in `code/prompts.py` | explorer/modeler → verifier/analyzer → corrector/revise |
| per-round thinking and run logs | attempts/<n>/report.md, events.jsonl, and chat runlog digest |
| acceptance/rejection and stagnation control | D4 verdict, progress test, REVISE/FORK, and resumable non-SOLVED states |
| hash-based cache and resume | run-local artifacts, evidence links, and state recovery |

The migration deliberately replaces private chain-of-thought storage with
human-readable reasoning, evidence, and reproducible artifacts. The roles and
loop semantics remain; only the execution substrate changes from the legacy
Python CLI to DSH skills and state files.
