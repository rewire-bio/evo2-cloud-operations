"""Entry point inside the container: python -m evo2ops.run --workloads w0,w1,w3,w2 --out /work/out"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import platform
import subprocess
import traceback
from pathlib import Path

import torch

from . import workloads as W
from .telemetry import GpuSampler, Timings

ORDER = ["w0", "w1", "w3", "w2", "w4"]


def environment() -> dict:
    query = "name,driver_version,memory.total,compute_cap"
    smi = subprocess.run(["nvidia-smi", f"--query-gpu={query}", "--format=csv,noheader"],
                         capture_output=True, text=True).stdout.strip()
    try:
        import transformer_engine  # noqa: F401
        has_te = True
    except ImportError:
        has_te = False
    freeze = Path("/opt/evo2ops/pip-freeze.txt")
    return {
        "platform_id": os.environ.get("PLATFORM_ID"),
        "image": os.environ.get("IMAGE_REF"),
        "code_sha256": os.environ.get("CODE_SHA256"),
        "nvidia_smi": smi,
        "torch": torch.__version__,
        "torch_cuda": torch.version.cuda,
        "cudnn": torch.backends.cudnn.version(),
        "gpu_name": torch.cuda.get_device_name(0),
        "transformer_engine_installed": has_te,
        "python": platform.python_version(),
        "kernel": platform.release(),
        "pip_freeze_sha256": W.sha256_file(freeze) if freeze.exists() else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workloads", default="w0,w1,w3,w2")
    parser.add_argument("--data", type=Path, default=Path("/work/data"))
    parser.add_argument("--out", type=Path, default=Path("/work/out"))
    parser.add_argument("--cache", type=Path, default=Path("/work/hf"))
    args = parser.parse_args()
    requested = [w for w in ORDER if w in args.workloads.split(",")]
    args.out.mkdir(parents=True, exist_ok=True)
    tag = "repeat" if requested == ["w4"] else "main"
    timings = Timings()
    receipt = {"started_utc": dt.datetime.now(dt.UTC).isoformat(), "workloads": requested,
               "environment": environment(), "timings_s": timings, "results": {}, "status": "running"}

    with GpuSampler(args.out / f"gpu-samples-{tag}.csv"):
        try:
            model = None
            if {"w0", "w1", "w3", "w4"} & set(requested):
                model = W.load_evo2("evo2_7b", args.cache, timings)
            if "w0" in requested:
                with timings.measure("w0_s"):
                    receipt["results"]["w0"] = W.w0_forward_test(model, args.data / "prompts.csv")
                if not receipt["results"]["w0"]["passed"]:
                    raise RuntimeError("W0 correctness gate failed; later workloads skipped")
            if "w1" in requested:
                with timings.measure("w1_s"):
                    receipt["results"]["w1"] = W.w1_brca1(
                        model, args.data / "GRCh37.p13_chr17.fna.gz", args.data / "brca1_variants.tsv",
                        args.out / "w1_brca1_scores.tsv")
            if "w4" in requested:
                with timings.measure("w4_s"):
                    receipt["results"]["w4"] = W.w1_brca1(
                        model, args.data / "GRCh37.p13_chr17.fna.gz", args.data / "brca1_variants.tsv",
                        args.out / "w4_repeat_scores.tsv", limit=W.pins.REPEAT_VARIANTS)
            if "w3" in requested:
                with timings.measure("w3_s"):
                    receipt["results"]["w3"] = W.w3_memory_probe(model)
            if model is not None:
                W.unload(model)
                model = None
            if "w2" in requested:
                base = W.load_evo2("evo2_7b_base", args.cache, timings)
                classifier = W.load_exon_classifier(args.cache)
                with timings.measure("w2_s"):
                    receipt["results"]["w2"] = W.w2_exon(
                        base, classifier, args.data / "samplePositions.tsv", args.out / "w2_exon_probabilities.tsv")
            receipt["status"] = "completed"
        except Exception:
            receipt["status"] = "failed"
            receipt["error"] = traceback.format_exc()
            raise
        finally:
            receipt["finished_utc"] = dt.datetime.now(dt.UTC).isoformat()
            W.write_json(args.out / f"receipt-{tag}.json", receipt)


if __name__ == "__main__":
    main()
