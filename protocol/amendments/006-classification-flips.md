# Amendment 6: classification flips between GPUs at a fixed threshold

Date: 13 October 2026. Written before any of the numbers below were computed. Analysis only, on
stored scores; no new GPU runs. The main study's results are unchanged. Raised in
[issue #3](https://github.com/rewire-bio/evo2-cloud-operations/issues/3) after the AMP audience
review asked how many BRCA1 variants would change call, not just rank, on a different GPU.

## Question

At a decision threshold fixed on H100 scores, how many variants change call (LOF or not LOF) when
the same threshold is applied to the L40S's scores? How many with FP8 off, with FP32, and between
two GPUs of the same architecture?

## Inputs

- Full set: the W1 scores (`delta`, 3,893 BRCA1 SNVs) from recorded run b75c67aa and reproduction
  30e7ae49, for P2 (Google Cloud H100), P3 (Runpod H100) and P5 (Runpod L40S), using the completed
  attempt named in each run's `operations.json`.
- Follow-up subset (amendment 5): 487 SNVs, 104 LOF; H100 (FH), L40S (FL) and L40 (FA) in the
  `default`, `fp8off` and, where run, `fp32` configurations, batch size 1.
- Labels and strata from `data/derived/brca1_variants.tsv`: `lof` (SGE function class LOF against
  FUNC and INT) and `region` (coding, noncoding).

## Thresholds

Score s = -delta, so higher means more likely LOF, as in the main analysis. A variant is called LOF
if s >= t. Candidate thresholds are the midpoints between adjacent distinct reference scores, so no
reference variant sits exactly on a threshold.

- **Youden:** the candidate maximising sensitivity + specificity - 1 on the reference; ties broken by
  the lowest threshold.
- **Fixed sensitivity 0.90 and 0.95:** the highest candidate whose sensitivity on the reference is at
  least the target.
- **Arc's notebook rule:** none. Arc's BRCA1 notebook at the pinned commit `53f1959` reports only
  AUROC (`roc_auc_score(y_true, -evo2_delta_score)`) and defines no decision threshold, so there is no
  such rule to test.

Thresholds are set on the reference scores only and applied unchanged to the other scores.

## Analysis (fixed now)

1. **Full set.** Reference P2 (recorded run). For each threshold, apply it to P5 and count variants
   whose call differs. Report the count overall and split by LOF and not LOF, and by coding and
   noncoding, with the direction (called LOF on H100 only, or on L40S only) and an exact
   (Clopper-Pearson) 95% interval on the proportion flipped in each stratum. Repeat with the
   reproduction's P5 against the same thresholds.
2. **Controls that must give 0 flips:** P2 against P3 (both H100), and each platform's recorded
   against reproduction scores. A nonzero control is reported and the full-set result is flagged.
3. **Follow-up subset.** Pairs: H100 against L40S in `default`, `fp8off` and `fp32`; L40 against L40S
   in `default` and `fp8off`. Thresholds are re-derived on the reference member's own subset scores
   (H100, or L40 for the L40 pairs), because changing precision shifts every score by about 1e-4,
   which would move a threshold set on default scores. Same counts and intervals as the full set.
   These thresholds rest on 104 LOF variants and will be less stable than the full-set ones.
   Secondary: the full-set P2 thresholds applied to the `default` H100 against L40S subset pair, to
   connect the subset to the full-set result.
4. **Distance to threshold.** For each flipped variant, |s_reference - t| divided by that pair's
   median absolute per-variant difference (computed from the pair, not fixed in advance). Report the
   median and maximum of this ratio for flipped variants, and the number of variants of the
   reference within one median difference of t.
5. Output: a short addendum and a table for talk slide s5e-repro in the form "N of 3,893 variants
   change call at threshold T (H100 to L40S); M with FP32". M comes from the subset and is reported
   as a count out of 487 with its interval, not scaled to 3,893.

## Approval

Approved by Tim Richardson on 13 October 2026 (issue #3, and approval of the implementation plan).
