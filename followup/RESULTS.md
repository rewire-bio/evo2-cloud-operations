# Follow-up results: why GPUs disagree, and what fixes it (amendment 5)

Run on 11 October 2026 on Runpod Secure Cloud: one H100 80 GB, one L40S 48 GB and one L40 48 GB
pod, same image and inputs as the main study. Subset: every 8th BRCA1 SNV (487 variants, 104 loss
of function). Raw outputs: [`evidence/followup-20261011/`](../evidence/followup-20261011/).
Cost: USD 4.98 (Runpod billing).

## Controls

The default configuration on the H100 and on the L40S reproduced the recorded run's scores for the
subset exactly (maximum absolute difference 0). Every configuration passed the W0 forward test.

## Agreement between GPUs

| Comparison | Median abs. difference | Max abs. difference | Spearman | Rank moves > 1% |
|---|---:|---:|---:|---:|
| H100 vs L40S, default (FP8 input projections) | 1.19e-4 | 5.81e-4 | 0.983 | 327 |
| H100 vs L40S, FP8 off (bfloat16) | 8.35e-5 | 3.52e-4 | 0.990 | 295 |
| **H100 vs L40S, FP32** | **4.77e-7** | **2.92e-6** | **1.000** | **0** |
| L40 vs L40S, default (same Ada architecture) | 1.13e-4 | 6.96e-4 | 0.980 | 320 |
| L40 vs L40S, FP8 off | 7.59e-5 | 4.15e-4 | 0.990 | 298 |
| H100 batch 8 vs batch 1, default | 0 | 0 | 1.000 | 0 |

Within one GPU, changing precision moved scores by as much as changing GPU did: FP8 off against
default had a median difference of 1.43e-4 (H100) and 1.37e-4 (L40S); FP32 against default 1.19e-4
(H100) and 1.16e-4 (L40S).

## Answers to the pre-registered questions

1. **FP8: a cause, not the main cause.** Turning FP8 input projections off reduced the median
   H100 against L40S difference to 0.70 of the default value (threshold for "main cause": below 0.1).
2. **FP32 removes the discrepancy.** In FP32 (TF32 disabled, PyTorch attention instead of
   flash-attention) the two GPUs agreed to a median of 4.8e-7, 250 times closer than the default, with
   identical rankings. The remaining difference is three orders of magnitude below the score
   differences between variants.
3. **Same architecture is not enough.** An L40 and an L40S, both Ada Lovelace (compute capability
   8.9), disagreed as much as an H100 and an L40S. The likely reason is that the GPU libraries pick
   kernels and reduction orders per device (the two GPUs have different numbers of
   multiprocessors), not per architecture. Validation therefore has to be per GPU product.
4. **Batch size does not matter** for equal-length windows: batch 8 was bit-identical to batch 1.

## Cost of FP32

| GPU | Default windows/s | FP32 windows/s | Slowdown | FP32 peak memory |
|---|---:|---:|---:|---:|
| H100 | 2.92 | 0.50 | 5.8x | 29.6 GiB |
| L40S | 0.92 | 0.27 | 3.4x | 29.6 GiB |

FP32 fits on a 48 GB GPU for 8 kb windows. At the October 2026 list prices used in the study, it
would raise the cost of scoring from about USD 0.52 to about USD 3 per 1,000 variants on the
Runpod H100, and from about USD 0.45 to 0.68 to about USD 1.5 on an L40S, depending on host speed.

## What the precision change does to accuracy

Subset AUROC (104 LOF of 487) was 0.889 to 0.893 in every configuration; the subset is too small to
separate them. FP32 and bfloat16 scores differ from the default by about 1e-4 per variant, so the
default scores carry rounding error of that size whichever GPU computes them.

## Implications

- For scores that must be identical, or nearly so, across hardware, compute in FP32. It costs 3 to 6
  times more GPU time.
- If FP32 is too expensive, fix the GPU product (not just the generation) and validate on it.
- Batching equal-length windows is safe.
- A FP32 run is a useful reference: it shows how much of a default score is rounding error.

## Operational note

The follow-up launcher ran the workloads detached and polled for completion, so dropped SSH
connections could not stop them. In this run the SSH call that started the job did not return
until the job finished; the workloads were unaffected. The launcher now uses `setsid` to detach
fully.
