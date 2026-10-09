# Running Evo 2 on AWS, Google Cloud and a GPU cloud

Status: approved by Tim Richardson on 7 October 2026; amendment 1 approved on 9 October 2026

## Research question

Can one pinned Evo 2 7B workload (sequence scoring, paired variant windows and embedding
extraction) be run reproducibly on single-GPU instances on AWS, Google Cloud and a GPU cloud?
Do the outputs agree across providers, and what are the measured GPU memory, wall time and cost?

## Purpose and contribution

Clinical informaticians evaluating Evo 2 need an executable recipe more than another benchmark.
Arc's repository documents installation and notebooks. It does not document provisioning, cost,
cross-hardware agreement or teardown on commercial clouds. This study provides:

1. One container image, pinned by digest, run unchanged on every platform.
2. Launch and teardown scripts for AWS EC2, Google Compute Engine and RunPod.
3. Measured receipts: instance type, region, driver, GPU, peak GPU memory, wall time and cost.
4. Agreement of numerical outputs across providers and GPU types.
5. Reproduction of two published Arc workflows (BRCA1 zero-shot scoring and exon classification)
   with the 7B checkpoints, against labels and simple baselines.

No new biological claim is made. Variant scores are not a calibrated clinical interpretation.

## Platforms

| ID | Provider | Instance | GPU | Purchase option |
|---|---|---|---|---|
| P1 | AWS EC2 | `p5.4xlarge` | 1 x H100 80 GB | On-demand |
| P2 | Google Compute Engine | `a3-highgpu-1g` | 1 x H100 80 GB | Spot (this shape is only offered as Spot or Flex-start) |
| P3 | RunPod Secure Cloud | GPU pod | 1 x H100 80 GB (SXM preferred; type recorded) | On-demand |
| P4 | AWS EC2 | `g6e.2xlarge` | 1 x L40S 48 GB | On-demand |

P1 is the reference platform for agreement comparisons. P4 tests the cheaper 48 GB GPU that
NVIDIA's Evo 2 NIM support matrix lists for the 7B model.

**Choice of GPU cloud.** RunPod Secure Cloud was chosen over Modal and Lambda because it runs an
arbitrary container image (so the same image digest runs everywhere), bills per second, and
publishes an ISO 27001 certificate, SOC 2 Type II report and HIPAA/GDPR programme. It says a BAA
can be executed; its commercial terms were not confirmed from a public source (amendment 1). Modal offers a BAA only on Enterprise plans and needs its
own Python SDK, which would change the code path. Lambda's compliance terms could not be confirmed
from a primary source. These terms are documented, not tested.

Regions are chosen by quota and capacity at run time and recorded. If a platform cannot obtain
capacity within the attempt limit, it is reported as unavailable, not silently substituted.

## Software and model pins

