"""Assemble results.json (scientific outputs) and operations.json (timings, memory, cost)
from the files each platform copied back. Offline and deterministic."""
from __future__ import annotations

import csv
import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from study.analysis import agreement, auroc, consequence_rule, grouped_bootstrap_auroc  # noqa: E402

GIB = 1024 ** 3


def read_json(path: Path):
    return json.loads(path.read_text()) if path.exists() else None


def completed_attempt(platform_dir: Path) -> Path | None:
    """The last attempt whose main receipt completed, if any."""
    for attempt in sorted(platform_dir.glob("attempt-*"), reverse=True):
        receipt = read_json(attempt / "receipt-main.json")
        if receipt and receipt.get("status") == "completed":
            return attempt
    return None


def utc(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def events(attempt: Path) -> dict:
    path = attempt / "events.jsonl"
    if not path.exists():
        return {}
    return {row["event"]: row["utc"] for row in map(json.loads, path.read_text().splitlines())}


def peak_smi_memory_mib(attempt: Path) -> float | None:
    peaks = []
    for path in attempt.glob("gpu-samples-*.csv"):
        with path.open() as handle:
            rows = [r for r in csv.reader(handle) if r and not r[0].startswith("timestamp")]
        peaks += [float(r[1]) for r in rows if r[1].strip().replace(".", "").isdigit()]
    return max(peaks) if peaks else None


def w1_scores(attempt: Path, name: str = "w1_brca1_scores.tsv") -> pd.Series:
    table = pd.read_csv(attempt / name, sep="\t")
    return table.set_index("id")["delta"]


def w2_probabilities(attempt: Path) -> pd.DataFrame:
    return pd.read_csv(attempt / "w2_exon_probabilities.tsv", sep="\t")


def platform_costs(instance: dict, ev: dict, prices: dict, platform_id: str) -> dict:
    # Runpod bills from pod creation (including the image pull); EC2 and GCE from RUNNING.
    start = ev.get("pod_created") or ev.get("running")
    if start is None or "terminated" not in ev:
        return {"billed_seconds": None, "usd": None}
    seconds = (utc(ev["terminated"]) - utc(start)).total_seconds()
    price = prices.get(platform_id, {})
    hourly = price.get("instance_usd_per_hour")
    storage = price.get("storage_usd_per_hour", 0.0)
    usd = None if hourly is None else round(seconds / 3600 * (hourly + storage), 2)
    return {"billed_seconds": round(seconds), "instance_usd_per_hour": hourly,
            "storage_usd_per_hour": storage, "usd": usd, "price_source": price.get("source")}


def assemble(config: dict, output: Path, root: Path) -> None:
    variants = pd.read_csv(root / "data/derived/brca1_variants.tsv", sep="\t").set_index("id")
    prices = read_json(output / "prices.json") or {}
    boot = config["bootstrap"]
    results = {"schema_version": 1, "mode": config["mode"], "study_kind": config["study_kind"],
               "platforms": {}, "agreement_with_reference": {}, "same_platform_repeat": {}}
    operations, details = {"platforms": {}}, {"agreement_with_reference": {}, "same_platform_repeat": {}}
    attempts = {}

    for platform in config["platforms"]:
        pid = platform["id"]
        attempt = completed_attempt(output / "platforms" / pid)
        if attempt is None:
            results["platforms"][pid] = {"status": "unavailable"}
            operations["platforms"][pid] = {"status": "unavailable",
                                            "attempts": len(list((output / "platforms" / pid).glob("attempt-*")))}
            continue
        attempts[pid] = attempt
        receipt = read_json(attempt / "receipt-main.json")
        repeat = read_json(attempt / "receipt-repeat.json") or {}
        delta = w1_scores(attempt).reindex(variants.index)
        exon = w2_probabilities(attempt)
        regions = {"all": slice(None), "coding": variants["region"] == "coding",
                   "noncoding": variants["region"] == "noncoding"}
        results["platforms"][pid] = {
            "status": "completed",
            "w0_mean_loss": receipt["results"]["w0"]["mean_loss"],
            "w0_mean_accuracy": receipt["results"]["w0"]["mean_accuracy"],
            "w0_passed": int(receipt["results"]["w0"]["passed"]),
            "w1_auroc": {k: auroc(variants["lof"][m], -delta[m]) for k, m in regions.items()},
            "w2_exon_auroc": auroc(exon["label"].astype(float).astype(int), exon["exon_probability"]),
        }
        ev = events(attempt)
        instance = read_json(attempt / "instance.json") or {}
        host = read_json(attempt / "host-timings.json") or {}
        w1 = receipt["results"]["w1"]
        operations["platforms"][pid] = {
            "status": "completed",
            "attempt": attempt.name,
            "instance": instance,
            "gpu": receipt["environment"]["gpu_name"],
            "environment": receipt["environment"],
            "events_utc": ev,
            "docker_pull_s": host.get("docker_pull_s"),
            "timings_s": {**receipt["timings_s"], **{f"repeat_{k}": v for k, v in repeat.get("timings_s", {}).items()}},
            "w1_sequences_per_second": w1["sequences_per_second"],
            "w1_peak_memory_gib": round(w1["peak_memory_allocated_bytes"] / GIB, 2),
            "w2_peak_memory_gib": round(receipt["results"]["w2"]["peak_memory_allocated_bytes"] / GIB, 2),
            "w3_memory_probe": [{**r, "peak_memory_gib": round(r["peak_memory_allocated_bytes"] / GIB, 2)}
                                for r in receipt["results"]["w3"]],
            "nvidia_smi_peak_memory_mib": peak_smi_memory_mib(attempt),
            "cost": platform_costs(instance, ev, prices, pid),
        }

    reference_id = next((p for p in (config["reference_platform"], config.get("reference_fallback")) if p in attempts),
                        next(iter(attempts), None))
    results["reference_platform"] = reference_id
    if reference_id:
        ref = attempts[reference_id]
        ref_delta = w1_scores(ref).reindex(variants.index)
        groups = variants["pos"].to_numpy()
        labels = variants["lof"].to_numpy()
        comparisons = {}
        for region in ("all", "coding", "noncoding"):
            m = np.ones(len(variants), bool) if region == "all" else (variants["region"] == region).to_numpy()
            comparisons[region] = grouped_bootstrap_auroc(
                labels[m],
                {"evo2_7b": -ref_delta.to_numpy()[m], "cadd": variants["cadd"].to_numpy()[m],
                 "phylop": variants["phylop"].to_numpy()[m],
                 "consequence_rule": consequence_rule(variants["consequence"])[m]},
                groups[m], n=boot["n"], seed=boot["seed"])
        results["brca1_evo2_vs_baselines"] = comparisons
        ref_exon = w2_probabilities(ref)["exon_probability"].to_numpy()
        for pid, attempt in attempts.items():
            if pid != reference_id:
                other = w1_scores(attempt).reindex(variants.index)
                full = agreement(ref_delta.to_numpy(), other.to_numpy())
                exon_diff = float(np.max(np.abs(ref_exon - w2_probabilities(attempt)["exon_probability"].to_numpy())))
                details["agreement_with_reference"][pid] = {"w1": full, "w2_max_abs_difference": exon_diff}
                results["agreement_with_reference"][pid] = {
                    "w1_max_abs_difference": full["max_abs_difference"],
                    "w1_median_abs_difference": full["median_abs_difference"],
                    "w1_spearman": full["spearman"],
                    "w2_max_abs_difference": exon_diff,
                }
    for pid, attempt in attempts.items():
        if (attempt / "w4_repeat_scores.tsv").exists():
            first = w1_scores(attempt)
            again = w1_scores(attempt, "w4_repeat_scores.tsv")
            rep = agreement(first.reindex(again.index).to_numpy(), again.to_numpy())
            details["same_platform_repeat"][pid] = rep
            results["same_platform_repeat"][pid] = {"max_abs_difference": rep["max_abs_difference"],
                                                    "spearman": rep["spearman"]}

    for name, value in (("results.json", results), ("operations.json", operations), ("agreement-details.json", details)):
        (output / name).write_text(json.dumps(value, indent=2, sort_keys=True, default=float) + "\n")
