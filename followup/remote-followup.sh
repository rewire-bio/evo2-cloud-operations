#!/usr/bin/env bash
# Runs detached inside the pod: one fresh process per configuration, then writes DONE.
# Usage: VARIANTS="default:1,fp8off:1" bash remote-followup.sh
set -u
mkdir -p /work/out /work/hf
nvidia-smi --query-gpu=name,driver_version,memory.total,compute_cap --format=csv,noheader > /work/out/host.txt 2>&1
for spec in ${VARIANTS//,/ }; do
  variant=${spec%%:*} batch=${spec##*:}
  name="$variant-b$batch"
  python /work/code/followup/gpu_followup.py --variant "$variant" --batch-size "$batch" \
    --out "/work/out/$name" > "/work/out/$name.log" 2>&1 || echo "$name exited non-zero" >> /work/out/failures.txt
done
touch /work/out/DONE
