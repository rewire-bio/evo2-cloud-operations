# Methods review: Evo 2 cloud operations study

Reviewer role: methods reviewer (independent). Date: 2026-10-09.
Snapshot revision: `64de22d083e740c876751da81fdc02f1acecd380`.
Recorded run reviewed: `b75c67aa959b424c88fd49bcce4d16b5` (provenance: git revision `e93491ac`,
image `sha256:22970720…`, code SHA-256 `17214923…`, config SHA-256 `dca1322f…`).
Comparison runs (read-only): `results/phased-20261009/` and rejected run `698234c1…`.

VERDICT: fail

The core measurements are sound and mostly well reported. I recomputed the exon-classifier AUROCs
and cross-platform probability differences by hand, and they match. The fail verdict comes from a
group of fixable reporting errors in `paper/main.tex`, plus three issues of baseline framing,
licensing and protocol deviation. Each one is listed below with the fix needed. None needs new GPU
runs. One gap in this review also needs closing: I had no code-execution tool, so I could not
recompute the W1 (BRCA1) AUROCs or W1 agreement statistics over 3,893 variants (see "Review
limitations").

---

## 1. What I checked and how

| Check | Method | Outcome |
|---|---|---|
| W2 exon AUROC, reference platform (P2) | Hand computation from `platforms/P2/attempt-1/w2_exon_probabilities.tsv`: 61 positives, 61 negatives, 3,721 pairs; counted negatives that outrank each positive | 205 discordant pairs, so AUROC = 1 − 205/3721 = **0.944907**. Matches `results.json` (0.944907282988444) |
| W2 exon AUROC, L40S (P5) | Same method on `platforms/P5/attempt-2/w2_exon_probabilities.tsv` | 203 discordant pairs, so AUROC = **0.945445**. Matches (0.9454447729105079) |
| W2 maximum absolute difference, P5 against P2 | Row-by-row inspection | Largest is index 6 (FAN1): 0.41134399 − 0.39121839 = **0.0201256**. Matches 0.020125597715377808 |
| W1 P3 against P2 identity | Spot check of the first 14 and last 10 rows of both `w1_brca1_scores.tsv` files | Identical in `ref_score`, `var_score` and `delta`. Consistent with max abs diff 0 and Spearman 1.0 |
| W1 P5 against P2 | Same rows | They differ. Reference-window log-likelihoods differ by about 1e-4, and some small deltas change sign (e.g. `chr17:41276132:A>T` is −2.35e-4 on H100 and +3.11e-4 on L40S). Consistent with median abs diff 1.17e-4 and max 1.31e-3 |
| L40S determinism across hosts and drivers | Phased P5 (US-TX-4, driver 595.91.07, kernel 6.8) against recorded P5 (US-MO-1, driver 580.159.03, kernel 6.17), first 7 rows | Bit-identical. Supports attributing the difference to the GPU model rather than driver, kernel or host |
| Label and subset counts | Grep counts on the run bundle's `brca1_variants.tsv` | LOF 823, INT 249 (so FUNC 2,821); coding 2,768, noncoding 1,125; no missing CADD or phyloP values. Matches protocol and figure labels |
| W0 | All `receipt-main.json` files | Per-sequence losses (0.181640625, 0.353515625, 0.5, 0.35546875) are identical on all three GPUs; mean 0.34765625 passes. Per-sequence **accuracies differ** on the L40S (mean 0.86260 against 0.86361) |
| Cost arithmetic | `operations.json` events × `prices.json` | P2: 2,734 s × 6.2892 USD/h = 4.78. P3: 2,526 s × 4.0174 USD/h = 2.82. P5 attempt 2: 9,531 s × 1.1174 USD/h = 2.96. All correct for the attempts included |
| Per-1,000-variant cost | `analyse.py` formula, recomputed | P3 ≈ 0.51, P5 ≈ 0.68, P2 ≈ 0.80 USD. At the phased host's 0.93 windows/s, P5 ≈ 0.45 USD. The "below to above the Runpod H100" statement holds |
| Code against protocol | `workloads.py`, `run.py`, `analysis.py`, `collect.py`, `prepare_inputs.py`, `configs/full.json` | W0–W4 implemented as specified (details in section 2) |
| Literature check | Findlay et al. 2018 Methods (PMC6181777), CADD v1.6 release notes | The Findlay table's CADD is **v1.3**. The function-score licence is "freely available for all nonprofit uses" |

## 2. Protocol conformance (implementation)

These match the protocol and its amendments:

- **W0.** Reimplements Arc's forward test with a tolerance of 1e-3. A failure raises and skips later workloads (`run.py`).
- **W1.** 8,192 bp windows. Score = variant mean log-likelihood minus reference mean
  log-likelihood (`score_sequences`, batch 1, `reduce_method="mean"`). AUROC uses the negated
  delta. Labels are LOF against FUNC+INT. Coding means Missense, Nonsense or Synonymous; everything else is noncoding.
- **Baselines.** CADD and mammalian phyloP are used un-negated, as amendment 1 requires. The
  consequence-rule mapping matches the table's strings ("Nonsense", "Canonical splice", "Splice
  region", "Missense").
- **Grouped bootstrap.** 2,000 resamples, seed 7, resampling whole positions. All score sets use
  the same resample indices, so differences are properly paired. Intervals are percentile intervals.
  `difference_vs_evo2_7b` is Evo 2 minus baseline, and the paper's "in CADD's disfavour" wording
  matches that sign.
- **Agreement.** Max and median absolute difference, Spearman on average ranks, and rank moves of
  more than 1% of n (38.93 places). W2 max abs probability difference. W4 statistics within each
  platform.
- **W4.** Runs in a separate process (`--workloads w4` gives `receipt-repeat.json`) on the first
  200 variants.
- **W3.** Stops at the first OOM. OOM occurred at 131,072 bp on both GPU models, so 262,144 bp was
  correctly not attempted.
- **Platforms.** Reference P2, fallback P3, P5 GPU list as in amendments 2 and 3. P1 and P4 are reported as
  unavailable. All three platforms used the same image digest, code hash and pip-freeze hash.
- **Recorded-run attempt limits.** P2 1, P3 1, P5 2. Within the limit of 2.

## 3. Blocking findings

### B1. The "Operational events" paragraph attributes other runs' events to the recorded run (`paper/main.tex` lines 206–211)

- "In the recorded run, the first Google Cloud attempt of the day had lost GPU access for new
  processes…" is wrong about which run this was. In the recorded run, P2 attempt 1 completed W0–W4
  (`launch-outcomes.json`: P2 attempts 1, completed; `receipt-repeat.json` status completed). The
  GPU-access failure happened in **rejected run 698234c1** (run log, 14:19–16:14).
- "L40S throughput varied by host: 0.93 windows per second on the first host and 0.61 on the host
  used in the recorded run." In context, "first host" reads as the recorded run's P5 attempt 1. That
  pod (`ge709dd9pdr5ow`, US-MO-1) ran at 0.59–0.67 sequences/s cumulative according to its own
  `workloads.log`, not 0.93. The 0.93 figure comes from the **phased** run's pod `eq8fyz8grfp4kt`
  in US-TX-4. The rejected run's L40S, also in US-TX-4, ran at 0.916. The evidence actually shows
  ≈0.92–0.93/s on both Texas hosts and ≈0.6/s on both Missouri hosts. That pattern should be
  reported as it is, with its run of origin.
- The paper never says that run 698234c1 was rejected by the harness for modification of
  scientific inputs during the run. Line 127 cites it only as an "earlier run" with bit-identical
  scores. The rejection and its reason should be disclosed, because the paper relies on that run
  for the bit-identity statement.

**Fix:** reword the paragraph so each event is attributed to the run it happened in (phased,
rejected 698234c1, recorded b75c67aa), and disclose the rejection.

### B2. `\PTwoDockerInstall` renders as "0 s" (paper line 196)

`scripts/analyse.py` reads `p.get("docker_install_s")` from `operations.json`, but
`scripts/collect.py` copies only `docker_pull_s` from `host-timings.json`. The recorded run's
`platforms/P2/attempt-1/host-timings.json` has `"docker_install_s": 21`; the phased run's value was
457 s. As built, the paper says Docker and the toolkit had to be installed "(0 s)", which is false.
Also, 21 s is not "large relative to this short workload", so the sentence's argument needs
revisiting once the correct value is shown.

**Fix:** carry `docker_install_s` through `collect.py`, or read `host-timings.json` in
`analyse.py`. Then re-check the sentence.

### B3. The recorded run's total cost leaves out a failed attempt (paper line 197, `TotalRunCost`)

`collect.py` costs only the completed attempt per platform. P5 attempt 1 in the recorded run (pod
`ge709dd9pdr5ow`) was created at 16:16:00 and deleted at 16:59:54. That is 2,634 s at
1.09 + 0.0274 USD/h, about **USD 0.82**, and it is not counted. "The recorded run cost USD
\TotalRunCost{} in total" therefore understates the cost: it is about 10.56 against an actual
≈11.38. The protocol counts failed attempts against the budget.

**Fix:** include failed-attempt billing in the total, or relabel it as "completed attempts only"
and state the failed-attempt cost separately. It would also help to report total study spend
(phased, rejected, recorded, aborted reproduction and image build) against the USD 150 cap. By my
rough estimate it is about USD 40; it is not reported anywhere.

### B4. The CADD baseline is v1.3, and the abstract overstates the coding/noncoding split

- Findlay et al. 2018 Methods state that CADD and phyloP annotations came from **CADD version 1.3**
  (PMC6181777). CADD v1.6 added the SpliceAI and MMSplice splicing predictors as features. Per its
  release notes, the gains are concentrated in splice-site and intronic variants, which is exactly
  the noncoding subset where Evo 2's advantage appears (noncoding Δ +0.077 [+0.044, +0.113]; coding
  Δ −0.001 [−0.026, +0.023]). Neither the paper nor `evidence/claims.json` gives the CADD version,
  so readers will assume current CADD. This is a baseline-fairness problem for the paper's main
  biological comparison.
