# Evo 2 operations: literature and source review

Retrieved 7 October 2026. Source identifiers refer to `literature/sources.json`. This review
covers how Evo 2 is deployed and run, not its biology in depth. Claims are limited to what each
source states.

## 1. The model

Evo 2 is a DNA language model from Arc Institute, published in Nature in 2026 after a February
2025 preprint [brixi2026]. It has 7B and 40B parameter versions (and later 1B and 20B
checkpoints), trained on the OpenGenome2 corpus, with a StripedHyena 2 architecture that mixes
convolution and attention and extends to a 1 Mb context at single-nucleotide resolution.
Code, weights (Apache-2.0) and data are open [brixi2026, arc-repo, hf-evo2-7b].

Arc's repository lists eight checkpoints. The 7B models (`evo2_7b`, `evo2_7b_262k`,
`evo2_7b_base`) can run in bfloat16 without Transformer Engine; the 1B, 20B and 40B models need
FP8 through Transformer Engine on a Hopper GPU for numerical accuracy, and 40B needs several
H100s [arc-repo]. Each checkpoint has a different context length (8 kb base, 262 kb, 1 Mb), and
Arc's two clinical-adjacent notebooks use different ones: BRCA1 scoring uses `evo2_1b_base` as a
quick demonstration and recommends 7B or 40B; exon classification uses `evo2_7b_base` embeddings
from layer `blocks.26` [arc-repo]. Recipes are therefore not interchangeable across checkpoints.

## 2. Deployment routes

| Route | What it is | Data leaves your account? | Notes |
|---|---|---|---|
| Self-hosted Vortex (`pip install evo2`) | Arc's inference code on your own GPU | No | Used in this study. Designed for generation with KV caching; long-sequence scoring is limited [arc-issue-146] |
| Self-hosted NVIDIA NIM | NVIDIA container with an HTTP API | No | Supported GPUs listed per model [nim-prereq]; container under NVIDIA software licence terms [ngc-nim] |
| AWS Marketplace / SageMaker NIM | NIM as a SageMaker model | No (runs in your account) | Recommends `ml.g6e.xlarge` (L40S) for real-time 7B; USD 1.00 per host-hour software fee plus infrastructure [aws-marketplace-nim] |
| NVIDIA hosted API (build.nvidia.com) | Remote API for 40B | Yes | Trial terms forbid production use and protected health information [nvidia-api-trial] |
| BioNeMo Framework / Savanna | Training and fine-tuning stacks with tensor and context parallelism | No | Arc's suggested route for long-sequence embeddings across several GPUs [bionemo-evo2, arc-issue-160] |
| Community GCP Batch wrapper | Third-party scripts for Cloud Batch on `a3-highgpu-1g` | No | Infrastructure reference only; project and registry defaults must be replaced [evo2-gcp] |

For clinical work the hosted API is excluded by its own terms: section 2.6 prohibits submitting
"protected health information, personal data (unless expressly permitted by an API Service)"
and section 1.2 limits use to trial purposes "without use ... in production" [nvidia-api-trial].

## 3. Hardware: what fits

- **7B on one GPU.** NVIDIA's NIM matrix lists H100 80 GB, H200, RTX 6000 Ada and L40S as
  single-GPU options for 7B, with 48 to 80 GB of GPU memory, 16 GB of CPU RAM and 50 GB of disk;
  40B needs two H100s or one H200 and 110 GB of disk [nim-prereq]. A user reports running the
  7B forward test on an RTX 4090 using about 22 GB [arc-issue-101].
- **Context capacity is not memory fit.** The 7B checkpoint accepts 1 Mb, but users report
  out-of-memory errors at about 50 kb on a 48 GB L40S [arc-issue-160] and on 80 GB GPUs for long
  scoring [arc-issue-146]; 40B on two H100s fails beyond about 80 kb [arc-issue-167]. Arc's
  maintainers point to BioNeMo or Savanna, or slower forced prompting in Vortex [arc-issue-146,
  arc-issue-160].
- **A100.** No FP8. 7B runs with FP8 projections disabled; for 1B and 40B this causes "major
  numerical discrepancies" according to a maintainer [arc-issue-173]. A packaging bug that
  required Transformer Engine for 7B was fixed in March 2026 [arc-issue-208].
