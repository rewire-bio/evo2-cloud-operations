# Response to the methods review (worker f0eb685d, verdict: fail)

Coordinator response, 9 October 2026. All changes are text, claims and documentation; no code,
configuration, data manifest or container changed. The reviewer's request for an independent W1
recomputation is met by `evidence/checks/verify_results.py` (pairwise AUROC and pandas ranks,
separate from the study code), whose output `evidence/checks/verification.json` matches
`results.json` exactly for all W1 AUROCs and agreement statistics.

| Finding | Response |
|---|---|
| B1 events attributed to the wrong run; rejected run undisclosed | Fixed. Operational events now name the run each event happened in; the rejection of 698234c1 and its reason are stated where it is used. L40S throughput is attributed to US-TX-4 (phased, rejected) and US-MO-1 (recorded) hosts. |
| B2 Docker install shown as "0 s" | Fixed in the text with values from `host-timings.json` (21 s recorded, 457 s phased). The underlying `collect.py` omission is noted for the next code revision; changing it now would change the scientific inputs of the recorded run. |
| B3 total cost omits failed attempt; study spend not reported | Fixed. The paper gives completed-attempt cost, the failed L40S attempt (USD 0.82), the recorded-run total (USD 11.38) and the approximate whole-study spend. |
| B4 CADD is v1.3; "entirely through noncoding" overstated | Fixed. CADD v1.3 is named in the abstract, results, figure caption, limitations and claims; a limitation notes that later CADD releases add splicing features. Wording now says the difference was concentrated in noncoding variants and no difference was detected on coding variants, and that subset AUROCs do not decompose the overall AUROC. |
| B5 memory conclusions beyond measurements | Fixed. Statements are limited to the lengths tested and to this code path; a linear extrapolation to 65 kb is labelled as untested. |
| B6 Findlay licence misstated | Corrected in `data/LICENSES.md` and the paper. The owner confirmed this is a nonprofit use. The manifest field is left unchanged because the manifest is hashed as a scientific input. |
| B7 protocol deviations without amendment | Amendment 4 lists them; acknowledged by the owner. |
| NB1 W0 resolution | Accuracy difference reported in the paper and claim `w0-runpod-l40s`. |
| NB2 interpretation wording | Revised to "about the typical (median) score"; reference-window shift mentioned. |
| NB3 claims for non-results numbers | Values from `operations.json` and earlier runs are cited to `evidence/checks/verification.json` or the run log; the harness accepts measurement claims only from `results.json`. |
| NB4 exon caveat | Added to the claim text. |
| NB5 bootstrap dependence | Stated as a limitation in the results. |
| NB6 cross-GPU AUROC interval | Computed: +0.0021 [0.0002, 0.0042]; reported. |
| NB7 rank-move metric | LOF-only Spearman (0.998) and top-k overlap (48 of 50) reported. |
| NB8 memory figure units | Caption gives usable GiB; figure code unchanged (scientific input). |
| NB9 FP8 | Methods state that FP8 input projections were active on all platforms. |
| NB10 billing reconciliation | Stated as not done line by line. |
| NB11 "reproduction" framing | Changed to "re-implements"; no published 7B reference compared. |
| NB12 bit-identity artefact | `evidence/checks/verification.json`. |
| NB13 flash-attn and image size | Pointed to the pip-freeze file and registry manifest. |
| NB14 Spot risk | Added. |
| NB15 exon classifier licence | Apache-2.0, recorded in `data/LICENSES.md`. |

The revised manuscript was not re-reviewed by a second worker.