- The abstract says Evo 2 beat CADD "**entirely** through noncoding variants". AUROC does not add
  up across subsets: the all-SNV AUROC includes cross-subset pairs, such as noncoding LOF against
  coding FUNC. Also, the coding interval (−0.026 to +0.023) shows no detectable difference; it does
  not establish equality. Claims `interp-noncoding` ("came from noncoding variants") and
  `diff-cadd-coding-ci-high` ("so the two were level") have the same issue in milder form.

**Fix:** write "CADD v1.3 (as provided in the Findlay et al. table)" in the abstract, results,
Figure 2 caption and claims. Add a limitation that later CADD releases with splicing features were
not compared. Replace "entirely through" with, for example, "the difference was concentrated in
noncoding variants; on coding variants no difference was detected (−0.001 [−0.026, +0.023])".

### B5. The memory conclusions go beyond the measurements (paper lines 160–162 and 223–226)

- "Window lengths beyond about 32 kb need multi-GPU inference" has no supporting measurement. W3
  probed 8,192, 32,768 and 131,072 bp only. Allocated memory was 16.83 GiB at 8,192 bp and 30.36
  GiB at 32,768 bp, roughly 0.55 GiB per kb. Linear extrapolation gives about 49 GiB at 65 kb, which
  fits the H100's 79.2 GiB usable (though not the L40S's 44.4 GiB). The paper's own citation, EVEE,
  ran 65 kb windows on H100s.
