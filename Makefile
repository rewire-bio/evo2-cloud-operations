.PHONY: data inputs test experiment collect reproduce analysis paper

# Offline steps (no cloud spend)
data:
	uv run --frozen python scripts/data.py --fetch

inputs: data
	uv run --frozen python scripts/prepare_inputs.py

test: inputs
	uv run --frozen python -m unittest discover -s tests -v

collect:
	uv run --frozen python scripts/experiment.py --config configs/full.json --output results/full --collect-only

analysis:
	uv run --frozen python scripts/analyse.py --results results/full

paper:
	uv run --frozen python scripts/build_paper.py

# Paid steps: launches GPU machines on every configured platform.
# Needs AWS_PROFILE, GCP_PROJECT and RUNPOD_API_KEY in the environment.
experiment: test
	uv run --frozen python scripts/experiment.py --config configs/full.json --output results/full

reproduce: experiment analysis paper
