# swarm-vs-solo report

> **MOCK example data** — generated from the deterministic `mock` adapter in CI.
> Do not treat these numbers as real agent performance.

| Agent | Mode | Harness | Runs | Pass rate | Mean wall (s) | Mean cost ($) | Total cost ($) |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| mock | solo | coevolve | 6 | 66.7% | 1.499 | 0.008204 | 0.049227 |
| mock | solo | fixed | 10 | 100.0% | 2.062 | 0.010329 | 0.103293 |
| mock | swarm | fixed | 4 | 100.0% | 0.252 | 0.017335 | 0.069339 |

## Harness experiment (held-out eval)

> **MOCK** — co-evolve arm uses deterministic train-batch updates only.

| Agent | Mode | Harness | Eval runs | Pass rate | Mean wall (s) | Mean cost ($) |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| mock | solo | coevolve | 1 | 100.0% | 0.203 | 0.011622 |
| mock | solo | fixed | 2 | 100.0% | 0.180 | 0.010302 |
| mock | swarm | fixed | 1 | 100.0% | 0.248 | 0.017226 |

### Harness revisions observed

- `coevolve`: **2** revision(s) in results
- `fixed`: **1** revision(s) in results

### Pass rate by batch (train batches + eval batch index −1)

| Harness | Batch | Runs | Pass rate |
| --- | ---: | ---: | ---: |
| coevolve | eval | 1 | 100.0% |
| coevolve | 0 | 2 | 0.0% |
| coevolve | 1 | 2 | 100.0% |
| coevolve | 2 | 1 | 100.0% |
| fixed | 0 | 14 | 100.0% |
