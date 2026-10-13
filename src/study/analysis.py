"""Statistics for the study: AUROC with grouped bootstrap intervals, and cross-platform agreement."""
from __future__ import annotations

import math

import numpy as np


def average_ranks(values: np.ndarray) -> np.ndarray:
    """1-based ranks with ties given their average rank."""
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(len(values), dtype=float)
    sorted_values = values[order]
    i = 0
    while i < len(values):
        j = i
        while j + 1 < len(values) and sorted_values[j + 1] == sorted_values[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def auroc(labels: np.ndarray, scores: np.ndarray) -> float:
    """Probability that a positive scores above a negative (Mann-Whitney), ties counted as half."""
    labels = np.asarray(labels).astype(bool)
    scores = np.asarray(scores, dtype=float)
    n_pos, n_neg = labels.sum(), (~labels).sum()
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    ranks = average_ranks(scores)
    return float((ranks[labels].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def grouped_bootstrap_auroc(labels, score_sets: dict[str, np.ndarray], groups, n: int = 2000, seed: int = 7) -> dict:
    """AUROC for each score set, with percentile intervals from resampling whole groups.

    The same resamples are used for every score set, so paired differences are also returned
    relative to the first score set.
    """
    labels = np.asarray(labels)
    groups = np.asarray(groups)
    unique = np.unique(groups)
    members = [np.flatnonzero(groups == g) for g in unique]
    rng = np.random.default_rng(seed)
    names = list(score_sets)
    point = {k: auroc(labels, v) for k, v in score_sets.items()}
    draws = {k: np.empty(n) for k in names}
    for b in range(n):
        idx = np.concatenate([members[i] for i in rng.integers(0, len(unique), len(unique))])
        for k in names:
            draws[k][b] = auroc(labels[idx], score_sets[k][idx])
    out = {}
    first = names[0]
    for k in names:
        entry = {"auroc": point[k], "ci95": [float(np.nanpercentile(draws[k], 2.5)), float(np.nanpercentile(draws[k], 97.5))]}
        if k != first:
            diff = draws[first] - draws[k]
            entry[f"difference_vs_{first}"] = point[first] - point[k]
            entry[f"difference_vs_{first}_ci95"] = [float(np.nanpercentile(diff, 2.5)), float(np.nanpercentile(diff, 97.5))]
        out[k] = entry
    return out


def spearman(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.corrcoef(average_ranks(np.asarray(a, float)), average_ranks(np.asarray(b, float)))[0, 1])


def agreement(reference: np.ndarray, other: np.ndarray, rank_fraction: float = 0.01) -> dict:
    """How closely one platform's scores match the reference platform's, variant by variant."""
    reference, other = np.asarray(reference, float), np.asarray(other, float)
    diff = np.abs(reference - other)
    rank_ref, rank_other = average_ranks(reference), average_ranks(other)
    moved = np.abs(rank_ref - rank_other) > rank_fraction * len(reference)
    return {
        "n": int(len(reference)),
        "max_abs_difference": float(diff.max()),
        "median_abs_difference": float(np.median(diff)),
        "spearman": spearman(reference, other),
        "rank_moves_over_1pct": int(moved.sum()),
    }


CONSEQUENCE_ORDER = {"Nonsense": 3, "Canonical splice": 3, "Splice region": 2, "Missense": 1}


def consequence_rule(consequences) -> np.ndarray:
    """Annotation-only baseline: nonsense and canonical splice > splice region > missense > other."""
    return np.array([CONSEQUENCE_ORDER.get(c, 0) for c in consequences], dtype=float)


def _binomial_cdf(k: int, n: int, p: float) -> float:
    """P(X <= k) for X ~ Binomial(n, p)."""
    if p <= 0:
        return 1.0
    if p >= 1:
        return 1.0 if k >= n else 0.0
    log_p, log_q = math.log(p), math.log1p(-p)
    return min(1.0, sum(math.exp(math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1) + i * log_p + (n - i) * log_q)
                        for i in range(k + 1)))


def _bisect(f, target: float, increasing: bool) -> float:
    lo, hi = 0.0, 1.0
    for _ in range(100):
        mid = (lo + hi) / 2
        if (f(mid) < target) == increasing:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def binomial_ci(k: int, n: int, alpha: float = 0.05) -> list[float]:
    """Exact (Clopper-Pearson) interval for a proportion k/n."""
    lower = 0.0 if k == 0 else _bisect(lambda p: 1 - _binomial_cdf(k - 1, n, p), alpha / 2, increasing=True)
    upper = 1.0 if k == n else _bisect(lambda p: _binomial_cdf(k, n, p), alpha / 2, increasing=False)
    return [lower, upper]


def _candidate_thresholds(labels: np.ndarray, scores: np.ndarray):
    """Midpoints between adjacent distinct scores, ascending, with sensitivity and specificity for 'LOF if score >= t'."""
    labels = np.asarray(labels).astype(bool)
    scores = np.asarray(scores, dtype=float)
    distinct = np.unique(scores)
    thresholds = (distinct[:-1] + distinct[1:]) / 2
    above = scores[None, :] >= thresholds[:, None]
    sensitivity = (above & labels).sum(axis=1) / labels.sum()
    specificity = (~above & ~labels).sum(axis=1) / (~labels).sum()
    return thresholds, sensitivity, specificity


def youden_threshold(labels, scores) -> float:
    """Threshold maximising sensitivity + specificity - 1; ties go to the lowest threshold."""
    thresholds, sensitivity, specificity = _candidate_thresholds(labels, scores)
    return float(thresholds[np.argmax(sensitivity + specificity - 1)])


def sensitivity_threshold(labels, scores, target: float) -> float:
    """Highest threshold whose sensitivity is at least the target."""
    thresholds, sensitivity, _ = _candidate_thresholds(labels, scores)
    return float(thresholds[np.flatnonzero(sensitivity >= target).max()])


def call_flips(reference, other, threshold: float, strata: dict[str, np.ndarray]) -> dict:
    """Variants called differently by two score sets at one threshold ('LOF if score >= threshold').

    strata maps a name to a boolean mask; each gets a count, direction and exact 95% interval.
    Distances to the threshold are in units of the pair's median absolute difference.
    """
    reference, other = np.asarray(reference, float), np.asarray(other, float)
    call_ref, call_other = reference >= threshold, other >= threshold
    flipped = call_ref != call_other
    out = {"threshold": float(threshold), "strata": {}}
    for name, mask in strata.items():
        mask = np.asarray(mask, bool)
        k, n = int((flipped & mask).sum()), int(mask.sum())
        out["strata"][name] = {
            "n": n, "flips": k, "proportion": k / n if n else float("nan"), "ci95": binomial_ci(k, n),
            "lof_on_reference_only": int((flipped & mask & call_ref).sum()),
            "lof_on_other_only": int((flipped & mask & call_other).sum()),
        }
    median_diff = float(np.median(np.abs(reference - other)))
    distance = np.abs(reference - threshold) / median_diff if median_diff else np.full(len(reference), np.inf)
    out["median_abs_difference"] = median_diff
    out["flipped_distance_in_median_differences"] = (
        {"median": float(np.median(distance[flipped])), "max": float(distance[flipped].max())} if flipped.any() else None)
    out["reference_within_one_median_difference"] = int((distance <= 1).sum())
    return out
