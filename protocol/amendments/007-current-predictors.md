# Amendment 7: current CADD, SpliceAI and REVEL on the BRCA1 variants

Date: 13 October 2026. Written before any score from the tables below was fetched or compared,
apart from one CADD row read while checking that remote lookup works. Analysis only, on published
precomputed scores; no GPU runs. The main study's results are unchanged. Raised in
[issue #4](https://github.com/rewire-bio/evo2-cloud-operations/issues/4) after the AMP audience
review asked whether Evo 2 7B's noncoding advantage over CADD v1.3 holds against current predictors.

## Question

On the same 3,893 BRCA1 SNVs and labels as W1, how do current CADD, SpliceAI and (for missense
variants) REVEL compare with Evo 2 7B? In particular, does Evo 2's noncoding advantage hold?

## Inputs

- Variants and labels: `data/derived/brca1_variants.tsv` (`lof` against FUNC and INT; `region`
  coding or noncoding; `consequence`). GRCh37 coordinates.
- Evo 2 7B: W1 scores from recorded run b75c67aa, Google Cloud H100 (P2), score = -delta.
- CADD v1.3: the column supplied with the Findlay et al. table, as in W1.
- **CADD v1.7, GRCh37**, `whole_genome_SNVs.tsv.gz` from
  `https://kircherlab.bihealth.org/download/CADD/v1.7/GRCh37/`. RawScore is the primary score;
  PHRED is reported as well. Fetched for chr17:41197000-41277000 by remote tabix query.
- **SpliceAI**, from the same CADD v1.7 release, `whole_genome_SNVs_inclAnno.tsv.gz`. CADD v1.7
  GRCh37 annotates each variant with Illumina's precomputed masked SpliceAI scores
  (`spliceai_scores.masked.all.hg19`, per CADD-scripts `config/references_GRCh37_v1.7.cfg`), matched
  by gene name. The score is the maximum of the four delta scores (acceptor gain and loss, donor gain
  and loss) on rows annotated to gene BRCA1. This replaces a direct download from Illumina, which
  needs an account; the values are the same precomputed masked scores.
- **REVEL v1.3**, `revel-v1.3_all_chromosomes.zip` from the REVEL download page
  (https://sites.google.com/site/revelgenomics/downloads). Rows matched on GRCh37 position, reference
  and alternate base; the score is the maximum over rows for a variant. REVEL scores missense
  variants only.
- Checksums: the published MD5 of each CADD file and its index are recorded; the REVEL zip's SHA-256
  is recorded; the SHA-256 of every local extract is recorded.

## Analysis (fixed now)

1. **Coverage.** For each table, the number of the 3,893 variants with no score, by region (and for
   REVEL, among the 2,086 missense variants).
2. **All, coding and noncoding.** AUROC for LOF against not LOF for Evo 2 7B, CADD v1.3, CADD v1.7
   (raw) and SpliceAI, with the W1 method: `grouped_bootstrap_auroc`, resampling positions, 2,000
   draws, seed 7. Computed on the variants scored by all four, with Evo 2 first so each predictor's
   paired difference from Evo 2 and its 95% interval are reported. CADD v1.7 PHRED is reported in the
   same way for reference.
3. **Missense.** On missense variants scored by REVEL: Evo 2 7B, CADD v1.3, CADD v1.7 and REVEL,
   same method.
4. **Reading the result.** Evo 2's advantage over a predictor "holds" in a region if the 95%
   interval of the paired difference (Evo 2 minus predictor) is above 0, "reverses" if below 0, and
   is "not detected" otherwise. The headline question is the noncoding comparison with CADD v1.7 and
   with SpliceAI.
5. **Licences.** CADD is free for non-commercial use; REVEL is free for non-commercial use; the
   study is a nonprofit use (`data/LICENSES.md`). Per-variant values from these tables are not
   committed. The repository keeps the fetch script, checksums and summary results only.

## Caveats stated in advance

- CADD v1.7 uses SpliceAI among its features, so CADD v1.7 and SpliceAI are not independent.
- REVEL was trained on disease and putatively neutral missense variants from HGMD and population
  data, which may include BRCA1 variants, so its BRCA1 performance may be optimistic. CADD and
  SpliceAI are not trained on variant labels of this kind.
- SpliceAI predicts splicing only, so it is not expected to separate coding LOF variants that act
  through the protein.

## Approval

Approved by Tim Richardson on 13 October 2026 ("can you do 4 please", issue #4).