- "The checkpoint's 1 Mb context is therefore not reachable in one forward pass **on a single
  GPU**" generalises from two GPU models (80 GB and 48 GB) to every single GPU. It also depends on
  this code path: `model.model.forward` with FFT prefill and full logits returned.

**Fix:** limit both statements to what was measured. For example: "on the 80 GB H100 and 48 GB
L40S, one forward pass fit at 32,768 bp and failed at 131,072 bp; lengths in between were not
tested". Alternatively, add a 65,536 bp probe in a future amended run.

### B6. Data licence for the Findlay table is misstated (`data/manifest.json`)

The manifest's licence field for `41586_2018_461_MOESM3_ESM.xlsx` frames the file as
"redistributed in ArcInstitute/evo2 (Apache-2.0 repository)". Arc's Apache-2.0 licence does not
relicense third-party data. Findlay et al.'s Data and Code Availability statement says function
scores are "freely available for all nonprofit uses" and are available to commercial entities by
licence, on conditions. The study does not redistribute the table, and committed evidence holds
only Evo 2 scores keyed by variant ID. Even so, the licence record is inaccurate, and the study
owner needs to confirm their use is nonprofit or otherwise permitted. I cannot determine that.

**Fix:** correct the licence field and cite the Findlay availability statement. The owner should
record that the use falls within those terms.

