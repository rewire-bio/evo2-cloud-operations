"""Exercise result assembly on synthetic platform outputs with the real file layout.

The fixture values are invented and only test the plumbing; they are not study results.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
from collect import assemble  # noqa: E402

CONFIG = {
    "mode": "full", "study_kind": "evo2_cloud_operations", "reference_platform": "P1",
    "bootstrap": {"n": 50, "seed": 7},
    "platforms": [{"id": "P1"}, {"id": "P2"}, {"id": "P3"}],
}


def fake_attempt(directory: Path, variants: pd.DataFrame, noise: float, seed: int) -> None:
    rng = np.random.default_rng(seed)
    directory.mkdir(parents=True)
    delta = -variants["lof"].to_numpy() * 1e-4 + rng.normal(0, 1e-4, len(variants))
    delta = delta + rng.normal(0, noise, len(variants))
    pd.DataFrame({"id": variants.index, "ref_score": -1.0, "var_score": -1.0 + delta, "delta": delta}).to_csv(
        directory / "w1_brca1_scores.tsv", sep="\t", index=False)
    pd.DataFrame({"id": variants.index[:200], "ref_score": -1.0, "var_score": -1.0, "delta": delta[:200]}).to_csv(
        directory / "w4_repeat_scores.tsv", sep="\t", index=False)
    labels = np.arange(122) % 2
    pd.DataFrame({"index": range(122), "gene_name": "G", "label": labels.astype(float),
                  "exon_probability": labels * 0.6 + 0.2, "embedding_norm": 1.0}).to_csv(
        directory / "w2_exon_probabilities.tsv", sep="\t", index=False)
    receipt = {
        "status": "completed", "environment": {"gpu_name": "fake"}, "timings_s": {"w1_s": 10.0},
        "results": {
            "w0": {"mean_loss": 0.3476, "mean_accuracy": 0.8634, "passed": True},
            "w1": {"sequences_per_second": 2.5, "peak_memory_allocated_bytes": 20 * 1024 ** 3},
            "w2": {"peak_memory_allocated_bytes": 18 * 1024 ** 3},
            "w3": [{"length": 8192, "status": "ok", "seconds": 1.0, "peak_memory_allocated_bytes": 2 ** 34}],
        },
    }
    (directory / "receipt-main.json").write_text(json.dumps(receipt))
    (directory / "events.jsonl").write_text(
        '{"event": "running", "utc": "2026-10-07T10:00:00Z"}\n{"event": "terminated", "utc": "2026-10-07T11:30:00Z"}\n')
    (directory / "instance.json").write_text('{"provider": "fake"}')


class CollectTests(unittest.TestCase):
    def test_assemble(self):
        variants = pd.read_csv(ROOT / "data/derived/brca1_variants.tsv", sep="\t").set_index("id")
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            fake_attempt(out / "platforms/P1/attempt-1", variants, 0.0, 1)
            fake_attempt(out / "platforms/P2/attempt-1", variants, 1e-6, 1)
            (out / "platforms/P3/attempt-1").mkdir(parents=True)  # a failed attempt with no receipt
            (out / "prices.json").write_text('{"P1": {"instance_usd_per_hour": 6.0, "storage_usd_per_hour": 0.0}}')
            assemble(CONFIG, out, ROOT)
            results = json.loads((out / "results.json").read_text())
            operations = json.loads((out / "operations.json").read_text())

        self.assertEqual(results["platforms"]["P3"], {"status": "unavailable"})
        self.assertGreater(results["platforms"]["P1"]["w1_auroc"]["all"], 0.5)
        self.assertEqual(results["platforms"]["P1"]["w2_exon_auroc"], 1.0)
        agreement = results["agreement_with_reference"]["P2"]
        self.assertLess(agreement["w1_max_abs_difference"], 1e-5)
        self.assertGreater(agreement["w1_spearman"], 0.99)
        self.assertEqual(results["same_platform_repeat"]["P1"]["max_abs_difference"], 0.0)
        cmp = results["brca1_evo2_vs_baselines"]["all"]
        self.assertEqual(set(cmp), {"evo2_7b", "cadd", "phylop", "consequence_rule"})
        self.assertEqual(operations["platforms"]["P1"]["cost"]["usd"], 9.0)
        self.assertEqual(operations["platforms"]["P1"]["cost"]["billed_seconds"], 5400)


if __name__ == "__main__":
    unittest.main()