- **Blackwell.** A user reports wrong losses for `evo2_1b_base` on an RTX 5070 Ti; maintainers had
  not tested Blackwell at the time [arc-issue-157].

## 4. Numerical agreement and correctness checks

Arc's README says to "always validate model outputs after configuration changes or on different
hardware by using the tests", and its forward-pass test states expected losses per checkpoint
(0.3477 for `evo2_7b`) [arc-repo]. Two open issues report that the same sequences give different
7B embeddings on H100 and L40S, without a published explanation [arc-issue-177, arc-issue-178].
Another reports that chunked "stateful" forward passes over long sequences do not reproduce
single-pass embeddings [arc-issue-196]. A container conversion to Singularity failed to find
`libcuda.so` until a symlink was added [arc-issue-195]. No source quantifies cross-provider or
cross-GPU agreement of variant scores; this study measures it.

## 5. Scale

The largest documented Evo 2 workload found is EVEE (preprint, April 2026): embeddings from
layer 27 of Evo 2 for 4,252,870 variants with 65 kb windows used about 20,000 H100-hours and
produced about 34 TB of bf16 embeddings [evee2026]. That is roughly 17 H100-seconds per variant
at that window size. Window length, layer choice and storage dominate the cost of such pipelines.

## 6. Clinical performance evidence (context only)

The Evo 2 paper reports strong zero-shot results on noncoding and splice variants and a state of
the art for BRCA1 noncoding SNVs, while ranking fourth and fifth on coding SNVs behind
AlphaMissense, ESM-1b and GPN-MSA [brixi2026]. A supervised classifier on 40B embeddings reached
AUROC 0.95 on all BRCA1 SNVs [brixi2026]. EVEE reports that probes trained on Evo 2 embeddings
exceed Evo 2 loss-based scoring (AUROC 0.932) on a deconfounded ClinVar benchmark, matching
AlphaMissense (0.972) on missense variants [evee2026]. These are retrospective benchmarks. None
of the sources reviewed shows prospective clinical validation, calibration, or ancestry-stratified
performance of Evo 2 in a diagnostic workflow.

## 7. Data governance

AWS lists EC2 and EBS as HIPAA-eligible services and requires a BAA before processing PHI
[aws-hipaa]. Google Cloud's BAA covers Compute Engine, under shared responsibility [gcp-hipaa].
RunPod states ISO 27001 certification, SOC 2 Type II and HIPAA/GDPR programmes [runpod-compliance],
and says BAAs "can be executed for HIPAA-covered entities" [runpod-baa]; the commercial terms for
a BAA were not available from a public primary source.
Modal offers a BAA only on Enterprise plans [modal-pricing]. A BAA does not make a deployment
compliant; access control, logging, encryption and region choice remain the customer's job.

Arc's checkpoints are PyTorch pickles loaded with `torch.load`, which can execute code when
loaded. Pinning the Hugging Face revision and checking the file hash before loading is a basic
control. The exon classifier on Hugging Face is loaded with `trust_remote_code` in Arc's notebook
[arc-repo, hf-exon-classifier].

## 8. Operational outlook

- **7B is a single-GPU workload; 40B is not.** For scoring short windows (8 kb), a 48 GB GPU is
  listed as supported [nim-prereq]; whether it is cheaper per variant than an H100 depends on
  throughput, which this study measures.
- **Long context is the operational bottleneck.** Long-window scoring and embeddings need
  multi-GPU frameworks (BioNeMo, Savanna) rather than the Vortex inference path, and these are
  harder to install and reproduce [arc-issue-146, arc-issue-160, arc-issue-167].
- **Hardware drift is a validation problem.** FP8 behaviour differs by GPU generation, and users
  report cross-GPU embedding differences. Any clinical pipeline needs a per-hardware acceptance
  test, at minimum Arc's forward-pass check, plus agreement checks on its own outputs.
- **Packaged routes are converging on NIM.** NVIDIA ships Evo 2 as a NIM container (v2.2.0,
  September 2026) [ngc-nim] and through SageMaker [aws-marketplace-nim]. That reduces install
  effort but adds a vendor licence and a less inspectable runtime.
- **Embedding pipelines outperform raw likelihoods but cost more.** EVEE's probe results
  [evee2026] come with tens of thousands of GPU-hours and terabytes of storage.
