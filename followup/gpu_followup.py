"""Amendment 5: score a BRCA1 subset under one numerical configuration. Runs inside the container.

  python gpu_followup.py --variant default|fp8off|fp32 --batch-size 1 --out /work/out/default-b1
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
import time
import traceback
from pathlib import Path

import torch

sys.path.insert(0, "/work/code/src")
from evo2ops import pins  # noqa: E402
from evo2ops.genome import read_first_fasta_record, read_variants, snv_windows  # noqa: E402
from evo2ops.workloads import fetch_verified, w0_forward_test  # noqa: E402

SUBSET_STRIDE = 8  # every 8th variant in table order


def load_model(variant: str, cache: Path):
    """Load evo2_7b with the requested numerics. Returns the model and the settings applied."""
    import yaml as real_yaml
    import evo2.models as evo2_models
    from evo2 import Evo2

    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    overrides = {}
    if variant in ("fp8off", "fp32"):
        # Evo 2 falls back to bfloat16 input projections for 7B models when it believes
        # Transformer Engine is absent. Transformer Engine's linear layers are still used, in bf16.
        evo2_models.HAS_TE = False
    if variant == "fp32":
        overrides = {"use_flash_attn": False, "attn_block_dtype": torch.float32, "mlp_dtype": torch.float32,
                     "hyena_block_dtype": torch.float32, "depthwise_dtype": torch.float32}

    class PatchedYaml:
        FullLoader = real_yaml.FullLoader

        @staticmethod
        def safe_load(text):
            config = real_yaml.safe_load(text)
            config.update(overrides)
            return config

    evo2_models.yaml = PatchedYaml
    pin = pins.WEIGHTS["evo2_7b"]
    path = fetch_verified(pin["repo_id"], pin["filename"], pin["revision"], pin["sha256"], cache)
    model = Evo2("evo2_7b", local_path=str(path))
    if variant == "fp32":
        model.model.float()
    config = model.model.config
    applied = {
        "variant": variant,
        "use_fp8_input_projections": bool(config.get("use_fp8_input_projections", False)),
        "use_flash_attn": bool(config.get("use_flash_attn", True)),
        "parameter_dtypes": sorted({str(p.dtype) for p in model.model.parameters()}),
        "tf32_matmul_allowed": torch.backends.cuda.matmul.allow_tf32,
    }
    return model, applied


def score(model, seqs: list[str], batch_size: int) -> tuple[list[float], float]:
    start = time.perf_counter()
    scores = model.score_sequences(seqs, batch_size=batch_size, reduce_method="mean")
    torch.cuda.synchronize()
    return [float(s) for s in scores], time.perf_counter() - start


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", choices=["default", "fp8off", "fp32"], required=True)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--data", type=Path, default=Path("/work/data"))
    parser.add_argument("--cache", type=Path, default=Path("/work/hf"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    receipt = {"started_utc": dt.datetime.now(dt.UTC).isoformat(), "batch_size": args.batch_size,
               "gpu_name": torch.cuda.get_device_name(0), "status": "running"}
    try:
        load_start = time.perf_counter()
        model, applied = load_model(args.variant, args.cache)
        receipt["applied"] = applied
        receipt["load_s"] = round(time.perf_counter() - load_start, 3)
        w0 = w0_forward_test(model, args.data / "prompts.csv")
        receipt["w0"] = {k: w0[k] for k in ("mean_loss", "mean_accuracy", "passed", "per_sequence_loss")}

        chromosome = read_first_fasta_record(args.data / "GRCh37.p13_chr17.fna.gz")
        variants = read_variants(args.data / "brca1_variants.tsv")[::SUBSET_STRIDE]
        ref_index, refs, var_seqs, ref_of = {}, [], [], []
        for row in variants:
            ref_seq, var_seq = snv_windows(chromosome, row["pos"], row["ref"], row["alt"], pins.BRCA1_WINDOW)
            if ref_seq not in ref_index:
                ref_index[ref_seq] = len(refs)
                refs.append(ref_seq)
            ref_of.append(ref_index[ref_seq])
            var_seqs.append(var_seq)
        torch.cuda.reset_peak_memory_stats()
        ref_scores, ref_s = score(model, refs, args.batch_size)
        var_scores, var_s = score(model, var_seqs, args.batch_size)
        with (args.out / "scores.tsv").open("w", newline="") as handle:
            writer = csv.writer(handle, delimiter="\t")
            writer.writerow(["id", "ref_score", "var_score", "delta"])
            for row, v, r in zip(variants, var_scores, ref_of):
                writer.writerow([row["id"], repr(ref_scores[r]), repr(v), repr(v - ref_scores[r])])
        windows = len(refs) + len(var_seqs)
        receipt.update({"variants": len(variants), "windows": windows, "scoring_s": round(ref_s + var_s, 3),
                        "windows_per_s": round(windows / (ref_s + var_s), 4),
                        "peak_memory_gib": round(torch.cuda.max_memory_allocated() / 1024 ** 3, 2),
                        "status": "completed"})
    except Exception:
        receipt["status"] = "failed"
        receipt["error"] = traceback.format_exc()
    finally:
        receipt["finished_utc"] = dt.datetime.now(dt.UTC).isoformat()
        (args.out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    main()
