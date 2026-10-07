# Running Evo 2 on AWS, Google Cloud and RunPod

A reproducible study and tutorial for clinical informaticians. One pinned Evo 2 7B container runs
the same workloads on AWS EC2, Google Compute Engine and RunPod Secure Cloud, and records what
it costs, how much GPU memory it needs, and whether the outputs agree across providers.

**Status: in progress.** The protocol is approved; cloud runs have not happened yet. No timing,
cost or agreement result in this repository is final until this notice is removed.

- [Protocol](protocol.md) and [amendments](protocol/amendments/)
- Container: [`container/`](container/)
- Workloads (run on the GPU): [`src/evo2ops/`](src/evo2ops/)
- Launchers: [`cloud/aws`](cloud/aws/), [`cloud/gcp`](cloud/gcp/), [`cloud/runpod`](cloud/runpod/)
- Analysis: [`scripts/collect.py`](scripts/collect.py), [`src/study/`](src/study/)

## Offline checks (no cloud spend)

```sh
make test   # fetches the pinned public inputs, checks hashes, runs the unit tests
```

## What this is not

Evo 2 likelihood scores are not calibrated clinical interpretations. The BRCA1 and exon examples
reproduce Arc Institute's published notebooks with public data; no patient data is used.
