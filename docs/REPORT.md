# swarm-vs-solo evaluation report (template)

Use this document when publishing results from `svs report`. Replace bracketed sections with your run metadata.

## Summary

| Field | Value |
| --- | --- |
| Date | [YYYY-MM-DD] |
| Task suite | [builtin / SWE-bench-Lite JSONL path] |
| Agents compared | [e.g. mock, claude, codex] |
| Modes | solo vs swarm (AutoSwarm `autoswarm run`) |
| Results file | [path to runs.jsonl] |

> If any row used the `mock` adapter, label the entire table **MOCK example data** and do not compare to live agents.

## Methodology

### Task isolation

Each task run copies the task `starter/` snapshot into a fresh Git repository and executes work inside a linked **git worktree**. Hidden pytest suites live outside the workspace until evaluation time, when they are copied to a temporary directory and executed with `PYTHONPATH` pointed at the agent workspace.

### Modes

- **solo** — the selected agent CLI adapter runs once against the task prompt.
- **swarm** — the same underlying CLI is invoked through **AutoSwarm** (`autoswarm run --agent <provider> --cwd <worktree>`), modeling host delegation to a child agent. The deterministic `mock` adapter simulates swarm overhead without API calls.

### Metrics

| Metric | Definition |
| --- | --- |
| Pass rate | Fraction of tasks where the agent completed and hidden pytest passed |
| Wall time | End-to-end seconds per task (worktree setup + agent + pytest) |
| Agent time | Adapter-reported or measured agent subprocess duration |
| Tokens / cost | Parsed from CLI JSON when available; otherwise adapter estimates |

### Reporting

`svs report` aggregates `runs.jsonl` by `(agent, mode)` and writes `report.md` plus PNG charts for pass rate, mean wall time, and mean cost.

## Results

[Paste `results/report/report.md` table here]

![Pass rate](report/pass_rate.png)

![Mean wall time](report/mean_wall_time.png)

![Mean cost](report/mean_cost.png)

## Threats to validity

1. **Suite scope** — Built-in tasks are small Python bug fixes; they do not represent large-repo maintenance (SWE-bench requires external repo checkout).
2. **Adapter fidelity** — CLI flags and token accounting differ per vendor; comparisons assume good-faith parsing of stream-json / AutoSwarm envelopes.
3. **Swarm definition** — AutoSwarm swarm mode in this harness is a single delegated child run, not a full multi-agent peer mesh with human host planning.
4. **Non-determinism** — Live LLM agents vary run-to-run; report confidence intervals or repeat runs when publishing.
5. **Cost model** — When usage metadata is missing, cost may be zero or estimated from generic token rates.
6. **Environment** — OS, model version, and API latency strongly affect wall time; pin versions in the table above.

## Reproduction

```bash
pip install -e ".[dev]"
svs run --tasks builtin --mode solo --agent mock --results results/runs.jsonl
svs run --tasks builtin --mode swarm --agent mock --results results/runs.jsonl
svs report --results results/runs.jsonl --output results/report
```

For live agents, install the corresponding CLI, authenticate, and swap `mock` for `claude`, `codex`, `grok`, or `cursor`. Swarm mode additionally requires the `autoswarm` CLI from [HKUDS/AutoSwarm](https://github.com/HKUDS/AutoSwarm).