### B7. Protocol deviations recorded without amendment or explicit acknowledgement

The run log is commendably complete, but these deviations from the approved protocol are not
labelled as deviations and have no amendment:

- **Attempt limits and stopping rule in the phased runs.** The protocol allows at most 2 attempts
  per platform per phase and says "stop a platform after two failed attempts". Phase 1 had P3 at
  9 attempts, P2 at 5 (attempt 3 ran about 20 minutes of billed compute) and P5 at 3, with attempt
  3 launched one minute after the run log declared P5 "unavailable for this phase".
- **"Each platform runs once."** The study ran a phased run, a rejected run, the recorded run and
  an aborted reproduction. The owner approved the clean run ("Yes please", per the run log), but
  this is not recorded in `protocol/amendments/` as the protocol requires for design changes.
- The paper relies on non-recorded runs for its evidence: the 0.93/s throughput, the India and
  Texas placements, and bit-identity "across runs".

**Fix:** add a deviation note or amendment that lists these departures, and obtain the owner's
renewed approval or acknowledgement. Under the reviewer instructions, material protocol changes
are blockers that need renewed human approval. I do not approve them on the owner's behalf. No
rerun is needed.

## 4. Non-blocking findings and suggestions

1. **The W0 gate has bf16 resolution.** Per-sequence losses are bf16-quantised (multiples of 2^-9
   near 0.35), so the 1e-3 gate cannot detect the ~1e-4 changes seen in W1. The L40S's identical
   loss but different accuracy (0.86260 against 0.86361) shows this directly. Report W0 accuracy
   and add it to claim `w0-runpod-l40s`. The paper's conclusion that "Arc's correctness test is
   not sufficient on its own" is supported.
2. **Wording of `interp-gpu-model`.** "Changed per-variant scores by an amount comparable to the
   scores" holds for the typical, near-zero FUNC scores (median |Δ| ≈ 1.2e-4). For strongly
   negative LOF scores (around −3e-3) the change is about 5%. Say "comparable to the typical
   (median) score". It is also worth noting that the reference-window log-likelihoods themselves
   shift by about 1e-4, which is the mechanism behind the sign flips.
3. **Claims do not cover all paper numbers.** The abstract and results cite values with no entry
   in `evidence/claims.json`: rank moves (2,627, from `agreement-details.json`), USD per 1,000
   variants, total run cost, OOM at 131 kb, throughput values, the 0.93/s phased value, and Docker
   pull and install times. Add claims with result pointers. Values from non-recorded runs should
   point to their run IDs.
4. **The `exon-auroc` claim leaves out its caveat.** The claim text lacks the possible
   training-set overlap that the paper states. Add it as a `limitations` field, or reword.
5. **Bootstrap dependence.** Resampling by position ignores dependence between neighbouring
   positions, whose 8 kb windows almost entirely overlap, and clustering by exon. Intervals may be
   too narrow. Consider a sensitivity analysis with exon-level blocks.
6. **No interval for the cross-GPU AUROC difference.** The "almost unchanged" AUROC (0.877
   against 0.875) has no paired interval. Computing one from the same resamples is cheap.
