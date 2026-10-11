"""Figure for the follow-up: how far apart two GPUs' scores are under each configuration.

  uv run --frozen python followup/plot_followup.py evidence/followup-20261011/followup-results.json out.png
"""
from __future__ import annotations

import json
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

BLUE, INK, INK_2, MUTED, GRID, SURFACE = "#2a78d6", "#0b0b0b", "#52514e", "#8a8984", "#e6e5e1", "#fcfcfb"

results = json.load(open(sys.argv[1]))["comparisons"]
rows = [
    ("H100 vs L40S, default", "default: H100 vs L40S"),
    ("L40 vs L40S, default\n(same architecture)", "same architecture: second Ada GPU vs L40S, default"),
    ("H100 vs L40S, FP8 off", "fp8off: H100 vs L40S"),
    ("H100 vs L40S, FP32", "fp32: H100 vs L40S"),
]
labels = [r[0] for r in rows][::-1]
values = [results[r[1]]["median_abs_difference"] for r in rows][::-1]

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": MUTED,
                     "xtick.color": INK_2, "ytick.color": INK_2, "axes.labelcolor": INK_2,
                     "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE})
fig, ax = plt.subplots(figsize=(7.2, 3.2))
bars = ax.barh(labels, values, color=[BLUE if "FP32" not in l else "#184f95" for l in labels], height=0.55)
ax.set_xscale("log")
ax.set_xlim(1e-7, 1e-3)
ax.grid(axis="x", color=GRID, linewidth=0.8)
ax.set_axisbelow(True)
for spine in ("top", "right"):
    ax.spines[spine].set_visible(False)
for bar, value in zip(bars, values):
    ax.text(value * 1.25, bar.get_y() + bar.get_height() / 2, f"{value:.1e}", va="center", fontsize=9, color=INK_2)
ax.set_xlabel("Median per-variant score difference between two GPUs (log scale)")
ax.set_title("Only FP32 brings two GPUs into agreement",
             loc="left", fontsize=10.5, fontweight="bold", color=INK)
fig.tight_layout()
fig.savefig(sys.argv[2], dpi=200)
