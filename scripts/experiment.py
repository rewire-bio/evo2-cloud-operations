"""Run the Evo 2 workloads on every configured platform, then assemble results.

This spends money: each platform launches a GPU machine. Credentials and accounts come from
the environment (AWS_PROFILE, GCP_PROJECT, RUNPOD_API_KEY), never from the repository.

  uv run --frozen python scripts/experiment.py --config configs/full.json --output results/full
  uv run --frozen python scripts/experiment.py --config configs/full.json --output results/full --collect-only
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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from data import verify_data  # noqa: E402
from collect import assemble  # noqa: E402

BUNDLE_DATA = {
    "prompts.csv": "data/raw/prompts.csv",
    "GRCh37.p13_chr17.fna.gz": "data/raw/GRCh37.p13_chr17.fna.gz",
    "samplePositions.tsv": "data/raw/samplePositions.tsv",
    "brca1_variants.tsv": "data/derived/brca1_variants.tsv",
}


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def build_bundle(bundle: Path, allow_dirty: bool) -> dict:
    """Code from the committed revision only, plus the verified inputs."""
    if git("status", "--porcelain", "--untracked-files=no") and not allow_dirty:
        raise SystemExit("Commit your changes first: runs use the committed revision only.")
    bundle.mkdir(parents=True, exist_ok=False)
    subprocess.run(["git", "archive", "--format=tar.gz", "-o", str(bundle / "code.tar.gz"), "HEAD", "src"],
                   cwd=ROOT, check=True)
    shutil.copy2(ROOT / "cloud/remote-run.sh", bundle / "remote-run.sh")
    (bundle / "data").mkdir()
    for name, source in BUNDLE_DATA.items():
        shutil.copy2(ROOT / source, bundle / "data" / name)
    return {
        "git_revision": git("rev-parse", "HEAD"),
        "code_sha256": sha256(bundle / "code.tar.gz"),
        "inputs_sha256": {name: sha256(bundle / "data" / name) for name in BUNDLE_DATA},
    }


def launch(platform: dict, image: str, bundle: Path, output: Path, code_sha: str, max_hours: int, attempts: int) -> dict:
    """Run one platform, retrying once on failure. Every attempt's directory is kept."""
    script = ROOT / "cloud" / platform["provider"] / "launch.sh"
    for attempt in range(1, attempts + 1):
        out = output / "platforms" / platform["id"] / f"attempt-{attempt}"
        out.mkdir(parents=True, exist_ok=False)
        env = {**os.environ, "PLATFORM_ID": platform["id"], "IMAGE_REF": image, "BUNDLE": str(bundle),
               "OUT": str(out), "CODE_SHA256": code_sha, "MAX_HOURS": str(max_hours)}
        env.update({k: str(v) for k, v in platform.get("env", {}).items()})
        with (out / "launcher.log").open("w") as log:
            status = subprocess.run(["bash", str(script)], env=env, stdout=log, stderr=subprocess.STDOUT).returncode
        (out / "launcher-exit.json").write_text(json.dumps({"exit_code": status}) + "\n")
        print(f"{platform['id']} attempt {attempt}: exit {status}", flush=True)
        if status == 0:
            return {"id": platform["id"], "attempts": attempt, "status": "completed"}
    return {"id": platform["id"], "attempts": attempts, "status": "failed"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--platforms", help="Comma-separated subset of platform IDs")
    parser.add_argument("--collect-only", action="store_true", help="Rebuild results from existing outputs")
    parser.add_argument("--allow-dirty", action="store_true", help="Smoke testing only; not for recorded runs")
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    if config.get("study_kind") != "evo2_cloud_operations":
        raise SystemExit("Unexpected study configuration")
    verify_data(ROOT / "data/manifest.json", ROOT)
    subprocess.run([sys.executable, str(ROOT / "scripts/prepare_inputs.py")], check=True)

    if not args.collect_only:
        platforms = config["platforms"]
        if args.platforms:
            wanted = set(args.platforms.split(","))
            platforms = [p for p in platforms if p["id"] in wanted]
        args.output.mkdir(parents=True, exist_ok=True)
        provenance = build_bundle(args.output / "bundle", args.allow_dirty)
        provenance.update({"image": config["image"], "config_sha256": sha256(args.config)})
        (args.output / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
        with ThreadPoolExecutor(len(platforms)) as pool:
            outcomes = list(pool.map(lambda p: launch(
                p, config["image"], args.output / "bundle", args.output, provenance["code_sha256"],
                config["max_hours"], config["max_attempts"]), platforms))
        (args.output / "launch-outcomes.json").write_text(json.dumps(outcomes, indent=2) + "\n")
        price_cmd = [sys.executable, str(ROOT / "scripts/prices.py"), "--output", str(args.output)]
        if os.environ.get("GCP_PROJECT"):
            price_cmd += ["--gcp-project", os.environ["GCP_PROJECT"]]
        subprocess.run(price_cmd, check=False)

    assemble(config, args.output, ROOT)
    print(args.output / "results.json")


if __name__ == "__main__":
    main()
