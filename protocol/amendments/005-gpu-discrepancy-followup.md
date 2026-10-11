# Amendment 5: follow-up on the cross-GPU score discrepancy

Date: 11 October 2026. Written before any follow-up run. The main study's results are unchanged;
this is an additional, exploratory experiment.

## Questions

1. **FP8.** Does disabling the 7B checkpoint's FP8 input projections make H100 and L40S scores agree?
2. **FP32.** Does running the model in FP32 (TF32 disabled, PyTorch attention instead of
   flash-attention) make them agree, and at what cost in time and memory?
3. **Architecture or product.** Does a different GPU with the same Ada Lovelace architecture as the
   L40S (an L40, or an RTX 6000 Ada if no L40 is available) give the L40S's scores exactly?
4. **Batch size.** On one GPU, does scoring in batches of 8 change scores compared with batch size 1?

## Design

- Same image (`sha256:22970720...`), weights, inputs and window construction as the main study.
- Variant subset: every 8th BRCA1 SNV in table order (487 variants, with their reference windows).
- Platforms (Runpod Secure Cloud, on demand, one pod each):
  - H100 80 GB: `default` batch 1 (control), `fp8off` batch 1, `fp32` batch 1, `default` batch 8.
  - L40S 48 GB: `default` batch 1 (control), `fp8off` batch 1, `fp32` batch 1.
  - L40 48 GB, falling back to RTX 6000 Ada 48 GB: `default` batch 1, `fp8off` batch 1.
- Each configuration runs in a fresh process, records the settings actually applied (FP8 flag,
  parameter dtypes, attention implementation) and runs the W0 forward test.
- Workloads run detached on the pod and the launcher polls for completion, so a dropped SSH
  connection no longer stops a run. Pods are deleted when the launcher exits.

## Analysis (fixed now)

- **Controls:** `default` batch 1 on H100 and L40S must reproduce the recorded run's scores for
  the subset exactly. If not, the follow-up is reported as not comparable.
- For each pair of configurations: maximum and median absolute per-variant difference, Spearman
  correlation, and rank moves of more than 1% of the subset.
- **Q1 answered "FP8 is a cause"** if `fp8off` H100 against `fp8off` L40S agrees more closely than
  `default` against `default` (lower median absolute difference). "The main cause" if their median
  absolute difference falls below 10% of the default-pair value.
- **Q2** reported the same way, plus time per window and peak memory. If FP32 fails to run, that is
  reported as the result.
- **Q3:** report whether L40 (or RTX 6000 Ada) `default` equals L40S `default` exactly.
- **Q4:** report the H100 batch 8 against batch 1 difference.
- AUROC on the subset is reported for each configuration for context only; the subset is too
  small for precise discrimination estimates.

## Budget

USD 15 cap for this follow-up (expected about USD 6), within the study's remaining budget.
Every pod has a 3-hour limit enforced by the launcher; failed configurations are not retried more
than once.

## Approval

Approved by Tim Richardson on 11 October 2026 (reply: "Great do the follow up please"), after the
follow-ups A to D were proposed with costs.
