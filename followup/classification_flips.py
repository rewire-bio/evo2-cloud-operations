"""Amendment 6: how many variants change call between GPUs at a threshold fixed on the H100. Offline.

  uv run --frozen python followup/classification_flips.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from study.analysis import call_flips, sensitivity_threshold, youden_threshold  # noqa: E402

RUNS = {"recorded": ROOT / "evidence/runs/recorded-b75c67aa", "reproduction": ROOT / "evidence/runs/reproduction-30e7ae49"}
FOLLOWUP = ROOT / "evidence/followup-20261011"
OUTPUT = ROOT / "evidence/classification-flips/results.json"
SUBSET_PAIRS = {
    "default: H100 vs L40S": ("FH/default-b1", "FL/default-b1"),
    "fp8off: H100 vs L40S": ("FH/fp8off-b1", "FL/fp8off-b1"),
    "fp32: H100 vs L40S": ("FH/fp32-b1", "FL/fp32-b1"),
    "default: L40 vs L40S": ("FA/default-b1", "FL/default-b1"),
    "fp8off: L40 vs L40S": ("FA/fp8off-b1", "FL/fp8off-b1"),
}


def lof_score(path: Path) -> pd.Series:
    """Higher means more likely loss of function."""
    return -pd.read_csv(path, sep="\t").set_index("id")["delta"]


def w1(run: str, pid: str) -> pd.Series:
    attempt = json.loads((RUNS[run] / "operations.json").read_text())["platforms"][pid]["attempt"]
    return lof_score(RUNS[run] / "platforms" / pid / attempt / "w1_brca1_scores.tsv")


def thresholds(labels: np.ndarray, scores: np.ndarray) -> dict[str, float]:
    return {"youden": youden_threshold(labels, scores),
            "sensitivity_0.90": sensitivity_threshold(labels, scores, 0.90),
            "sensitivity_0.95": sensitivity_threshold(labels, scores, 0.95)}


def compare(variants: pd.DataFrame, reference: pd.Series, other: pd.Series, cuts: dict[str, float]) -> dict:
    v = variants.loc[reference.index]
    lof, coding = v["lof"].to_numpy(bool), (v["region"] == "coding").to_numpy()
    strata = {"all": np.ones(len(v), bool), "lof": lof, "not_lof": ~lof, "coding": coding, "noncoding": ~coding}
    ref, oth = reference.to_numpy(), other.reindex(reference.index).to_numpy()
    out = {}
    for name, t in cuts.items():
        called = ref >= t
        out[name] = {"reference_sensitivity": float(called[lof].mean()), "reference_specificity": float((~called[~lof]).mean()),
                     **call_flips(ref, oth, t, strata)}
    return out


def main() -> None:
    variants = pd.read_csv(ROOT / "data/derived/brca1_variants.tsv", sep="\t").set_index("id")
    h100 = w1("recorded", "P2")
    full_cuts = thresholds(variants.loc[h100.index, "lof"].to_numpy(), h100.to_numpy())
    result = {"thresholds_full_set": full_cuts, "full_set": {}, "controls": {}, "subset": {}}
    result["full_set"]["recorded: H100 (P2) vs L40S (P5)"] = compare(variants, h100, w1("recorded", "P5"), full_cuts)
    result["full_set"]["reproduction: H100 (P2, recorded) vs L40S (P5)"] = compare(variants, h100, w1("reproduction", "P5"), full_cuts)

    def control_flips(a: pd.Series, b: pd.Series) -> int:
        return max(c["strata"]["all"]["flips"] for c in compare(variants, a, b, full_cuts).values())

    result["controls"]["recorded: P2 vs P3 (both H100)"] = control_flips(h100, w1("recorded", "P3"))
    for pid in ("P2", "P3", "P5"):
        result["controls"][f"{pid}: recorded vs reproduction"] = control_flips(w1("recorded", pid), w1("reproduction", pid))

    for label, (a, b) in SUBSET_PAIRS.items():
        ref = lof_score(FOLLOWUP / a / "scores.tsv")
        cuts = thresholds(variants.loc[ref.index, "lof"].to_numpy(), ref.to_numpy())
        result["subset"][label] = {"reference": a, "other": b, "thresholds": cuts,
                                   "flips": compare(variants, ref, lof_score(FOLLOWUP / b / "scores.tsv"), cuts)}
    a, b = SUBSET_PAIRS["default: H100 vs L40S"]
    result["subset_with_full_set_thresholds"] = {
        "default: H100 vs L40S": compare(variants, lof_score(FOLLOWUP / a / "scores.tsv"),
                                         lof_score(FOLLOWUP / b / "scores.tsv"), full_cuts)}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
