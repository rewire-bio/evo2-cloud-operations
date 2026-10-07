#!/usr/bin/env bash
# Runs on the GPU machine. Expects /work/code (study code), /work/data (inputs).
# Usage: remote-run.sh docker|direct IMAGE_REF PLATFORM_ID CODE_SHA256
#   docker: on a VM with Docker and the NVIDIA container toolkit (EC2, GCE)
#   direct: already inside the image (RunPod pod)
set -euo pipefail
mode=$1 image=$2 platform_id=$3 code_sha=$4
mkdir -p /work/out /work/hf

{
  echo "uname=$(uname -a)"
  nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
  df -h /work | tail -1
  free -g | sed -n 2p
} > /work/out/host.txt 2>&1 || true

run_workloads='cd /work && export PYTHONPATH=/work/code/src &&
  python -m evo2ops.run --workloads w0,w1,w3,w2 &&
  python -m evo2ops.run --workloads w4'

if [[ $mode == docker ]]; then
  command -v docker >/dev/null || { echo "Docker is not installed on this image" >&2; exit 2; }
  start=$SECONDS
  sudo docker pull "$image" > /work/out/docker-pull.log 2>&1
  echo "{\"docker_pull_s\": $((SECONDS - start))}" > /work/out/host-timings.json
  sudo docker run --rm --gpus all --ipc=host --ulimit memlock=-1 --ulimit stack=67108864 \
    -v /work:/work -e PLATFORM_ID="$platform_id" -e IMAGE_REF="$image" -e CODE_SHA256="$code_sha" \
    "$image" bash -c "$run_workloads" 2>&1 | tee /work/out/workloads.log
  sudo chown -R "$(id -u):$(id -g)" /work/out
else
  echo '{"docker_pull_s": null}' > /work/out/host-timings.json
  PLATFORM_ID="$platform_id" IMAGE_REF="$image" CODE_SHA256="$code_sha" \
    bash -c "$run_workloads" 2>&1 | tee /work/out/workloads.log
fi