- Container: built from `nvcr.io/nvidia/pytorch:25.04-py3` (the base of Arc's Dockerfile),
  pinned by digest, with `evo2==0.6.0` and `vtx==1.1.0`; published to
  `ghcr.io/rewire-bio/evo2-cloud-operations` and referenced by digest. Package versions inside the
  image, including whether Transformer Engine is present, are recorded.
- Arc code reference: `ArcInstitute/evo2` commit `53f1959` (notebooks and test data).
- Weights (Hugging Face, Apache-2.0), downloaded at pinned revisions and SHA-256 checked before load:
  - `arcinstitute/evo2_7b` revision `bda0089f`, `evo2_7b.pt`, SHA-256 `c66645929dc1b9c6...`
  - `arcinstitute/evo2_7b_base` revision `074097e9`, `evo2_7b_base.pt`, SHA-256 `d8a0e775a5d84992...`
  - `schmojo/evo2-exon-classifier` revision `3ce7ccd4`, `model.safetensors`, SHA-256 `0394fdbf4f533a28...`
- Arc's checkpoint loader uses `torch.load` with pickle, which can execute code. Hash checks are
  mandatory before load. The exon classifier needs `trust_remote_code`; its two Python files are
  pinned by revision and were reviewed (a small multilayer perceptron).

## Data

All inputs are public; no patient data are used. Files come from the pinned Arc commit and are
SHA-256 checked (`data/manifest.json`). They are fetched at run time, not redistributed.

- `GRCh37.p13_chr17.fna.gz`: chromosome 17, GRCh37.
- `41586_2018_461_MOESM3_ESM.xlsx`: Findlay et al. 2018 BRCA1 saturation genome editing table:
  3,893 SNVs with functional class (FUNC 2,821, INT 249, LOF 823), consequence, CADD score and
  mammalian phyloP.
- `samplePositions.tsv`: 122 labelled exon/non-exon positions from Arc's exon-classifier notebook.
- `prompts.csv`: Arc's four forward-pass test sequences.
- Synthetic DNA for memory probes, generated from seed 20261007.

## Workloads

- **W0 correctness gate.** Arc's forward-pass test with `evo2_7b`. Pass if mean loss is within
  1e-3 of Arc's expected 0.3476563. A platform that fails W0 does not run W1 to W4; the failure
  is reported.
- **W1 BRCA1 paired variant windows.** `evo2_7b`, 8,192 bp windows centred on each SNV, as in
  Arc's notebook. Score = variant mean log-likelihood minus reference mean log-likelihood
  (`score_sequences`, batch size 1, `reduce_method='mean'`). Labels: `LOF` against `FUNC`+`INT`.
  Metric: AUROC of the negated score, overall and for coding (missense, nonsense, synonymous)
  and noncoding (all other consequences) subsets.
  Baselines from the same table, needing no GPU: CADD score, mammalian phyloP (higher = more
  conserved = predicted LOF; amendment 1), and a
  consequence rule (nonsense and canonical splice > splice region > missense > other).
- **W2 embeddings and exon classifier.** `evo2_7b_base`, final-token embedding from layer
  `blocks.26` for forward and reverse sequences, concatenated, scored by the pinned classifier.
  Metric: AUROC on the 122 positions. The classifier's training data may include these
  positions, so this is a pipeline demonstration, not an evaluation.
- **W3 memory and time probe.** `evo2_7b` single forward pass on synthetic sequences of 8,192,
  32,768, 131,072 and 262,144 bp. Record peak GPU memory and time. Stop at the first
  out-of-memory error and report it as a result.
- **W4 same-platform repeat.** On each platform, rescore the first 200 BRCA1 variants in a
  second process, to separate run-to-run variation from cross-hardware variation.

## Metrics and uncertainty

- AUROC with 95% intervals from 2,000 bootstrap resamples (seed 7). For W1, resample positions,
  keeping the three SNVs at a position together. Evo 2 against each baseline: paired bootstrap
  difference in AUROC with its interval. No significance thresholds; intervals are reported.
- Cross-platform agreement for each platform against P1: maximum and median absolute difference
  in per-variant scores, Spearman correlation, and the number of W1 variants whose rank moves by
  more than 1% of the list. W2: maximum absolute difference in classifier probabilities.
  W4 gives the same statistics within a platform.
- Operations: container pull time, weight download and verification time, model load time,
  workload wall time, sequences per second, peak GPU memory (`torch.cuda.max_memory_allocated`
  and sampled `nvidia-smi`), and end-to-end billed instance time.
- Cost: billed instance seconds times the provider's list price retrieved by API at run time,
  plus storage. Reconciled against billing records where available.

## Analysis plan and stopping conditions

Each platform runs once, from a clean committed study revision, using the same image digest.
Outputs, receipts and logs are copied back and committed as evidence. Analysis code builds all
tables, figures and paper values from those files. Failed attempts are kept.

Stop a platform after two failed attempts. Stop the study if spend reaches the cap.

## Reproduction and tolerances

`results.json` holds only scientific outputs: W0 loss and accuracy, W1 and W2 AUROCs, baseline
AUROCs, and agreement statistics. Timings and costs go in `operations.json` and are not compared.

Reproduction reruns every platform from a clean checkout with the same image digest and
configuration. Tolerance, fixed now: absolute 0.01, relative 0. Different GPU models may differ
in bf16 arithmetic; agreement statistics are measured, not assumed.

## Budgets

- Cloud spend hard cap: USD 150 for the whole study, including the image build, original runs,
  reproduction and failed attempts. Planned: about USD 45 for the original runs and about the
  same for reproduction.
- Every instance self-terminates after 3 hours (EC2 shutdown behaviour `terminate` plus an OS
  timer; GCE `--max-run-duration` with delete; RunPod pod self-removal plus a local watchdog).
- At most 2 attempts per platform per phase; at most 30 worker calls; under 2 GB of retained
  evidence in the repository. No weights, embeddings or raw sequences are committed.

## Limitations

- One checkpoint size (7B). The 40B model needs two H100s or one H200 and is described from
  sources only.
- BRCA1 and exon tasks reproduce published notebook workflows on one gene and 122 positions.
  They say nothing about clinical validity, calibration or ancestry.
- One run per platform: timings are receipts, not a performance benchmark.
- List prices change; costs are dated.
- Compliance terms are documented from provider pages, not audited.

## Approval and amendments

The owner must explicitly approve this protocol and budget before any paid run. Design changes
are recorded in `protocol/amendments/` and need renewed approval.
