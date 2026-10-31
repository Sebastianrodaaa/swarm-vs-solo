# swarm-vs-solo evaluation report (template)

Use this document when publishing results from `svs report`. Replace bracketed sections with your run metadata.

## Summary

| Field | Value |
| --- | --- |
| Date | [YYYY-MM-DD] |
| Task suite | [builtin / SWE-bench-Lite JSONL path] |
| Agents compared | [e.g. mock, claude, codex] |
| Modes | solo vs swarm (AutoSwarm `autoswarm run`) |
| Harness arms | [fixed / coevolve] |
| Results file | [path to runs.jsonl] |
| Harness run dir | [path to coevolve revisions, if applicable] |

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

`svs report` aggregates `runs.jsonl` by `(agent, mode, harness)` and writes `report.md` plus PNG charts for pass rate, mean wall time, and mean cost. When the co-evolve arm is present, additional charts cover pass rate by batch, harness revision counts, and held-out eval cost/time.

## Harness experiment (fixed vs co-evolve)

Recent work argues that **policy and harness should be co-trained or co-evolved** rather than treating prompts, tools, and rubrics as frozen scaffolding ([CoHARL](https://arxiv.org/abs/2610.36469v1), [co-evolving rubrics and harnesses](https://arxiv.org/abs/2610.36826v1), [*Your Policy Is Secretly a Harness*](https://huggingface.co/papers/2610.37255)). `svs` adds a second axis alongside solo vs swarm:

| Arm | CLI | Behavior |
| --- | --- | --- |
| **fixed** | `--harness fixed` (default) | Static system prompt, tool list, and grading rubric for every task. |
| **coevolve** | `--harness coevolve` | Tasks are split into **train** (~70%) and **held-out eval** (~30%) via a deterministic hash of `task_id`. Train tasks run in batches (`--batch-size`, default 2). After each train batch, a **harness updater** rewrites prompt, tools, and rubric using **train failures only**, then saves `run_dir/harness/rev_NNN.json` so every revision is diffable. Eval tasks run once at the end under the final harness; they never feed the updater. |

### Leakage controls

1. **Split discipline** — Updater input is restricted to failed records with `split=train`. Eval task ids and eval failures are excluded from update logic.
2. **Reporting** — Harness comparison tables and `harness_eval_cost_time.png` use the **held-out eval split** when co-evolve rows exist, so headline pass rates are not train-contaminated.
3. **Artifacts** — Versioned harness JSON under `--run-dir` documents exactly what changed between batches (prompt diff, tools added, rubric edits, policy flags).

### Mock adapter (CI)

The deterministic `mock` adapter simulates co-evolution without vendor APIs: early revisions withhold golden fixes until train-batch updates authorize repairs and generalize `src/` edits. This exercises batching, revision persistence, eval scoring, and reporting in CI.

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
7. **Harness updater fidelity** — The bundled updater is deterministic and lightweight (not an LLM). Live co-evolve experiments should replace it with your training loop while keeping the same JSON schema and leakage guards.
8. **Held-out size** — Small suites yield few eval tasks; pass rates on eval have high variance. Prefer full suites or repeated runs for publication.

## Reproduction

```bash
pip install -e ".[dev]"
svs run --tasks builtin --mode solo --agent mock --harness fixed --results results/runs.jsonl
svs run --tasks builtin --mode solo --agent mock --harness coevolve --batch-size 2 --run-dir results/coevolve-run --results results/runs.jsonl
svs run --tasks builtin --mode swarm --agent mock --results results/runs.jsonl
svs report --results results/runs.jsonl --output results/report
```

For live agents, install the corresponding CLI, authenticate, and swap `mock` for `claude`, `codex`, `grok`, or `cursor`. Swarm mode additionally requires the `autoswarm` CLI from [HKUDS/AutoSwarm](https://github.com/HKUDS/AutoSwarm).
