# Amendment 2: defer AWS runs; add a RunPod L40S platform

Date: 9 October 2026. Made before any GPU run or Evo 2 result.

## Change

1. P1 (AWS `p5.4xlarge`) and P4 (AWS `g6e.2xlarge`) are deferred, not dropped. The study owner
   has no AWS account for this work yet. Their launcher, configuration and costs stay in the
   repository and are labelled untested until they run under a later amendment.
2. The reference platform for agreement comparisons becomes P2 (Google Cloud `a3-highgpu-1g`,
   H100). If P2 is unavailable, P3 (RunPod H100) is the reference.
3. New platform P5: RunPod Secure Cloud, 1 x L40S 48 GB, on-demand. It replaces P4 as the test of
   the cheaper 48 GB GPU that NVIDIA lists for Evo 2 7B.

## Reason

No AWS credentials are available for the study account. Keeping an L40S platform preserves the
question about the cheaper GPU and the H100 against L40S agreement check reported as unexplained
in Arc issues 177 and 178.

## Effect

- Cross-provider H100 comparison: Google Cloud against RunPod (two providers instead of three).
- Cross-GPU comparison: L40S on RunPod against H100 on RunPod (same provider, same image, so the
  GPU is the main difference) and against H100 on Google Cloud.
- The article describes the AWS configuration from sources and labels it untested.
- Workloads, metrics, tolerances and the USD 150 cap are unchanged. Planned spend falls to about
  USD 20 for the original runs and the same for reproduction.

## Approval

Approved by Tim Richardson on 9 October 2026 (reply "continue" when asked to approve this amendment).
