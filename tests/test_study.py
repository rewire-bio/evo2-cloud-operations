"""Offline tests: sequence preparation, statistics and input integrity. No GPU needed."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from evo2ops.genome import read_first_fasta_record, snv_windows, synthetic_dna  # noqa: E402
from study.analysis import agreement, auroc, average_ranks, consequence_rule, grouped_bootstrap_auroc  # noqa: E402

CHR17 = ROOT / "data/raw/GRCh37.p13_chr17.fna.gz"


class WindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.chromosome = read_first_fasta_record(CHR17)

    def test_matches_arc_notebook_output(self):
        # Arc's BRCA1 notebook prints these slices for the first variant (chr17:41276135 T>G).
        ref_seq, var_seq = snv_windows(self.chromosome, 41276135, "T", "G", 8192)
        self.assertEqual(ref_seq[4082:4112], "TGTTCCAATGAACTTTAACACATTAGAAAA")
        self.assertEqual(var_seq[4082:4112], "TGTTCCAATGAACTGTAACACATTAGAAAA")
        self.assertEqual(len(ref_seq), 8192)

    def test_rejects_wrong_reference_base(self):
        with self.assertRaises(ValueError):
            snv_windows(self.chromosome, 41276135, "A", "G", 8192)

    def test_window_clipped_at_chromosome_start(self):
        ref_seq, var_seq = snv_windows("ACGTACGTAC", 2, "C", "T", 8)
        self.assertEqual(ref_seq, "ACGTA")
        self.assertEqual(var_seq, "ATGTA")

    def test_synthetic_dna_is_seeded(self):
        self.assertEqual(synthetic_dna(50, 1), synthetic_dna(50, 1))
        self.assertNotEqual(synthetic_dna(50, 1), synthetic_dna(50, 2))


class StatisticsTests(unittest.TestCase):
    def test_auroc_reference_cases(self):
        labels = np.array([0, 0, 1, 1])
        self.assertEqual(auroc(labels, np.array([1, 2, 3, 4])), 1.0)
        self.assertEqual(auroc(labels, np.array([4, 3, 2, 1])), 0.0)
        self.assertEqual(auroc(labels, np.array([1, 1, 1, 1])), 0.5)
        # Positives 3 and 1.5 against negatives 1 and 2: 3>1, 3>2, 1.5>1, 1.5<2, so 3 of 4 pairs.
        self.assertEqual(auroc(labels, np.array([1, 2, 3, 1.5])), 0.75)

    def test_auroc_matches_pairwise_definition(self):
        rng = np.random.default_rng(0)
        labels = rng.integers(0, 2, 300)
        scores = np.round(rng.normal(size=300) + labels, 1)  # rounding creates ties
        pos, neg = scores[labels == 1], scores[labels == 0]
        pairwise = ((pos[:, None] > neg[None, :]) + 0.5 * (pos[:, None] == neg[None, :])).mean()
        self.assertAlmostEqual(auroc(labels, scores), pairwise, places=12)

    def test_average_ranks_ties(self):
        np.testing.assert_array_equal(average_ranks(np.array([10, 20, 20, 30])), [1, 2.5, 2.5, 4])

    def test_grouped_bootstrap_is_reproducible_and_paired(self):
        rng = np.random.default_rng(1)
        labels = rng.integers(0, 2, 200)
        a = labels + rng.normal(size=200)
        groups = np.arange(200) // 3
        first = grouped_bootstrap_auroc(labels, {"a": a, "b": a.copy()}, groups, n=200)
        second = grouped_bootstrap_auroc(labels, {"a": a, "b": a.copy()}, groups, n=200)
        self.assertEqual(first, second)
        self.assertEqual(first["b"]["difference_vs_a_ci95"], [0.0, 0.0])
        low, high = first["a"]["ci95"]
        self.assertLess(low, first["a"]["auroc"])
        self.assertGreater(high, first["a"]["auroc"])

    def test_agreement_identical_and_shifted(self):
        x = np.linspace(-1, 1, 101)
        same = agreement(x, x.copy())
        self.assertEqual((same["max_abs_difference"], same["rank_moves_over_1pct"]), (0.0, 0))
        self.assertAlmostEqual(same["spearman"], 1.0)
        shifted = agreement(x, x + 0.5)
        self.assertAlmostEqual(shifted["max_abs_difference"], 0.5)
        self.assertEqual(shifted["rank_moves_over_1pct"], 0)

    def test_consequence_rule_order(self):
        np.testing.assert_array_equal(
            consequence_rule(["Nonsense", "Canonical splice", "Splice region", "Missense", "Synonymous"]),
            [3, 3, 2, 1, 0])


if __name__ == "__main__":
    unittest.main()
