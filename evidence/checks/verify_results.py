"""Independent checks of the recorded run, written separately from scripts/collect.py and
src/study/analysis.py (methods review, 9 October 2026).

- Recomputes W1 AUROCs by direct pairwise comparison, and cross-GPU agreement with pandas ranks.
- Compares per-variant scores between the recorded run and the two earlier runs.
- Adds rank stability among LOF variants, top-k overlap, and a paired grouped-bootstrap interval
  for the L40S minus H100 AUROC difference.
- Totals billed cost per run including failed attempts, and collects Docker timings.

Usage: uv run --frozen python evidence/checks/verify_results.py STUDY_DIR > evidence/checks/verification.json
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

STUDY = Path(sys.argv[1]).resolve()
RECORDED = STUDY / ".research/runs/b75c67aa959b424c88fd49bcce4d16b5/output"
EARLIER = {
    "phased-20261009": (STUDY / "results/phased-20261009", {"P2": "attempt-5", "P3": "attempt-9", "P5": "attempt-3"}),
    "rejected-698234c1": (STUDY / ".research/runs/698234c107414bfab47bbbdf4bf613d5/output", None),
    "reproduction-30e7ae49": (STUDY / ".research/reproductions/30e7ae49c4ca4c2e854c61825a3738ce/checkout/results/full", None),
}
CODING = {"Missense", "Nonsense", "Synonymous"}


def pairwise_auroc(labels: np.ndarray, scores: np.ndarray) -> float:
    pos, neg = scores[labels == 1], scores[labels == 0]
    greater = (pos[:, None] > neg[None, :]).sum()
    ties = (pos[:, None] == neg[None, :]).sum()
    return float((greater + 0.5 * ties) / (len(pos) * len(neg)))


def completed(run_dir: Path, pid: str) -> Path:
    for attempt in sorted((run_dir / "platforms" / pid).glob("attempt-*"), reverse=True):
        receipt = attempt / "receipt-main.json"
        if receipt.exists() and json.loads(receipt.read_text())["status"] == "completed":
            return attempt
    raise FileNotFoundError(pid)


def delta(attempt: Path) -> pd.Series:
    return pd.read_csv(attempt / "w1_brca1_scores.tsv", sep="\t").set_index("id")["delta"]


def utc(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


bundle = next(RECORDED.glob("bundle-*"))
variants = pd.read_csv(bundle / "data/brca1_variants.tsv", sep="\t").set_index("id")
lof = variants["lof"].to_numpy()
coding = variants["consequence"].isin(CODING).to_numpy()
scores = {pid: delta(completed(RECORDED, pid)).reindex(variants.index) for pid in ("P2", "P3", "P5")}
out: dict = {"recorded_run": RECORDED.parent.name, "w1_auroc": {}, "agreement_vs_P2": {}, "across_runs": {},
             "costs": {}, "docker_s": {}}

for pid, s in scores.items():
    neg = -s.to_numpy()
    out["w1_auroc"][pid] = {"all": pairwise_auroc(lof, neg), "coding": pairwise_auroc(lof[coding], neg[coding]),
                            "noncoding": pairwise_auroc(lof[~coding], neg[~coding])}

ref = scores["P2"]
for pid in ("P3", "P5"):
    other = scores[pid]
    diff = (ref - other).abs()
    ranks_ref, ranks_other = ref.rank(), other.rank()
    lof_ids = variants.index[lof == 1]
    lof_ref, lof_other = ref[lof_ids].rank(), other[lof_ids].rank()
    top = {k: len(set(ref.nsmallest(k).index) & set(other.nsmallest(k).index)) for k in (50, 100, 200)}
    out["agreement_vs_P2"][pid] = {
        "max_abs_difference": float(diff.max()), "median_abs_difference": float(diff.median()),
        "spearman": float(ranks_ref.corr(ranks_other)),
        "rank_moves_over_1pct": int(((ranks_ref - ranks_other).abs() > 0.01 * len(ref)).sum()),
        "lof_only_spearman": float(lof_ref.corr(lof_other)),
        "lof_only_rank_moves_over_1pct": int(((lof_ref - lof_other).abs() > 0.01 * len(lof_ids)).sum()),
        "top_k_overlap_most_damaging": top,
    }

# Paired grouped bootstrap: L40S minus H100 AUROC, resampling positions (seed 11, 2,000 draws).
rng = np.random.default_rng(11)
groups = variants["pos"].to_numpy()
members = [np.flatnonzero(groups == g) for g in np.unique(groups)]
h100, l40s = -scores["P2"].to_numpy(), -scores["P5"].to_numpy()
draws = []
for _ in range(2000):
    idx = np.concatenate([members[i] for i in rng.integers(0, len(members), len(members))])
    draws.append(pairwise_auroc(lof[idx], l40s[idx]) - pairwise_auroc(lof[idx], h100[idx]))
out["l40s_minus_h100_auroc"] = {"point": out["w1_auroc"]["P5"]["all"] - out["w1_auroc"]["P2"]["all"],
                                "ci95": [float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))]}

for name, (run_dir, chosen) in EARLIER.items():
    out["across_runs"][name] = {}
    for pid in ("P2", "P3", "P5"):
        attempt = run_dir / "platforms" / pid / chosen[pid] if chosen else completed(run_dir, pid)
        earlier = delta(attempt).reindex(variants.index)
        out["across_runs"][name][pid] = float((earlier - scores[pid]).abs().max())

prices = json.loads((RECORDED / "prices.json").read_text())
for pid in ("P2", "P3", "P5"):
    hourly = prices[pid]["instance_usd_per_hour"] + prices[pid]["storage_usd_per_hour"]
    attempts = {}
    for attempt in sorted((RECORDED / "platforms" / pid).glob("attempt-*")):
        ev = {r["event"]: r["utc"] for r in map(json.loads, (attempt / "events.jsonl").read_text().splitlines())}
        start = ev.get("pod_created") or ev.get("running")
        if start and "terminated" in ev:
            seconds = (utc(ev["terminated"]) - utc(start)).total_seconds()
            attempts[attempt.name] = {"billed_seconds": seconds, "usd": round(seconds / 3600 * hourly, 2)}
    out["costs"][pid] = {"attempts": attempts, "usd_total": round(sum(a["usd"] for a in attempts.values()), 2)}
out["costs"]["recorded_run_usd_total"] = round(sum(out["costs"][p]["usd_total"] for p in ("P2", "P3", "P5")), 2)

for name, path in {"recorded": RECORDED / "platforms/P2/attempt-1/host-timings.json",
                   "phased": STUDY / "results/phased-20261009/platforms/P2/attempt-5/host-timings.json"}.items():
    out["docker_s"][name] = json.loads(path.read_text())

json.dump(out, sys.stdout, indent=2)
print()
