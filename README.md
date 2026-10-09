# Running Evo 2 on Google Cloud, Runpod and AWS

A reproducible study and tutorial for clinical informaticians. One pinned Evo 2 7B container
image runs the same workloads on several clouds and GPUs, and records what each run cost, how
much GPU memory it needed, and whether the outputs agree across hardware.

**Status: in progress.** Runpod H100 and L40S runs are recorded. Google Cloud is pending GPU
quota. AWS is deferred (amendment 2) and its launcher is untested. The paper is not written yet.

- [Protocol](protocol.md) and [amendments](protocol/amendments/)
- [Literature and source review](literature/review.md)
- [Run log](evidence/run-log.md), including every failed attempt

## What runs

All workloads use public data only. No patient data is involved.

| ID | Workload | Checkpoint | Purpose |
|---|---|---|---|
| W0 | Arc's forward-pass test on 4 sequences | `evo2_7b` | Correctness gate: loss must be within 0.001 of 0.3477 |
| W1 | BRCA1 paired windows, 3,893 SNVs, 8,192 bp | `evo2_7b` | Variant scoring at realistic volume; compared with CADD, phyloP and a consequence rule |
| W2 | Exon classifier on 122 positions, layer `blocks.26` | `evo2_7b_base` | Embedding extraction into a small trained classifier |
| W3 | One forward pass at 8, 32, 131 and 262 kb | `evo2_7b` | Memory against sequence length; stops at the first out-of-memory error |
| W4 | First 200 BRCA1 variants again, in a new process | `evo2_7b` | Run-to-run repeatability on the same machine |

## Choosing hardware

Evo 2 7B runs in bfloat16 on one GPU. The 1B, 20B and 40B checkpoints need FP8 through
Transformer Engine on a Hopper GPU, and 40B needs two H100s or one H200
([Arc README](https://github.com/ArcInstitute/evo2/tree/53f195997257c56c00e5ef8d33a54f5baad143a6),
[NVIDIA NIM support matrix](https://docs.nvidia.com/nim/bionemo/evo2/latest/prerequisites.html)).

| Provider | Machine | GPU | How to buy | Launcher |
|---|---|---|---|---|
| Google Cloud | `a3-highgpu-1g` | 1 x H100 80 GB | Spot or Flex-start only | [`cloud/gcp/launch.sh`](cloud/gcp/launch.sh) |
| Runpod | Secure Cloud pod | 1 x H100 80 GB SXM | On-demand | [`cloud/runpod/launch.sh`](cloud/runpod/launch.sh) |
| Runpod | Secure Cloud pod | 1 x L40S 48 GB | On-demand | same |
| AWS (untested) | `p5.4xlarge` | 1 x H100 80 GB | On-demand | [`cloud/aws/launch.sh`](cloud/aws/launch.sh) |
| AWS (untested) | `g6e.2xlarge` | 1 x L40S 48 GB | On-demand | same |

Disk: allow at least 100 GB. The image is about 25 GB unpacked and the two 7B checkpoints are
13.8 GB and 13.0 GB. The launchers use 200 GB.

Context length is not memory fit. On an 80 GB H100, a single forward pass at 131 kb ran out of
memory (see W3 in the results). Long-window scoring needs multi-GPU frameworks such as BioNeMo.

## Before you start

1. Quota: a new cloud account usually has zero GPU quota.
   - Google Cloud: "Preemptible NVIDIA H100 GPUs" of at least 1 in your region.
   - AWS: "Running On-Demand P instances" of 16 vCPUs (`p5.4xlarge`) and "Running On-Demand G
     and VT instances" of 8 vCPUs (`g6e.2xlarge`).
   - Runpod: prepaid credit; no quota.
2. Credentials, kept outside the repository, for example in `~/.config/evo2ops/env` with mode 600:
   ```sh
   GCP_PROJECT=your-project
   RUNPOD_API_KEY=rpa_...
   AWS_PROFILE=your-profile
   ```
3. Local tools: `uv`, `jq`, `ssh`, and the `gcloud` and `aws` CLIs for those providers.

## Run it

```sh
make test                                   # offline: fetch inputs, check hashes, run tests
set -a; source ~/.config/evo2ops/env; set +a
uv run --frozen python scripts/experiment.py --config configs/full.json \
  --output results/full --platforms P3      # one platform; omit --platforms for all
```

Each launcher creates a machine with a one-off SSH key and a 3-hour limit, copies the committed
code and inputs, runs the pinned image, copies results back, and deletes the machine whatever
happens. Results land in `results/full/platforms/<ID>/attempt-<n>/`; `results/full/results.json`
and `operations.json` are rebuilt after every run.

## Controls that matter in a clinical setting

- **Pin everything.** The image is referenced by digest
  (`ghcr.io/rewire-bio/evo2-cloud-operations@sha256:22970720...`), the Hugging Face weights by
  revision, and the input files by SHA-256 ([`src/evo2ops/pins.py`](src/evo2ops/pins.py),
  [`data/manifest.json`](data/manifest.json)).
- **Check weight hashes before loading.** Arc's loader uses `torch.load` (pickle), which can run
  code. `fetch_verified` refuses a file whose hash does not match.
- **Avoid remote code.** Arc's exon notebook loads the classifier with `trust_remote_code`. This
  study rebuilds the two-layer network locally and loads only the pinned safetensors weights.
- **Run a correctness test on every new machine.** W0 reproduces Arc's expected loss; a wrong
  driver, GPU generation or FP8 setting shows up here first (see Arc issue 157 on Blackwell).
- **Keep patient data off hosted APIs.** NVIDIA's hosted Evo 2 API terms prohibit protected
  health information and production use. Self-hosting in a cloud account covered by a BAA (AWS
  EC2 and EBS, Google Compute Engine) is the route for identifiable data; a BAA alone does not
  make a deployment compliant.

## Repository layout

```
container/        Dockerfile and the image's recorded pip freeze
src/evo2ops/      code that runs on the GPU (W0 to W4)
cloud/            launchers for AWS, Google Cloud and Runpod
scripts/          input preparation, orchestration, price capture, result assembly
src/study/        statistics (AUROC, grouped bootstrap, agreement)
tests/            offline tests
```

## Licences

Study code: to be set at publication. Evo 2 code and weights: Apache-2.0 (Arc Institute). Input
data are fetched at run time from Arc's repository at a pinned commit and are not redistributed.
