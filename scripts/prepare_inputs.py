"""Build the GPU job's input bundle from the verified raw data. Deterministic; no GPU needed.

Writes data/derived/brca1_variants.tsv: one row per Findlay et al. SNV with the columns the
GPU job needs (id, pos, ref, alt) and the label and baseline columns the analysis needs.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from evo2ops.genome import read_first_fasta_record, snv_windows  # noqa: E402
from evo2ops.pins import BRCA1_WINDOW  # noqa: E402

CODING = {"Missense", "Nonsense", "Synonymous"}


def brca1_table(xlsx: Path) -> pd.DataFrame:
    raw = pd.read_excel(xlsx, header=2)
    table = pd.DataFrame({
        "id": [f"chr17:{p}:{r}>{a}" for p, r, a in zip(raw["position (hg19)"], raw["reference"], raw["alt"])],
        "pos": raw["position (hg19)"].astype(int),
        "ref": raw["reference"],
        "alt": raw["alt"],
        "consequence": raw["consequence"],
        "func_class": raw["func.class"],
        "function_score": raw["function.score.mean"],
        "cadd": raw["CADD.score"],
        "phylop": raw["phyloP (mammalian)"],
    })
    table["lof"] = (table["func_class"] == "LOF").astype(int)
    table["region"] = ["coding" if c in CODING else "noncoding" for c in table["consequence"]]
    if table["id"].duplicated().any():
        raise ValueError("Duplicate variant identifiers")
    return table


def main() -> None:
    raw, derived = ROOT / "data/raw", ROOT / "data/derived"
    derived.mkdir(parents=True, exist_ok=True)
    table = brca1_table(raw / "41586_2018_461_MOESM3_ESM.xlsx")
    chromosome = read_first_fasta_record(raw / "GRCh37.p13_chr17.fna.gz")
    for row in table.itertuples():
        snv_windows(chromosome, row.pos, row.ref, row.alt, BRCA1_WINDOW)  # raises on a reference mismatch
    table.to_csv(derived / "brca1_variants.tsv", sep="\t", index=False)
    print(f"{len(table)} variants, {table['lof'].sum()} LOF; windows checked against GRCh37 chr17")


if __name__ == "__main__":
    main()
