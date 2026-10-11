"""Amendment 5: launch the follow-up pods in parallel, then compare configurations.

  uv run --frozen python followup/run_followup.py --output results/followup-<date>
  uv run --frozen python followup/run_followup.py --output results/followup-<date> --analyse-only
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from study.analysis import agreement, auroc  # noqa: E402

IMAGE = json.loads((ROOT / "configs/full.json").read_text())["image"]
RECORDED = ROOT / "evidence/runs/recorded-b75c67aa/platforms"
PODS = [
    {"id": "FH", "gpus": ["NVIDIA H100 80GB HBM3"], "variants": "default:1,fp8off:1,fp32:1,default:8"},
    {"id": "FL", "gpus": ["NVIDIA L40S"], "variants": "default:1,fp8off:1,fp32:1"},
    {"id": "FA", "gpus": ["NVIDIA L40", "NVIDIA RTX 6000 Ada Generation"], "variants": "default:1,fp8off:1"},
]
DATA = {"prompts.csv": "data/raw/prompts.csv", "GRCh37.p13_chr17.fna.gz": "data/raw/GRCh37.p13_chr17.fna.gz",
        "brca1_variants.tsv": "data/derived/brca1_variants.tsv"}


def build_bundle(bundle: Path) -> str:
    if subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT, text=True).strip():
        raise SystemExit("Commit first: follow-up runs use the committed revision only.")
    bundle.mkdir(parents=True)
    subprocess.run(["git", "archive", "--format=tar.gz", "-o", str(bundle / "code.tar.gz"), "HEAD", "src", "followup"],
                   cwd=ROOT, check=True)
    (bundle / "data").mkdir()
    for name, source in DATA.items():
        shutil.copy2(ROOT / source, bundle / "data" / name)
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def launch(pod: dict, bundle: Path, output: Path) -> dict:
    out = output / pod["id"]
    env = {**os.environ, "PLATFORM_ID": pod["id"], "GPU_TYPE_IDS": json.dumps(pod["gpus"]),
           "VARIANTS": pod["variants"], "IMAGE_REF": IMAGE, "BUNDLE": str(bundle), "OUT": str(out)}
    out.mkdir(parents=True, exist_ok=True)
    with (out / "launcher.log").open("w") as log:
        code = subprocess.run(["bash", str(ROOT / "followup/launch-runpod.sh")], env=env,
                              stdout=log, stderr=subprocess.STDOUT).returncode
    return {"pod": pod["id"], "exit_code": code}


def scores(path: Path) -> pd.Series:
    return pd.read_csv(path, sep="\t").set_index("id")["delta"]


def analyse(output: Path) -> dict:
    variants = pd.read_csv(ROOT / "data/derived/brca1_variants.tsv", sep="\t").set_index("id")
    configs = {}
    for receipt in sorted(output.glob("F*/*/receipt.json")):
        r = json.loads(receipt.read_text())
        key = f"{receipt.parent.parent.name}/{receipt.parent.name}"
        configs[key] = {"receipt": r, "scores": scores(receipt.parent / "scores.tsv") if r["status"] == "completed" else None}
    result = {"configurations": {}, "controls": {}, "comparisons": {}}
    for key, c in configs.items():
        r = c["receipt"]
        entry = {k: r.get(k) for k in ("status", "gpu_name", "applied", "windows_per_s", "peak_memory_gib", "load_s")}
        entry["w0"] = r.get("w0")
        if c["scores"] is not None:
            s = c["scores"]
            entry["subset_auroc"] = auroc(variants.loc[s.index, "lof"].to_numpy(), -s.to_numpy())
        else:
            entry["error_tail"] = (r.get("error") or "")[-800:]
        result["configurations"][key] = entry

    def pair(a: str, b: str):
        if configs.get(a, {}).get("scores") is None or configs.get(b, {}).get("scores") is None:
            return None
        x, y = configs[a]["scores"], configs[b]["scores"].reindex(configs[a]["scores"].index)
        return agreement(x.to_numpy(), y.to_numpy())

    for pod, platform, attempt in (("FH", "P2", "attempt-1"), ("FL", "P5", "attempt-2")):
        key = f"{pod}/default-b1"
        if configs.get(key, {}).get("scores") is not None:
            recorded = scores(RECORDED / platform / attempt / "w1_brca1_scores.tsv")
            s = configs[key]["scores"]
            result["controls"][key] = float((s - recorded.reindex(s.index)).abs().max())
    alt = "FA/default-b1"
    pairs = {
        "default: H100 vs L40S": ("FH/default-b1", "FL/default-b1"),
        "fp8off: H100 vs L40S": ("FH/fp8off-b1", "FL/fp8off-b1"),
        "fp32: H100 vs L40S": ("FH/fp32-b1", "FL/fp32-b1"),
        "H100: fp8off vs default": ("FH/default-b1", "FH/fp8off-b1"),
        "L40S: fp8off vs default": ("FL/default-b1", "FL/fp8off-b1"),
        "H100: fp32 vs default": ("FH/default-b1", "FH/fp32-b1"),
        "L40S: fp32 vs default": ("FL/default-b1", "FL/fp32-b1"),
        "same architecture: second Ada GPU vs L40S, default": (alt, "FL/default-b1"),
        "same architecture: second Ada GPU vs L40S, fp8off": ("FA/fp8off-b1", "FL/fp8off-b1"),
        "H100: batch 8 vs batch 1": ("FH/default-b1", "FH/default-b8"),
    }
    for label, (a, b) in pairs.items():
        result["comparisons"][label] = pair(a, b)
    d, f = result["comparisons"].get("default: H100 vs L40S"), result["comparisons"].get("fp8off: H100 vs L40S")
    if d and f:
        ratio = f["median_abs_difference"] / d["median_abs_difference"] if d["median_abs_difference"] else None
        result["q1_fp8"] = {"median_ratio_fp8off_to_default": ratio,
                            "verdict": "no evidence" if ratio is None or ratio >= 1 else
                            ("main cause" if ratio < 0.1 else "a cause")}
    (output / "followup-results.json").write_text(json.dumps(result, indent=2, default=float) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--analyse-only", action="store_true")
    args = parser.parse_args()
    if not args.analyse_only:
        args.output.mkdir(parents=True, exist_ok=False)
        revision = build_bundle(args.output / "bundle")
        (args.output / "provenance.json").write_text(json.dumps({"git_revision": revision, "image": IMAGE,
            "code_sha256": hashlib.sha256((args.output / "bundle/code.tar.gz").read_bytes()).hexdigest()}, indent=2))
        with ThreadPoolExecutor(len(PODS)) as pool:
            outcomes = list(pool.map(lambda p: launch(p, args.output / "bundle", args.output), PODS))
        (args.output / "launch-outcomes.json").write_text(json.dumps(outcomes, indent=2) + "\n")
    print(json.dumps(analyse(args.output), indent=2, default=float))


if __name__ == "__main__":
    main()
