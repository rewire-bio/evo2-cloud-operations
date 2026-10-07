"""Sequence preparation shared by the GPU job and the local tests. Standard library only."""
from __future__ import annotations

import csv
import gzip
import random
from pathlib import Path


def read_first_fasta_record(path: Path) -> str:
    """Return the first record of a (gzipped) FASTA file as one string, case preserved."""
    opener = gzip.open if path.suffix == ".gz" else open
    parts: list[str] = []
    with opener(path, "rt") as handle:
        for line in handle:
            if line.startswith(">"):
                if parts:
                    break
                continue
            parts.append(line.strip())
    return "".join(parts)


def snv_windows(chromosome: str, pos: int, ref: str, alt: str, window: int) -> tuple[str, str]:
    """Reference and variant windows around a 1-based SNV position.

    Matches Arc's BRCA1 notebook: the window starts window//2 bases before the
    variant and the variant sits at index window//2 (or at pos-1 near the start).
    """
    p = pos - 1
    start = max(0, p - window // 2)
    end = min(len(chromosome), p + window // 2)
    ref_seq = chromosome[start:end]
    offset = min(window // 2, p)
    if ref_seq[offset].upper() != ref.upper():
        raise ValueError(f"Reference mismatch at {pos}: genome has {ref_seq[offset]}, table has {ref}")
    var_seq = ref_seq[:offset] + alt + ref_seq[offset + 1:]
    return ref_seq, var_seq


def read_variants(path: Path) -> list[dict]:
    """Read the prepared BRCA1 variant table (id, pos, ref, alt)."""
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    for row in rows:
        row["pos"] = int(row["pos"])
    return rows


def read_exon_positions(path: Path) -> list[dict]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def synthetic_dna(length: int, seed: int) -> str:
    rng = random.Random(seed)
    return "".join(rng.choice("ACGT") for _ in range(length))
