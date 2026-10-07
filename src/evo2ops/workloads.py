"""The Evo 2 workloads W0 to W4. Runs inside the container on a CUDA GPU."""
from __future__ import annotations

import csv
import hashlib
import json
import time
from pathlib import Path

import torch
import torch.nn.functional as F

from . import pins
from .genome import read_exon_positions, read_first_fasta_record, read_variants, snv_windows, synthetic_dna


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(16 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def fetch_verified(repo_id: str, filename: str, revision: str, sha256: str, cache_dir: Path) -> Path:
    """Download one file at a pinned revision and refuse to return it unless the hash matches.

    Arc's checkpoints are loaded with torch.load (pickle), so an unverified file could run code.
    """
    from huggingface_hub import hf_hub_download

    path = Path(hf_hub_download(repo_id=repo_id, filename=filename, revision=revision, cache_dir=str(cache_dir)))
    actual = sha256_file(path)
    if actual != sha256:
        raise RuntimeError(f"SHA-256 mismatch for {repo_id}/{filename}: expected {sha256}, got {actual}")
    return path


def load_evo2(name: str, cache_dir: Path, timings: dict):
    from evo2 import Evo2

    pin = pins.WEIGHTS[name]
    start = time.perf_counter()
    path = fetch_verified(pin["repo_id"], pin["filename"], pin["revision"], pin["sha256"], cache_dir)
    timings[f"{name}_download_and_verify_s"] = round(time.perf_counter() - start, 3)
    start = time.perf_counter()
    model = Evo2(name, local_path=str(path))
    torch.cuda.synchronize()
    timings[f"{name}_load_s"] = round(time.perf_counter() - start, 3)
    return model


def unload(model) -> None:
    del model
    torch.cuda.empty_cache()


def w0_forward_test(model, prompts_csv: Path) -> dict:
    """Arc's forward-pass check (evo2/test/test_evo2.py), reimplemented without its CLI."""
    with prompts_csv.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        next(reader)
        sequences = [row[0] for row in reader]
    torch.manual_seed(1)
    torch.cuda.manual_seed(1)
    losses, accuracies = [], []
    for seq in sequences:
        input_ids = torch.tensor(model.tokenizer.tokenize(seq), dtype=int).to("cuda:0")
        with torch.inference_mode():
            logits, _ = model.model.forward(input_ids.unsqueeze(0))
        target, pred = input_ids[1:], logits[0, :-1, :]
        losses.append(F.cross_entropy(pred, target.long()).item())
        accuracies.append((target == torch.argmax(pred, dim=-1)).float().mean().item())
    mean_loss = sum(losses) / len(losses)
    return {
        "per_sequence_loss": losses,
        "per_sequence_accuracy": accuracies,
        "mean_loss": mean_loss,
        "mean_accuracy": sum(accuracies) / len(accuracies),
        "expected_loss": pins.W0_EXPECTED_LOSS,
        "passed": abs(mean_loss - pins.W0_EXPECTED_LOSS) < pins.W0_TOLERANCE,
    }


def _score_all(model, seqs: list[str], label: str) -> tuple[list[float], float]:
    """Score sequences one at a time (batch size 1, as in Arc's notebook) with progress output."""
    scores: list[float] = []
    start = time.perf_counter()
    for i, seq in enumerate(seqs):
        scores.extend(model.score_sequences([seq], batch_size=1, reduce_method="mean"))
        if (i + 1) % 250 == 0:
            rate = (i + 1) / (time.perf_counter() - start)
            print(f"[{label}] {i + 1}/{len(seqs)} sequences, {rate:.2f}/s", flush=True)
    torch.cuda.synchronize()
    return [float(s) for s in scores], time.perf_counter() - start


def w1_brca1(model, chr17_fasta: Path, variants_tsv: Path, out_tsv: Path, limit: int | None = None) -> dict:
    """Paired reference/variant windows; delta = variant minus reference mean log-likelihood."""
    chromosome = read_first_fasta_record(chr17_fasta)
    variants = read_variants(variants_tsv)[:limit]
    ref_index: dict[str, int] = {}
    refs, var_seqs, ref_of_variant = [], [], []
    for row in variants:
        ref_seq, var_seq = snv_windows(chromosome, row["pos"], row["ref"], row["alt"], pins.BRCA1_WINDOW)
        if ref_seq not in ref_index:
            ref_index[ref_seq] = len(refs)
            refs.append(ref_seq)
        ref_of_variant.append(ref_index[ref_seq])
        var_seqs.append(var_seq)
    torch.cuda.reset_peak_memory_stats()
    ref_scores, ref_seconds = _score_all(model, refs, "reference windows")
    var_scores, var_seconds = _score_all(model, var_seqs, "variant windows")
    with out_tsv.open("w", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["id", "ref_score", "var_score", "delta"])
        for row, var_score, ref_i in zip(variants, var_scores, ref_of_variant):
            ref_score = ref_scores[ref_i]
            writer.writerow([row["id"], repr(ref_score), repr(var_score), repr(var_score - ref_score)])
    sequences = len(refs) + len(var_seqs)
    return {
        "variants": len(variants),
        "reference_windows": len(refs),
        "sequences_scored": sequences,
        "scoring_seconds": round(ref_seconds + var_seconds, 3),
        "sequences_per_second": round(sequences / (ref_seconds + var_seconds), 4),
        "peak_memory_allocated_bytes": torch.cuda.max_memory_allocated(),
    }


class ExonClassifier(torch.nn.Module):
    """The pinned classifier's architecture, rebuilt locally so no remote code is executed."""

    def __init__(self, embedding_dim: int, hidden_dim: int):
        super().__init__()
        self.fc_layers = torch.nn.Sequential(
            torch.nn.Linear(embedding_dim, hidden_dim), torch.nn.ReLU(), torch.nn.Linear(hidden_dim, 1)
        )

    def forward(self, x):
        return torch.sigmoid(self.fc_layers(x))


def load_exon_classifier(cache_dir: Path) -> ExonClassifier:
    from safetensors.torch import load_file

    pin = pins.EXON_CLASSIFIER
    path = fetch_verified(pin["repo_id"], pin["filename"], pin["revision"], pin["sha256"], cache_dir)
    model = ExonClassifier(pin["embedding_dim"], pin["hidden_dim"])
    model.load_state_dict(load_file(str(path)), strict=True)
    return model.eval().to("cuda:0")


def _final_token_embedding(model, sequence: str, layer: str) -> torch.Tensor:
    """As in Arc's exon notebook: final-token embedding from one layer, as float32."""
    input_ids = torch.tensor(model.tokenizer.tokenize(sequence), dtype=torch.int).unsqueeze(0).to("cuda:0")
    with torch.no_grad():
        _, embeddings = model(input_ids, return_embeddings=True, layer_names=[layer])
    return embeddings[layer][0, -1, :].to(torch.float32)


def w2_exon(model, classifier: ExonClassifier, positions_tsv: Path, out_tsv: Path) -> dict:
    positions = read_exon_positions(positions_tsv)
    torch.cuda.reset_peak_memory_stats()
    start = time.perf_counter()
    rows = []
    for i, row in enumerate(positions):
        embedding = torch.cat([
            _final_token_embedding(model, row["forward_seq"], pins.EXON_LAYER),
            _final_token_embedding(model, row["reverse_seq"], pins.EXON_LAYER),
        ])
        with torch.no_grad():
            probability = classifier(embedding.unsqueeze(0)).item()
        rows.append([i, row["gene_name"], row["label"], repr(probability), repr(embedding.norm().item())])
    torch.cuda.synchronize()
    seconds = time.perf_counter() - start
    with out_tsv.open("w", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["index", "gene_name", "label", "exon_probability", "embedding_norm"])
        writer.writerows(rows)
    return {
        "positions": len(rows),
        "sequence_length": len(positions[0]["forward_seq"]),
        "embedding_seconds": round(seconds, 3),
        "peak_memory_allocated_bytes": torch.cuda.max_memory_allocated(),
    }


def w3_memory_probe(model) -> list[dict]:
    """Single forward passes on growing synthetic sequences; stop at the first out-of-memory error."""
    results = []
    for length in pins.PROBE_LENGTHS:
        seq = synthetic_dna(length, pins.PROBE_SEED)
        input_ids = torch.tensor(model.tokenizer.tokenize(seq), dtype=torch.int).unsqueeze(0).to("cuda:0")
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
        start = time.perf_counter()
        try:
            with torch.inference_mode():
                logits, _ = model.model.forward(input_ids)
            torch.cuda.synchronize()
            results.append({
                "length": length, "status": "ok",
                "seconds": round(time.perf_counter() - start, 3),
                "peak_memory_allocated_bytes": torch.cuda.max_memory_allocated(),
            })
            del logits
        except torch.OutOfMemoryError as error:
            results.append({
                "length": length, "status": "out_of_memory",
                "peak_memory_allocated_bytes": torch.cuda.max_memory_allocated(),
                "message": str(error).splitlines()[0],
            })
            break
        finally:
            del input_ids
            torch.cuda.empty_cache()
    return results


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
