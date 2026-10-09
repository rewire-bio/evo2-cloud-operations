"""Build figures, tables and LaTeX values from results/full. Offline and deterministic."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

# Reference light palette (dataviz skill): categorical slots 1 and 2, text and grid tokens.
BLUE, ORANGE = "#2a78d6", "#eb6834"
INK, INK_2, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#8a8984", "#e6e5e1", "#fcfcfb"
GPU_COLOUR = {"H100": BLUE, "L40S": ORANGE}

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": MUTED, "axes.labelcolor": INK_2,
    "xtick.color": INK_2, "ytick.color": INK_2, "axes.grid": True, "grid.color": GRID,
    "grid.linewidth": 0.8, "axes.spines.top": False, "axes.spines.right": False,
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.titlesize": 10.5, "axes.titleweight": "bold", "axes.titlecolor": INK,
})


def label(pid: str, ops: dict) -> str:
    inst = ops["platforms"][pid]["instance"]
    provider = {"runpod": "Runpod", "gcp": "Google Cloud", "aws": "AWS"}[inst["provider"]]
    return f"{provider} {gpu_short(ops['platforms'][pid]['gpu'])}"


def gpu_short(name: str) -> str:
    return "H100" if "H100" in name else "L40S" if "L40S" in name else name.replace("NVIDIA ", "")


def completed_attempt(root: Path, pid: str) -> Path:
    return root / "platforms" / pid / json.loads((root / "operations.json").read_text())["platforms"][pid]["attempt"]


def fig_agreement(results: dict, ops: dict, root: Path, out: Path) -> None:
    ref = results["reference_platform"]
    others = [p for p in results["agreement_with_reference"]]
    ref_scores = pd.read_csv(completed_attempt(root, ref) / "w1_brca1_scores.tsv", sep="\t").set_index("id")["delta"]
    fig, axes = plt.subplots(1, len(others), figsize=(4.6 * len(others), 4.3), squeeze=False)
    for ax, pid in zip(axes[0], others):
        other = pd.read_csv(completed_attempt(root, pid) / "w1_brca1_scores.tsv", sep="\t").set_index("id")["delta"]
        x, y = ref_scores.to_numpy() * 1e3, other.reindex(ref_scores.index).to_numpy() * 1e3
        lim = [min(x.min(), y.min()), max(x.max(), y.max())]
        ax.plot(lim, lim, color=MUTED, linewidth=1, linestyle="--", zorder=1)
        colour = GPU_COLOUR.get(gpu_short(ops["platforms"][pid]["gpu"]), BLUE)
        ax.scatter(x, y, s=6, color=colour, alpha=0.45, linewidths=0, zorder=2)
        a = results["agreement_with_reference"][pid]
        ax.set_title(f"{label(pid, ops)} against {label(ref, ops)}")
        ax.set_xlabel(f"{label(ref, ops)} score (x 10^-3)")
        ax.set_ylabel(f"{label(pid, ops)} score (x 10^-3)")
        ax.text(0.03, 0.97, f"Spearman {a['w1_spearman']:.3f}\nmedian |difference| {a['w1_median_abs_difference']:.1e}",
                transform=ax.transAxes, va="top", color=INK_2, fontsize=9)
    fig.tight_layout()
    fig.savefig(out / "fig-agreement.png", dpi=200)
    plt.close(fig)


def fig_memory(ops: dict, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(6.2, 3.8))
    seen = set()
    for pid, p in sorted(ops["platforms"].items()):
        if p.get("status") != "completed":
            continue
        gpu = gpu_short(p["gpu"])
        if gpu in seen:
            continue  # one line per GPU model; same-model platforms give the same memory
        seen.add(gpu)
        ok = [r for r in p["w3_memory_probe"] if r["status"] == "ok"]
        oom = [r for r in p["w3_memory_probe"] if r["status"] != "ok"]
        colour = GPU_COLOUR.get(gpu, BLUE)
        # The two GPUs allocate the same memory, so the second line is dashed to stay visible.
        ax.plot([r["length"] / 1000 for r in ok], [r["peak_memory_gib"] for r in ok], color=colour,
                linewidth=2, marker="o", markersize=7, markeredgecolor=SURFACE, markeredgewidth=2, label=gpu,
                linestyle="-" if not seen - {gpu} else (0, (4, 3)), zorder=2 + len(seen))
        for r in oom:
            ax.scatter([r["length"] / 1000], [r["peak_memory_gib"]], marker="X", s=90, color=colour,
                       edgecolor=SURFACE, linewidth=1.5, zorder=3)
            ax.annotate(f"{gpu}: out of memory", (r["length"] / 1000, r["peak_memory_gib"]),
                        xytext=(8, 6 if gpu == "H100" else -12), textcoords="offset points", color=INK_2, fontsize=9)
        total = 80 if gpu == "H100" else 48
        ax.axhline(total, color=colour, linewidth=1, linestyle=":")
        ax.text(8.5, total + 1.5, f"{gpu} memory, {total} GB", color=INK_2, fontsize=8.5, ha="left")
    ax.set_xscale("log", base=2)
    ax.set_xticks([8.192, 32.768, 131.072, 262.144], ["8 kb", "33 kb", "131 kb", "262 kb"])
    ax.set_ylabel("Peak GPU memory allocated (GiB)")
    ax.set_xlabel("Single sequence length (log scale)")
    ax.set_ylim(0, 90)
    ax.set_title("Evo 2 7B, one forward pass: memory against sequence length", loc="left")
    ax.legend(frameon=False, loc="lower right")
    ax.text(12, 4, "Both GPUs allocate the same memory up to 33 kb", color=INK_2, fontsize=8.5)
    fig.tight_layout()
    fig.savefig(out / "fig-memory.png", dpi=200)
    plt.close(fig)


def fig_auroc(results: dict, out: Path) -> None:
    names = {"evo2_7b": "Evo 2 7B (zero-shot)", "cadd": "CADD", "phylop": "phyloP (mammalian)",
             "consequence_rule": "Consequence rule"}
    regions = [("all", "All 3,893 SNVs"), ("coding", "Coding (2,768)"), ("noncoding", "Noncoding (1,125)")]
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.2), sharey=True)
    order = list(names)[::-1]
    for ax, (region, title) in zip(axes, regions):
        data = results["brca1_evo2_vs_baselines"][region]
        for i, key in enumerate(order):
            row = data[key]
            colour = BLUE if key == "evo2_7b" else MUTED
            ax.plot(row["ci95"], [i, i], color=colour, linewidth=2, solid_capstyle="round")
            ax.scatter([row["auroc"]], [i], color=colour, s=50, edgecolor=SURFACE, linewidth=2, zorder=3)
            ax.text(row["ci95"][1] + 0.008, i, f"{row['auroc']:.3f}", va="center", fontsize=8.5, color=INK_2)
        ax.set_yticks(range(len(order)), [names[k] for k in order])
        ax.set_xlim(0.65, 1.0)
        ax.set_title(title, loc="left")
        ax.set_xlabel("AUROC, LOF against FUNC/INT (95% CI)")
        ax.grid(axis="y", visible=False)
    fig.tight_layout()
    fig.savefig(out / "fig-auroc.png", dpi=200)
    plt.close(fig)


def operations_table(results: dict, ops: dict) -> pd.DataFrame:
    rows = []
    for pid, p in sorted(ops["platforms"].items()):
        if p.get("status") != "completed":
            continue
        cost, w1 = p["cost"], p["w1_sequences_per_second"]
        hourly = (cost["instance_usd_per_hour"] or 0) + (cost["storage_usd_per_hour"] or 0)
        variants_per_hour = w1 * 3600 * 3893 / 5219  # each variant needs its own window plus a shared reference
        rows.append({
            "platform": pid, "label": label(pid, ops), "gpu": p["gpu"],
            "region": p["instance"].get("zone"), "purchase": p["instance"].get("purchase_option"),
            "usd_per_hour": round(hourly, 2), "sequences_per_s": round(w1, 2),
            "usd_per_1000_variants": round(hourly / variants_per_hour * 1000, 3),
            "billed_minutes": round(cost["billed_seconds"] / 60, 1), "run_usd": cost["usd"],
            "w1_peak_gib": p["w1_peak_memory_gib"],
            "max_ok_length": max(r["length"] for r in p["w3_memory_probe"] if r["status"] == "ok"),
        })
    return pd.DataFrame(rows)


NAMES = {"P1": "POne", "P2": "PTwo", "P3": "PThree", "P4": "PFour", "P5": "PFive"}


def write_latex(results: dict, ops: dict, table: pd.DataFrame, out: Path) -> None:
    """Every number in the paper comes from here; main.tex only references these macros."""
    m = {}
    m["RefPlatform"] = results["reference_platform"]
    for row in table.itertuples():
        n = NAMES[row.platform]
        m[f"{n}Label"] = row.label
        m[f"{n}Gpu"] = row.gpu.replace("NVIDIA ", "")
        m[f"{n}Zone"] = row.region
        m[f"{n}Hourly"] = f"{row.usd_per_hour:.2f}"
        m[f"{n}Rate"] = f"{row.sequences_per_s:.2f}"
        m[f"{n}PerThousand"] = f"{row.usd_per_1000_variants:.2f}"
        m[f"{n}Minutes"] = f"{row.billed_minutes:.0f}"
        m[f"{n}Cost"] = f"{row.run_usd:.2f}"
        p = ops["platforms"][row.platform]
        r = results["platforms"][row.platform]
        m[f"{n}Loss"] = f"{r['w0_mean_loss']:.5f}"
        m[f"{n}AurocAll"] = f"{r['w1_auroc']['all']:.3f}"
        m[f"{n}AurocExon"] = f"{r['w2_exon_auroc']:.3f}"
        m[f"{n}PeakGib"] = f"{p['w1_peak_memory_gib']:.1f}"
        m[f"{n}SmiPeakGb"] = f"{p['nvidia_smi_peak_memory_mib'] / 1024:.1f}"
        probe = {q["length"]: q for q in p["w3_memory_probe"]}
        m[f"{n}ThirtyTwoGib"] = f"{probe[32768]['peak_memory_gib']:.1f}"
        m[f"{n}OomAt"] = f"{min((q['length'] for q in p['w3_memory_probe'] if q['status'] != 'ok'), default=0) // 1000}"
        m[f"{n}DockerInstall"] = str(p.get("docker_install_s") or 0)
        m[f"{n}DockerPull"] = str(p.get("docker_pull_s") or 0)
    for pid, a in results["agreement_with_reference"].items():
        n = NAMES[pid]
        m[f"{n}MaxDiff"] = f"{a['w1_max_abs_difference']:.1e}" if a["w1_max_abs_difference"] else "0"
        m[f"{n}MedianDiff"] = f"{a['w1_median_abs_difference']:.1e}" if a["w1_median_abs_difference"] else "0"
        m[f"{n}Spearman"] = f"{a['w1_spearman']:.3f}"
        m[f"{n}ExonDiff"] = f"{a['w2_max_abs_difference']:.3f}" if a["w2_max_abs_difference"] else "0"
    details = json.loads((ROOT_RESULTS[0] / "agreement-details.json").read_text())
    for pid, a in details["agreement_with_reference"].items():
        m[f"{NAMES[pid]}RankMoves"] = f"{a['w1']['rank_moves_over_1pct']:,}"
    for region, rows in results["brca1_evo2_vs_baselines"].items():
        key = region.capitalize()
        for name, row in rows.items():
            tag = {"evo2_7b": "Evo", "cadd": "Cadd", "phylop": "Phylop", "consequence_rule": "Rule"}[name]
            m[f"Auroc{tag}{key}"] = f"{row['auroc']:.3f}"
            m[f"Auroc{tag}{key}Lo"] = f"{row['ci95'][0]:.3f}"
            m[f"Auroc{tag}{key}Hi"] = f"{row['ci95'][1]:.3f}"
            if name != "evo2_7b":
                d, ci = row["difference_vs_evo2_7b"], row["difference_vs_evo2_7b_ci95"]
                m[f"Diff{tag}{key}"] = f"{d:+.3f}"
                m[f"Diff{tag}{key}Lo"] = f"{ci[0]:+.3f}"
                m[f"Diff{tag}{key}Hi"] = f"{ci[1]:+.3f}"
    m["TotalRunCost"] = f"{table['run_usd'].sum():.2f}"
    lines = ["% Generated by scripts/analyse.py from results; do not edit."]
    lines += [f"\\newcommand{{\\{k}}}{{{v}}}" for k, v in sorted(m.items())]
    (out / "macros.tex").write_text("\n".join(lines) + "\n")
    rows = [f"{r.label} & {gpu_short(r.gpu)} & {r.region} & {r.purchase} & {r.usd_per_hour:.2f} & "
            f"{r.sequences_per_s:.2f} & {r.usd_per_1000_variants:.2f} & {r.billed_minutes:.0f} & {r.run_usd:.2f} \\\\"
            for r in table.itertuples()]
    (out / "operations-table.tex").write_text("\n".join(rows) + "\n")


ROOT_RESULTS: list[Path] = []


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, default=ROOT / "results/full")
    args = parser.parse_args()
    ROOT_RESULTS.append(args.results)
    results = json.loads((args.results / "results.json").read_text())
    ops = json.loads((args.results / "operations.json").read_text())
    figures = ROOT / "paper/figures"
    figures.mkdir(parents=True, exist_ok=True)
    fig_agreement(results, ops, args.results, figures)
    fig_memory(ops, figures)
    fig_auroc(results, figures)
    table = operations_table(results, ops)
    generated = ROOT / "paper/generated"
    generated.mkdir(parents=True, exist_ok=True)
    table.to_csv(generated / "operations.csv", index=False)
    write_latex(results, ops, table, generated)
    print(table.to_string(index=False))


if __name__ == "__main__":
    main()
