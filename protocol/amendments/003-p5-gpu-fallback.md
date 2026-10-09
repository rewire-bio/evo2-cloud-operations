# Amendment 3: P5 accepts any 48 GB Ada-generation GPU

Date: 9 October 2026. Made after the P3 (Runpod H100) run, before any P5 output.

## Change

P5 (Runpod Secure Cloud, cheaper 48 GB GPU) now tries, in order: NVIDIA L40S, NVIDIA L40,
NVIDIA RTX 6000 Ada Generation. The GPU actually used is recorded and reported.

## Reason

Both P5 launch attempts at 10:21 UTC were refused for lack of L40S capacity, and Runpod's capacity
API then showed no Secure Cloud L40S on any host CUDA version. L40 and RTX 6000 Ada have the same
Ada Lovelace architecture (compute capability 8.9, FP8 support) and 48 GB of memory as the L40S.
NVIDIA's Evo 2 NIM support matrix lists both L40S and RTX 6000 Ada for the 7B model.

## Effect

The question P5 answers becomes "does a 48 GB Ada-generation GPU suffice, and do its scores
match the H100's?" rather than a question about the L40S specifically. Memory bandwidth and
clock speeds differ between these GPUs, so throughput is reported for the GPU used only.
Workloads, metrics, tolerances and the USD 150 cap are unchanged. The P3 results were seen
before this amendment; the change concerns only which GPU P5 may use.

## Approval

Approved by Tim Richardson on 9 October 2026 (chose "Allow L40 / RTX 6000 Ada" when asked).
