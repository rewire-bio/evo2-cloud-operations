# Classification flips between GPUs at a fixed threshold (amendment 6)

Analysis of stored scores only, 13 October 2026, as pre-registered in
[amendment 6](../protocol/amendments/006-classification-flips.md) ([issue #3](https://github.com/rewire-bio/evo2-cloud-operations/issues/3)).
Script: [`classification_flips.py`](classification_flips.py). Output:
[`evidence/classification-flips/results.json`](../evidence/classification-flips/results.json).

**Answer.** With a threshold fixed on the H100, 72 of 3,893 BRCA1 variants (1.8%) change call on
the L40S at the Youden threshold, and 152 to 189 (3.9% to 4.9%) at thresholds chosen for 90% or 95%
sensitivity. Flipped variants sit close to the threshold: half are within 0.7 of the median
cross-GPU difference (about 8e-5). In FP32, 0 of 487 subset variants change call at two of the three
thresholds and 1 of 487 at the third, against 8 to 22 of 487 in the default configuration.

## Thresholds

Set on the Google Cloud H100 scores (P2, recorded run); LOF if -delta >= t. Arc's BRCA1 notebook
reports only AUROC and defines no decision threshold, so there is none to test.

| Threshold | t (on -delta) | Sensitivity | Specificity |
|---|---:|---:|---:|
| Youden | 1.698e-3 | 0.793 | 0.782 |
| Sensitivity 0.90 | 9.97e-4 | 0.900 | 0.643 |
| Sensitivity 0.95 | 6.98e-4 | 0.950 | 0.539 |

## Controls

All 0 flips at every threshold: Google Cloud H100 against Runpod H100, and each platform's recorded
run against its reproduction. The reproduction's L40S therefore gives the same flips as the
recorded one.

## Full set: H100 to L40S, default configuration (3,893 variants)

Flips with exact 95% intervals.

| Threshold | All | LOF (823) | Not LOF (3,070) | Coding (2,768) | Noncoding (1,125) | LOF on H100 only / L40S only |
|---|---|---|---|---|---|---:|
| Youden | 72 (1.8%, 1.5 to 2.3) | 13 (1.6%, 0.8 to 2.7) | 59 (1.9%, 1.5 to 2.5) | 63 (2.3%, 1.8 to 2.9) | 9 (0.8%, 0.4 to 1.5) | 41 / 31 |
| Sensitivity 0.90 | 152 (3.9%, 3.3 to 4.6) | 18 (2.2%, 1.3 to 3.4) | 134 (4.4%, 3.7 to 5.2) | 125 (4.5%, 3.8 to 5.4) | 27 (2.4%, 1.6 to 3.5) | 73 / 79 |
| Sensitivity 0.95 | 189 (4.9%, 4.2 to 5.6) | 15 (1.8%, 1.0 to 3.0) | 174 (5.7%, 4.9 to 6.6) | 152 (5.5%, 4.7 to 6.4) | 37 (3.3%, 2.3 to 4.5) | 102 / 87 |

The flips run in both directions in similar numbers, so the L40S is not systematically more or
less likely to call LOF. Lower thresholds flip more variants because more variants lie near them.

## Distance to the threshold

The median absolute H100 to L40S difference is 1.17e-4. Measured in units of that difference:

| Threshold | Flipped: median distance | Flipped: max distance | H100 variants within 1 unit of t |
|---|---:|---:|---:|
| Youden | 0.68 | 5.4 | 150 |
| Sensitivity 0.90 | 0.67 | 5.4 | 235 |
| Sensitivity 0.95 | 0.66 | 3.9 | 334 |

About two thirds of flips (47 of 72 at Youden) come from variants within one unit of the threshold,
and about a third of those variants flip (47 of 150). The rest flip from further away, up to 5 units
(about 6e-4), because a few variants have much larger cross-GPU differences than the median.

## Follow-up subset (487 variants, 104 LOF)

Thresholds re-derived on the first-named configuration's own subset scores. Flips out of 487:

| Pair | Youden | Sensitivity 0.90 | Sensitivity 0.95 |
|---|---:|---:|---:|
| H100 vs L40S, default | 8 | 13 | 22 |
| H100 vs L40S, FP8 off | 3 | 14 | 11 |
| **H100 vs L40S, FP32** | **0** (0 to 0.8%) | **0** (0 to 0.8%) | **1** (0.0 to 1.1%) |
| L40 vs L40S, default | 8 | 14 | 25 |
| L40 vs L40S, FP8 off | 7 | 13 | 12 |
| H100 vs L40S, default, full-set thresholds | 8 | 18 | 24 |

The one FP32 flip sits 6.9e-7 from its threshold (1.4 FP32 median differences). Turning FP8 off
does not consistently reduce flips. Two Ada GPUs (L40, L40S) flip as many calls as an H100 and an
L40S. The subset thresholds rest on 104 LOF variants, so per-threshold counts are noisy; the
default and full-set-threshold rows agree with the full-set rates within their intervals.

## Implications

- At a fixed threshold, moving from an H100 to an L40S changes the call for about 2% to 5% of BRCA1
  SNVs, depending on where the threshold sits. These are borderline variants, but a binary call
  hides that.
- Validate a threshold on the GPU product it will run on, or compute in FP32 (0 to 1 flips in 487).
- Report a margin around the threshold: variants within about 1e-4 of t (here 150 to 334 of 3,893)
  can change call with hardware alone.

## For slide s5e-repro

> 72 of 3,893 variants (1.8%) change call at the Youden threshold (H100 to L40S); 0 of 487 with
> FP32 (8 of 487 in the default configuration).

| Threshold | Default, full set | Default, subset | FP32, subset |
|---|---:|---:|---:|
| Youden | 72 / 3,893 (1.8%) | 8 / 487 | 0 / 487 |
| 90% sensitivity | 152 / 3,893 (3.9%) | 13 / 487 | 0 / 487 |
| 95% sensitivity | 189 / 3,893 (4.9%) | 22 / 487 | 1 / 487 |