7. **The rank-move metric is hard to interpret.** Most of the 3,893 scores sit in a dense
   near-zero cluster, so ~1e-4 noise moves many ranks by more than 39 places (2,627). That is
   correct but dominated by FUNC variants. Also report rank stability among LOF variants, or
   top-k overlap.
8. **Memory figure.** Horizontal lines at "80 GB" and "48 GB" are drawn on a GiB axis. PyTorch
   reports 79.18 GiB and 44.39 GiB usable. Label the usable capacity.
9. **FP8 framing.** The model config in the logs shows `use_fp8_input_projections: True` with
   Transformer Engine installed on all platforms. The literature claim `lit-hardware` ("runs in
   bfloat16") is accurate as a source statement, but the paper should say plainly that the
   measured runs used FP8 input projections. The discussion's FP8 hypothesis is appropriately
   flagged as untested.
10. **Billing reconciliation.** The protocol says costs are "reconciled against billing records
    where available". The paper does not say whether this was done.
11. **"Reproduction" framing.** Contribution 5 calls these reproductions of Arc workflows, but
    no published reference value is compared. Arc's BRCA1 notebook demonstrates `evo2_1b_base`.
    Either compare against the Evo 2 paper's reported 7B BRCA1 values, or call these
    "re-implementations".
12. **Bit-identity across runs** (paper line 127) rests on the run log. Add a computed comparison
    artefact (max abs diff per platform, phased and rejected against recorded) so it can be traced.
    My spot checks agree.
13. **Unverified details:** "flash-attn 2.7.3" and "12 GB compressed image" (paper lines 78 and
    195) have no evidence in the run outputs I reviewed. Point them to the pip-freeze file and the
    image manifest.
14. **Spot risk.** The P2 Spot instance was not pre-empted, but the cost comparison should note
    that Spot capacity can be reclaimed mid-run.
15. **Exon-classifier licence.** The licence of `schmojo/evo2-exon-classifier` is not recorded in
    the manifest or the protocol.

## 5. Strengths

- Clean separation of `results.json` (science) from `operations.json` (operations). Every number
  is derived from per-variant files by deterministic scripts.
- Strong evidence that same-GPU-model outputs are deterministic: identical across two providers,
  across processes (W4) and across L40S hosts with different drivers and kernels.
- The phyloP sign amendment is transparent, and its rationale was fixed in advance.
- Failed attempts are kept on disk, and the run log is candid, including the harness rejection
  and the orphaned firewall rule.
- Hash-pinned weights. The exon classifier is rebuilt locally rather than loaded with
  `trust_remote_code`.

## 6. Review limitations

- **W1 AUROCs (0.875, 0.877, subsets, baselines, bootstrap intervals) and W1 agreement statistics
  (median 1.17e-4, max 1.31e-3, Spearman 0.983, rank moves 2,627) were not independently
  recomputed.** No code-execution tool was available in this review environment, and hand
  computation over 3,893 variants is not reliable. I verified the inputs (label counts, subset
  counts, no missing baseline values), the code paths, and row-level spot checks consistent with
  the reported values. Before sign-off, the coordinator or a reproduction worker should rerun
  `scripts/collect.py` (or an independent AUROC/Spearman implementation) on
  `.research/runs/b75c67aa…/output` and confirm the W1 values to within 1e-12.
- I checked bit-identity between runs on sampled rows only, not whole files.

## Sources (external, retrieved 2026-10-09)

- Findlay et al. 2018, author manuscript, Methods (CADD v1.3) and Data Availability:
  https://pmc.ncbi.nlm.nih.gov/articles/PMC6181777
- CADD v1.6 release notes (SpliceAI and MMSplice features):
  https://cadd.kircherlab.bihealth.org/static/ReleaseNotes_CADD_v1.6.pdf
- Rentzsch et al. 2021, CADD-Splice, Genome Medicine: https://link.springer.com/doi/10.1186/s13073-021-00835-9
