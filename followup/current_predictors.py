"""Amendment 7: current CADD, SpliceAI and REVEL against Evo 2 7B on the BRCA1 variants. No GPU.

  uv run --frozen python followup/current_predictors.py --fetch   # needs tabix, curl and unzip; then analyses
  uv run --frozen python followup/current_predictors.py           # analyse already fetched extracts

Per-variant values from these tables stay in data/raw/current-predictors (not committed).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from study.analysis import grouped_bootstrap_auroc  # noqa: E402

RAW = ROOT / "data/raw/current-predictors"
OUTPUT = ROOT / "evidence/current-predictors"
RUN = ROOT / "evidence/runs/recorded-b75c67aa"
CADD = "https://kircherlab.bihealth.org/download/CADD/v1.7/GRCh37"
REVEL_URL = "https://rothsj06.dmz.hpc.mssm.edu/revel-v1.3_all_chromosomes.zip"
REGION = ("17", 41197000, 41277000)
SPLICEAI = ["SpliceAI-acc-gain", "SpliceAI-acc-loss", "SpliceAI-don-gain", "SpliceAI-don-loss"]
BOOTSTRAP = {"n": 2000, "seed": 7}  # as configs/full.json


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def tabix(url: str, columns: list[str], out: Path) -> None:
    """Fetch the region by remote tabix query, keeping only the named columns."""
    chrom, start, end = REGION
    header = subprocess.check_output(["tabix", "-H", url], cwd=RAW, text=True).splitlines()[-1].lstrip("#").split("\t")
    keep = [header.index(c) for c in columns]
    body = subprocess.check_output(["tabix", url, f"{chrom}:{start}-{end}"], cwd=RAW, text=True)
    with out.open("w") as handle:
        handle.write("\t".join(columns) + "\n")
        for line in body.splitlines():
            fields = line.split("\t")
            handle.write("\t".join(fields[i] for i in keep) + "\n")


def published_md5(url: str) -> str:
    return subprocess.check_output(["curl", "-sSfL", url + ".md5"], text=True).split()[0]


def fetch() -> dict:
    RAW.mkdir(parents=True, exist_ok=True)
    sources = {"region_grch37": f"{REGION[0]}:{REGION[1]}-{REGION[2]}", "tables": {}}
    for name, filename, columns in (
        ("cadd_v1.7", "whole_genome_SNVs.tsv.gz", ["Chrom", "Pos", "Ref", "Alt", "RawScore", "PHRED"]),
        ("spliceai_via_cadd_v1.7", "whole_genome_SNVs_inclAnno.tsv.gz", ["Chrom", "Pos", "Ref", "Alt", "GeneName", *SPLICEAI]),
    ):
        url = f"{CADD}/{filename}"
        out = RAW / f"{name}.tsv"
        tabix(url, columns, out)
        index = RAW / f"{filename}.tbi"
        sources["tables"][name] = {
            "url": url, "published_md5": published_md5(url), "index_published_md5": published_md5(url + ".tbi"),
            "index_md5_matches": hashlib.md5(index.read_bytes()).hexdigest() == published_md5(url + ".tbi"),
            "extract": out.name, "extract_sha256": sha256(out)}
    archive = RAW / "revel-v1.3_all_chromosomes.zip"
    if not archive.exists():
        subprocess.run(["curl", "-sSfL", "--retry", "3", "-o", str(archive), REVEL_URL], check=True)
    out = RAW / "revel_v1.3.tsv"
    with zipfile.ZipFile(archive) as z, out.open("w", newline="") as handle:
        (member,) = z.namelist()  # one CSV, revel_with_transcript_ids
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["Chrom", "Pos", "Ref", "Alt", "REVEL"])
        with z.open(member) as raw:
            lines = io.TextIOWrapper(raw)
            columns = next(lines).strip().split(",")
            prefix = REGION[0] + ","
            for line in lines:
                if not line.startswith(prefix):
                    continue
                row = dict(zip(columns, line.strip().split(",")))
                if row["hg19_pos"] != "." and REGION[1] <= int(row["hg19_pos"]) <= REGION[2]:
                    writer.writerow([row["chr"], row["hg19_pos"], row["ref"], row["alt"], row["REVEL"]])
    sources["tables"]["revel_v1.3"] = {"url": REVEL_URL, "archive_sha256": sha256(archive), "member": member,
                                       "extract": out.name, "extract_sha256": sha256(out)}
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "sources.json").write_text(json.dumps(sources, indent=2) + "\n")
    return sources


def keyed(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, sep="\t", dtype={"Chrom": str}, na_values=["NA", "."])
    df["id"] = "chr" + df["Chrom"] + ":" + df["Pos"].astype(str) + ":" + df["Ref"] + ">" + df["Alt"]
    return df


def load_scores(variants: pd.DataFrame) -> pd.DataFrame:
    sources = json.loads((OUTPUT / "sources.json").read_text())
    for name, entry in sources["tables"].items():
        if sha256(RAW / entry["extract"]) != entry["extract_sha256"]:
            raise SystemExit(f"{entry['extract']} does not match sources.json; run with --fetch")
    cadd = keyed(RAW / "cadd_v1.7.tsv").drop_duplicates("id").set_index("id")
    splice = keyed(RAW / "spliceai_via_cadd_v1.7.tsv")
    splice = splice[splice["GeneName"] == "BRCA1"]
    splice = splice.assign(score=splice[SPLICEAI].max(axis=1)).groupby("id")["score"].max()
    revel = keyed(RAW / "revel_v1.3.tsv").groupby("id")["REVEL"].max()
    attempt = json.loads((RUN / "operations.json").read_text())["platforms"]["P2"]["attempt"]
    evo2 = -pd.read_csv(RUN / "platforms/P2" / attempt / "w1_brca1_scores.tsv", sep="\t").set_index("id")["delta"]
    return pd.DataFrame({
        "evo2_7b": evo2.reindex(variants.index), "cadd_v1.3": variants["cadd"],
        "cadd_v1.7": cadd["RawScore"].reindex(variants.index), "cadd_v1.7_phred": cadd["PHRED"].reindex(variants.index),
        "spliceai": splice.reindex(variants.index), "revel": revel.reindex(variants.index)})


def compare(variants: pd.DataFrame, scores: pd.DataFrame, mask: np.ndarray, names: list[str]) -> dict:
    m = mask & scores[names].notna().all(axis=1).to_numpy()
    out = grouped_bootstrap_auroc(variants["lof"].to_numpy()[m], {k: scores[k].to_numpy()[m] for k in names},
                                  variants["pos"].to_numpy()[m], **BOOTSTRAP)
    for k in names[1:]:
        low, high = out[k]["difference_vs_evo2_7b_ci95"]
        out[k]["evo2_advantage"] = "holds" if low > 0 else "reverses" if high < 0 else "not detected"
    return {"n": int(m.sum()), "lof": int(variants["lof"].to_numpy()[m].sum()), "auroc": out}


def analyse() -> dict:
    variants = pd.read_csv(ROOT / "data/derived/brca1_variants.tsv", sep="\t").set_index("id")
    scores = load_scores(variants)
    regions = {"all": np.ones(len(variants), bool), "coding": (variants["region"] == "coding").to_numpy(),
               "noncoding": (variants["region"] == "noncoding").to_numpy()}
    missense = (variants["consequence"] == "Missense").to_numpy()
    result = {"coverage_missing": {}, "main": {}, "main_phred": {}, "missense": None}
    for k in ("cadd_v1.7", "spliceai", "revel"):
        missing = scores[k].isna().to_numpy()
        result["coverage_missing"][k] = {r: int((missing & m).sum()) for r, m in {**regions, "missense": missense}.items()}
    for region, m in regions.items():
        result["main"][region] = compare(variants, scores, m, ["evo2_7b", "cadd_v1.3", "cadd_v1.7", "spliceai"])
        result["main_phred"][region] = compare(variants, scores, m, ["evo2_7b", "cadd_v1.7_phred"])
    result["missense"] = compare(variants, scores, missense, ["evo2_7b", "cadd_v1.3", "cadd_v1.7", "revel"])
    (OUTPUT / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fetch", action="store_true")
    args = parser.parse_args()
    if args.fetch:
        fetch()
    print(json.dumps(analyse(), indent=2))


if __name__ == "__main__":
    main()
