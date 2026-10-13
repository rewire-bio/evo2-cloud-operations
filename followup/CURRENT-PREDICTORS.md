# Current CADD, SpliceAI and REVEL on the BRCA1 variants (amendment 7)

Analysis of published precomputed scores, 13 October 2026, as pre-registered in
[amendment 7](../protocol/amendments/007-current-predictors.md) ([issue #4](https://github.com/rewire-bio/evo2-cloud-operations/issues/4)).
Script: [`current_predictors.py`](current_predictors.py). Outputs:
[`results.json`](../evidence/current-predictors/results.json) and
[`sources.json`](../evidence/current-predictors/sources.json) (URLs and checksums). Per-variant values
from the third-party tables are not committed.

**Answer.** Evo 2 7B's noncoding advantage was an advantage over CADD v1.3 only. Against current CADD
(v1.7) and SpliceAI, no difference was detected on noncoding variants: Evo 2 0.953, CADD v1.7 0.932,
SpliceAI 0.963. On coding variants CADD v1.7 is better than Evo 2 (0.892 against 0.840), and on
missense variants REVEL (0.867) and CADD v1.7 (0.828) are both better than Evo 2 (0.785). Overall,
Evo 2 and CADD v1.7 are level (0.875 and 0.881).

## Sources

| Predictor | Table | Score used |
|---|---|---|
| CADD v1.7 | `whole_genome_SNVs.tsv.gz`, GRCh37, kircherlab.bihealth.org | RawScore (PHRED gives the same AUROCs to 0.001) |
| SpliceAI | Illumina's masked precomputed scores, as annotated in CADD v1.7 `whole_genome_SNVs_inclAnno.tsv.gz` | Maximum of the four delta scores, BRCA1 rows |
| REVEL v1.3 | `revel-v1.3_all_chromosomes.zip` | Maximum over transcripts |

Both CADD files were queried remotely for chr17:41197000-41277000 by tabix; their downloaded indexes
match the published MD5s. Every one of the 3,893 variants had a CADD v1.7 and a SpliceAI score, and
every one of the 2,086 missense variants had a REVEL score. Evo 2 and CADD v1.3 values reproduce the
W1 results exactly.

## AUROC, LOF against FUNC and INT

95% intervals from 2,000 resamples of positions (seed 7), as in W1. "Difference" is Evo 2 minus the
predictor, paired on the same resamples.

| Region | Predictor | AUROC (95% CI) | Difference from Evo 2 (95% CI) | Evo 2 advantage |
|---|---|---|---|---|
| All (3,893; 823 LOF) | Evo 2 7B | 0.875 (0.859 to 0.891) | | |
| | CADD v1.3 | 0.804 (0.782 to 0.824) | +0.071 (+0.050 to +0.095) | Holds |
| | CADD v1.7 | 0.881 (0.862 to 0.897) | -0.006 (-0.025 to +0.014) | Not detected |
| | SpliceAI | 0.694 (0.665 to 0.723) | +0.181 (+0.151 to +0.211) | Holds |
| Coding (2,768; 584 LOF) | Evo 2 7B | 0.840 (0.818 to 0.861) | | |
| | CADD v1.3 | 0.841 (0.821 to 0.860) | -0.001 (-0.026 to +0.023) | Not detected |
| | CADD v1.7 | 0.892 (0.875 to 0.908) | -0.052 (-0.073 to -0.030) | Reverses |
| | SpliceAI | 0.588 (0.559 to 0.618) | +0.252 (+0.215 to +0.286) | Holds |
| Noncoding (1,125; 239 LOF) | Evo 2 7B | 0.953 (0.935 to 0.968) | | |
| | CADD v1.3 | 0.875 (0.839 to 0.909) | +0.077 (+0.044 to +0.113) | Holds |
| | CADD v1.7 | 0.932 (0.906 to 0.955) | +0.021 (-0.003 to +0.045) | Not detected |
| | SpliceAI | 0.963 (0.945 to 0.980) | -0.011 (-0.025 to +0.003) | Not detected |
| Missense (2,086; 441 LOF) | Evo 2 7B | 0.785 (0.756 to 0.813) | | |
| | CADD v1.3 | 0.738 (0.710 to 0.768) | +0.047 (+0.009 to +0.083) | Holds |
| | CADD v1.7 | 0.828 (0.800 to 0.853) | -0.042 (-0.074 to -0.009) | Reverses |
| | REVEL | 0.867 (0.843 to 0.889) | -0.081 (-0.114 to -0.048) | Reverses |

## Reading this

- 230 of the 239 noncoding LOF variants are canonical splice or splice-region variants, so a
  splicing model does as well as Evo 2 there. On coding variants, where loss of function mostly acts
  through the protein, SpliceAI's AUROC is 0.588.
- CADD v1.7 includes SpliceAI among its features, which is the likely reason it closed most of the
  noncoding gap that CADD v1.3 left.
- Evo 2 is a zero-shot model with no splicing or protein features, and it matches the best
  noncoding predictor here without training on labels. That is the defensible claim; "beats current
  tools" is not.
- REVEL was trained on labelled missense variants that may include BRCA1, so its missense result
  may be optimistic. CADD v1.7 and SpliceAI were not trained on labels of that kind.
- One gene and one assay, as for W1.

## For slides s4-matrix and s5f-auroc

Replace "current CADD, REVEL and SpliceAI not compared" with one row per predictor:

| Predictor | All | Coding | Noncoding | Missense |
|---|---:|---:|---:|---:|
| Evo 2 7B (zero-shot) | 0.875 | 0.840 | 0.953 | 0.785 |
| CADD v1.3 (supplied with the data) | 0.804 | 0.841 | 0.875 | 0.738 |
| CADD v1.7 | 0.881 | 0.892 | 0.932 | 0.828 |
| SpliceAI (masked, precomputed) | 0.694 | 0.588 | 0.963 | not compared |
| REVEL v1.3 | missense only | missense only | missense only | 0.867 |

Suggested line: "Against current CADD and SpliceAI, Evo 2's noncoding advantage is not detected
(0.953 against 0.932 and 0.963); on coding and missense variants current tools lead."
